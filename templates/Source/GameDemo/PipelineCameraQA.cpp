#include "PipelineCameraQA.h"
#include "GameDemo.h"
#include "Camera/CameraComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/CapsuleComponent.h"
#include "GameFramework/PlayerController.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/SpringArmComponent.h"
#include "EngineUtils.h"
#include "Misc/App.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonSerializer.h"
#include "Engine/World.h"

namespace { const FKey Directions[]={EKeys::W,EKeys::S,EKeys::A,EKeys::D}; const int Modes[]={0,1,2,1}; }
APipelineCameraQA::APipelineCameraQA()
{
    PrimaryActorTick.bCanEverTick=true;PrimaryActorTick.TickGroup=TG_PostUpdateWork;
    Samples.SetNum(16);
}
bool APipelineCameraQA::FindProbeSpace()
{
    // A camera/input test needs a clear movement fixture, not an assumption that
    // every authored spawn has five metres of unobstructed ground in all axes.
    const FVector Spawn=Player->GetAuthoredSpawnPosition();
    FVector Center=Player->Opponent?(Spawn+Player->Opponent->GetAuthoredSpawnPosition())*.5:Spawn;
    Center.Z=Spawn.Z;
    TArray<FVector> Candidates={Spawn,Center};
    for(float Radius: {200.f,400.f,600.f})for(int32 I=0;I<8;++I)
        Candidates.Add(Center+FRotator(0,I*45.f,0).Vector()*Radius);
    FCollisionQueryParams Params(SCENE_QUERY_STAT(CameraProbeSpace),true,Player);
    if(Player->Opponent)Params.AddIgnoredActor(Player->Opponent);
    const float Half=Player->GetCapsuleComponent()->GetScaledCapsuleHalfHeight();
    const float Radius=Player->GetCapsuleComponent()->GetScaledCapsuleRadius()+2;
    const FCollisionShape Shape=FCollisionShape::MakeCapsule(Radius,Half);
    const FRotator Flat(0,Player->CameraBoom->GetComponentRotation().Yaw,0);
    const FVector Front=Flat.Vector(),Right=FRotationMatrix(Flat).GetUnitAxis(EAxis::Y);
    const FVector Axes[]={Front,-Front,Right,-Right};
    for(const FVector& Candidate:Candidates)
    {
        ++ProbeCandidates;bool Clear=true;FString Reason;float BaseZ=0;FVector Origin;
        for(int32 Axis=0;Axis<4&&Clear;++Axis)
        {
            FVector PreviousProbe;
            for(int32 Step=0;Step<=11;++Step)
            {
                const FVector XY=Candidate+Axes[Axis]*float(Step*50);FHitResult Ground;
                ++ProbeQueries;
                if(!GetWorld()->LineTraceSingleByChannel(Ground,XY+FVector(0,0,200),XY-FVector(0,0,400),ECC_Visibility,Params)
                    ||Ground.ImpactNormal.Z<.94f||FMath::Abs(Ground.ImpactPoint.Z-(Spawn.Z-Half))>50)
                {Clear=false;Reason=TEXT("missing or steep floor");break;}
                if(Axis==0&&Step==0){BaseZ=Ground.ImpactPoint.Z;Origin=FVector(Candidate.X,Candidate.Y,BaseZ+Half+2.5f);}
                if(FMath::Abs(Ground.ImpactPoint.Z-BaseZ)>15)
                {Clear=false;Reason=TEXT("floor height varies beyond flat probe budget");break;}
                const FVector Probe(XY.X,XY.Y,Ground.ImpactPoint.Z+Half+5.f);
                ++ProbeQueries;
                if(GetWorld()->OverlapBlockingTestByChannel(Probe,FQuat::Identity,ECC_Pawn,Shape,Params))
                {Clear=false;Reason=FString::Printf(TEXT("capsule overlap at %s"),*Probe.ToString());break;}
                FHitResult Block;
                if(Step>0)
                {
                    ++ProbeQueries;
                    if(GetWorld()->SweepSingleByChannel(Block,PreviousProbe,Probe,FQuat::Identity,ECC_Pawn,Shape,Params))
                    {Clear=false;Reason=FString::Printf(TEXT("capsule sweep blocked by %s / %s at %s"),
                        *GetNameSafe(Block.GetActor()),*GetNameSafe(Block.GetComponent()),*Block.ImpactPoint.ToString());break;}
                }
                PreviousProbe=Probe;
            }
        }
        if(Clear){TestOrigin=Origin;return true;}
        if(ProbeCandidates==1)SpawnProbeRejection=Reason;
    }
    return false;
}
void APipelineCameraQA::BeginCase(int32 Index)
{
    auto* PC=Cast<APlayerController>(Player->GetController());if(!PC)return;
    if(Held.IsValid())PC->InputKey(FInputKeyEventArgs::CreateSimulated(Held,IE_Released,0));
    Player->ResetDuel();
    Player->SetActorLocation(TestOrigin,false,nullptr,ETeleportType::TeleportPhysics);
    const FVector Before=Player->GetActorLocation();Player->SetViewMode(Modes[Index/4]);
    MaxSwitchDisplacement=FMath::Max(MaxSwitchDisplacement,float(FVector::Dist(Before,Player->GetActorLocation())));
    // Pawn interference belongs to combat QA; retain actual terrain/structure collision here.
    Player->GetCapsuleComponent()->SetCollisionResponseToChannel(ECC_Pawn,ECR_Ignore);
    Held=Directions[Index%4];PC->InputKey(FInputKeyEventArgs::CreateSimulated(Held,IE_Pressed,1));
    Case=Index;CaseAge=0;Previous=Player->GetActorLocation();
}
void APipelineCameraQA::Tick(float Dt)
{
    Super::Tick(Dt);if(Finished)return;Age+=Dt;
    if(!Player)
    {
        for(TActorIterator<AGameDemoFighter>I(GetWorld());I;++I)if(!I->IsBoss)Player=*I;
        if(!Player){if(Age>5)Finish();return;}
        FApp::SetUseFixedTimeStep(true);FApp::SetFixedDeltaTime(1.0/60.0);
        AddTickPrerequisiteActor(Player);AddTickPrerequisiteComponent(Player->GetMesh());AddTickPrerequisiteComponent(Player->CameraBoom);
    }
    if(Age<2)return;
    if(Case<0)
    {
        // Inspect the actual startup camera before the test calls SetViewMode.
        const auto& PP=Player->Camera->PostProcessSettings;
        StartupProjectionPolicyValid=Player->ViewMode==2
            &&Player->Camera->ProjectionMode==ECameraProjectionMode::Orthographic
            &&PP.bOverride_LumenAmbientOcclusionIntensity&&FMath::IsNearlyZero(PP.LumenAmbientOcclusionIntensity);
        ProbeSpaceValid=FindProbeSpace();
        if(!ProbeSpaceValid){Finish();return;}
        BeginCase(0);return;
    }
    CaseAge+=Dt;
    if(CaseAge>1.6f){if(Case==15)Finish();else BeginCase(Case+1);return;}
    const FVector Step=Player->GetActorLocation()-Previous;Previous=Player->GetActorLocation();
    auto& S=Samples[Case];
    if(CaseAge<.4f)return;
    const auto* Mesh=Player->GetMesh();const int Mode=Modes[Case/4];
    S.Visibility&=Mesh->IsVisible()&&!Player->IsHidden()&&(Mesh->bOwnerNoSee==(Mode==0));
    S.Scale&=Mesh->GetRelativeScale3D().GetMin()>.05f;
    S.Projection&=(Player->Camera->ProjectionMode==ECameraProjectionMode::Orthographic)==(Mode==2);
    const auto& PP=Player->Camera->PostProcessSettings;
    S.ProjectionPolicy&=Mode==2?(PP.bOverride_LumenAmbientOcclusionIntensity&&FMath::IsNearlyZero(PP.LumenAmbientOcclusionIntensity)):!PP.bOverride_LumenAmbientOcclusionIntensity;
    S.MaxStep=FMath::Max(S.MaxStep,float(Step.Size()));
    const FRotator Flat(0,Player->CameraBoom->GetComponentRotation().Yaw,0);
    const FVector Front=FRotationMatrix(Flat).GetUnitAxis(EAxis::X),Right=FRotationMatrix(Flat).GetUnitAxis(EAxis::Y);
    const FVector Wanted=Case%4==0?Front:Case%4==1?-Front:Case%4==2?-Right:Right;
    if(Step.Size2D()>.05f)
    {
        const float Error=FMath::RadiansToDegrees(FMath::Acos(FMath::Clamp(FVector::DotProduct(Step.GetSafeNormal2D(),Wanted),-1.,1.)));
        S.MaxInputError=FMath::Max(S.MaxInputError,Error);S.Travel+=Step.Size2D();++S.Frames;
    }
    if(auto* PC=Cast<APlayerController>(Player->GetController()))
    {
        if(Mode!=0)
        {
            int W,H;PC->GetViewportSize(W,H);FVector2D Pixel;
            S.Framed&=PC->ProjectWorldLocationToScreen(Player->GetActorLocation(),Pixel)&&W>0&&H>0&&Pixel.X>W*.2&&Pixel.X<W*.8&&Pixel.Y>H*.15&&Pixel.Y<H*.85;
        }
        if(Case%4==0&&S.Frames==35)PC->ConsoleCommand(TEXT("HighResShot 1"));
    }
}
void APipelineCameraQA::Finish()
{
    Finished=true;
    if(Player)if(auto* PC=Cast<APlayerController>(Player->GetController()))if(Held.IsValid())PC->InputKey(FInputKeyEventArgs::CreateSimulated(Held,IE_Released,0));
    auto O=MakeShared<FJsonObject>();TArray<TSharedPtr<FJsonValue>> Rows;bool Passed=ProbeSpaceValid&&StartupProjectionPolicyValid&&Player&&Case==15&&MaxSwitchDisplacement<.01f;
    for(int I=0;I<Samples.Num();I++)
    {
        const auto& S=Samples[I];const bool Good=S.Frames>=30&&S.Travel>100&&S.MaxInputError<8&&S.MaxStep<25&&S.Visibility&&S.Scale&&S.Projection&&S.Framed&&S.ProjectionPolicy;
        Passed&=Good;auto Row=MakeShared<FJsonObject>();Row->SetNumberField(TEXT("case"),I);
        Row->SetStringField(TEXT("camera"),Modes[I/4]==0?TEXT("first"):Modes[I/4]==1?TEXT("third"):TEXT("isometric"));
        Row->SetStringField(TEXT("key"),Directions[I%4].ToString());Row->SetNumberField(TEXT("samples"),S.Frames);
        Row->SetNumberField(TEXT("travel_cm"),S.Travel);Row->SetNumberField(TEXT("max_input_error_deg"),S.MaxInputError);Row->SetNumberField(TEXT("max_world_step_cm"),S.MaxStep);
        Row->SetBoolField(TEXT("owner_visibility_correct"),S.Visibility);Row->SetBoolField(TEXT("projection_correct"),S.Projection);
        Row->SetBoolField(TEXT("projection_policy_correct"),S.ProjectionPolicy);
        Row->SetBoolField(TEXT("player_framed"),S.Framed);Row->SetBoolField(TEXT("mesh_scale_valid"),S.Scale);Row->SetBoolField(TEXT("passed"),Good);Rows.Add(MakeShared<FJsonValueObject>(Row));
    }
    O->SetArrayField(TEXT("cases"),Rows);O->SetNumberField(TEXT("switch_displacement_cm"),MaxSwitchDisplacement);O->SetBoolField(TEXT("returned_to_third"),Player&&Player->ViewMode==1);O->SetBoolField(TEXT("passed"),Passed);
    O->SetBoolField(TEXT("probe_space_validated"),ProbeSpaceValid);O->SetNumberField(TEXT("probe_candidates"),ProbeCandidates);O->SetNumberField(TEXT("probe_queries"),ProbeQueries);
    O->SetStringField(TEXT("test_origin_cm"),TestOrigin.ToString());O->SetStringField(TEXT("authored_spawn_cm"),Player?Player->GetAuthoredSpawnPosition().ToString():TEXT("missing"));
    O->SetStringField(TEXT("authored_spawn_rejection"),SpawnProbeRejection);
    O->SetBoolField(TEXT("startup_projection_policy_correct"),StartupProjectionPolicyValid);
    FString Json;auto Writer=TJsonWriterFactory<>::Create(&Json);FJsonSerializer::Serialize(O,Writer);
    FFileHelper::SaveStringToFile(Json,*(FPaths::ProjectSavedDir()/TEXT("GameDemoCameraQA.json")));
    UE_LOG(LogTemp,Display,TEXT("CAMERA_QA passed=%d"),Passed);FPlatformMisc::RequestExit(false);
}
