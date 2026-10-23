"""Audit connected rock undersides against the saved, triangulated terrain."""
import bpy, json, sys, hashlib
from pathlib import Path
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

job=json.loads(Path(sys.argv[sys.argv.index('--')+1]).read_text())
report=json.loads(Path(job['report']).read_text())
bpy.ops.wm.open_mainfile(filepath=report['blend'])
ground=bpy.data.objects['Environment_0']
tree=BVHTree.FromPolygons([ground.matrix_world@v.co for v in ground.data.vertices], [tuple(p.vertices) for p in ground.data.polygons])
rows=[]
for index,entry in enumerate(report['environment']):
    if entry.get('semantic_id')!=4 and index not in job.get('extra_environment_indices',[]):continue
    ob=bpy.data.objects['Environment_'+str(index)];me=ob.data
    vertices=np.empty((len(me.vertices),3),np.float32);me.vertices.foreach_get('co',vertices.ravel())
    matrix=np.asarray(ob.matrix_world);vertices=vertices@matrix[:3,:3].T+matrix[:3,3]
    parent=list(range(len(vertices)))
    def find(v):
        while parent[v]!=v:parent[v]=parent[parent[v]];v=parent[v]
        return v
    # Imported scan UV/normal seams can duplicate coincident vertices. Join
    # those positions for connectivity analysis without editing the scene.
    _,first,inverse=np.unique(np.round(vertices,2),axis=0,return_index=True,return_inverse=True)
    for i,representative in enumerate(first[inverse]):parent[i]=int(representative)
    edges=np.empty((len(me.edges),2),np.int32);me.edges.foreach_get('vertices',edges.ravel())
    for a,b in edges:
        a=find(int(a));b=find(int(b))
        if a!=b:parent[b]=a
    roots=np.array([find(i) for i in range(len(vertices))])
    order=np.argsort(roots);bounds=np.r_[0,1+np.flatnonzero(np.diff(roots[order])),len(order)]
    for start,end in zip(bounds[:-1],bounds[1:]):
        ids=order[start:end]
        if len(ids)<40:continue
        points=vertices[ids];low=points.min(0);high=points.max(0)
        underside=points[points[:,2]<=low[2]+(high[2]-low[2])*.18]
        underside=underside[np.linspace(0,len(underside)-1,min(128,len(underside)),dtype=int)]
        gaps=[]
        for q in underside:
            hit=tree.ray_cast(Vector((float(q[0]),float(q[1]),50000)),Vector((0,0,-1)))[0]
            if hit:gaps.append((float(q[2])-hit.z)/100)
        row={'environment':index,'component':int(roots[ids[0]]),'vertices':len(ids),
             'material':entry.get('material'),'semantic_id':entry.get('semantic_id'),
             'center_m':[((low[0]+high[0])/200),-((low[1]+high[1])/200),(low[2]+high[2])/200],
             'bounds_m':{'min':[low[0]/100,-high[1]/100,low[2]/100], 'max':[high[0]/100,-low[1]/100,high[2]/100]},
             'samples':len(gaps)}
        if gaps:row.update(min_bottom_gap_m=min(gaps),p20_bottom_gap_m=float(np.percentile(gaps,20)),
                           p80_bottom_gap_m=float(np.percentile(gaps,80)),max_bottom_gap_m=max(gaps),
                           buried_fraction=float(np.mean(np.asarray(gaps)<=.002)),whole_piece_detached=min(gaps)>.002)
        flank=points[points[:,2]<=low[2]+(high[2]-low[2])*.45]
        flank=flank[np.linspace(0,len(flank)-1,min(256,len(flank)),dtype=int)]
        flank_gaps=[]
        for q in flank:
            hit=tree.ray_cast(Vector((float(q[0]),float(q[1]),50000)),Vector((0,0,-1)))[0]
            if hit:flank_gaps.append((float(q[2])-hit.z)/100)
        if flank_gaps:row['lower_flank']={'height_fraction':.45,'samples':len(flank_gaps),
            'max_gap_m':max(flank_gaps),'p95_gap_m':float(np.percentile(flank_gaps,95)),
            'buried_fraction':float(np.mean(np.asarray(flank_gaps)<=.002))}
        rows.append(row)
    print('ROCK_GROUP_AUDITED',index,flush=True)
result={'source_report_sha256':hashlib.sha256(Path(job['report']).read_bytes()).hexdigest(),
        'source_blend_sha256':hashlib.sha256(Path(report['blend']).read_bytes()).hexdigest(),
        'method':'Saved rock geometry with coincident scan seams connected for analysis only. Tip support: lowest 18 percent, up to 128 samples. Lower flank: lowest 45 percent, up to 256 samples. Both measured against detailed terrain BVH; flank gaps and whole-piece detachment are distinct from current-view acceptance.',
        'components':rows}
Path(job['out']).write_text(json.dumps(result,indent=2,default=lambda value:value.item()),encoding='utf-8')
print('ROCK_AUDIT',len(rows),'components',sum(r.get('whole_piece_detached',False) for r in rows),'detached',flush=True)
