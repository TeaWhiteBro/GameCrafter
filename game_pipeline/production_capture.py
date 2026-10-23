"""Calibrated scenario capture, complete paired export, and independent release checks."""
from pathlib import Path
import copy, json, shutil
import numpy as np
from PIL import Image,ImageDraw
from .core import ROOT,StageError,read_json,write_json,digest,fingerprint
from .workflow import CAMERAS,CHANNELS
from .dataset import load_frame,whitebox_check,calibration_check,whitebox_tone,annotate
from .rendering import profile
from .capture_quality import near_field_fraction,require_near_field,check_sequence

def plan_jobs(assembled,cfg):
    """One job contract for early probing and final production collection."""
    if not assembled.get('whitebox',{}).get('available'):raise StageError('Structural whitebox companion is mandatory')
    if 'exploration' in cfg['activities'] and not assembled.get('exploration'):raise StageError('Exploration capture requested without a roaming map')
    sequence=[]
    route_length=assembled.get('exploration',{}).get('route_length_m',150)
    roam_warmup=round(min(25,2+route_length*.2/4.9)*60)
    # The standard combat bot approaches before sustained melee. Keep the
    # entire clip before its scripted death/reset phase, including long clips.
    combat_warmup=min(900,max(330,1800-cfg['frames']))
    for activity in cfg['activities']:
        for camera in cfg['cameras']:
            sequence.append({'key':activity+'_'+camera,'camera':camera,'activity':activity,'frames':cfg['frames'],
                'width':cfg['width'],'height':cfg['height'],'whitebox':True,'warmup_frames':combat_warmup if activity=='combat' else roam_warmup,'calibration':False})
    if cfg.get('visibility_policy')=='all_activities_v1':
        for job in sequence:job['visibility_policy']='all_activities_v1'
    calibration=[{'key':'calibration_'+c,'camera':c,'activity':'idle','frames':4,'width':cfg['width'],
        'height':cfg['height'],'whitebox':True,'warmup_frames':90,'calibration':True} for c in cfg['cameras']]
    return {'schema_version':4,'channels':CHANNELS,'cameras':cfg['cameras'],'activities':cfg['activities'],
        'simulation_fps':60,'sequences':sequence,'calibration':calibration,
        'pairing':'All modalities share one post-animation capture tick per camera. Cameras use separate controlled scenario runs; cross-run bone identity is not guaranteed.',
        'sampling':'Standard combat bot: prefer sustained melee at 15 seconds; longer clips start earlier to end by 30 seconds, before scripted death/reset. Actual contact must still pass. Exploration samples an early segment after about 20 percent of unique-road length; not full-map dataset coverage. Full-map traversal is verified separately.',
        'whitebox':'Independent structural low mesh and animated capsules; paired camera/time, intentionally different silhouettes.'}


def capture_plan(ctx,cfg):
    if not ctx.inputs['playtest'].get('passed') or not ctx.inputs['camera_validation'].get('passed'):
        raise StageError('Gameplay and camera acceptance are prerequisites for data collection')
    path=ctx.directory/'capture_plan.json'
    write_json(path,plan_jobs(read_json(ctx.inputs['ue_assemble']['report']),cfg))
    return {'plan':str(path),'_files':[path]}

def export_fingerprint():
    """Direct export reuse is narrower than reuse of verified native frames."""
    paths=['capture_dataset.py','game_pipeline/dataset.py','game_pipeline/whitebox_presence.py',
           'game_pipeline/capture_quality.py','game_pipeline/production_capture.py']
    return fingerprint({p:digest(ROOT/p) for p in paths})


def committed(folder,project,job,require_exporter=False):
    folder=Path(folder)
    p=folder/'commit.json'
    if not p.is_file():return False
    commit=read_json(p)
    if commit.get('job')!=job:return False
    if require_exporter and commit.get('exporter')!=export_fingerprint():return False
    if not commit.get('files') or 'source.json' not in commit['files']:return False
    if not all((folder/f).is_file() and digest(folder/f)==sha for f,sha in commit.get('files',{}).items()):return False
    source=read_json(folder/'source.json');base=Path(project).parent
    if source.get('rendering_profile')!=profile():return False
    return source.get('project')==str(Path(project).resolve()) and bool(source.get('files')) and all((base/f).is_file() and digest(base/f)==sha for f,sha in source['files'].items())

