"""Data-driven connected walking routes and their structural companion.

Route elevation is shared by terrain, paving, planting exclusions and runtime QA.
Content positions and landmark designs remain in the scene contract.
"""
import math
import numpy as np
try:from .route_elevation import interpolate as interpolate_elevation
except ImportError:from route_elevation import interpolate as interpolate_elevation
try:
    from .planting_footprint import signed_distance, validate_place
except ImportError:
    from planting_footprint import signed_distance, validate_place


class RouteField:
    def __init__(self, config):
        self.config = config
        for place in config.get('places', []) + config.get('foundation_pads', []):validate_place(place)
        self.routes = []
        starts, ends, widths, route_ids = [], [], [], []
        self.route_widths = []
        for route in config.get('routes', []):
            controls = np.array(route['points'], dtype=float)
            if len(controls) < 2 or route['width'] < 2:
                raise ValueError('Exploration routes require two points and a 2m walking width')
            points = []
            for i in range(len(controls)-1):
                a,b = controls[i],controls[i+1]
                before=controls[max(0,i-1)];after=controls[min(len(controls)-1,i+2)]
                count=max(2,math.ceil(np.linalg.norm((b-a)[:2])/1.0))
                for j in range(count):
                    t=j/count
                    p=.5*((2*a)+(-before+b)*t+(2*before-5*a+4*b-after)*t*t+(-before+3*a-3*b+after)*t*t*t)
                    # A two-control edge is a straight segment. Easing XY while
                    # interpolating Z linearly falsely steepens ramp endpoints.
                    if len(controls)==2:p=a+(b-a)*t
                    p[2]=interpolate_elevation(controls,i,t)
                    points.append(p)
            points.append(controls[-1]);points=np.array(points)
            distances=np.r_[0,np.cumsum(np.linalg.norm(np.diff(points[:,:2],axis=0),axis=1))]
            profile=route.get('width_profile',[route['width'],route['width']])
            sampled_widths=np.interp(distances/max(.001,distances[-1]),np.linspace(0,1,len(profile)),profile)
            self.route_widths.append(sampled_widths)
            route_ids.extend([len(self.routes)]*(len(points)-1))
            self.routes.append((route,points))
            starts.extend(points[:-1]);ends.extend(points[1:]);widths.extend((sampled_widths[:-1]+sampled_widths[1:])*.5)
        self.a=np.array(starts);self.d=np.array(ends)-self.a;self.widths=np.array(widths)
        self.route_ids=np.array(route_ids,dtype=int)
        self.lengths=(self.d[:,:2]**2).sum(1) if starts else np.array([])
        self._route_subsets={}

    def nearest(self,x,y):
        return self.query(x,y)[:3]

    def query(self,x,y,route_names=None):
        if not len(self.a):return 1e6,0,0,-1
        if route_names is None:a,d,lengths,widths,route_ids=self.a,self.d,self.lengths,self.widths,self.route_ids
        else:
            key=tuple(sorted(route_names))
            if key not in self._route_subsets:
                ids=[i for i,(r,points) in enumerate(self.routes) if r.get('id') in key];mask=np.isin(self.route_ids,ids)
                self._route_subsets[key]=(self.a[mask],self.d[mask],self.lengths[mask],self.widths[mask],self.route_ids[mask])
            a,d,lengths,widths,route_ids=self._route_subsets[key]
            if not len(a):return 1e6,0,0,-1
        q=np.array([x,y])-a[:,:2]
        t=np.clip((q*d[:,:2]).sum(1)/np.maximum(.001,lengths),0,1)
        dist=((q-t[:,None]*d[:,:2])**2).sum(1)
        i=int(dist.argmin())
        return math.sqrt(dist[i]),float(a[i,2]+t[i]*d[i,2]),float(widths[i]),int(route_ids[i])

    def height(self,x,y,base):
        dist,z,width=self.nearest(x,y)
        w=max(0,min(1,(width*.5+4.5-dist)/4.5));w=w*w*(3-2*w)
        result=base*(1-w)+z*w
        for place in self.config.get('foundation_pads',[])+self.config.get('places',[]):
            if not place.get('flatten',True):continue
            px,py,pz=place['center']
            distance=signed_distance(x,y,place['outline']) if place.get('outline') else math.hypot(x-px,y-py)-place['radius']
            fade=place.get('edge_fade_m',3)
            w=max(0,min(1,1-distance/max(.1,fade)));w=w*w*(3-2*w)
            result=result*(1-w)+pz*w
        return result

    def clear(self,x,y,margin=0):
        d,z,w=self.nearest(x,y)
        if d<w*.5+margin:return True
        for p in self.config.get('places',[])+self.config.get('foundation_pads',[]):
            if p.get('clear_outline'):
                if signed_distance(x,y,p['clear_outline'])<=margin:return True
            elif math.hypot(x-p['center'][0],y-p['center'][1])<p.get('clear_radius',p['radius'])+margin:return True
        return False


