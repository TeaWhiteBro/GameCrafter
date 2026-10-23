#include "PipelineCapture.h"
#include "RenderViewPolicy.h"
#include "PipelineWhitebox.h"
#include "GameDemo.h"
#include "Camera/CameraComponent.h"
#include "Components/SceneCaptureComponent2D.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Components/MeshComponent.h"
#include "Components/PrimitiveComponent.h"
#include "Engine/TextureRenderTarget2D.h"
#include "Engine/StaticMeshActor.h"
#include "Engine/StaticMesh.h"
#include "EngineUtils.h"
#include "GameFramework/SpringArmComponent.h"
#include "Materials/MaterialInterface.h"
#include "Materials/Material.h"
#include "Misc/App.h"
#include "Misc/CommandLine.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "HAL/PlatformFileManager.h"
#include "HAL/IConsoleManager.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"
#include "TextureResource.h"
#include "Math/InverseRotationMatrix.h"

namespace
{
using JO=TSharedPtr<FJsonObject>;
TSharedPtr<FJsonValue> Num(double V){return MakeShared<FJsonValueNumber>(V);}
TArray<TSharedPtr<FJsonValue>> VectorJSON(FVector V){return {Num(V.X),Num(V.Y),Num(V.Z)};}
TArray<TSharedPtr<FJsonValue>> MatrixJSON(const FMatrix& M)
{ TArray<TSharedPtr<FJsonValue>> A;for(int I=0;I<4;I++)for(int J=0;J<4;J++)A.Add(Num(M.M[I][J]));return A; }
bool SaveJSON(JO J,const FString& Path)
{ FString S;auto W=TJsonWriterFactory<>::Create(&S);FJsonSerializer::Serialize(J.ToSharedRef(),W);return FFileHelper::SaveStringToFile(S,*Path,FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM); }
template<class T> bool SaveRaw(const TArray<T>& Values,const FString& Path)
{ TArray<uint8> Bytes;Bytes.SetNumUninitialized(Values.Num()*sizeof(T));FMemory::Memcpy(Bytes.GetData(),Values.GetData(),Bytes.Num());return FFileHelper::SaveArrayToFile(Bytes,*Path); }
void CV(const TCHAR* Name,int Value){if(auto* C=IConsoleManager::Get().FindConsoleVariable(Name))C->Set(Value,ECVF_SetByCode);}
}

APipelineCapture::APipelineCapture()
{
    PrimaryActorTick.bCanEverTick=true;PrimaryActorTick.TickGroup=TG_PostUpdateWork;
    RootComponent=CreateDefaultSubobject<USceneComponent>(TEXT("CaptureRoot"));
    RGB=CreateDefaultSubobject<USceneCaptureComponent2D>(TEXT("AlignedRGB"));
    Depth=CreateDefaultSubobject<USceneCaptureComponent2D>(TEXT("AlignedDepth"));
    Labels=CreateDefaultSubobject<USceneCaptureComponent2D>(TEXT("AlignedSemantics"));
    Whitebox=CreateDefaultSubobject<USceneCaptureComponent2D>(TEXT("AlignedWhitebox"));
    for(auto* C:{RGB.Get(),Depth.Get(),Labels.Get(),Whitebox.Get()})
    {
        C->SetupAttachment(RootComponent);C->bCaptureEveryFrame=false;C->bCaptureOnMovement=false;
        C->bAlwaysPersistRenderingState=true;
        C->ShowFlags.SetTemporalAA(false);C->ShowFlags.SetAntiAliasing(false);
        C->ShowFlags.SetMotionBlur(false);C->ShowFlags.SetDepthOfField(false);
        C->ShowFlags.SetScreenPercentage(false);
        C->ShowFlags.SetPostProcessing(true);C->ShowFlags.SetPostProcessMaterial(true);C->ShowFlags.SetTonemapper(true);
    }
}

void APipelineCapture::Fail(const FString& Reason)
{
    Finished=true;JO J=MakeShared<FJsonObject>();J->SetBoolField(TEXT("ok"),false);J->SetStringField(TEXT("error"),Reason);
    if(!Directory.IsEmpty()&&!FPaths::FileExists(Directory/TEXT("capture_result.json")))SaveJSON(J,Directory/TEXT("capture_result.json"));
    UE_LOG(LogTemp,Error,TEXT("DATASET FAILURE: %s"),*Reason);
    FPlatformMisc::RequestExit(false);
}

