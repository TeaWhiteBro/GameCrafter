"""Geometry hygiene and deformation evidence. Dimensions are in metres until export."""
import bpy, bmesh, math
import numpy as np
from mathutils import Matrix, Quaternion, Vector

def cleanup(meshes, height):
    result={'welded_vertices':0,'degenerate_edges_removed':0,'loose_vertices_removed':0,'dust_vertices_removed':0}
    for mesh in meshes:
        bm=bmesh.new();bm.from_mesh(mesh.data)
        before=len(bm.verts)
        # Weld coincident geometry while retaining per-loop UV seams. Do not voxel
        # remesh textured armor or weld across an anatomical gap.
        bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=height*.000015)
        result['welded_vertices']+=before-len(bm.verts)
        before=len(bm.edges)
        bmesh.ops.dissolve_degenerate(bm,edges=list(bm.edges),dist=height*.000002)
        result['degenerate_edges_removed']+=before-len(bm.edges)
        loose=[v for v in bm.verts if not v.link_faces]
        result['loose_vertices_removed']+=len(loose)
        if loose:bmesh.ops.delete(bm,geom=loose,context='VERTS')
        # Only sub-millimetre isolated flecks are discarded; rivets and armor plates stay.
        remaining=set(bm.verts);dust=[];components=[]
        while remaining:
            first=remaining.pop();island=[first];stack=[first]
            while stack:
                v=stack.pop()
                for e in v.link_edges:
                    q=e.other_vert(v)
                    if q in remaining:remaining.remove(q);stack.append(q);island.append(q)
            if len(island)<24:
                p=np.array([v.co for v in island])
                if np.linalg.norm(p.max(0)-p.min(0))<height*.0012:dust.extend(island)
            components.append(len(island))
        result['dust_vertices_removed']+=len(dust)
        if dust:bmesh.ops.delete(bm,geom=dust,context='VERTS')
        bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(mesh.data);bm.free();mesh.data.update()
        result.setdefault('connected_components',[]).append({'mesh':mesh.name,'count':len(components),'largest_vertices':sorted(components,reverse=True)[:12]})
    return result

