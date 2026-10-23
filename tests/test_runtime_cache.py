import tempfile,threading,time,unittest
from pathlib import Path
from game_pipeline.runtime_cache import materialize

class RuntimeCacheTests(unittest.TestCase):
    def test_reader_cannot_copy_partially_linked_binaries(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);runtime=root/'runtime';calls=[];errors=[];partial=threading.Event()
            def build():
                calls.append(1);p=runtime/'Binaries/Win64';p.mkdir(parents=True,exist_ok=True)
                (p/'UnrealEditor-GameDemo.dll').write_bytes(b'module');partial.set();time.sleep(.25)
                (p/'UnrealEditor-GameDemo.pdb').write_bytes(b'complete symbols')
            def run(dest):
                try:materialize(runtime,root/dest,build)
                except BaseException as e:errors.append(e)
            a=threading.Thread(target=run,args=('a',));a.start();partial.wait(2)
            b=threading.Thread(target=run,args=('b',));b.start();a.join(5);b.join(5)
            self.assertFalse(errors);self.assertEqual(len(calls),1)
            for dest in ['a','b']:self.assertEqual((root/dest/'Binaries/Win64/UnrealEditor-GameDemo.pdb').read_bytes(),b'complete symbols')

    def test_incomplete_or_corrupt_cache_is_rebuilt(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);runtime=root/'runtime';p=runtime/'Binaries/Win64';p.mkdir(parents=True)
            dll=p/'UnrealEditor-GameDemo.dll';dll.write_bytes(b'incomplete');calls=[]
            def build():calls.append(1);dll.write_bytes(b'complete')
            materialize(runtime,root/'out',build);dll.write_bytes(b'corrupt')
            materialize(runtime,root/'out',build)
            self.assertEqual(len(calls),2);self.assertEqual((root/'out/Binaries/Win64/UnrealEditor-GameDemo.dll').read_bytes(),b'complete')

if __name__=='__main__':unittest.main()