void APipelineCapture::BeginPlay()
{
    Super::BeginPlay();
    FParse::Value(FCommandLine::Get(),TEXT("DatasetOutput="),Directory);
    FParse::Value(FCommandLine::Get(),TEXT("DatasetWidth="),Width);
    FParse::Value(FCommandLine::Get(),TEXT("DatasetHeight="),Height);
    FParse::Value(FCommandLine::Get(),TEXT("DatasetFrames="),Frames);
    FParse::Value(FCommandLine::Get(),TEXT("DatasetWarmup="),Warmup);
    if(Warmup<32||Warmup>36000){Fail(TEXT("Invalid capture warmup"));return;}
    Cycle=FParse::Param(FCommandLine::Get(),TEXT("DatasetCameraCycle"));
    Calibration=FParse::Param(FCommandLine::Get(),TEXT("DatasetCalibration"));
    if(Directory.IsEmpty()||Width<64||Height<64||Width>4096||Height>4096||Frames<1){Fail(TEXT("Invalid dataset arguments"));return;}
    if(FPaths::FileExists(Directory/TEXT("capture_result.json"))) {Fail(TEXT("Refuse to overwrite an existing capture"));return;}
    IFileManager::Get().MakeDirectory(*(Directory/TEXT("raw")),true);
    FApp::SetUseFixedTimeStep(true);FApp::SetFixedDeltaTime(SimStep);
    CV(TEXT("r.CustomDepth"),3);CV(TEXT("r.AntiAliasingMethod"),0);CV(TEXT("r.MotionBlurQuality"),0);
    CV(TEXT("r.DepthOfFieldQuality"),0);CV(TEXT("r.ScreenPercentage"),100);CV(TEXT("r.DynamicRes.OperationMode"),0);
    CV(TEXT("r.CustomDepthTemporalAAJitter"),0);
}

