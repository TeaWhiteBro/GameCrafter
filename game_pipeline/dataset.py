"""Lossless aligned training artifacts plus explicitly labeled viewing proxies."""
from pathlib import Path
import json, subprocess, hashlib
import numpy as np
from PIL import Image,ImageDraw
from .whitebox_presence import presence as whitebox_presence

CLASSES={0:'sky',1:'terrain',2:'paving',3:'architecture',4:'rock',5:'vegetation',6:'prop',10:'player',11:'boss',255:'unknown'}
PALETTE={0:(16,23,38),1:(109,81,53),2:(168,153,120),3:(121,115,154),4:(103,112,119),5:(48,128,71),6:(180,120,53),10:(57,186,242),11:(236,92,66),255:(255,0,255)}

def calibration_check(meta,rgb,depth,ids):
    h,w=ids.shape;yy,xx=np.mgrid[:h,:w];expected=np.zeros_like(ids);z=np.zeros_like(depth)
    for obj in sorted(meta['calibration'],key=lambda o:-o['front_depth_m']):
        corners=np.array(obj['front_corners_px']);lo=corners.min(0);hi=corners.max(0)
        mask=(xx>=lo[0])&(xx<=hi[0])&(yy>=lo[1])&(yy<=hi[1])
        expected[mask]=obj['class_id'];z[mask]=obj['front_depth_m']
    roi=expected>0;actual=(ids==200)|(ids==201)
    union=int((roi|actual).sum());intersection=int((roi&actual&(expected==ids)).sum())
    match=roi&(expected==ids)
    error=float(np.max(np.abs(depth[match]-z[match]))) if match.any() else 1e9
    r,g,b=np.moveaxis(rgb.astype(float),-1,0)
    # Filmic tonemapping can desaturate bright emitters; classify chroma, not
    # a fixed linear intensity ratio, while still requiring a large hue margin.
    red=(r-g>35)&(r-b>35);cyan=(g-r>35)&(b-r>35)
    rgb_match=((ids==200)&red)|((ids==201)&cyan)
    coverage=float(rgb_match[actual].mean()) if actual.any() else 0.
    iou=intersection/max(1,union)
    return {'passed':iou>.97 and error<.005 and coverage>.98,'raster_iou':iou,'max_depth_error_m':error,'rgb_class_agreement':coverage,'pixels':int(match.sum())}

def project(points,matrix,width,height):
    points=np.asarray(points,float);m=np.asarray(matrix,float).reshape(4,4)
    clip=np.c_[points,np.ones(len(points))]@m
    # A point exactly on the perspective eye plane has no finite projection.
    # Keep it undefined; never turn it into a plausible screen coordinate.
    ndc=np.full((len(points),2),np.nan,dtype=float)
    np.divide(clip[:,:2],clip[:,3:4],out=ndc,where=clip[:,3:4]!=0)
    return (ndc*np.array([.5,-.5])+.5)*np.array([width,height])-.5

def validate_semantic_source(meta,depth,ids,stencil):
    """Verify native visibility encoding; never edit semantic IDs in the exporter."""
    if meta.get('semantic_encoding')!='scene_depth_clear_to_sky_v1' or meta.get('semantic_background_min_depth_m')!=1e10:
        raise ValueError('Unknown native semantic encoding')
    if stencil.shape!=ids.shape or depth.shape!=ids.shape:
        raise ValueError('Native semantic source extent mismatch')
    expected=np.where(depth>=1e10,0,stencil).astype(np.uint8)
    changes=int(np.count_nonzero(expected!=stencil))
    if not np.array_equal(ids,expected) or meta.get('background_stencil_changes')!=changes:
        raise ValueError('Native semantic IDs disagree with preserved stencil and synchronous depth')

def load_frame(path):
    path=Path(path);meta=json.loads(path.read_text(encoding='utf-8'));h,w=meta['height'],meta['width'];prefix=path.with_suffix('')
    rgb=np.fromfile(str(prefix)+'.bgra',np.uint8).reshape(h,w,4)[:,:,[2,1,0]]
    depth=np.fromfile(str(prefix)+'.depth','<f4').reshape(h,w)
    ids=np.fromfile(str(prefix)+'.ids',np.uint8).reshape(h,w)
    if meta.get('semantic_encoding'):
        stencil=np.fromfile(str(prefix)+'.stencil',np.uint8).reshape(h,w)
        validate_semantic_source(meta,depth,ids,stencil)
    return meta,rgb,depth,ids

