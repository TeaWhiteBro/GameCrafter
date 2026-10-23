"""Whole-component bounded transforms; crossing components are never cut."""
import math
import numpy as np
from collections import defaultdict,deque
from mathutils import Vector

def move_islands(ob,repair,delta):
    me=ob.data;coords=np.empty((len(me.vertices),3),np.float32);me.vertices.foreach_get('co',coords.ravel())
    matrix=np.array(ob.matrix_world,dtype=float);world=coords@matrix[:3,:3].T+matrix[:3,3]
    x,y,_=repair['center_m'];radius=repair['radius_m']*100;low,high=repair['z_range_m']
    if repair.get('box_half_extent_m'):
        dx=world[:,0]/100-x;dy=-world[:,1]/100-y;angle=math.radians(repair.get('yaw_deg',0));ca,sa=math.cos(angle),math.sin(angle)
        hx,hy=repair['box_half_extent_m'];selected=(abs(dx*ca+dy*sa)<hx)&(abs(-dx*sa+dy*ca)<hy)
    else:selected=(world[:,0]-x*100)**2+(world[:,1]+y*100)**2<radius**2
    selected&=(world[:,2]>low*100)&(world[:,2]<high*100)
    if not selected.any():return 0
    edges=np.empty((len(me.edges),2),np.int32);me.edges.foreach_get('vertices',edges.ravel())
    edges=edges[selected[edges[:,0]]|selected[edges[:,1]]]
    adjacent=defaultdict(list);frontier=[]
    for a,b in edges:
        if selected[a] and selected[b]:adjacent[int(a)].append(int(b));adjacent[int(b)].append(int(a))
        elif selected[a]:frontier.append(int(a))
        else:frontier.append(int(b))
    discarded=set(frontier);queue=deque(frontier)
    while queue:
        for index in adjacent[queue.popleft()]:
            if index not in discarded:discarded.add(index);queue.append(index)
    if discarded:selected[list(discarded)]=False
    count=int(selected.sum())
    if count:
        local=ob.matrix_world.inverted().to_3x3()@Vector((delta[0]*100,-delta[1]*100,delta[2]*100))
        coords[selected]+=np.array(local);me.vertices.foreach_set('co',coords.ravel());me.update()
    return count
