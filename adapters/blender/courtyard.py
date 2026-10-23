"""Fitted courts, covered arcades and apses, parameterized in scene coordinates."""
import math
import numpy as np
from mathutils import Vector


def fitted_court(api):
    cfg=api['cfg'];rng=api['rng'];cx,cy=api['center'];rx,ry=cfg['court_radii']
    mesh,finish=api['mesh'],api['finish_stone'];mat=api['spec']['path_material']
    spacing=cfg.get('paver_spacing',.78);seeds=[]
    for row in range(-math.ceil(ry/spacing)-1,math.ceil(ry/spacing)+2):
        for col in range(-math.ceil(rx/spacing)-1,math.ceil(rx/spacing)+2):
            x=col*spacing+rng.uniform(-.30,.30);y=row*spacing+rng.uniform(-.30,.30)
            # Local changes in slab size break the regular cellular pattern.
            keep=rng.random()>.14+.15*max(0,api['n'](x,y,.38,9))
            if keep and (x/rx)**2+(y/ry)**2<1.02:seeds.append([cx+x,cy+y])
    seeds=np.array(seeds);count=0
    for i,seed in enumerate(seeds):
        r=api['court'](*seed)
        if r>.85 and rng.random()<.20:continue
        poly=[seed+np.array(p) for p in [(-2,-2),(2,-2),(2,2),(-2,2)]]
        for other in np.argsort(((seeds-seed)**2).sum(1))[1:20]:
            normal=seeds[other]-seed;mid=(seed+seeds[other])*.5;result=[]
            for j,p in enumerate(poly):
                q=poly[(j+1)%len(poly)];dp=float(np.dot(p-mid,normal));dq=float(np.dot(q-mid,normal))
                if dp<=0:result.append(p)
                if (dp<=0)!=(dq<=0):result.append(p+(q-p)*dp/(dp-dq))
            poly=result
            if len(poly)<3:break
        if len(poly)<3:continue
        # Clip the cell to a convex ellipse. Radially projecting each vertex
        # folds boundary cells back on themselves, producing inverted crowns.
        for angle in np.linspace(0,math.tau,96,endpoint=False):
            normal=np.array([math.cos(angle)/rx,math.sin(angle)/ry]);result=[]
            for j,p in enumerate(poly):
                q=poly[(j+1)%len(poly)]
                dp=float(np.dot(p-np.array([cx,cy]),normal)-1)
                dq=float(np.dot(q-np.array([cx,cy]),normal)-1)
                if dp<=0:result.append(p)
                if (dp<=0)!=(dq<=0):result.append(p+(q-p)*dp/(dp-dq))
            poly=result
            if len(poly)<3:break
        if len(poly)<3:continue
        mean=np.mean(poly,axis=0);gap=rng.uniform(.950,.977);poly=[mean+(p-mean)*gap for p in poly]
        if rng.random()<.38:
            j=rng.randrange(len(poly));p=poly[j]
            poly[j:j+1]=[p*.89+poly[j-1]*.11,p*.85+poly[(j+1)%len(poly)]*.15]
        top=cfg.get('court_base_z',0)+.135+.009*api['n'](*mean,.7,2)-.055*api['smooth'](.82,1.,r);N=len(poly)
        vs=[(float(p[0]),float(p[1]),z) for z in [top-.14,top] for p in poly]
        vs.append((float(mean[0]),float(mean[1]),top+.002))
        faces=[tuple(range(N-1,-1,-1))]+[(N+j,N+(j+1)%N,2*N) for j in range(N)]+[(j,(j+1)%N,(j+1)%N+N,j+N) for j in range(N)]
        patch=api['smooth'](-.18,.38,api['n'](*mean,.42,4))
        moss=max(api['smooth'](.48,1.,r)*rng.uniform(.1,.8),patch*.30);value=rng.uniform(.65,1.10)
        colors=[(value,moss,0,1)]*(2*N)+[(value,moss*.08,0,1)]
        finish(mesh('Fitted court slab',vs,faces,mat,colors=colors),.014);count+=1
        plant=cfg.get('scatter',{}).get('plant_asset')
        if plant and r>.65 and rng.random()<.38:
            p=poly[rng.randrange(N)];s=rng.uniform(.16,.38)
            api['instance'](plant,(float(p[0]),float(p[1]),top-.012),(s,s,s*.58),rng.uniform(0,math.tau),i,False)
    return count