def whitebox_check(meta,whitebox):
    """Validate actual companion presence, camera/time and evaluated capsule anchors."""
    companion=meta.get('whitebox',{});capsules=companion.get('capsules',[])
    errors=[]
    for capsule in capsules:
        actor=next((a for a in meta['actors'] if a['role']==capsule['role']),None)
        if not actor:return {'passed':False,'error':'Unknown capsule role'}
        bones={b['name']:np.array(b['world_cm']) for b in actor['bones']}
        if capsule['from_bone'] not in bones or capsule['to_bone'] not in bones:return {'passed':False,'error':'Missing capsule bone'}
        a,b=bones[capsule['from_bone']],bones[capsule['to_bone']]
        if capsule['head_extension']:
            delta=(b-a)/max(1e-8,np.linalg.norm(b-a));a=b;b=b+delta*capsule['radius_cm']*.5
        errors.extend([float(np.linalg.norm(a-capsule['a_cm'])),float(np.linalg.norm(b-capsule['b_cm']))])
    error=max(errors,default=1e9)
    same_view=np.array_equal(companion.get('world_to_clip'),meta['world_to_clip'])
    same_step=companion.get('simulation_step')==meta['simulation_step']
    presence=whitebox_presence(meta,whitebox);nonempty=presence['passed']
    expected_roles={a['role'] for a in meta['actors']}
    roles={c['role'] for c in capsules}
    return {'passed':bool(error<.02 and same_view and same_step and nonempty and roles==expected_roles and len(capsules)>=len(expected_roles)*11),'max_capsule_anchor_error_cm':error,'same_camera':same_view,'same_simulation_step':same_step,'nonempty':nonempty,'presence':presence,'capsules':len(capsules)}

def whitebox_tone(image):
    """Fixed display-channel transfer, never adaptive per frame/camera.

    The original GPU BGRA remains available in raw/. This expands the subtle
    gray normal-shading contrast after UE's filmic output without changing any
    raster positions, RGB, metric depth, IDs or bone coordinates.
    """
    return np.rint(255.*(image.astype(np.float32)/255.)**4).astype(np.uint8)

def annotate(meta,depth,ids):
    h,w=ids.shape;overlay=Image.new('RGBA',(w,h));draw=ImageDraw.Draw(overlay);max_error=0;inside=0;visible=0
    for actor in meta['actors']:
        bones=actor['bones'];predicted=project([b['world_cm'] for b in bones],meta['world_to_clip'],w,h)
        for b,px in zip(bones,predicted):
            if b['in_front'] and not np.isfinite(px).all():
                raise ValueError('A joint marked in front has an undefined projection')
            if b['in_front']:max_error=max(max_error,float(np.linalg.norm(px-b['pixel_xy'])))
            x,y=b['pixel_xy'];on=b['in_front'] and 0<=x<w and 0<=y<h and not actor['camera_hidden']
            b['in_frame']=bool(on);b['visible']=False
            if on:
                ix,iy=int(np.clip(round(x),0,w-1)),int(np.clip(round(y),0,h-1));inside+=1
                b['scene_depth_m']=float(depth[iy,ix])
                # Interior joints sit behind their own skin. Require matching role ID,
                # rather than treating the body surface as an occluder of its skeleton.
                b['visible']=bool(ids[iy,ix]==actor['class_id'] and b['camera_z_m']<=depth[iy,ix]+.75)
                visible+=int(b['visible'])
        for b in bones:
            pi=b['parent']
            if pi<0 or pi>=len(bones):continue
            parent=bones[pi]
            if b['in_frame'] and parent['in_frame']:
                # Store both amodal coordinates and a depth-tested visible overlay.
                a=np.array(parent['pixel_xy']);z0=parent['camera_z_m'];end=np.array(b['pixel_xy']);z1=b['camera_z_m']
                length=np.linalg.norm(end-a);steps=max(2,int(length*2))
                if steps>max(w,h)*3:continue
                for t in np.linspace(0,1,steps):
                    x,y=a*(1-t)+end*t;ix,iy=int(round(x)),int(round(y))
                    if 0<=ix<w and 0<=iy<h and ids[iy,ix]==actor['class_id'] and z0*(1-t)+z1*t<=depth[iy,ix]+.75:
                        c=PALETTE[actor['class_id']];draw.ellipse((x-1,y-1,x+1,y+1),fill=(*c,255))
    return overlay,{'projection_error_px':max_error,'joints_in_frame':inside,'visible_joints':visible}

