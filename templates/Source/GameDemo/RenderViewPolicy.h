#pragma once
#include "Engine/Scene.h"

// UE 5.8 short-range screen AO produces large bands in orthographic urban
// views. Keep Lumen GI/reflections and VSM; isolate this optional AO term to
// perspective views. Both gameplay and paired RGB use this per-view policy.
inline void ApplyPipelineProjectionPolicy(FPostProcessSettings& Settings, bool Orthographic)
{
    Settings.bOverride_LumenAmbientOcclusionIntensity = Orthographic;
    Settings.LumenAmbientOcclusionIntensity = Orthographic ? 0.f : 1.f;
}