def assign_skin(meshes,rig,height,config=None):
    config=config or {}
    if config.get('method')=='bone_heat':
        from heat_skin import assign
        return assign(meshes,rig,height,config)
    if config.get('method') not in [None,'anatomical_chains']:raise RuntimeError('Unknown skinning method')
    bones=[b for b in rig.data.bones if b.use_deform]
    starts=np.array([b.head_local for b in bones]);ends=np.array([b.tail_local for b in bones]);seg=ends-starts;norm=(seg*seg).sum(1)
    names=[b.name for b in bones];categories=[]
    for b in bones:
        if any(x in b.name for x in ['Upperarm','Forearm','Hand']):categories.append(b.name[:2]+'arm')
        elif any(x in b.name for x in ['Thigh','Calf','Foot']):categories.append(b.name[:2]+'leg')
        else:categories.append('core')
    ids={cat:np.array([i for i,c in enumerate(categories) if c==cat]) for cat in set(categories)}
    hip=rig.data.bones['Hip'].head_local.z
    shoulder=rig.data.bones['L_Upperarm'].head_local.x
    elbow=rig.data.bones['L_Forearm'].head_local
    wrist=rig.data.bones['L_Hand'].head_local
    rigid_count=0
    for mesh in meshes:
        mesh.vertex_groups.clear();groups=[mesh.vertex_groups.new(name=b.name) for b in bones]
        pts=np.array([v.co for v in mesh.data.vertices]);p=pts[:,None,:]-starts[None,:,:]
        t=np.clip((p*seg).sum(2)/np.maximum(norm,1e-10),0,1);dist=((p-t[:,:,None]*seg)**2).sum(2)
        # Allocate each vertex to an anatomical chain before solving its adjacent
        # influences. Euclidean proximity alone can attach a hand to a thigh.
        arms=np.abs(pts[:,0])>np.interp(pts[:,2],[0,wrist.z,elbow.z,height*.75,height],
            [abs(wrist.x)*.73,abs(wrist.x)*.73,abs(elbow.x)*.72,shoulder*config.get('shoulder_boundary',.76),shoulder*.98])
        arms &= (pts[:,2]>wrist.z-height*.13)&(pts[:,2]<height*.86)
        cat=np.full(len(pts),'core',dtype='<U8')
        cat[(pts[:,2]<hip-height*.045)&(pts[:,0]>=0)]='L_leg'
        cat[(pts[:,2]<hip-height*.045)&(pts[:,0]<0)]='R_leg'
        cat[arms&(pts[:,0]>=0)]='L_arm';cat[arms&(pts[:,0]<0)]='R_arm'
        # Optional measured anatomical volumes protect wide torsos and appendages
        # that a default lateral silhouette heuristic cannot separate reliably.
        region_masks=[]
        for region in config.get('anatomical_regions',[]):
            pnorm=pts/height
            if region.get('shape')=='ellipsoid':
                center=np.asarray(region['center']);radii=np.asarray(region['radii'])
                if center.shape!=(3,) or radii.shape!=(3,) or np.any(radii<=0):raise RuntimeError('Invalid anatomical ellipsoid')
                mask=(((pnorm-center)/radii)**2).sum(1)<=1
            elif region.get('shape')=='box':
                low=np.asarray(region['min']);high=np.asarray(region['max'])
                if low.shape!=(3,) or high.shape!=(3,) or np.any(high<=low):raise RuntimeError('Invalid anatomical box')
                mask=np.all((pnorm>=low)&(pnorm<=high),axis=1)
            else:raise RuntimeError('Unknown anatomical region shape')
            if 'chain' in region:
                if region['chain'] not in ids:raise RuntimeError('Unknown anatomical chain')
                cat[mask]=region['chain']
            if 'bone' in region:
                if region['bone'] not in names:raise RuntimeError('Unknown anatomical bone')
                region_masks.append((mask,names.index(region['bone'])))
        for c,indices in ids.items():
            rows=cat!=c
            for i in indices:dist[rows,i]+=height*height*20
        # Small disconnected details inherit one rigid bone; never let rivets melt.
        parent=np.arange(len(pts))
        def root(i):
            while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
            return i
        for e in mesh.data.edges:
            a,b=e.vertices;parent[root(a)]=root(b)
        roots=np.array([root(i) for i in range(len(pts))]);labels,counts=np.unique(roots,return_counts=True)
        rigid={};weights=np.zeros((len(pts),len(bones)),dtype=np.float64);locked=np.zeros(len(pts),dtype=bool)
        for key,count in zip(labels,counts):
            ix=np.where(roots==key)[0];size=np.linalg.norm(np.ptp(pts[ix],axis=0))
            if size<height*.105:
                choice=int(np.argmin(dist[ix].mean(0)));rigid_count+=1
                weights[ix,choice]=1.;locked[ix]=True;rigid[int(key)]=True
        for i in range(len(pts)):
            if int(roots[i]) in rigid:continue
            nearest=np.argsort(dist[i])[:2];d=dist[i,nearest]
            w=np.exp(-(d-d[0])/(height*.027)**2);w/=w.sum()
            weights[i,nearest]=w
        for region in config.get('rigid_regions',[]):
            if region['bone'] not in names:raise RuntimeError('Unknown rigid region bone')
            weight=np.clip((pts[:,2]/height-region['z_min'])/region.get('feather',.025),0,1)
            weight[cat!=region.get('chain','core')]=0
            target=np.zeros_like(weights);target[:,names.index(region['bone'])]=1
            weights=weights*(1-weight[:,None])+target*weight[:,None]
            locked[weight>.999]=True
        for mask,index in region_masks:
            weights[mask]=0;weights[mask,index]=1;locked[mask]=True
        # Smooth across actual surface edges, not through empty space. In particular,
        # soften the shoulder/groin boundary without letting a nearby hand borrow leg weights.
        edges=np.array([e.vertices[:] for e in mesh.data.edges]);degree=np.bincount(edges.ravel(),minlength=len(pts));degree=np.maximum(degree,1)
        for step in range(12):
            neighbors=np.zeros_like(weights)
            np.add.at(neighbors,edges[:,0],weights[edges[:,1]]);np.add.at(neighbors,edges[:,1],weights[edges[:,0]])
            updated=weights*.35+neighbors/degree[:,None]*.65;updated[locked]=weights[locked];weights=updated
        for i,row in enumerate(weights):
            inds=np.argsort(row)[-4:];ws=row[inds];ws/=max(ws.sum(),1e-12)
            for index,w in zip(inds,ws):
                if w>1e-5:groups[int(index)].add([i],float(w),'REPLACE')
        mod=mesh.modifiers.new('AnatomicalSkin','ARMATURE');mod.object=rig;mod.use_deform_preserve_volume=True
    return {'rigid_detail_islands':rigid_count,'method':'anatomical_chains_with_topology_smoothing','topology_smoothing_iterations':12}