def build_arcades(api):
    cfg=api['cfg'];rng=api['rng'];block,mesh,finish,arch,cylinder=[api[k] for k in ['block','mesh','finish_stone','arch','cylinder']]
    plant=cfg.get('scatter',{}).get('plant_asset');structures=0
    for run in cfg.get('arcades',[]):
        start,end=Vector((*run['start'],0)),Vector((*run['end'],0));delta=end-start;length=delta.length;tangent=delta.normalized();side=Vector((-tangent.y,tangent.x,0))
        yaw=math.atan2(tangent.y,tangent.x);width=run.get('width',2.5);base=run.get('base_z',.08);h=run.get('height',4.5);bays=run.get('bays',max(2,round(length/3.3)));bay=length/bays
        mat=run.get('material',api['spec']['path_material']);trim=run.get('trim_material',mat);roof=run.get('roof_material',trim)
        def p(x,y,z):return start+tangent*x+side*y+Vector((0,0,z))
        # The covered aisle is traversable at grade; its pavement joins the court.
        for row in range(max(1,round(width/.70))):
            for col in range(max(1,round(length/.9))):
                nx=max(1,round(length/.9));ny=max(1,round(width/.70))
                block(p((col+.5)*length/nx,(row+.5)*width/ny,base-.03),(length/nx-.018,width/ny-.018,.14),mat,yaw,.016)
        # Paired arcades support a real roof and create depth behind each opening.
        for j in range(bays):
            for yy in ([0] if run.get('backing_wall',False) else [0,width]):
                x=(j+.5)*bay;center=p(x,yy,base)
                arch(center,bay+.10,.52,h,mat,yaw,thickness=.37)
                radius=(bay+.10)/2;spring=h-radius
                for k in range(16):
                    x0=-radius+2*radius*k/16;x1=-radius+2*radius*(k+1)/16
                    z0=spring+math.sqrt(max(0,radius*radius-x0*x0));z1=spring+math.sqrt(max(0,radius*radius-x1*x1))
                    vs=[p(x+xx,yy+depth,base+zz) for depth in [-.245,.245] for xx,zz in [(x0,z0),(x1,z1),(x1,h+.10),(x0,h+.10)]]
                    finish(mesh('Arcade spandrel',vs,[(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)],mat),.012)
                # Narrow engaged shafts distinguish the springing and support line.
                for sign in [-1,1]:
                    point=p(x+sign*(radius-.185),yy-.30,base)
                    for zz,rr,dd in [(.11,.25,.22),(.28,.19,.12),(spring*.5,.125,max(.1,spring-.5)),(spring-.18,.19,.20)]:
                        cylinder(point+Vector((0,0,zz)),rr,dd,trim,20)
            # Coursed backing and narrow windows give the covered aisle an interior.
            wall_height=h if run.get('backing_wall',False) else .64
            rows=max(2,round(wall_height/.35));hh=wall_height/rows;cols=max(4,round(bay/.62))
            if j in run.get('open_bays',[]):rows=0
            for row in range(rows):
                for k in range(cols):
                    x=j*bay+(k+.5)*bay/cols;z=hh*(row+.5);dx=x-(j+.5)*bay
                    if run.get('backing_wall',False) and abs(dx)<.42 and 1.5<z<h-1.0+math.sqrt(max(0,.42**2-dx**2)):continue
                    if run.get('broken_end') and j==bays-1 and k>cols-2 and z>h*.72:continue
                    block(p(x,width,base+z),(bay/cols-.014,.65,hh-.012),mat,yaw,.020)
            if run.get('backing_wall',False):
                arch(p((j+.5)*bay,width+.34,base+1.48),1.10,.22,h-2.20,trim,yaw,thickness=.17)
                block(p((j+.5)*bay,width+.35,base+1.48),(1.2,.82,.18),trim,yaw,.024)
            # Discreet roundels occupy spandrels, with real geometric depth.
            if j>0 and run.get('detail_material'):
                for radius,tube in [(.22,.026),(.29,.020)]:api['ring'](p(j*bay,-.32,base+h-.58),radius,tube,run['detail_material'],(math.pi/2,0,yaw))
        for j in range(bays+1):
            for zz,dim in [(base+.17,(.9,.96,.34)),(base+h*.45,(.58,.48,h*.86)),(base+h-.10,(.82,.74,.30))]:
                block(p(j*bay,width+.35,zz),dim,mat,yaw,.025)
        for row,(zz,ww,hh) in enumerate([(h+.12,.67,.22),(h+.35,.84,.18),(h+.50,.74,.14)]):
            for j in range(bays*3):
                for yy in [0,width]:block(p((j+.5)*length/(bays*3),yy,base+zz),(length/(bays*3)-.014,ww,hh),trim,yaw,.020)
        # Sloped overlapping roof courses; tile scale and restrained breaks are data.
        courses=max(3,round(width/.38));cols=max(3,round(length/.44));slope=run.get('roof_rise',.62)/width
        for j in range(courses+1):
            for i in range(cols):
                if run.get('broken_end',False) and i>cols-4 and j<2 and rng.random()<.65:continue
                x=(i+.5)*length/cols;y=-.38+j*(width+.76)/(courses+1);dy=(width+.76)/(courses+1)+.09;dx=length/cols-.018;z=base+h+.57+y*slope
                missing=False
                for damage in run.get('roof_openings',[]):
                    start_x,end_x,depth=damage
                    boundary=depth+.06*math.sin(x*4.1)+.035*math.cos(x*9.3)
                    if start_x<x/length<end_x and j/(courses+1)<boundary:missing=True
                if missing:continue
                verts=[];faces=[];nx=5
                for thickness in [0,.07]:
                    for yy in [-dy/2,dy/2]:
                        for k in range(nx):
                            xx=-dx/2+dx*k/(nx-1);curve=.09*math.cos(xx/dx*math.pi)
                            verts.append(p(x+xx,y+yy,z+yy*slope+curve+thickness))
                for k in range(nx-1):
                    faces.extend([(k,k+1,nx+k+1,nx+k),(2*nx+k,3*nx+k,3*nx+k+1,2*nx+k+1),
                        (k,2*nx+k,2*nx+k+1,k+1),(nx+k,nx+k+1,3*nx+k+1,3*nx+k)])
                faces.extend([(0,nx,3*nx,2*nx),(nx-1,3*nx-1,4*nx-1,2*nx-1)])
                mesh('Curved clay roof tile',verts,faces,roof)
        # Intact rafters explain how surviving roof fragments are supported.
        for j in range(bays*2+1):
            x=j*length/(bays*2);y=width/2;z=base+h+.50+y*slope
            verts=[p(x+xx,y+yy,z+yy*slope+zz) for zz in [-.09,.04] for xx,yy in [(-.085,-width/2-.25),(.085,-width/2-.25),(.085,width/2+.25),(-.085,width/2+.25)]]
            finish(mesh('Roof support rafter',verts,[(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)],trim),.010)
        # Plant clusters occupy foundation pockets and a few cornice joints.
        if plant:
            for i in range(bays*35):
                x=rng.uniform(.3,length-.3);yy=rng.choice([-.45,width+.38])+rng.uniform(-.24,.24);pos=p(x,yy,0)
                z=max(api['height'](pos.x,pos.y),base)-.015;s=rng.uniform(.38,1.10)
                api['instance'](plant,(pos.x,pos.y,z),(s,s,s*.7),rng.uniform(0,math.tau),i,False)
            for j in range(bays*2):
                x=rng.uniform(.4,length-.4);pos=p(x,0,base+h+.47);s=rng.uniform(.20,.36)
                api['instance'](plant,pos,(s,s,s*.7),rng.uniform(0,math.tau),j,False)
        structures+=1
    return structures