void APipelineCapture::Initialize()
{
    for(TActorIterator<AGameDemoFighter> I(GetWorld());I;++I)
    {
        if(!I->IsBoss)Player=*I;
        AddTickPrerequisiteActor(*I);AddTickPrerequisiteComponent(I->GetMesh());
        AddTickPrerequisiteComponent(I->CameraBoom);
    }
    if(!Player){Fail(TEXT("No player"));return;}
    auto* LabelMaterial=LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/Generated/Data/M_Semantic.M_Semantic"));
    if(!LabelMaterial){Fail(TEXT("Missing renderer semantic material"));return;}
    int Unknown=0;
    for(TActorIterator<AActor> I(GetWorld());I;++I)
    {
        if(I->ActorHasTag(TEXT("whitebox")))continue;
        int Id=255;
        if(auto* F=Cast<AGameDemoFighter>(*I))Id=F->IsBoss?11:10;
        for(auto Tag:I->Tags){FString S=Tag.ToString();if(S.RemoveFromStart(TEXT("semantic:")))Id=FCString::Atoi(*S);}
        TArray<UPrimitiveComponent*> Components;I->GetComponents(Components);
        for(auto* C:Components)
        {
            if(!C->IsVisible()||I->IsHidden()||!C->IsRegistered())continue;
            if(C->IsA<USkeletalMeshComponent>() || C->IsA<UStaticMeshComponent>())
            {
                if(!((Id>=1&&Id<=6)||Id==10||Id==11))Unknown++;
                if(auto* MC=Cast<UMeshComponent>(C))for(int MI=0;MI<MC->GetNumMaterials();MI++)
                {
                    auto* Material=MC->GetMaterial(MI);
                    if(Material && Material->GetBlendMode()!=BLEND_Opaque && Material->GetBlendMode()!=BLEND_Masked)
                    {
                        // Only explicitly authored, non-refractive thin glazing
                        // may transmit the measured opaque surface behind it.
                        // Unknown translucent sources still fail immediately.
                        if(!I->ActorHasTag(TEXT("capture:opaque_surface_behind_glass_v1")) || Material->GetBlendMode()!=BLEND_Translucent)
                        {Fail(TEXT("Dense capture currently requires opaque/masked surfaces: ")+I->GetName());return;}
                    }
                }
                C->SetRenderCustomDepth(!I->ActorHasTag(TEXT("capture:opaque_surface_behind_glass_v1")));C->SetCustomDepthStencilValue(Id);
            }
        }
    }
    if(Unknown){Fail(FString::Printf(TEXT("%d render meshes lack explicit semantic labels"),Unknown));return;}
    auto* WhiteMaterial=LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/Generated/Data/M_Whitebox.M_Whitebox"));
    for(TActorIterator<AActor> I(GetWorld());I;++I)if(I->ActorHasTag(TEXT("whitebox")))
    {
        I->SetActorHiddenInGame(false);TArray<UPrimitiveComponent*> Components;I->GetComponents(Components);
        for(auto* C:Components){WhiteboxComponents.Add(C);Whitebox->ShowOnlyComponent(C);}
    }
    HasWhitebox=WhiteboxComponents.Num()>0;
    if(FParse::Param(FCommandLine::Get(),TEXT("DatasetRequireWhitebox"))&&!HasWhitebox){Fail(TEXT("Scene lacks structural whitebox geometry"));return;}
    if(HasWhitebox)
    {
        if(!WhiteMaterial){Fail(TEXT("Whitebox material missing"));return;}
        for(TActorIterator<AGameDemoFighter> I(GetWorld());I;++I)
        {
            auto* Proxy=GetWorld()->SpawnActor<APipelineWhitebox>();
            if(!Proxy->Setup(*I,WhiteMaterial)){Fail(TEXT("Incomplete capsule semantic bone map"));return;}
            WhiteboxCharacters.Add(Proxy);
            for(UStaticMeshComponent* C:Proxy->Parts){WhiteboxComponents.Add(C);Whitebox->ShowOnlyComponent(C);}
        }
    }
    Whitebox->PrimitiveRenderMode=ESceneCapturePrimitiveRenderMode::PRM_UseShowOnlyList;
    int Index=0;
    for(auto* C:{RGB.Get(),Depth.Get(),Labels.Get(),Whitebox.Get()})
    {
        UTextureRenderTarget2D* RT=NewObject<UTextureRenderTarget2D>(this);Targets.Add(RT);
        RT->ClearColor=FLinearColor::Black;RT->bAutoGenerateMips=false;
        RT->InitCustomFormat(Width,Height,Index==1?PF_A32B32G32R32F:PF_B8G8R8A8,Index==1||Index==2);
        // FinalColorLDR already contains display-encoded RGB. Store it without
        // another sRGB render-target write; leave depth, IDs and whitebox unchanged.
        if(Index==0){RT->bForceLinearGamma=true;RT->TargetGamma=2.2f;}
        RT->UpdateResourceImmediate(true);C->TextureTarget=RT;
        C->CaptureSource=Index==1?ESceneCaptureSource::SCS_SceneDepth:ESceneCaptureSource::SCS_FinalColorLDR;
        C->PostProcessBlendWeight=1;
        auto& PP=C->PostProcessSettings;
        PP.bOverride_MotionBlurAmount=true;PP.MotionBlurAmount=0;
        PP.bOverride_VignetteIntensity=true;PP.VignetteIntensity=0;
        PP.bOverride_SceneFringeIntensity=true;PP.SceneFringeIntensity=0;
        PP.bOverride_FilmGrainIntensity=true;PP.FilmGrainIntensity=0;
        if(Index==0)
        {
            PP.bOverride_DynamicGlobalIlluminationMethod=true;PP.DynamicGlobalIlluminationMethod=EDynamicGlobalIlluminationMethod::Lumen;
            PP.bOverride_ReflectionMethod=true;PP.ReflectionMethod=EReflectionMethod::Lumen;
        }
        if(Index==2){PP.WeightedBlendables.Array.Add(FWeightedBlendable(1,LabelMaterial));C->ShowFlags.SetAtmosphere(false);C->ShowFlags.SetFog(false);}
        if(Index==3)
        {
            C->ShowFlags.SetAtmosphere(false);C->ShowFlags.SetFog(false);
            PP.bOverride_DynamicGlobalIlluminationMethod=true;PP.DynamicGlobalIlluminationMethod=EDynamicGlobalIlluminationMethod::None;
            PP.bOverride_ReflectionMethod=true;PP.ReflectionMethod=EReflectionMethod::None;
            PP.bOverride_AutoExposureMethod=true;PP.AutoExposureMethod=EAutoExposureMethod::AEM_Manual;
            PP.bOverride_AutoExposureApplyPhysicalCameraExposure=true;PP.AutoExposureApplyPhysicalCameraExposure=false;
            PP.bOverride_AutoExposureBias=true;PP.AutoExposureBias=0;
            PP.bOverride_BloomIntensity=true;PP.BloomIntensity=0;
        }
        Index++;
    }
    UE_LOG(LogTemp,Display,TEXT("DATASET MATERIAL %s domain=%d location=%d blendables=%d postprocess=%d tonemap=%d"),*LabelMaterial->GetName(),int(LabelMaterial->GetMaterial()->MaterialDomain),int(LabelMaterial->GetMaterial()->BlendableLocation),Labels->PostProcessSettings.WeightedBlendables.Array.Num(),Labels->ShowFlags.PostProcessing,Labels->ShowFlags.Tonemapper);
    Ready=true;
}

