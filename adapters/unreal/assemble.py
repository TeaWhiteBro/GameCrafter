"""UE integration jobs: character animation, then scene/render/gameplay assembly."""
import unreal as u
import json, os, traceback, math, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import surfaces
import semantics
job=json.loads(Path(os.environ['GAME_PIPELINE_JOB']).read_text(encoding='utf-8'))
out=Path(job['out']);out.mkdir(parents=True,exist_ok=True)
report={'ok':False,'warnings':[],'static_import_contract':job.get('static_import_contract'),'reused_static_indices':list(job.get('reused_static',{}))};AT=u.AssetToolsHelpers.get_asset_tools();ML=u.MaterialEditingLibrary
EA=u.get_editor_subsystem(u.EditorActorSubsystem);LE=u.get_editor_subsystem(u.LevelEditorSubsystem)
BASE='/Game/Generated'

def save(o):u.EditorAssetLibrary.save_loaded_asset(o,False)
def prop(o,key,val):
    try:o.set_editor_property(key,val)
    except Exception as e:report['warnings'].append(key+': '+str(e))
def create(name,path,cls,factory):return u.load_asset(path+'/'+name) or AT.create_asset(name,path,cls,factory)
def tex(path,name,normal=False,linear=False,flip=False):
    dest=BASE+'/Textures';task=u.AssetImportTask();task.filename=path;task.destination_path=dest;task.destination_name=name;task.automated=True;task.replace_existing=True;task.save=True
    AT.import_asset_tasks([task]);asset=u.load_asset(dest+'/'+name)
    if not asset:raise RuntimeError('Texture import failed: '+name)
    if normal:asset.set_editor_property('compression_settings',u.TextureCompressionSettings.TC_NORMALMAP);asset.set_editor_property('flip_green_channel',flip)
    asset.set_editor_property('srgb',not (normal or linear))
    save(asset);return asset
def node(mat,cls,**props):
    n=ML.create_material_expression(mat,cls,0,0)
    for k,v in props.items():n.set_editor_property(k,v)
    return n
def output(n,channel,p):
    if not ML.connect_material_property(n,channel,p):raise RuntimeError('Material output connection failed')
def wire(a,channel,b,socket):
    if ML.connect_material_expressions(a,channel,b,socket):return
    if socket in ['Input','VectorInput','Coordinates','UVs'] and ML.connect_material_expressions(a,channel,b,''):return
    raise RuntimeError('Material node connection failed: '+socket+'; available='+str(ML.get_material_expression_input_names(b)))
def material(name,data,world=False,skeletal=False):
    if data.get('surface'):return surfaces.build(name,data,globals(),job.get('texture_library',{}))
    mat=create(name,BASE+'/Materials',u.Material,u.MaterialFactoryNew());ML.delete_all_material_expressions(mat)
    if skeletal:prop(mat,'used_with_skeletal_mesh',True)
    outputs={'base':u.MaterialProperty.MP_BASE_COLOR,'normal':u.MaterialProperty.MP_NORMAL,'roughness':u.MaterialProperty.MP_ROUGHNESS}
    textures=data.get('textures',{})
    if 'base' not in textures:output(node(mat,u.MaterialExpressionConstant3Vector,constant=u.LinearColor(*data.get('color',[.3,.3,.3]),1)),'',u.MaterialProperty.MP_BASE_COLOR)
    if 'roughness' not in textures and 'orm' not in textures:output(node(mat,u.MaterialExpressionConstant,r=data.get('roughness',.7)),'',u.MaterialProperty.MP_ROUGHNESS)
    if 'orm' not in textures:output(node(mat,u.MaterialExpressionConstant,r=data.get('metallic',0)),'',u.MaterialProperty.MP_METALLIC)
    if data.get('emissive_color'):
        output(node(mat,u.MaterialExpressionConstant3Vector,constant=u.LinearColor(*[v*data.get('emissive_strength',1) for v in data['emissive_color']],1)),'',u.MaterialProperty.MP_EMISSIVE_COLOR)
    for kind,path in textures.items():
        texture=tex(path,'T_'+name+'_'+kind,normal=kind=='normal',linear=kind in ['orm','roughness'],flip=skeletal and kind=='normal')
        if world:
            obj=node(mat,u.MaterialExpressionTextureObject,texture=texture)
            sm=node(mat,u.MaterialExpressionMaterialFunctionCall)
            func='WorldAlignedNormal' if kind=='normal' else 'WorldAlignedTexture'
            sm.set_material_function(u.load_asset('/Engine/Functions/Engine_MaterialFunctions01/Texturing/'+func))
            wire(obj,'',sm,'TextureObject');size=node(mat,u.MaterialExpressionConstant3Vector,constant=u.LinearColor(260,260,260,1));wire(size,'',sm,'TextureSize');channel='XYZ Texture'
        else:
            sm=node(mat,u.MaterialExpressionTextureSample,texture=texture)
            sm.set_editor_property('sampler_type',u.MaterialSamplerType.SAMPLERTYPE_NORMAL if kind=='normal' else u.MaterialSamplerType.SAMPLERTYPE_LINEAR_COLOR if kind in ['orm','roughness'] else u.MaterialSamplerType.SAMPLERTYPE_COLOR);channel='RGB'
        if kind=='orm':output(sm,'G',u.MaterialProperty.MP_ROUGHNESS);output(sm,'B',u.MaterialProperty.MP_METALLIC)
        elif kind in outputs:output(sm,channel,outputs[kind])
    ML.recompile_material(mat);save(mat);return mat