def existing_stress_map(rig, semantic_map):
    """Resolve bend joints through the actual chains, never assume source bone names."""
    mapping={'Waist':semantic_map['spine_start'],'Spine02':semantic_map['spine_end']}
    for side,prefix in [('left','L_'),('right','R_')]:
        for canonical,semantic in [('Upperarm','upperarm'),('Thigh','thigh')]:
            mapping[prefix+canonical]=semantic_map[side+'_'+semantic]
        for canonical,start,end in [('Forearm','upperarm','hand'),('Calf','thigh','foot')]:
            first=rig.data.bones[semantic_map[side+'_'+start]]
            current=rig.data.bones[semantic_map[side+'_'+end]].parent;chain=[]
            while current and current!=first:
                chain.append(current);current=current.parent
            if current!=first or not chain:raise RuntimeError('Cannot resolve a bend joint for '+side+'_'+canonical+'; provide a compatible rig')
            candidates=[b for b in chain if 'twist' not in b.name.lower() and b.length>height_epsilon(rig)]
            if not candidates:raise RuntimeError('No nonzero bend bone for '+side+'_'+canonical)
            mapping[prefix+canonical]=max(candidates,key=lambda b:b.length).name
    return mapping

def height_epsilon(rig):
    return max((b.length for b in rig.data.bones),default=1)*.001