void APipelineCapture::Tick(float Dt)
{
    Super::Tick(Dt);if(Finished)return;SimulationOrdinal++;
    if(!Ready){Initialize();return;}
    if(++Steps<Warmup){if(Steps>Warmup-32)Capture(Dt,false);return;}
    Capture(Dt);
}

void APipelineCapture::Capture(float Dt,bool Write)
{
    if(Cycle)
    {
        int Desired=FMath::Min(2,Frame*3/Frames);
        if(Player->ViewMode!=Desired){Player->SetViewMode(Desired);Steps=0;Warmup=30;return;}
    }
    FMinimalViewInfo View;Player->Camera->GetCameraView(0,View);
    View.AspectRatio=float(Width)/Height;View.bConstrainAspectRatio=false;
    // The same explicit projection is used for all raster passes and joint projection.
    View.bAutoCalculateOrthoPlanes=false;View.OrthoNearClipPlane=0;View.OrthoFarClipPlane=50000;
    const FMatrix Projection=View.CalculateProjectionMatrix();
    const FMatrix ViewMatrix=FTranslationMatrix(-View.Location)*FInverseRotationMatrix(View.Rotation)*
        FMatrix(FPlane(0,0,1,0),FPlane(1,0,0,0),FPlane(0,1,0,0),FPlane(0,0,0,1));
    const FMatrix VP=ViewMatrix*Projection;
    TArray<TSharedPtr<FJsonValue>> CalibrationJSON;
    if(Calibration)
    {
        const FVector Front=View.Rotation.Vector(),Right=FRotationMatrix(View.Rotation).GetUnitAxis(EAxis::Y),Up=FRotationMatrix(View.Rotation).GetUnitAxis(EAxis::Z);
        for(int I=0;I<2;I++)
        {
            const int Id=200+I;const float Distance=I==0?320:220;
            if(CalibrationActors.Num()<=I)
            {
                auto* A=GetWorld()->SpawnActor<AStaticMeshActor>();auto* C=A->GetStaticMeshComponent();
                C->SetMobility(EComponentMobility::Movable);C->SetStaticMesh(LoadObject<UStaticMesh>(nullptr,TEXT("/Engine/BasicShapes/Cube.Cube")));
                C->SetMaterial(0,LoadObject<UMaterialInterface>(nullptr,*(FString(TEXT("/Game/Generated/Data/M_Calibration"))+FString::FromInt(I))));
                C->SetCollisionEnabled(ECollisionEnabled::NoCollision);C->SetRenderCustomDepth(true);C->SetCustomDepthStencilValue(Id);C->SetCastShadow(false);
                CalibrationActors.Add(A);Whitebox->ShowOnlyComponent(C);
            }
            const FVector Position=View.Location+Front*Distance+Right*(I==0?-30:30);
            CalibrationActors[I]->SetActorLocationAndRotation(Position,View.Rotation);
            CalibrationActors[I]->SetActorScale3D(FVector(.4,1.4,1.2));
            JO Item=MakeShared<FJsonObject>();Item->SetNumberField(TEXT("class_id"),Id);Item->SetNumberField(TEXT("front_depth_m"),(Distance-20)*.01);
            TArray<TSharedPtr<FJsonValue>> Corners;
            for(int X:{-1,1})for(int Y:{-1,1})
            {
                const FVector P=Position-Front*20+Right*(70*X)+Up*(60*Y);const FVector4 Clip=VP.TransformFVector4(FVector4(P,1));
                Corners.Add(MakeShared<FJsonValueArray>(TArray<TSharedPtr<FJsonValue>>{Num((.5+.5*Clip.X/Clip.W)*Width-.5),Num((.5-.5*Clip.Y/Clip.W)*Height-.5)}));
            }
            Item->SetArrayField(TEXT("front_corners_px"),Corners);CalibrationJSON.Add(MakeShared<FJsonValueObject>(Item));
        }
    }
    for(APipelineWhitebox* Proxy:WhiteboxCharacters)Proxy->UpdatePose();
    for(auto* C:{RGB.Get(),Depth.Get(),Labels.Get(),Whitebox.Get()})
    {
        if(C==Whitebox&&!HasWhitebox)continue;
        C->SetWorldLocationAndRotation(View.Location,View.Rotation);
        C->ProjectionType=View.ProjectionMode;C->FOVAngle=View.FOV;C->OrthoWidth=View.OrthoWidth;
        ApplyPipelineProjectionPolicy(C->PostProcessSettings,View.ProjectionMode==ECameraProjectionMode::Orthographic);
        C->bAutoCalculateOrthoPlanes=false;
        C->bUseCustomProjectionMatrix=true;C->CustomProjectionMatrix=Projection;
        C->HiddenComponents.Reset();
        if(C!=Whitebox)for(UPrimitiveComponent* P:WhiteboxComponents)C->HideComponent(P);
        if(Player->ViewMode==0)
        {
            C->HideComponent(Player->GetMesh());
            if(C==Whitebox)for(APipelineWhitebox* Proxy:WhiteboxCharacters)if(Proxy->Fighter==Player)for(UStaticMeshComponent* P:Proxy->Parts)C->HideComponent(P);
        }
        C->CaptureScene();
    }
    if(!Write)return;
    TArray<FColor> Color,Semantic,WhiteColor;TArray<FLinearColor> Z;
    FReadSurfaceDataFlags Flags(RCM_UNorm);Flags.SetLinearToGamma(false);
    if(!Targets[0]->GameThread_GetRenderTargetResource()->ReadPixels(Color,Flags) ||
       !Targets[2]->GameThread_GetRenderTargetResource()->ReadPixels(Semantic,Flags) ||
       !Targets[1]->GameThread_GetRenderTargetResource()->ReadLinearColorPixels(Z))
    {Fail(TEXT("GPU readback failed"));return;}
    if(Color.Num()!=Width*Height||Z.Num()!=Color.Num()||Semantic.Num()!=Color.Num()){Fail(TEXT("Pass extent mismatch"));return;}
    if(HasWhitebox && (!Targets[3]->GameThread_GetRenderTargetResource()->ReadPixels(WhiteColor,Flags)||WhiteColor.Num()!=Color.Num())){Fail(TEXT("Whitebox readback failed"));return;}
    TArray<float> Metres;TArray<uint8> IDs,Stencil;Metres.Reserve(Z.Num());IDs.Reserve(Z.Num());Stencil.Reserve(Z.Num());
    int BackgroundStencilChanges=0;
    for(int I=0;I<Z.Num();I++)
    {
        const float M=Z[I].R*.01f;const uint8 Raw=Semantic[I].R;
        // Only the engine clear-depth range has no visible scene surface.
        // Preserve raw stencil separately so this native encoding is independently auditable.
        const uint8 Label=M>=1.0e10f?0:Raw;
        Metres.Add(M);Stencil.Add(Raw);IDs.Add(Label);
        if(Label!=Raw)BackgroundStencilChanges++;
    }
    FString Prefix=Directory/TEXT("raw")/FString::Printf(TEXT("%06d"),Frame);
    JO J=MakeShared<FJsonObject>();J->SetNumberField(TEXT("frame_id"),Frame);
    J->SetNumberField(TEXT("simulation_step"),SimulationOrdinal);J->SetNumberField(TEXT("engine_frame_counter"),GFrameCounter);J->SetNumberField(TEXT("time_seconds"),GetWorld()->GetTimeSeconds());
    J->SetNumberField(TEXT("delta_seconds"),Dt);J->SetStringField(TEXT("camera_mode"),Player->ViewModeName());
    J->SetNumberField(TEXT("width"),Width);J->SetNumberField(TEXT("height"),Height);
    J->SetStringField(TEXT("semantic_encoding"),TEXT("scene_depth_clear_to_sky_v1"));
    J->SetStringField(TEXT("transparency_policy"),TEXT("Explicit non-refractive thin glass transmits the underlying opaque depth and semantic surface; RGB includes glazing. Unknown translucency is rejected."));
    J->SetNumberField(TEXT("semantic_background_min_depth_m"),1.0e10);
    J->SetNumberField(TEXT("background_stencil_changes"),BackgroundStencilChanges);
    J->SetBoolField(TEXT("orthographic"),View.ProjectionMode==ECameraProjectionMode::Orthographic);
    J->SetNumberField(TEXT("fov_x_deg"),View.FOV);J->SetNumberField(TEXT("ortho_width_cm"),View.OrthoWidth);
    J->SetArrayField(TEXT("camera_world_cm"),VectorJSON(View.Location));
    J->SetArrayField(TEXT("camera_pitch_yaw_roll"),{Num(View.Rotation.Pitch),Num(View.Rotation.Yaw),Num(View.Rotation.Roll)});
    J->SetArrayField(TEXT("world_to_view"),MatrixJSON(ViewMatrix));J->SetArrayField(TEXT("projection"),MatrixJSON(Projection));
    J->SetArrayField(TEXT("world_to_clip"),MatrixJSON(VP));
    if(Calibration)J->SetArrayField(TEXT("calibration"),CalibrationJSON);
    TArray<TSharedPtr<FJsonValue>> Actors;
    for(TActorIterator<AGameDemoFighter> I(GetWorld());I;++I)
    {
        auto* F=*I;auto* Mesh=F->GetMesh();JO A=MakeShared<FJsonObject>();
        A->SetStringField(TEXT("role"),F->IsBoss?TEXT("boss"):TEXT("player"));A->SetNumberField(TEXT("class_id"),F->IsBoss?11:10);
        A->SetStringField(TEXT("action"),F->Action);A->SetNumberField(TEXT("health"),F->Health);
        A->SetArrayField(TEXT("position_cm"),VectorJSON(F->GetActorLocation()));A->SetArrayField(TEXT("velocity_cm_s"),VectorJSON(F->GetVelocity()));
        A->SetBoolField(TEXT("camera_hidden"),F==Player&&Player->ViewMode==0);
        TArray<TSharedPtr<FJsonValue>> Bones;
        for(int B=0;B<Mesh->GetNumBones();B++)
        {
            const FName Name=Mesh->GetBoneName(B);const FVector P=Mesh->GetSocketLocation(Name);
            const FVector4 Clip=VP.TransformFVector4(FVector4(P,1));const FVector4 Cam=ViewMatrix.TransformFVector4(FVector4(P,1));
            const bool Front=Clip.W>0&&Cam.Z>0;
            double U=Front?(.5+.5*Clip.X/Clip.W)*Width-.5:-10000;
            double V=Front?(.5-.5*Clip.Y/Clip.W)*Height-.5:-10000;
            JO Bone=MakeShared<FJsonObject>();Bone->SetStringField(TEXT("name"),Name.ToString());Bone->SetNumberField(TEXT("index"),B);
            Bone->SetNumberField(TEXT("parent"),Mesh->GetBoneIndex(Mesh->GetParentBone(Name)));
            Bone->SetArrayField(TEXT("world_cm"),VectorJSON(P));Bone->SetArrayField(TEXT("pixel_xy"),{Num(U),Num(V)});
            Bone->SetNumberField(TEXT("camera_z_m"),Cam.Z*.01);Bone->SetBoolField(TEXT("in_front"),Front);
            Bones.Add(MakeShared<FJsonValueObject>(Bone));
        }
        A->SetArrayField(TEXT("bones"),Bones);Actors.Add(MakeShared<FJsonValueObject>(A));
    }
    J->SetArrayField(TEXT("actors"),Actors);
    if(HasWhitebox)
    {
        JO W=MakeShared<FJsonObject>();W->SetStringField(TEXT("representation"),TEXT("structural_scene_and_articulated_capsules"));
        W->SetNumberField(TEXT("simulation_step"),SimulationOrdinal);W->SetArrayField(TEXT("world_to_clip"),MatrixJSON(VP));
        TArray<TSharedPtr<FJsonValue>> Capsules;
        for(APipelineWhitebox* Proxy:WhiteboxCharacters)for(const auto& Limb:Proxy->Limbs)
        {
            JO L=MakeShared<FJsonObject>();L->SetStringField(TEXT("role"),Proxy->Fighter->IsBoss?TEXT("boss"):TEXT("player"));
            L->SetStringField(TEXT("from_bone"),Limb.From.ToString());L->SetStringField(TEXT("to_bone"),Limb.To.ToString());
            L->SetBoolField(TEXT("head_extension"),Limb.Head);L->SetNumberField(TEXT("radius_cm"),Limb.Radius);
            L->SetArrayField(TEXT("a_cm"),VectorJSON(Limb.A));L->SetArrayField(TEXT("b_cm"),VectorJSON(Limb.B));
            L->SetBoolField(TEXT("camera_hidden"),Proxy->Fighter==Player&&Player->ViewMode==0);
            Capsules.Add(MakeShared<FJsonValueObject>(L));
        }
        W->SetArrayField(TEXT("capsules"),Capsules);J->SetObjectField(TEXT("whitebox"),W);
    }
    // Commit metadata last. A partial pass set can never be mistaken for a frame.
    if(!SaveRaw(Color,Prefix+TEXT(".bgra"))||!SaveRaw(Metres,Prefix+TEXT(".depth"))||!SaveRaw(Stencil,Prefix+TEXT(".stencil"))||!SaveRaw(IDs,Prefix+TEXT(".ids"))||(HasWhitebox&&!SaveRaw(WhiteColor,Prefix+TEXT(".whitebox.bgra")))||!SaveJSON(J,Prefix+TEXT(".json")))
    {Fail(TEXT("Frame write failed"));return;}
    Frame++;
    if(Frame>=Frames)
    {
        JO Result=MakeShared<FJsonObject>();Result->SetBoolField(TEXT("ok"),true);Result->SetNumberField(TEXT("frames"),Frame);
        Result->SetNumberField(TEXT("width"),Width);Result->SetNumberField(TEXT("height"),Height);Result->SetNumberField(TEXT("simulation_fps"),60);
        Result->SetStringField(TEXT("depth"),TEXT("float32 little-endian camera-forward depth in metres; not ray distance"));
        Result->SetStringField(TEXT("matrix_convention"),TEXT("row-major matrices, world row vectors; view axes right/up/forward, UE world cm"));
        Result->SetStringField(TEXT("pixel_convention"),TEXT("top-left origin; integer pixel centers; NDC maps to [0,width] minus 0.5"));
        Result->SetBoolField(TEXT("hud_in_rgb"),false);Result->SetBoolField(TEXT("temporal_aa"),false);Result->SetBoolField(TEXT("motion_blur"),false);
        Result->SetBoolField(TEXT("calibration_only"),Calibration);Result->SetBoolField(TEXT("whitebox"),HasWhitebox);
        Result->SetStringField(TEXT("semantic_encoding"),TEXT("scene_depth_clear_to_sky_v1"));
        Result->SetStringField(TEXT("semantic_source"),TEXT("raw stencil preserved in .stencil; .ids uses class 0 only at synchronous depth >=1e10 metres; finite surface labels unchanged"));
        Result->SetStringField(TEXT("capture_policy"),TEXT("synchronous RGB, metric depth, labels and optional structural whitebox at one post-animation simulation step; offline fixed timestep"));
        SaveJSON(Result,Directory/TEXT("capture_result.json"));Finished=true;FPlatformMisc::RequestExit(false);
    }
}