def skeletal(role,data):
    from material_slots import material_index
    dest=BASE+'/Characters/'+role;opt=u.FbxImportUI();opt.automated_import_should_detect_type=False
    opt.import_mesh=True;opt.import_as_skeletal=True;opt.import_animations=False;opt.import_materials=False;opt.import_textures=False;opt.create_physics_asset=False
    opt.mesh_type_to_import=u.FBXImportType.FBXIT_SKELETAL_MESH
    task=u.AssetImportTask();task.filename=data['fbx'];task.destination_path=dest;task.destination_name='SK_'+role;task.automated=True;task.replace_existing=True;task.save=True;task.options=opt;task.factory=u.FbxFactory()
    AT.import_asset_tasks([task]);mesh=next((o for o in task.get_objects() if isinstance(o,u.SkeletalMesh)),None)
    if not mesh or not mesh.get_editor_property('skeleton'):raise RuntimeError('Skeletal import failed: '+role)
    mats=[material('M_'+role+'_'+str(i),m,skeletal=True) for i,m in enumerate(data['materials'])]
    slots=mesh.get_editor_property('materials')
    bindings=[]
    for i,slot in enumerate(slots):
        imported=slot.get_editor_property('imported_material_slot_name');name=slot.get_editor_property('material_slot_name')
        index=material_index(imported,name,data['materials'])
        slot.set_editor_property('material_interface',mats[index]);slots[i]=slot
        bindings.append({'slot':i,'imported_name':str(imported),'source_material':data['materials'][index]['name'],'material':mats[index].get_path_name()})
    report.setdefault('material_bindings',{})[role]=bindings
    mesh.set_editor_property('materials',slots);save(mesh.get_editor_property('skeleton'));save(mesh);return mesh

def ikrig(name,mesh,bones):
    rig=create('IK_'+name,BASE+'/Rigs',u.IKRigDefinition,u.IKRigDefinitionFactory());c=u.IKRigController.get_controller(rig);c.set_skeletal_mesh(mesh)
    for ch in c.get_retarget_chains():c.remove_retarget_chain(ch.chain_name)
    c.set_retarget_root(bones['hips']);c.set_root_motion_bone(bones['root'])
    chains=[('Spine','spine_start','spine_end'),('Head','neck','head')]
    for side in ['left','right']:chains += [(side+'Clavicle',side+'_clavicle',side+'_clavicle'),(side+'Arm',side+'_upperarm',side+'_hand'),(side+'Leg',side+'_thigh',side+'_foot')]
    for label,start,end in chains:c.add_retarget_chain(label,bones[start],bones[end],'')
    save(rig);return rig