def build(api):
    if api['route_field'].config.get('composition_version',1)>=2:
        from landscape_routes import build as build_landscape_routes
        return build_landscape_routes(api)
    field=api['route_field'];cfg=field.config;rng=api['rng'];height=api['height']
    block=api['block'];mesh=api['mesh'];mat=cfg['paving_material'];slabs=0
    for route,points in field.routes:
        for j in range(len(points)-1):
            p,q=points[j],points[j+1];delta=q-p;length=float(np.linalg.norm(delta[:2]));yaw=math.atan2(delta[1],delta[0]);side=np.array([-math.sin(yaw),math.cos(yaw),0])
            cols=max(2,round(route['width']/.83))
            for k in range(cols):
                # Worn slabs taper into the planted shoulders, never into a hard rectangle.
                if (k in [0,cols-1] and rng.random()<.28) or rng.random()<.08:continue
                pos=(p+q)*.5+side*((k+.5)*route['width']/cols-route['width']/2)
                if any(math.hypot(pos[0]-v['center'][0],pos[1]-v['center'][1])<v['radius']+.15 for v in cfg.get('places',[])):continue
                top=height(pos[0],pos[1])+.07
                ob=block((pos[0],pos[1],top-.07),(length-.024,route['width']/cols-.027,.14),mat,yaw+rng.uniform(-.025,.025),.012)
                slabs+=1
    # Local courts have a coherent perimeter and fitted irregular slabs.
    from courtyard import fitted_court
    for place in cfg.get('places',[]):
        x,y,z=place['center'];r=place['radius'];before={o for v in api['groups'].values() for o in v}
        local=dict(api);local['center']=[x,y];local['court']=lambda xx,yy:math.hypot(xx-x,yy-y)/r
        local['cfg']={**api['cfg'],'court_radii':[r,r],'paver_spacing':.94,'scatter':{}}
        slabs+=fitted_court(local)
        for objects in api['groups'].values():
            for ob in objects:
                if ob not in before:ob.location.z+=z-.06
        # Low, segmented seating walls leave both the route and view open.
        for aa,bb in place.get('wall_arcs',[]):
            count=max(3,round(math.radians(bb-aa)*r/.8))
            for row in range(2):
                for j in range(count):
                    a=math.radians(aa)+(j/count)*math.radians(bb-aa);b=a+math.radians(bb-aa)/count-.008
                    mid=(a+b)/2;dist,_,width=field.nearest(x+(r+.36)*math.cos(mid),y+(r+.36)*math.sin(mid))
                    if dist<width/2+.85:continue
                    api['wedge'](x,y,z+.20+row*.34,r+.1,r+.62,a+.004,b,.32,cfg['wall_material'])
        if place.get('well'):
            # A solid, dry stone basin at the edge, clear of the walking line.
            wx,wy=place['well'];zz=height(wx,wy)
            for row in range(3):
                for j in range(16):
                    a=j*math.tau/16+(row%2)*.09
                    api['wedge'](wx,wy,zz+.14+row*.24,.68,1.12,a+.007,a+math.tau/16-.007,.23,cfg['wall_material'])
            api['cylinder']((wx,wy,zz+.03),.70,.12,api['spec']['floor_material'])
    # Scan clusters describe the route margins, keeping the actual corridor clear.
    for route,points in field.routes:
        for j in range(2,len(points)-2,3):
            p=points[j];delta=points[j+1]-points[j-1];yaw=math.atan2(delta[1],delta[0]);side=np.array([-math.sin(yaw),math.cos(yaw),0])
            for sign in [-1,1]:
                pos=p+side*sign*(route['width']/2+rng.uniform(.7,2.7))
                if field.clear(*pos[:2],.25):continue
                if j%9==2:
                    s=rng.uniform(1.8,3.5);h=s*.55
                    api['instance'](cfg['rock_asset'],(pos[0],pos[1],height(*pos[:2])-h*.32),(s,s*.78,h),yaw,j,True)
                for k in range(9):
                    x=pos[0]+rng.uniform(-1.6,1.6);y=pos[1]+rng.uniform(-1.6,1.6)
                    if field.clear(x,y,.20):continue
                    s=rng.uniform(.4,.92)
                    api['instance'](cfg['plant_asset'],(x,y,height(x,y)-.018),(s,s,s*.82),rng.uniform(0,math.tau),k,False)
    qa=[]
    # Every fourth sample is close enough to follow the curves without corner cutting.
    for route,points in field.routes:
        qa.extend([list(map(float,p)) for p in points[::4]])
        qa.append(list(map(float,points[-1])))
    max_grade=max(abs(d[2])/max(.01,np.linalg.norm(d[:2])) for d in field.d)
    if max_grade>.30:raise ValueError('Walking route exceeds 30 percent grade')
    return {'route_length_m':float(sum(np.sqrt(field.lengths))),'paving_slabs':slabs,'max_grade':float(max_grade),
            'waypoints_m':qa,'places':cfg['places'],'encounter_radius_m':cfg.get('encounter_radius_m',12),
            'play_bounds':cfg['play_bounds']}


