"""Conditional bamboo repair: measured source bases and attached fine-leaf sprays.

Only supports separated, approximately circular bare culms at the declared cut.
Preserves lower source geometry/UVs. It is not generic plant reconstruction.
"""
import bpy,bmesh,math,random
import numpy as np
from mathutils import Vector

def section(ob,z,tolerance):
    vertices=np.array([v.co[:] for v in ob.data.vertices]);edges=np.array([e.vertices[:] for e in ob.data.edges])
    a,b=vertices[edges[:,0]],vertices[edges[:,1]]
    mask=((a[:,2]<z)&(b[:,2]>z))|((b[:,2]<z)&(a[:,2]>z));a,b=a[mask],b[mask]
    points=a+(b-a)*((z-a[:,2])/(b[:,2]-a[:,2]))[:,None]
    remaining=set(range(len(points)));groups=[]
    while remaining:
        todo=[remaining.pop()];group=[]
        while todo:
            i=todo.pop();group.append(i)
            nearby={j for j in remaining if np.linalg.norm(points[j,:2]-points[i,:2])<tolerance}
            remaining-=nearby;todo.extend(nearby)
        p=points[group];extent=np.ptp(p[:,:2],axis=0)
        if len(p)<8 or min(extent)<.015 or max(extent)/min(extent)>1.7:raise ValueError('Ambiguous bare culm section; inspect source before refining')
        # Circle fit is independent of uneven edge sampling density.
        xy=p[:,:2];fit=np.linalg.lstsq(np.c_[2*xy,np.ones(len(xy))],(xy*xy).sum(1),rcond=None)[0]
        center=np.r_[fit[:2],z];r=float(np.sqrt(fit[2]+(fit[:2]**2).sum()))
        if np.abs(np.linalg.norm(xy-center[:2],axis=1)-r).max()>r*.3:raise ValueError('Culm section is not sufficiently round')
        groups.append((center,r))
    return sorted(groups,key=lambda g:tuple(g[0]))

