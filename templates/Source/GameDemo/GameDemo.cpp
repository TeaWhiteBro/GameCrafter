#include "GameDemo.h"
#include "PipelineCapture.h"
#include "PipelineCameraQA.h"
#include "PipelineFramePacing.h"
#include "Modules/ModuleManager.h"
#include "Animation/AnimInstanceProxy.h"
#include "Animation/AnimSequence.h"
#include "Animation/AnimationPoseData.h"
#include "GameFramework/SpringArmComponent.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/PlayerController.h"
#include "Camera/CameraComponent.h"
#include "Components/CapsuleComponent.h"
#include "Engine/Canvas.h"
#include "Engine/Engine.h"
#include "EngineUtils.h"
#include "Kismet/GameplayStatics.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Misc/App.h"
#include "Dom/JsonObject.h"
#include "Serialization/JsonSerializer.h"
#include "HAL/IConsoleManager.h"
#include "InputKeyEventArgs.h"
#include "Engine/SkeletalMesh.h"

IMPLEMENT_PRIMARY_GAME_MODULE(FDefaultGameModuleImpl, GameDemo, "GameDemo");

// Evaluate genuine UE animation assets and blend from the exact displayed pose.
// The animation system owns bone evaluation, skinning and animation tick ordering.
struct FGameDemoAnimProxy : FAnimInstanceProxy
{
    UAnimSequence* Sequence=nullptr;
    float Time=0, Blend=1, Age=0, Flinch=0, Speed=0;
    int32 Revision=-1;
    bool PlayerSecondaryMotion=false, NewPose=false;
    FName RootName, SpineName;
    FName AimSpineName, LeftArmName, RightArmName;
    FVector SkinForward=FVector::ForwardVector;
    float AimWeight=0;
    TArray<FTransform> LastPose, TransitionPose;
    FGameDemoAnimProxy(UAnimInstance* Instance):FAnimInstanceProxy(Instance){}
    virtual void PreUpdate(UAnimInstance* Instance,float Dt) override
    {
        FAnimInstanceProxy::PreUpdate(Instance,Dt);
        auto* F=Cast<AGameDemoFighter>(Instance->GetOwningActor());
        if(!F)return;
        Sequence=F->MotionClips.IsValidIndex(F->ActiveClip)?F->MotionClips[F->ActiveClip]:nullptr;
        RootName=F->MotionRootBone;SpineName=F->SpineBone;
        AimSpineName=F->AimSpineBone;LeftArmName=F->LeftArmBone;RightArmName=F->RightArmBone;SkinForward=F->GetImportedForward();
        AimWeight=FMath::FInterpTo(AimWeight,F->Locked&&F->ActiveClip>=1&&F->ActiveClip<=5?1.f:0.f,Dt,14);
        Time=F->ClipTime;Blend=F->PoseBlend;Flinch=F->Flinch;PlayerSecondaryMotion=!F->IsBoss;Speed=F->MotionSpeed;Age+=Dt;
        NewPose=Revision!=F->PoseRevision;Revision=F->PoseRevision;
    }
    virtual bool Evaluate(FPoseContext& Output) override
    {
        Output.ResetToRefPose();
        if(Sequence)
        {
            FAnimationPoseData Data(Output);
            Sequence->GetAnimationPose(Data,FAnimExtractContext(FMath::Clamp(Time,0.f,FMath::Max(.001f,Sequence->GetPlayLength()-.0001f)),false));
        }
        // FBX adds a rig parent above Root. UE's root lock only locks bone zero,
        // so remove travel from the actual motion root before blending poses.
        // CharacterMovement owns world translation; vertical pose and turns remain animated.
        const auto& Bones=Output.Pose.GetBoneContainer();
        for(FCompactPoseBoneIndex I:Output.Pose.ForEachBoneIndex())
        {
            const int32 RefIndex=Bones.MakeMeshPoseIndex(I).GetInt();
            if(Bones.GetReferenceSkeleton().GetBoneName(RefIndex)==RootName)
            {
                FVector P=Output.Pose[I].GetTranslation();
                const FVector Ref=Bones.GetRefPoseTransform(I).GetTranslation();
                P.X=Ref.X;P.Y=Ref.Y;Output.Pose[I].SetTranslation(P);
            }
        }
        const int32 Count=Output.Pose.GetNumBones();
        if(AimWeight>.001f)
        {
            TArray<FTransform> Component;Component.SetNum(Count);
            int32 Left=INDEX_NONE,Right=INDEX_NONE;TArray<int32> SpineIndices;
            auto Rebuild=[&]()
            {
                for(FCompactPoseBoneIndex I:Output.Pose.ForEachBoneIndex())
                {
                    const int32 Parent=Bones.GetParentBoneIndex(I).GetInt();
                    Component[I.GetInt()]=Parent==INDEX_NONE?Output.Pose[I]:Output.Pose[I]*Component[Parent];
                }
            };
            Rebuild();
            for(FCompactPoseBoneIndex I:Output.Pose.ForEachBoneIndex())
            {
                const FName Name=Bones.GetReferenceSkeleton().GetBoneName(Bones.MakeMeshPoseIndex(I).GetInt());
                if(Name==LeftArmName)Left=I.GetInt();if(Name==RightArmName)Right=I.GetInt();
                if(Name==AimSpineName||Name==SpineName)SpineIndices.Add(I.GetInt());
            }
            if(Left!=INDEX_NONE&&Right!=INDEX_NONE&&SpineIndices.Num())
            {
                const FVector Facing=FVector::CrossProduct(Component[Right].GetLocation()-Component[Left].GetLocation(),FVector::UpVector);
                const float Correction=FMath::Clamp(FMath::FindDeltaAngleDegrees(Facing.Rotation().Yaw,SkinForward.Rotation().Yaw),-75.f,75.f)*AimWeight;
                // Counter-turn the torso while preserving the authored sidestepping legs.
                for(int32 Index:SpineIndices)
                {
                    const FCompactPoseBoneIndex I(Index);const int32 Parent=Bones.GetParentBoneIndex(I).GetInt();
                    const FQuat ParentRotation=Parent==INDEX_NONE?FQuat::Identity:Component[Parent].GetRotation();
                    const FQuat Delta=ParentRotation.Inverse()*FQuat(FVector::UpVector,FMath::DegreesToRadians(Correction/SpineIndices.Num()))*ParentRotation;
                    Output.Pose[I].SetRotation(Delta*Output.Pose[I].GetRotation());Rebuild();
                }
            }
        }
        if(NewPose && LastPose.Num()==Count)TransitionPose=LastPose;
        if(TransitionPose.Num()==Count && Blend<1)
        {
            const float A=FMath::SmoothStep(0.f,1.f,Blend);
            for(FCompactPoseBoneIndex I:Output.Pose.ForEachBoneIndex())
            { FTransform P;P.Blend(TransitionPose[I.GetInt()],Output.Pose[I],A);Output.Pose[I]=P; }
        }
        for(FCompactPoseBoneIndex I:Output.Pose.ForEachBoneIndex())
        {
            const int32 RefIndex=Bones.MakeMeshPoseIndex(I).GetInt();
            const FName Name=Bones.GetReferenceSkeleton().GetBoneName(RefIndex);
            if(PlayerSecondaryMotion && Name.ToString().StartsWith(TEXT("Tail")))
            {
                float Amount=(.018f+FMath::Min(Speed/400.f,1.f)*.035f)*FMath::Sin(Age*4.f-RefIndex*.55f);
                Output.Pose[I].ConcatenateRotation(FQuat(FVector::RightVector,Amount));
            }
            if(Name==SpineName && Flinch>0)
                Output.Pose[I].ConcatenateRotation(FQuat(FVector::ForwardVector,-Flinch*.13f));
        }
        Output.Pose.NormalizeRotations();
        LastPose.SetNum(Count);
        for(FCompactPoseBoneIndex I:Output.Pose.ForEachBoneIndex())LastPose[I.GetInt()]=Output.Pose[I];
        NewPose=false;
        return true;
    }
};
UGameDemoAnim::UGameDemoAnim(){bUseMultiThreadedAnimationUpdate=false;}
FAnimInstanceProxy* UGameDemoAnim::CreateAnimInstanceProxy(){return new FGameDemoAnimProxy(this);}
void UGameDemoAnim::DestroyAnimInstanceProxy(FAnimInstanceProxy* P){delete P;}