def whitebox(api,helpers):
    if api['route_field'].config.get('composition_version',1)>=2:
        from landscape_routes import whitebox as build_landscape_whitebox
        return build_landscape_whitebox(api,helpers)
    field=api['route_field'];mesh=helpers['mesh'];disc=helpers['disc'];wedge=helpers['wedge']
    for route,points in field.routes:
        vs=[]
        for i,p in enumerate(points):
            delta=points[min(len(points)-1,i+1)]-points[max(0,i-1)]
            d=np.array([-delta[1],delta[0],0]);d=d/max(.001,np.linalg.norm(d))
            for sign in [-1,1]:
                q=p+d*sign*route['width']/2;vs.append((q[0],q[1],api['height'](q[0],q[1])+.07))
        mesh('walking route',vs,[(2*i,2*i+1,2*i+3,2*i+2) for i in range(len(points)-1)])
    for place in field.config.get('places',[]):
        x,y,z=place['center'];r=place['radius'];disc('landmark court',x,y,z+.075,r,r,.14)
        for aa,bb in place.get('wall_arcs',[]):
            count=max(3,round(math.radians(bb-aa)*r/.8))
            for j in range(count):
                a=math.radians(aa)+j/count*math.radians(bb-aa);b=a+math.radians(bb-aa)/count
                mid=(a+b)/2;dist,_,width=field.nearest(x+(r+.36)*math.cos(mid),y+(r+.36)*math.sin(mid))
                if dist<width/2+.85:continue
                wedge('seating wall',x,y,z+.38,r+.1,r+.62,a,b,.66,2)
        if place.get('well'):
            x,y=place['well'];wedge('well',x,y,api['height'](x,y)+.38,.68,1.12,0,math.tau,.74)
