"""Optional metric urban facade detail; no scene names or fixed placements.

Solid exterior buildings only. Ground routes must remain outside the footprint.
The structural companion retains the building, awning and major sign envelope;
typography, shutter ribs and small services are intentionally detailed-only.
"""
import math

def validate(item):
    for key in ['sign_text','secondary_text']:
        value=item.get(key,'')
        if not isinstance(value,str) or len(value)>28 or any(ord(c)<32 for c in value):
            raise ValueError(key+' must be a short printable label (28 characters maximum)')
    for key in ['lit_window_material','letter_material','accent_material']:
        if key in item and (not isinstance(item[key],str) or not item[key]):
            raise ValueError('Invalid urban '+key)
    for key in ['urban_detail','balconies']:
        if key in item and type(item[key]) is not bool:raise ValueError(key+' must be boolean')
    for key,lo,hi in [('bay_width',1.8,5),('floor_height',2.2,4.5)]:
        if key in item and (type(item[key]) not in (int,float) or not math.isfinite(item[key]) or not lo<=item[key]<=hi):
            raise ValueError('Invalid urban '+key)

def lettering(text,center,width,height,material,mesh):
    if not text:return
    import bpy
    curve=bpy.data.curves.new('Facade typography','FONT');curve.body=text
    curve.align_x='CENTER';curve.align_y='CENTER';curve.size=1;curve.extrude=.008;curve.resolution_u=4
    ob=bpy.data.objects.new('Typography construction',curve);bpy.context.collection.objects.link(ob)
    bpy.ops.object.select_all(action='DESELECT')
    bpy.context.view_layer.objects.active=ob;ob.select_set(True)
    bpy.ops.object.convert(target='MESH');ob=bpy.context.object
    xs=[v.co.x for v in ob.data.vertices];ys=[v.co.y for v in ob.data.vertices]
    if xs and ys:
        scale=min(width/max(.01,max(xs)-min(xs)),height/max(.01,max(ys)-min(ys)))
        mx=(max(xs)+min(xs))/2;my=(max(ys)+min(ys))/2
        # Scene XY is authored in UE's left-handed world basis. A reader facing
        # local +Y has screen-right -X there; Blender font coordinates are RH.
        # Give labels the explicit readable basis, independent of module yaw.
        vertices=[(center[0]-(v.co.x-mx)*scale,center[1]-v.co.z,center[2]+(v.co.y-my)*scale) for v in ob.data.vertices]
        mesh('dimensional signage '+text,vertices,[tuple(reversed(f.vertices)) for f in ob.data.polygons],material)
    bpy.data.objects.remove(ob,do_unlink=True)

