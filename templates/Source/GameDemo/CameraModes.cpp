#include "GameDemo.h"
#include "Camera/CameraComponent.h"
#include "GameFramework/SpringArmComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "GameFramework/PlayerController.h"
#include "InputCoreTypes.h"
#include "RenderViewPolicy.h"

FString AGameDemoFighter::ViewModeName() const
{ return ViewMode==0?TEXT("first"):ViewMode==1?TEXT("third"):TEXT("isometric"); }

void AGameDemoFighter::SetViewMode(int32 Mode)
{
    if(IsBoss)return;
    if(ViewMode==2)SavedIsoYaw=CameraBoom->GetComponentRotation().Yaw;
    else OrbitYaw=CameraBoom->GetComponentRotation().Yaw;
    ViewMode=FMath::Clamp(Mode,0,2);
    ApplyPipelineProjectionPolicy(Camera->PostProcessSettings,ViewMode==2);
    Camera->SetRelativeLocation(FVector::ZeroVector);
    Camera->SetRelativeRotation(FRotator::ZeroRotator);
    CameraBoom->SocketOffset=FVector::ZeroVector;
    CameraBoom->bEnableCameraLag=false;
    CameraBoom->bEnableCameraRotationLag=false;
    GetMesh()->SetOwnerNoSee(ViewMode==0);
    GetMesh()->bCastHiddenShadow=true;
    if(ViewMode==2)
    {
        Camera->SetProjectionMode(ECameraProjectionMode::Orthographic);
        Camera->SetOrthoWidth(CameraWidthCm);
        Camera->SetAutoCalculateOrthoPlanes(true);
        CameraBoom->TargetOffset=FVector::ZeroVector;
        CameraBoom->TargetArmLength=3600;
        CameraBoom->bDoCollisionTest=false;
        CameraBoom->SetWorldRotation(FRotator(CameraPitch,SavedIsoYaw,0));
    }
    else
    {
        Camera->SetProjectionMode(ECameraProjectionMode::Perspective);
        Camera->SetFieldOfView(ViewMode==0?90:75);
        CameraBoom->TargetOffset=FVector(0,0,CharacterHeightCm*(ViewMode==0?.42f:.24f));
        CameraBoom->TargetArmLength=ViewMode==0?0:ThirdPersonDistance;
        CameraBoom->bDoCollisionTest=ViewMode==1;
        CameraBoom->ProbeSize=16;
        CameraBoom->SetWorldRotation(FRotator(ViewMode==0?0:OrbitPitch,OrbitYaw,0));
    }
}

void AGameDemoFighter::UpdateViewInput(float Dt)
{
    // Authored observation cameras own their lens, radius and orientation.
    // Gameplay input must not silently reset a diagnostic view each frame.
    if(ArtQAMode)return;
    auto* PC=Cast<APlayerController>(GetController());if(!PC)return;
    if(PC->WasInputKeyJustPressed(EKeys::One))SetViewMode(0);
    if(PC->WasInputKeyJustPressed(EKeys::Two))SetViewMode(1);
    if(PC->WasInputKeyJustPressed(EKeys::Three))SetViewMode(2);
    if(PC->WasInputKeyJustPressed(EKeys::V))SetViewMode((ViewMode+1)%3);
    float Spin=(PC->IsInputKeyDown(EKeys::E)?1.f:0)-(PC->IsInputKeyDown(EKeys::Q)?1.f:0);
    FRotator Rot=CameraBoom->GetComponentRotation();Rot.Yaw+=Spin*60*Dt;
    if(ViewMode!=2)
    {
        float X=0,Y=0;PC->GetInputMouseDelta(X,Y);
        Rot.Yaw+=X*.14f;Rot.Pitch=FMath::Clamp(Rot.Pitch+Y*.14f,ViewMode==0?-80.f:-65.f,ViewMode==0?80.f:30.f);
        OrbitYaw=Rot.Yaw;OrbitPitch=Rot.Pitch;
        if(ViewMode==1)
        {
            if(PC->WasInputKeyJustPressed(EKeys::MouseScrollUp))ThirdPersonDistance=FMath::Max(180.f,ThirdPersonDistance-40);
            if(PC->WasInputKeyJustPressed(EKeys::MouseScrollDown))ThirdPersonDistance=FMath::Min(1000.f,ThirdPersonDistance+40);
            CameraBoom->TargetArmLength=ThirdPersonDistance;
        }
    }
    else
    {
        if(PC->WasInputKeyJustPressed(EKeys::MouseScrollUp))Camera->SetOrthoWidth(FMath::Max(1150.f,Camera->OrthoWidth-100));
        if(PC->WasInputKeyJustPressed(EKeys::MouseScrollDown))Camera->SetOrthoWidth(FMath::Min(3000.f,Camera->OrthoWidth+100));
        CameraWidthCm=Camera->OrthoWidth;
    }
    CameraBoom->SetWorldRotation(Rot);
}
