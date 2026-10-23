#pragma once
#include "CoreMinimal.h"
#include "Animation/AnimInstance.h"
#include "GameFramework/Character.h"
#include "GameFramework/GameModeBase.h"
#include "GameFramework/HUD.h"
#include "GameDemo.generated.h"

class UAnimSequence;
class USpringArmComponent;
class UCameraComponent;

UCLASS(Transient)
class GAMEDEMO_API UGameDemoAnim : public UAnimInstance
{
    GENERATED_BODY()
public:
    UGameDemoAnim();
protected:
    virtual FAnimInstanceProxy* CreateAnimInstanceProxy() override;
    virtual void DestroyAnimInstanceProxy(FAnimInstanceProxy* Proxy) override;
};

UCLASS()
class GAMEDEMO_API AGameDemoFighter : public ACharacter
{
    GENERATED_BODY()
public:
    AGameDemoFighter();
    virtual void BeginPlay() override;
    virtual void Tick(float DeltaSeconds) override;
    UPROPERTY(EditAnywhere,BlueprintReadWrite,Category="GameDemo") bool IsBoss=false;
    UPROPERTY(EditAnywhere,BlueprintReadWrite,Category="GameDemo") TArray<TObjectPtr<UAnimSequence>> MotionClips;
    UPROPERTY(VisibleAnywhere,BlueprintReadOnly,Category="GameDemo") TObjectPtr<USpringArmComponent> CameraBoom;
    UPROPERTY(VisibleAnywhere,BlueprintReadOnly,Category="GameDemo") TObjectPtr<UCameraComponent> Camera;
    UPROPERTY(BlueprintReadOnly,Category="GameDemo") float Health=100;
    UPROPERTY(BlueprintReadOnly,Category="GameDemo") float Stamina=100;
    UPROPERTY(BlueprintReadOnly,Category="GameDemo") float Poise=0;
    UPROPERTY(BlueprintReadOnly,Category="GameDemo") FString Action=TEXT("idle");
    UPROPERTY(BlueprintReadOnly,Category="GameDemo") TObjectPtr<AGameDemoFighter> Opponent;
    UPROPERTY(EditAnywhere,BlueprintReadWrite,Category="Pipeline") FString DisplayName=TEXT("Fighter");
    UPROPERTY(EditAnywhere,BlueprintReadWrite,Category="Pipeline") FString GameTitle=TEXT("Generated Demo");
    UPROPERTY(EditAnywhere,BlueprintReadWrite,Category="Pipeline") float ConfigHealth=120;
    UPROPERTY(EditAnywhere,BlueprintReadWrite,Category="Pipeline") float CharacterHeightCm=180;
    UPROPERTY(EditAnywhere,BlueprintReadWrite,Category="Pipeline") float CameraWidthCm=2200;
    UPROPERTY(EditAnywhere,BlueprintReadWrite,Category="Pipeline") float CameraPitch=-43;
    UPROPERTY(EditAnywhere,BlueprintReadWrite,Category="Pipeline") float CameraYaw=-90;
    UPROPERTY(EditAnywhere,BlueprintReadWrite,Category="Pipeline") float WalkStrideSpeed=253;
    UPROPERTY(EditAnywhere,BlueprintReadWrite,Category="Pipeline") float RunStrideSpeed=505;
    UPROPERTY(EditAnywhere,BlueprintReadWrite,Category="Exploration") float EncounterRadiusCm=0;
    UPROPERTY(EditAnywhere,BlueprintReadWrite,Category="Exploration") TArray<FVector> ExplorationWaypoints;
    UPROPERTY(EditAnywhere,BlueprintReadWrite,Category="Exploration") TArray<FVector> ExplorationPlaces;
    UPROPERTY(EditAnywhere,BlueprintReadWrite,Category="Exploration") TArray<FString> ExplorationNames;
    TSet<int32> DiscoveredPlaces;
    FString CurrentPlace;
    bool ReturningHome=false, ShowRouteMap=true;
    bool IsExploring() const { return ExplorationWaypoints.Num()>0; }
    UPROPERTY(EditAnywhere,BlueprintReadWrite,Category="Pipeline") FName MotionRootBone=TEXT("Root");
    UPROPERTY(EditAnywhere,BlueprintReadWrite,Category="Pipeline") FName HipBone=TEXT("Hip");
    UPROPERTY(EditAnywhere,BlueprintReadWrite,Category="Pipeline") FName HeadBone=TEXT("Head");
    UPROPERTY(EditAnywhere,BlueprintReadWrite,Category="Pipeline") FName FootBone=TEXT("L_Foot");
    UPROPERTY(EditAnywhere,BlueprintReadWrite,Category="Pipeline") FName SpineBone=TEXT("Spine02");
    UPROPERTY(EditAnywhere,BlueprintReadWrite,Category="Pipeline") FName AimSpineBone=TEXT("Spine01");
    UPROPERTY(EditAnywhere,BlueprintReadWrite,Category="Pipeline") FName LeftThighBone=TEXT("L_Thigh");
    UPROPERTY(EditAnywhere,BlueprintReadWrite,Category="Pipeline") FName RightThighBone=TEXT("R_Thigh");
    UPROPERTY(EditAnywhere,BlueprintReadWrite,Category="Pipeline") FName LeftArmBone=TEXT("L_Upperarm");
    UPROPERTY(EditAnywhere,BlueprintReadWrite,Category="Pipeline") FName RightArmBone=TEXT("R_Upperarm");
    UPROPERTY(EditAnywhere,BlueprintReadWrite,Category="Pipeline") TArray<FName> StrikeBones;
    UPROPERTY(EditAnywhere,BlueprintReadWrite,Category="Pipeline") TMap<FName,FName> CaptureBoneMap;
    int32 ActiveClip=0, PoseRevision=0;
    float ClipTime=0, PoseBlend=1, PoseBlendDuration=.12f, ActionTime=0, ActionDuration=1;
    float Flinch=0, MotionSpeed=0;
    bool Locked=false, Engaged=false, Guarding=false;
    float GuardAge=100, HitPause=0, Cooldown=1.4f, MaxHealth=100;
    int32 Flasks=2, HitCount=0, ParryCount=0, DodgeCount=0;
    void StartAction(const FString& Name, int32 Clip, float Rate=1, float Blend=.12f);
    void ResetDuel();
    void ReceiveStrike(AGameDemoFighter* Attacker, float Damage, float Impact);
    void SampleMovementQA(const FVector2D& ScreenOffset);
    void SampleHitQA(const FVector2D& ScreenOffset);
    void SampleFacingQA();
    FVector GetImportedForward() const { return ImportedForward; }
    FVector GetAuthoredSpawnPosition() const { return SpawnPosition; }
    // 0: first person, 1: third person, 2: orthographic 2.5D.
    int32 ViewMode=2;
    void SetViewMode(int32 Mode);
    void UpdateViewInput(float Dt);
    FString ViewModeName() const;
private:
    void UpdateExploration(float Dt);
    void UpdateExplorationQA(float Dt);
    void WriteExplorationQA();
    bool RoamQAMode=false, RoamQAComplete=false, RoamLeashReturned=false, RoamReengaged=false;
    float RoamAge=0, RoamStill=0, RoamTravel=0, RoamMaxStep=0, RoamAirTime=0, RoamMaxAirTime=0;
    float RoamFinishWait=0;
    int32 RoamWaypoint=0, RoamSamples=0;
    FVector RoamPrevious=FVector::ZeroVector;
    TSet<int32> RoamCaptured;
    float RoamAvoidSign=0;
    int32 RoamAvoidFrames=0;
    TArray<int32> RoamCaptureOrder;
    float OrbitYaw=-90, OrbitPitch=-18, ThirdPersonDistance=500;
    float SavedIsoYaw=-90;
    bool FacingCalibrated=false, FacingQAMode=false, FacingQAComplete=false, ArtQAMode=false;
    FVector ImportedForward=FVector::ZeroVector;
    float MeshFacingYaw=0, FacingQAAge=0;
    int32 FacingCase=-1, ArtQAStage=0;
    bool ArtQAFramingValid=true;
    TArray<FVector2D> ArtQAProjectedFocus;
    struct FFacingSample { int32 Frames=0; float MaxInputError=0, MaxBodyError=0, BodyErrorSum=0, Travel=0; };
    TArray<FFacingSample> FacingSamples;
    TSet<FKey> FacingKeys;
    FVector FacingPreviousPosition=FVector::ZeroVector;
    bool CalibrateFacing();
    FVector BodyForward() const;
    void UpdateFacingQA(float Dt);
    void WriteFacingQA();
    void UpdateArtQA();
    bool HitQAMode=false, HitQAComplete=false;
    float HitQAAge=0, HitQANext=3, HitMinScale=100, HitMinHeight=10000, HitMaxCenterError=0;
    int32 HitQAStrikes=0, HitQAFrames=0, HitQAReactionFrames=0, HitQAInvisibleFrames=0;
    double HitQALastFrame=0;
    TArray<float> HitQAFrameTimes;
    void UpdateHitQA(float Dt);
    void WriteHitQA();
    bool MovementQAMode=false, MovementQAComplete=false;
    float MovementQAAge=0, MovementQASampledTime=0, MaxRootTravel=0, MaxHipStep=0, MaxCenterError=0, MaxWorldStep=0;
    int32 MovementQAFrames=0, MovementQALoops=0, PreviousMovementClip=-1;
    float PreviousMovementClipTime=0;
    FVector PreviousHipLocal=FVector::ZeroVector, PreviousMovementPosition=FVector::ZeroVector;
    TSet<FKey> MovementQAKeys;
    void UpdateMovementQA(float Dt);
    void WriteMovementQA();
    FVector SpawnPosition, MoveDirection=FVector::ZeroVector, DashDirection=FVector::ForwardVector;
    FRotator SpawnRotation;
    float Rate=1, BufferedTime=0, WorldAge=0, DamageFlash=0, LastAttackAge=0;
    bool QueuedLight=false, QueuedHeavy=false, Connected=false;
    int32 BossPattern=0, BossChainRemaining=0;
    FVector LastHands[4];
    TSet<TWeakObjectPtr<AActor>> HitActors;
    TSet<FString> VisitedActions;
    float QATime=0, QADeltaSum=0, QABotClock=0;
    int32 QAFrames=0, QAStage=0;
    float QAInitialHeight=0, QABossInitialHeight=0, QADeathZ=0, QADeathDrop=0, QAResetHeight=0;
    bool QAMode=false, QAWritten=false;
    void UpdatePlayer(float Dt);
    void UpdateBoss(float Dt);
    void UpdateMotion(float Dt);
    float MeleeSeparationCm() const;
    void TraceStrike();
    void LightAttack();
    void HeavyAttack();
    void Evade();
    void FinishAction();
    void WriteQA();
    bool IsAttacking() const;
    bool CanAct() const;
    float ClipLength(int32 Index) const;
};

UCLASS()
class GAMEDEMO_API AGameDemoGameMode : public AGameModeBase
{
    GENERATED_BODY()
public:
    AGameDemoGameMode();
    virtual void BeginPlay() override;
};

UCLASS()
class GAMEDEMO_API AGameDemoHUD : public AHUD
{
    GENERATED_BODY()
public:
    virtual void DrawHUD() override;
};
