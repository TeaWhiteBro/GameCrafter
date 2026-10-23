"""Capture the latest assembled scene before the full gameplay suite; not a release gate."""
import argparse,json,sqlite3,subprocess,time,shutil
from pathlib import Path
from game_pipeline.core import RunLock,read_json,write_json,StageError
from game_pipeline.rendering import launch_args

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--run-dir',type=Path,required=True)
    parser.add_argument('--machine',type=Path,default=Path(__file__).with_name('machine.local.json'))
    args=parser.parse_args();root=args.run_dir.resolve();machine=read_json(args.machine)
    with RunLock(root/'.run.lock'):
        db=sqlite3.connect(root/'run.sqlite')
        row=db.execute('select result,status,fingerprint from nodes where name="ue_assemble"').fetchone()
        if not row or row[1]!='complete':raise StageError('First run the pipeline through ue_assemble.')
        project=Path(json.loads(row[0])['project']);out=root/'previews'/str(time.time_ns());out.mkdir(parents=True)
        startup=subprocess.STARTUPINFO();startup.dwFlags|=subprocess.STARTF_USESHOWWINDOW;startup.wShowWindow=0
        started=time.time()
        with (out/'process.log').open('w',encoding='utf-8') as log:
            proc=subprocess.Popen([machine['unreal_editor'],str(project),'/Game/Generated/Maps/Demo','-game','-RenderOffscreen',
                '-windowed','-ResX=1600','-ResY=900','-ForceRes','-NoSound','-unattended','-nosplash','-NoLiveCoding',
                '-PipelineExit','-GameDemoArtReview','-ddc=InstalledNoZenLocalFallback','-abslog='+str(out/'engine.log')]+launch_args(),
                startupinfo=startup,stdout=log,stderr=subprocess.STDOUT)
            try:code=proc.wait(timeout=240)
            except BaseException:
                proc.terminate()
                try:proc.wait(timeout=15)
                except subprocess.TimeoutExpired:proc.kill();proc.wait()
                raise
        if code:raise StageError('Preview process failed; inspect '+str(out/'engine.log'))
        shots=sorted((project.parent/'Saved/Screenshots').rglob('*.png'),key=lambda p:p.stat().st_mtime)
        fresh=[p for p in shots if p.stat().st_mtime>=started]
        if len(fresh)!=2:raise StageError('Expected two fresh runtime overview captures.')
        files=[]
        for i,source in enumerate(fresh):
            target=out/f'view_{i}.png';shutil.copy2(source,target);files.append(str(target))
        write_json(out/'preview.json',{'project':str(project),'assembly_fingerprint':row[2],'images':files,'scope':'visual preflight only; full gameplay and final visual review still required'})
        print(out)

if __name__=='__main__':main()