def capture_job(ctx,project,job):
    target=ctx.directory/job['key'];out=target
    if committed(out,project,job,require_exporter=True):
        return out
    attempt=0
    while out.exists():
        attempt+=1;out=target.with_name(target.name+'_attempt_'+str(attempt))
        if committed(out,project,job,require_exporter=True):
            return out
    # Native frames, viewing videos, and PNGs are substantial; check before starting UE.
    estimated=job['width']*job['height']*job['frames']*26
    if shutil.disk_usage(ctx.directory).free<estimated+2*1024**3:raise StageError('Insufficient disk space for complete capture exports')
    args=[ctx.machine['python'],ROOT/'capture_dataset.py','--project',project,'--out',out,
        '--camera',job['camera'],'--frames',str(job['frames']),'--width',str(job['width']),'--height',str(job['height']),
        '--activity',job['activity'],'--warmup-frames',str(job['warmup_frames']),'--whitebox','--unreal-editor',ctx.machine['unreal_editor']]
    if job['calibration']:args+=['--calibration','--no-videos']
    reused=False
    for stage in sorted(ctx.directory.parent.iterdir(),key=lambda p:p.stat().st_mtime,reverse=True):
        # A completed sequence has its own full receipt even if another camera
        # later failed. Verify that receipt and source rather than discarding it.
        if not stage.is_dir():continue
        for old in stage.glob(job['key']+'*'):
            if not old.is_dir() or not committed(old,project,job):continue
            out.mkdir(parents=True)
            for source in [old/'source.json',old/'capture_result.json']+list((old/'raw').glob('*')):
                dest=out/source.relative_to(old);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,dest)
            write_json(out/'raw_reuse.json',{'source':str(old),'commit_sha256':digest(old/'commit.json'),'reason':'Exact project content and activity/camera settings; committed native frames verified before exporter-only replay.'})
            reused=True;args+=['--process-only'];break
        if reused:break
    ctx.run(args,timeout=max(900,job['frames']*12),log_name=job['key']+'.log')
    report=read_json(out/'validation.json')
    if not report.get('passed') or not report.get('export_complete'):raise StageError('Capture/export failed: '+job['key'])
    # Fail this sequence before spending time on the remaining camera runs.
    check_sequence(out,job)
    if job['activity']=='combat' and not job['calibration'] and job['camera']!='first':
        counts={'player':[],'boss':[]}
        for path in sorted((out/'raw').glob('*.json')):
            _,_,_,ids=load_frame(path)
            for role,cls in [('player',10),('boss',11)]:counts[role].append(int(np.count_nonzero(ids==cls)))
        visibility={role:validate_combat_visibility(values,job['width']*job['height'],role)
                    for role,values in counts.items()}
        write_json(out/'combat_visibility.json',visibility)
    if exploration_visibility_required(job):
        counts=[]
        for path in sorted((out/'raw').glob('*.json')):
            native,_,_,ids=load_frame(path)
            counts.append(exploration_player_pixels(native['actors'],ids))
        write_json(out/'exploration_visibility.json',validate_exploration_visibility(counts,job['width']*job['height']))
    files={str(p.relative_to(out)):digest(p) for p in out.rglob('*') if p.is_file() and p.name not in ['engine.log','process.log','commit.json']}
    write_json(out/'commit.json',{'job':job,'files':files,'exporter':export_fingerprint()})
    return out

def capture_probe(ctx,cfg):
    """Capture complete final jobs early, then reuse verified immutable exports."""
    project=ctx.inputs['ue_assemble']['project']
    plan=plan_jobs(read_json(ctx.inputs['ue_assemble']['report']),cfg)
    scope=cfg.get('probe_scope','first_combat')
    if scope not in ('first_combat','all_requested'):raise StageError('Unknown early capture scope')
    jobs=plan['sequences'] if scope=='all_requested' else [next(j for j in plan['sequences'] if j['key']=='combat_first')]
    sequences={}
    for job in jobs:
        out=capture_job(ctx,project,job)
        check=validate_sequence(out,job,project)
        sequences[job['key']]={'directory':str(out),'job':job,'validation':check}
    record=ctx.directory/'probe.json'
    write_json(record,{'passed':True,'schema_version':2,'sequences':sequences,
        'scope':scope,'acceptance':'All requested jobs must pass; gameplay, independent calibration and final all-frame pairing remain mandatory.'})
    return {'passed':True,'probe':str(record),'_files':[p for p in ctx.directory.rglob('*')
        if p.is_file() and p.name not in ['engine.log','process.log','receipt.json']]}


