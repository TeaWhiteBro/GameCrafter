#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "PipelineWhitebox.generated.h"
class AGameDemoFighter;
class UStaticMeshComponent;
class UMaterialInterface;
USTRUCT()
struct FWhiteboxLimb
{
    GENERATED_BODY()
    FName From,To;
    float Radius=10;
    bool Head=false;
    FVector A,B;
    UPROPERTY() TObjectPtr<UStaticMeshComponent> Shaft;
    UPROPERTY() TObjectPtr<UStaticMeshComponent> CapA;
    UPROPERTY() TObjectPtr<UStaticMeshComponent> CapB;
};
UCLASS()
class GAMEDEMO_API APipelineWhitebox : public AActor
{
    GENERATED_BODY()
public:
    APipelineWhitebox();
    bool Setup(AGameDemoFighter* F,UMaterialInterface* Material);
    void UpdatePose();
    UPROPERTY() TObjectPtr<AGameDemoFighter> Fighter;
    UPROPERTY() TArray<FWhiteboxLimb> Limbs;
    UPROPERTY() TArray<TObjectPtr<UStaticMeshComponent>> Parts;
};
