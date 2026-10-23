#include "PipelineFramePacing.h"
#include "CoreMinimal.h"

#if PLATFORM_WINDOWS
#include "Windows/WindowsHWrapper.h"
#endif

void ConfigurePipelineFramePacing()
{
#if PLATFORM_WINDOWS && defined(PROCESS_POWER_THROTTLING_IGNORE_TIMER_RESOLUTION)
    // UE already requests 1 ms timer resolution. Windows may ignore that request
    // for an occluded process, making its 60 FPS sleep overshoot. Change only the
    // timer-resolution policy of this process; keep CPU/power settings untouched.
    PROCESS_POWER_THROTTLING_STATE State{};
    State.Version = PROCESS_POWER_THROTTLING_CURRENT_VERSION;
    State.ControlMask = PROCESS_POWER_THROTTLING_IGNORE_TIMER_RESOLUTION;
    State.StateMask = 0;
    const bool Applied = !!::SetProcessInformation(::GetCurrentProcess(), ProcessPowerThrottling, &State, sizeof(State));
    const uint32 Error = Applied ? 0u : static_cast<uint32>(::GetLastError());
    UE_LOG(LogTemp, Display, TEXT("PIPELINE_FRAME_PACING timer_resolution_honored=%d win32_error=%u scope=current_process"), Applied, Error);
#else
    UE_LOG(LogTemp, Display, TEXT("PIPELINE_FRAME_PACING native_platform_policy"));
#endif
}