def animate():
    from motion_metrics import measure_clip
    source=u.load_asset('/Game/Characters/Mannequins/Meshes/SKM_Manny_Simple')
    if not source:raise RuntimeError('Configured UE mannequin animation library is not installed')
    bones={'root':'root','hips':'pelvis','spine_start':'spine_01','spine_end':'spine_05','neck':'neck_01','head':'head'}
    for side,letter in [('left','l'),('right','r')]:
        for k,v in [('clavicle','clavicle'),('upperarm','upperarm'),('hand','hand'),('thigh','thigh'),('foot','foot')]:bones[side+'_'+k]=v+'_'+letter
    source_rig=ikrig('source',source,bones)
    clip_paths=['Unarmed/MM_Idle','Unarmed/Walk/MF_Unarmed_Walk_Fwd','Unarmed/Walk/MF_Unarmed_Walk_Bwd','Unarmed/Walk/MF_Unarmed_Walk_Left','Unarmed/Walk/MF_Unarmed_Walk_Right','Unarmed/Jog/MF_Unarmed_Jog_Fwd','Unarmed/Attack/MM_Attack_01','Unarmed/Attack/MM_Attack_02','Unarmed/Attack/MM_Attack_03','Unarmed/Attack/MM_ChargedAttack','Unarmed/Jump/MM_Dash','Rifle/HitReact/MM_HitReact_Front_Hvy_01','Rifle/HitReact/MM_HitReact_Front_Lgt_01','Death/MM_Death_Front_01']
    assets=[u.EditorAssetLibrary.find_asset_data('/Game/Characters/Mannequins/Anims/'+p) for p in clip_paths]
    report['characters']={}
    for role,path in job['characters'].items():
        data=json.loads(Path(path).read_text());mesh=skeletal(role,data);target=ikrig(role,mesh,data['bone_map'])
        rt=create('RT_'+role,BASE+'/Rigs',u.IKRetargeter,u.IKRetargetFactory());c=u.IKRetargeterController.get_controller(rt)
        c.set_ik_rig(u.RetargetSourceOrTarget.SOURCE,source_rig);c.set_ik_rig(u.RetargetSourceOrTarget.TARGET,target)
        if c.get_num_retarget_ops()==0:c.add_default_ops()
        c.auto_map_chains(u.AutoMapChainType.EXACT,True);c.auto_align_all_bones(u.RetargetSourceOrTarget.TARGET);save(rt)
        results=u.IKRetargetBatchOperation.duplicate_and_retarget(assets,source,mesh,rt,prefix=role+'_',target_path=BASE+'/Animations/'+role,include_referenced_assets=False,overwrite_existing_files=True)
        paths=[]
        for clip in clip_paths:
            path=BASE+'/Animations/'+role+'/'+role+'_'+clip.split('/')[-1];a=u.load_asset(path)
            if not isinstance(a,u.AnimSequence):raise RuntimeError('Missing motion clip '+path)
            a.set_editor_property('additive_anim_type',u.AdditiveAnimationType.AAT_NONE)
            a.set_editor_property('ref_pose_seq',None);a.set_editor_property('ref_pose_type',u.AdditiveBasePoseType.ABPT_REF_POSE)
            prop(a,'force_root_lock',True);prop(a,'enable_root_motion',False);save(a);paths.append(path)
        locomotion={'walk':measure_clip(u.load_asset(paths[1]),data['bone_map']),'run':measure_clip(u.load_asset(paths[5]),data['bone_map'])}
        report['characters'][role]={'mesh':mesh.get_path_name(),'clips':paths,'bone_map':data['bone_map'],'height_cm':data['height_cm'],'motion_count':len(paths),'locomotion':locomotion}
        print('ANIMATION_READY',role,len(paths),flush=True)