def build(item,box,beam,cylinder,mesh,proxy):
    w,d=item['size'];base=item.get('base_z',.14);h=item.get('height',3.5)
    stone=item['material'];metal=item['timber_material'];wall=item.get('wall_material',stone)
    roof=item['roof_material'];glass=item.get('window_material',roof)
    lit=item.get('lit_window_material',glass);accent=item.get('accent_material',metal)
    sign=item.get('sign_material',metal);letters=item.get('letter_material',lit)
    front=-d/2
    box('urban building solid',(0,0,base+h/2),(w,d,h),wall,True)
    box('continuous footing',(0,0,base+.14),(w+.18,d+.15,.28),stone,True)
    ground_height=min(3.25,h*.65);bays=max(2,round(w/item.get('bay_width',3.1)));bw=w/bays
    # Deep layered shop bays, opaque glazing and physically attached roller doors.
    for bay in range(bays):
        x=(bay+.5)*bw-w/2;z=base+ground_height*.48
        box('shop bay casing',(x,front-.10,z),(bw-.20,.22,ground_height*.87),metal)
        box('shop inset',(x,front-.225,z),(bw-.38,.035,ground_height*.80),glass if bay%3!=1 else accent)
        if not proxy:
            for side in [-1,1]:box('shop jamb',(x+side*(bw/2-.15),front-.29,z),(.10,.24,ground_height*.90),stone)
            if bay%3==1:
                for j in range(16):box('roller shutter rib',(x,front-.26,base+.25+j*(ground_height-.45)/16),(bw-.40,.045,.028),metal)
            else:
                box('shop glazing mullion',(x,front-.28,z),(.055,.075,ground_height*.80),metal)
                box('door rail',(x,front-.29,base+.92),(bw-.40,.06,.035),metal)
    box('awning shell',(0,front-.68,base+ground_height),(w+.25,1.42,.17),roof)
    box('signboard back',(0,front-.83,base+ground_height+.45),(w*.92,.20,.72),metal)
    box('signboard face',(0,front-.945,base+ground_height+.45),(w*.89,.035,.60),sign)
    if not proxy:
        lettering(item.get('sign_text',''),(0,front-.978,base+ground_height+.45),w*.77,.43,letters,mesh)
        box('canopy practical',(0,front-.84,base+ground_height-.11),(w*.72,.16,.025),lit)
        for x in [-w*.37,w*.37]:beam('awning brace',(x,front-.04,base+ground_height-.8),(x,front-.97,base+ground_height-.1),.07,.07,metal)
    levels=max(0,int((h-ground_height-.8)/item.get('floor_height',2.75)));pitch=(h-ground_height-.8)/max(1,levels)
    for level in range(levels):
        z=base+ground_height+1.05+(level+.45)*pitch
        box('floor reveal',(0,front-.035,z-pitch*.44),(w,.09,.10),stone)
        for bay in range(bays):
            x=(bay+.5)*bw-w/2;ww=bw*.65;hh=min(1.9,pitch*.66)
            box('upper window surround',(x,front-.095,z),(ww+.18,.20,hh+.18),metal)
            selected=lit if (bay*7+level*3+int(w))%5 in [0,1] else glass
            box('upper window glazing',(x,front-.21,z),(ww,.025,hh),selected)
            if not proxy:
                box('upper window mullion',(x,front-.25,z),(.048,.065,hh),metal)
                box('weather sill',(x,front-.27,z-hh/2),(ww+.22,.36,.09),stone)
                if item.get('balconies') and level%2==0 and bay%2==0:
                    box('balcony tray',(x,front-.51,z-hh/2-.07),(ww+.36,1.02,.13),stone)
                    box('balcony top rail',(x,front-1,z-hh/2+.78),(ww+.35,.055,.055),metal)
                    for k in range(7):box('balcony rail',(x+(k/6-.5)*(ww+.3),front-1,z-hh/2+.4),(.035,.035,.78),metal)
    box('flat roof coping',(0,0,base+h),(w+.28,d+.28,.22),stone)
    # Roofline enclosure and serviced roof avoid a simple capped cube.
    for y in [-d/2,d/2]:box('roof parapet',(0,y,base+h+.34),(w,.19,.55),wall)
    for x in [-w/2,w/2]:box('roof side parapet',(x,0,base+h+.34),(.19,d,.55),wall)
    if not proxy:
        for side in [-1,1]:
            cylinder('rainwater downpipe',(side*(w/2-.10),front-.24,base+.12),.055,h-.1,metal)
            box('vertical pilaster',(side*(w/2-.055),front-.065,base+h/2),(.17,.15,h),stone)
        # Supported projecting blade sign. Its full envelope stays above walking height.
        if item.get('secondary_text'):
            x=w*.36;zz=base+min(h-.7,ground_height+3.4)
            box('blade sign cabinet',(x,front-.45,zz),(.85,.32,2.45),metal)
            box('blade sign inset',(x,front-.625,zz),(.71,.03,2.28),sign)
            text=item['secondary_text']
            for i,char in enumerate(text[:6]):lettering(char,(x,front-.65,zz+(len(text[:6])-1)*.17-i*.34),.50,.29,letters,mesh)
        for x in [-w*.27,w*.24]:
            box('HVAC feet',(x,0,base+h+.18),(1.35,1.25,.3),metal)
            box('HVAC enclosure',(x,0,base+h+.70),(1.25,1.1,.8),accent)
            for j in range(7):box('HVAC vent',(x,-.57,base+h+.40+j*.08),(1.06,.04,.032),metal)
            cylinder('roof ventilator',(x,.10,base+h+1.12),.33,.23,metal)
