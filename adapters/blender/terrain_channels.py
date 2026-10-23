"""Bounded landscape channels with an opaque paired surface and shared bed."""
import math

def validate(items):
    if not isinstance(items,list):raise ValueError('terrain_channels must be an array')
    for item in items:
        points=item.get('points',[])
        if not 2<=len(points)<=20 or any(len(p)!=2 or any(type(v) not in (float,int) or not math.isfinite(v) for v in p) for p in points):raise ValueError('Channel needs finite XY points')
        if any(math.dist(a,b)<.5 for a,b in zip(points,points[1:])):raise ValueError('Channel control points must be separated')
        if not 1<=item.get('width',0)<=20 or not .1<=item.get('bed_depth',0)<=5 or not .5<=item.get('bank_width',0)<=10:raise ValueError('Invalid channel dimensions')
        if type(item.get('surface_z')) not in (int,float) or not math.isfinite(item['surface_z']):raise ValueError('Invalid channel elevation')
        if not item.get('material'):raise ValueError('Channel surface material required')
        if not 0<=item.get('edge_variation',0)<=.25:raise ValueError('Channel edge variation must stay within 25 percent')
        if 'integrated_banks' in item and type(item['integrated_banks']) is not bool:raise ValueError('integrated_banks must be boolean')
        if item.get('coping_material') and not item.get('integrated_banks'):raise ValueError('Coping requires integrated banks')
    return items

def bank_outline(c,extra=0.):
    """Continuous ribbon with rounded terminal banks; no exposed square caps."""
    controls=c['points'];points=[]
    for a,b in zip(controls,controls[1:]):
        count=max(1,math.ceil(math.dist(a,b)/.65))
        points.extend([(a[0]+(b[0]-a[0])*j/count,a[1]+(b[1]-a[1])*j/count) for j in range(count)])
    points.append(controls[-1]);left=[];right=[];angles=[]
    for i,p in enumerate(points):
        a=points[max(0,i-1)];b=points[min(len(points)-1,i+1)];angle=math.atan2(b[1]-a[1],b[0]-a[0]);angles.append(angle)
        r=half_width(c,*p)+extra;nx,ny=-math.sin(angle),math.cos(angle)
        left.append((p[0]+nx*r,p[1]+ny*r));right.append((p[0]-nx*r,p[1]-ny*r))
    end=points[-1];start=points[0];re=half_width(c,*end)+extra;rs=half_width(c,*start)+extra
    endcap=[(end[0]+re*math.cos(angles[-1]+math.pi/2-j*math.pi/18),end[1]+re*math.sin(angles[-1]+math.pi/2-j*math.pi/18)) for j in range(1,18)]
    startcap=[(start[0]+rs*math.cos(angles[0]-math.pi/2-j*math.pi/18),start[1]+rs*math.sin(angles[0]-math.pi/2-j*math.pi/18)) for j in range(1,18)]
    return list(reversed(left+endcap+list(reversed(right))+startcap))

def integrated_bank_meshes(api,c):
    # Extend the water underneath the bank. Detailed terrain supplies the final
    # shoreline through depth occlusion, using the same excavation function.
    outline=bank_outline(c,c['bank_width']);z=c['surface_z']
    api['mesh']('Terrain integrated water',[(x,y,z) for x,y in outline],[tuple(range(len(outline)))],c['material'],smooth_faces=False,preserve_winding=True)
    if not c.get('coping_material'):return
    edge=bank_outline(c,c['bank_width']*.42);field=api['route_field'];faces=[(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]
    for a,b in zip(edge,edge[1:]+edge[:1]):
        length=math.dist(a,b)
        if length<1e-6:continue
        count=max(1,math.ceil(length/.82));dx,dy=(b[0]-a[0])/length,(b[1]-a[1])/length
        for i in range(count):
            t=(i+.5)/count;x=a[0]+(b[0]-a[0])*t;y=a[1]+(b[1]-a[1])*t
            if field.clear(x,y,.65):continue
            width=.46;half=length/count*.5;top=max(z+.30,api['height'](x,y)+.07);bottom=z-c['bed_depth']-.18
            for lo,hi,wide,label in [(bottom,top-.07,width,'Pool retaining wall'),(top-.07,top,width+.16,'Pool stone coping')]:
                vs=[(x+u*dx-v*dy,y+u*dy+v*dx,zz) for zz in [lo,hi] for u,v in [(-half,-wide/2),(half,-wide/2),(half,wide/2),(-half,wide/2)]]
                api['mesh'](label,vs,faces,c['coping_material'],smooth_faces=False)

def half_width(c,x,y):
    return c['width']*.5*(1+c.get('edge_variation',0)*(.65*math.sin(x*.63+y*.49)+.35*math.sin(y*1.37-x*.21)))

def bed(items,x,y,z):
    for c in items:
        distance=1e9;nearest=(x,y)
        for a,b in zip(c['points'],c['points'][1:]):
            dx=b[0]-a[0];dy=b[1]-a[1];t=max(0,min(1,((x-a[0])*dx+(y-a[1])*dy)/(dx*dx+dy*dy)))
            here=math.hypot(x-a[0]-t*dx,y-a[1]-t*dy)
            if here<distance:distance=here;nearest=(a[0]+t*dx,a[1]+t*dy)
        edge=half_width(c,*nearest);fade=max(0,min(1,(edge+c['bank_width']-distance)/c['bank_width']))
        fade=fade*fade*(3-2*fade);target=c['surface_z']-c['bed_depth']
        z=z*(1-fade)+min(z,target)*fade
    return z

def build(api):
    for c in validate(api['cfg'].get('terrain_channels',[])):
        if c.get('integrated_banks'):
            integrated_bank_meshes(api,c);continue
        # Overlapping quads are avoided: one connected strip with shared corners.
        points=c['points'];v=[];colors=[]
        cross=[-1,-.76,0,.76,1] if c.get('frost_banks',False) else [-1,1]
        if c.get('edge_variation',0):
            dense=[]
            for a,b in zip(points,points[1:]):
                steps=max(1,math.ceil(math.dist(a,b)/.7))
                dense.extend([[a[k]+(b[k]-a[k])*j/steps for k in range(2)] for j in range(steps)])
            points=dense+[points[-1]]
        for i,p in enumerate(points):
            a=points[max(0,i-1)];b=points[min(len(points)-1,i+1)]
            dx=b[0]-a[0];dy=b[1]-a[1];n=math.hypot(dx,dy)
            width=half_width(c,*p)
            for sign in cross:
                v.append((p[0]-sign*dy/n*width,p[1]+sign*dx/n*width,c['surface_z']))
                colors.append((abs(sign)**5,0,0,1))
        stride=len(cross)
        faces=[(i*stride+j,(i+1)*stride+j,(i+1)*stride+j+1,i*stride+j+1) for i in range(len(points)-1) for j in range(stride-1)]
        kwargs={'colors':colors} if c.get('frost_banks',False) else {}
        api['mesh']('Continuous opaque channel surface',v,faces,c['material'],smooth_faces=False,preserve_winding=True,**kwargs)
