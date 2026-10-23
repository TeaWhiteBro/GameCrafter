"""Connected masonry, terraces and open domes. All dimensions/materials are recipe data."""
import math
import numpy as np
from mathutils import Vector

def build_terrace(api):
    cfg=api['cfg'];rng=api['rng'];t=cfg['terrace'];mat=api['spec']['path_material'];cx,cy=api['center'];radius=t['radius'];top=t['height']
    wedge,cylinder,block,mesh,finish=[api[k] for k in ['wedge','cylinder','block','mesh','finish_stone']]
    cylinder((cx,cy,top*.5),radius,top,mat,128)
    # A true retaining structure, with staggered masonry courses and moulded rim.
    for row in range(max(1,int(top/.32))):
        count=64
        for i in range(count):
            a=(i+.5*(row%2))*math.tau/count
            wedge(cx,cy,.32*(row+.5),radius-.22,radius+.18,a+.002,a+math.tau/count-.004,.31,mat)
    for i in range(64):
        a=i*math.tau/64
        wedge(cx,cy,top-.005,radius-.3,radius+.32,a+.002,a+math.tau/64-.004,.16,mat)
    # Jittered Voronoi slabs read as fitted, worn flagstones rather than a brick grid.
    seeds=[];spacing=t.get('paver_spacing',.66);extent=math.ceil(radius/spacing)+1
    for row in range(-extent,extent+1):
        for col in range(-extent,extent+1):
            x=col*spacing+rng.uniform(-.21,.21);y=row*spacing+rng.uniform(-.21,.21)
            if math.hypot(x,y)<radius-.22:seeds.append(np.array([x+cx,y+cy]))
    seeds=np.array(seeds);count=0
    for i,seed in enumerate(seeds):
        r=np.linalg.norm(seed-np.array([cx,cy]))
        if r>radius-.7 and rng.random()<.12:continue
        poly=[seed+np.array([x,y]) for x,y in [(-1.5,-1.5),(1.5,-1.5),(1.5,1.5),(-1.5,1.5)]]
        for other in np.argsort(((seeds-seed)**2).sum(1))[1:18]:
            normal=seeds[other]-seed;mid=(seed+seeds[other])*.5;result=[]
            for j,p in enumerate(poly):
                q=poly[(j+1)%len(poly)];dp=float(np.dot(p-mid,normal));dq=float(np.dot(q-mid,normal))
                if dp<=0:result.append(p)
                if (dp<=0)!=(dq<=0):result.append(p+(q-p)*dp/(dp-dq))
            poly=result
            if len(poly)<3:break
        if len(poly)<3:continue
        # Trim the outer envelope, then sink occasional damaged stones into bedding.
        poly=[np.array([cx,cy])+(p-np.array([cx,cy]))*min(1,(radius-.23)/np.linalg.norm(p-np.array([cx,cy]))) for p in poly]
        mean=np.mean(poly,axis=0);poly=[mean+(p-mean)*rng.uniform(.935,.98) for p in poly]
        if rng.random()<.46:
            corner=rng.randrange(len(poly));p=poly[corner]
            poly[corner:corner+1]=[p*.86+poly[corner-1]*.14,p*.84+poly[(corner+1)%len(poly)]*.16]
        z=top+.045+rng.uniform(-.014,.013);N=len(poly)
        vs=[(float(p[0]),float(p[1]),zz) for zz in [z-.14,z] for p in poly]
        vs.append((float(mean[0]),float(mean[1]),z+.002))
        faces=[tuple(range(N-1,-1,-1))]+[(N+j,N+(j+1)%N,N*2) for j in range(N)]+[(j,(j+1)%N,(j+1)%N+N,j+N) for j in range(N)]
        edge_moss=max(0,(r/radius-.40)/.60)*rng.uniform(.45,1.0);value=rng.uniform(.72,1.08)
        colors=[(value,edge_moss,0,1)]*(N*2)+[(value,edge_moss*.06,0,1)]
        finish(mesh('Fitted flagstone',vs,faces,mat,colors=colors),.016);count+=1
        plant=cfg.get('scatter',{}).get('plant_asset')
        if plant and r>radius*.68 and rng.random()<.32:
            p=poly[rng.randrange(N)];s=rng.uniform(.18,.42)
            api['instance'](plant,(float(p[0]),float(p[1]),z-.015),(s,s,s*.52),rng.uniform(0,math.tau),i,False)
    # Fallen fragments share the wall material and collect along the perimeter.
    # Keep the dueling space and the stair opening clear.
    for i in range(cfg.get('masonry_fragments',95)):
        a=rng.uniform(0,math.tau)
        if math.radians(62)<a<math.radians(118):continue
        r=rng.uniform(radius-.85,radius-.22);x=cx+math.cos(a)*r;y=cy+math.sin(a)*r
        sx=rng.uniform(.11,.42);sy=rng.uniform(.10,.28);h=rng.uniform(.04,.15)
        block((x,y,top+.052+h*.5),(sx,sy,h),mat,rng.uniform(0,math.tau),.012)
    # Quiet astronomical inlays, flush with the stone rather than decorative particles.
    inlay=cfg['engraving_material'];ring=api['ring']
    for r in [.60,2.0,2.08,4.0,4.09]:ring((cx,cy,top+.061),r,.017,inlay)
    for i in range(8):
        a=i*math.tau/8;ca,sa=math.cos(a),math.sin(a);length=1.66 if i%2==0 else 1.08
        pts=[(.23,-.06),(length,0),(.23,.06),(.45,0)]
        mesh('Inlaid compass point',[(cx+x*ca-y*sa,cy+x*sa+y*ca,top+.063) for x,y in pts],[(0,1,3),(1,2,3)],inlay,False)
    for i in range(48):
        a=i*math.tau/48;r=2.22
        block((cx+math.cos(a)*r,cy+math.sin(a)*r,top+.057),(.16 if i%4 else .28,.018,.009),inlay,a,0)
    # Broad curved approach, each rise below the character step limit.
    steps=t.get('steps',8);rise=(top-.08)/steps
    for i in range(steps):
        r0=radius+.15+i*.43;r1=r0+.47;z=top-i*rise
        parts=10
        for j in range(parts):
            a=math.radians(67+j*4.6)
            wedge(cx,cy,z*.5,r0,r1,a+.002,a+math.radians(4.6)-.002,z,mat)
    # Low parapets with piers belong to the retaining platform, with deliberate entrances.
    for a0,a1 in [(5,56),(122,173),(178,208),(333,355)]:
        for row in range(2):
            num=max(2,int((a1-a0)/6))
            for i in range(num):
                a=math.radians(a0+(a1-a0)*(i+.5*(row%2))/num);b=a+math.radians((a1-a0)/num)-.006
                if row==1 and rng.random()<.12:continue
                wedge(cx,cy,top+.28+.31*row,radius-.10,radius+.30,a+.004,b,.30,mat)
        for a in [a0,a1]:
            rad=math.radians(a);x=cx+math.cos(rad)*(radius+.03);y=cy+math.sin(rad)*(radius+.03)
            block((x,y,top+.55),(.58,.58,1.10),mat,rad,.024)
            block((x,y,top+1.13),(.72,.72,.18),mat,rad,.026)
    return count

