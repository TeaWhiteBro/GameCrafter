"""Bind review labels to visible pixels; original training/render files stay intact."""
from pathlib import Path
import textwrap
from PIL import Image,ImageDraw,ImageFont,ImageOps
from .core import digest,write_json,StageError

def prepare(directory,paths,labels):
    if len(paths)!=len(labels) or not paths:raise StageError('Review images and labels must have a one-to-one mapping')
    folder=Path(directory)/'labeled_evidence';folder.mkdir(parents=True,exist_ok=True)
    try:
        title_font=ImageFont.truetype('C:/Windows/Fonts/segoeuib.ttf',26)
        label_font=ImageFont.truetype('C:/Windows/Fonts/segoeui.ttf',19)
    except OSError:
        title_font=ImageFont.load_default(size=26);label_font=ImageFont.load_default(size=19)
    result=[];manifest=[]
    for i,(source,label) in enumerate(zip(paths,labels),1):
        source=Path(source);before=digest(source)
        # Only a leading CURRENT label declares present evidence. References
        # may contain phrases such as "NOT current" and must remain historical.
        role='CURRENT' if label.upper().startswith('CURRENT') else 'REFERENCE'
        with Image.open(source) as original:
            picture=ImageOps.exif_transpose(original).convert('RGBA')
            picture.thumbnail((1600,1400),Image.Resampling.LANCZOS)
            background=Image.new('RGBA',picture.size,(245,245,245,255));background.alpha_composite(picture)
            canvas=Image.new('RGB',(max(960,picture.width),picture.height+124),(24,57,43) if role=='CURRENT' else (89,56,32))
            canvas.paste(background.convert('RGB'),((canvas.width-picture.width)//2,124))
        draw=ImageDraw.Draw(canvas)
        draw.text((18,8),f'IMAGE {i:02d} | {role} | {source.name}',font=title_font,fill='white')
        for row,line in enumerate(textwrap.wrap(label,width=max(60,(canvas.width-36)//10))[:3]):
            draw.text((18,48+row*23),line,font=label_font,fill=(240,238,221))
        target=folder/f'{i:03d}_{role.lower()}.jpg';canvas.save(target,quality=94,subsampling=0,optimize=True)
        if digest(source)!=before:raise StageError('Source evidence changed while labeling')
        result.append(str(target));manifest.append({'index':i,'role':role,'label':label,'source':str(source),'source_sha256':before,'annotated':str(target),'annotated_sha256':digest(target)})
    write_json(folder/'manifest.json',{'purpose':'Visible image identity for review only. Original RGB and multimodal data are unchanged.','images':manifest})
    return result
