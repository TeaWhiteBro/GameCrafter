"""Capture an isolated released UE demo at a fixed simulated rate, then validate/export."""
from pathlib import Path
import argparse,json,os,subprocess,sys,hashlib,time
from game_pipeline.dataset import process
from game_pipeline.rendering import launch_args,profile
ROOT=Path(__file__).resolve().parent

def main():
    p=argparse.ArgumentParser();p.add_argument('--project',type=Path);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--camera',choices=['first','third','isometric'],default='isometric');p.add_argument('--frames',type=int,default=360)
    p.add_argument('--width',type=int,default=640);p.add_argument('--height',type=int,default=360)
    p.add_argument('--process-only',action='store_true');p.add_argument('--autoplay',action='store_true');p.add_argument('--no-videos',action='store_true')
    p.add_argument('--calibration',action='store_true')
    p.add_argument('--whitebox',action='store_true',help='Require a structural scene + capsule companion pass')
    p.add_argument('--activity',choices=['combat','exploration','idle'])
    p.add_argument('--warmup-frames',type=int)
    p.add_argument('--unreal-editor',type=Path,help='Use the engine configured by the invoking pipeline')
    a=p.parse_args();out=a.out.resolve()
    if not a.process_only:
        if out.exists():raise ValueError('Use a NEW output folder; an interrupted capture is never overwritten')
        if not a.project or not a.project.is_file():raise ValueError('Valid upgraded UE project required')
        out.mkdir(parents=True);m=json.loads((ROOT/'machine.local.json').read_text(encoding='utf-8-sig'))
        if a.unreal_editor:m['unreal_editor']=str(a.unreal_editor.resolve())
        base=a.project.resolve().parent
        source_files=[a.project.resolve(),base/'Binaries/Win64/UnrealEditor-GameDemo.dll',base/'Config/DefaultEngine.ini',base/'Content/Generated/Maps/Demo.umap',base/'Content/Generated/Data/M_Semantic.uasset']
        if (base/'Content/Generated/Data/M_Whitebox.uasset').exists():source_files += [base/'Content/Generated/Data/M_Whitebox.uasset',base/'Content/Generated/Environment/SM_Group_Whitebox.uasset']
        activity=a.activity or ('combat' if a.autoplay else 'idle')
        warmup=a.warmup_frames if a.warmup_frames is not None else 90 if a.calibration or activity=='idle' else 330 if activity=='combat' else 150
        if not 32<=warmup<=36000:raise ValueError('Invalid warmup frame count')
        source_files=sorted(set(source_files+list((base/'Content').rglob('*.uasset'))+list((base/'Content').rglob('*.umap'))))
        settings={'activity':activity,'warmup_frames':warmup,'frames':a.frames,'width':a.width,'height':a.height,'whitebox':a.whitebox,'calibration':a.calibration}
        receipt={'project':str(a.project.resolve()),'camera':a.camera,'calibration':a.calibration,'capture_settings':settings,'files':{str(f.relative_to(base)):hashlib.sha256(f.read_bytes()).hexdigest() for f in source_files},'started_unix':time.time()}
        receipt['rendering_profile']=profile()
        (out/'source.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
        args=[m['unreal_editor'],str(a.project.resolve()),'/Game/Generated/Maps/Demo','-game','-windowed','-ResX='+str(a.width),'-ResY='+str(a.height),'-ForceRes','-NoLiveCoding','-ddc=InstalledNoZenLocalFallback','-unattended','-nosplash','-DatasetCapture','-DatasetOutput='+str(out),'-DatasetWidth='+str(a.width),'-DatasetHeight='+str(a.height),'-DatasetFrames='+str(a.frames),'-PipelineCamera='+a.camera,'-abslog='+str(out/'engine.log')]
        # Set simulation timing before engine/world initialization, not only from an actor tick.
        args+=['-DatasetWarmup='+str(warmup),'-UseFixedTimeStep','-FPS=60','-RenderOffscreen']+launch_args()
        if not a.calibration:
            if activity=='combat':args.append('-GameDemoTest')
            elif activity=='exploration':args.append('-GameDemoExplorationTest')
        if a.calibration:args.append('-DatasetCalibration')
        if a.whitebox:args.append('-DatasetRequireWhitebox')
        start=None
        if os.name=='nt':start=subprocess.STARTUPINFO();start.dwFlags|=subprocess.STARTF_USESHOWWINDOW;start.wShowWindow=0
        start_time=time.monotonic()
        with (out/'process.log').open('w') as log:subprocess.run(args,stdout=log,stderr=subprocess.STDOUT,cwd=a.project.parent,startupinfo=start,check=True,timeout=max(600,a.frames*12))
        receipt['elapsed_wall_seconds']=time.monotonic()-start_time
        (out/'source.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    if a.whitebox and not json.loads((out/'capture_result.json').read_text()).get('whitebox'):
        raise ValueError('Structural whitebox was requested but this project/runtime did not produce it')
    print(json.dumps(process(out,not a.no_videos),indent=2))

if __name__=='__main__':main()
