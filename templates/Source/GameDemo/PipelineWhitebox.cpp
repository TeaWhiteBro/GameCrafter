#include "PipelineWhitebox.h"
#include "GameDemo.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Engine/SkeletalMesh.h"
#include "Materials/MaterialInterface.h"

APipelineWhitebox::APipelineWhitebox()
{
    PrimaryActorTick.bCanEverTick=false;
    RootComponent=CreateDefaultSubobject<USceneComponent>(TEXT("ProxyRoot"));
    Tags.Add(TEXT("whitebox"));
}
bool APipelineWhitebox::Setup(AGameDemoFighter* F,UMaterialInterface* Material)
{
    Fighter=F;
    // Resolve intermediate joints from the actual reference hierarchy. A rig
    // may contain twists/helpers and need not use mannequin bone names.
    const auto& Ref=F->GetMesh()->GetSkeletalMeshAsset()->GetRefSkeleton();
    TArray<FTransform> Rest=Ref.GetRefBonePose();
    for(int I=0;I<Rest.Num();I++)if(Ref.GetParentIndex(I)>=0)Rest[I]=Rest[I]*Rest[Ref.GetParentIndex(I)];
    for(FString Side:{FString(TEXT("left")),FString(TEXT("right"))})for(int Chain=0;Chain<2;Chain++)
    {
        FName Key(*(Side+(Chain==0?TEXT("_forearm"):TEXT("_calf"))));
        if(F->CaptureBoneMap.Contains(Key))continue;
        FName First=F->CaptureBoneMap.FindRef(FName(*(Side+(Chain==0?TEXT("_upperarm"):TEXT("_thigh")))));
        FName Last=F->CaptureBoneMap.FindRef(FName(*(Side+(Chain==0?TEXT("_hand"):TEXT("_foot")))));
        int A=Ref.FindBoneIndex(First),B=Ref.FindBoneIndex(Last);if(A<0||B<0)return false;
        int Best=INDEX_NONE,Current=Ref.GetParentIndex(B);float Error=FLT_MAX;
        const FVector Start=Rest[A].GetLocation(),End=Rest[B].GetLocation();const float Length=FVector::Distance(Start,End);
        while(Current>=0&&Current!=A)
        {
            const float Fraction=FVector::Distance(Rest[Current].GetLocation(),Start)/FMath::Max(1.f,Length);
            if(Fraction>.15f&&Fraction<.85f&&FMath::Abs(Fraction-.5f)<Error){Best=Current;Error=FMath::Abs(Fraction-.5f);}
            Current=Ref.GetParentIndex(Current);
        }
        if(Current!=A||Best<0)return false;
        F->CaptureBoneMap.Add(Key,Ref.GetBoneName(Best));
    }
    auto Create=[&](const TCHAR* Asset)
    {
        auto* C=NewObject<UStaticMeshComponent>(this);AddInstanceComponent(C);C->SetupAttachment(RootComponent);
        C->SetStaticMesh(LoadObject<UStaticMesh>(nullptr,Asset));C->SetMobility(EComponentMobility::Movable);
        C->SetMaterial(0,Material);C->SetCollisionEnabled(ECollisionEnabled::NoCollision);C->SetGenerateOverlapEvents(false);
        C->SetCastShadow(false);C->SetAffectDistanceFieldLighting(false);C->SetAffectDynamicIndirectLighting(false);
        C->SetVisibleInRayTracing(false);C->SetVisibleInSceneCaptureOnly(true);C->SetRenderCustomDepth(false);
        C->RegisterComponent();Parts.Add(C);return C;
    };
    const TArray<TPair<FName,FName>> Pairs={
        {TEXT("hips"),TEXT("spine_end")},{TEXT("spine_end"),TEXT("neck")},{TEXT("neck"),TEXT("head")},
        {TEXT("left_upperarm"),TEXT("left_forearm")},{TEXT("left_forearm"),TEXT("left_hand")},
        {TEXT("right_upperarm"),TEXT("right_forearm")},{TEXT("right_forearm"),TEXT("right_hand")},
        {TEXT("left_thigh"),TEXT("left_calf")},{TEXT("left_calf"),TEXT("left_foot")},
        {TEXT("right_thigh"),TEXT("right_calf")},{TEXT("right_calf"),TEXT("right_foot")}};
    for(int I=0;I<Pairs.Num();I++)
    {
        const auto& P=Pairs[I];if(!F->CaptureBoneMap.Contains(P.Key)||!F->CaptureBoneMap.Contains(P.Value))return false;
        FWhiteboxLimb L;L.From=F->CaptureBoneMap[P.Key];L.To=F->CaptureBoneMap[P.Value];L.Head=I==2;
        auto* M=F->GetMesh();if(M->GetBoneIndex(L.From)<0||M->GetBoneIndex(L.To)<0)return false;
        const float Length=FVector::Distance(M->GetSocketLocation(L.From),M->GetSocketLocation(L.To));
        const float Shoulders=FVector::Distance(M->GetSocketLocation(F->LeftArmBone),M->GetSocketLocation(F->RightArmBone));
        // Shoulder armour must not set the depth of the skull or the ribcage.
        // Bound each axial proxy by its own rest-chain length; this preserves
        // the abstract capsule body without inflating broad-shouldered rigs.
        const float HeadRadius=FMath::Min(Shoulders*.29f,FMath::Max(3.f,Length*.85f));
        const float TorsoRadius=FMath::Min(Shoulders*.40f,FMath::Max(3.f,Length*.45f));
        L.Radius=I==0?TorsoRadius:I==1?Shoulders*.15f:I==2?HeadRadius:FMath::Max(3.f,Length*(I>=7?.22f:.20f));
        L.Shaft=Create(TEXT("/Engine/BasicShapes/Cylinder.Cylinder"));
        L.CapA=Create(TEXT("/Engine/BasicShapes/Sphere.Sphere"));L.CapB=Create(TEXT("/Engine/BasicShapes/Sphere.Sphere"));
        Limbs.Add(L);
    }
    UpdatePose();return true;
}
void APipelineWhitebox::UpdatePose()
{
    for(auto& L:Limbs)
    {
        L.A=Fighter->GetMesh()->GetSocketLocation(L.From);L.B=Fighter->GetMesh()->GetSocketLocation(L.To);
        if(L.Head){const FVector D=(L.B-L.A).GetSafeNormal();L.A=L.B;L.B+=D*L.Radius*.5f;}
        const FVector D=L.B-L.A;const float Length=D.Size();
        L.Shaft->SetWorldLocationAndRotation((L.A+L.B)*.5f,FQuat::FindBetweenNormals(FVector::UpVector,D.GetSafeNormal()));
        L.Shaft->SetWorldScale3D(FVector(L.Radius/50.f,L.Radius/50.f,FMath::Max(.001f,Length/100.f)));
        L.CapA->SetWorldLocation(L.A);L.CapB->SetWorldLocation(L.B);
        L.CapA->SetWorldScale3D(FVector(L.Radius/50.f));L.CapB->SetWorldScale3D(FVector(L.Radius/50.f));
    }
}
