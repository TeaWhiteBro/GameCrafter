"""Measured albedo-region edits; preserve spatial texture/UV detail and independent PBR controls."""
import numpy as np
from mathutils import Vector

def spatial_uv_mask(ob, image, height_range):
    """Rasterize the actual source roof/body region into its existing UV atlas."""
    width,height=image.size;mask=np.zeros((height,width),dtype=bool)
    low=min(v.co.z for v in ob.data.vertices);span=max(v.co.z for v in ob.data.vertices)-low
    uv=ob.data.uv_layers.active
    for face in ob.data.polygons:
        z=(face.center.z-low)/max(span,1e-8)
        if not height_range[0]<=z<=height_range[1]:continue
        points=np.array([[uv.data[i].uv.x%1*width,uv.data[i].uv.y%1*height] for i in face.loop_indices])
        for i in range(1,len(points)-1):
            a,b,c=points[[0,i,i+1]]
            if np.ptp([a[0],b[0],c[0]])>width*.5 or np.ptp([a[1],b[1],c[1]])>height*.5:continue
            x0,y0=np.maximum(0,np.floor(np.minimum(np.minimum(a,b),c)).astype(int)-1)
            x1,y1=np.minimum([width-1,height-1],np.ceil(np.maximum(np.maximum(a,b),c)).astype(int)+1)
            if x1<x0 or y1<y0:continue
            xx,yy=np.meshgrid(np.arange(x0,x1+1)+.5,np.arange(y0,y1+1)+.5)
            cross=[(q[0]-p[0])*(yy-p[1])-(q[1]-p[1])*(xx-p[0]) for p,q in [(a,b),(b,c),(c,a)]]
            inside=((cross[0]>=-1e-6)&(cross[1]>=-1e-6)&(cross[2]>=-1e-6))|((cross[0]<=1e-6)&(cross[1]<=1e-6)&(cross[2]<=1e-6))
            mask[y0:y1+1,x0:x1+1] |= inside
    return mask | np.roll(mask,1,0) | np.roll(mask,-1,0) | np.roll(mask,1,1) | np.roll(mask,-1,1)

def hsv(rgb):
    high=rgb.max(-1);low=rgb.min(-1);delta=high-low;den=np.maximum(delta,1e-8);h=np.zeros_like(high)
    for channel,expr in [(0,((rgb[...,1]-rgb[...,2])/den)%6),(1,(rgb[...,2]-rgb[...,0])/den+2),(2,(rgb[...,0]-rgb[...,1])/den+4)]:
        h=np.where((rgb.argmax(-1)==channel)&(delta>1e-8),expr*60,h)
    return np.stack([h,np.where(high>1e-8,delta/np.maximum(high,1e-8),0),high],-1)

def refine(ob,rules,image):
    pixels=np.asarray(image.pixels[:],dtype=np.float32).reshape(image.size[1],image.size[0],4)
    original=pixels.copy();values=hsv(original[...,:3]);label=np.zeros(pixels.shape[:2],dtype=np.int16);audit=[]
    for i,rule in enumerate(rules,1):
        limits=rule['hsv_range'];mask=np.ones(pixels.shape[:2],bool)
        for axis,(low,high) in enumerate(limits):mask &= (values[...,axis]>=low)&(values[...,axis]<=high)
        if rule.get('height_range'):
            mask &= spatial_uv_mask(ob,image,rule['height_range'])
        mask &= label==0;label[mask]=i
        pixels[mask,:3]=np.clip(original[mask,:3]*np.asarray(rule['rgb_multiplier']),0,1)
        audit.append({'region':rule['name'],'selected_pixels':int(mask.sum()),'fraction':float(mask.mean()),'operation':rule})
        if not mask.any():raise ValueError('Texture region selected no pixels: '+rule['name'])
    image.pixels.foreach_set(pixels.ravel());image.update()
    original_mat=ob.data.materials[0];indices=[0]
    for rule in rules:
        if rule.get('split_material',True) is False:
            indices.append(0);continue
        mat=original_mat.copy();mat.name=rule['name'];bs=next(n for n in mat.node_tree.nodes if n.type=='BSDF_PRINCIPLED')
        if 'roughness' in rule:
            for link in list(bs.inputs['Roughness'].links):mat.node_tree.links.remove(link)
            bs.inputs['Roughness'].default_value=rule['roughness']
        mat['pipeline_normal_strength']=rule.get('normal_strength',.5)
        for node in mat.node_tree.nodes:
            if node.type=='NORMAL_MAP':node.inputs['Strength'].default_value=rule.get('normal_strength',.5)
        ob.data.materials.append(mat);indices.append(len(ob.data.materials)-1)
    uv=ob.data.uv_layers.active
    for face in ob.data.polygons:
        point=sum((uv.data[i].uv for i in face.loop_indices),Vector((0,0)))/len(face.loop_indices)
        selected=label[min(image.size[1]-1,int((point.y%1)*image.size[1])),min(image.size[0]-1,int((point.x%1)*image.size[0]))]
        face.material_index=indices[selected]
    return {'method':'UV-preserving HSV-selected albedo edits with independent PBR material regions','regions':audit}
