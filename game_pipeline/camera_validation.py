"""Exercise view switches in one running game, separate from fixed-view route QA."""
from pathlib import Path
import shutil,time
from .core import StageError,read_json,write_json
from .rendering import launch_args

def validate_report(report):
    if report.get('probe_space_validated') is not True or report.get('probe_queries',0)<1:
        raise StageError('Camera switch test lacks actual collision-validated probe space')
    cases=report.get('cases',[])
    if len(cases)!=16 or report.get('passed') is not True or not report.get('returned_to_third'):
        raise StageError('Camera switch suite incomplete or failed')
    expected=['first']*4+['third']*4+['isometric']*4+['third']*4
    for i,(row,mode) in enumerate(zip(cases,expected)):
        if row.get('case')!=i or row.get('camera')!=mode or not row.get('passed') or row.get('samples',0)<30 or row.get('travel_cm',0)<=100:
            raise StageError('Camera case lacks valid movement and switch evidence: '+str(i))
        if not all(row.get(k) is True for k in ['owner_visibility_correct','projection_correct','player_framed','mesh_scale_valid']):
            raise StageError('Camera visibility/projection/framing failed')
        if row.get('max_input_error_deg',180)>=8 or row.get('max_world_step_cm',1e9)>=25:
            raise StageError('Camera input direction or motion continuity failed')
    if report.get('switch_displacement_cm',1e9)>=.01:raise StageError('Camera switch moved the player')
    return report

def run(ctx,cfg):
    if not ctx.inputs['playtest'].get('passed'):raise StageError('Gameplay must pass before camera acceptance')
    project=ctx.inputs['ue_assemble']['project'];base=Path(project).parent
    expected=base/'Saved/GameDemoCameraQA.json'
    if expected.exists():expected.unlink()
    start=time.time()
    # A runtime-only fixed-step toggle can miss engine startup timing state.
    # Initialize fixed 60 Hz before the world starts; screenshots must not add simulation time.
    ctx.run([ctx.machine['unreal_editor'],project,'/Game/Generated/Maps/Demo','-game','-RenderOffscreen',
        '-windowed','-ResX=1600','-ResY=900','-ForceRes','-NoSound','-unattended','-nosplash','-NoLiveCoding',
        '-GameDemoCameraTest','-UseFixedTimeStep','-FPS=60',
        '-ddc=InstalledNoZenLocalFallback','-abslog='+str(ctx.directory/'engine.log')]+launch_args(),timeout=240,cwd=base)
    if not expected.is_file():raise StageError('Camera test did not produce evidence')
    report=read_json(expected);path=ctx.directory/'validation.json';write_json(path,report)
    views=[]
    for image in sorted((base/'Saved/Screenshots').rglob('*.png'),key=lambda p:p.stat().st_mtime):
        if image.stat().st_mtime>=start:
            dest=ctx.directory/f'view_{len(views)}.png';shutil.copy2(image,dest);views.append(str(dest))
    if len(views)!=4:raise StageError('Camera switch suite must produce four current views')
    validate_report(report)
    return {'passed':True,'validation':str(path),'views':views,'_files':[path]+views}