def static(entry,index,mat):
    reused=job.get('reused_static',{}).get(str(index))
    if reused:
        import hashlib
        if hashlib.sha256(Path(entry['file']).read_bytes()).hexdigest()!=reused['source_sha256'] or hashlib.sha256(Path(reused['package']).read_bytes()).hexdigest()!=reused['package_sha256']:raise RuntimeError('Static reuse integrity failure')
        mesh=u.load_asset(BASE+'/Environment/SM_Group_'+str(index))
        if not mesh:raise RuntimeError('Verified reused mesh could not be loaded')
        if entry.get('triangles',0)>10000 and entry['collision']:ML.set_material_usage(mat,u.MaterialUsage.MATUSAGE_NANITE);save(mat)
        changed=False
        for slot in range(max(1,len(mesh.get_editor_property('static_materials')))):
            current=mesh.get_material(slot)
            if current is None or current.get_path_name()!=mat.get_path_name():
                mesh.set_material(slot,mat);changed=True
        # Reassigning an identical material triggers costly mesh rebuilds.
        # The current material asset is already saved at its package path.
        if changed:save(mesh)
        return mesh
    # FRESH_STATIC_CONTRACT
    opt=u.FbxImportUI();opt.automated_import_should_detect_type=False;opt.import_mesh=True;opt.import_as_skeletal=False;opt.import_materials=False;opt.import_textures=False
    opt.mesh_type_to_import=u.FBXImportType.FBXIT_STATIC_MESH
    opt.static_mesh_import_data.combine_meshes=True;opt.static_mesh_import_data.auto_generate_collision=False;opt.static_mesh_import_data.transform_vertex_to_absolute=True
    opt.static_mesh_import_data.normal_import_method=u.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS
    opt.static_mesh_import_data.vertex_color_import_option=u.VertexColorImportOption.REPLACE
    opt.static_mesh_import_data.generate_lightmap_u_vs=False
    # Save once after current Nanite/collision/material settings are applied.
    # Reimports can inherit an old group slot's settings during the import.
    task=u.AssetImportTask();task.filename=entry['file'];task.destination_path=BASE+'/Environment';task.destination_name='SM_Group_'+str(index);task.automated=True;task.replace_existing=True;task.save=False;task.options=opt;task.factory=u.FbxFactory();AT.import_asset_tasks([task])
    mesh=u.load_asset(task.destination_path+'/'+task.destination_name)
    if not mesh:raise RuntimeError('Environment import failed')
    ns=mesh.get_editor_property('nanite_settings')
    ns.enabled=entry.get('triangles',0)>10000 and entry['collision']
    if ns.enabled:
        ML.set_material_usage(mat,u.MaterialUsage.MATUSAGE_NANITE);save(mat)
        # Complex collision uses Nanite's fallback mesh. Aggressive simplification
        # of a joined terrain batch can create invisible ridges in the play space.
        ns.fallback_target=u.NaniteFallbackTarget.PERCENT_TRIANGLES
        ns.fallback_percent_triangles=1.;ns.fallback_relative_error=0.
    mesh.set_editor_property('nanite_settings',ns)
    if entry['collision']:mesh.get_editor_property('body_setup').set_editor_property('collision_trace_flag',u.CollisionTraceFlag.CTF_USE_COMPLEX_AS_SIMPLE)
    for i in range(max(1,len(mesh.get_editor_property('static_materials')))):mesh.set_material(i,mat)
    save(mesh);return mesh
def spawn(cls,label,pos=(0,0,0),rot=(0,0,0)):
    actor=EA.spawn_actor_from_class(cls,u.Vector(*pos),u.Rotator(pitch=rot[0],yaw=rot[1],roll=rot[2]),False);actor.set_actor_label(label);return actor

def import_environment_batch():
    scene=json.loads(Path(job['scene']).read_text());mats={}
    from ground_finishes import apply as apply_ground_finishes
    scene=apply_ground_finishes(scene,job.get('ground_finishes',{}),job['texture_library'])
    from vegetation_rendering import configure as configure_vegetation
    report['vegetation_rendering']=[];report['imported_indices']=[]
    for i in job['import_indices']:
        entry=scene['environment'][i];name=entry['material']
        if name not in mats:
            data=dict(scene['materials'][name]);data['textures']=data.get('textures') or job['texture_library'].get(data.get('texture_set',''),{})
            mats[name]=material('M_Environment_'+name,data,world=True)
        mesh=static(entry,i,mats[name])
        foliage=configure_vegetation(u,mesh,mats[name],entry,save)
        if foliage:report['vegetation_rendering'].append(foliage)
        report['imported_indices'].append(i)
        print('STATIC_BATCH_SAVED',i,flush=True)

