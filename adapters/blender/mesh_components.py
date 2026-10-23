"""Saved-mesh connected islands, optionally joining scan attribute seams."""
import numpy as np

def components(ob,seams=False):
 me=ob.data;coords=np.empty((len(me.vertices),3),np.float32);me.vertices.foreach_get('co',coords.ravel())
 matrix=np.asarray(ob.matrix_world);world=coords@matrix[:3,:3].T+matrix[:3,3]
 parent=list(range(len(coords)))
 def find(v):
  while parent[v]!=v:parent[v]=parent[parent[v]];v=parent[v]
  return v
 if seams:
  _,first,inverse=np.unique(np.round(world,2),axis=0,return_index=True,return_inverse=True)
  for i,j in enumerate(first[inverse]):parent[i]=int(j)
 edges=np.empty((len(me.edges),2),np.int32);me.edges.foreach_get('vertices',edges.ravel())
 for a,b in edges:
  a=find(int(a));b=find(int(b))
  if a!=b:parent[b]=a
 roots=np.array([find(i) for i in range(len(coords))]);order=np.argsort(roots);cuts=np.r_[0,1+np.flatnonzero(np.diff(roots[order])),len(order)]
 groups={int(roots[order[a]]):order[a:b] for a,b in zip(cuts[:-1],cuts[1:])}
 return coords,world,groups
