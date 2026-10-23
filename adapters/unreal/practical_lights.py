"""Install authored practical lights and record measured UE component values."""
import unreal as u

def install(lighting,spawn):
    result=[]
    for i,item in enumerate(lighting.get('local_lights',[])):
        actor=spawn(u.PointLight,'Practical light '+str(i),tuple(v*100 for v in item['position']))
        comp=actor.light_component;comp.set_mobility(u.ComponentMobility.MOVABLE)
        comp.set_editor_property('intensity_units',u.LightUnits.LUMENS)
        comp.set_editor_property('use_inverse_squared_falloff',True)
        comp.set_intensity(item['intensity_lm']);comp.set_light_color(u.LinearColor(*item['color'],1))
        comp.set_editor_property('attenuation_radius',item['range_m']*100)
        comp.set_editor_property('source_radius',item.get('source_radius_m',.12)*100)
        position=actor.get_actor_location()
        result.append({'index':i,'position_cm':[position.x,position.y,position.z],
            'intensity_lm':comp.get_editor_property('intensity'),'range_cm':comp.get_editor_property('attenuation_radius'),
            'source_radius_cm':comp.get_editor_property('source_radius')})
    return result
