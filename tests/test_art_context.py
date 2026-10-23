import copy,unittest
from game_pipeline.art_context import resource_intent

class ResourceIntentTests(unittest.TestCase):
 def scene(self):
  return {'floor_material':'soil','path_material':'stone','materials':{'stone':{'texture_set':'rock','tint':[1,1,1]}},'objects':[{'kind':'asset','asset':'rock','position':[0,0,0],'scale':[2,2,2]}],
   'composition':{'destination_details':[{'kind':'timber_hall','center':[0,0],'material':'stone','roof_material':'iron'}], 'exploration':{'routes':[{'surface':'stone','points':[[0,0,0],[5,0,0]]}],'places':[{'name':'workshop','center':[0,0,0]}],'planting_regions':[{'palette':[{'asset':'grass'}],'count':10}]}}}
 def test_position_grounding_and_route_adjustments_reuse_resource_intent(self):
  a=self.scene();b=copy.deepcopy(a)
  b['objects'][0].update(position=[30,20,-.2],scale=[3,2,2],grounding='footprint')
  b['composition']['destination_details'][0]['center']=[20,10]
  b['composition']['exploration']['routes'][0]['points'][1]=[6,1,0]
  b['composition']['exploration']['planting_regions'][0]['count']=30
  self.assertEqual(resource_intent(a),resource_intent(b))
 def test_material_asset_and_destination_function_changes_replan(self):
  a=self.scene()
  for kind in ['material','asset','destination']:
   b=copy.deepcopy(a)
   if kind=='material':b['materials']['stone']['tint']=[.4,.5,.6]
   elif kind=='asset':b['objects'][0]['asset']='timber'
   else:b['composition']['destination_details'][0]['kind']='overlook_terrace'
   self.assertNotEqual(resource_intent(a),resource_intent(b))
 def test_context_cannot_mutate_the_scene(self):
  a=self.scene();before=copy.deepcopy(a);resource_intent(a)['materials']['stone']['tint'][0]=0
  self.assertEqual(a,before)
 def test_production_graph_scopes_new_plans_and_preserves_legacy_contract(self):
  from game_pipeline import workflow
  from game_pipeline.cli import graph
  from game_pipeline.core import ROOT,read_json
  base=read_json(ROOT/'examples/local_assets.spec.json');base['full_playtest']=True;base['review_agent']=True;s=workflow.configure(base, source_policy='provided')
  a=next(n for n in graph(s,{}) if n.name=='art_plan').config
  s['scene']['objects'][0]['position'][0]+=3
  b=next(n for n in graph(s,{}) if n.name=='art_plan').config
  self.assertEqual(a,b)
  s['production'].pop('art_planning_scope')
  legacy=next(n for n in graph(s,{}) if n.name=='art_plan').config
  self.assertIn('objects',legacy['scene'])
