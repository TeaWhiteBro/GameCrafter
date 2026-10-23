# Exact stage dependencies

Generated from `workflow_graph.json`. Solid edges are declared production dependencies. Dashed bootstrap edges supply the run specification and are not production-DAG edges.

```mermaid
flowchart TD
  design["Brief → GameSpec<br/>agent.design"]
  concept["Concept image<br/>image.gpt_image"]
  asset_demands["Asset allocation<br/>agent.environment_demands"]
  surface_assets["Public PBR sources<br/>resources.public_surfaces"]
  environment_assets["Environment sources<br/>environment.generate"]
  art_plan["Art direction<br/>agent.art_plan"]
  scene_layout["Scene layout<br/>agent.scene_layout"]
  exploration_plan["Exploration network<br/>agent.exploration_plan"]
  mesh_player["Player source<br/>mesh.source"]
  rig_player["Player rig + QA<br/>blender.rig"]
  mesh_boss["Boss source<br/>mesh.source"]
  rig_boss["Boss rig + QA<br/>blender.rig"]
  scene["Detailed + structural scene<br/>blender.scene"]
  ue_project["Isolated UE project<br/>ue.project"]
  animations["Motion retargeting<br/>ue.animation"]
  ue_assemble["Rendering + gameplay<br/>ue.assemble"]
  scene_preflight["Current-view preflight<br/>ue.scene_preflight"]
  capture_probe["Early all-condition coverage<br/>ue.capture_probe"]
  playtest["Gameplay regression<br/>ue.playtest"]
  camera_validation["Camera switching<br/>ue.camera_validation"]
  capture_plan["Condition plan<br/>agent.capture_plan"]
  calibration["Independent calibration<br/>ue.calibration"]
  dataset["Five-channel capture<br/>ue.dataset_paired"]
  pair_validation["Native/export validation<br/>dataset.validate_pairs"]
  review["Final visual review<br/>agent.review"]
  delivery["Accepted release<br/>release.playable"]
  design -. GameSpec .-> concept
  concept --> asset_demands
  asset_demands --> surface_assets
  asset_demands --> environment_assets
  surface_assets --> environment_assets
  concept --> art_plan
  environment_assets --> art_plan
  concept --> scene_layout
  art_plan --> scene_layout
  scene_layout --> exploration_plan
  concept --> exploration_plan
  art_plan --> exploration_plan
  design -. GameSpec .-> mesh_player
  mesh_player --> rig_player
  design -. GameSpec .-> mesh_boss
  mesh_boss --> rig_boss
  exploration_plan --> scene
  design -. GameSpec .-> ue_project
  ue_project --> animations
  rig_player --> animations
  rig_boss --> animations
  ue_project --> ue_assemble
  animations --> ue_assemble
  scene --> ue_assemble
  ue_assemble --> scene_preflight
  scene --> scene_preflight
  concept --> scene_preflight
  ue_assemble --> capture_probe
  scene_preflight --> capture_probe
  ue_assemble --> playtest
  scene_preflight --> playtest
  capture_probe --> playtest
  ue_assemble --> camera_validation
  playtest --> camera_validation
  ue_assemble --> capture_plan
  playtest --> capture_plan
  camera_validation --> capture_plan
  ue_assemble --> calibration
  capture_plan --> calibration
  ue_assemble --> dataset
  capture_plan --> dataset
  calibration --> dataset
  capture_probe --> dataset
  ue_assemble --> pair_validation
  capture_plan --> pair_validation
  calibration --> pair_validation
  dataset --> pair_validation
  playtest --> review
  concept --> review
  scene --> review
  rig_player --> review
  rig_boss --> review
  camera_validation --> review
  pair_validation --> review
  scene_preflight --> review
  art_plan --> review
  exploration_plan --> review
  review --> delivery
  playtest --> delivery
  dataset --> delivery
  scene_preflight --> delivery
  camera_validation --> delivery
  capture_plan --> delivery
  calibration --> delivery
  pair_validation --> delivery
  capture_probe --> delivery
  art_plan --> delivery
  exploration_plan --> delivery
  surface_assets --> delivery
  asset_demands --> delivery
  environment_assets --> delivery
```

Prerequisite machine checks and executing-agent replay / launch observation are outside this DAG.