def build_apses(api):
    cfg=api['cfg'];rng=api['rng'];block,wedge,mesh,finish,arch=[api[k] for k in ['block','wedge','mesh','finish_stone','arch']]
    for item in cfg.get('apses',[]):
        cx,cy=item['center'];r=item['radius'];h=item['height'];base=item.get('base_z',.08);mat=item.get('material',api['spec']['path_material']);trim=item.get('trim_material',mat);roof=item.get('roof_material',trim)
        rotation=math.radians(item.get('rotation_deg',0));opening=math.radians(item.get('opening_degrees',100));a0=math.pi/2+opening/2+rotation;a1=math.pi/2+math.tau-opening/2+rotation
        rows=round(h/.37);segments=max(12,round((a1-a0)*r/.72));hh=h/rows
        from curved_wall import build_wall
        build_wall(item,lambda name,vs,fs,material:mesh(name,vs,fs,material,colors=[(.96,.04,0,1)]*len(vs),smooth_faces=False),mat)
        for zz,extra,thick in [(base+.15,.40,.28),(base+.42,.35,.16),(base+h+.05,.42,.25),(base+h+.29,.54,.16)]:
            for i in range(segments):
                aa=a0+(a1-a0)*i/segments;wedge(cx,cy,zz,r-.32,r+extra,aa+.003,aa+(a1-a0)/segments-.003,thick,trim)
        # A semicircular tiled vault, cut open toward the court.
        rise=item.get('roof_rise',r*.78);bands=11;sectors=48
        roof_a0,roof_a1=(0,math.tau) if item.get('complete_roof') else (a0,a1)
        for band in range(bands):
            for sector in range(sectors):
                t0=band*math.pi/2/bands;t1=(band+1)*math.pi/2/bands-.003;aa=roof_a0+sector*(roof_a1-roof_a0)/sectors;bb=roof_a0+(sector+1)*(roof_a1-roof_a0)/sectors-.002
                verts=[]
                for extra in [0,.10]:
                    for t,a in [(t0,aa),(t0,bb),(t1,bb),(t1,aa)]:verts.append((cx+(r+.15+extra)*math.cos(t)*math.cos(a),cy+(r+.15+extra)*math.cos(t)*math.sin(a),base+h+.39+(rise+extra)*math.sin(t)))
                finish(mesh('Vault shell tile',verts,[(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)],roof),.008)
        if item.get('front_portal'):
            width=2*r*math.sin(opening/2);front=r*math.cos(opening/2);yaw=rotation;ca,sa=math.cos(yaw),math.sin(yaw)
            def point(x,y,z):return (cx+x*ca-y*sa,cy+x*sa+y*ca,base+z)
            arch(point(0,front,0),width,1.05,h+.15,mat,yaw,thickness=.52)
            rad=width/2;spring=h+.15-rad
            for k in range(24):
                x0=-rad+width*k/24;x1=-rad+width*(k+1)/24;z0=spring+math.sqrt(max(0,rad*rad-x0*x0));z1=spring+math.sqrt(max(0,rad*rad-x1*x1))
                vs=[point(x,front+y,z) for y in [-.50,.50] for x,z in [(x0,z0),(x1,z1),(x1,h+.48),(x0,h+.48)]]
                finish(mesh('Sanctuary entrance wall',vs,[(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)],mat),.018)
            for z,depth,thick in [(h+.48,1.22,.23),(h+.69,1.38,.18)]:block(point(0,front,z),(width+.5,depth,thick),trim,yaw,.025)
        # The entrance jambs continue the wall and cornice down to the paving.
        for a in [a0,a1]:
            x,y=cx+math.cos(a)*r,cy+math.sin(a)*r
            for zz,dim in [(base+.16,(.9,.9,.32)),(base+h/2,(.61,.61,h-.32)),(base+h+.14,(.94,.94,.38))]:block((x,y,zz),dim,trim,a,.025)
        plant=cfg.get('scatter',{}).get('plant_asset')
        if plant:
            for i in range(160):
                a=rng.uniform(a0,a1);rr=r+rng.uniform(.28,.75);x,y=cx+math.cos(a)*rr,cy+math.sin(a)*rr;s=rng.uniform(.28,.70)
                api['instance'](plant,(x,y,max(base,api['height'](x,y))-.02),(s,s,s*.70),a,i,False)


