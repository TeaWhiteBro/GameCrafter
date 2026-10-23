"""Distinct architectural destinations and their matching coarse structures.

Locations, dimensions and materials are content data. The same construction
functions produce detailed masonry and the simplified structural companion.
"""
import math
import numpy as np
try:
    from .ground_support import footing_bottom
except ImportError:  # Blender's standalone script entry point.
    from ground_support import footing_bottom

FACES=[(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]

def validate(items):
    if not isinstance(items,list):raise ValueError('destination_details must be an array of objects with a kind field, not a kind-keyed object')
    required={'vault_liner':['radius','rise'],'bell_tower':['roof_material'],
              'herb_bed':['soil_material','plant_asset'],
              'terraced_foundation':['size','rise'],
              'belvedere':['timber_material','roof_material'], 'footbridge':['size','timber_material'],
              'timber_hall':['size','timber_material','roof_material'],
              'forge_hearth':['size','height','metal_material'],
              'workshop_station':['size','timber_material','metal_material'],
              'bell_rack':['size','timber_material','metal_material']}
    required['overlook_terrace']=['size','timber_material']
    required['hoist_station']=['size','timber_material','metal_material']
    required['dry_garden']=['size','surface_material']
    required['garden_basin']=['radius']
    required['mast_footing']=['radius','height','base_z','metal_material','material']
    required['masonry_gallery']=['size','height','roof_material']
    required['masonry_tower']=['size','height','roof_material']
    for item in items:
        if not isinstance(item,dict):raise ValueError('Each destination_details entry must be an object with kind and center')
        kind=item.get('kind')
        if kind not in required:raise ValueError('Unknown destination detail: '+str(kind))
        if len(item.get('center',[]))!=2 or not all(isinstance(v,(int,float)) and math.isfinite(v) for v in item['center']):raise ValueError('Destination requires finite XY centre')
        for key in required[kind]:
            if key not in item:raise ValueError(kind+' missing '+key)
        for key in ['width','height','radius','rise','stair_run','plant_size','roof_rise']:
            if key in item and (not isinstance(item[key],(int,float)) or not math.isfinite(item[key]) or item[key]<=0):raise ValueError('Invalid positive dimension '+key)
        if 'size' in item and (len(item['size'])!=2 or any(not isinstance(v,(int,float)) or not math.isfinite(v) or v<=.4 for v in item['size'])):raise ValueError('Invalid destination size')
        if kind in ('masonry_gallery','masonry_tower'):
            try:from .masonry_destinations import validate as validate_masonry
            except ImportError:from masonry_destinations import validate as validate_masonry
            validate_masonry(item)
        if kind=='bell_tower':
            if item.get('height',8.7)<=3:raise ValueError('Belfry needs positive lower walls')
            if not 1.5<=item.get('width',3.4)<=4.8:raise ValueError('Belfry width must be 1.5-4.8m to fit its 2.5m arched upper openings; larger towers need a different module')
        if kind=='forge_hearth' and (not 2.5<=item['size'][0]<=5 or not 2<=item['size'][1]<=5 or not 4<=item['height']<=10):
            raise ValueError('Forge hearth needs width 2.5-5m, depth 2-5m and chimney height 4-10m')
        if kind=='bell_rack' and (not 2.5<=item['size'][0]<=5 or not 1<=item['size'][1]<=3 or not 2.5<=item.get('height',3.3)<=5):
            raise ValueError('Bell rack needs space for its hollow casting and supports')
        if kind=='workshop_station' and (not 1.8<=item['size'][0]<=5 or not .8<=item['size'][1]<=2.4):
            raise ValueError('Workshop station needs a practical bench footprint')
        if kind=='hoist_station' and (not 2.4<=item['size'][0]<=5 or not 1.8<=item['size'][1]<=4 or not 2.6<=item.get('height',3.4)<=5):
            raise ValueError('Hoist station needs a supported working footprint and overhead clearance')
        if item.get('trellis') and not item.get('timber_material'):raise ValueError('Trellis requires timber material')
        if 'plant_spacing' in item:
            spacing=item['plant_spacing']
            if not isinstance(spacing,list) or len(spacing)!=2 or any(type(v) not in (int,float) or not math.isfinite(v) or not .25<=v<=3 for v in spacing):raise ValueError('plant_spacing requires two finite dimensions in 0.25-3m')
        if 'rail_style' in item and item['rail_style'] not in ['timber','stone']:raise ValueError('Unknown overlook rail_style')
        if 'entry_steps' in item:
            entry=item['entry_steps']
            if type(entry.get('steps')) is not int or not 2<=entry['steps']<=12 or not .05<=entry.get('rise',0)/entry['steps']<=.18 or not 1<=entry.get('run',0)<=5 or not 2<=entry.get('width',0)<=8:raise ValueError('Invalid terrace entry steps')
        if kind=='timber_hall':
            for flag in ('open_sides','furniture'):
                if flag in item and type(item[flag]) is not bool:raise ValueError('Timber hall '+flag+' must be boolean')
            if item.get('enclosure') not in (None,'lodge'):raise ValueError('Unknown timber hall enclosure')
            if item.get('enclosure')=='lodge' and not item.get('window_material'):raise ValueError('Lodge enclosure requires window_material')
            if not 4<=item['size'][0]<=16 or not 6<=item['size'][1]<=30:raise ValueError('Timber hall size must be width 4-16m, length 6-30m')
            if not 3<=item.get('height',4.5)<=8:raise ValueError('Timber hall eave height must be 3-8m')
            bays=item.get('bays',4)
            if type(bays) is not int or not 2<=bays<=10 or not 1.5<=item['size'][1]/bays<=5:raise ValueError('Timber hall bays must span 1.5-5m')


def build(api,proxy=False):
    validate(api['cfg'].get('destination_details',[]))
    counts={};plantings=[]
    def emit(name,vs,fs,mat,finish=.015,smooth=True):
        counts[name]=counts.get(name,0)+1
        ob=api['mesh'](name,vs,fs,mat,colors=[(.93,.06,0,1)]*len(vs),smooth_faces=smooth)
        if not proxy and finish:api.get('finish_stone',lambda x,w:x)(ob,finish)
        return ob
    def box(name,p,d,mat,yaw=0,smooth=True):
        ca,sa=math.cos(yaw),math.sin(yaw)
        vs=[(p[0]+x*ca-y*sa,p[1]+x*sa+y*ca,p[2]+z) for z in [-d[2]/2,d[2]/2] for x,y in [(-d[0]/2,-d[1]/2),(d[0]/2,-d[1]/2),(d[0]/2,d[1]/2),(-d[0]/2,d[1]/2)]]
        return emit(name,vs,FACES,mat,smooth=smooth)
    def wall(name,p,d,mat,yaw=0):
        if proxy:return box(name,p,d,mat,yaw)
        nx=max(1,math.ceil(d[0]/.68));nz=max(1,math.ceil(d[2]/.31));ca,sa=math.cos(yaw),math.sin(yaw)
        for j in range(nz):
            edges=np.linspace(-d[0]/2,d[0]/2,nx+1)
            if j%2:edges=np.r_[-d[0]/2,(edges[:-1]+edges[1:])*.5,d[0]/2]
            for a,b in zip(edges,edges[1:]):
                x=(a+b)/2;box(name,(p[0]+x*ca,p[1]+x*sa,p[2]-d[2]/2+(j+.5)*d[2]/nz),(b-a-.010,d[1],d[2]/nz-.012),mat,yaw)
    def column(name,x,y,z,r,h,mat):
        n=12 if proxy else 24;vs=[(x+r*math.cos(i*math.tau/n),y+r*math.sin(i*math.tau/n),zz) for zz in [z,z+h] for i in range(n)]
        emit(name,vs,[tuple(range(n-1,-1,-1)),tuple(range(n,2*n))]+[(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)],mat)
    def arch(name,c,w,depth,h,mat,yaw=0,th=.28):
        try:from .arch_profiles import parameters,ordinate
        except ImportError:from arch_profiles import parameters,ordinate
        r=w/2;profile=api['cfg'].get('arch_profile','round');spring,rise=parameters(r,h,profile);ca,sa=math.cos(yaw),math.sin(yaw)
        def pt(x,y,z):return (c[0]+x*ca-y*sa,c[1]+x*sa+y*ca,c[2]+z)
        for sign in [-1,1]:wall(name+' pier',pt(sign*(r-th/2),0,spring/2),(th,depth,spring),mat,yaw)
        n=12 if proxy else 24
        for i in range(n):
            a=i*math.pi/n;b=(i+1)*math.pi/n
            gap=0 if proxy else .003
            emit(name+' voussoir',[pt(rad*math.cos(t),y,spring+ordinate(t,rad,r,rise,profile)) for y in [-depth/2,depth/2] for rad,t in [(r-th,a+gap),(r,a+gap),(r,b-gap),(r-th,b-gap)]],FACES,mat)
    def roof(name,c,w,l,rise,mat,yaw=0,seams=True):
        ca,sa=math.cos(yaw),math.sin(yaw)
        def pt(x,y,z):return (c[0]+x*ca-y*sa,c[1]+x*sa+y*ca,c[2]+z)
        for sign in [-1,1]:
            vs=[pt(x,y,z+th) for th in [0,.11] for x,y,z in [(0,-l/2,rise),(sign*w/2,-l/2,0),(sign*w/2,l/2,0),(0,l/2,rise)]]
            emit(name+' continuous slope',vs,FACES,mat)
            if not proxy and seams:
                for y in np.arange(-l/2+.10,l/2,.34):
                    vs=[pt(x,yy,z+th) for th in [.12,.16] for x,yy,z in [(0,y-.016,rise),(sign*w/2,y-.016,0),(sign*w/2,y+.016,0),(0,y+.016,rise)]]
                    emit(name+' standing seam',vs,FACES,mat,0)
    for item in api['cfg'].get('destination_details',[]):
        kind=item['kind'];x,y=item['center'];z=item.get('base_z',api['height'](x,y));mat=item.get('material',api['spec']['path_material'])
        if kind=='mast_footing':
            try:from .mast_footing import build as build_footing
            except ImportError:from mast_footing import build as build_footing
            build_footing(item,api['height'],emit,proxy)
        elif kind in ('masonry_gallery','masonry_tower'):
            try:from .masonry_destinations import build as build_masonry
            except ImportError:from masonry_destinations import build as build_masonry
            build_masonry(item,api,proxy,box,wall,arch,emit)
        elif kind=='dry_garden':
            w,l=item['size'];yaw=math.radians(item.get('yaw_deg',0));ca,sa=math.cos(yaw),math.sin(yaw)
            def pt(xx,yy):return (x+xx*ca-yy*sa,y+xx*sa+yy*ca)
            def terrain_box(name,xx,yy,ww,ll,material,thickness=.07):
                px,py=pt(xx,yy);zz=api['height'](px,py)+.025
                box(name,(px,py,zz-thickness/2),(ww,ll,thickness),material,yaw,smooth=False)
            nx=max(2,math.ceil(w/.4));ny=max(2,math.ceil(l/.4))
            for j in range(ny):
                for i in range(nx):terrain_box('Dry garden gravel bed',-w/2+(i+.5)*w/nx,-l/2+(j+.5)*l/ny,w/nx+.006,l/ny+.006,item['surface_material'])
            # Continuous low curb, built against terrain on both representations.
            for yy in [-l/2,l/2]:
                for i in range(nx):terrain_box('Dry garden stone curb',-w/2+(i+.5)*w/nx,yy,w/nx,.14,mat,.13)
            for xx in [-w/2,w/2]:
                for j in range(ny):terrain_box('Dry garden stone curb',xx,-l/2+(j+.5)*l/ny,.14,l/ny,mat,.13)
            if not proxy:
                for j in range(max(1,int(l/.14))):
                    yy=-l/2+.16+j*.14
                    vs=[]
                    for i in range(nx+1):
                        xx=-w/2+.16+(w-.32)*i/nx;wave=.035*math.sin(xx*2+yy*.5)
                        for dy in [-.012,.012]:
                            px,py=pt(xx,yy+wave+dy);vs.append((px,py,api['height'](px,py)+.03))
                    emit('Raked gravel ridge',vs,[(i*2,i*2+1,i*2+3,i*2+2) for i in range(nx)],item['surface_material'],0,smooth=False)
        elif kind=='garden_basin':
            radius=item['radius'];segments=16 if proxy else 64;h=item.get('height',.48)
            # A continuous carved vessel: outer wall, rim, inner wall and closed bottom.
            rings=[(radius*.65,0),(radius,.08),(radius,h),(radius*.75,h),(radius*.60,h*.45)]
            vs=[(x+r*math.cos(i*math.tau/segments),y+r*math.sin(i*math.tau/segments),z+zz) for r,zz in rings for i in range(segments)]
            fs=[(j*segments+i,j*segments+(i+1)%segments,(j+1)*segments+(i+1)%segments,(j+1)*segments+i) for j in range(len(rings)-1) for i in range(segments)]
            centre=len(vs);vs.append((x,y,z+h*.38));last=(len(rings)-1)*segments
            fs.extend((last+i,last+(i+1)%segments,centre) for i in range(segments))
            fs.append(tuple(range(segments-1,-1,-1)));emit('Carved garden wash basin',vs,fs,mat,0)
            if item.get('water_material'):
                # A contained opaque surface stays inside the vessel cavity.
                rr=radius*.64;level=z+h*.78
                water_vs=[(x+rr*math.cos(i*math.tau/segments),y+rr*math.sin(i*math.tau/segments),level+dz) for dz in [-.012,0] for i in range(segments)]
                water_fs=[tuple(range(segments-1,-1,-1)),tuple(range(segments,2*segments))]+[(i,(i+1)%segments,(i+1)%segments+segments,i+segments) for i in range(segments)]
                emit('Contained ritual water',water_vs,water_fs,item['water_material'],0,smooth=False)
        elif kind=='vault_liner':
            r=item['radius'];rise=item['rise'];bands=10 if proxy else 24;sectors=32 if proxy else 64
            vs=[];fs=[]
            for extra in [0,.12]:
                for j in range(bands+1):
                    t=j*math.pi/2/bands
                    for i in range(sectors):
                        a=i*math.tau/sectors;vs.append((x+(r+extra)*math.cos(t)*math.cos(a),y+(r+extra)*math.cos(t)*math.sin(a),z+(rise+extra)*math.sin(t)))
            size=(bands+1)*sectors
            for side in [0,1]:
                for j in range(bands):
                    for i in range(sectors):
                        a=side*size+j*sectors+i;b=side*size+j*sectors+(i+1)%sectors;fs.append((a,b,b+sectors,a+sectors))
            for i in range(sectors):fs.append((i,(i+1)%sectors,(i+1)%sectors+size,i+size))
            emit('Continuous interior vault',vs,fs,mat,0)
        elif kind=='bell_tower':
            w=item.get('width',3.4);h=item.get('height',8.7);stem=h-2.8
            base=min(api['height'](x+dx,y+dy) for dx in [-w/2,w/2] for dy in [-w/2,w/2])-.2
            box('Tower foundation',(x,y,(base+z+.22)/2),(w+.5,w+.5,z+.22-base),mat)
            for dy in [-w/2,w/2]:wall('Belfry lower wall',(x,y+dy,z+stem/2),(w+.35,.48,stem),mat)
            for dx in [-w/2,w/2]:wall('Belfry side wall',(x+dx,y,z+stem/2),(w,.48,stem),mat,math.pi/2)
            for zz in [.18,stem-.1,stem+.16,h-.12]:box('Tower string course',(x,y,z+zz),(w+.7,w+.7,.22),mat)
            for dy in [-w/2,w/2]:arch('Belfry opening',(x,y+dy,z+stem+.22),w,.46,2.5,mat,th=.34)
            for dx in [-w/2,w/2]:arch('Belfry opening',(x+dx,y,z+stem+.22),w,.46,2.5,mat,math.pi/2,th=.34)
            roof('Belfry copper roof',(x,y,z+h+.12),w+.9,w+.9,1.35,item['roof_material'])
            # Keep the casting legible within the clear arch aperture. Its
            # material is independent from the roof and its crown reaches a
            # supported yoke. Both representations retain the hollow mouth.
            metal=item.get('bell_material',item['roof_material'])
            radius=min(w*.27,1.18);rise=1.60;bellbase=z+stem+.50
            profile=[(1,0),(1.03,.07),(.88,.17),(.62,.72),(.48,.91),(.22,1)]
            vs=[];n=16 if proxy else 48
            for shell in [0,1]:
                for rr,zz in profile:
                    rad=rr*radius-(min(.06,radius*.12) if shell else 0)
                    for i in range(n):
                        a=i*math.tau/n;vs.append((x+rad*math.cos(a),y+rad*math.sin(a),bellbase+zz*rise))
            fs=[];layer=n*len(profile)
            for shell in [0,1]:
                for j in range(len(profile)-1):
                    for i in range(n):
                        a=shell*layer+j*n+i;b=shell*layer+j*n+(i+1)%n;fs.append((a,b,b+n,a+n))
            for i in range(n):fs.append((i,(i+1)%n,(i+1)%n+layer,i+layer))
            emit('Cast bell',vs,fs,metal,0)
            column('Bell clapper',x,y,bellbase-.10,.09,rise+.14,metal)
            box('Bell suspension',(x,y,z+stem+2.50),(.24,w+.3,.24),item.get('timber_material',mat))
            column('Bell crown hanger',x,y,z+stem+2.04,.11,.52,metal)
        elif kind in ('workshop_station','bell_rack'):
            w,d=item['size'];yaw=math.radians(item.get('yaw_deg',0));ca,sa=math.cos(yaw),math.sin(yaw)
            wood=item['timber_material'];metal=item['metal_material']
            def pt(xx,yy,zz):return (x+xx*ca-yy*sa,y+xx*sa+yy*ca,z+zz)
            if kind=='workshop_station':
                for xx in [-w*.4,w*.4]:
                    for yy in [-d*.34,d*.34]:box('Workbench joined leg',pt(xx,yy,.45),(.18,.18,.9),wood,yaw)
                box('Workbench heavy top',pt(0,0,.96),(w,d,.20),wood,yaw)
                box('Workbench stretcher',pt(0,0,.24),(w,.18,.2),wood,yaw)
                for xx in [-w*.42,w*.42]:box('Tool rack post',pt(xx,d*.46,1.4),(.15,.15,2.8),wood,yaw)
                for zz in [1.85,2.55]:box('Tool rack rail',pt(0,d*.46,zz),(w,.14,.14),wood,yaw)
                box('Anvil foot',pt(0,-.06,1.11),(.78,.43,.12),metal,yaw)
                box('Anvil waist',pt(0,-.06,1.28),(.36,.25,.26),metal,yaw)
                box('Anvil working face',pt(0,-.06,1.48),(1.0,.45,.18),metal,yaw)
                emit('Anvil tapered horn',[pt(xx,yy,zz) for xx,ww,zz in [(.48,.22,1.39),(1.0,.035,1.48)] for yy,zz in [(-.06-ww,zz),(-.06+ww,zz),(-.06+ww,1.56),(-.06-ww,1.56)]],FACES,metal)
                if not proxy:
                    for j in range(5):
                        xx=-w*.32+j*w*.16
                        box('Hanging tool shaft',pt(xx,d*.42,2.0-j*.04),(.045,.045,.62),wood,yaw)
                        box('Hanging hammer head',pt(xx,d*.42,2.28-j*.04),(.24,.09,.10),metal,yaw)
                    for j in range(3):box('Stacked metal billet',pt(-w*.3,-d*.2,1.10+j*.06),(.5,.23,.055),metal,yaw+.15*j)
            else:
                h=item.get('height',3.3)
                for xx in [-w*.44,w*.44]:
                    px,py,_=pt(xx,0,0);bottom=api['height'](px,py)-.15
                    box('Bell rack stone foot',(px,py,(bottom+z+.28)/2),(.72,d,z+.28-bottom),mat,yaw)
                    box('Bell rack timber upright',pt(xx,0,h/2),(.28,.32,h),wood,yaw)
                    for zz in [.55,h-.4]:box('Bell rack iron strap',pt(xx,0,zz),(.30,.34,.08),metal,yaw)
                box('Bell rack lintel',pt(0,0,h),(w+.3,.38,.34),wood,yaw)
                box('Bell rack yoke',pt(0,0,h-.36),(w*.68,.20,.20),wood,yaw)
                box('Bell rack through axle',pt(0,0,h-.36),(w*.92,.14,.14),metal,yaw)
                for xx in [-w*.44,w*.44]:
                    box('Bell rack axle bearing',pt(xx,0,h-.36),(.32,.44,.28),metal,yaw)
                for xx in [-.14,.14]:
                    box('Bell crown hanger',pt(xx,0,h-.43),(.10,.14,.38),metal,yaw)
                radius=min(w*.29,.95);rise=h*.54;bottom=h-.48-rise;n=16 if proxy else 48
                profile=[(1,0),(1.03,.07),(.88,.17),(.62,.72),(.48,.91),(.22,1)]
                vs=[]
                for shell in [0,1]:
                    for rr,zz in profile:
                        rad=rr*radius-(.065 if shell else 0)
                        for i in range(n):a=i*math.tau/n;vs.append(pt(rad*math.cos(a),rad*math.sin(a),bottom+zz*rise))
                fs=[];layer=n*len(profile)
                for shell in [0,1]:
                    for j in range(len(profile)-1):
                        for i in range(n):a=shell*layer+j*n+i;b=shell*layer+j*n+(i+1)%n;fs.append((a,b,b+n,a+n))
                for i in range(n):fs.append((i,(i+1)%n,(i+1)%n+layer,i+layer))
                emit('Suspended hollow bronze casting',vs,fs,metal,0)
                px,py,pz=pt(0,0,bottom-.08);column('Bell rack clapper',px,py,pz,.09,rise+.18,metal)
        elif kind=='hoist_station':
            w,d=item['size'];h=item.get('height',3.4);wood=item['timber_material'];metal=item['metal_material']
            yaw=math.radians(item.get('yaw_deg',0));ca,sa=math.cos(yaw),math.sin(yaw)
            def pt(xx,yy,zz):return np.array((x+xx*ca-yy*sa,y+xx*sa+yy*ca,z+zz))
            def rod(name,a,b,r,material,n=None):
                a=pt(*a);b=pt(*b);axis=b-a;axis/=np.linalg.norm(axis)
                side=np.cross(axis,[0,0,1])
                if np.linalg.norm(side)<.01:side=np.cross(axis,[0,1,0])
                side/=np.linalg.norm(side);other=np.cross(axis,side);n=n or (10 if proxy else 24)
                vs=[q+r*(side*math.cos(i*math.tau/n)+other*math.sin(i*math.tau/n)) for q in [a,b] for i in range(n)]
                fs=[tuple(range(n-1,-1,-1)),tuple(range(n,2*n))]+[(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
                emit(name,vs,fs,material,0)
            def hoop(name,xx,yy,zz,r,tube):
                n=20 if proxy else 48;ring=6 if proxy else 10
                vs=[pt(xx+tube*math.sin(b),yy+(r+tube*math.cos(b))*math.cos(a),zz+(r+tube*math.cos(b))*math.sin(a)) for a in np.linspace(0,math.tau,n,endpoint=False) for b in np.linspace(0,math.tau,ring,endpoint=False)]
                fs=[(i*ring+j,i*ring+(j+1)%ring,((i+1)%n)*ring+(j+1)%ring,((i+1)%n)*ring+j) for i in range(n) for j in range(ring)]
                emit(name,vs,fs,metal,0)
            for xx in [-w*.42,w*.42]:
                px,py,_=pt(xx,0,0);bottom=min(z-.15,footing_bottom(api['height'],(px,py),(.74,d),yaw))
                box('Hoist grounded stone foot',(px,py,(bottom+z+.16)/2),(.74,d,z+.16-bottom),mat,yaw,smooth=False)
                box('Hoist timber upright',pt(xx,0,h/2),(.26,.32,h),wood,yaw,smooth=False)
                for sign in [-1,1]:rod('Hoist diagonal brace',(xx,sign*d*.42,.16),(xx,0,h*.60),.09,wood)
                box('Hoist iron bearing',pt(xx,-.10,1.10),(.34,.42,.42),metal,yaw)
            box('Hoist crown beam',pt(0,0,h),(w+.4,.40,.34),wood,yaw,smooth=False)
            rod('Hoist through axle',(-w*.56,-.10,1.10),(w*.56,-.10,1.10),.09,metal)
            rod('Hoist winding drum',(-w*.28,-.10,1.10),(w*.28,-.10,1.10),.34,wood)
            for xx in [-w*.29,w*.29]:rod('Hoist drum flange',(xx-.05,-.10,1.10),(xx+.05,-.10,1.10),.46,metal)
            hoop('Hoist handwheel',w*.56,-.10,1.10,.68,.065)
            for a in np.linspace(0,math.tau,8,endpoint=False):rod('Hoist wheel spoke',(w*.56,-.10,1.10),(w*.56,-.10+.66*math.cos(a),1.10+.66*math.sin(a)),.035,metal)
            # The cable is a solid connected path from drum, over the crown
            # pulley, to the supported load. It is retained by the proxy too.
            rod('Hoist lifting cable',(0,-.42,1.10),(0,-.42,h-.05),.028,metal)
            rod('Hoist lifting cable',(0,-.42,h-.05),(0,-d*.36,h-.05),.028,metal)
            rod('Hoist lifting cable',(0,-d*.36,h-.05),(0,-d*.36,.66),.028,metal)
            rod('Hoist crown pulley',(-.12,-d*.36,h-.05),(.12,-d*.36,h-.05),.20,metal)
            box('Hoist casting form',pt(0,-d*.36,.36),(w*.58,d*.42,.70),wood,yaw,smooth=False)
            for xx in [-w*.20,w*.20]:box('Hoist form iron band',pt(xx,-d*.36,.36),(.10,d*.44,.73),metal,yaw)
        elif kind=='forge_hearth':
            w,d=item['size'];h=item['height'];yaw=math.radians(item.get('yaw_deg',0));ca,sa=math.cos(yaw),math.sin(yaw)
            def pt(xx,yy,zz):return (x+xx*ca-yy*sa,y+xx*sa+yy*ca,z+zz)
            bottom=min(api['height'](*pt(xx,yy,0)[:2]) for xx in [-w/2,w/2] for yy in [-d/2,d/2])-.18
            box('Hearth grounded plinth',(x,y,(bottom+z+.16)/2),(w+.5,d+.5,z+.16-bottom),mat,yaw)
            opening=w*.72;mouth=2.35
            arch('Hearth open mouth',pt(0,-d/2,.16),opening,.55,mouth,mat,yaw,.34)
            for sign in [-1,1]:
                wall('Hearth side cheek',pt(sign*(w/2-.24),0,1.30), (d,.48,2.28),mat,yaw+math.pi/2)
            wall('Hearth rear wall',pt(0,d/2-.24,1.30),(w,.48,2.28),mat,yaw)
            # Closed tapered hood and flue, with a real void below its arch.
            vs=[pt(xx,yy,zz) for width,depth,zz in [(w+.18,d+.15,2.50),(w*.52,d*.64,3.45)] for xx,yy in [(-width/2,-depth/2),(width/2,-depth/2),(width/2,depth/2),(-width/2,depth/2)]]
            emit('Hearth tapered smoke hood',vs,FACES,mat)
            wall('Hearth chimney front',pt(0,-d*.27,(h+3.45)/2),(w*.55,.30,h-3.45),mat,yaw)
            wall('Hearth chimney rear',pt(0,d*.27,(h+3.45)/2),(w*.55,.30,h-3.45),mat,yaw)
            for sign in [-1,1]:wall('Hearth chimney side',pt(sign*w*.25,0,(h+3.45)/2),(d*.54,.30,h-3.45),mat,yaw+math.pi/2)
            box('Hearth chimney cornice',pt(0,0,h),(w*.65,d*.72,.24),mat,yaw)
            metal=item['metal_material']
            box('Hearth iron lintel',pt(0,-d/2-.06,2.60),(w+.25,.15,.18),metal,yaw)
            if not proxy:
                for xx in np.linspace(-opening*.30,opening*.30,7):box('Hearth grate bar',pt(xx,-d*.2,.34),(.07,d*.56,.09),metal,yaw)
        elif kind=='timber_hall':
            w,l=item['size'];h=item.get('height',4.5);rise=item.get('roof_rise',1.8);bays=item.get('bays',4)
            wood=item['timber_material'];roofmat=item['roof_material'];yaw=math.radians(item.get('yaw_deg',0));ca,sa=math.cos(yaw),math.sin(yaw)
            def pt(xx,yy,zz):return (x+xx*ca-yy*sa,y+xx*sa+yy*ca,z+zz)
            def beam(name,a,b,thickness,material):
                a=np.array(pt(*a));b=np.array(pt(*b));d=b-a
                side=np.cross(d,[0,0,1]);side/=max(.001,np.linalg.norm(side));other=np.cross(d,side);other/=max(.001,np.linalg.norm(other))
                vs=[q+side*u+other*v for q in [a,b] for u,v in [(-thickness/2,-thickness/2),(thickness/2,-thickness/2),(thickness/2,thickness/2),(-thickness/2,thickness/2)]]
                emit(name,vs,FACES,material,0)
            bottom=min(api['height'](*pt(xx,yy,0)[:2]) for xx in [-w/2-.4,w/2+.4] for yy in [-l/2-.4,l/2+.4])-.2
            box('Hall continuous foundation',(x,y,(bottom+z+.08)/2),(w+.8,l+.8,max(.1,z+.08-bottom)),mat,yaw)
            if item.get('floor_material'):
                # Rectangular boards cover the complete floor, including its
                # corners. A generic worn masonry octagon removes metre-wide
                # wedges when scaled to a room and is unsuitable for decking.
                fw,fl=w-.34,l+.30;floor=item['floor_material']
                if proxy:
                    box('Hall floor envelope',pt(0,0,.125),(fw,fl,.10),floor,yaw,smooth=False)
                else:
                    n=math.ceil(fw/.24)
                    for i in range(n):
                        box('Hall floor board',pt(-fw/2+(i+.5)*fw/n,0,.125),(fw/n-.003,fl,.10),floor,yaw,smooth=False)
            for yy in np.linspace(-l/2,l/2,bays+1):
                for xx in [-w/2,w/2]:
                    box('Hall stone post foot',pt(xx,yy,.2),(.72,.72,.4),mat,yaw)
                    box('Hall timber post',pt(xx,yy,h/2),(.3,.3,h),wood,yaw)
                    if not proxy:
                        beam('Hall knee brace',(xx,yy,h-.85),(xx-math.copysign(.85,xx),yy,h),.18,wood)
                        for zz in [.65,h-.4]:box('Hall iron post strap',pt(xx,yy,zz),(.32,.32,.09),item.get('metal_material',roofmat),yaw)
                box('Hall tie beam',pt(0,yy,h),(w+.5,.28,.28),wood,yaw)
                if not proxy:
                    for sign in [-1,1]:beam('Hall roof truss',(sign*w/2,yy,h+.12),(0,yy,h+rise+.12),.22,wood)
            for sign in [-1,1]:
                box('Hall eave beam',pt(sign*w/2,0,h),(.3,l+.6,.3),wood,yaw)
                # Side infill supports the workshop silhouette; both ends remain open.
                if not item.get('open_sides',False):wall('Hall masonry side infill',pt(sign*w/2,0,.62), (l,.38,1.24),mat,yaw+math.pi/2)
            box('Hall ridge timber',pt(0,0,h+rise),(.24,l+.65,.24),wood,yaw)
            roof('Hall continuous pitched roof',pt(0,0,h+.14),w+1,l+1,rise,roofmat,yaw,item.get('roof_seams',True))
            if item.get('enclosure')=='lodge':
                try:from .lodge_details import build as build_lodge
                except ImportError:from lodge_details import build as build_lodge
                build_lodge(item,pt,box,emit,yaw,proxy)
            if not proxy and item.get('furniture',True):
                for sign in [-1,1]:
                    box('Hall workbench top',pt(sign*(w/2-.75),0,.96),(.72,l*.55,.14),wood,yaw)
                    for yy in [-l*.22,l*.22]:box('Hall workbench leg',pt(sign*(w/2-.75),yy,.45),(.17,.17,.9),wood,yaw)
        elif kind=='herb_bed':
            w,l=item.get('size',[3.8,1.6]);h=item.get('height',.48);yaw=math.radians(item.get('yaw_deg',0));ca,sa=math.cos(yaw),math.sin(yaw)
            corners=[api['height'](x+xx*ca-yy*sa,y+xx*sa+yy*ca) for xx in [-w/2,w/2] for yy in [-l/2,l/2]]
            z=min(corners)-.10;h=max(corners)+h-z
            def pt(xx,yy,zz):return (x+xx*ca-yy*sa,y+xx*sa+yy*ca,z+zz)
            for yy in [-l/2,l/2]:wall('Herb bed curb',pt(0,yy,h/2),(w+.24,.20,h),mat,yaw)
            for xx in [-w/2,w/2]:wall('Herb bed end',pt(xx,0,h/2),(.20,l,h),mat,yaw)
            box('Cultivated soil',pt(0,0,h*.63),(w-.17,l-.17,h*.65),item['soil_material'],yaw)
            if item.get('trellis'):
                timber=item['timber_material'];yy=l/2+.08
                for xx in [-w/2+.18,w/2-.18]:box('Trellis post',pt(xx,yy,1.15),(.14,.14,2.3),timber,yaw)
                for hh in [.8,1.3,1.8,2.25]:box('Trellis rail',pt(0,yy,hh),(w,.10,.09),timber,yaw)
                for xx in np.linspace(-w/2+.3,w/2-.3,9):box('Trellis upright',pt(xx,yy,1.55),(.045,.07,1.45),timber,yaw)
            if not proxy:
                dx,dy=item.get('plant_spacing',[.43,.38])
                for ix,xx in enumerate(np.arange(-w/2+max(.26,dx/2),w/2,dx)):
                    for iy,yy in enumerate(np.arange(-l/2+max(.23,dy/2),l/2,dy)):
                        pos=pt(xx,yy,h*.93-item.get('plant_embed_m',0));plantings.append({'asset':item['plant_asset'],'position':list(pos),'size':item.get('plant_size',.62),'variant':(ix+iy)%6,'yaw':ix*1.7+iy*.6})
        elif kind=='terraced_foundation':
            w,l=item['size'];top=z+item['rise'];bottom=footing_bottom(api['height'],(x,y),(w,l),embed=.25)
            box('Raised gallery foundation',(x,y,(bottom+top)/2),(w,l,top-bottom),mat)
            if item.get('floor_material'):
                if proxy:box('Raised gallery floor',(x,y,top+.032),(w,l,.064),item['floor_material'])
                else:
                    nx=max(2,math.ceil(w/1.1));ny=max(2,math.ceil(l/.8))
                    for ix in range(nx):
                        for iy in range(ny):box('Raised gallery fitted paving',(x-w/2+(ix+.5)*w/nx,y-l/2+(iy+.5)*l/ny,top+.032),(w/nx-.008,l/ny-.008,.064),item['floor_material'],smooth=False)
            # Wide shallow treads lead to the raised aisle, with two landing levels.
            start=y-l/2-item.get('stair_run',2.0);run=y-l/2-start;steps=max(2,math.ceil(item['rise']/.15))
            for j in range(steps):
                zz=z+item['rise']*(j+1)/steps;yy=start+(j+.5)*run/steps
                depth=run/steps+.012;bottom=min(z-.2,footing_bottom(api['height'],(x,yy),(w,depth)))
                box('Gallery ascending tread',(x,yy,(bottom+zz)/2),(w,depth,zz-bottom),mat)
            for side in [-1,1]:
                wall('Terrace retaining parapet',(x+side*(w/2-.18),y,top+.38),(l,.40,.76),mat,math.pi/2)
                box('Terrace coping',(x+side*(w/2-.18),y,top+.82),(.55,l+.12,.16),mat)
        elif kind=='footbridge':
            span,width=item['size'];wood=item['timber_material'];yaw=math.radians(item.get('yaw_deg',0));ca,sa=math.cos(yaw),math.sin(yaw)
            def pt(xx,yy,zz):return (x+xx*ca-yy*sa,y+xx*sa+yy*ca,z+zz)
            # The path passes under the deck; deck ends join the raised banks.
            for xx in [-span/2,span/2]:
                center=pt(xx,0,0);bottom=min(api['height'](*pt(xx+dx,dy,0)[:2]) for dx in [-.4,.4] for dy in [-width/2,width/2])-.2
                wall('Bridge masonry abutment',(center[0],center[1],(bottom+z)/2),(.75,width+.7,max(.3,z-bottom)),mat,yaw)
            for yy in [-width*.36,width*.36]:box('Bridge timber girder',pt(0,yy,-.18),(span+.6,.26,.4),wood,yaw)
            if proxy:box('Bridge deck envelope',pt(0,0,.08),(span+.7,width,.18),wood,yaw)
            else:
                n=math.ceil((span+.7)/.24)
                for i in range(n):box('Bridge deck plank',pt(-(span+.7)/2+(i+.5)*(span+.7)/n,0,.08),((span+.7)/n-.009,width,.18),wood,yaw)
            for yy in [-width/2,width/2]:
                for xx in np.linspace(-span/2,span/2,7):box('Bridge rail post',pt(xx,yy,.64),(.14,.14,1.2),wood,yaw)
                for hh in [.58,1.12]:box('Bridge handrail',pt(0,yy,hh),(span+.8,.12,.12),wood,yaw)
        elif kind=='overlook_terrace':
            w,l=item['size'];wood=item['timber_material'];yaw=math.radians(item.get('yaw_deg',0));ca,sa=math.cos(yaw),math.sin(yaw)
            def pt(xx,yy,zz):return (x+xx*ca-yy*sa,y+xx*sa+yy*ca,z+zz)
            inset=item.get('plinth_inset_m',-.3)
            bottom=footing_bottom(api['height'],(x,y),(w-2*inset,l-2*inset),yaw)
            box('Overlook continuous plinth',(x,y,(bottom+z+.10)/2),(w-2*inset,l-2*inset,z+.10-bottom),mat,yaw)
            if item.get('coursed_plinth'):
                for sign in [-1,1]:
                    wall('Overlook coursed stone side',pt(sign*(w/2-inset),0,(bottom-z+.1)/2),(l-2*inset,.22,z+.10-bottom),mat,yaw+math.pi/2)
                    wall('Overlook coursed stone end',pt(0,sign*(l/2-inset),(bottom-z+.1)/2),(w-2*inset,.22,z+.10-bottom),mat,yaw)
            if item.get('entry_steps'):
                e=item['entry_steps'];n=e['steps'];depth=e['run']/n
                for i in range(n):
                    yy=-l/2-e['run']+(i+.5)*depth;top=z+.14-e['rise']*(1-(i+1)/n)
                    centre=pt(0,yy,0);low=min(top-.12,footing_bottom(api['height'],centre[:2],(e['width'],depth),yaw))
                    box('Overlook arrival step',(centre[0],centre[1],(top+low)/2),(e['width'],depth+.008,top-low),mat,yaw,smooth=False)
            if item.get('floor_material') and inset>0:
                for sign in [-1,1]:
                    box('Overlook timber side fascia',pt(sign*(w/2-.05),0,-.02),(.10,l,.32),item['floor_material'],yaw,smooth=False)
                    box('Overlook timber end fascia',pt(0,sign*(l/2-.05),-.02),(w,.10,.32),item['floor_material'],yaw,smooth=False)
            if item.get('floor_material'):
                floor=item['floor_material'];n=1 if proxy else math.ceil(l/.21)
                for i in range(n):box('Overlook deck plank',pt(0,-l/2+(i+.5)*l/n,.12),(w,l/n-(0 if proxy else .005),.04),floor,yaw,smooth=False)
            if item.get('rail_style')=='timber':
                for sign in [-1,1]:
                    for yy in np.linspace(-l/2,l/2,max(2,math.ceil(l/1.6)+1)):box('Overlook timber post',pt(sign*w/2,yy,.65),(.16,.16,1.10),wood,yaw,smooth=False)
                    for zz in [.5,1.15]:box('Overlook timber side rail',pt(sign*w/2,0,zz),(.16,l+.3,.14),wood,yaw,smooth=False)
                if not item.get('through_passage',False):
                    for xx in np.linspace(-w/2,w/2,max(2,math.ceil(w/1.6)+1)):box('Overlook outer post',pt(xx,l/2,.65),(.16,.16,1.1),wood,yaw,smooth=False)
                    for zz in [.5,1.15]:box('Overlook timber outer rail',pt(0,l/2,zz),(w+.3,.16,.14),wood,yaw,smooth=False)
            else:
                for sign in [-1,1]:
                    wall('Overlook side parapet',pt(sign*w/2,0,.51),(l,.32,.82),mat,yaw+math.pi/2)
                    box('Overlook parapet coping',pt(sign*w/2,0,.96),(.48,l+.18,.14),mat,yaw)
                    box('Overlook corner pier',pt(sign*w/2,l/2,.78),(.62,.62,1.36),mat,yaw)
                if not item.get('through_passage',False):wall('Overlook outer parapet',pt(0,l/2,.42),(w,.30,.64),mat,yaw)
            if not item.get('through_passage',False):
                for xx in [-w*.3,w*.3]:box('Overlook bench support',pt(xx,l*.23,.3),(.34,.4,.48),mat,yaw)
                box('Overlook long timber seat',pt(0,l*.23,.58),(w*.78,.55,.15),wood,yaw)
        elif kind=='belvedere':
            w,l=item.get('size',[5.2,3.8]);h=item.get('height',3.2);timber=item['timber_material'];roofmat=item['roof_material']
            bottom=min(api['height'](x+xx,y+yy) for xx in [-w/2-.4,w/2+.4] for yy in [-l/2-.4,l/2+.4])-.15
            box('Belvedere plinth',(x,y,(bottom+z+.08)/2),(w+.8,l+.8,z+.08-bottom),mat)
            if item.get('floor_material'):
                # The canopy's own plinth is taller than the approach terrace.
                # Put its finished floor above that plinth, not below it.
                fw,fl=w+.8,l+.8
                nx=1 if proxy else math.ceil(fw/.95);ny=1 if proxy else math.ceil(fl/1.05)
                for i in range(nx):
                    for j in range(ny):
                        box('Belvedere fitted finish',(x-fw/2+(i+.5)*fw/nx,y-fl/2+(j+.5)*fl/ny,z+.11),
                            (fw/nx-(0 if proxy else .008),fl/ny-(0 if proxy else .008),.08),item['floor_material'],smooth=False)
            for xx in [-w/2,w/2]:
                for yy in [-l/2,l/2]:
                    box('Pavilion stone foot',(x+xx,y+yy,z+.16),(.64,.64,.38),mat)
                    box('Pavilion timber post',(x+xx,y+yy,z+h/2),(.24,.24,h),timber)
                    # Short diagonal knee braces are real supporting timbers.
                    for axis in [0,1]:
                        dx=(-1 if xx>0 else 1)*.70 if axis==0 else 0;dy=(-1 if yy>0 else 1)*.70 if axis==1 else 0
                        a=np.array([x+xx,y+yy,z+h-.72]);b=a+[dx,dy,.72];d=b-a;side=np.cross(d,[0,0,1]);side/=max(.001,np.linalg.norm(side));other=np.cross(d,side);other/=np.linalg.norm(other)
                        vs=[q+side*u+other*v for q in [a,b] for u,v in [(-.07,-.07),(.07,-.07),(.07,.07),(-.07,.07)]];emit('Pavilion knee brace',vs,FACES,timber)
            for yy in [-l/2,l/2]:box('Pavilion crossbeam',(x,y+yy,z+h),(w+.65,.25,.28),timber)
            for xx in [-w/2,w/2]:box('Pavilion eave beam',(x+xx,y,z+h),(.25,l+.65,.28),timber)
            roof('Belvedere standing seam roof',(x,y,z+h+.17),w+1.0,l+1.0,item.get('roof_rise',1.45),roofmat)
            for yy in ([l/2] if item.get('open_front',False) else [-l/2,l/2]):
                box('Lookout bench',(x,y+yy*.72,z+.58),(w-.8,.43,.15),timber)
                for xx in [-w*.3,w*.3]:box('Bench stone support',(x+xx,y+yy*.72,z+.25),(.35,.40,.52),mat)
        else:raise ValueError('Unknown destination detail: '+kind)
    return {'counts':counts,'plantings':plantings}