AGameDemoFighter::AGameDemoFighter()
{
    PrimaryActorTick.bCanEverTick=true;
    GetCapsuleComponent()->InitCapsuleSize(34,88);
    GetCapsuleComponent()->SetCollisionResponseToChannel(ECC_Camera,ECR_Ignore);
    GetCharacterMovement()->bOrientRotationToMovement=false;
    GetCharacterMovement()->MaxWalkSpeed=320;
    GetCharacterMovement()->MaxAcceleration=1800;
    GetCharacterMovement()->BrakingDecelerationWalking=1600;
    GetCharacterMovement()->GroundFriction=8;
    GetCharacterMovement()->MaxStepHeight=40;
    GetCharacterMovement()->bRunPhysicsWithNoController=true;
    bUseControllerRotationYaw=false;
    GetMesh()->SetRelativeLocation(FVector(0,0,-88));
    GetMesh()->SetAnimationMode(EAnimationMode::AnimationBlueprint);
    GetMesh()->SetAnimInstanceClass(UGameDemoAnim::StaticClass());
    GetMesh()->VisibilityBasedAnimTickOption=EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;
    GetMesh()->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    GetMesh()->SetBoundsScale(1.5f);
    CameraBoom=CreateDefaultSubobject<USpringArmComponent>(TEXT("FollowBoom"));CameraBoom->SetupAttachment(RootComponent);
    CameraBoom->SetUsingAbsoluteRotation(true);CameraBoom->SetRelativeRotation(FRotator(-43.23f,-108.f,0));
    CameraBoom->TargetArmLength=3600;CameraBoom->TargetOffset=FVector::ZeroVector;
    CameraBoom->bDoCollisionTest=false;
    CameraBoom->bEnableCameraLag=false;
    Camera=CreateDefaultSubobject<UCameraComponent>(TEXT("FollowCamera"));Camera->SetupAttachment(CameraBoom);
    Camera->SetProjectionMode(ECameraProjectionMode::Orthographic);Camera->SetOrthoWidth(CameraWidthCm);
    Camera->SetAutoCalculateOrthoPlanes(true);
}
void AGameDemoFighter::BeginPlay()
{
    Super::BeginPlay();
    SpawnPosition=GetActorLocation();SpawnRotation=GetActorRotation();
    MaxHealth=ConfigHealth;Health=MaxHealth;
    // Apply the follow contract to existing placed actors as well as new actors.
    CameraBoom->TargetArmLength=3600;CameraBoom->TargetOffset=FVector::ZeroVector;CameraBoom->SocketOffset=FVector::ZeroVector;
    CameraBoom->bDoCollisionTest=false;CameraBoom->bEnableCameraLag=false;CameraBoom->bEnableCameraRotationLag=false;
    CameraBoom->SetWorldRotation(FRotator(CameraPitch,CameraYaw,0));
    Camera->SetProjectionMode(ECameraProjectionMode::Orthographic);Camera->SetOrthoWidth(CameraWidthCm);
    GetMesh()->AddTickPrerequisiteComponent(GetCharacterMovement());
    CameraBoom->AddTickPrerequisiteComponent(GetCharacterMovement());
    const float HalfHeight=CharacterHeightCm*.49f;
    GetCapsuleComponent()->SetCapsuleSize(CharacterHeightCm*.19f,HalfHeight);
    GetMesh()->SetRelativeLocation(FVector(0,0,-HalfHeight));
    FacingCalibrated=CalibrateFacing();
    if(IsBoss)GetCharacterMovement()->MaxWalkSpeed=205;
    if(StrikeBones.Num()!=4)StrikeBones={TEXT("R_Hand"),TEXT("L_Hand"),TEXT("R_Foot"),TEXT("L_Foot")};
    GetMesh()->SetAnimInstanceClass(UGameDemoAnim::StaticClass());
    for(TActorIterator<AGameDemoFighter> I(GetWorld());I;++I)if(I->IsBoss!=IsBoss)Opponent=*I;
    StartAction(TEXT("idle"),0);
    QAMode=FParse::Param(FCommandLine::Get(),TEXT("GameDemoTest"));
    MovementQAMode=FParse::Param(FCommandLine::Get(),TEXT("GameDemoMovementTest"));
    HitQAMode=FParse::Param(FCommandLine::Get(),TEXT("GameDemoHitTest"));
    FacingQAMode=FParse::Param(FCommandLine::Get(),TEXT("GameDemoFacingTest"));
    ArtQAMode=FParse::Param(FCommandLine::Get(),TEXT("GameDemoArtReview"));
    RoamQAMode=FParse::Param(FCommandLine::Get(),TEXT("GameDemoExplorationTest"));
    if(RoamQAMode){FApp::SetUseFixedTimeStep(true);FApp::SetFixedDeltaTime(1.0/60.0);}
    if(FacingQAMode)FacingSamples.SetNum(20);
    if(!IsBoss){if(auto* PC=UGameplayStatics::GetPlayerController(this,0)){PC->Possess(this);PC->SetViewTarget(this);PC->SetInputMode(FInputModeGameOnly());PC->bShowMouseCursor=false;}
        OrbitYaw=CameraYaw;SavedIsoYaw=CameraYaw;ThirdPersonDistance=CharacterHeightCm*2.8f;
        FString RequestedView;FParse::Value(FCommandLine::Get(),TEXT("PipelineCamera="),RequestedView);
        if(RequestedView==TEXT("first"))SetViewMode(0);else if(RequestedView==TEXT("third"))SetViewMode(1);else SetViewMode(2);
    }
}
float AGameDemoFighter::ClipLength(int32 I)const{return MotionClips.IsValidIndex(I)&&MotionClips[I]?MotionClips[I]->GetPlayLength():1.f;}
bool AGameDemoFighter::IsAttacking()const{return ActiveClip>=6&&ActiveClip<=9;}
bool AGameDemoFighter::CanAct()const{return Action==TEXT("idle")||Action==TEXT("move")||Action==TEXT("guard");}
void AGameDemoFighter::StartAction(const FString& Name,int32 Clip,float PlayRate,float BlendTime)
{
    Action=Name;ActiveClip=Clip;Rate=PlayRate;ClipTime=0;ActionTime=0;
    ActionDuration=ClipLength(Clip)/FMath::Max(.05f,Rate);PoseBlend=0;PoseBlendDuration=BlendTime;PoseRevision++;
    HitActors.Reset();Connected=false;VisitedActions.Add(Name);
    const TArray<FName>& Names=StrikeBones;
    for(int i=0;i<4;i++)LastHands[i]=GetMesh()->GetSocketLocation(Names[i]);
    if(IsAttacking()){LastAttackAge=WorldAge;Guarding=false;}
}
void AGameDemoFighter::LightAttack()
{
    if(Health<=0)return;
    if(CanAct()&&Stamina>=10){Stamina-=10;StartAction(TEXT("light1"),6,IsBoss?.86f:1.13f,.11f);}
    else if(IsAttacking()&&ActiveClip<9){QueuedLight=true;BufferedTime=.8f;}
}
void AGameDemoFighter::HeavyAttack()
{
    if(CanAct()&&Stamina>=25){Stamina-=25;StartAction(TEXT("heavy"),9,IsBoss?.82f:1.03f,.16f);}
}
void AGameDemoFighter::Evade()
{
    if(Stamina<18||Health<=0||Action==TEXT("stagger")||Action==TEXT("dodge"))return;
    if(IsAttacking()&&ActionTime<ActionDuration*.62f)return;
    Stamina-=18;DashDirection=MoveDirection.IsNearlyZero()?-GetActorForwardVector():MoveDirection;
    StartAction(TEXT("dodge"),10,1.1f,.07f);DodgeCount++;QueuedLight=false;
}
void AGameDemoFighter::UpdatePlayer(float Dt)
{
    auto* PC=Cast<APlayerController>(GetController());if(!PC)return;
    if(RoamQAMode){UpdateExplorationQA(Dt);return;}
    if(PC->WasInputKeyJustPressed(EKeys::R)){ResetDuel();return;}
    UpdateViewInput(Dt);
    if(Health<=0)return;
    if(PC->WasInputKeyJustPressed(EKeys::Tab))
    {
        const bool InRange=Opponent&&(!IsExploring()||FVector::Dist2D(GetActorLocation(),Opponent->SpawnPosition)<Opponent->EncounterRadiusCm);
        Locked=InRange&&!Locked;
        if(Locked){Engaged=true;Opponent->Engaged=true;}
    }
    const FRotator Flat(0,CameraBoom->GetComponentRotation().Yaw,0);
    const FVector Front=FRotationMatrix(Flat).GetUnitAxis(EAxis::X),Right=FRotationMatrix(Flat).GetUnitAxis(EAxis::Y);
    MoveDirection=(Front*((PC->IsInputKeyDown(EKeys::W)?1:0)-(PC->IsInputKeyDown(EKeys::S)?1:0))+Right*((PC->IsInputKeyDown(EKeys::D)?1:0)-(PC->IsInputKeyDown(EKeys::A)?1:0))).GetSafeNormal();
    const bool Guard=PC->IsInputKeyDown(EKeys::C);
    if(Guard&&!Guarding)GuardAge=0;
    Guarding=Guard&&CanAct();
    if(PC->WasInputKeyJustPressed(EKeys::J)||PC->WasInputKeyJustPressed(EKeys::LeftMouseButton))LightAttack();
    if(PC->WasInputKeyJustPressed(EKeys::K)||PC->WasInputKeyJustPressed(EKeys::RightMouseButton))HeavyAttack();
    if(PC->WasInputKeyJustPressed(EKeys::SpaceBar))Evade();
    if(PC->WasInputKeyJustPressed(EKeys::T)&&CanAct()&&Flasks>0&&Health<MaxHealth){Health=FMath::Min(MaxHealth,Health+65);Flasks--;}
    if(PC->WasInputKeyJustPressed(EKeys::F)&&Opponent&&Opponent->Action==TEXT("stagger")&&FVector::Dist2D(GetActorLocation(),Opponent->GetActorLocation())<220&&CanAct())
    {StartAction(TEXT("riposte"),9,1.3f,.1f);}
    if(CanAct())
    {
        GetCharacterMovement()->MaxWalkSpeed=Guarding?145:(PC->IsInputKeyDown(EKeys::LeftShift)&&!Locked?490:300);
        AddMovementInput(MoveDirection);
        if(Locked&&Opponent&&Opponent->Health>0)SetActorRotation(FMath::RInterpTo(GetActorRotation(),(Opponent->GetActorLocation()-GetActorLocation()).Rotation(),Dt,11).Clamp());
        else if(ViewMode==0)SetActorRotation(FRotator(0,CameraBoom->GetComponentRotation().Yaw,0));
        else if(!MoveDirection.IsNearlyZero())SetActorRotation(FMath::RInterpTo(GetActorRotation(),MoveDirection.Rotation(),Dt,12));
        auto Rot=GetActorRotation();Rot.Pitch=0;Rot.Roll=0;SetActorRotation(Rot);
    }
}
void AGameDemoFighter::UpdateBoss(float Dt)
{
    if(ArtQAMode||FParse::Param(FCommandLine::Get(),TEXT("GameDemoCameraTest")))return;
    if(FacingQAMode&&Opponent&&!Opponent->FacingQAComplete)
    {
        if(Opponent->FacingCase<16)return;
        Engaged=true;Cooldown=100;
    }
    if(HitQAMode&&Opponent&&!Opponent->HitQAComplete)return;
    if(MovementQAMode&&Opponent&&!Opponent->MovementQAComplete)return;
    if(!Opponent||Opponent->Health<=0||Health<=0)return;
    if(EncounterRadiusCm>0)
    {
        if(Engaged&&!ReturningHome&&(FVector::Dist2D(Opponent->GetActorLocation(),SpawnPosition)>EncounterRadiusCm||FVector::Dist2D(GetActorLocation(),SpawnPosition)>EncounterRadiusCm))
        {
            ReturningHome=true;Engaged=false;Opponent->Locked=false;Opponent->Engaged=false;
            BossChainRemaining=0;QueuedLight=false;QueuedHeavy=false;HitPause=0;Guarding=false;StartAction(TEXT("idle"),0,1,.22f);
        }
        if(ReturningHome)
        {
            const FVector Home=SpawnPosition-GetActorLocation();
            if(Home.Size2D()>45)
            {
                MoveDirection=Home.GetSafeNormal2D();AddMovementInput(MoveDirection,1,true);
                SetActorRotation(FMath::RInterpTo(GetActorRotation(),FRotator(0,Home.Rotation().Yaw,0),Dt,5));
            }
            else
            {
                ReturningHome=false;GetCharacterMovement()->StopMovementImmediately();MoveDirection=FVector::ZeroVector;
                Health=MaxHealth;Poise=0;Stamina=100;Cooldown=1.4f;
            }
            return;
        }
    }
    const FVector To=Opponent->GetActorLocation()-GetActorLocation();const float Dist=To.Size2D();
    if(Dist<380)Engaged=true;
    if(!Engaged)return;
    if(CanAct())
    {
        FRotator Facing=To.Rotation();Facing.Pitch=0;Facing.Roll=0;SetActorRotation(FMath::RInterpTo(GetActorRotation(),Facing,Dt,5));
        if(Dist>185){MoveDirection=To.GetSafeNormal2D();AddMovementInput(MoveDirection,1,true);}
        else
        {
            MoveDirection=FVector::ZeroVector;
            if(Cooldown<=0)
            {
                BossPattern++;BossChainRemaining=(BossPattern%3==0?2:BossPattern%3==1?1:0);
                if(BossPattern%4==0){BossChainRemaining=0;HeavyAttack();}
                else {Stamina=100;LightAttack();}
                Cooldown=(Health<MaxHealth*.55f?1.15f:1.65f);
            }
        }
    }
    else if(IsAttacking()&&ActionTime<ActionDuration*.18f)
    {auto Facing=To.Rotation();Facing.Pitch=0;Facing.Roll=0;SetActorRotation(FMath::RInterpTo(GetActorRotation(),Facing,Dt,4));}
}
float AGameDemoFighter::MeleeSeparationCm() const
{
    if(!Opponent)return 0;
    // A capsule covers the body, not the animated armour/arms leaning forward.
    // Preserve a proportionate working gap without changing collision shapes.
    return GetCapsuleComponent()->GetScaledCapsuleRadius()+Opponent->GetCapsuleComponent()->GetScaledCapsuleRadius()
        +FMath::Min(CharacterHeightCm,Opponent->CharacterHeightCm)*.30f;
}
void AGameDemoFighter::UpdateMotion(float Dt)
{
    if(CanAct())
    {
        const float Speed=GetVelocity().Size2D();int32 Want=0;
        if(Guarding)Want=6;
        else if(Speed>12)
        {
            const FVector Local=GetActorTransform().InverseTransformVectorNoScale(GetVelocity());
            Want=(!Locked&&!IsBoss)?(Speed>360?5:1):FMath::Abs(Local.Y)>FMath::Abs(Local.X)?(Local.Y>0?4:3):(Local.X<0?2:(Speed>360?5:1));
        }
        if(ActiveClip!=Want)
        {
            const bool KeepPhase=ActiveClip>=1&&ActiveClip<=5&&Want>=1&&Want<=5;
            const float Phase=ClipTime/ClipLength(ActiveClip);
            StartAction(Guarding?TEXT("guard"):Want?TEXT("move"):TEXT("idle"),Want,1,.18f);
            if(KeepPhase)ClipTime=Phase*ClipLength(Want);
        }
        Action=Guarding?TEXT("guard"):Want?TEXT("move"):TEXT("idle");
        if(Guarding)ClipTime=ClipLength(6)*.13f;
        else{float R=Want==0?1:Speed/(Want==5?RunStrideSpeed:WalkStrideSpeed);ClipTime=FMath::Fmod(ClipTime+Dt*R,ClipLength(ActiveClip));}
        return;
    }
    ActionTime+=Dt;ClipTime=FMath::Min(ActionTime*Rate,ClipLength(ActiveClip)-.0001f);
    const float T=ActionTime/FMath::Max(.01f,ActionDuration);
    if(Action==TEXT("dodge"))
    {if(T>.08f&&T<.68f)AddActorWorldOffset(DashDirection*(IsBoss?650.f:620.f)*Dt,true);}
    else if(IsAttacking())
    {
        if(T>.15f&&T<.47f)
        {
            FVector Step=GetActorForwardVector()*(IsBoss?155.f:100.f)*Dt;
            if(Opponent&&Opponent->Health>0)
            {
                const FVector To=Opponent->GetActorLocation()-GetActorLocation();
                const FVector Inward=To.GetSafeNormal2D();
                const float Closing=FMath::Max(0.f,FVector::DotProduct(Step,Inward));
                const float Room=FMath::Max(0.f,To.Size2D()-MeleeSeparationCm());
                const float Ease=FMath::Clamp(Room/30.f,0.f,1.f);
                // Ease just the inward lunge; preserve lateral motion, the full
                // skeletal action, sweep collision and measured hand strikes.
                Step-=Inward*(Closing-FMath::Min(Closing*Ease,Room));
            }
            AddActorWorldOffset(Step,true);
        }
        if(T>.20f&&T<.76f)TraceStrike();
        if(T>.80f&&ActiveClip<8&&((QueuedLight&&BufferedTime>0)||BossChainRemaining>0))
        {
            int32 Next=ActiveClip+1;
            if(IsBoss)BossChainRemaining--;else if(Stamina<10)return;else Stamina-=10;
            QueuedLight=false;StartAction(Next==7?TEXT("light2"):TEXT("light3"),Next,IsBoss?(Health<MaxHealth*.55f?.98f:.87f):1.13f,.10f);return;
        }
    }
    if(ActionTime>=ActionDuration&&Action!=TEXT("death"))FinishAction();
}
void AGameDemoFighter::FinishAction()
{
    QueuedLight=false;StartAction(TEXT("idle"),0,1,.18f);
}
void AGameDemoFighter::TraceStrike()
{
    const TArray<FName>& Names=StrikeBones;
    for(int i=0;i<4;i++)
    {
        FVector Now=GetMesh()->GetSocketLocation(Names[i]);
        FCollisionQueryParams Params(SCENE_QUERY_STAT(GameDemoStrike),false,this);
        FCollisionObjectQueryParams Objects;Objects.AddObjectTypesToQuery(ECC_Pawn);
        TArray<FHitResult> Hits;
        GetWorld()->SweepMultiByObjectType(Hits,LastHands[i],Now,FQuat::Identity,Objects,FCollisionShape::MakeSphere(IsBoss?34:24),Params);
        LastHands[i]=Now;
        for(const auto& H:Hits)if(auto* Target=Cast<AGameDemoFighter>(H.GetActor()))
        {
            if(Target==this||HitActors.Contains(Target))continue;
            HitActors.Add(Target);
            float Damage=IsBoss?(ActiveClip==9?38:22):(Action==TEXT("riposte")?150:ActiveClip==9?67:ActiveClip==8?37:ActiveClip==7?28:24);
            Target->ReceiveStrike(this,Damage,ActiveClip==9?48:ActiveClip==8?30:20);
        }
    }
}
void AGameDemoFighter::ReceiveStrike(AGameDemoFighter* A,float Damage,float Impact)
{
    if(Health<=0||Action==TEXT("death"))return;
    if(Action==TEXT("dodge")&&ActionTime>.035f&&ActionTime<ActionDuration*.72f)return;
    FVector Toward=(A->GetActorLocation()-GetActorLocation()).GetSafeNormal2D();
    bool Front=FVector::DotProduct(GetActorForwardVector(),Toward)>.15f;
    if(!IsBoss&&Guarding&&Front)
    {
        if(GuardAge<.23f)
        {
            ParryCount++;A->Poise=0;A->StartAction(TEXT("stagger"),11,.5f,.08f);A->HitPause=.07f;HitPause=.04f;return;
        }
        if(Stamina>Impact*.7f){Stamina-=Impact*.7f;Damage*=.12f;Flinch=.6f;}
        else {Stamina=0;Guarding=false;StartAction(TEXT("stagger"),11,.85f,.06f);}
    }
    Health=FMath::Max(0.f,Health-Damage);A->HitCount++;Flinch=1;HitPause=.045f;A->HitPause=.045f;Engaged=true;
    Poise+=Impact;
    if(Health<=0){StartAction(TEXT("death"),13,IsBoss?.9f:1.f,.14f);GetCharacterMovement()->StopMovementImmediately();GetCharacterMovement()->DisableMovement();GetCapsuleComponent()->SetCollisionResponseToChannel(ECC_Pawn,ECR_Ignore);}
    else if(IsBoss&&Poise>=100){Poise=0;StartAction(TEXT("stagger"),11,.55f,.10f);Cooldown=2;BossChainRemaining=0;}
    else if(!IsBoss&&!Guarding)StartAction(TEXT("hit"),12,1.25f,.055f);
    else if(IsBoss&&CanAct())StartAction(TEXT("hit"),12,1.25f,.075f);
}
void AGameDemoFighter::ResetDuel()
{
    for(TActorIterator<AGameDemoFighter> I(GetWorld());I;++I)
    {
        auto* F=*I;F->SetActorLocationAndRotation(F->SpawnPosition,F->SpawnRotation);F->Health=F->MaxHealth;F->Stamina=100;F->Poise=0;
        F->HitPause=0;F->Engaged=false;F->ReturningHome=false;F->Locked=false;F->Guarding=false;F->Flasks=2;F->BossChainRemaining=0;F->Cooldown=1.4f;
        F->GetCapsuleComponent()->SetCollisionEnabled(ECollisionEnabled::QueryAndPhysics);F->GetCapsuleComponent()->SetCollisionResponseToChannel(ECC_Pawn,ECR_Block);F->GetCharacterMovement()->SetMovementMode(MOVE_Walking);F->GetCharacterMovement()->StopMovementImmediately();F->StartAction(TEXT("idle"),0);
    }
}
void AGameDemoFighter::Tick(float Dt)
{
    Super::Tick(Dt);WorldAge+=Dt;
    if(FParse::Param(FCommandLine::Get(),TEXT("PipelineExit")) && ((QAWritten && WorldAge>43) || (MovementQAComplete && WorldAge>38) || (HitQAComplete && WorldAge>42))) { FPlatformMisc::RequestExit(false); return; }
    Cooldown-=Dt;BufferedTime-=Dt;GuardAge+=Dt;
    PoseBlend=FMath::Min(1.f,PoseBlend+Dt/FMath::Max(.02f,PoseBlendDuration));Flinch=FMath::Max(0.f,Flinch-Dt*4);
    if(!Opponent)for(TActorIterator<AGameDemoFighter>I(GetWorld());I;++I)if(I->IsBoss!=IsBoss)Opponent=*I;
    if(MovementQAMode&&!IsBoss&&!MovementQAComplete)UpdateMovementQA(Dt);
    if(FacingQAMode&&!IsBoss&&!FacingQAComplete)UpdateFacingQA(Dt);
    if(ArtQAMode&&!IsBoss)UpdateArtQA();
    UpdateExploration(Dt);
    if(!IsBoss){if(HitQAMode&&!HitQAComplete)UpdateHitQA(Dt);else UpdatePlayer(Dt);}else UpdateBoss(Dt);
    if(HitPause>0){HitPause-=Dt;GetCharacterMovement()->StopMovementImmediately();return;}
    if(!IsAttacking()&&Action!=TEXT("dodge")&&GuardAge>.4f)Stamina=FMath::Min(100.f,Stamina+Dt*(IsBoss?70:23));
    if(WorldAge-LastAttackAge>4)Poise=FMath::Max(0.f,Poise-Dt*12);
    MotionSpeed=GetVelocity().Size2D();UpdateMotion(Dt);
    if(QAMode&&!IsBoss&&!QAWritten)
    {
        QATime+=Dt;QABotClock+=Dt;
        if(QATime>3 && QATime<31){QAFrames++;QADeltaSum+=Dt;}
        auto StandingHeight=[](AGameDemoFighter* F){return F->GetMesh()->GetSocketLocation(F->HeadBone).Z-F->GetMesh()->GetSocketLocation(F->FootBone).Z;};
        if(QAStage==0 && QATime>2)
        {
            QAInitialHeight=StandingHeight(this);QABossInitialHeight=Opponent?StandingHeight(Opponent):0;QAStage=1;
            if(!FParse::Param(FCommandLine::Get(),TEXT("DatasetCapture")))if(auto* PC=Cast<APlayerController>(GetController()))PC->ConsoleCommand(TEXT("HighResShot 1"));
        }
        if(QATime>4 && QATime<31)
        {
            if(Opponent){Health=FMath::Max(Health,70.f);Opponent->Health=FMath::Max(Opponent->Health,250.f);Locked=true;Opponent->Engaged=true;
                // The capture bot supplies view input as well as movement. Normal
                // gameplay keeps free look; all capture passes share this camera.
                if(ViewMode!=2 && FParse::Param(FCommandLine::Get(),TEXT("DatasetCapture")))
                {
                    const FVector Target=Opponent->GetMesh()->GetSocketLocation(Opponent->SpineBone);
                    const FVector Pivot=CameraBoom->GetComponentLocation()+CameraBoom->TargetOffset;
                    FRotator Desired=(Target-Pivot).Rotation();
                    Desired.Pitch=ViewMode==0?FMath::Clamp(Desired.Pitch,-65.f,65.f):-18.f;
                    Desired.Roll=0;
                    const FRotator View=FMath::RInterpTo(CameraBoom->GetComponentRotation(),Desired,Dt,6);
                    CameraBoom->SetWorldRotation(View);OrbitYaw=View.Yaw;OrbitPitch=View.Pitch;
                }
                const FVector D=Opponent->GetActorLocation()-GetActorLocation();
                if(CanAct())
                {
                    const bool Capture=FParse::Param(FCommandLine::Get(),TEXT("DatasetCapture"));
                    const float Separation=MeleeSeparationCm();
                    const float Approach=Capture?FMath::Max(140.f,Separation+18.f):140.f;
                    if(D.Size2D()>Approach)AddMovementInput(D.GetSafeNormal2D());
                    else if(Capture&&D.Size2D()<Separation+3.f)AddMovementInput(-D.GetSafeNormal2D());
                }}
            Stamina=100;
            if(QATime<23 && QABotClock>.27f){LightAttack();QABotClock=0;}
            else if(QATime>24 && QATime<27 && CanAct())HeavyAttack();
            else if(QATime>28 && QATime<30 && CanAct())Evade();
        }
        if(QAStage==1 && QATime>22)
        {QAStage=2;if(!FParse::Param(FCommandLine::Get(),TEXT("DatasetCapture")))if(auto* PC=Cast<APlayerController>(GetController()))PC->ConsoleCommand(TEXT("HighResShot 1"));}
        if(QAStage==2 && QATime>33 && Opponent)
        {Guarding=false;ReceiveStrike(Opponent,1000,0);QADeathZ=GetActorLocation().Z;QAStage=3;}
        if(QAStage==3)
        {
            QADeathDrop=FMath::Max(QADeathDrop,QADeathZ-GetActorLocation().Z);
            if(QATime>37){ResetDuel();QAStage=4;}
        }
        if(QAStage==4 && QATime>39){QAResetHeight=StandingHeight(this);WriteQA();}
    }
}
void AGameDemoFighter::UpdateMovementQA(float Dt)
{
    MovementQAAge+=Dt;
    auto* PC=Cast<APlayerController>(GetController());if(!PC)return;
    TSet<FKey> Wanted;
    const float T=MovementQAAge;
    if(T>=2 && T<7)Wanted.Add(EKeys::S);
    else if(T<12 && T>=7)Wanted.Add(EKeys::W);
    else if(T<15.5f && T>=12){Wanted.Add(EKeys::S);Wanted.Add(EKeys::LeftShift);}
    else if(T<19 && T>=15.5f){Wanted.Add(EKeys::W);Wanted.Add(EKeys::LeftShift);}
    else if(T<21 && T>=19)Wanted.Add(EKeys::D);
    else if(T<23 && T>=21)Wanted.Add(EKeys::A);
    else if(T<25 && T>=23){Wanted.Add(EKeys::S);Wanted.Add(EKeys::D);}
    else if(T<27 && T>=25){Wanted.Add(EKeys::W);Wanted.Add(EKeys::A);}
    else if(T<29 && T>=27){Wanted.Add(EKeys::D);Locked=true;}
    else if(T<31 && T>=29){Wanted.Add(EKeys::A);Locked=false;}
    for(const FKey& K:MovementQAKeys)if(!Wanted.Contains(K))PC->InputKey(FInputKeyEventArgs::CreateSimulated(K,IE_Released,0));
    for(const FKey& K:Wanted)if(!MovementQAKeys.Contains(K))PC->InputKey(FInputKeyEventArgs::CreateSimulated(K,IE_Pressed,1));
    MovementQAKeys=Wanted;
    if(T>33){WriteMovementQA();MovementQAComplete=true;ResetDuel();}
}
void AGameDemoFighter::SampleMovementQA(const FVector2D& ScreenOffset)
{
    if(!MovementQAMode||MovementQAComplete||MovementQAAge<2||MovementQAAge>32)return;
    const FVector RootLocal=GetMesh()->GetSocketTransform(MotionRootBone,RTS_Component).GetLocation();
    const FVector HipLocal=GetMesh()->GetSocketTransform(HipBone,RTS_Component).GetLocation();
    MaxRootTravel=FMath::Max(MaxRootTravel,static_cast<float>(RootLocal.Size2D()));
    MaxCenterError=FMath::Max(MaxCenterError,static_cast<float>(ScreenOffset.Size()));
    if(MovementQAFrames>0)
    {
        MaxHipStep=FMath::Max(MaxHipStep,static_cast<float>(FVector::Dist(HipLocal,PreviousHipLocal)));
        MaxWorldStep=FMath::Max(MaxWorldStep,static_cast<float>(FVector::Dist(GetActorLocation(),PreviousMovementPosition)));
    }
    if(ActiveClip>=1&&ActiveClip<=5&&PreviousMovementClip==ActiveClip&&ClipTime<PreviousMovementClipTime)MovementQALoops++;
    PreviousMovementClip=ActiveClip;PreviousMovementClipTime=ClipTime;
    PreviousHipLocal=HipLocal;PreviousMovementPosition=GetActorLocation();MovementQAFrames++;MovementQASampledTime+=GetWorld()->GetDeltaSeconds();
}
void AGameDemoFighter::WriteMovementQA()
{
    auto O=MakeShared<FJsonObject>();
    O->SetNumberField(TEXT("rendered_frames"),MovementQAFrames);O->SetNumberField(TEXT("fps"),MovementQAFrames/FMath::Max(.01f,MovementQASampledTime));
    O->SetNumberField(TEXT("completed_locomotion_loops"),MovementQALoops);
    O->SetNumberField(TEXT("maximum_motion_root_offset_cm"),MaxRootTravel);
    O->SetNumberField(TEXT("maximum_local_hip_step_cm"),MaxHipStep);
    O->SetNumberField(TEXT("maximum_world_step_cm"),MaxWorldStep);
    O->SetNumberField(TEXT("maximum_player_center_error_pixels"),MaxCenterError);
    O->SetBoolField(TEXT("no_root_motion_snap"),MaxRootTravel<.1f&&MaxHipStep<25&&MovementQALoops>=8);
    O->SetBoolField(TEXT("player_stays_centered"),MaxCenterError<2);
    TArray<TSharedPtr<FJsonValue>> Names;for(const auto& N:VisitedActions)Names.Add(MakeShared<FJsonValueString>(N));O->SetArrayField(TEXT("states"),Names);
    FString Json;auto W=TJsonWriterFactory<>::Create(&Json);FJsonSerializer::Serialize(O,W);FFileHelper::SaveStringToFile(Json,*(FPaths::ProjectSavedDir()/TEXT("GameDemoMovementQA.json")));
}
void AGameDemoFighter::UpdateHitQA(float Dt)
{
    HitQAAge+=Dt;
    if(HitQAAge>=HitQANext && HitQAStrikes<16 && Opponent)
    {
        Health=MaxHealth;Opponent->Health=Opponent->MaxHealth;
        Guarding=false;Opponent->Guarding=false;
        ReceiveStrike(Opponent,1,20);Opponent->ReceiveStrike(this,1,20);
        if(HitQAStrikes%2==1)
        {
            StartAction(TEXT("stagger"),11,.85f,.08f);
            Opponent->StartAction(TEXT("stagger"),11,.85f,.10f);
        }
        ++HitQAStrikes;HitQANext+=2.1f;
    }
    if(HitQAAge>38){HitQAComplete=true;WriteHitQA();ResetDuel();}
}
void AGameDemoFighter::SampleHitQA(const FVector2D& ScreenOffset)
{
    if(!HitQAMode||HitQAComplete||HitQAAge<2)return;
    const double Now=FPlatformTime::Seconds();
    if(HitQALastFrame>0)HitQAFrameTimes.Add(static_cast<float>((Now-HitQALastFrame)*1000));
    HitQALastFrame=Now;++HitQAFrames;
    HitMaxCenterError=FMath::Max(HitMaxCenterError,static_cast<float>(ScreenOffset.Size()));
    for(auto* F:{this,Opponent.Get()})
    {
        if(!F)continue;
        if(!F->GetMesh()->IsVisible()||F->IsHidden())++HitQAInvisibleFrames;
        if(F->ActiveClip!=11&&F->ActiveClip!=12)continue;
        ++HitQAReactionFrames;
        for(const FTransform& Bone:F->GetMesh()->GetComponentSpaceTransforms())
            HitMinScale=FMath::Min(HitMinScale,static_cast<float>(Bone.GetScale3D().GetAbsMin()));
        const float H=F->GetMesh()->GetSocketLocation(F->HeadBone).Z-F->GetMesh()->GetSocketLocation(F->FootBone).Z;
        HitMinHeight=FMath::Min(HitMinHeight,H/(F->CharacterHeightCm/180.f));
    }
}
void AGameDemoFighter::WriteHitQA()
{
    auto O=MakeShared<FJsonObject>();
    O->SetNumberField(TEXT("repeated_strikes_per_character"),HitQAStrikes);
    O->SetNumberField(TEXT("rendered_frames"),HitQAFrames);
    O->SetNumberField(TEXT("reaction_frames"),HitQAReactionFrames);
    O->SetNumberField(TEXT("minimum_component_bone_scale"),HitMinScale);
    O->SetNumberField(TEXT("minimum_normalized_head_height_cm"),HitMinHeight);
    O->SetNumberField(TEXT("hidden_frames"),HitQAInvisibleFrames);
    O->SetNumberField(TEXT("maximum_center_error_pixels"),HitMaxCenterError);
    O->SetBoolField(TEXT("hit_pose_stays_visible"),HitQAStrikes==16&&HitQAReactionFrames>200&&HitMinScale>.8f&&HitMinHeight>60&&HitQAInvisibleFrames==0);
    HitQAFrameTimes.Sort();double Sum=0;for(float T:HitQAFrameTimes)Sum+=T;
    if(HitQAFrameTimes.Num())
    {
        O->SetNumberField(TEXT("real_average_fps"),1000*HitQAFrameTimes.Num()/Sum);
        O->SetNumberField(TEXT("frame_time_p99_ms"),HitQAFrameTimes[FMath::Min(HitQAFrameTimes.Num()-1,FMath::FloorToInt(HitQAFrameTimes.Num()*.99f))]);
    }
    FString Json;auto W=TJsonWriterFactory<>::Create(&Json);FJsonSerializer::Serialize(O,W);
    FFileHelper::SaveStringToFile(Json,*(FPaths::ProjectSavedDir()/TEXT("GameDemoHitQA.json")));
}
void AGameDemoFighter::WriteQA()
{
    QAWritten=true;auto O=MakeShared<FJsonObject>();O->SetNumberField(TEXT("seconds"),QADeltaSum);O->SetNumberField(TEXT("frames"),QAFrames);O->SetNumberField(TEXT("fps"),QAFrames/FMath::Max(.01f,QADeltaSum));
    O->SetNumberField(TEXT("player_hits"),HitCount);O->SetNumberField(TEXT("boss_hits"),Opponent?Opponent->HitCount:0);
    O->SetNumberField(TEXT("initial_player_head_above_foot_cm"),QAInitialHeight);O->SetNumberField(TEXT("initial_boss_head_above_foot_cm"),QABossInitialHeight);
    O->SetNumberField(TEXT("death_capsule_drop_cm"),QADeathDrop);O->SetNumberField(TEXT("reset_player_head_above_foot_cm"),QAResetHeight);
    O->SetNumberField(TEXT("dodges"),DodgeCount);
    O->SetBoolField(TEXT("upright_initial_and_reset"),QAInitialHeight>CharacterHeightCm*.5f && QABossInitialHeight>(Opponent?Opponent->CharacterHeightCm*.5f:0) && QAResetHeight>CharacterHeightCm*.5f);
    O->SetBoolField(TEXT("death_stays_on_ground"),QADeathDrop<2);
    TArray<TSharedPtr<FJsonValue>> Names;for(const auto& N:VisitedActions)Names.Add(MakeShared<FJsonValueString>(N));O->SetArrayField(TEXT("player_states"),Names);
    Names.Reset();if(Opponent)for(const auto& N:Opponent->VisitedActions)Names.Add(MakeShared<FJsonValueString>(N));O->SetArrayField(TEXT("boss_states"),Names);
    FString Json;auto W=TJsonWriterFactory<>::Create(&Json);FJsonSerializer::Serialize(O,W);FFileHelper::SaveStringToFile(Json,*(FPaths::ProjectSavedDir()/TEXT("GameDemoQA.json")));
    if(auto* PC=Cast<APlayerController>(GetController()))PC->ConsoleCommand(TEXT("HighResShot 1"));
    ResetDuel();
}
AGameDemoGameMode::AGameDemoGameMode(){DefaultPawnClass=nullptr;HUDClass=AGameDemoHUD::StaticClass();}
void AGameDemoGameMode::BeginPlay()
{
    Super::BeginPlay();
    ConfigurePipelineFramePacing();
    if(auto* V=IConsoleManager::Get().FindConsoleVariable(TEXT("t.MaxFPS")))V->Set(60.f);
    if(auto* PC=UGameplayStatics::GetPlayerController(this,0))for(TActorIterator<AGameDemoFighter>I(GetWorld());I;++I)if(!I->IsBoss){PC->Possess(*I);PC->SetViewTarget(*I);break;}
    if(FParse::Param(FCommandLine::Get(),TEXT("DatasetCapture")))GetWorld()->SpawnActor<APipelineCapture>();
    if(FParse::Param(FCommandLine::Get(),TEXT("GameDemoCameraTest")))GetWorld()->SpawnActor<APipelineCameraQA>();
}
void AGameDemoHUD::DrawHUD()
{
    Super::DrawHUD();if(!Canvas)return;
    auto* P=Cast<AGameDemoFighter>(GetOwningPawn());if(!P)return;
    const float W=Canvas->SizeX,H=Canvas->SizeY,S=FMath::Clamp(W/1440.f,.65f,1.5f);
    const FVector Projected=Canvas->Project(P->GetActorLocation());P->SampleMovementQA(FVector2D(Projected.X-W*.5f,Projected.Y-H*.5f));P->SampleHitQA(FVector2D(Projected.X-W*.5f,Projected.Y-H*.5f));P->SampleFacingQA();
    auto Text=[&](const FString& T,float X,float Y,FLinearColor C,float Scale){DrawText(T,C,X,Y,GEngine->GetSmallFont(),Scale*S,false);};
    auto Bar=[&](float X,float Y,float Width,float Value,FLinearColor C){DrawRect(FLinearColor(.018f,.022f,.027f,.88f),X-2,Y-2,Width+4,9*S+4);DrawRect(C,X,Y,Width*FMath::Clamp(Value,0.f,1.f),9*S);};
    Text(P->GameTitle,34*S,25*S,FLinearColor(.8f,.85f,.82f),1.3);
    Text(TEXT("1 FIRST  /  2 THIRD  /  3 ISOMETRIC  /  V CYCLE"),34*S,49*S,FLinearColor(.44f,.53f,.56f),.8);
    if(P->Opponent&&P->Opponent->Health>0&&(!P->IsExploring()||P->Opponent->Engaged||FVector::Dist2D(P->GetActorLocation(),P->Opponent->GetActorLocation())<1000)){float BW=FMath::Min(540*S,W*.48f);Bar((W-BW)/2,58*S,BW,P->Opponent->Health/P->Opponent->MaxHealth,FLinearColor(.43f,.12f,.13f));Text(P->Opponent->DisplayName,W/2-110*S,28*S,FLinearColor(.78f,.78f,.70f),1.0);}
    if(P->IsExploring())
    {
        Text(P->CurrentPlace,34*S,79*S,FLinearColor(.86f,.78f,.57f),1.05);
        Text(FString::Printf(TEXT("EXPLORE  %d / %d landmarks   SHIFT run   M map"),P->DiscoveredPlaces.Num(),P->ExplorationPlaces.Num()),34*S,102*S,FLinearColor(.67f,.72f,.65f),.8);
        if(P->ShowRouteMap)
        {
            const float Size=190*S,X=W-Size-26*S,Y=24*S;
            DrawRect(FLinearColor(.015f,.023f,.025f,.78f),X,Y,Size,Size);
            FVector Low=P->ExplorationWaypoints[0],High=Low;
            for(const auto& V:P->ExplorationWaypoints){Low.X=FMath::Min(Low.X,V.X);Low.Y=FMath::Min(Low.Y,V.Y);High.X=FMath::Max(High.X,V.X);High.Y=FMath::Max(High.Y,V.Y);}
            const float Scale=(Size-24*S)/FMath::Max(High.X-Low.X,High.Y-Low.Y);
            auto Map=[&](const FVector& V){return FVector2D(X+Size/2+(V.X-(High.X+Low.X)/2)*Scale,Y+Size/2-(V.Y-(High.Y+Low.Y)/2)*Scale);};
            for(int32 I=1;I<P->ExplorationWaypoints.Num();++I){auto A=Map(P->ExplorationWaypoints[I-1]),B=Map(P->ExplorationWaypoints[I]);DrawLine(A.X,A.Y,B.X,B.Y,FLinearColor(.47f,.47f,.36f,.9f),1.5*S);}
            for(int32 I=0;I<P->ExplorationPlaces.Num();++I){auto V=Map(P->ExplorationPlaces[I]);DrawRect(P->DiscoveredPlaces.Contains(I)?FLinearColor(.77f,.65f,.35f):FLinearColor(.4f,.48f,.44f),V.X-3*S,V.Y-3*S,6*S,6*S);}
            auto V=Map(P->GetActorLocation());DrawRect(FLinearColor(.9f,.94f,.88f),V.X-3*S,V.Y-3*S,6*S,6*S);
            Text(TEXT("N"),X+Size-16*S,Y+6*S,FLinearColor(.72f,.76f,.72f),.8);
        }
    }
    Bar(34*S,H-98*S,240*S,P->Health/P->MaxHealth,FLinearColor(.53f,.13f,.15f));
    Bar(34*S,H-78*S,185*S,P->Stamina/100,FLinearColor(.30f,.48f,.40f));
    Text(FString::Printf(TEXT("VITALITY %d     FLASKS %d"),FMath::CeilToInt(P->Health),P->Flasks),34*S,H-123*S,FLinearColor(.76f,.78f,.71f),.85);
    Text(TEXT("WASD move   J combo   K heavy   SPACE evade   C parry   TAB lock   R reset"),34*S,H-38*S,FLinearColor(.65f,.73f,.74f),.83);
    if(P->Opponent&&P->Opponent->Action==TEXT("stagger"))Text(TEXT("GUARD BROKEN  -  F to punish"),W/2-125*S,H*.71f,FLinearColor(.87f,.75f,.44f),1.1);
    if(P->Health<=0)Text(TEXT("FALLEN  -  R to retry"),W/2-100*S,H*.45f,FLinearColor(.9f,.75f,.7f),1.5);
    else if(P->Opponent&&P->Opponent->Health<=0&&(!P->IsExploring()||FVector::Dist2D(P->GetActorLocation(),P->Opponent->GetActorLocation())<1000))Text(TEXT("BOSS DEFEATED  -  R to duel again"),W/2-160*S,H*.45f,FLinearColor(.88f,.84f,.64f),1.35);
}