def build_gardens(api):
    cfg=api['cfg'];rng=api['rng'];plant=cfg.get('scatter',{}).get('plant_asset');mat=api['spec']['path_material']
    for bed in cfg.get('garden_beds',[]):
        cx,cy=bed['center'];rx,ry=bed['radii'];raise_z=bed.get('height',.3);n=56
        vs=[(cx,cy,api['height'](cx,cy)+raise_z)];colors=[(.08,.86,.3,1)]
        for j in range(n):
            a=j*math.tau/n;x=cx+rx*math.cos(a);y=cy+ry*math.sin(a);vs.append((x,y,api['height'](x,y)+.015));colors.append((.10,.68,.25,1))
        api['mesh']('Planted earth bed',vs,[(0,j+1,(j+1)%n+1) for j in range(n)],api['spec']['floor_material'],colors=colors)
        if plant:
            for i in range(bed.get('plants',95)):
                a=rng.uniform(0,math.tau);r=math.sqrt(rng.random())*.96;x=cx+rx*r*math.cos(a);y=cy+ry*r*math.sin(a);s=rng.uniform(.38,1.18)
                api['instance'](plant,(x,y,api['height'](x,y)+raise_z*(1-r)-.02),(s,s*rng.uniform(.7,1.2),s*rng.uniform(.58,.98)),a,i,False)
    for approach in cfg.get('approaches',[]):
        ax,ay=approach['start'];bx,by=approach['end'];length=math.hypot(bx-ax,by-ay);yaw=math.atan2(by-ay,bx-ax);ca,sa=math.cos(yaw),math.sin(yaw);width=approach.get('width',3.5)
        rows=max(2,int(length/.72));cols=max(2,int(width/.78))
        for j in range(rows):
            for i in range(cols):
                if j>rows*.75 and rng.random()<.20:continue
                x=(j+.5)*length/rows;y=(i+.5)*width/cols-width/2;xw=ax+x*ca-y*sa;yw=ay+x*sa+y*ca
                top=api['height'](xw,yw)+.048
                api['block']((xw,yw,top-.05),(length/rows-.02,width/cols-.024,.10),mat,yaw+rng.uniform(-.025,.025),.017)
    for detail in cfg.get('court_inlays',[]):
        x,y=detail.get('center',[0,0]);material=detail['material']
        for radius in detail.get('radii',[2.4,2.46]):api['ring']((x,y,.146),radius,.013,material)
