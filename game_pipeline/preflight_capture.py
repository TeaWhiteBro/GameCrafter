"""Runtime observation producer, separate from visual review policy."""
from pathlib import Path
import shutil,time,re
from .core import StageError,read_json,write_json
from .rendering import launch_args

def check_material_compilation(path):
    text=Path(path).read_text(encoding='utf-8',errors='replace')
    if 'Failed to compile Material ' in text:
        raise StageError('Runtime material compilation failed; default fallback is not acceptable art evidence: '+str(path))

def check_oblique_camera(path,count):
    body=Path(path).read_text(encoding='utf-8',errors='replace')
    rows=re.findall(r'ART_CAMERA_DISTANCE index=(\d+) oblique=1 actual_cm=([0-9.]+)',body)
    clear=re.findall(r'OBLIQUE_CAMERA index=(\d+) foreground_clear=(\d)',body)
    if ([int(i) for i,d in rows]!=list(range(count)) or
        [int(i) for i,c in clear]!=list(range(count)) or
        any(c!='1' for i,c in clear) or any(abs(float(d)-2100)>=2 for i,d in rows)):
        raise StageError('Oblique views lack actual camera radius or foreground-clearance evidence')
    return {'camera_distance_cm':[float(d) for i,d in rows], 'foreground_queries_passed':True}

def preserve_failed_runtime(directory,base,name,filename,start,error):
    """Retain fresh partial evidence when the process itself fails or times out."""
    files=[]
    for i,source in enumerate(sorted((base/'Saved/Screenshots').rglob('*.png'))):
        if source.stat().st_mtime<start:continue
        target=directory/f'failed_{name}_{i:02d}.png';shutil.copy2(source,target);files.append(str(target))
    source=base/'Saved'/filename
    if source.is_file() and source.stat().st_mtime>=start:
        target=directory/f'failed_{name}.json';shutil.copy2(source,target);files.append(str(target))
    write_json(directory/f'failed_{name}_process.json',{'passed':False,'error':str(error),'partial_evidence':files,'note':'Fresh partial evidence only; not successful runtime or review evidence.'})

def capture_runtime(ctx, project, scene, directory, oblique_views=False):
    base=Path(project).parent
    views=[];current_labels=[];evidence={}
    tests=[('overview','GameDemoArtReview','GameDemoArtQA.json')]
    if scene.get('exploration'):
        tests += [('places','GameDemoArtReview','GameDemoArtQA.json')]
        if oblique_views:tests += [('oblique','GameDemoArtReview','GameDemoArtQA.json')]
        tests += [('route_'+camera,'GameDemoExplorationTest','GameDemoExplorationQA.json') for camera in ['first','third','isometric']]
    for name,flag,filename in tests:
        path=base/'Saved'/filename
        if path.exists():path.unlink()
        start=time.time()
        args=[ctx.machine['unreal_editor'],project,'/Game/Generated/Maps/Demo','-game','-RenderOffscreen',
            '-windowed','-ResX=1600','-ResY=900','-ForceRes','-NoSound','-unattended','-NoLiveCoding','-PipelineExit',
            '-'+flag,'-ddc=InstalledNoZenLocalFallback','-abslog='+str(directory/(name+'_engine.log'))]
        if name.startswith('route_'):args+=['-PipelineCamera='+name.removeprefix('route_'),'-UseFixedTimeStep','-FPS=60']
        if name=='places':args+=['-PipelinePlaceReview']
        if name=='oblique':args+=['-PipelinePlaceReview','-PipelinePlaceOblique']
        try:ctx.run(args+launch_args(),timeout=300,cwd=base,log_name=str((directory/(name+'.log')).relative_to(ctx.directory)))
        except Exception as error:
            preserve_failed_runtime(directory,base,name,filename,start,error)
            raise
        try:check_material_compilation(directory/(name+'_engine.log'))
        except StageError as error:
            preserve_failed_runtime(directory,base,name,filename,start,error)
            raise
        if not path.is_file():raise StageError('Scene preflight lacks actual runtime evidence: '+name)
        item=read_json(path);evidence[name]=item;write_json(directory/(name+'.json'),item)
        if name=='oblique':
            item['measured_observation']=check_oblique_camera(directory/(name+'_engine.log'),len(scene['exploration']['places']))
            write_json(directory/(name+'.json'),item)
        expected=2 if name=='overview' else len(scene['exploration']['places'])*(2 if name=='places' else 1)
        valid=item.get('passed') if name.startswith('route_') else item.get('current_runtime_views') and item.get('view_count')==expected
        if name=='places':valid=valid and item.get('view_centres_verified') is True and item.get('ground_camera_clearance_verified') is True
        if name=='oblique':valid=valid and item.get('view_centres_verified') is True and item.get('oblique_perspective') is True
        current=[p for p in (base/'Saved/Screenshots').rglob('*.png') if p.stat().st_mtime>=start]
        if valid and len(current)<expected:
            raise StageError('Scene preflight lacks current place images')
        for index,p in enumerate(sorted(current,key=lambda p:p.stat().st_mtime)):
            target=directory/f'{name}_{len(views):02d}.png';shutil.copy2(p,target);views.append(str(target))
            place_index=item.get('captured_place_indices',list(range(len(current))))[index]
            if name=='places':
                count=len(scene['exploration']['places']);place=scene['exploration']['places'][index%count]['name']+(' elevated structure view' if index<count else ' opposing ground view')
            elif name=='oblique':place=scene['exploration']['places'][index]['name']+' oblique perspective; normal runtime lighting and all geometry retained'
            else:place=scene['exploration']['places'][place_index]['name'] if name.startswith('route_') and place_index<len(scene['exploration']['places']) else 'courtyard overview'
            current_labels.append(f'CURRENT revised environment: {name}, {place}. Judge actual current defects from this image.')
        if not valid:raise StageError('Scene preflight runtime failed: '+name+'; partial screenshots and diagnostics preserved')
    return {"views":[str(Path(p).relative_to(directory)) for p in views],"labels":current_labels,"evidence":evidence}