def reusable_probe(ctx,project,job):
    value=ctx.inputs.get('capture_probe',{})
    if not value.get('passed'):return None
    probe=read_json(value['probe'])
    if not probe.get('passed'):return None
    entry=probe.get('sequences',{}).get(job['key'],{}) if 'sequences' in probe else probe
    if entry.get('job')!=job:return None
    out=Path(entry['directory'])
    if not committed(out,project,job,require_exporter=True):return None
    # Read-only validation: never modify the committed producer's output.
    validate_sequence(out,job,project)
    return out


def collect(ctx,calibration):
    project=ctx.inputs['ue_assemble']['project'];plan=read_json(ctx.inputs['capture_plan']['plan'])
    if not calibration and not ctx.inputs['calibration'].get('passed'):raise StageError('All camera calibrations must pass first')
    collections={};reused_files=[]
    for job in plan['calibration' if calibration else 'sequences']:
        reused=None if calibration else reusable_probe(ctx,project,job)
        out=reused or capture_job(ctx,project,job)
        if reused:
            reused_files += [out/'commit.json']+[out/p for p in read_json(out/'commit.json')['files']]
        collections[job['key']]={'directory':str(out),'job':job,'validation':read_json(out/'validation.json'),
            'reused_early_probe':bool(reused)}
    record=ctx.directory/'collections.json';write_json(record,{'passed':True,'cameras':plan['cameras'],'sequences':collections,'project':project})
    return {'passed':True,'collections':str(record),'_files':reused_files+[p for p in ctx.directory.rglob('*') if p.is_file() and p.name not in ['engine.log','process.log','receipt.json']]}

def calibration(ctx,cfg):return collect(ctx,True)
def dataset(ctx,cfg):return collect(ctx,False)

def validate_combat_visibility(pixel_counts,total_pixels,role='boss'):
    """Motion behind the camera is not useful combat coverage. Allow brief occlusion."""
    minimum=max(4,int(np.ceil(total_pixels*.001)))
    visible=[n>=minimum for n in pixel_counts]
    opening=visible[:6]
    if role not in ('player','boss'):raise StageError('Unknown combat visibility role')
    result={'minimum_'+role+'_pixels':minimum,role+'_visible_frames':sum(visible),
        'frames':len(visible),'opening_visible_frames':sum(opening),
        'minimum_pixel_count':min(pixel_counts,default=0),
        'required_fraction':.8,'required_opening_fraction':.5}
    if not visible or sum(visible)<np.ceil(len(visible)*.8) or sum(opening)<np.ceil(len(opening)*.5):
        raise StageError('Combat subject is out of frame or occluded: '+json.dumps(result))
    return result

def exploration_visibility_required(job):
    return (job.get('visibility_policy')=='all_activities_v1' and not job['calibration']
            and job['activity']=='exploration' and job['camera']!='first')


def exploration_player_pixels(actors,ids):
    players=[a for a in actors if a.get('role')=='player']
    if len(players)!=1 or players[0].get('camera_hidden') is not False or players[0].get('class_id')!=10:
        raise StageError('Missing visible exploration player identity')
    return int(np.count_nonzero(ids==10))


