#include "GameDemo.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/PlayerController.h"
#include "GameFramework/SpringArmComponent.h"
#include "Components/CapsuleComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Camera/CameraComponent.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonSerializer.h"
#include "Engine/World.h"

void AGameDemoFighter::UpdateExploration(float Dt)
{
    if(IsBoss||!IsExploring())return;
    CurrentPlace=TEXT("Exploration");
    if(Opponent&&FVector::Dist2D(GetActorLocation(),Opponent->SpawnPosition)<1200)CurrentPlace=TEXT("Encounter courtyard");
    for(int32 I=0;I<ExplorationPlaces.Num();++I)
        if(FVector::Dist2D(GetActorLocation(),ExplorationPlaces[I])<650)
        {DiscoveredPlaces.Add(I);if(ExplorationNames.IsValidIndex(I))CurrentPlace=ExplorationNames[I];}
    if(auto* PC=Cast<APlayerController>(GetController()))
        if(!RoamQAMode&&PC->WasInputKeyJustPressed(EKeys::M))ShowRouteMap=!ShowRouteMap;
    if(GetActorLocation().Z < -3000 && !RoamQAMode)ResetDuel();
}

void AGameDemoFighter::UpdateExplorationQA(float Dt)
{
    if(RoamQAComplete)return;
    RoamAge+=Dt;
    if(!IsExploring()){WriteExplorationQA();return;}
    if(RoamAge<2){RoamPrevious=GetActorLocation();return;}
    if(RoamSamples==0&&Opponent)Opponent->Engaged=true;
    const FVector Step=GetActorLocation()-RoamPrevious;RoamPrevious=GetActorLocation();
    ++RoamSamples;RoamTravel+=Step.Size2D();RoamMaxStep=FMath::Max(RoamMaxStep,float(Step.Size()));
    RoamStill=Step.Size2D()<.3f?RoamStill+Dt:0;
    RoamAirTime=GetCharacterMovement()->IsFalling()?RoamAirTime+Dt:0;RoamMaxAirTime=FMath::Max(RoamMaxAirTime,RoamAirTime);
    if(Opponent&&RoamAge>12&&!Opponent->Engaged&&!Opponent->ReturningHome&&FVector::Dist2D(Opponent->GetActorLocation(),Opponent->SpawnPosition)<85)RoamLeashReturned=true;
    if(RoamWaypoint<ExplorationWaypoints.Num())
    {
        FVector To=ExplorationWaypoints[RoamWaypoint]-GetActorLocation();
        if(To.Size2D()<65){++RoamWaypoint;RoamStill=0;}
        else if(CanAct())
        {
            Locked=false;MoveDirection=To.GetSafeNormal2D();GetCharacterMovement()->MaxWalkSpeed=490;
            // Walk around a live opponent, keeping real collision and damage.
            // Static obstructions still stop the test instead of being skipped.
            if(Opponent)
            {
                FVector Relative=Opponent->GetActorLocation()-GetActorLocation();Relative.Z=0;
                const float Along=FVector::DotProduct(Relative,MoveDirection);
                const FVector Side(-MoveDirection.Y,MoveDirection.X,0);
                const float Across=FVector::DotProduct(Relative,Side);
                if(Along>-60&&Along<340&&FMath::Abs(Across)<180)
                {
                    if(RoamAvoidSign==0)RoamAvoidSign=Across>0?-1:1;
                    MoveDirection=(MoveDirection+Side*RoamAvoidSign*1.65f).GetSafeNormal2D();
                    ++RoamAvoidFrames;
                }
                else RoamAvoidSign=0;
            }
            AddMovementInput(MoveDirection);
            const FRotator Desired(0,MoveDirection.Rotation().Yaw,0);
            SetActorRotation(FMath::RInterpTo(GetActorRotation(),Desired,Dt,12));
            if(ViewMode!=2)CameraBoom->SetWorldRotation(FMath::RInterpTo(CameraBoom->GetComponentRotation(),FRotator(ViewMode==0?-3:-18,Desired.Yaw,0),Dt,2));
        }
        for(int32 I:DiscoveredPlaces)
            if(!RoamCaptured.Contains(I))
            {
                RoamCaptured.Add(I);
                RoamCaptureOrder.Add(I);
                if(!FParse::Param(FCommandLine::Get(),TEXT("DatasetCapture")))if(auto* PC=Cast<APlayerController>(GetController()))PC->ConsoleCommand(TEXT("HighResShot 1"));
            }
    }
    else
    {
        // A new itinerary may end outside aggro range. Actually approach the
        // encounter again rather than assuming its endpoint causes engagement.
        if(Opponent&&!RoamReengaged)
        {
            const FVector To=Opponent->GetActorLocation()-GetActorLocation();
            if(To.Size2D()>320&&CanAct())
            {
                MoveDirection=To.GetSafeNormal2D();GetCharacterMovement()->MaxWalkSpeed=490;
                AddMovementInput(MoveDirection);SetActorRotation(FRotator(0,MoveDirection.Rotation().Yaw,0));
            }
            if(Opponent->Engaged&&!Opponent->ReturningHome)RoamReengaged=true;
        }
        if(RoamReengaged){RoamFinishWait+=Dt;if(RoamFinishWait>2)WriteExplorationQA();}
    }
    if(RoamStill>8||RoamAge>170||Health<=0)WriteExplorationQA();
}

