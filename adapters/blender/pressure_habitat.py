"""Metric pressure-room shells with real door gaps and a structural companion.

The same geometry program serves submarine, orbital or industrial interiors.
Identities, material roles, dimensions and connected room placements are data.
"""
import math
FACES=[(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]

def validate(config):
    if not isinstance(config,dict) or not 1<=len(config.get('rooms',[]))<=24:raise ValueError('Habitat requires 1-24 room modules')
    names=set()
    for room in config['rooms']:
        if not isinstance(room.get('id'),str) or room['id'] in names:raise ValueError('Room identities must be unique')
        names.add(room['id'])
        if type(room.get('rounded_pressure_portals',False)) is not bool:raise ValueError('Rounded pressure portal selection must be boolean')
        if type(room.get('flanged_ribs',False)) is not bool:raise ValueError('Flanged rib selection must be boolean')
        if type(room.get('bulkhead_services',False)) is not bool:raise ValueError('Bulkhead service selection must be boolean')
        for key in ['center','size']:
            if len(room.get(key,[]))!=2 or any(type(v) not in (int,float) or not math.isfinite(v) for v in room[key]):raise ValueError('Room '+key+' needs finite XY metres')
        if any(not 3<=v<=40 for v in room['size']):raise ValueError('Room span must be 3-40m')
        for key,lo,hi,default in [('base_z',-20,30,0),('wall_height',3,12,4.2),('roof_rise',.3,12,4),('slope_y',-.3,.3,0),('roof_glass_fraction',.25,1,1),('rib_width',.12,.6,.20),('rib_depth',.12,.6,.22),('opaque_panel_span_m',1.8,8,2.7)]:
            value=room.get(key,default)
            if type(value) not in (int,float) or not math.isfinite(value) or not lo<=value<=hi:raise ValueError('Invalid room '+key)
        if not all(room.get(k) for k in ['deck_material','frame_material','shell_material','glass_material','trim_material','light_material']):raise ValueError('Room material role missing')
        for door in room.get('doors',[]):
            if door.get('side') not in ['west','east','north','south']:raise ValueError('Unknown room side')
            span=room['size'][1 if door['side'] in ['east','west'] else 0]
            if not 2.4<=door.get('width',0)<=10 or abs(door.get('offset',0))+door['width']/2>span/2-.15:raise ValueError('Door must fit inside the wall with usable clearance')
            if not 2.6<=door.get('height',4)<=room.get('wall_height',4.2):raise ValueError('Door head clearance is invalid')
    return config

def build(api,proxy=False):
    config=validate(api['cfg']['pressure_habitat']);result=[];flanges=set()
    for room in config['rooms']:
        cx,cy=room['center'];w,d=room['size'];base=room.get('base_z',0);h=room.get('wall_height',4.2);rise=room.get('roof_rise',4)
        slope=room.get('slope_y',0);deck=room['deck_material'];frame=room['frame_material'];shell=room['shell_material'];glass=room['glass_material'];trim=room['trim_material'];lamp=room['light_material']
        count=0
        def world(p):return (p[0]+cx,p[1]+cy,p[2]+base+slope*(p[1]+d/2))
        def mesh(name,vs,fs,material,collision=True):
            nonlocal count
            if proxy and material==glass:return None
            count+=1
            ob=api['mesh']('Habitat '+room['id']+' '+name,[world(p) for p in vs],fs,material,collision=collision,smooth_faces=False)
            if not proxy and material!=glass and 'finish_stone' in api:api['finish_stone'](ob,.012)
            return ob
        def box(name,x,y,z,dx,dy,dz,material,collision=True):
            return mesh(name,[(x+xx*dx/2,y+yy*dy/2,z+zz*dz/2) for zz in [-1,1] for xx,yy in [(-1,-1),(1,-1),(1,1),(-1,1)]],FACES,material,collision)
        def beam(name,a,b,width,depth,material):
            delta=[b[i]-a[i] for i in range(3)];length=math.sqrt(sum(v*v for v in delta));axis=[v/length for v in delta]
            side=[-axis[1],axis[0],0]
            if math.hypot(*side[:2])<.001:side=[1,0,0]
            length2=math.sqrt(sum(v*v for v in side));side=[v/length2 for v in side]
            up=[axis[1]*side[2]-axis[2]*side[1],axis[2]*side[0]-axis[0]*side[2],axis[0]*side[1]-axis[1]*side[0]]
            if not proxy and name=='vault pressure rib' and room.get('flanged_ribs',False):
                # A structural I section, not a decorative black curtain-wall line.
                for label,ww,dd,shift in [('web',width*.24,depth,0),('upper flange',width,depth*.14,depth*.43),('lower flange',width,depth*.14,-depth*.43)]:
                    vs=[tuple(p[i]+s*side[i]*ww/2+(t*dd/2+shift)*up[i] for i in range(3)) for p in [a,b] for s,t in [(-1,-1),(1,-1),(1,1),(-1,1)]]
                    mesh(name+' '+label,vs,FACES,material)
                return
            vs=[tuple(p[i]+s*side[i]*width/2+t*up[i]*depth/2 for i in range(3)) for p in [a,b] for s,t in [(-1,-1),(1,-1),(1,1),(-1,1)]]
            return mesh(name,vs,FACES,material)
        def tube(name,a,b,radius,material):
            delta=[b[i]-a[i] for i in range(3)];length=math.sqrt(sum(v*v for v in delta));axis=[v/length for v in delta]
            side=[-axis[1],axis[0],0]
            if math.hypot(*side[:2])<.001:side=[1,0,0]
            size=math.sqrt(sum(v*v for v in side));side=[v/size for v in side]
            up=[axis[1]*side[2]-axis[2]*side[1],axis[2]*side[0]-axis[0]*side[2],axis[0]*side[1]-axis[1]*side[0]]
            n=24;vs=[tuple(p[k]+radius*(math.cos(math.tau*i/n)*side[k]+math.sin(math.tau*i/n)*up[k]) for k in range(3)) for p in [a,b] for i in range(n)]
            fs=[(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]+[tuple(reversed(range(n))),tuple(range(n,2*n))]
            mesh(name,vs,fs,material,False)
        # Continuous dry support. Surface panels are flush with its top.
        box('dry structural deck',0,0,-.20,w,d,.40,deck)
        if not proxy:
            nx=max(2,math.ceil(w/1.45));ny=max(2,math.ceil(d/1.45))
            for j in range(ny):
                for i in range(nx):
                    x=-w/2+(i+.5)*w/nx;y=-d/2+(j+.5)*d/ny
                    box('fitted deck panel',x,y,.006,w/nx-.018,d/ny-.018,.012,deck)
                    if i in [0,nx-1] and j%2==0:
                        box('recessed service hatch',x,y,.014,w/nx*.64,d/ny*.65,.012,frame)
            for side in [-1,1]:box('deck edge safety strip',side*(w/2-.42),0,.018,.065,d-.5,.012,trim,False)
        # Walls are split at exact doorway edges. No solid full-wall collider
        # is left behind an apparently open decorative arch.
        for side in ['west','east','south','north']:
            span=d if side in ['west','east'] else w
            doors=[q for q in room.get('doors',[]) if q['side']==side]
            cuts=sorted(set([-span/2,span/2]+[q.get('offset',0)+sign*q['width']/2 for q in doors for sign in [-1,1]]))
            glazed=side in room.get('glazed_sides',['west','east','north','south'])
            def wall_piece(label,a,b,z,dz,material,thick=.22):
                if b-a<.005 or dz<.005:return
                mid=(a+b)/2
                if side in ['west','east']:box(label,(-1 if side=='west' else 1)*w/2,mid,z,thick,b-a,dz,material)
                else:box(label,mid,(-1 if side=='south' else 1)*d/2,z,b-a,thick,dz,material)
            for a,b in zip(cuts,cuts[1:]):
                mid=(a+b)/2;door=next((q for q in doors if abs(mid-q.get('offset',0))<q['width']/2-.001),None)
                if door:
                    dh=door.get('height',4);wall_piece('pressure-door header',a,b,(h+dh)/2,h-dh,frame,.40)
                    for edge in [a,b]:wall_piece('gasketed door jamb',edge-.10,edge+.10,dh/2,dh,frame,.42)
                    wall_piece('header status light',a+.18,b-.18,dh+.09,.055,lamp,.43)
                    if room.get('rounded_pressure_portals',False):
                        xy=((-1 if side=='west' else 1)*w/2,mid) if side in ['west','east'] else (mid,(-1 if side=='south' else 1)*d/2)
                        identity=tuple(round(v,3) for v in world((*xy,0)))
                        if identity not in flanges:
                            flanges.add(identity)
                            for ring,(outer,inner,depth,material) in enumerate([(1,.90,.34,frame),(.96,.925,.39,trim)]):
                                vs=[];n=40
                                for dep in [-depth/2,depth/2]:
                                    for radius in [outer,inner]:
                                        for k in range(n):
                                            theta=math.tau*k/n;u=mid+math.cos(theta)*(b-a)/2*radius;zz=dh/2+.10+math.sin(theta)*dh/2*radius
                                            vs.append((xy[0]+dep,u,zz) if side in ['west','east'] else (u,xy[1]+dep,zz))
                                fs=[]
                                for k in range(n):
                                    j=(k+1)%n;fs.extend([(k,j,j+n,k+n),(k+2*n,k+3*n,j+3*n,j+2*n),(k,k+2*n,j+2*n,j),(k+n,j+n,j+3*n,k+3*n)])
                                mesh('rounded pressure-door flange '+str(ring),vs,fs,material)
                    if 'portal_tests' in api:
                        x=(-w/2 if side=='west' else w/2) if side in ['west','east'] else mid
                        y=mid if side in ['west','east'] else (-d/2 if side=='south' else d/2)
                        direction=(1,0,0) if side in ['west','east'] else (0,1,0)
                        p=world((x,y,1.2));origin=[p[i]-direction[i]*.7 for i in range(3)]
                        api['portal_tests'].append({'name':room['id']+' '+side,'origin_m':origin,'direction':direction,'distance_m':1.4,'clear_width_m':door['width']-.2})
                    continue
                wall_piece('sealed lower pressure hull',a,b,.53,1.06,shell,.28)
                wall_piece('upper sealed infill',a,b,(h+1.08)/2,h-1.08,glass if glazed else shell,.045 if glazed else .22)
                subdivisions=max(1,math.ceil((b-a)/(2.7 if glazed else room.get('opaque_panel_span_m',2.7))))
                for j in range(subdivisions+1):
                    at=a+(b-a)*j/subdivisions;wall_piece('reinforced vertical mullion',at-.075,at+.075,h/2,h,frame,.35)
                    if room.get('bulkhead_services') and not glazed:
                        wall_piece('deep welded bulkhead web',at-.09,at+.09,h/2,h,frame,.60)
                        wall_piece('pressure bulkhead flange face',at-.20,at+.20,h/2,h,frame,.68)
                        if not proxy:
                            for zz in [.35,.85,1.35,1.85,2.35,2.85,h-.30]:
                                wall_piece('structural flange fastener',at-.045,at+.045,zz,.09,trim,.71)
                for z in [1.07,h-.05]:wall_piece('continuous seal rail',a,b,z,.10,frame,.35)
                if not proxy:
                    wall_piece('interior service conduit',a,b,h-.38,.065,trim,.38)
                    if not glazed:
                        wall_piece('bolted horizontal panel flange',a,b,h*.54,.06,frame,.34)
                        for j in range(subdivisions):
                            at=a+(b-a)*(j+.5)/subdivisions
                            wall_piece('recessed service access panel',at-.42,at+.42,h*.54+.52,.76,room.get('inset_material',shell),.31)
                            for xx in [-.37,.37]:
                                for zz in [-.30,.30]:wall_piece('access-panel fastener',at+xx-.025,at+xx+.025,h*.54+.52+zz,.05,frame,.335)
        # A segmented elliptical glass pressure vault. Both camera families
        # can see through it; no camera-specific disappearing opaque ceiling.
        ns=16 if not proxy else 10
        profile=[(-w/2*math.cos(math.pi*i/ns),h+rise*math.sin(math.pi*i/ns)) for i in range(ns+1)]
        stations=max(2,math.ceil(d/3.5))
        for j in range(stations+1):
            y=-d/2+d*j/stations
            for i in range(ns):
                x0,z0=profile[i];x1,z1=profile[i+1]
                beam('vault pressure rib',(x0,y,z0),(x1,y,z1),room.get('rib_width',.20),room.get('rib_depth',.22),frame)
        for i,(x,z) in enumerate(profile):
            if i%2==0:beam('longitudinal seal frame',(x,-d/2,z),(x,d/2,z),.10,.12,frame)
        for i in range(ns):
            x0,z0=profile[i];x1,z1=profile[i+1]
            vs=[(x0,-d/2,z0),(x1,-d/2,z1),(x1,d/2,z1),(x0,d/2,z0)]
            transmitting=abs((x0+x1)/2)<=w*room.get('roof_glass_fraction',1)/2
            if transmitting:
                if not proxy:mesh('sealed roof glazing',vs,[(0,1,2,3)],glass)
            else:
                mesh('insulated pressure roof panel',vs+[(x,y,z-.12) for x,y,z in vs],FACES,shell)
        if not proxy:
            # End-cap glazing follows the exact arch instead of an open triangle.
            for y in [-d/2,d/2]:
                for i in range(ns):
                    x0,z0=profile[i];x1,z1=profile[i+1]
                    mesh('arched sealed endcap',[(x0,y,h),(x1,y,h),(x1,y,z1),(x0,y,z0)],[(0,1,2,3)],glass)
            # Small connected equipment rails and ceiling lights, outside routes.
            for side in [-1,1]:
                for j in range(stations):
                    y=-d/2+(j+.5)*d/stations;x=side*(w/2-.3)
                    box('fixture housing',x,y,h-.64,.18,.92,.16,frame,False)
                    box('warm caged fixture',x-side*.10,y,h-.64,.045,.72,.09,lamp,False)
            for x in [-w*.24,w*.24]:
                beam('connected overhead cable tray',(x,-d/2,h+rise*.65),(x,d/2,h+rise*.65),.18,.12,shell)
            if room.get('bulkhead_services'):
                for side in [-1,1]:
                    for k in range(3):
                        x=side*(w/2-.55-k*.25);z=h-.32-k*.11
                        tube('continuous pressure service pipe',(x,-d/2+.25,z),(x,d/2-.25,z),.085 if k==0 else .055,frame if k!=1 else trim)
                        # Short supported drops and visible clamps connect the
                        # ceiling service bank to each end bulkhead.
                        for y in [-d/2+.45,d/2-.45]:
                            tube('pressure service downfeed',(x,y,z),(x,y,z-1.10),.075 if k==0 else .05,frame)
                    for j in range(stations):
                        y=-d/2+(j+.5)*d/stations
                        box('wall ceiling knee bracket',side*(w/2-.30),y,h-.65,.45,.23,.70,frame)
                        box('service bank support clamp',side*(w/2-.77),y,h-.48,1.1,.09,.07,trim,False)
        # Real support columns link the dry deck to the surrounding foundation.
        for x in [-w/2+.7,w/2-.7]:
            for y in [-d/2+.7,d/2-.7]:
                bottom=api['height'](cx+x,cy+y)-base-slope*(y+d/2)-.3
                if bottom<-.4:box('external support pylon',x,y,(bottom-.3)/2,.48,.48,-.3-bottom,frame)
        result.append({'id':room['id'],'center':room['center'],'size':room['size'],'base_z':base,'slope_y':slope,'doors':len(room.get('doors',[])),'parts':count,'dry_support':True,'glazing':'non-refractive transmissive shell'})
    return result