def validate_exploration_visibility(pixel_counts,total_pixels):
    """A low-cost occlusion sentinel, not a substitute for visual readability review."""
    if not pixel_counts or any(type(n) is not int or n<0 or n>total_pixels for n in pixel_counts):
        raise StageError('Invalid exploration visibility samples')
    minimum=max(4,int(np.ceil(total_pixels*.00025)))
    visible=[n>=minimum for n in pixel_counts]
    gap=longest=0
    for flag in visible:
        gap=0 if flag else gap+1;longest=max(longest,gap)
    result={'minimum_player_pixels':minimum,'visible_frames':sum(visible),'frames':len(visible),
            'required_fraction':.9,'opening_visible_frames':sum(visible[:6]),
            'longest_occlusion_frames':longest,'maximum_occlusion_frames':12,
            'scope':'Captured exploration segment only; complete map traversal is a separate gameplay test.'}
    if sum(visible)<np.ceil(len(visible)*.9) or sum(visible[:6])<np.ceil(min(6,len(visible))*.5) or longest>12:
        raise StageError('Exploration player is out of frame or occluded: '+json.dumps(result))
    return result


def validate_combat_contact(samples):
    """Visible air swings are not evidence of an actual combat interaction."""
    previous={};events={'player':0,'boss':0};closest=float('inf')
    for actors in samples:
        roles={a['role']:a for a in actors}
        if len(actors)!=2 or set(roles)!={'player','boss'}:raise StageError('Combat needs both participants')
        positions=[]
        for role in ['player','boss']:
            actor=roles[role];position=np.asarray(actor.get('position_cm',[]),dtype=float)
            health=actor.get('health')
            if position.shape!=(3,) or not np.isfinite(position).all() or isinstance(health,bool) or not isinstance(health,(int,float)) or not np.isfinite(health):
                raise StageError('Missing finite combat telemetry')
            positions.append(position)
            damaged=role in previous and health<previous[role]-.01
            if damaged or actor['action'] in ['hit','stagger']:events[role]+=1
            previous[role]=health
        closest=min(closest,float(np.linalg.norm((positions[0]-positions[1])[:2])))
    result={'impact_frames':events,'closest_distance_cm':closest,'maximum_contact_distance_cm':500}
    if not samples or closest>500 or not sum(events.values()):
        raise StageError('Combat clip lacks actual contact or hit feedback: '+json.dumps(result))
    return result