def refine(ob,settings):
    rng=random.Random(settings.get('seed',73));cut=settings['cut_height_m'];height=settings['height_m']
    if not .3<cut<height*.35 or not 2<=settings['expected_culms']<=16:raise ValueError('Invalid culm refinement envelope')
    sections=section(ob,cut,settings.get('section_join_m',.045));lower=section(ob,cut-.2,settings.get('section_join_m',.045))
    if len(sections)!=settings['expected_culms'] or len(lower)!=len(sections):raise ValueError('Measured culm count disagrees with declared source')
    stems=[];used=set()
    for center,radius in sections:
        j=min((j for j in range(len(lower)) if j not in used),key=lambda j:np.linalg.norm(lower[j][0][:2]-center[:2]));used.add(j)
        tangent=(center-lower[j][0])/.2
        if np.linalg.norm(tangent[:2])>.3:raise ValueError('Bare culm tangent too steep or ambiguous')
        stems.append((Vector(center),radius,Vector(tangent)))
    source_faces=len(ob.data.polygons);bm=bmesh.new();bm.from_mesh(ob.data)
    bmesh.ops.bisect_plane(bm,geom=list(bm.verts)+list(bm.edges)+list(bm.faces),dist=1e-6,plane_co=(0,0,cut),plane_no=(0,0,1),clear_outer=True,clear_inner=False)
    loose=[v for v in bm.verts if not v.link_faces]
    if loose:bmesh.ops.delete(bm,geom=loose,context='VERTS')
    bm.to_mesh(ob.data);bm.free();ob.data.update();retained=len(ob.data.polygons)
    vertices=[];faces=[];indices=[];leaf_count=0;branch_count=0
    def add(vs,fs,mi):
        offset=len(vertices);vertices.extend(vs);faces.extend(tuple(offset+i for i in f) for f in fs);indices.extend([mi]*len(fs))
    def tube(points,radii,mi=0,sides=7):
        vs=[]
        for i,(p,r) in enumerate(zip(points,radii)):
            r=float(r)
            axis=(points[min(i+1,len(points)-1)]-points[max(i-1,0)]).normalized();u=axis.cross(Vector((0,1,0))).normalized();v=axis.cross(u)
            vs.extend(p+r*(u*math.cos(j*math.tau/sides)+v*math.sin(j*math.tau/sides)) for j in range(sides))
        fs=[(k*sides+j,k*sides+(j+1)%sides,(k+1)*sides+(j+1)%sides,(k+1)*sides+j) for k in range(len(points)-1) for j in range(sides)]
        fs += [tuple(range(sides-1,-1,-1)),tuple((len(points)-1)*sides+j for j in range(sides))];add(vs,fs,mi)
    def leaf(root,direction,length,width,mi):
        nonlocal leaf_count
        side=direction.cross(Vector((0,0,1))).normalized();normal=side.cross(direction).normalized()
        vs=[root]
        for t in [.25,.58,.82]:
            center=root+direction*(length*t)+Vector((0,0,-length*.40*t*t));half=width*.5*math.sin(t*math.pi)**.7
            vs.extend([center-side*half,center+normal*width*.09,center+side*half])
        vs.append(root+direction*length+Vector((0,0,-length*.4)))
        fs=[(0,1,2),(0,2,3)]
        for k in [1,4]:fs.extend([(k,k+3,k+4,k+1),(k+1,k+4,k+5,k+2)])
        fs += [(7,10,8),(8,10,9)];add(vs,fs,mi);leaf_count+=1
    heights=np.linspace(height*.80,height,len(stems));rng.shuffle(heights);audit=[]
    for index,(base,radius,tangent) in enumerate(stems):
        top=float(heights[index]);lean=Vector((base.x,base.y,0))
        if lean.length<.01:lean=Vector((1,0,0))
        lean.normalize();bend=rng.uniform(.2,.55)
        def center(z):
            z=float(z)
            t=(z-cut)/(top-cut);return base+tangent*(z-cut)+lean*bend*t*t
        def rad(z):return float(radius*max(.025,(top-z)/(top-cut))**.65)
        zs=np.linspace(cut-.035,top-.025,70);tube([center(z) for z in zs],[rad(z) for z in zs],index%2,12)
        for z in np.arange(cut+.27,top-.18,.38):
            tube([center(z-.011),center(z+.011)],[rad(z)*1.12]*2,2,12)
        for level,z in enumerate(np.linspace(max(cut+.65,top*.41),top-.27,9)):
            for sign in [-1,1]:
                angle=index*2.4+level*.91+(0 if sign>0 else math.pi)+rng.uniform(-.35,.35)
                direction=Vector((math.cos(angle),math.sin(angle),.2)).normalized();extent=rng.uniform(.5,1.12)*(1-.38*(z/top))
                start=center(z);end=start+direction*extent+Vector((0,0,.16));mid=start.lerp(end,.5)+Vector((0,0,.07))
                tube([start,mid,end],[rad(z)*.24,.008,.0025],0,6);branch_count+=1
                for node in range(2,8):
                    t=node/8;root=start.lerp(end,t)+Vector((0,0,math.sin(t*math.pi)*.07))
                    side=Vector((-direction.y,direction.x,0));sgn=1 if node%2 else -1
                    axis=(direction*.50+side*sgn*.75+Vector((0,0,rng.uniform(-.2,.2)))).normalized()
                    tip=root+axis*rng.uniform(.24,.40);tube([root,tip],[.0035,.0012],0,5)
                    for k in range(6):
                        q=(k+.45)/6;point=root.lerp(tip,q);alt=1 if k%2 else -1
                        ld=(axis*.50+side*alt*.60+Vector((0,0,rng.uniform(-.12,.25)))).normalized()
                        leaf(point,ld,rng.uniform(.22,.36),rng.uniform(.022,.039),3+rng.randrange(4))
        audit.append({'source_center_m':list(base),'radius_m':radius,'retained_height_m':cut,'tip_height_m':top,'overlap_m':.035})
    colors=[[.085,.19,.028],[.11,.235,.037],[.23,.31,.092],[.055,.18,.018],[.085,.25,.027],[.14,.30,.052],[.09,.215,.032]]
    me=bpy.data.meshes.new('Attached narrow leaf culms');me.from_pydata(vertices,[],faces);me.update()
    for i,color in enumerate(colors):
        mat=bpy.data.materials.new('Bamboo_culm' if i<3 else 'Bamboo_leaf');mat.use_nodes=True;mat.diffuse_color=(*color,1);mat['pipeline_collision']=False
        bs=mat.node_tree.nodes.get('Principled BSDF');bs.inputs['Base Color'].default_value=(*color,1);bs.inputs['Roughness'].default_value=.47 if i<3 else .64
        if i>=3:mat['pipeline_surface']='botanical'
        me.materials.append(mat)
    for p,mi in zip(me.polygons,indices):p.material_index=mi;p.use_smooth=True
    new=bpy.data.objects.new('Attached narrow leaf culms',me);bpy.context.collection.objects.link(new)
    bpy.ops.object.select_all(action='DESELECT');ob.select_set(True);new.select_set(True);bpy.context.view_layer.objects.active=ob;bpy.ops.object.join()
    triangles=sum(len(p.vertices)-2 for p in ob.data.polygons)
    if triangles>settings.get('triangle_budget',110000):raise ValueError('Culm refinement exceeds declared triangle budget')
    return {'method':'measured source bare sections + UV-preserved lower culms + attached tapered culms and alternate lanceolate sprays',
        'source_faces':source_faces,'retained_source_faces':retained,'culms':audit,'leaf_count':leaf_count,'branch_count':branch_count,'triangles':triangles,'particle_systems':0}
