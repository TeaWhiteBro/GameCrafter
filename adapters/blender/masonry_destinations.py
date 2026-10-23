"""Traversable masonry galleries and attached defensive masses.

All placement and materials are supplied by the scene contract. Detailed and
structural geometry share portals, floor elevations and supporting volumes.
"""
import math


KINDS = {'masonry_gallery', 'masonry_tower'}


def validate(item):
    w, length = item['size']
    h = item.get('height', 5.2)
    if not 3 <= w <= 18 or not 3 <= length <= 30 or not 3 <= h <= 15:
        raise ValueError('Masonry destination exceeds its dimensional envelope')
    if item['kind'] == 'masonry_gallery':
        if item.get('roof_profile','flat') not in ['flat','barrel']:raise ValueError('Unknown gallery roof profile')
        if item.get('portal_profile','round') not in ['round','lintel']:raise ValueError('Unknown gallery portal profile')
        bays = item.get('bays', 4)
        if type(bays) is not int or not 1 <= bays <= 10 or not 2 <= length / bays <= 5:
            raise ValueError('Gallery bays must span 2-5 metres')
        if h - length / bays / 2 < 2.5:
            raise ValueError('Gallery requires 2.5m clear spring height')


def build(item, api, proxy, box, wall, arch, emit=None):
    validate(item)
    x, y = item['center']; w, length = item['size']
    z = item.get('base_z', .135); h = item.get('height', 5.2)
    angle = math.radians(item.get('yaw_deg', 0)); co, si = math.cos(angle), math.sin(angle)
    stone = item['material']; fill = item.get('wall_material', stone)
    roof = item.get('roof_material', stone); floor = item.get('floor_material', stone)
    def p(a, b, c):
        return (x + a*co-b*si, y+a*si+b*co, z+c)
    low = min(api['height'](*p(a,b,0)[:2]) for a in [-w/2,w/2] for b in [-length/2,length/2])-.18
    box('Masonry grounded foundation', (x,y,(low+z)/2), (w+.22,length+.22,max(.1,z-low)),stone,angle,smooth=False)
    if item['kind'] == 'masonry_gallery':
        # A flush floor has a complete rectangular edge, never a worn-box wedge.
        nx=1 if proxy else math.ceil(w/.9); ny=1 if proxy else math.ceil(length/1.2)
        for i in range(nx):
            for j in range(ny):
                box('Gallery fitted floor',p(-w/2+(i+.5)*w/nx,-length/2+(j+.5)*length/ny,.015),
                    (w/nx-(0 if proxy else .009),length/ny-(0 if proxy else .009),.06),floor,angle,smooth=False)
        bays=item.get('bays',4); bay=length/bays
        for side in [-1,1]:
            for j in range(bays):
                yy=-length/2+(j+.5)*bay
                if item.get('portal_profile','round')=='lintel':
                    box('Gallery stone lintel',p(side*w/2,yy,h-.72),(.76,bay+.12,.56),stone,angle,smooth=False)
                    box('Gallery stepped lintel crown',p(side*w/2,yy,h-.39),(.91,bay+.2,.14),roof,angle,smooth=False)
                else:
                    arch('Gallery lateral arch',p(side*w/2,yy,0),bay+.06,.65,h-.45,stone,angle+math.pi/2,.4)
            for j in range(bays+1):
                yy=-length/2+j*bay
                box('Gallery pier',p(side*w/2,yy,(h-.45)/2),(.72,.64,h-.45),stone,angle)
                box('Gallery pier foot',p(side*w/2,yy,.14),(.92,.86,.28),stone,angle)
                box('Gallery pier capital',p(side*w/2,yy,h-.65),(.92,.86,.25),stone,angle)
            box('Gallery continuous cornice',p(side*w/2,0,h-.23),(1.04,length+.5,.32),stone,angle)
        if item.get('roof_profile')=='barrel':
            if emit is None:raise ValueError('Barrel vault needs a mesh emitter')
            n=12 if proxy else 48;verts=[];radius=(w+.7)*.5;rise=item.get('roof_rise',2.1)
            for zz in [0,.25]:
                for yy in [-length*.5-.3,length*.5+.3]:
                    for i in range(n+1):
                        a=math.pi*i/n;verts.append(p(radius*math.cos(a),yy,h+.02+rise*math.sin(a)+zz))
            count=n+1;faces=[]
            for side in [0,1]:
                k=side*2*count
                faces += [(k+i,k+i+1,k+count+i+1,k+count+i) for i in range(n)]
            for edge in [0,count]:faces += [(edge+i,edge+i+1,2*count+edge+i+1,2*count+edge+i) for i in range(n)]
            for i in [0,n]:faces.append((i,count+i,3*count+i,2*count+i))
            emit('Continuous masonry barrel vault',verts,faces,roof,0,smooth=True)
        else:box('Gallery supported roof',p(0,0,h+.05),(w+.7,length+.6,.42),roof,angle,smooth=False)
        for side in [-1,1]:
            box('Gallery roof parapet',p(side*(w/2+.15),0,h+.45),(.3,length+.6,.50),fill,angle)
        if not proxy:
            for yy in [-length/2+.5,0,length/2-.5]:
                box('Gallery ceiling tie',p(0,yy,h-.31),(w,.22,.20),item.get('timber_material',stone),angle)
    else:
        box('Tower earthen mass',p(0,0,h/2),(w,length,h),fill,angle)
        for xx in [-w/2,w/2]:
            for yy in [-length/2,length/2]:
                if proxy:
                    box('Tower corner pier',p(xx,yy,h/2),(.55,.55,h),stone,angle)
                else:
                    rows=math.ceil(h/.45)
                    for row in range(rows):
                        box('Tower corner quoin',p(xx,yy,(row+.5)*h/rows),(.60,.60,h/rows-.01),stone,angle)
        for hh,over,thick in [(.3,.25,.24),(h-.25,.14,.25),(h+.05,.42,.25)]:
            box('Tower masonry stringcourse',p(0,0,hh),(w+over,length+over,thick),stone,angle)
        box('Tower roof terrace',p(0,0,h+.20),(w+.1,length+.1,.16),roof,angle)
        for side in [-1,1]:
            box('Tower parapet',p(side*w/2,0,h+.6),(.4,length,.8),fill,angle)
            box('Tower parapet',p(0,side*length/2,h+.6),(w,.4,.8),fill,angle)
            for i in range(max(3,round(w/1.4))):
                xx=-w/2+(i+.5)*w/max(3,round(w/1.4))
                box('Tower merlon',p(xx,side*length/2,h+1.12),(.60,.50,.52),stone,angle)
            for i in range(max(3,round(length/1.4))):
                yy=-length/2+(i+.5)*length/max(3,round(length/1.4))
                box('Tower merlon',p(side*w/2,yy,h+1.12),(.50,.60,.52),stone,angle)
        if not proxy:
            # Surface recesses are ornamental; the exterior tower remains solid.
            dark=item.get('recess_material',stone)
            for side in [-1,1]:
                for xx in [-w*.25,w*.25]:
                    box('Tower shaded window',p(xx,side*(length/2+.013),h*.60),(.46,.035,1.10),dark,angle,smooth=False)
                    box('Tower window sill',p(xx,side*(length/2+.10),h*.60-.59),(.72,.26,.14),stone,angle)
                for yy in [-length*.25,length*.25]:
                    box('Tower shaded side window',p(side*(w/2+.013),yy,h*.60),(.035,.46,1.10),dark,angle,smooth=False)