def stress_test(meshes,rig,height,out,render=False,semantic_map=None):
    poses={
      'rest':{},
      'reach':{'L_Upperarm':(0,0,-65),'R_Upperarm':(0,0,65),'L_Forearm':(100,0,0),'R_Forearm':(80,0,0)},
      'stride':{'L_Thigh':(-45,0,0),'R_Thigh':(32,0,0),'L_Calf':(68,0,0),'L_Upperarm':(20,0,-15),'R_Upperarm':(-32,0,12)},
      'crouch':{'L_Thigh':(-48,0,-10),'R_Thigh':(-48,0,10),'L_Calf':(88,0,0),'R_Calf':(88,0,0),'Waist':(12,0,0)},
      'strike':{'Spine02':(0,30,0),'R_Upperarm':(-65,0,50),'R_Forearm':(80,0,0),'L_Upperarm':(-30,0,-25)},
    }
    mapped=existing_stress_map(rig,semantic_map) if semantic_map else None
    # Existing rigs can use arbitrary bone rolls. Apply anatomical component-space
    # rotations, converted into each bone's own rest basis, without re-skinning.
    if mapped:
        up=(rig.data.bones[semantic_map['head']].head_local-rig.data.bones[semantic_map['hips']].head_local).normalized()
        lateral=rig.data.bones[semantic_map['left_upperarm']].head_local-rig.data.bones[semantic_map['right_upperarm']].head_local
        lateral=(lateral-up*lateral.dot(up)).normalized();forward=up.cross(lateral).normalized()
        if lateral.length<.9 or up.length<.9:raise RuntimeError('Degenerate anatomical axes in existing skin')
        axes=(lateral,forward,up)
    previous_pose=rig.data.pose_position;rig.data.pose_position='POSE'
    for b in rig.pose.bones:b.matrix_basis=Matrix.Identity(4)
    bpy.context.view_layer.update()
    rest={};edges={};rest_points={};spike_edges={};spike_rest={}
    for mesh in meshes:
        p=np.array([v.co for v in mesh.data.vertices]);e=np.array([edge.vertices[:] for edge in mesh.data.edges]);length=np.linalg.norm(p[e[:,0]]-p[e[:,1]],axis=1)
        valid=length>height*.001
        rest[mesh.name]=length[valid];edges[mesh.name]=e[valid]
        spike_valid=length>height*.000002
        spike_edges[mesh.name]=e[spike_valid];spike_rest[mesh.name]=length[spike_valid]
        evaluated=mesh.evaluated_get(bpy.context.evaluated_depsgraph_get());me=evaluated.to_mesh()
        if len(me.vertices)!=len(p):raise RuntimeError('Topology-changing modifier must be resolved before deformation QA')
        rest_points[mesh.name]=np.array([v.co for v in me.vertices]);evaluated.to_mesh_clear()
    scene=bpy.context.scene;tests=[]
    if render:
        scene.render.engine='CYCLES';scene.cycles.samples=12;scene.render.resolution_x=560;scene.render.resolution_y=680;scene.render.resolution_percentage=100
        scene.world=bpy.data.worlds.new('DeformationReview');scene.world.color=(.16,.16,.16);scene.view_settings.view_transform='AgX'
        for name,pos,power in [('Key',(height*2,-height*2,height*2),600*height),('Fill',(-height*2,-height,height*1.3),330*height),('Rim',(height,height*2,height*2),650*height)]:
            d=bpy.data.lights.new(name,'AREA');d.energy=power;d.size=height*2;o=bpy.data.objects.new(name,d);bpy.context.collection.objects.link(o);o.location=pos;o.rotation_euler=(Vector((0,0,height*.5))-o.location).to_track_quat('-Z','Y').to_euler()
        cam=bpy.data.cameras.new('QA_Camera');camera=bpy.data.objects.new('QA_Camera',cam);bpy.context.collection.objects.link(camera);camera.location=(height*.8,-height*3,height*.9);camera.rotation_euler=(Vector((0,0,height*.5))-camera.location).to_track_quat('-Z','Y').to_euler();cam.type='ORTHO';cam.ortho_scale=height*1.5;scene.camera=camera
    for label,pose in poses.items():
        for b in rig.pose.bones:b.matrix_basis=Matrix.Identity(4)
        for name,angles in pose.items():
            actual=mapped[name] if mapped else name
            if actual not in rig.pose.bones:raise RuntimeError('Missing stress-test bone '+actual)
            bone=rig.pose.bones[actual]
            if mapped:
                delta=Quaternion()
                for axis,angle in zip(axes,angles):delta=Quaternion(axis,math.radians(angle))@delta
                basis=bone.bone.matrix_local.to_quaternion()
                bone.rotation_mode='QUATERNION';bone.rotation_quaternion=basis.inverted()@delta@basis
            else:
                bone.rotation_mode='XYZ';bone.rotation_euler=tuple(math.radians(x) for x in angles)
        bpy.context.view_layer.update();ratios=[];movement=0;spike_excess=0
        for mesh in meshes:
            evaluated=mesh.evaluated_get(bpy.context.evaluated_depsgraph_get());me=evaluated.to_mesh();p=np.array([v.co for v in me.vertices]);e=edges[mesh.name]
            ratios.extend((np.linalg.norm(p[e[:,0]]-p[e[:,1]],axis=1)/rest[mesh.name]).tolist());evaluated.to_mesh_clear()
            movement=max(movement,float(np.linalg.norm(p-rest_points[mesh.name],axis=1).max())/height)
            se=spike_edges[mesh.name];sl=spike_rest[mesh.name]
            stretched=np.linalg.norm(p[se[:,0]]-p[se[:,1]],axis=1)
            severe=stretched>sl*8
            if severe.any():spike_excess=max(spike_excess,float((stretched[severe]-sl[severe]).max())/height)
        ratios=np.array(ratios);bad=float(np.mean(ratios>4)) if len(ratios) else 1
        test={'pose':label,'edge_stretch_p99':float(np.percentile(ratios,99)) if len(ratios) else None,'edges_over_4x_fraction':bad,'sparse_spike_excess_fraction':spike_excess,'max_vertex_motion_fraction':movement,'passed':bad<.006 and spike_excess<.08 and (not mapped or label=='rest' or movement>.025)}
        if render:
            path=out/('pose_'+label+'.png');scene.render.filepath=str(path);bpy.ops.render.render(write_still=True);test['image']=str(path)
        tests.append(test)
    for b in rig.pose.bones:b.matrix_basis=Matrix.Identity(4)
    rig.data.pose_position=previous_pose
    bpy.context.view_layer.update()
    return {'passed':all(t['passed'] for t in tests),'pose_tests':tests,'limits':{'edges_over_4x_fraction':.006,'sparse_spike_excess_fraction':.08,'spike_minimum_ratio':8},'resolved_stress_bones':mapped,'scope':'edge stretching, sparse spikes and actual skin motion; silhouette and completeness also require visual review'}