void AGameDemoFighter::WriteExplorationQA()
{
    if(RoamQAComplete)return;
    RoamQAComplete=true;GetCharacterMovement()->StopMovementImmediately();
    auto O=MakeShared<FJsonObject>();
    O->SetStringField(TEXT("camera"),ViewModeName());
    O->SetNumberField(TEXT("waypoints_reached"),RoamWaypoint);O->SetNumberField(TEXT("waypoints_total"),ExplorationWaypoints.Num());
    O->SetNumberField(TEXT("travel_m"),RoamTravel/100);O->SetNumberField(TEXT("samples"),RoamSamples);
    O->SetNumberField(TEXT("duration_s"),RoamAge);O->SetNumberField(TEXT("max_world_step_cm"),RoamMaxStep);
    O->SetNumberField(TEXT("max_falling_s"),RoamMaxAirTime);O->SetNumberField(TEXT("places_discovered"),DiscoveredPlaces.Num());
    O->SetBoolField(TEXT("boss_returned_home"),RoamLeashReturned);O->SetBoolField(TEXT("boss_reengaged"),RoamReengaged);
    O->SetBoolField(TEXT("expected_owner_visibility"),GetMesh()->bOwnerNoSee==(ViewMode==0));
    const bool Passed=RoamWaypoint==ExplorationWaypoints.Num()&&RoamSamples>600&&RoamTravel>15000&&RoamMaxStep<90&&RoamMaxAirTime<.8f&&DiscoveredPlaces.Num()==ExplorationPlaces.Num()&&RoamLeashReturned&&RoamReengaged&&GetMesh()->bOwnerNoSee==(ViewMode==0);
    O->SetBoolField(TEXT("passed"),Passed);
    O->SetStringField(TEXT("final_position"),GetActorLocation().ToString());
    O->SetNumberField(TEXT("health"),Health);O->SetNumberField(TEXT("still_s"),RoamStill);
    O->SetNumberField(TEXT("dynamic_avoidance_frames"),RoamAvoidFrames);
    TArray<TSharedPtr<FJsonValue>> CaptureOrder;for(int32 I:RoamCaptureOrder)CaptureOrder.Add(MakeShared<FJsonValueNumber>(I));
    O->SetArrayField(TEXT("captured_place_indices"),CaptureOrder);
    if(Opponent){O->SetStringField(TEXT("opponent_position"),Opponent->GetActorLocation().ToString());O->SetBoolField(TEXT("opponent_engaged"),Opponent->Engaged);}
    const FVector Target=ExplorationWaypoints.IsValidIndex(RoamWaypoint)?ExplorationWaypoints[RoamWaypoint]:(Opponent?Opponent->GetActorLocation():GetActorLocation());
    FHitResult Hit;FCollisionQueryParams Params(SCENE_QUERY_STAT(RoamStopDiagnostic),false,this);
    if(GetWorld()->SweepSingleByChannel(Hit,GetActorLocation(),GetActorLocation()+(Target-GetActorLocation()).GetSafeNormal2D()*180,FQuat::Identity,ECC_Pawn,GetCapsuleComponent()->GetCollisionShape(),Params))
    {O->SetStringField(TEXT("blocking_actor"),GetNameSafe(Hit.GetActor()));O->SetStringField(TEXT("blocking_component"),GetNameSafe(Hit.GetComponent()));}
    FString Json;auto Writer=TJsonWriterFactory<>::Create(&Json);FJsonSerializer::Serialize(O,Writer);
    FFileHelper::SaveStringToFile(Json,*(FPaths::ProjectSavedDir()/TEXT("GameDemoExplorationQA.json")));
    UE_LOG(LogTemp,Display,TEXT("EXPLORATION_QA passed=%d reached=%d/%d travel=%.1fm position=%s"),Passed,RoamWaypoint,ExplorationWaypoints.Num(),RoamTravel/100,*GetActorLocation().ToString());
    if(FParse::Param(FCommandLine::Get(),TEXT("PipelineExit")))FPlatformMisc::RequestExit(false);
}
