"""Diagnostic for ambiguous raised paving edges; not a substitute for route QA.

Job: report, out, paving_material. Use a material group containing paving only.
Checks every up-facing polygon centre against saved terrain, then checks actual
underside support of each component with an edge higher than 8 cm. A raised top
surface is not by itself evidence that the whole stone is floating.
"""
import bpy,json,sys,math,hashlib
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree
import numpy as np
job=json.loads(Path(sys.argv[sys.argv.index('--')+1]).read_text())
report=json.loads(Path(job['report']).read_text());bpy.ops.wm.open_mainfile(filepath=report['blend'])
terrain=bpy.data.objects['Environment_0'];verts=[terrain.matrix_world@v.co for v in terrain.data.vertices]
bvh=BVHTree.FromPolygons(verts,[list(p.vertices) for p in terrain.data.polygons])
material=job['paving_material']
matches=[i for i,e in enumerate(report['environment']) if e['material']==material]
if len(matches)!=1:raise ValueError('Select one unambiguous paving-only material group')
index=matches[0]
ob=bpy.data.objects['Environment_'+str(index)];mesh=ob.data
samples=[];high_faces=[]
for p in mesh.polygons:
 if p.normal.z<.3:continue
 q=ob.matrix_world@p.center
 hit,normal,face,distance=bvh.ray_cast(Vector((q.x,q.y,50000)),Vector((0,0,-1)))
 if hit:
  gap=float(q.z-hit.z)/100;samples.append((gap,float(q.x)/100,-float(q.y)/100))
  if gap>.08:high_faces.append(p.index)
values=np.array([x[0] for x in samples])
result={'samples':len(samples),'p50_m':float(np.percentile(values,50)),'p95_m':float(np.percentile(values,95)),
 'p99_m':float(np.percentile(values,99)),'max_m':float(values.max()),'fraction_above_8cm':float(np.mean(values>.08)),
 'largest_gaps':sorted(samples,reverse=True)[:40],'method':'Up-facing route-stone polygon centres against the saved detailed terrain BVH, independent of analytic height function.'}
parent=list(range(len(mesh.vertices)))
def find(v):
 while parent[v]!=v:parent[v]=parent[parent[v]];v=parent[v]
 return v
for e in mesh.edges:
 a,b=map(find,e.vertices)
 if a!=b:parent[b]=a
roots={find(mesh.polygons[i].vertices[0]) for i in high_faces};bottom={r:set() for r in roots}
for p in mesh.polygons:
 r=find(p.vertices[0])
 if r in bottom and p.normal.z<-.3:bottom[r].update(p.vertices)
support=[]
for root,ids in bottom.items():
 gaps=[]
 for i in ids:
  q=ob.matrix_world@mesh.vertices[i].co;hit=bvh.ray_cast(Vector((q.x,q.y,50000)),Vector((0,0,-1)))[0]
  if hit:gaps.append((q.z-hit.z)/100)
 support.append({'component':root,'bottom_samples':len(gaps),'minimum_bottom_gap_m':min(gaps),
  'buried_bottom_fraction':sum(g<=0 for g in gaps)/len(gaps),'whole_piece_detached':min(gaps)>.002})
result['high_edge_piece_support']=support
result['support_scope']='Connected pieces with an up-facing polygon centre more than 8 cm above terrain; top height alone is diagnostic, not a floating-stone verdict.'
result['paving_material']=material
result['source_report_sha256']=hashlib.sha256(Path(job['report']).read_bytes()).hexdigest()
result['source_blend_sha256']=hashlib.sha256(Path(report['blend']).read_bytes()).hexdigest()
Path(job['out']).write_text(json.dumps(result,indent=2));print('PAVER_AUDIT',json.dumps(result),flush=True)
