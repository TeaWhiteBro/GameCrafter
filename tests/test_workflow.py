import copy,json,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from game_pipeline import workflow
from game_pipeline.rendering import profile
from game_pipeline.core import StageError,read_json,write_json,digest,ROOT
from game_pipeline.cli import graph,REGISTRY
from game_pipeline.camera_validation import validate_report
from game_pipeline.production_capture import capture_plan,committed,validate_sequence,validate_combat_visibility,validate_combat_contact
from game_pipeline.dataset import whitebox_tone,annotate,project
import numpy as np
from PIL import Image

class WorkflowTests(unittest.TestCase):
    def test_original_brief_reaches_both_reviews_without_replacing_gates(self):
        base=read_json(ROOT/'examples/local_assets.spec.json');base['full_playtest']=True;base['review_agent']=True
        base['prompt']='All gameplay is inside dry rooms; the ocean outside is an observation backdrop.'
        spec=workflow.configure(base,source_policy='provided')
        nodes={n.name:n for n in graph(spec,{})}
        for stage in ['scene_preflight','review']:
            self.assertEqual(nodes[stage].config['original_user_brief'],base['prompt'])
        self.assertIn('scene_preflight',nodes['playtest'].deps)
        self.assertIn('pair_validation',nodes['review'].deps)
        self.assertTrue(nodes['review'].config['visual_agent'])
    def test_practical_benchmarks_reach_early_and_final_reviews(self):
        base=read_json(ROOT/'examples/local_assets.spec.json');base['full_playtest']=True;base['review_agent']=True
        spec=workflow.configure(base, source_policy='provided')
        spec['quality_benchmarks']=['accepted_overview.png','accepted_route.png']
        nodes={n.name:n for n in graph(spec,{})}
        for stage in ['scene_preflight','review']:
            self.assertEqual(nodes[stage].config['quality_benchmarks'],spec['quality_benchmarks'])
            self.assertEqual(nodes[stage].config['_source_files'],spec['quality_benchmarks'])
    def test_world_profile_requires_all_data_views_and_roaming(self):
        spec=workflow.configure({})
        self.assertEqual(spec['dataset']['activities'],['combat','exploration'])
        for key,value in [('whitebox',False),('cameras',['third']),('channels',['rgb','depth']),('autoplay',False)]:
            bad=copy.deepcopy(spec);bad['dataset'][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):workflow.validate(bad)
    def test_existing_spec_is_not_silently_migrated(self):
        spec={'scene':{}};self.assertIsNone(workflow.validate(spec));self.assertNotIn('dataset',spec)
    def test_profiles_are_independent_and_support_arena(self):
        a=workflow.configure({},'arena_demo',96);b=workflow.configure({})
        a['dataset']['channels'].pop();self.assertEqual(len(b['dataset']['channels']),5)
        self.assertEqual(a['dataset']['activities'],['combat'])
    def test_bad_frame_count_and_duplicate_camera_rejected(self):
        for value in [True,0,59,1201,90.5]:
            with self.subTest(value=value),self.assertRaises(ValueError):workflow.configure({},frames=value)
        spec=workflow.configure({});spec['dataset']['cameras']=['first','third','third','isometric']
        with self.assertRaises(ValueError):workflow.validate(spec)
    def test_graph_cannot_release_before_all_gates(self):
        base=read_json(ROOT/'examples/local_assets.spec.json');base['full_playtest']=True;base['review_agent']=True
        spec=workflow.configure(base,frames=96,source_policy='provided')
        nodes=graph(spec,{});names=[n.name for n in nodes];seen=set()
        for node in nodes:
            self.assertIn(node.adapter,REGISTRY);self.assertTrue(set(node.deps)<=seen);seen.add(node.name)
        self.assertEqual(len(names),len(set(names)))
        self.assertLess(names.index('exploration_plan'),names.index('mesh_player'))
        self.assertLess(names.index('scene_preflight'),names.index('playtest'))
        self.assertIn('scene_preflight',next(n for n in nodes if n.name=='playtest').deps)
        release=next(n for n in nodes if n.name=='delivery')
        self.assertTrue({'camera_validation','calibration','pair_validation','dataset','exploration_plan','art_plan'}<=set(release.deps))
        self.assertEqual(next(n for n in nodes if n.name=='scene').deps,['exploration_plan'])
    def camera_sample(self):
        modes=['first']*4+['third']*4+['isometric']*4+['third']*4
        return {'passed':True,'returned_to_third':True,'switch_displacement_cm':0,
                'probe_space_validated':True,'probe_queries':140,
          'cases':[{'case':i,'camera':m,'passed':True,'samples':50,'travel_cm':200,'max_input_error_deg':1,
            'max_world_step_cm':5,'owner_visibility_correct':True,'projection_correct':True,'player_framed':True,'mesh_scale_valid':True} for i,m in enumerate(modes)]}
    def test_camera_switch_requires_real_motion_and_restored_visibility(self):
        validate_report(self.camera_sample())
        for key,value in [('samples',0),('travel_cm',0),('owner_visibility_correct',False),('max_input_error_deg',90),('max_world_step_cm',120)]:
            data=self.camera_sample();data['cases'][12][key]=value
            with self.subTest(key=key),self.assertRaises(StageError):validate_report(data)
    def test_camera_suite_cannot_skip_return_leg(self):
        data=self.camera_sample();data['cases']=data['cases'][:12]
        with self.assertRaises(StageError):validate_report(data)
    def test_camera_suite_requires_collision_validated_probe_space(self):
        for key,value in [('probe_space_validated',False),('probe_queries',0)]:
            data=self.camera_sample();data[key]=value
            with self.assertRaisesRegex(StageError,'probe space'):validate_report(data)
    def test_raw_commit_rejects_changed_scene_asset(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);base=root/'project';base.mkdir();p=base/'a.uproject';p.write_text('{}');asset=base/'mesh.uasset';asset.write_bytes(b'v1')
            out=root/'out';out.mkdir();write_json(out/'source.json',{'project':str(p.resolve()),'rendering_profile':profile(),'files':{'mesh.uasset':digest(asset)}})
            write_json(out/'commit.json',{'job':{'camera':'third'},'files':{'source.json':digest(out/'source.json')}})
            self.assertTrue(committed(out,str(p),{'camera':'third'}));asset.write_bytes(b'v2')
            self.assertFalse(committed(out,str(p),{'camera':'third'}))

class PairedExportTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.project=self.root/'game.uproject';self.project.write_text('{}');self.out=self.root/'sequence';self.out.mkdir()
        self.job={'key':'combat_third','camera':'third','activity':'combat','frames':3,'width':64,'height':64,'whitebox':True,'warmup_frames':330,'calibration':False}
        settings={k:v for k,v in self.job.items() if k not in ['key','camera']}
        write_json(self.out/'source.json',{'project':str(self.project.resolve()),'camera':'third','capture_settings':settings,'rendering_profile':profile(),'files':{self.project.name:digest(self.project)}})
        write_json(self.out/'validation.json',{'passed':True,'export_complete':True,'lossless_semantic_video_roundtrip':True})
        write_json(self.out/'dataset.json',{'whitebox':True})
        for n in ['raw','rgb','depth','semantic_ids','skeleton','joints','whitebox']:(self.out/n).mkdir()
        records=[];matrix=np.diag([.003,.003,.003,1]).reshape(-1).tolist()
        for f in range(3):
            stem=f'{f:06d}';bones=[{'name':str(i),'world_cm':[i*2.+f*.2,0.,100.],'parent':i-1,'in_front':True,'camera_z_m':1.} for i in range(12)]
            for bone,pixel in zip(bones,project([b['world_cm'] for b in bones],matrix,64,64)):bone['pixel_xy']=pixel.tolist()
            meta={'frame_id':f,'simulation_step':f+330,'time_seconds':5.5+f/60,'camera_mode':'third','width':64,'height':64,'camera_world_cm':[0,0,0],
                  'world_to_clip':matrix,'projection':matrix,'actors':[{'role':'boss','class_id':11,'action':'move','health':780-f,'position_cm':[0,0,100],'camera_hidden':False,'bones':bones},
                  {'role':'player','class_id':10,'action':'light1','health':120,'position_cm':[0,100,100],'camera_hidden':False,'bones':copy.deepcopy(bones)}]}
            caps=[{'role':'boss','from_bone':str(i),'to_bone':str(i+1),'a_cm':bones[i]['world_cm'],'b_cm':bones[i+1]['world_cm'],'radius_cm':2.,'head_extension':False} for i in range(11)]
            caps += [{**copy.deepcopy(c),'role':'player'} for c in caps]
            meta['whitebox']={'simulation_step':f+330,'world_to_clip':matrix,'capsules':caps}
            rgb=np.full((64,64,3),80+f,np.uint8);depth=np.full((64,64),3,np.float32);ids=np.full((64,64),11,np.uint8)
            ids[24:40,24:32]=10
            white=np.full((64,64,3),180,np.uint8);white[:20]=130
            for arr,ext in [(rgb,'.bgra'),(white,'.whitebox.bgra')]:
                np.dstack([arr[:,:,::-1],np.full((64,64),255,np.uint8)]).tofile(self.out/'raw'/(stem+ext))
            depth.tofile(self.out/'raw'/(stem+'.depth'));ids.tofile(self.out/'raw'/(stem+'.ids'));write_json(self.out/'raw'/(stem+'.json'),meta)
            Image.fromarray(rgb).save(self.out/'rgb'/(stem+'.png'));np.save(self.out/'depth'/(stem+'.npy'),depth)
            Image.fromarray(ids).save(self.out/'semantic_ids'/(stem+'.png'));Image.fromarray(whitebox_tone(white)).save(self.out/'whitebox'/(stem+'.png'))
            skeleton,_=annotate(meta,depth,ids);skeleton.save(self.out/'skeleton'/(stem+'.png'));write_json(self.out/'joints'/(stem+'.json'),meta)
            records.append({'frame_id':f,'time_seconds':meta['time_seconds'],'camera_mode':'third','rgb':'rgb/'+stem+'.png','depth':'depth/'+stem+'.npy','semantics':'semantic_ids/'+stem+'.png','skeleton':'skeleton/'+stem+'.png','metadata':'joints/'+stem+'.json','whitebox':'whitebox/'+stem+'.png'})
        (self.out/'frames.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in records))
        for n in ['rgb.mp4','depth_preview.mp4','semantic_preview.mp4','skeleton.mp4','skeleton_overlay.mp4','semantic_ids_lossless.mkv','whitebox.mp4','whitebox_pair.mp4']:(self.out/n).write_bytes(b'fixture_export_presence'*8)
    def check(self):return validate_sequence(self.out,self.job,str(self.project))
    def test_paired_native_exports_pass(self):self.assertTrue(self.check()['passed'])
    def test_moving_bones_behind_camera_cannot_pass_combat_capture(self):
        for f in range(3):
            stem=f'{f:06d}';ids=np.full((64,64),3,np.uint8)
            ids.tofile(self.out/'raw'/(stem+'.ids'))
            Image.fromarray(ids).save(self.out/'semantic_ids'/(stem+'.png'))
            meta=read_json(self.out/'raw'/(stem+'.json'))
            depth=np.fromfile(self.out/'raw'/(stem+'.depth'),np.float32).reshape(64,64)
            skeleton,_=annotate(meta,depth,ids);skeleton.save(self.out/'skeleton'/(stem+'.png'))
            write_json(self.out/'joints'/(stem+'.json'),meta)
        with self.assertRaisesRegex(StageError,'Combat subject'):self.check()
    def test_brief_combat_occlusion_is_allowed_but_long_absence_rejected(self):
        self.assertEqual(validate_combat_visibility([100]*8+[0]*2,4096)['boss_visible_frames'],8)
        for counts in [[],[100]*7+[0]*3,[1]*10,[0]*4+[100]*16]:
            with self.subTest(counts=counts),self.assertRaisesRegex(StageError,'Combat subject'):
                validate_combat_visibility(counts,4096)
    def test_empty_air_swings_fail_even_when_both_actors_are_visible(self):
        samples=[[{'role':'player','position_cm':[0,0,0],'action':'light1','health':120},
                  {'role':'boss','position_cm':[0,100,0],'action':'light2','health':780}] for _ in range(60)]
        with self.assertRaisesRegex(StageError,'actual contact'):validate_combat_contact(samples)
        hit=copy.deepcopy(samples);hit[-1][1]['health']=750
        self.assertEqual(validate_combat_contact(hit)['impact_frames']['boss'],1)
        far=copy.deepcopy(hit)
        for frame in far:frame[1]['position_cm']=[0,1000,0]
        with self.assertRaisesRegex(StageError,'actual contact'):validate_combat_contact(far)
    def test_player_occlusion_is_checked_separately_from_visible_boss(self):
        self.assertEqual(validate_combat_visibility([100]*10,4096,'player')['player_visible_frames'],10)
        self.assertEqual(validate_combat_visibility([100]*10,4096)['boss_visible_frames'],10)
        with self.assertRaisesRegex(StageError,'Combat subject'):
            validate_combat_visibility([1]*10,4096,'player')
    def test_actual_hit_reaction_counts_when_health_is_clamped(self):
        sample=[{'role':'player','position_cm':[0,0,0],'action':'hit','health':70},
                {'role':'boss','position_cm':[0,100,0],'action':'light1','health':250}]
        self.assertEqual(validate_combat_contact([sample])['impact_frames']['player'],1)
        sample[0]['position_cm'][0]=float('nan')
        with self.assertRaisesRegex(StageError,'finite combat'):validate_combat_contact([sample])
    def test_rendering_change_rejects_old_capture_even_when_content_matches(self):
        p=self.out/'source.json';source=read_json(p);source['rendering_profile']['version']=-1;write_json(p,source)
        with self.assertRaisesRegex(StageError,'rendering profile'):self.check()
    def test_committed_capture_requires_current_rendering_profile(self):
        p=self.out/'source.json';source=read_json(p);source.pop('rendering_profile');write_json(p,source)
        write_json(self.out/'commit.json',{'job':self.job,'files':{'source.json':digest(p)}})
        self.assertFalse(committed(self.out,str(self.project),self.job))
    def test_missing_whitebox_frame_fails(self):
        (self.out/'whitebox/000001.png').unlink()
        with self.assertRaisesRegex(StageError,'missing or extra'):self.check()
    def test_shifted_rgb_or_ids_fail_against_native(self):
        p=self.out/'semantic_ids/000001.png';im=np.asarray(Image.open(p)).copy();im[0,0]=10;Image.fromarray(im).save(p)
        with self.assertRaisesRegex(StageError,'Semantic ID'):self.check()
    def test_wrong_depth_unit_fails(self):
        p=self.out/'depth/000001.npy';np.save(p,np.load(p)*100)
        with self.assertRaisesRegex(StageError,'Metric depth'):self.check()
    def test_previous_pose_cannot_masquerade_as_current_skeleton(self):
        p=self.out/'joints/000001.json';m=read_json(p);m['actors'][0]['bones'][0]['world_cm'][0]+=5;write_json(p,m)
        with self.assertRaisesRegex(StageError,'stale or altered'):self.check()
    def test_missing_viewing_video_blocks_completion(self):
        (self.out/'whitebox.mp4').unlink()
        with self.assertRaisesRegex(StageError,'Missing requested video'):self.check()
    def test_different_activity_cannot_reuse_capture(self):
        self.job['activity']='exploration'
        with self.assertRaisesRegex(StageError,'scenario/settings'):self.check()

if __name__=='__main__':unittest.main()
