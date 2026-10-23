"""Observed albedo evidence for resource selection; never infer color from names."""
import json,math
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont,ImageStat

def prepare(machine,directory):
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    entries=sorted(machine.get('texture_library',{}).items())
    cols=6;cw=190;ch=205;header=54
    sheet=Image.new('RGB',(cols*cw,header+max(1,math.ceil(len(entries)/cols))*ch),'#e7ebee')
    draw=ImageDraw.Draw(sheet)
    font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',14) if Path('C:/Windows/Fonts/arial.ttf').exists() else ImageFont.load_default()
    draw.text((12,10),'ACTUAL SOURCE ALBEDO: sRGB swatches, before tint/paint/UE lighting',font=font,fill='#15242c')
    draw.text((12,29),'Use visible texture and color; asset names do not guarantee appearance.',font=font,fill='#15242c')
    metrics={}
    for i,(name,maps) in enumerate(entries):
        if not maps.get('base'):raise ValueError('Surface has no albedo: '+name)
        with Image.open(maps['base']) as src:pic=src.convert('RGB').resize((176,176))
        x=(i%cols)*cw+7;y=header+(i//cols)*ch
        sheet.paste(pic,(x,y));draw.text((x,y+179),name,font=font,fill='#15242c')
        pixels=list(pic.resize((24,24)).getdata());luma=sorted((.2126*r+.7152*g+.0722*b)/255 for r,g,b in pixels)
        metrics[name]={'mean_rgb_srgb':[round(v/255,3) for v in ImageStat.Stat(pic).mean],
            'median_luminance_srgb':round(luma[len(luma)//2],3),'dark_fraction_below_0_2':round(sum(v<.2 for v in luma)/len(luma),3),
            'channels':sorted(maps),'interpretation':'Observed source albedo, not final illuminated material or a color recommendation.'}
    path=directory/'surface_albedo_evidence.jpg';sheet.save(path,quality=93)
    report=directory/'surface_albedo_evidence.json';report.write_text(json.dumps(metrics,indent=2),encoding='utf-8')
    return {'image':str(path),'metrics':metrics,'files':[path,report]+[Path(maps['base']) for _,maps in entries]}