def encode(ffmpeg,pattern,dest,fps,lossless=False):
    args=[ffmpeg,'-v','error','-y','-framerate',str(fps),'-i',str(pattern)]
    args+=['-c:v','ffv1','-level','3','-pix_fmt','gray'] if lossless else ['-c:v','libx264','-crf','18','-pix_fmt','yuv420p']
    subprocess.run(args+[str(dest)],check=True)

def verify_semantic_video(ffmpeg,directory,count,frame_bytes):
    with (directory/'video_verify.log').open('w') as log:
        proc=subprocess.Popen([ffmpeg,'-v','error','-i',str(directory/'semantic_ids_lossless.mkv'),'-f','rawvideo','-pix_fmt','gray','-'],stdout=subprocess.PIPE,stderr=log)
        try:
            for i in range(count):
                decoded=bytearray()
                while len(decoded)<frame_bytes:
                    block=proc.stdout.read(frame_bytes-len(decoded))
                    if not block:raise ValueError('Semantic video ended before its frame manifest')
                    decoded.extend(block)
                expected=np.asarray(Image.open(directory/'semantic_ids'/f'{i:06d}.png'),np.uint8).tobytes()
                if decoded!=expected:raise ValueError('Lossless semantic video failed byte-for-byte round trip')
            if proc.stdout.read(1):raise ValueError('Semantic video has unexpected extra frames')
            if proc.wait(timeout=30):raise ValueError('Semantic video decoder failed')
        except BaseException:
            proc.kill();proc.wait();raise
        finally:proc.stdout.close()