def assemble():
    scene=json.loads(Path(job['scene']).read_text());anims=json.loads(Path(job['animations']).read_text())['characters']
    from ground_finishes import apply as apply_ground_finishes
    scene=apply_ground_finishes(scene,job.get('ground_finishes',{}),job['texture_library'])
    report['ground_finishes']=job.get('ground_finishes',{})
    if u.EditorAssetLibrary.does_asset_exist(BASE+'/Maps/Demo'):
        LE.load_level(BASE+'/Maps/Demo')
        for actor in EA.get_all_level_actors():
            if not isinstance(actor,(u.WorldSettings,u.LevelScriptActor)):EA.destroy_actor(actor)
    else:LE.new_level(BASE+'/Maps/Demo')
    mats={}
    for name,mat in scene['materials'].items():
        data=dict(mat);data['textures']=mat.get('textures') or job['texture_library'].get(mat.get('texture_set',''),{})
        mats[name]=material('M_Environment_'+name,data,world=True)
    from vegetation_rendering import configure as configure_vegetation
    from foliage_wind import configure_shadow_cache
    report['vegetation_rendering']=[]
    report['foliage_shadow_cache']=[]
    for i,entry in enumerate(scene['environment']):
        mesh=static(entry,i,mats[entry['material']])
        foliage=configure_vegetation(u,mesh,mats[entry['material']],entry,save)
        if foliage:report['vegetation_rendering'].append(foliage)
        placements=entry.get('instances',[{'position_cm':[0,0,0],'yaw_deg':0,'scale':[1,1,1]}])
        if 'instances' in entry and (entry.get('instance_contract') not in ['upright_shared_mesh_v1','upright_shared_mesh_v2'] or (entry['collision'] and entry.get('instance_contract')!='upright_shared_mesh_v2') or entry.get('semantic_id') not in [3,4,5,6] or not placements):
            raise RuntimeError('Invalid shared geometry contract')
        for j,placement in enumerate(placements):
            actor=spawn(u.StaticMeshActor,'Environment '+str(i)+' instance '+str(j),placement['position_cm'],(0,placement['yaw_deg'],0))
            actor.set_actor_scale3d(u.Vector(*placement['scale']));actor.static_mesh_component.set_static_mesh(mesh)
            actor.static_mesh_component.set_collision_profile_name('BlockAll' if entry['collision'] else 'NoCollision')
            shadow_cache=configure_shadow_cache(u,actor.static_mesh_component,entry,scene['materials'][entry['material']])
            if shadow_cache:report['foliage_shadow_cache'].append({'material':entry['material'],**shadow_cache})
            semantics.tag(actor,entry.get('semantic_id',semantics.class_for_material(entry['material'],scene['materials'][entry['material']])))
            if scene['materials'][entry['material']].get('surface')=='thin_glass':
                actor.tags=list(actor.tags)+[u.Name('capture:opaque_surface_behind_glass_v1')]
                actor.static_mesh_component.set_render_custom_depth(False)
        if 'instances' in entry:report.setdefault('shared_geometry',[]).append({'index':i,'instances':len(placements),'source_triangles':entry['triangles'],'expanded_triangles':entry['expanded_triangles']})
    import whitebox
    report['whitebox']=whitebox.install(scene,static,spawn)
    # Play-space containment is a gameplay rule, independent of the art theme.
    half=scene['size_m']*50
    bounds=scene.get('exploration',{}).get('play_bounds',{'min':[-half/100,-half/100],'max':[half/100,half/100]})
    xmin,ymin=bounds['min'];xmax,ymax=bounds['max'];cx=(xmin+xmax)*50;cy=(ymin+ymax)*50
    for i,(pos,scale) in enumerate([((xmax*100,cy,1000),(.2,ymax-ymin,30)),((xmin*100,cy,1000),(.2,ymax-ymin,30)),((cx,ymax*100,1000),(xmax-xmin,.2,30)),((cx,ymin*100,1000),(xmax-xmin,.2,30))]):
        wall=spawn(u.StaticMeshActor,'Play bounds '+str(i),pos);wall.static_mesh_component.set_static_mesh(u.load_asset('/Engine/BasicShapes/Cube'))
        wall.set_actor_scale3d(u.Vector(*scale));wall.static_mesh_component.set_collision_profile_name('BlockAll');wall.set_actor_hidden_in_game(True)
    lighting=dict(scene['lighting']);lighting.update(job.get('lighting_overrides',{}))
    from practical_lights import install as install_practical_lights
    report['practical_lights']=install_practical_lights(lighting,spawn)
    sun=spawn(u.DirectionalLight,'Sun',rot=(lighting['sun_pitch'],lighting['sun_yaw'],0));sun.light_component.set_mobility(u.ComponentMobility.MOVABLE)
    sun.light_component.set_intensity(lighting['sun_intensity']);sun.light_component.set_light_color(u.LinearColor(*lighting['sun_color'],1));prop(sun.light_component,'light_source_angle',lighting.get('sun_angle_deg',2.2));prop(sun.light_component,'atmosphere_sun_light',True)
    atmosphere=spawn(u.SkyAtmosphere,'Atmosphere')
    from atmosphere_profiles import install as install_atmosphere_profile
    report['weather_profile']=install_atmosphere_profile(u,atmosphere.get_component_by_class(u.SkyAtmosphereComponent),lighting)
    if 'sky_luminance_factor' in lighting:
        value=float(lighting['sky_luminance_factor'])
        if not 1<=value<=20000:raise ValueError('Invalid visible sky luminance factor')
        atmosphere.get_component_by_class(u.SkyAtmosphereComponent).set_editor_property('sky_luminance_factor',u.LinearColor(value,value,value,1))
    sky=spawn(u.SkyLight,'Sky bounce');sky.light_component.set_mobility(u.ComponentMobility.MOVABLE)
    captured=lighting.get('sky_mode','daylight_cubemap')=='captured'
    prop(sky.light_component,'source_type',u.SkyLightSourceType.SLS_CAPTURED_SCENE if captured else u.SkyLightSourceType.SLS_SPECIFIED_CUBEMAP)
    if not captured:prop(sky.light_component,'cubemap',u.load_asset('/Engine/MapTemplates/Sky/DaylightAmbientCubemap.DaylightAmbientCubemap'))
    prop(sky.light_component,'real_time_capture',captured);sky.light_component.set_intensity(lighting['sky_intensity'])
    sky.light_component.set_light_color(u.LinearColor(*lighting.get('sky_color',[.82,.9,1]),1))
    report['lighting_profile']={'sky_mode':lighting.get('sky_mode','daylight_cubemap'),'sky_color':lighting.get('sky_color',[.82,.9,1]),'sun_angle_deg':lighting.get('sun_angle_deg',2.2)}
    fog=spawn(u.ExponentialHeightFog,'Distance haze',(0,0,-150));prop(fog.component,'fog_density',lighting['fog_density']);prop(fog.component,'start_distance',lighting.get('fog_start_m',22)*100)
    if 'fog_color' in lighting:prop(fog.component,'fog_inscattering_luminance',u.LinearColor(*lighting['fog_color'],1))
    if 'fog_height_falloff' in lighting:prop(fog.component,'fog_height_falloff',lighting['fog_height_falloff'])
    pp=spawn(u.PostProcessVolume,'Exposure');pp.set_editor_property('unbound',True);settings=pp.get_editor_property('settings')
    for key,value in [('auto_exposure_method',u.AutoExposureMethod.AEM_MANUAL),('auto_exposure_apply_physical_camera_exposure',False),('auto_exposure_bias',lighting['exposure_bias']),('motion_blur_amount',.08),('bloom_intensity',lighting.get('bloom_intensity',.05)),('vignette_intensity',.12)]:prop(settings,'override_'+key,True);prop(settings,key,value)
    pp.set_editor_property('settings',settings)
    world=u.get_editor_subsystem(u.UnrealEditorSubsystem).get_editor_world();world.get_world_settings().set_editor_property('default_game_mode',u.load_class(None,'/Script/GameDemo.GameDemoGameMode'))
    fighter_cls=u.load_class(None,'/Script/GameDemo.GameDemoFighter')
    report['fighters']={}
    for role in ['player','boss']:
        char=anims[role];pos=scene['spawns'][role];other=scene['spawns']['boss' if role=='player' else 'player'];yaw=math.degrees(math.atan2(other[1]-pos[1],other[0]-pos[0]))
        actor=spawn(fighter_cls,role,(pos[0]*100,pos[1]*100,pos[2]*100+char['height_cm']*.49+5),(0,yaw,0));actor.set_editor_property('is_boss',role=='boss')
        mesh=u.load_asset(char['mesh']);actor.mesh.set_skeletal_mesh_asset(mesh);actor.set_editor_property('motion_clips',[u.load_asset(p) for p in char['clips']])
        settings={'display_name':job['characters_config'][role]['name'],'game_title':job['title'],'character_height_cm':char['height_cm'],'config_health':job['gameplay'][role+'_health'],
          'camera_width_cm':job['gameplay']['camera_width_cm'],'camera_pitch':job['gameplay']['camera_pitch'],'camera_yaw':job['gameplay']['camera_yaw'],
          'walk_stride_speed':char['locomotion']['walk']['stride_speed_cm_s'],'run_stride_speed':char['locomotion']['run']['stride_speed_cm_s'],
          'motion_root_bone':char['bone_map']['root'],'hip_bone':char['bone_map']['hips'],'head_bone':char['bone_map']['head'],'foot_bone':char['bone_map']['left_foot'],'spine_bone':char['bone_map']['spine_end'],
          'left_thigh_bone':char['bone_map']['left_thigh'],'right_thigh_bone':char['bone_map']['right_thigh'],
          'aim_spine_bone':char['bone_map']['spine_start'],
          'left_arm_bone':char['bone_map']['left_upperarm'],'right_arm_bone':char['bone_map']['right_upperarm'],
          'strike_bones':[char['bone_map'][k] for k in ['right_hand','left_hand','right_foot','left_foot']],
          'capture_bone_map':{u.Name(k):u.Name(v) for k,v in char['bone_map'].items()}}
        for key,value in settings.items():actor.set_editor_property(key,value)
        if scene.get('exploration'):
            ex=scene['exploration'];actor.set_editor_property('encounter_radius_cm',ex['encounter_radius_m']*100)
            if role=='player':
                # Complete the actual itinerary and return to the known clear
                # player spawn. The runtime then approaches the live encounter;
                # a fabricated Boss-relative endpoint can sit inside its capsule.
                waypoints=ex['waypoints_m']+[scene['spawns']['player']]
                actor.set_editor_property('exploration_waypoints',[u.Vector(*(v*100 for v in p)) for p in waypoints])
                actor.set_editor_property('exploration_places',[u.Vector(*(v*100 for v in p['center'])) for p in ex['places']])
                actor.set_editor_property('exploration_names',[p['name'] for p in ex['places']])
        report['fighters'][role]={'mesh':char['mesh'],'height_cm':char['height_cm'],'animations':len(char['clips'])}
    semantics.material()
    if scene.get('exploration'):report['exploration']=scene['exploration']
    LE.save_current_level();report['map']=BASE+'/Maps/Demo';report['lighting']=lighting;report['semantic_classes']=semantics.CLASSES

try:
    u.SystemLibrary.execute_console_command(None,'Interchange.FeatureFlags.Import.FBX 0')
    if job['mode']=='animation':animate()
    elif job['mode']=='static_assets':import_environment_batch()
    else:assemble()
    # Every modified asset and the map have already been saved explicitly.
    # Do not force-save unrelated upstream animation packages.
    report['ok']=True
except Exception:report['error']=traceback.format_exc();print(report['error'],flush=True)
(out/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('UE_ADAPTER_RESULT',report['ok'],flush=True)
