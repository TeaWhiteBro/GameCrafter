#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "PipelineCapture.generated.h"
class AGameDemoFighter;
class USceneCaptureComponent2D;
class UTextureRenderTarget2D;
class UPrimitiveComponent;
class APipelineWhitebox;
UCLASS()
class GAMEDEMO_API APipelineCapture : public AActor
{
    GENERATED_BODY()
public:
    APipelineCapture();
    virtual void BeginPlay() override;
    virtual void Tick(float Dt) override;
private:
    UPROPERTY() TObjectPtr<USceneCaptureComponent2D> RGB;
    UPROPERTY() TObjectPtr<USceneCaptureComponent2D> Depth;
    UPROPERTY() TObjectPtr<USceneCaptureComponent2D> Labels;
    UPROPERTY() TObjectPtr<USceneCaptureComponent2D> Whitebox;
    UPROPERTY() TArray<TObjectPtr<UPrimitiveComponent>> WhiteboxComponents;
    UPROPERTY() TArray<TObjectPtr<APipelineWhitebox>> WhiteboxCharacters;
    UPROPERTY() TArray<TObjectPtr<UTextureRenderTarget2D>> Targets;
    UPROPERTY() TObjectPtr<AGameDemoFighter> Player;
    UPROPERTY() TArray<TObjectPtr<AActor>> CalibrationActors;
    FString Directory;
    int32 Width=640,Height=360,Frame=0,Frames=180,Warmup=90,Steps=0,SimulationOrdinal=0;
    double SimStep=1./60.;
    bool Ready=false,Finished=false,Cycle=false,Calibration=false,HasWhitebox=false;
    void Initialize();
    void Capture(float Dt,bool Write=true);
    void Fail(const FString& Reason);
};
