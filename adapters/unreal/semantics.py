"""Renderer-grounded, versioned semantic classes. No image segmentation inference."""
CLASSES={'sky':0,'terrain':1,'paving':2,'architecture':3,'rock':4,'vegetation':5,'prop':6,'player':10,'boss':11,'unknown':255}

def class_for_material(name,material,floor=None,path=None):
    if material.get('semantic_class'):
        value=material['semantic_class']
        if value not in CLASSES:raise ValueError('Unknown semantic class '+value)
        return CLASSES[value]
    if name==floor:return CLASSES['terrain']
    if name==path:return CLASSES['paving']
    return CLASSES[{'layered_ground':'terrain','masonry':'architecture','grass':'vegetation','foliage':'vegetation','scan':'rock','metal':'prop'}.get(material.get('surface'),'prop')]

def material():
    import unreal as u
    path='/Game/Generated/Data';name='M_Semantic';ml=u.MaterialEditingLibrary
    mat=u.load_asset(path+'/'+name)
    if not mat:mat=u.AssetToolsHelpers.get_asset_tools().create_asset(name,path,u.Material,u.MaterialFactoryNew())
    for node in list(ml.get_material_expressions(mat)):ml.delete_material_expression(mat,node)
    mat.set_editor_property('material_domain',u.MaterialDomain.MD_POST_PROCESS)
    mat.set_editor_property('blendable_location',u.BlendableLocation.BL_REPLACING_TONEMAPPER)
    mat.set_editor_property('blendable_priority',100)
    stencil=ml.create_material_expression(mat,u.MaterialExpressionSceneTexture)
    stencil.set_editor_property('scene_texture_id',u.SceneTextureId.PPI_CUSTOM_STENCIL)
    divide=ml.create_material_expression(mat,u.MaterialExpressionDivide);divide.set_editor_property('const_b',255.)
    ml.connect_material_expressions(stencil,'Color',divide,'A')
    ml.connect_material_property(divide,'',u.MaterialProperty.MP_EMISSIVE_COLOR)
    ml.recompile_material(mat);u.EditorAssetLibrary.save_loaded_asset(mat)
    for i,color in enumerate([(0.8,0.,0.),(0.,0.8,0.8)]):
        name='M_Calibration'+str(i);m=u.load_asset(path+'/'+name)
        if not m:m=u.AssetToolsHelpers.get_asset_tools().create_asset(name,path,u.Material,u.MaterialFactoryNew())
        ml.delete_all_material_expressions(m);m.set_editor_property('shading_model',u.MaterialShadingModel.MSM_UNLIT)
        c=ml.create_material_expression(m,u.MaterialExpressionConstant3Vector);c.set_editor_property('constant',u.LinearColor(*color,1))
        ml.connect_material_property(c,'',u.MaterialProperty.MP_EMISSIVE_COLOR);ml.recompile_material(m);u.EditorAssetLibrary.save_loaded_asset(m)
    return mat

def tag(actor,identity):
    import unreal as u
    tags=[t for t in actor.tags if not str(t).startswith('semantic:')]
    actor.tags=tags+[u.Name('semantic:'+str(identity))]
