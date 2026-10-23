import unittest,sys
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'adapters/blender'))
from destination_details import build,validate

class DestinationTests(unittest.TestCase):
 def test_overlook_entry_steps_match_companion_and_end_at_deck(self):
  item={'kind':'overlook_terrace','center':[0,0],'size':[8.4,6.6],'base_z':2.5,'yaw_deg':180,'timber_material':'wood','floor_material':'wood','coursed_plinth':True,'entry_steps':{'steps':5,'rise':.52,'run':3,'width':4.8}}
  captures=[]
  for proxy in [False,True]:
   _,g=self.generate(item,proxy,lambda x,y:2.5-.08*y)
   steps=[v for n,v,f,m in g if n=='Overlook arrival step'];self.assertEqual(len(steps),5)
   tops=[v[:,2].max() for v in steps];self.assertAlmostEqual(tops[-1],2.64);self.assertLess(max(np.diff(tops)),.18)
   self.assertTrue(all(v[:,2].min()<=min(2.5-.08*y for x,y,z in v) for v in steps));captures.append(steps)
  np.testing.assert_allclose(captures[0],captures[1])
 def test_carved_basin_is_closed_without_degenerate_centre_faces(self):
  item={'kind':'garden_basin','center':[3,-4],'radius':.56,'height':.46}
  for proxy in [False,True]:
   _,g=self.generate(item,proxy,lambda x,y:0)
   _,v,fs,_=g[0];edges={}
   for f in fs:
    self.assertEqual(len(set(f)),len(f))
    area=sum(np.linalg.norm(np.cross(v[f[i]]-v[f[0]],v[f[i+1]]-v[f[0]])) for i in range(1,len(f)-1))
    self.assertGreater(area,1e-7)
    for a,b in zip(f,f[1:]+f[:1]):key=tuple(sorted([a,b]));edges[key]=edges.get(key,0)+1
   self.assertTrue(all(n==2 for n in edges.values()))
 def test_dry_garden_companion_omits_rake_but_preserves_footprint(self):
  item={'kind':'dry_garden','center':[0,0],'size':[4.4,5.8],'surface_material':'gravel','yaw_deg':28}
  _,high=self.generate(item,False,lambda x,y:.1*x);_,low=self.generate(item,True,lambda x,y:.1*x)
  self.assertTrue(any(n=='Raked gravel ridge' for n,v,f,m in high))
  self.assertFalse(any(n=='Raked gravel ridge' for n,v,f,m in low))
  for name in ['Dry garden gravel bed','Dry garden stone curb']:
   a=np.concatenate([v for n,v,f,m in high if n==name]);b=np.concatenate([v for n,v,f,m in low if n==name]);np.testing.assert_allclose(a,b)
 def test_hoist_keeps_working_assembly_and_grounded_feet_in_both_representations(self):
  item={'kind':'hoist_station','center':[0,0],'base_z':0,'size':[3.4,2.8],'height':3.5,'timber_material':'wood','metal_material':'iron'}
  for proxy in [False,True]:
   _,g=self.generate(item,proxy,lambda x,y:.25*x-.1*y)
   for name in ['Hoist winding drum','Hoist handwheel','Hoist lifting cable','Hoist casting form','Hoist grounded stone foot']:
    self.assertTrue(any(n==name for n,v,f,m in g))
   for n,v,f,m in g:
    self.assertTrue(np.isfinite(v).all())
    if n=='Hoist grounded stone foot':self.assertLess(v[:,2].min(),min(.25*x-.1*y for x,y,z in v))
   cable=np.concatenate([v for n,v,f,m in g if n=='Hoist lifting cable'])
   form=np.concatenate([v for n,v,f,m in g if n=='Hoist casting form'])
   self.assertLess(cable[:,2].min(),form[:,2].max())
 def test_unpaved_discovery_zone_does_not_have_to_clear_all_vegetation(self):
  from exploration import RouteField
  e={'routes':[{'width':3,'points':[[0,-20,0],[0,20,0]]}],'places':[{'center':[0,0,0],'radius':8,'clear_radius':2.5,'surface':'none','flatten':False}]}
  f=RouteField(e)
  self.assertFalse(f.clear(5,0))
  self.assertTrue(f.clear(1,5))
  e['places'][0].pop('clear_radius');self.assertTrue(RouteField(e).clear(5,0))
 def test_scattering_reserves_building_foundations_beyond_route(self):
  from exploration import RouteField
  f=RouteField({'routes':[{'points':[[0,0,0],[10,0,0]],'width':3}], 'foundation_pads':[{'center':[20,20,0],'radius':8}]})
  self.assertTrue(f.clear(22,23));self.assertFalse(f.clear(35,35))
 def test_workshop_equipment_keeps_structural_mass_and_removes_small_tools(self):
  item={'kind':'workshop_station','center':[0,0],'size':[2.8,1.2],'timber_material':'wood','metal_material':'iron'}
  _,high=self.generate(item);_,low=self.generate(item,True)
  self.assertTrue(any(n=='Anvil tapered horn' for n,v,f,m in low))
  self.assertTrue(any(n=='Hanging hammer head' for n,v,f,m in high))
  self.assertFalse(any(n=='Hanging hammer head' for n,v,f,m in low))
  for n,v,f,m in high+low:
   self.assertTrue(np.isfinite(v).all());self.assertTrue(all(max(face)<len(v) for face in f))
 def test_suspended_bell_is_hollow_in_both_representations(self):
  item={'kind':'bell_rack','center':[0,0],'base_z':0,'size':[3.3,1.6],'height':3.5,'timber_material':'wood','metal_material':'bronze'}
  for proxy in [False,True]:
   _,geometry=self.generate(item,proxy,lambda x,y:0)
   bell=next(v for n,v,f,m in geometry if n=='Suspended hollow bronze casting')
   self.assertGreater(bell[:,2].min(),.5)
   self.assertGreater(np.linalg.norm(bell[:,:2],axis=1).min(),.1)
 def test_wrong_container_returns_actionable_error_instead_of_attribute_crash(self):
  for value in [{'bell_tower':{'center':[0,0]}},['bell_tower']]:
   with self.assertRaisesRegex(ValueError,'destination_details'):validate(value)
 def test_bell_load_path_reaches_yoke_axle_and_posts(self):
  item={'kind':'bell_rack','center':[0,0],'base_z':0,'size':[3.3,1.6],'height':3.5,'timber_material':'wood','metal_material':'bronze'}
  for proxy in [False,True]:
   _,g=self.generate(item,proxy,lambda x,y:0)
   get=lambda name:np.concatenate([v for n,v,f,m in g if n==name])
   bell=get('Suspended hollow bronze casting');hanger=get('Bell crown hanger');axle=get('Bell rack through axle');posts=get('Bell rack timber upright')
   self.assertLess(hanger[:,2].min(),bell[:,2].max())
   self.assertGreater(hanger[:,2].max(),axle[:,2].min())
   self.assertGreater(axle[:,0].max(),posts[:,0].max()-.28)
 def test_terrace_treads_reach_ground_on_a_sloped_approach(self):
  height=lambda x,y:.7*y-.4*x
  item={'kind':'terraced_foundation','center':[0,0],'size':[8,4],'rise':.75,'base_z':2}
  for proxy in [False,True]:
   _,g=self.generate(item,proxy,height)
   for n,v,f,m in g:
    if n=='Gallery ascending tread':
     self.assertLess(v[:,2].min(),min(height(x,y) for x,y,z in v))
 def test_wide_belfry_cannot_generate_negative_arch_spring_height(self):
  with self.assertRaisesRegex(ValueError,'width'):validate([{'kind':'bell_tower','center':[0,0],'width':11,'height':18,'roof_material':'metal'}])
 def test_hearth_has_paired_open_front_and_grounded_flue(self):
  item={'kind':'forge_hearth','center':[0,0],'base_z':0,'size':[3.5,3],'height':6,'material':'brick','metal_material':'iron'}
  detail,g=self.generate(item,False,lambda x,y:0);coarse,p=self.generate(item,True,lambda x,y:0)
  self.assertTrue(any(n=='Hearth tapered smoke hood' for n,v,f,m in p))
  self.assertFalse(any(n=='Hearth grate bar' for n,v,f,m in p))
  self.assertAlmostEqual(min(v[:,2].min() for n,v,f,m in p),-.18)
  # No solid face spans the mouth center at torso height on its front plane.
  for n,v,f,m in p:
   if v[:,1].min()<=-1.5<=v[:,1].max() and v[:,2].min()<1<v[:,2].max():
    self.assertGreater(min(abs(v[:,0])),.5)
 def generate(self,item,proxy=False,height=lambda x,y:.3*x+.1*y):
  geometry=[]
  def mesh(name,vs,fs,mat,**kw):geometry.append((name,np.array(vs),fs,mat))
  result=build({'cfg':{'destination_details':[item]},'spec':{'path_material':'stone'},'height':height,'mesh':mesh},proxy)
  return result,geometry
 def test_bed_is_embedded_on_slope_and_companion_encloses_soil(self):
  item={'kind':'herb_bed','center':[0,0],'size':[3.4,1.4],'soil_material':'soil','plant_asset':'herb'}
  result,g=self.generate(item);_,proxy=self.generate(item,True)
  soil=next(v for n,v,f,m in g if n=='Cultivated soil')
  self.assertTrue(result['plantings'])
  self.assertAlmostEqual(min(v[:,2].min() for n,v,f,m in proxy),-.3*1.7-.1*.7-.10)
  self.assertTrue(all(p['position'][2]<=soil[:,2].max()+.001 for p in result['plantings']))
 def test_gallery_has_several_ascending_treads(self):
  _,g=self.generate({'kind':'terraced_foundation','center':[0,0],'size':[8,4],'rise':.75,'base_z':0},True,lambda x,y:0)
  tops=[v[:,2].max() for n,v,f,m in g if n=='Gallery ascending tread']
  self.assertEqual(len(tops),5);self.assertEqual(tops,sorted(set(tops)));self.assertAlmostEqual(tops[-1],.75)
 def test_roof_slopes_are_closed_volumes_in_both_representations(self):
  item={'kind':'belvedere','center':[0,0],'timber_material':'wood','roof_material':'metal'}
  for proxy in [False,True]:
   _,g=self.generate(item,proxy)
   roofs=[(v,f) for n,v,f,m in g if 'continuous slope' in n]
   self.assertEqual(len(roofs),2)
   for v,f in roofs:
    edges={}
    for face in f:
     for a,b in zip(face,face[1:]+face[:1]):
      key=tuple(sorted((a,b)));edges[key]=edges.get(key,0)+1
    self.assertEqual(set(edges.values()),{2})
 def test_open_terrace_preserves_open_arrival_and_structural_parapets(self):
  item={'kind':'overlook_terrace','center':[0,0],'base_z':0,'size':[6,4],'timber_material':'wood'}
  for proxy in [False,True]:
   _,g=self.generate(item,proxy,lambda x,y:0)
   self.assertFalse(any('roof' in n.lower() for n,v,f,m in g))
   self.assertTrue(any(n=='Overlook continuous plinth' for n,v,f,m in g))
   for n,v,f,m in g:
    if v[:,2].max()>.4 and v[:,1].min()<=-2<=v[:,1].max():self.assertGreater(abs(v[:,0]).min(),2.7)
 def test_invalid_inputs_fail_before_emitting_partial_geometry(self):
  for item in [{'kind':'unknown','center':[0,0]}, {'kind':'vault_liner','center':[0,0],'radius':-1,'rise':2}, {'kind':'bell_tower','center':[0,0],'height':1,'roof_material':'metal'}]:
   with self.assertRaises(ValueError):self.generate(item)
 def test_proxy_removes_brick_and_plant_detail_but_keeps_bell(self):
  item={'kind':'bell_tower','center':[0,0],'roof_material':'metal'}
  _,high=self.generate(item);_,low=self.generate(item,True)
  self.assertLess(sum(len(f) for n,v,f,m in low),sum(len(f) for n,v,f,m in high)*.5)
  self.assertTrue(any(n=='Cast bell' for n,v,f,m in low))
 def test_missing_destination_scan_fails_resource_contract(self):
  from game_pipeline.contracts import validate_scene_resources,ContractError
  scene={'materials':{'soil':{}},'objects':[],'composition':{'destination_details':[{'kind':'herb_bed','center':[0,0],'soil_material':'soil','plant_asset':'missing'}]}}
  with self.assertRaisesRegex(ContractError,'planting'):validate_scene_resources(scene,{})
 def test_optional_deck_and_bell_materials_require_real_bindings(self):
  from game_pipeline.contracts import validate_scene_resources,ContractError
  for key in ['floor_material','bell_material']:
   scene={'materials':{'stone':{}},'objects':[],'composition':{'destination_details':[{'kind':'bell_tower','center':[0,0],'roof_material':'stone',key:'missing'}]}}
   with self.assertRaisesRegex(ContractError,'Unknown destination material'):validate_scene_resources(scene,{})
 def test_timber_hall_keeps_open_ends_and_paired_roof_envelope(self):
  item={'kind':'timber_hall','center':[0,0],'base_z':0,'size':[8,12],'height':4.5,'bays':4,'timber_material':'wood','roof_material':'roof'}
  _,detail=self.generate(item,False,lambda x,y:0);_,coarse=self.generate(item,True,lambda x,y:0)
  for name in ['Hall continuous pitched roof continuous slope','Hall continuous foundation','Hall timber post','Hall masonry side infill']:
   a=[v for n,v,f,m in detail if n==name];b=[v for n,v,f,m in coarse if n==name]
   self.assertTrue(a and b)
   # Structural infill encloses the detailed 5/6 mm mortar gaps.
   tolerance=.007 if name=='Hall masonry side infill' else 1e-6
   self.assertTrue(np.allclose(np.concatenate(a).min(axis=0),np.concatenate(b).min(axis=0),atol=tolerance))
   self.assertTrue(np.allclose(np.concatenate(a).max(axis=0),np.concatenate(b).max(axis=0),atol=tolerance))
  # At body height, the long-axis center corridor contains no solid support.
  for n,v,f,m in coarse:
   if v[:,2].max()>.5 and v[:,2].min()<2:
    self.assertGreater(np.abs(v[:,0]).min(),3)
  self.assertTrue(any('roof truss' in n for n,v,f,m in detail))
  self.assertFalse(any('roof truss' in n for n,v,f,m in coarse))
 def test_workshop_deck_covers_room_corners_with_planar_unsmoothed_boards(self):
  item={'kind':'timber_hall','center':[0,0],'base_z':0,'size':[10,16],'height':5.2,'bays':4,'timber_material':'wood','roof_material':'roof','floor_material':'floor','yaw_deg':-28}
  emitted=[]
  def mesh(name,vs,fs,mat,**kw):emitted.append((name,np.array(vs),fs,kw))
  build({'cfg':{'destination_details':[item]},'spec':{'path_material':'stone'},'height':lambda x,y:0,'mesh':mesh})
  boards=[(v,fs,kw) for n,v,fs,kw in emitted if n=='Hall floor board']
  self.assertGreater(len(boards),30)
  a=np.deg2rad(-28);rotation=np.array([[np.cos(a),-np.sin(a)],[np.sin(a),np.cos(a)]])
  local=[v[:,:2]@rotation for v,fs,kw in boards]
  for x in [-4.82,4.82]:
   for y in [-8.14,8.14]:
    self.assertTrue(any(np.all(p.min(0)<[x,y]) and np.all(p.max(0)>[x,y]) for p in local),'The floor must cover rectangular corners, not leave a masonry chamfer wedge')
  for v,fs,kw in boards:
   self.assertFalse(kw['smooth_faces'])
   self.assertAlmostEqual(np.ptp(v[4:,2]),0)
   self.assertLessEqual(v[:,2].min(),.08)
  _,proxy=self.generate(item,True,lambda x,y:0)
  envelope=next(v for n,v,f,m in proxy if n=='Hall floor envelope')
  self.assertAlmostEqual(envelope[:,2].max(),max(v[:,2].max() for v,fs,kw in boards))
 def test_tower_bell_fills_aperture_and_attaches_to_supported_yoke(self):
  item={'kind':'bell_tower','center':[0,0],'base_z':0,'width':4.4,'height':11,'roof_material':'roof','bell_material':'bronze'}
  for proxy in [False,True]:
   _,g=self.generate(item,proxy,lambda x,y:0)
   get=lambda name:np.concatenate([v for n,v,f,m in g if n==name])
   bell=get('Cast bell');hanger=get('Bell crown hanger');yoke=get('Bell suspension')
   self.assertGreater(np.ptp(bell[:,0]),2.3)
   self.assertEqual(next(m for n,v,f,m in g if n=='Cast bell'),'bronze')
   self.assertGreater(np.linalg.norm(bell[:,:2],axis=1).min(),.05)
   self.assertLess(hanger[:,2].min(),bell[:,2].max())
   self.assertGreater(hanger[:,2].max(),yoke[:,2].min())
   self.assertGreater(yoke[:,1].max(),2.2)
