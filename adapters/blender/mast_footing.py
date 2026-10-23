"""Ground-seated masonry socket with four real diagonal structural braces."""
import math
import numpy as np

FACES = [(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]

def build(item, height, emit, proxy=False):
    x,y = item['center']; z=item['base_z'];r=item['radius'];h=item['height']
    stone=item['material'];metal=item['metal_material']
    n=8; angles=[math.tau*i/n for i in range(n)]
    bottom=min(height(x+r*math.cos(a),y+r*math.sin(a)) for a in angles)-.18
    # The closed octagonal socket extends below all measured ground contacts.
    levels=[(bottom,r),(z+.22,r),(z+.57,r*.72)]
    vs=[(x+rr*math.cos(a),y+rr*math.sin(a),zz) for zz,rr in levels for a in angles]
    fs=[tuple(range(n-1,-1,-1)),tuple(range(2*n,3*n))]
    fs += [(j*n+i,j*n+(i+1)%n,(j+1)*n+(i+1)%n,(j+1)*n+i) for j in range(2) for i in range(n)]
    emit('Embedded mast masonry socket',vs,fs,stone,.012,False)
    for a in [math.pi/4+i*math.pi/2 for i in range(4)]:
        start=np.array([x+r*.88*math.cos(a),y+r*.88*math.sin(a),z+.20])
        end=np.array([x+.13*math.cos(a),y+.13*math.sin(a),z+h])
        axis=end-start;side=np.cross(axis,[0,0,1]);side/=np.linalg.norm(side)
        other=np.cross(axis,side);other/=np.linalg.norm(other)
        vs=[p+side*s+other*t for p in [start,end] for s,t in [(-.065,-.065),(.065,-.065),(.065,.065),(-.065,.065)]]
        emit('Mast diagonal anchor brace',vs,FACES,metal,.006,False)
