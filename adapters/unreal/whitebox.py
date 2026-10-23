"""Import the structural companion as a capture-only, non-interacting layer."""
import unreal as u

def material():
    path='/Game/Generated/Data';name='M_Whitebox';ml=u.MaterialEditingLibrary
    mat=u.load_asset(path+'/'+name)
    if not mat:mat=u.AssetToolsHelpers.get_asset_tools().create_asset(name,path,u.Material,u.MaterialFactoryNew())
    ml.delete_all_material_expressions(mat);mat.set_editor_property('shading_model',u.MaterialShadingModel.MSM_UNLIT)
    mat.set_editor_property('two_sided',True)
    n=ml.create_material_expression(mat,u.MaterialExpressionPixelNormalWS)
    light=ml.create_material_expression(mat,u.MaterialExpressionConstant3Vector);light.set_editor_property('constant',u.LinearColor(-.45,-.35,.82,1))
    dot=ml.create_material_expression(mat,u.MaterialExpressionDotProduct)
    ml.connect_material_expressions(n,'',dot,'A');ml.connect_material_expressions(light,'',dot,'B')
    mul=ml.create_material_expression(mat,u.MaterialExpressionMultiply);mul.set_editor_property('const_b',.28);ml.connect_material_expressions(dot,'',mul,'A')
    add=ml.create_material_expression(mat,u.MaterialExpressionAdd);add.set_editor_property('const_b',.48);ml.connect_material_expressions(mul,'',add,'A')
    ml.connect_material_property(add,'',u.MaterialProperty.MP_EMISSIVE_COLOR);ml.recompile_material(mat);u.EditorAssetLibrary.save_loaded_asset(mat)
    return mat

def install(scene,static,spawn):
    entry=scene.get('whitebox')
    if not entry:return {'available':False,'reason':'Scene adapter did not provide structural companion geometry'}
    if entry.get('ratio',1)>=.5 or 'portal_tests' not in entry:raise ValueError('Whitebox geometry contract is incomplete')
    mat=material();mesh=static({**entry,'collision':False},'Whitebox',mat)
    actor=spawn(u.StaticMeshActor,'Structural whitebox');c=actor.static_mesh_component;c.set_static_mesh(mesh)
    c.set_collision_profile_name('NoCollision');c.set_editor_property('cast_shadow',False)
    c.set_editor_property('affect_distance_field_lighting',False);c.set_editor_property('affect_dynamic_indirect_lighting',False)
    c.set_editor_property('visible_in_ray_tracing',False);c.set_editor_property('visible_in_scene_capture_only',True)
    actor.tags=[u.Name('whitebox')];actor.set_actor_hidden_in_game(True)
    return {'available':True,'triangles':entry['triangles'],'source_spec_sha256':entry['source_spec_sha256'],'asset':mesh.get_path_name(),'capture_only':True,'collision':False}
