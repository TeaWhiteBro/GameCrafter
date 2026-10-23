"""PBR surface families. Image sources and appearance parameters live in the job."""
import unreal as u, math, re
from foliage_wind import SWAY_X_CM, SWAY_Y_CM, FOLIAGE_WEIGHT

def build(name,data,api,texture_library):
    node,wire,output,tex,create,save,prop=[api[k] for k in ['node','wire','output','tex','create','save','prop']]
    ML=u.MaterialEditingLibrary
    m=create(name,api['BASE']+'/Materials',u.Material,u.MaterialFactoryNew())
    for expression in list(ML.get_material_expressions(m)):ML.delete_material_expression(m,expression)
    family=data['surface'];world=family in ['layered_ground','masonry','metal'] or (family=='pbr' and data.get('triplanar',True));prop(m,'tangent_space_normal',not world)
    def nd(cls,**kw):return node(m,cls,**kw)
    def c(x):return nd(u.MaterialExpressionConstant,r=x)
    def v(x):return nd(u.MaterialExpressionConstant3Vector,constant=u.LinearColor(*x,1))
    def mul(a,b):
        q=nd(u.MaterialExpressionMultiply);wire(a,'',q,'A');wire(b,'',q,'B');return q
    def add(a,b):
        q=nd(u.MaterialExpressionAdd);wire(a,'',q,'A');wire(b,'',q,'B');return q
    def lerp(a,b,w):
        q=nd(u.MaterialExpressionLinearInterpolate);wire(a,'',q,'A');wire(b,'',q,'B');wire(w,'',q,'Alpha');return q
    def mask(a,channel):
        q=nd(u.MaterialExpressionComponentMask,**{x.lower():x in channel for x in 'RGBA'});wire(a,'',q,'Input');return q
    def custom(code,inputs,kind=u.CustomMaterialOutputType.CMOT_FLOAT3):
        q=nd(u.MaterialExpressionCustom);q.set_editor_property('code',code);q.set_editor_property('output_type',kind)
        entries=[]
        for k in inputs:
            entry=u.CustomInput();entry.set_editor_property('input_name',k);entries.append(entry)
        q.set_editor_property('inputs',entries)
        for k,value in inputs.items():wire(value,'',q,k)
        return q
    def out(n,p,channel=''):output(n,channel,p)
    pos=nd(u.MaterialExpressionWorldPosition);normal=nd(u.MaterialExpressionVertexNormalWS);vc=nd(u.MaterialExpressionVertexColor)
    def uv(scale,angle=0):
        return custom(f'return float2(P.x*{math.cos(angle)}-P.y*{math.sin(angle)},P.x*{math.sin(angle)}+P.y*{math.cos(angle)})/{float(scale)};',{'P':pos},u.CustomMaterialOutputType.CMOT_FLOAT2)
    def sample(path,key,kind='base',coord=None,triplanar=False,scale=180):
        tx=tex(path,'T_'+name+'_'+key,normal=kind=='normal',linear=kind in ['roughness','orm','alpha','metallic','ao','height'],flip=data.get('normal_opengl',False) and kind=='normal')
        if triplanar:
            obj=nd(u.MaterialExpressionTextureObject,texture=tx);sm=nd(u.MaterialExpressionMaterialFunctionCall);sm.set_material_function(u.load_asset('/Engine/Functions/Engine_MaterialFunctions01/Texturing/'+('WorldAlignedNormal' if kind=='normal' else 'WorldAlignedTexture')))
            wire(obj,'',sm,'TextureObject');wire(v([scale]*3),'',sm,'TextureSize')
            # Return through a reroute because function outputs have named pins.
            route=nd(u.MaterialExpressionReroute);wire(sm,'XYZ Texture',route,'Input');return route
        sm=nd(u.MaterialExpressionTextureSample,texture=tx);sm.set_editor_property('sampler_type',u.MaterialSamplerType.SAMPLERTYPE_NORMAL if kind=='normal' else u.MaterialSamplerType.SAMPLERTYPE_LINEAR_COLOR if kind in ['roughness','orm','alpha','metallic','ao','height'] else u.MaterialSamplerType.SAMPLERTYPE_COLOR)
        if coord:wire(coord,'',sm,'UVs')
        return sm
    def layer(key,settings):
        textures=texture_library[settings['texture_set']];coord=uv(settings.get('scale_cm',220),settings.get('rotation',0))
        tri=data.get('triplanar',False);scale=settings.get('scale_cm',220)
        color=sample(textures['base'],key+'_base',coord=coord,triplanar=tri,scale=scale);color=mul(color,v(settings.get('tint',[1,1,1])))
        if settings.get('paint_color'):
            color=custom('float l=dot(C,float3(.2126,.7152,.0722));return Paint*(1.+D*(2.*l-1.));',
                {'C':color,'Paint':v(settings['paint_color']),'D':c(settings.get('paint_detail',.16))})
        if settings.get('desaturate'):
            color=custom('float l=dot(C,float3(.2126,.7152,.0722));return lerp(C,l.xxx,S);',{'C':color,'S':c(settings['desaturate'])})
        nn=sample(textures['normal'],key+'_normal','normal',coord,triplanar=tri,scale=scale)
        rough=mask(sample(textures['roughness'],key+'_rough','roughness',coord,triplanar=tri,scale=scale),'R')
        return color,nn,rough
    if family=='thin_glass':
        if data.get('capture_policy')!='opaque_surface_behind_glass_v1' or data.get('refraction'):
            raise ValueError('Thin glass requires non-refractive underlying-surface capture')
        prop(m,'blend_mode',u.BlendMode.BLEND_TRANSLUCENT)
        prop(m,'two_sided',True)
        prop(m,'translucency_lighting_mode',u.TranslucencyLightingMode.TLM_SURFACE_PER_PIXEL_LIGHTING)
        prop(m,'allow_custom_depth_writes',False)
        out(v(data.get('color',[.24,.46,.52])),u.MaterialProperty.MP_BASE_COLOR)
        out(c(data.get('roughness',.10)),u.MaterialProperty.MP_ROUGHNESS)
        out(c(0),u.MaterialProperty.MP_METALLIC)
        # No screen-space refraction: depth/labels identify the unchanged
        # underlying opaque surface, while RGB retains subtle glazing highlights.
        out(c(data.get('opacity',.045)),u.MaterialProperty.MP_OPACITY)
    elif family=='layered_ground':
        sets=data['layers'];a=layer('soil',sets[0]);b=layer('rock',sets[1]);d=layer('moss',sets[2]);rw=mask(vc,'R');mw=mask(vc,'G');wet=mask(vc,'B')
        co=lerp(lerp(a[0],b[0],rw),d[0],mw)
        nn=lerp(lerp(a[1],b[1],rw),d[1],mw)
        rough=add(c(.38),mul(lerp(lerp(a[2],b[2],rw),d[2],mw),c(.37)))
        if data.get('vertex_wear_surface'):
            wear=data['vertex_wear_surface'];surface=layer('wear',wear)
            if data.get('wear_zones'):
                from surface_wetness import shader
                wet=custom(shader(data['wear_zones']),{'P':pos,'N':normal,'Base':wet},u.CustomMaterialOutputType.CMOT_FLOAT1)
            co=lerp(co,surface[0],wet);nn=lerp(nn,surface[1],mul(wet,c(.4)))
            rough=lerp(rough,c(wear['roughness']),wet)
        else:
            co=mul(co,lerp(c(1.06),c(.79),wet));rough=lerp(rough,c(.31),wet)
        out(co,u.MaterialProperty.MP_BASE_COLOR)
        normal_code='return normalize(lerp(V,N,.45));' if data.get('triplanar',False) else 'return normalize(V+float3(N.xy*.24,0));'
        out(custom(normal_code,{'V':normal,'N':nn}),u.MaterialProperty.MP_NORMAL)
        out(rough,u.MaterialProperty.MP_ROUGHNESS)
    elif family=='masonry':
        textures=data.get('textures') or texture_library[data['texture_set']];scale=data.get('scale_cm',180)
        co=sample(textures['base'],'base',triplanar=True,scale=scale)
        co=custom('float l=dot(C,float3(.2126,.7152,.0722));return lerp(C,l.xxx,S);',{'C':co,'S':c(data.get('desaturate',.50))})
        co=mul(co,v(data.get('tint',[1.15,1.18,1.12])));co=mul(co,lerp(c(.87),c(1.09),mask(vc,'R')))
        if data.get('macro_variation_strength'):
            co=custom('float w=.5+.22*sin(P.x*.0031+sin(P.y*.0043))+.18*sin(P.y*.0061+P.z*.008);return C*lerp(1.,.70+w*.42,S);',{'C':co,'P':pos,'S':c(data['macro_variation_strength'])})
        weather=custom('float p=sin(P.x*.008+sin(P.y*.010))+sin(P.y*.006+P.z*.011)+.35*sin(P.x*.049+P.y*.023);return saturate(G*(.75+p*.32));',{'P':pos,'G':mask(vc,'G')},u.CustomMaterialOutputType.CMOT_FLOAT1)
        if data.get('weather_texture_set'):
            moss=texture_library[data['weather_texture_set']]
            moss_color=sample(moss['base'],'weather_base',triplanar=True,scale=110)
            moss_color=mul(moss_color,v(data.get('weather_tint',[.78,.91,.68])))
        else:moss_color=mul(co,v([.40,.62,.29]))
        co=lerp(co,moss_color,mul(weather,c(.80)))
        out(co,u.MaterialProperty.MP_BASE_COLOR)
        nn=sample(textures['normal'],'normal','normal',triplanar=True,scale=scale)
        out(custom('return normalize(lerp(V,N,S));',{'V':normal,'N':nn,'S':c(data.get('normal_strength',.25))}),u.MaterialProperty.MP_NORMAL)
        rr=mask(sample(textures['roughness'],'rough','roughness',triplanar=True,scale=scale),'R');out(add(c(.36),mul(rr,c(.32))),u.MaterialProperty.MP_ROUGHNESS)
    elif family=='pbr':
        textures=data.get('textures') or texture_library[data['texture_set']];scale=data.get('scale_cm',200);tri=data.get('triplanar',True)
        coord=None if tri else uv(scale,data.get('rotation',0))
        co=sample(textures['base'],'base',coord=coord,triplanar=tri,scale=scale)
        breakup=float(data.get('texture_breakup_strength',0))
        if not 0<=breakup<=1:raise ValueError('Texture breakup strength must be in [0,1]')
        if breakup:
            # Incommensurate world scales reduce visible repetition while
            # retaining the same photographed material and physical normal map.
            medium=sample(textures['base'],'breakup_medium',coord=None if tri else uv(scale*2.731,.53),triplanar=tri,scale=scale*2.731)
            large=sample(textures['base'],'breakup_large',coord=None if tri else uv(scale*9.137,-.37),triplanar=tri,scale=scale*9.137)
            co=custom('float w=.5+.22*sin(P.x*.0017+sin(P.y*.0023))+.18*sin(P.y*.0031-P.z*.0019);float3 b=lerp(M,L,.30+.26*w);return lerp(C,b,S)*(.84+.24*w);',{'C':co,'M':medium,'L':large,'P':pos,'S':c(breakup)})
        if data.get('paint_color'):
            # Opaque paint replaces wood hue, while measured grain and matched
            # roughness/normal maps retain the substrate's surface structure.
            co=custom('float l=dot(C,float3(.2126,.7152,.0722));return Paint*(1.+D*(2.*l-1.));',
                {'C':co,'Paint':v(data['paint_color']),'D':c(data.get('paint_detail',.16))})
        if data.get('desaturate'):co=custom('float l=dot(C,float3(.2126,.7152,.0722));return lerp(C,l.xxx,S);',{'C':co,'S':c(data['desaturate'])})
        co=mul(co,v(data.get('tint',[1,1,1])))
        if data.get('vertex_wear_tint'):
            co=lerp(co,mul(co,v(data['vertex_wear_tint'])),mask(vc,'B'))
        wear=data.get('vertex_wear_surface')
        if wear:
            wear_scale=wear.get('scale_cm',65)
            wear_color=sample(textures['base'],'wear_base',coord=None if tri else uv(wear_scale),triplanar=tri,scale=wear_scale)
            wear_color=custom('float lum=dot(C,float3(.2126,.7152,.0722));return Paint*(1.+D*(2.*lum-1.));',{'C':wear_color,'Paint':v(wear['paint_color']),'D':c(wear.get('detail',.8))})
            co=lerp(co,wear_color,mask(vc,'B'))
        ice=None
        if data.get('frozen_surface'):
            from frozen_surface import shader,validate
            frozen=validate(data['frozen_surface'])
            # HLSL reserves "line" as a geometry primitive modifier. Normalize
            # the controlled source's local identifier at the UE boundary;
            # geometry/contract validation does not depend on shader spelling.
            frozen_code=re.sub(r'\bline\b','iceFractureDistance',shader(frozen))
            ice=custom(frozen_code,{'P':pos,'V':nd(u.MaterialExpressionCameraVectorWS)})
            frost=custom('return saturate(F*S+E*.78);',{'F':mask(ice,'R'),'E':mask(vc,'R'),'S':c(frozen.get('frost_strength',.46))},u.CustomMaterialOutputType.CMOT_FLOAT1)
            co=mul(co,lerp(c(.55),c(1.7),mask(ice,'B')))
            co=lerp(co,v([.38,.46,.48]),frost)
            co=lerp(co,v([.48,.57,.59]),mul(mask(ice,'G'),c(frozen.get('crack_strength',.32))))
        if data.get('vertex_tone_strength'):
            co=mul(co,custom('return lerp(1.,clamp(R,.45,1.4),S);',{'R':mask(vc,'R'),'S':c(data['vertex_tone_strength'])},u.CustomMaterialOutputType.CMOT_FLOAT1))
        wet=None
        if data.get('wetness',0)>0:
            # Surface response, not a transparent decal or extra geometry. XY
            # world coordinates make adjacent material batches agree at seams.
            wet=custom('float2 q=P.xy/(Scale*100.); float f=.46+.22*sin(q.x+1.1*sin(q.y*.71))+.20*sin(q.y*1.37+.8*sin(q.x*.53))+.10*sin(q.x*2.93-q.y*2.11); return W*smoothstep(.56,.80,f)*smoothstep(.72,.96,N.z);',
                {'P':pos,'N':normal,'Scale':c(data.get('wetness_scale_m',2.5)),'W':c(data['wetness'])},u.CustomMaterialOutputType.CMOT_FLOAT1)
        if data.get('wetness_zones'):
            from surface_wetness import shader
            wet=custom(shader(data['wetness_zones']),{'P':pos,'N':normal,'Base':wet if wet is not None else c(0)},u.CustomMaterialOutputType.CMOT_FLOAT1)
        if wet is not None:co=mul(co,lerp(c(1),c(.60),wet))
        out(co,u.MaterialProperty.MP_BASE_COLOR)
        nn=sample(textures['normal'],'normal','normal',coord,triplanar=tri,scale=scale)
        strength=c(data.get('normal_strength',.5))
        if wear:
            wear_normal=sample(textures['normal'],'wear_normal','normal',None if tri else uv(wear_scale),triplanar=tri,scale=wear_scale)
            nn=lerp(nn,wear_normal,mask(vc,'B'))
            strength=lerp(strength,c(wear.get('normal_strength',.65)),mask(vc,'B'))
        if wet is not None:strength=mul(strength,lerp(c(1),c(.4),wet))
        out(custom('return normalize(lerp(V,N,S));',{'V':normal if tri else v([0,0,1]),'N':nn,'S':strength}),u.MaterialProperty.MP_NORMAL)
        rr=mask(sample(textures['roughness'],'rough','roughness',coord,triplanar=tri,scale=scale),'R')
        response=custom('return clamp(R*S+B,.06,.98);',{'R':rr,'S':c(data.get('roughness_scale',1)),'B':c(data.get('roughness_bias',0))},u.CustomMaterialOutputType.CMOT_FLOAT1)
        if wear:
            wear_rough=mask(sample(textures['roughness'],'wear_rough','roughness',None if tri else uv(wear_scale),triplanar=tri,scale=wear_scale),'R')
            response=lerp(response,c(wear['roughness']) if 'roughness' in wear else add(c(.4),mul(wear_rough,c(.45))),mask(vc,'B'))
        if ice is not None:response=lerp(c(.10),c(.68),frost)
        if wet is not None:response=lerp(response,c(.13),wet)
        out(response,u.MaterialProperty.MP_ROUGHNESS)
        if 'metallic' in textures:metal=mask(sample(textures['metallic'],'metal','metallic',coord,triplanar=tri,scale=scale),'R')
        else:metal=c(data.get('metallic',0))
        out(metal,u.MaterialProperty.MP_METALLIC)
        if 'ao' in textures:out(mask(sample(textures['ao'],'ao','ao',coord,triplanar=tri,scale=scale),'R'),u.MaterialProperty.MP_AMBIENT_OCCLUSION)
        if data.get('water_surface'):
            from water_surface import validate as validate_water, normal_shader, variation_shader
            water=validate_water(data['water_surface'])
            prop(m,'tangent_space_normal',False)
            water_time=nd(u.MaterialExpressionTime)
            variation=custom(variation_shader(water),{'P':pos,'T':water_time},u.CustomMaterialOutputType.CMOT_FLOAT1)
            water_tint=mul(v(water.get('tint',[.035,.10,.075])),lerp(c(.60),c(1.35),variation))
            bed_mix=mul(c(water.get('bed_visibility',.2)),lerp(c(.55),c(1.25),variation))
            out(lerp(water_tint,co,bed_mix),u.MaterialProperty.MP_BASE_COLOR)
            out(custom(normal_shader(water),{'P':pos,'T':water_time,'N':normal}),u.MaterialProperty.MP_NORMAL)
            out(mul(c(water.get('roughness',.16)),lerp(c(.75),c(1.25),variation)),u.MaterialProperty.MP_ROUGHNESS)
            out(c(0),u.MaterialProperty.MP_METALLIC)
            out(c(.5),u.MaterialProperty.MP_SPECULAR)
            out(c(1),u.MaterialProperty.MP_AMBIENT_OCCLUSION)
    elif family=='metal':
        patina=custom('return saturate(.48+.22*sin(P.x*.018+sin(P.z*.036))+.27*sin(P.y*.021+P.z*.013));',{'P':pos},u.CustomMaterialOutputType.CMOT_FLOAT1)
        out(lerp(v(data.get('color',[.20,.10,.038])),v(data.get('patina',[.065,.19,.16])),patina),u.MaterialProperty.MP_BASE_COLOR)
        out(lerp(c(.36),c(.67),patina),u.MaterialProperty.MP_ROUGHNESS);out(c(.82),u.MaterialProperty.MP_METALLIC)
    elif family in ['scan','foliage']:
        textures=data['textures'];co=sample(textures['base'],'base')
        if data.get('desaturate'):co=custom('float l=dot(C,float3(.2126,.7152,.0722));return lerp(C,l.xxx,S);',{'C':co,'S':c(data['desaturate'])})
        co=mul(co,v(data.get('tint',[1,1,1])));out(co,u.MaterialProperty.MP_BASE_COLOR)
        if 'normal' in textures:
            nn=sample(textures['normal'],'normal','normal');out(lerp(v([0,0,1]),nn,c(data.get('normal_strength',.65))),u.MaterialProperty.MP_NORMAL)
        if 'roughness' in textures:rr=mask(sample(textures['roughness'],'roughness','roughness'),'R')
        elif 'orm' in textures:rr=mask(sample(textures['orm'],'orm','orm'),'G')
        else:rr=c(data.get('roughness',.65))
        out(add(c(data.get('roughness_bias',.26)),mul(rr,c(data.get('roughness_scale',.43)))),u.MaterialProperty.MP_ROUGHNESS)
        if 'metallic' in textures:out(mask(sample(textures['metallic'],'metallic','metallic'),'R'),u.MaterialProperty.MP_METALLIC)
        elif 'orm' in textures:out(mask(sample(textures['orm'],'metallic','orm'),'B'),u.MaterialProperty.MP_METALLIC)
        else:out(c(data.get('metallic',0)),u.MaterialProperty.MP_METALLIC)
        if 'emissive' in textures:out(mul(sample(textures['emissive'],'emissive'),c(data.get('emissive_strength',1))),u.MaterialProperty.MP_EMISSIVE_COLOR)
        if 'ao' in textures:out(mask(sample(textures['ao'],'ao','ao'),'R'),u.MaterialProperty.MP_AMBIENT_OCCLUSION)
        if family=='foliage':
            prop(m,'two_sided',True);prop(m,'blend_mode',u.BlendMode.BLEND_MASKED);prop(m,'shading_model',u.MaterialShadingModel.MSM_TWO_SIDED_FOLIAGE)
            out(mask(sample(textures['alpha'],'alpha','alpha'),'R'),u.MaterialProperty.MP_OPACITY_MASK);out(mul(co,c(.4)),u.MaterialProperty.MP_SUBSURFACE_COLOR)
        elif data.get('thin_leaf_subsurface'):
            prop(m,'two_sided',True);prop(m,'shading_model',u.MaterialShadingModel.MSM_TWO_SIDED_FOLIAGE)
            out(mul(co,c(data.get('subsurface_strength',.4))),u.MaterialProperty.MP_SUBSURFACE_COLOR)
    elif family=='botanical':
        prop(m,'two_sided',True);prop(m,'shading_model',u.MaterialShadingModel.MSM_TWO_SIDED_FOLIAGE)
        co=v(data.get('color',[.8,.4,.6]));out(co,u.MaterialProperty.MP_BASE_COLOR)
        out(mul(co,c(.48)),u.MaterialProperty.MP_SUBSURFACE_COLOR);out(c(.68),u.MaterialProperty.MP_ROUGHNESS)
    elif family=='grass':
        prop(m,'two_sided',True);prop(m,'shading_model',u.MaterialShadingModel.MSM_TWO_SIDED_FOLIAGE)
        co=mul(v(data.get('color',[.07,.12,.038])),lerp(c(.46),c(1.13),mask(vc,'R')));out(co,u.MaterialProperty.MP_BASE_COLOR);out(mul(co,c(.5)),u.MaterialProperty.MP_SUBSURFACE_COLOR);out(c(.65),u.MaterialProperty.MP_ROUGHNESS)
    if family in ['foliage','grass','botanical']:
        time=nd(u.MaterialExpressionTime)
        weight=mask(vc,'R') if family=='grass' else c(FOLIAGE_WEIGHT)
        wind=custom(f'float a=sin(T*1.4+P.x*.018+P.y*.011);return float3(a*{SWAY_X_CM},sin(T*1.1+P.y*.012)*{SWAY_Y_CM},0)*W;',{'P':pos,'T':time,'W':weight})
        out(wind,u.MaterialProperty.MP_WORLD_POSITION_OFFSET)
    out(c(.32),u.MaterialProperty.MP_SPECULAR)
    ML.recompile_material(m);save(m);return m
