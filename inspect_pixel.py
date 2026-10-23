"""Offline pixel → semantic category → world position → geometry candidates."""
import argparse,json,hashlib
from pathlib import Path
import numpy as np
from PIL import Image
from game_pipeline.pixel_trace import unproject,candidates

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset',type=Path,required=True)
    parser.add_argument('--frame',type=int,default=0)
    parser.add_argument('--pixel',type=int,nargs=2,required=True,metavar=('X','Y'))
    parser.add_argument('--geometry-audit',type=Path)
    parser.add_argument('--out',type=Path)
    a=parser.parse_args();stem=f'{a.frame:06d}';meta_path=a.dataset/'joints'/f'{stem}.json'
    meta=json.loads(meta_path.read_text(encoding='utf-8'))
    x,y=a.pixel
    if not (0<=x<meta['width'] and 0<=y<meta['height']):raise ValueError('Pixel outside capture')
    depth=np.load(a.dataset/'depth'/f'{stem}.npy');ids=np.asarray(Image.open(a.dataset/'semantic_ids'/f'{stem}.png'))
    world=unproject(meta,[x,y],depth[y,x]);class_id=int(ids[y,x])
    result={'frame_id':meta['frame_id'],'pixel':[x,y],'class_id':class_id,'world_m':world,
        'camera_metadata_sha256':hashlib.sha256(meta_path.read_bytes()).hexdigest(),
        'geometry_candidates':[],'interpretation':'Bounding-box candidates within the sampled semantic class; confirm source scene provenance and exact geometry before editing.'}
    if a.geometry_audit:
        audit=json.loads(a.geometry_audit.read_text(encoding='utf-8'))
        result.update(geometry_candidates=candidates(world,class_id,audit),geometry_audit_sha256=hashlib.sha256(a.geometry_audit.read_bytes()).hexdigest())
    text=json.dumps(result,ensure_ascii=False,indent=2)
    if a.out:a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(text,encoding='utf-8')
    print(text)

if __name__=='__main__':main()