def build_structures(api):
    cfg=api['cfg'];rng=api['rng'];wedge=api['wedge'];block=api['block'];cylinder=api['cylinder'];mesh=api['mesh'];finish=api['finish_stone'];arch=api['arch'];ring=api['ring'];mat=cfg.get('structure_material',api['spec']['path_material']);metal=cfg.get('dome_material',mat)
    def portal_spandrel(cx,cy,base,width,depth,arch_height,wall_height,yaw=0):
        r=width*.5;spring=arch_height-r;ca,sa=math.cos(yaw),math.sin(yaw)
        for i in range(20):
            x0=-r+width*i/20;x1=-r+width*(i+1)/20
            z0=spring+math.sqrt(max(0,r*r-x0*x0));z1=spring+math.sqrt(max(0,r*r-x1*x1))
            vs=[]
            for yy in [-depth/2,depth/2]:
                for x,z in [(x0,z0),(x1,z1),(x1,wall_height),(x0,wall_height)]:vs.append((cx+x*ca-yy*sa,cy+x*sa+yy*ca,base+z))
            finish(mesh('Portal spandrel',vs,[(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)],mat),.012)
    def wall(cx,cy,base,radius,height,a0,a1,windows=(),broken=False):
        rows=max(1,round(height/.36));hh=height/rows;segments=max(8,round((a1-a0)*radius/.68))
        for row in range(rows):
            for i in range(-1 if row%2 else 0,segments):
                offset=.5*(row%2)
                aa=max(a0,a0+(a1-a0)*(i+offset)/segments);bb=min(a1,a0+(a1-a0)*(i+1+offset)/segments)
                mid=(aa+bb)*.5;z=(row+.5)*hh
                opening=False
                for w in windows:
                    dx=radius*math.atan2(math.sin(mid-w),math.cos(mid-w))
                    if abs(dx)<.47 and .92<z<2.61+math.sqrt(max(0,.47*.47-dx*dx)):opening=True
                if opening:continue
                damage=abs(math.atan2(math.sin(mid-.35),math.cos(mid-.35)))
                if broken and damage<.75 and z>height*(.68+.15*damage/.75):continue
                wedge(cx,cy,base+z,radius-.26,radius+.28,aa+.003,bb-.003,hh-.012,mat)
    def cornice(cx,cy,z,radius,broken=False):
        for dz,extra,depth in [(0,.04,.16),(.20,.16,.19),(.40,.27,.14)]:
            for i in range(48):
                a=i*math.tau/48
                if broken and abs(math.atan2(math.sin(a-.35),math.cos(a-.35)))<.80:continue
                wedge(cx,cy,z+dz,radius-.26,radius+extra,a+.002,a+math.tau/48-.002,depth,mat)
    def rib(cx,cy,base,radius,rise,angle,start=0,end=math.pi/2,width=.15):
        vs=[];fs=[];N=36
        az=Vector((math.cos(angle),math.sin(angle),0));side=Vector((-math.sin(angle),math.cos(angle),0))
        for i in range(N+1):
            t=start+(end-start)*i/N;p=Vector((cx,cy,base))+az*(radius*math.cos(t))+Vector((0,0,rise*math.sin(t)))
            normal=(az*math.cos(t)+Vector((0,0,math.sin(t)))).normalized()
            for a,b in [(-1,-1),(1,-1),(1,1),(-1,1)]:vs.append(p+side*(a*width*.5)+normal*(b*.047))
        for i in range(N):
            for j in range(4):fs.append((i*4+j,i*4+(j+1)%4,(i+1)*4+(j+1)%4,(i+1)*4+j))
        fs.extend([(3,2,1,0),(N*4,N*4+1,N*4+2,N*4+3)])
        return mesh('Dome structural rib',vs,fs,metal)
    def dome(cx,cy,base,radius,rise):
        for i in range(12):
            angle=i*math.tau/12
            rib(cx,cy,base,radius,rise,angle,end=(math.pi/2 if i not in [3,4] else 1.05))
        for t in [.0,.50,1.05,1.34]:ring((cx,cy,base+rise*math.sin(t)),radius*math.cos(t),.063,metal)
        # Partial curved roof sheets make the silhouette legible while exposing the frame.
        for sector in range(12):
            for band in range(5):
                if band<3 and (sector in [1,2,3,4,5] or rng.random()<.32):continue
                vs=[];fs=[];nu,nv=7,5
                for j in range(nv+1):
                    t=(band+(j/nv))*(math.pi/2)/5+.008
                    for i in range(nu+1):
                        a=(sector+i/nu)*math.tau/12
                        vs.append((cx+radius*math.cos(t)*math.cos(a),cy+radius*math.cos(t)*math.sin(a),base+rise*math.sin(t)))
                for j in range(nv):
                    for i in range(nu):
                        k=j*(nu+1)+i;fs.append((k,k+1,k+nu+2,k+nu+1));fs.append((k+nu+1,k+nu+2,k+1,k))
                mesh('Surviving roof sheet',vs,fs,metal,False)
    for structure in cfg.get('structures',[]):
        cx,cy=structure['center'];base=structure['base_z'];radius=structure['radius'];h=structure['height'];kind=structure['kind']
        cylinder((cx,cy,base*.5),radius+.35,base,mat,96)
        for zz,extra,thick in [(base+.14,.40,.25),(base+.49,.31,.18),(base+h*.55,.34,.20)]:
            for i in range(48):
                a=i*math.tau/48
                if kind=='rotunda' and .45<a<2.69:continue
                wedge(cx,cy,zz,radius-.28,radius+extra,a+.002,a+math.tau/48-.003,thick,mat)
        if kind=='rotunda':
            # Rear drum, front portal and side panels form one building envelope.
            wall(cx,cy,base,radius,h,math.radians(145),math.radians(395),windows=[math.radians(210),math.radians(300)])
            front=cy+radius*.78;opening=3.5
            arch((cx,front,base),opening,1.12,h-.25,mat)
            portal_spandrel(cx,front,base,opening,1.10,h-.25,h)
            for sign in [-1,1]:
                for row in range(round(h/.37)):
                    hh=h/round(h/.37)
                    for col in range(3):
                        x=cx+sign*(1.90+col*.67);block((x,front,base+hh*(row+.5)),(.66,1.10,hh-.014),mat,bevel=.022)
                for zz,ss,dd in [(base+.18,.95,.36),(base+h*.5,.66,h-.6),(base+h-.08,.98,.26)]:
                    block((cx+sign*1.88,front+.62,zz),(ss,.40,dd),mat,bevel=.026)
            block((cx,front,base+h-.08),(opening+.35,1.24,.34),mat,bevel=.028)
            block((cx,front+.04,base+h+.22),(opening+3.6,1.34,.20),mat,bevel=.025)
            for a in [math.radians(k) for k in [150,205,260,315,25]]:
                x=cx+math.cos(a)*(radius+.22);y=cy+math.sin(a)*(radius+.22)
                for zz,ww,dd in [(base+.28,1.02,.56),(base+h*.5,.63,h-.60),(base+h-.12,.94,.32)]:
                    block((x,y,zz),(.60,ww,dd),mat,a,.03)
            cornice(cx,cy,base+h,radius)
            dome(cx,cy,base+h+.50,radius+.06,structure.get('dome_rise',3.5))
        elif kind=='tower':
            wall(cx,cy,base,radius,h,0,math.tau,windows=[math.pi/2],broken=structure.get('broken',False))
            cornice(cx,cy,base+h,radius,structure.get('broken',False))
            arch((cx,cy+radius+.19,base+.88),1.42,.35,2.48,mat,thickness=.22)
            block((cx,cy+radius+.20,base+.91),(1.61,.57,.22),mat,bevel=.025)
            for a in [math.pi*.21,math.pi*.81,math.pi*1.22,math.pi*1.72]:
                x=cx+math.cos(a)*(radius+.18);y=cy+math.sin(a)*(radius+.18)
                block((x,y,base+h*.45),(.44,.52,h*.90),mat,a,.028)
                block((x,y,base+.18),(.72,.76,.36),mat,a,.025)
            if structure.get('instrument',True):
                z=base+h+1.20;r=radius*.58
                cylinder((cx,cy,base+h+.57),r*.55,.34,mat)
                for rot in [(0,0,0),(math.pi/2,0,0),(1.15,.70,.2)]:ring((cx,cy,z),r,.045,metal,rot)
        # Planting grows out of ledges and lower joints, sharing the scanned library.
        plant=cfg.get('scatter',{}).get('plant_asset')
        if plant:
            for i in range(100):
                a=rng.uniform(0,math.tau);r=radius+rng.uniform(.1,.65);z=base+rng.choice([.02,.04,.1,h*.55+.12,h+.17]);s=rng.uniform(.28,.75)
                api['instance'](plant,(cx+math.cos(a)*r,cy+math.sin(a)*r,z),(s,s,s*.62),a,i,False)
            # Dense hanging vegetation follows two sheltered wall joints.
            for a in [math.radians(54),math.radians(129)]:
                for i in range(36):
                    aa=a+rng.uniform(-.17,.17);z=base+h*(.38+i/58);s=rng.uniform(.19,.41)
                    ob=api['instance'](plant,(cx+math.cos(aa)*(radius+.34),cy+math.sin(aa)*(radius+.34),z),(s,s,s*.80),aa,i,False)
                    ob.rotation_euler.x=.75
    # Straight connecting galleries are data-defined endpoints, not independent props.
    for gallery in cfg.get('galleries',[]):
        ax,ay=gallery['start'];bx,by=gallery['end'];base=gallery['base_z'];h=gallery['height'];length=math.hypot(bx-ax,by-ay);yaw=math.atan2(by-ay,bx-ax)
        cx,cy=(ax+bx)/2,(ay+by)/2;width=min(2.5,length*.68)
        block((cx,cy,base*.5),(length+.30,1.60,base),mat,yaw,.022)
        arch((cx,cy,base),width,.83,h-.10,mat,yaw)
        portal_spandrel(cx,cy,base,width,.81,h-.10,h,yaw)
        tangent=Vector((math.cos(yaw),math.sin(yaw),0))
        for sign in [-1,1]:
            rem=(length-width)*.5
            for row in range(max(1,round(h/.36))):
                hh=h/max(1,round(h/.36));p=Vector((cx,cy,base+hh*(row+.5)))+tangent*(sign*(width*.5+rem*.5))
                block(p,(rem,.85,hh-.013),mat,yaw,.025)
        block((cx,cy,base+h+.04),(length,.99,.28),mat,yaw,.022)
        for i in range(4):
            if rng.random()<.6:
                p=Vector((cx,cy,base+h+.33))+tangent*rng.uniform(-length*.4,length*.4);block(p,(.58,.85,.30),mat,yaw,.02)
