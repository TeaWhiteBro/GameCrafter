"""Optional dimensional architecture; same metric construction drives the structural companion."""
import math
FACES=[(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]
KINDS={'curved_pavilion','beam_gate','capped_wall','street_frontage','garden_bench','graphic_panel','access_ramp','box_assembly','roof_service'}

def validate(items):
    if not isinstance(items,list):raise ValueError('modular_architecture must be an array')
    for item in items:
        if item.get('kind') not in KINDS:raise ValueError('Unsupported modular architecture kind')
        for key,count in [('center',2),('size',2)]:
            v=item.get(key)
            if not isinstance(v,list) or len(v)!=count or any(type(n) not in (int,float) or not math.isfinite(n) for n in v):raise ValueError('Modular '+key+' needs two finite metre values')
        if any(not .4<=v<=40 for v in item['size']):raise ValueError('Modular size must be 0.4-40m')
        for key,lo,hi,default in [('height',1,60 if item['kind']=='box_assembly' else 18,3.5),('roof_rise',.2,5,1.8),('upturn',0,1.5,.45),('base_z',-20,80 if item['kind']=='roof_service' else 30,.14),('yaw_deg',-360,360,0)]:
            value=item.get(key,default)
            if type(value) not in (int,float) or not math.isfinite(value) or not lo<=value<=hi:raise ValueError('Invalid modular '+key)
        for key in ['material','timber_material','roof_material']:
            if not item.get(key):raise ValueError('Missing modular '+key)
        if item['kind']=='box_assembly':
            parts=item.get('parts')
            if not isinstance(parts,list) or not 1<=len(parts)<=128:raise ValueError('Box assembly requires 1-128 bounded components')
            for part in parts:
                for key in ['position','scale']:
                    value=part.get(key)
                    if not isinstance(value,list) or len(value)!=3 or any(type(v) not in (int,float) or not math.isfinite(v) for v in value):raise ValueError('Assembly '+key+' requires three finite values')
                if any(not .005<=v<=60 for v in part['scale']) or any(abs(v)>80 for v in part['position']):raise ValueError('Assembly component exceeds metric envelope')
                if not isinstance(part.get('material'),str) or not part['material']:raise ValueError('Assembly component material missing')
                if type(part.get('yaw_deg',0)) not in (int,float) or not math.isfinite(part.get('yaw_deg',0)):raise ValueError('Assembly component yaw invalid')
        if item['kind']=='graphic_panel' and not item.get('window_material'):raise ValueError('Graphic panel requires window_material')
        if item['kind']=='roof_service':
            if item.get('service_type') not in ('tank','hvac','antenna'):raise ValueError('Unknown roof service_type')
            if min(item['size'])<2:raise ValueError('Roof service platform needs at least two metres per side')
            # Equipment may sit on the existing 60m tower vocabulary; bound
            # its entire silhouette, rather than treating roof height as terrain.
            if item.get('base_z',.14)+item.get('height',3.5)+.25>80:raise ValueError('Roof service exceeds 80m world envelope')
        if item.get('urban_detail'):
            try:from .urban_frontage import validate as validate_urban
            except ImportError:from urban_frontage import validate as validate_urban
            validate_urban(item)
    return items

def build(api,proxy=False):
    items=validate(api['cfg'].get('modular_architecture',[]));height=api['height']
    summaries=[]
    for index,item in enumerate(items):
        cx,cy=item['center'];w,d=item['size'];base=item.get('base_z',.14);h=item.get('height',3.5);yaw=math.radians(item.get('yaw_deg',0));ca,sa=math.cos(yaw),math.sin(yaw)
        stone=item['material'];wood=item['timber_material'];roof=item['roof_material'];wall=item.get('wall_material',stone)
        def point(x,y,z):return (cx+x*ca-y*sa,cy+x*sa+y*ca,z)
        def mesh(label,vertices,faces,mat,collision=True,preserve_winding=False):
            options={}
            if not collision:options['collision']=False
            if preserve_winding:options['preserve_winding']=True
            ob=api['mesh']('Module '+str(index)+' '+label,[point(*p) for p in vertices],faces,mat,**options)
            if not proxy:
                for polygon in ob.data.polygons:polygon.use_smooth=False
            return ob
        def box(label,p,scale,mat,ground=False):
            x,y,z=p;dx,dy,dz=scale
            vs=[(x+xx*dx/2,y+yy*dy/2,z+zz*dz/2) for zz in [-1,1] for xx,yy in [(-1,-1),(1,-1),(1,1),(-1,1)]]
            if ground:
                perimeter=[point(x+dx*(i/8-.5),y+sy*dy/2,0) for i in range(9) for sy in [-1,1]]
                perimeter += [point(x+sx*dx/2,y+dy*(i/8-.5),0) for i in range(9) for sx in [-1,1]]
                lower=min(z-dz/2,min(height(px,py) for px,py,_ in perimeter)-.08)
                vs=[(px,py,lower if i<4 else pz) for i,(px,py,pz) in enumerate(vs)]
            return mesh(label,vs,FACES,mat)
        def beam(label,a,b,width,depth,mat):
            delta=[b[i]-a[i] for i in range(3)];length=math.sqrt(sum(n*n for n in delta));axis=[n/length for n in delta]
            side=[-axis[1],axis[0],0]
            if math.hypot(side[0],side[1])<.01:side=[1,0,0]
            sl=math.sqrt(sum(n*n for n in side));side=[n/sl for n in side]
            up=[axis[1]*side[2]-axis[2]*side[1],axis[2]*side[0]-axis[0]*side[2],axis[0]*side[1]-axis[1]*side[0]]
            vs=[tuple(p[i]+s*side[i]*width/2+t*up[i]*depth/2 for i in range(3)) for p in [a,b] for s,t in [(-1,-1),(1,-1),(1,1),(-1,1)]]
            return mesh(label,vs,FACES,mat)
        def tile_roll(label,a,b,r,mat):
            delta=[b[i]-a[i] for i in range(3)];length=math.sqrt(sum(v*v for v in delta));axis=[v/length for v in delta]
            side=[-axis[1],axis[0],0];sl=math.hypot(*side[:2]);side=[v/sl for v in side]
            up=[axis[1]*side[2]-axis[2]*side[1],axis[2]*side[0]-axis[0]*side[2],axis[0]*side[1]-axis[1]*side[0]]
            n=8;vs=[tuple(p[k]+r*(side[k]*math.cos(j*math.pi/n)+up[k]*math.sin(j*math.pi/n)) for k in range(3)) for p in [a,b] for j in range(n+1)]
            fs=[(j,j+1,j+n+2,j+n+1) for j in range(n)]+[tuple(range(n,-1,-1)),tuple(range(n+1,2*n+2)),(0,n,n*2+1,n+1)]
            return mesh(label,vs,fs,mat)
        def cylinder(label,p,r,length,mat):
            segments=10 if proxy else 24
            vs=[(p[0]+r*math.cos(i*math.tau/segments),p[1]+r*math.sin(i*math.tau/segments),p[2]+z) for z in [0,length] for i in range(segments)]
            fs=[tuple(range(segments-1,-1,-1)),tuple(range(segments,segments*2))]+[(i,(i+1)%segments,(i+1)%segments+segments,i+segments) for i in range(segments)]
            return mesh(label,vs,fs,mat)
        def roof_surface(width,depth,z,rise,upturn):
            nx=max(4,math.ceil(width/(1.2 if proxy else .32)));ny=max(4,math.ceil(depth/(1.2 if proxy else .42)))
            def roof_z(x,y):
                tx=abs(x)/(width/2);ty=abs(y)/(depth/2);t=max(tx,ty)
                return z+rise*(1-t)**1.25+upturn*t**8*(.35+.65*tx*ty)
            vs=[(width*(i/nx-.5),depth*(j/ny-.5),roof_z(width*(i/nx-.5),depth*(j/ny-.5))+layer) for layer in [0,.18] for j in range(ny+1) for i in range(nx+1)]
            n=(nx+1)*(ny+1);fs=[]
            for j in range(ny):
                for i in range(nx):
                    a=j*(nx+1)+i;fs += [(a,a+nx+1,a+nx+2,a+1),(a+n,a+1+n,a+nx+2+n,a+nx+1+n)]
            for j in range(ny):
                for i in [0,nx]:a=j*(nx+1)+i;b=a+nx+1;fs.append((a,b,b+n,a+n))
            for i in range(nx):
                for j in [0,ny]:a=j*(nx+1)+i;b=a+1;fs.append((a,b,b+n,a+n))
            mesh('thick curved hip roof',vs,fs,roof)
            if not proxy:
                # Raised tile ridges run down each roof face; all align with the physical shell.
                for side in [-1,1]:
                    for j in range(max(2,int(depth/.48))+1):
                        y=-depth*.48+j*depth*.96/max(2,int(depth/.48))
                        stop=min(width*.5, max(.12,(1-abs(y)/(depth*.5))*width*.5))
                        for k in range(6):
                            x0=side*(width*.5-stop*k/6);x1=side*(width*.5-stop*(k+1)/6)
                            tile_roll('rounded ceramic tile roll',(x0,y,roof_z(x0,y)+.19),(x1,y,roof_z(x1,y)+.19),.065,roof)
                for side in [-1,1]:
                    for j in range(max(2,int(width/.42))+1):
                        x=-width*.48+j*width*.96/max(2,int(width/.42));stop=min(depth*.5,max(.12,(1-abs(x)/(width*.5))*depth*.5))
                        for k in range(6):
                            y0=side*(depth*.5-stop*k/6);y1=side*(depth*.5-stop*(k+1)/6)
                            tile_roll('rounded ceramic end roll',(x,y0,roof_z(x,y0)+.19),(x,y1,roof_z(x,y1)+.19),.065,roof)
                for side in [-1,1]:
                    for k in range(16):
                        y0=depth*(k/16-.5);y1=depth*((k+1)/16-.5);x=side*width/2
                        beam('eave fascia',(x,y0,roof_z(x,y0)-.035),(x,y1,roof_z(x,y1)-.035),.15,.2,wood)
                tile_roll('rounded ridge cap',(-width*.12,0,z+rise+.20),(width*.12,0,z+rise+.20),.16,roof)
        kind=item['kind']
        summaries.append({'kind':kind,'center':item['center'],'size':item['size'],'height':h,'proxy':proxy})
        if proxy and kind in ['curved_pavilion','beam_gate'] and 'portal_tests' in api:
            api['portal_tests'].append({'name':kind+' '+str(index),'origin_m':point(0,-d/2-1,base+1),
                'direction':[-sa,ca,0],'distance_m':d+2,'clear_width_m':w-1})
        if kind=='box_assembly':
            for part_index,part in enumerate(item['parts']):
                x,y,z=part['position'];dx,dy,dz=part['scale'];angle=math.radians(part.get('yaw_deg',0));co,si=math.cos(angle),math.sin(angle)
                # The detailed and structural representations use identical
                # transformed solids; omit only tiny non-structural trim in proxy.
                if proxy and (min(dx,dy,dz)<.06 or dx*dy*dz<.008):continue
                vertices=[(x+xx*dx/2*co-yy*dy/2*si,y+xx*dx/2*si+yy*dy/2*co,z+zz*dz)
                    for zz in [0,1] for xx,yy in [(-1,-1),(1,-1),(1,1),(-1,1)]]
                mesh('assembled component '+str(part_index),vertices,FACES,part['material'])
        elif kind=='roof_service':
            # Independent roof equipment on an authored roof elevation. Never
            # extend its plinth to terrain: both representations keep the roof.
            box('service platform',(0,0,base+.10),(w,d,.20),stone)
            mode=item['service_type']
            if mode=='tank':
                radius=min(w,d)*.28;bottom=base+.55;length=max(.8,h-.65)
                for x in [-radius*.7,radius*.7]:
                    for y in [-radius*.7,radius*.7]:box('tank support',(x,y,base+.36),(.18,.18,.32),wood)
                cylinder('service tank',(0,0,bottom),radius,length,roof)
                cylinder('tank crown',(0,0,bottom+length),radius*1.025,.10,wood)
                if not proxy:
                    for t in [.03,.33,.68,.98]:cylinder('tank reinforcing band',(0,0,bottom+length*t),radius*1.025,.055,wood)
                    cylinder('service riser',(radius+.20,0,base+.2),.07,h-.22,wood)
                    beam('tank feed',(radius+.2,0,base+h-.10),(0,0,base+h-.10),.12,.12,wood)
            elif mode=='hvac':
                for side in [-1,1]:
                    x=side*w*.25
                    box('air-handler curb',(x,0,base+.3),(w*.42,d*.72,.2),wood)
                    box('air-handler casing',(x,0,base+.4+h*.3),(w*.39,d*.65,h*.6),roof)
                    cylinder('extraction fan',(x,0,base+.4+h*.6),min(w*.15,d*.22),.22,wood)
                    if not proxy:
                        for j in range(9):box('air-handler louvre',(x,-d*.331,base+.5+j*h*.051),(w*.32,.035,.04),wood)
                        for side2 in [-1,1]:beam('fan guard',(x-w*.12,side2*.16,base+.67+h*.6),(x+w*.12,side2*.16,base+.67+h*.6),.035,.035,roof)
                box('connecting duct',(0,d*.22,base+.55),(w*.5,d*.24,.38),wood)
            else:
                box('antenna mounting',(0,0,base+.4),(w*.4,d*.4,.6),roof)
                radius=min(w,d)*.22
                for x in [-radius,radius]:
                    beam('antenna mast leg',(x,0,base+.7),(0,0,base+h),.12,.12,wood)
                for y in [-radius,radius]:beam('antenna mast brace',(0,y,base+.7),(0,0,base+h),.12,.12,wood)
                if not proxy:
                    for t in [.40,.62,.83]:beam('antenna crossbar',(-radius,0,base+h*t),(radius,0,base+h*t),.07,.07,roof)
                    for x in [-radius*.65,radius*.65]:box('radio panel',(x,0,base+h*.77),(.27,.16,h*.3),stone)
            if not proxy:
                # Guarding ties each installation into its surrounding roof.
                for x in [-w*.45,w*.45]:
                    for y in [-d*.45,d*.45]:cylinder('service guard post',(x,y,base+.2),.03,.9,wood)
                for y in [-d*.45,d*.45]:beam('service guard rail',(-w*.45,y,base+1.1),(w*.45,y,base+1.1),.045,.045,wood)
        elif kind=='access_ramp':
            low=min(height(*point(x,y,0)[:2]) for x in [-w/2,w/2] for y in [-d/2,d/2])-.08
            vertices=[(-w/2,-d/2,low),(w/2,-d/2,low),(w/2,d/2,low),(-w/2,d/2,low),
                (-w/2,-d/2,base),(w/2,-d/2,base),(w/2,d/2,base+h),(-w/2,d/2,base+h)]
            mesh('continuous access ramp',vertices,FACES,stone)
            if not proxy:
                for x in [-w/2+.06,w/2-.06]:
                    beam('ramp handrail',(x,-d/2,base+.94),(x,d/2,base+h+.94),.05,.05,wood)
                    for i in range(6):
                        y=d*(i/5-.5);cylinder('ramp rail post',(x,y,base+h*i/5),.035,.94,wood)
        elif kind=='graphic_panel':
            # Readable UV graphics use a separate non-colliding face. The board
            # remains in the structural companion and receives the same pose.
            box('display cabinet',(0,0,base+h/2),(w,d,h),wood)
            if not proxy:
                front=-d/2-.015
                ob=mesh('graphic display',[(-w*.47,front,base+h*.035),(w*.47,front,base+h*.035),
                    (w*.47,front,base+h*.965),(-w*.47,front,base+h*.965)],[(0,1,2,3)],item['window_material'],collision=False,preserve_winding=True)
                layer=ob.data.uv_layers.new(name='GraphicUV')
                coords=[(1,0),(0,0),(0,1),(1,1)]
                for loop in ob.data.loops:layer.data[loop.index].uv=coords[loop.vertex_index]
        elif kind=='garden_bench':
            # Supported seat/back construction, usable across garden and street families.
            for x in [-w*.37,w*.37]:
                for y in [-d*.32,d*.32]:box('bench leg',(x,y,base+.23),(.105,.105,.46),wood,True)
                box('seat bearer',(x,0,base+.40),(.12,d,.10),wood)
                box('back stile',(x,d*.36,base+h*.5),(.105,.105,h),wood,True)
            if proxy:box('seat envelope',(0,0,base+.47),(w,d,.08),wood)
            else:
                for i in range(4):box('seat board',(0,-d*.5+d*(i+.5)/4,base+.47),(w,d/4-.012,.07),wood)
            for z in [base+h*.69,base+h*.92]:box('back rail',(0,d*.36,z),(w,.09,.15),wood)
            box('lower stretcher',(0,0,base+.2),(w*.77,.09,.10),wood)
        elif kind=='curved_pavilion':
            # The floor stays flush with neighbouring route tops; posts do not cross the open aisle.
            box('foundation',(0,0,base-.14),(w+.25,d+.25,.28),stone,True)
            floor=item.get('floor_material',wood)
            if proxy:box('deck',(0,0,base+.018),(w,d,.036),floor)
            else:
                n=max(2,round(d/.2))
                for i in range(n):box('deck board',(0,-d/2+(i+.5)*d/n,base+.018),(w,d/n-.006,.036),floor)
            for x in [-w/2+.24,w/2-.24]:
                for y in [-d/2+.24,d/2-.24]:
                    box('stone shoe',(x,y,base+.1),(.56,.56,.2),stone)
                    box('post',(x,y,base+h/2),(.28,.28,h),wood)
                    if not proxy:
                        for sign in [-1,1]:beam('knee bracket',(x,y,base+h-.6),(x+sign*.5,y,base+h-.12),.16,.17,wood)
                        for sign in [-1,1]:beam('transverse knee bracket',(x,y,base+h-.6),(x,y+sign*.5,base+h-.12),.16,.17,wood)
                        for zz,ww in [(base+.23,.33),(base+h-.44,.42),(base+h-.17,.54)]:box('post joinery collar',(x,y,zz),(ww,ww,.13),wood)
            for y in [-d/2+.24,d/2-.24]:box('cross beam',(0,y,base+h-.04),(w+.6,.36,.4),wood)
            for x in [-w/2+.24,w/2-.24]:box('long beam',(x,0,base+h-.04),(.34,d+.5,.36),wood)
            if not proxy:
                for i in range(max(3,int(d/.65))+1):
                    y=-d*.5+i*d/max(3,int(d/.65));beam('rafter',(-w*.56,y,base+h+.03),(w*.56,y,base+h+.03),.105,.14,wood)
                box('tea bench',(-w*.35,0,base+.38),(.6,d*.50,.12),wood)
                for y in [-d*.20,d*.20]:box('bench foot',(-w*.35,y,base+.18),(.35,.15,.36),wood)
            roof_surface(w+1.7,d+1.7,base+h+.17,item.get('roof_rise',1.8),item.get('upturn',.45))
        elif kind=='beam_gate':
            for x in [-w*.35,w*.35]:
                box('grounded shoe',(x,0,base+.10),(.7,.7,.2),stone,True)
                cylinder('round column',(x,0,base),.19,h,wood)
            box('lower lintel',(0,0,base+h-.68),(w*.90,.30,.30),wood)
            box('central tie',(0,0,base+h-.36),(.2,.23,.6),wood)
            for i in range(12):
                x0=w*(i/12-.5);x1=w*((i+1)/12-.5)
                z0=base+h+.22*(abs(2*x0/w)**3);z1=base+h+.22*(abs(2*x1/w)**3)
                beam('curved upper lintel',(x0,0,z0),(x1,0,z1),.52,.3,wood)
                beam('dark upper cap',(x0,0,z0+.18),(x1,0,z1+.18),.62,.08,roof)
        elif kind=='capped_wall':
            box('grounded plinth',(0,0,base+.22),(w,d+.15,.44),stone,True)
            box('plaster panel',(0,0,base+h/2),(w,d,h),wall,True)
            for x in [-w/2,w/2]:box('wall post',(x,0,base+h/2),(.23,d+.12,h+.12),wood,True)
            roof_surface(w+.32,d+.7,base+h,.3,.08)
        elif kind=='street_frontage':
            if item.get('urban_detail'):
                try:from .urban_frontage import build as build_urban
                except ImportError:from urban_frontage import build as build_urban
                build_urban(item,box,beam,cylinder,mesh,proxy)
                continue
            box('building solid',(0,0,base+h/2),(w,d,h),wall,True)
            box('ground plinth',(0,-d/2-.06,base+.17),(w+.16,.20,.34),stone,True)
            bays=max(2,int(w/2.5));floors=max(1,int(h/3));glass=item.get('window_material',roof)
            for level in range(floors):
                z=base+(level+.5)*h/floors
                for bay in range(bays):
                    x=(bay+.5)*w/bays-w/2;bw=w/bays*.74;bh=h/floors*.60
                    box('recess frame',(x,-d/2-.07,z),(bw+.16,.15,bh+.16),wood)
                    box('window plane',(x,-d/2-.155,z),(bw,.04,bh),glass)
                    if not proxy:
                        box('mullion',(x,-d/2-.19,z),(.06,.065,bh),wood)
                        box('window sill',(x,-d/2-.25,z-bh/2),(bw+.2,.4,.10),stone)
            box('store awning',(0,-d/2-.7,base+2.7),(w*.92,1.45,.20),roof)
            box('sign fascia',(0,-d/2-.8,base+3.06),(w*.82,.18,.42),item.get('sign_material',wood))
            box('roof cornice',(0,0,base+h),(w+.45,d+.4,.28),stone)
    return summaries