def validate_sequence(folder,job,project):
    """Compare every authoritative exported raster with native frames and check active motion."""
    folder=Path(folder);validation=read_json(folder/'validation.json');schema=read_json(folder/'dataset.json')
    if not validation.get('passed') or not validation.get('export_complete') or not schema.get('whitebox'):
        raise StageError('Missing completed five-channel export')
    source=read_json(folder/'source.json');base=Path(project).parent
    if source.get('rendering_profile')!=profile():raise StageError('Capture rendering profile is stale or missing')
    if source.get('project')!=str(Path(project).resolve()) or source.get('camera')!=job['camera']:
        raise StageError('Capture source project/camera mismatch')
    settings={k:job[k] for k in ['activity','warmup_frames','frames','width','height','whitebox','calibration']}
    if source.get('capture_settings')!=settings:raise StageError('Capture scenario/settings mismatch')
    if not source.get('files') or any(not (base/p).is_file() or digest(base/p)!=h for p,h in source['files'].items()):
        raise StageError('Capture uses stale runtime, scene, material or character content')
    records=[json.loads(line) for line in (folder/'frames.jsonl').read_text().splitlines()]
    if len(records)!=job['frames']:raise StageError('Sequence has missing or extra frames')
    if any(len(list((folder/name).glob('*'+ext)))!=job['frames'] for name,ext in [('rgb','.png'),('depth','.npy'),('semantic_ids','.png'),('skeleton','.png'),('whitebox','.png'),('joints','.json')]):
        raise StageError('A modality has missing or extra frame files')
    previous=None;previous_bones=None;moving=0;early_motion=0;opening_activity=False;boss_pixels=[];player_pixels=[];combat_samples=[];near_field=[]
    for index,row in enumerate(records):
        if row['frame_id']!=index or row['camera_mode']!=job['camera']:
            raise StageError('Frame/camera identity mismatch')
        stem=f'{index:06d}'
        required={'rgb':'rgb/'+stem+'.png','depth':'depth/'+stem+'.npy','semantics':'semantic_ids/'+stem+'.png',
            'skeleton':'skeleton/'+stem+'.png','metadata':'joints/'+stem+'.json','whitebox':'whitebox/'+stem+'.png'}
        if any(row.get(k)!=v for k,v in required.items()):raise StageError('Frame manifest does not pair the requested channels')
        native,rgb,depth,ids=load_frame(folder/'raw'/(stem+'.json'));meta=read_json(folder/row['metadata'])
        if native.get('semantic_encoding')!=schema.get('semantic_encoding'):
            raise StageError('Frame semantic encoding differs from dataset schema')
        if job['activity']=='combat' and not job['calibration']:
            bosses=[a for a in native['actors'] if a['role']=='boss' and not a['camera_hidden']]
            if len(bosses)!=1 or bosses[0].get('class_id')!=11:raise StageError('Missing combat subject identity')
            boss_pixels.append(int(np.count_nonzero(ids==bosses[0]['class_id'])))
            if job['camera']!='first':
                players=[a for a in native['actors'] if a['role']=='player' and not a['camera_hidden']]
                if len(players)!=1 or players[0].get('class_id')!=10:raise StageError('Missing visible player identity')
                player_pixels.append(int(np.count_nonzero(ids==10)))
            combat_samples.append([{k:a.get(k) for k in ['role','position_cm','health','action']} for a in native['actors']])
            if job['camera']=='first':near_field.append(near_field_fraction(native,depth,ids))
        if exploration_visibility_required(job):player_pixels.append(exploration_player_pixels(native['actors'],ids))
        if any(meta.get(k)!=native.get(k) for k in ['frame_id','simulation_step','time_seconds','camera_mode','camera_world_cm','world_to_clip','projection']):
            raise StageError('Skeleton export no longer describes the native frame/camera')
        if [[b['world_cm'] for b in a['bones']] for a in meta['actors']] != [[b['world_cm'] for b in a['bones']] for a in native['actors']]:
            raise StageError('Exported skeleton has stale or altered animated bone positions')
        if meta['frame_id']!=index or meta['camera_mode']!=job['camera'] or meta['time_seconds']!=row['time_seconds']:
            raise StageError('Per-modality timing mismatch')
        if [meta['width'],meta['height']]!=[job['width'],job['height']]:raise StageError('Raster dimensions mismatch')
        if previous is not None and abs(meta['time_seconds']-previous-1/60)>.0001:raise StageError('Discontinuous simulation time')
        previous=meta['time_seconds']
        if not np.array_equal(np.asarray(Image.open(folder/row['rgb'])),rgb):raise StageError('RGB export differs from native frame')
        if not np.array_equal(np.asarray(Image.open(folder/row['semantics'])),ids):raise StageError('Semantic ID export differs from native frame')
        skeleton,_=annotate(copy.deepcopy(native),depth,ids)
        if not np.array_equal(np.asarray(Image.open(folder/row['skeleton'])),np.asarray(skeleton)):
            raise StageError('Skeleton raster differs from the current native pose and visibility')
        expected=np.where(np.isfinite(depth)&(depth>0)&(depth<5000)&(ids!=0),depth,np.nan).astype('<f4')
        exported=np.load(folder/row['depth'],allow_pickle=False)
        if exported.dtype!=np.dtype('<f4') or not np.array_equal(exported,expected,equal_nan=True):raise StageError('Metric depth export differs from native frame')
        white=np.fromfile(folder/'raw'/(stem+'.whitebox.bgra'),np.uint8).reshape(job['height'],job['width'],4)[:,:,[2,1,0]]
        if not whitebox_check(meta,white)['passed'] or not np.array_equal(np.asarray(Image.open(folder/row['whitebox'])),whitebox_tone(white)):
            raise StageError('Whitebox camera, capsule or raster pairing failed')
        if job['calibration']:
            if not calibration_check(native,rgb,depth,ids)['passed'] or not calibration_check(native,white,depth,ids)['passed']:
                raise StageError('Independent camera raster/metric calibration failed')
        for actor in meta['actors']:
            if actor['camera_hidden'] != (actor['role']=='player' and job['camera']=='first'):
                raise StageError('Camera owner visibility wrong in exported skeleton')
            if index<=5 and actor.get('action') in ['move','light1','light2','light3','heavy','hit','stagger','dodge','riposte']:opening_activity=True
        bones=np.array([b['world_cm'] for a in meta['actors'] for b in a['bones']])
        if previous_bones is not None and bones.shape==previous_bones.shape and np.max(np.abs(bones-previous_bones))>.01:
            moving+=1
            if index<=5:early_motion+=1
        previous_bones=bones
    combat_visibility=None;player_visibility=None;combat_contact=None;near_field_check=None
    if not job['calibration']:
        if moving<min(10,job['frames']//4) or not early_motion or not opening_activity:raise StageError('Active scenario has a static opening or insufficient character motion')
        if job['activity']=='combat':
            combat_visibility=validate_combat_visibility(boss_pixels,job['width']*job['height'])
            if job['camera']!='first':player_visibility=validate_combat_visibility(player_pixels,job['width']*job['height'],'player')
            combat_contact=validate_combat_contact(combat_samples)
            if job['camera']=='first':near_field_check=require_near_field(near_field)
        if exploration_visibility_required(job):player_visibility=validate_exploration_visibility(player_pixels,job['width']*job['height'])
        if validation.get('lossless_semantic_video_roundtrip') is not True:raise StageError('Lossless semantic video was not verified')
        for name in ['rgb.mp4','depth_preview.mp4','semantic_preview.mp4','skeleton.mp4','skeleton_overlay.mp4','semantic_ids_lossless.mkv','whitebox.mp4','whitebox_pair.mp4']:
            if not (folder/name).is_file() or (folder/name).stat().st_size<100:raise StageError('Missing requested video export: '+name)
    return {'passed':True,'frames':len(records),'active_motion_pairs':moving,'motion_in_first_five_pairs':early_motion,'combat_visibility':combat_visibility,'player_visibility':player_visibility,'combat_contact':combat_contact,'near_field':near_field_check,'source_files':source['files']}

def validate_pairs(ctx,cfg):
    project=ctx.inputs['ue_assemble']['project'];plan=read_json(ctx.inputs['capture_plan']['plan'])
    collections={**read_json(ctx.inputs['calibration']['collections'])['sequences'],**read_json(ctx.inputs['dataset']['collections'])['sequences']}
    expected=plan['calibration']+plan['sequences']
    if set(collections)!=set(j['key'] for j in expected):raise StageError('Missing or unexpected camera/scenario collection')
    checks={};sources=None;views=[]
    for job in expected:
        folder=Path(collections[job['key']]['directory']);check=validate_sequence(folder,job,project)
        if sources is None:sources=check['source_files']
        elif check['source_files']!=sources:raise StageError('Camera/scenario runs do not share exactly the same content revision')
        check.pop('source_files');checks[job['key']]=check
        if not job['calibration']:
            canvas=Image.new('RGB',(1600,620),'#191e21');draw=ImageDraw.Draw(canvas)
            draw.text((12,8),job['key']+' | RGB / Depth / Semantics / Skeleton / Structural whitebox',fill='white')
            for ri,index in enumerate([0,job['frames']//2,job['frames']-1]):
                for ci,name in enumerate(['rgb','depth_preview','semantic_preview','skeleton','whitebox']):
                    with Image.open(folder/name/f'{index:06d}.png') as im:
                        im=im.convert('RGBA');background=Image.new('RGBA',im.size,(14,18,22,255));background.alpha_composite(im)
                        canvas.paste(background.convert('RGB').resize((320,180)),(ci*320,32+ri*196))
            path=ctx.directory/(job['key']+'.jpg');canvas.save(path,quality=90);views.append(str(path))
    path=ctx.directory/'validation.json';write_json(path,{'passed':True,'channels':CHANNELS,'cameras':plan['cameras'],
        'activities':plan['activities'],'collections':collections,'checks':checks,'views':views,
        'whitebox_pairing':'Shared camera/time and capsule bone anchors; detailed and structural silhouettes intentionally differ.'})
    return {'passed':True,'validation':str(path),'views':views,'_files':[path]+views}

REGISTRY={'agent.capture_plan':capture_plan,'ue.capture_probe':capture_probe,'ue.calibration':calibration,'ue.dataset_paired':dataset,'dataset.validate_pairs':validate_pairs}