def process(directory,videos=True):
    directory=Path(directory).resolve();result=json.loads((directory/'capture_result.json').read_text())
    if result.get('ok') is not True:raise ValueError('Runtime capture failed')
    paths=sorted((directory/'raw').glob('*.json'))
    if len(paths)!=result['frames']:raise ValueError('Incomplete frame set')
    names=['rgb','depth','semantic_ids','semantic_preview','depth_preview','skeleton','overlay','joints']
    if result.get('whitebox'):names+=['whitebox','whitebox_pair']
    for name in names:(directory/name).mkdir(exist_ok=True)
    records=[];checks={'complete':True,'finite_depth':True,'ontology':True,'projection':True,'temporal_continuity':True,'no_unknown_labels':True}
    last=None;stats=[];class_counts={};rgb_changed=0;last_rgb=None;calibrations=[];whitebox_stats=[]
    allowed=set(CLASSES)|({200,201} if result.get('calibration_only') else set())
    for path in paths:
        meta,rgb,depth,ids=load_frame(path);index=meta['frame_id'];stem=f'{index:06d}'
        if meta.get('semantic_encoding')!=result.get('semantic_encoding'):
            raise ValueError('Frame semantic encoding differs from capture result')
        projection=np.array(meta['projection']).reshape(4,4);view=np.array(meta['world_to_view']).reshape(4,4)
        cv=view@np.diag([1,-1,1,1]);cv[3,:3]/=100
        meta['world_to_camera_cv_m']=cv.T.reshape(-1).tolist()
        meta['extrinsics_convention']='row-major matrix multiplying column [world_x_m,world_y_m,world_z_m,1]; camera right/down/forward'
        w,h=meta['width'],meta['height'];cx=w*(.5+.5*projection[2,0])-.5;cy=h*(.5-.5*projection[2,1])-.5
        meta['intrinsics']={'model':'orthographic','pixels_per_metre':[w*projection[0,0]*50,h*projection[1,1]*50],'principal_point':[w*.5-.5,h*.5-.5]} if meta['orthographic'] else {'model':'pinhole','K':[[w*projection[0,0]/2,0,cx],[0,h*projection[1,1]/2,cy],[0,0,1]]}
        if index!=len(records):raise ValueError('Non-contiguous frame IDs')
        if result.get('whitebox'):
            white=np.fromfile(str(path.with_suffix(''))+'.whitebox.bgra',np.uint8).reshape(h,w,4)[:,:,[2,1,0]]
            wb=whitebox_check(meta,white);wb['frame_id']=index;whitebox_stats.append(wb)
            checks['whitebox_pairing']=checks.get('whitebox_pairing',True) and wb['passed']
            if result.get('calibration_only'):
                checks['whitebox_raster_calibration']=checks.get('whitebox_raster_calibration',True) and calibration_check(meta,white,depth,ids)['passed']
            white=whitebox_tone(white)
            meta['whitebox']['png_transfer']='round(255 * (raw_display_channel / 255)^4), independently for R/G/B; original BGRA preserved in raw'
            Image.fromarray(white).save(directory/'whitebox'/(stem+'.png'))
            pair=Image.new('RGB',(w*2,h));pair.paste(Image.fromarray(rgb));pair.paste(Image.fromarray(white),(w,0));pair.save(directory/'whitebox_pair'/(stem+'.png'))
        valid=np.isfinite(depth)&(depth>0)&(depth<5000)&(ids!=0)
        checks['finite_depth'] &=bool(np.isfinite(depth).all() and np.all(depth>=0))
        observed=set(int(n) for n in np.unique(ids));checks['ontology'] &= observed<=allowed
        if result.get('calibration_only'):
            calibration=calibration_check(meta,rgb,depth,ids);calibrations.append(calibration)
            checks['metric_raster_calibration']=checks.get('metric_raster_calibration',True) and calibration['passed']
        checks['no_unknown_labels'] &=255 not in observed
        for cls,count in zip(*np.unique(ids,return_counts=True)):class_counts[int(cls)]=class_counts.get(int(cls),0)+int(count)
        overlay,stat=annotate(meta,depth,ids);stats.append(stat);checks['projection'] &= stat['projection_error_px']<.01
        if last and meta['camera_mode']==last['camera_mode']:
            checks['temporal_continuity'] &= abs(meta['time_seconds']-last['time_seconds']-1/60)<.0001
        last=meta
        training_depth=np.where(valid,depth,np.nan).astype('<f4');np.save(directory/'depth'/(stem+'.npy'),training_depth)
        Image.fromarray(rgb).save(directory/'rgb'/(stem+'.png'))
        Image.fromarray(ids).save(directory/'semantic_ids'/(stem+'.png'))
        colors=np.zeros((*ids.shape,3),np.uint8)
        for cls,color in PALETTE.items():colors[ids==cls]=color
        Image.fromarray(colors).save(directory/'semantic_preview'/(stem+'.png'))
        near,far=(20.,50.) if meta['orthographic'] else (.5,30.)
        d=np.clip((far-depth)/(far-near),0,1);d[~valid]=0
        dv=(np.dstack([d*.7,d,d*.85])*255).astype(np.uint8);Image.fromarray(dv).save(directory/'depth_preview'/(stem+'.png'))
        overlay.save(directory/'skeleton'/(stem+'.png'))
        comp=Image.fromarray(rgb).convert('RGBA');comp.alpha_composite(overlay);comp.convert('RGB').save(directory/'overlay'/(stem+'.png'))
        (directory/'joints'/(stem+'.json')).write_text(json.dumps(meta,indent=2),encoding='utf-8')
        records.append({'frame_id':index,'time_seconds':meta['time_seconds'],'camera_mode':meta['camera_mode'],'rgb':'rgb/'+stem+'.png','depth':'depth/'+stem+'.npy','semantics':'semantic_ids/'+stem+'.png','skeleton':'skeleton/'+stem+'.png','metadata':'joints/'+stem+'.json'})
        if result.get('whitebox'):records[-1]['whitebox']='whitebox/'+stem+'.png'
        if last_rgb is not None:rgb_changed+=int(not np.array_equal(last_rgb,rgb))
        last_rgb=rgb.copy()
    report={'passed':bool(all(checks.values())),'checks':{k:bool(v) for k,v in checks.items()},'frames':len(records),'class_pixel_counts':class_counts,'max_projection_error_px':max(s['projection_error_px'] for s in stats),'joints_in_frame':sum(s['joints_in_frame'] for s in stats),'visible_joints':sum(s['visible_joints'] for s in stats),'changing_rgb_frames':rgb_changed,'calibration':calibrations}
    if whitebox_stats:report['whitebox']={'max_capsule_anchor_error_cm':max(s.get('max_capsule_anchor_error_cm',1e9) for s in whitebox_stats),'paired_frames':len(whitebox_stats),
        'failed_frames':[s for s in whitebox_stats if not s['passed']],
        'presence_methods':{method:sum(s.get('presence',{}).get('method')==method for s in whitebox_stats) for method in ['global_contrast','capsule_local_contrast','none']}}
    (directory/'validation.json').write_text(json.dumps({**report,'passed':False,'frame_checks_passed':report['passed'],'export_complete':False},indent=2),encoding='utf-8')
    (directory/'frames.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in records),encoding='utf-8')
    schema={**result,'schema_version':1,'classes':CLASSES,'palette':PALETTE,'depth_storage':'NPY float32 metres, camera-forward Z, NaN for sky/invalid','depth_preview_bounds_m':{'isometric':[20,50],'perspective':[.5,30]},'skeleton':'post-animation bone positions; amodal coordinates plus role-surface visibility at the projected pixel (not literal optical visibility of an internal bone); hidden first-person player body is explicitly flagged','authoritative_data':['rgb PNG','depth NPY','semantic_ids PNG','joints JSON'],'viewing_proxies':['rgb.mp4','depth_preview.mp4','semantic_preview.mp4','skeleton_overlay.mp4']}
    (directory/'dataset.json').write_text(json.dumps(schema,indent=2),encoding='utf-8')
    if result.get('whitebox'):
        schema['schema_version']=2
        schema['whitebox_contract']='Independent simplified structural scene + articulated capsules; same world/camera/time as RGB; silhouettes intentionally differ. Not RGB depth or a material override. First-person self-body hidden in both.'
        schema['whitebox_png_transfer']='Fixed power-4 display-channel contrast curve; original native output is raw/*.whitebox.bgra. No per-frame normalization.'
        schema['authoritative_data'].append('whitebox PNG');schema['viewing_proxies']+=['whitebox.mp4','whitebox_pair.mp4']
        (directory/'dataset.json').write_text(json.dumps(schema,indent=2),encoding='utf-8')
    if not report['passed']:raise ValueError('Capture validation failed: '+json.dumps(report['checks']))
    if videos:
        import imageio_ffmpeg
        ffmpeg=imageio_ffmpeg.get_ffmpeg_exe()
        for source,dest in [('rgb','rgb'),('depth_preview','depth_preview'),('semantic_preview','semantic_preview'),('skeleton','skeleton'),('overlay','skeleton_overlay')]:encode(ffmpeg,directory/source/'%06d.png',directory/(dest+'.mp4'),60)
        if result.get('whitebox'):
            for source in ['whitebox','whitebox_pair']:encode(ffmpeg,directory/source/'%06d.png',directory/(source+'.mp4'),60)
        encode(ffmpeg,directory/'semantic_ids/%06d.png',directory/'semantic_ids_lossless.mkv',60,True)
        verify_semantic_video(ffmpeg,directory,len(records),result['width']*result['height'])
        report['lossless_semantic_video_roundtrip']=True
    images=[Image.open(directory/n/'000000.png').convert('RGB') for n in ['rgb','overlay','depth_preview','semantic_preview']]
    w,h=images[0].size;panel=Image.new('RGB',(w*2,h*2))
    for i,im in enumerate(images):panel.paste(im,((i%2)*w,(i//2)*h))
    panel.save(directory/'preview.png');report['export_complete']=True;report['videos_generated']=videos
    (directory/'validation.json').write_text(json.dumps(report,indent=2),encoding='utf-8');return report
