#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "PipelineCameraQA.generated.h"
class AGameDemoFighter;
UCLASS()
class GAMEDEMO_API APipelineCameraQA : public AActor
{
    GENERATED_BODY()
public:
    APipelineCameraQA();
    virtual void Tick(float Dt) override;
private:
    UPROPERTY() TObjectPtr<AGameDemoFighter> Player;
    float Age=0,CaseAge=0,MaxSwitchDisplacement=0;
    int32 Case=-1;
    FVector Previous=FVector::ZeroVector;
    FVector TestOrigin=FVector::ZeroVector;
    int32 ProbeCandidates=0,ProbeQueries=0;
    bool ProbeSpaceValid=false;
    bool StartupProjectionPolicyValid=false;
    FString SpawnProbeRejection;
    FKey Held;
    bool Finished=false;
    struct FSample { int32 Frames=0; float Travel=0,MaxInputError=0,MaxStep=0; bool Visibility=true,Projection=true,Scale=true,Framed=true,ProjectionPolicy=true; };
    TArray<FSample> Samples;
    void BeginCase(int32 Index);
    bool FindProbeSpace();
    void Finish();
};
