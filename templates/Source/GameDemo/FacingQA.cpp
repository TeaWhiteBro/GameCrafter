#include "GameDemo.h"
#include "Engine/SkeletalMesh.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/SpringArmComponent.h"
#include "GameFramework/PlayerController.h"
#include "Camera/CameraComponent.h"
#include "Components/CapsuleComponent.h"
#include "InputKeyEventArgs.h"
#include "Dom/JsonObject.h"
#include "Serialization/JsonSerializer.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"

namespace
{
float Angle(const FVector& A,const FVector& B)
{
    if(A.IsNearlyZero()||B.IsNearlyZero())return 180;
    return FMath::RadiansToDegrees(FMath::Acos(FMath::Clamp(FVector::DotProduct(A.GetSafeNormal2D(),B.GetSafeNormal2D()),-1.,1.)));
}
void SaveQA(const TSharedRef<FJsonObject>& O,const TCHAR* File)
{
    FString Text;auto W=TJsonWriterFactory<>::Create(&Text);FJsonSerializer::Serialize(O,W);
    FFileHelper::SaveStringToFile(Text,*(FPaths::ProjectSavedDir()/File));
}
const FKey Directions[]={EKeys::W,EKeys::A,EKeys::S,EKeys::D};
const FVector2D ScreenDirections[]={FVector2D(0,-1),FVector2D(-1,0),FVector2D(0,1),FVector2D(1,0)};
}

bool AGameDemoFighter::CalibrateFacing()
{
    auto* SkinAsset=GetMesh()->GetSkeletalMeshAsset();if(!SkinAsset)return false;
    const FReferenceSkeleton& Ref=SkinAsset->GetRefSkeleton();
    auto Position=[&](FName Name,FVector& P)
    {
        int32 I=Ref.FindBoneIndex(Name);if(I==INDEX_NONE)return false;
        FTransform T=Ref.GetRefBonePose()[I];
        while((I=Ref.GetParentIndex(I))!=INDEX_NONE)T=T*Ref.GetRefBonePose()[I];
        P=T.GetLocation();return !P.ContainsNaN();
    };
    FVector L,R,LA,RA,Hip,Head;
    if(!Position(LeftThighBone,L)||!Position(RightThighBone,R)||!Position(LeftArmBone,LA)||!Position(RightArmBone,RA)||!Position(HipBone,Hip)||!Position(HeadBone,Head))return false;
    const FVector Up=(Head-Hip).GetSafeNormal();
    const FVector PelvisRight=(R-L).GetSafeNormal(),ShoulderRight=(RA-LA).GetSafeNormal();
    if(FVector::Dist(L,R)<1||FVector::Dist(LA,RA)<1||Up.Z<.85||FVector::DotProduct(PelvisRight,ShoulderRight)<.8)return false;
    // UE's +Y is anatomical right, +Z is up. Measure AFTER FBX conversion.
    ImportedForward=FVector::CrossProduct((PelvisRight+ShoulderRight).GetSafeNormal(),Up).GetSafeNormal2D();
    MeshFacingYaw=-ImportedForward.Rotation().Yaw;
    float Fault=0;
    if(FParse::Param(FCommandLine::Get(),TEXT("GameDemoFacingTest")))FParse::Value(FCommandLine::Get(),TEXT("PipelineFacingFault="),Fault);
    GetMesh()->SetRelativeRotation(FRotator(0,MeshFacingYaw+Fault,0));
    UE_LOG(LogTemp,Display,TEXT("PIPELINE_FACING %s imported=(%.3f,%.3f) correction=%.3f fault=%.1f"),IsBoss?TEXT("boss"):TEXT("player"),ImportedForward.X,ImportedForward.Y,MeshFacingYaw,Fault);
    return true;
}

FVector AGameDemoFighter::BodyForward() const
{
    // The torso indicates facing; hips may turn sideways in an authored strafe.
    const FVector Right=GetMesh()->GetSocketLocation(RightArmBone)-GetMesh()->GetSocketLocation(LeftArmBone);
    return FVector::CrossProduct(Right,FVector::UpVector).GetSafeNormal2D();
}

void AGameDemoFighter::UpdateFacingQA(float Dt)
{
    FacingQAAge+=Dt;
    auto* PC=Cast<APlayerController>(GetController());if(!PC||!Opponent)return;
    if(FacingQAAge<2)return;
    const int32 Next=FMath::FloorToInt((FacingQAAge-2)/1.8f);
    if(Next>=20)
    {
        for(const FKey& K:FacingKeys)PC->InputKey(FInputKeyEventArgs::CreateSimulated(K,IE_Released,0));
        FacingKeys.Reset();WriteFacingQA();FacingQAComplete=true;
        if(FParse::Param(FCommandLine::Get(),TEXT("PipelineExit")))FPlatformMisc::RequestExit(false);
        return;
    }
    if(Next!=FacingCase)
    {
        for(const FKey& K:FacingKeys)PC->InputKey(FInputKeyEventArgs::CreateSimulated(K,IE_Released,0));
        FacingKeys.Reset();ResetDuel();FacingCase=Next;
        const FVector Center=(SpawnPosition+Opponent->SpawnPosition)*.5f;
        FVector P=Center;P.Z=SpawnPosition.Z;
        FVector B=Center;B.Z=Opponent->SpawnPosition.Z;B.Y-=550;
        CameraBoom->SetWorldRotation(FRotator(CameraPitch,CameraYaw+(Next<12?(Next/4)*83.f:0),0));
        Camera->SetOrthoWidth(FMath::Min(CameraWidthCm,1250.f));
        if(Next>=16)
        {
            const FVector To=FRotator(0,(Next-16)*90.f,0).Vector();
            B=Center;B.Z=Opponent->SpawnPosition.Z;P=B+To*350;P.Z=SpawnPosition.Z;
            Opponent->Engaged=true;Opponent->Cooldown=100;
        }
        SetActorLocation(P);Opponent->SetActorLocation(B);FacingPreviousPosition=Next>=16?B:P;
        Locked=Next>=12&&Next<16;
        if(Next<16)
        {
            GetCapsuleComponent()->SetCollisionResponseToChannel(ECC_Pawn,ECR_Ignore);
            Opponent->GetCharacterMovement()->DisableMovement();
            const FKey K=Directions[Next%4];FacingKeys.Add(K);
            PC->InputKey(FInputKeyEventArgs::CreateSimulated(K,IE_Pressed,1));
        }
    }
}

void AGameDemoFighter::SampleFacingQA()
{
    if(!FacingQAMode||FacingQAComplete||FacingCase<0||!Opponent)return;
    auto* PC=Cast<APlayerController>(GetController());if(!PC)return;
    auto* F=FacingCase>=16?Opponent.Get():this;
    FVector Step=F->GetActorLocation()-FacingPreviousPosition;FacingPreviousPosition=F->GetActorLocation();
    // A high-res capture can draw the HUD twice without a new simulation step.
    if(FacingCase<16&&Step.Size2D()<KINDA_SMALL_NUMBER)return;
    const float Phase=FMath::Fmod(FacingQAAge-2,1.8f);
    if(Phase<.85f||Phase>1.65f)return;
    FFacingSample& S=FacingSamples[FacingCase];
    const bool Aim=FacingCase>=12;
    const FVector Wanted=Aim?(F->Opponent->GetActorLocation()-F->GetActorLocation()).GetSafeNormal2D():Step.GetSafeNormal2D();
    if(Wanted.IsNearlyZero())return;
    const float Error=Angle(F->BodyForward(),Wanted);
    S.MaxBodyError=FMath::Max(S.MaxBodyError,Error);S.BodyErrorSum+=Error;S.Travel+=Step.Size2D();
    if(FacingCase<16)
    {
        FVector2D Start,End;
        const FVector HorizontalStep(Step.X,Step.Y,0);
        const bool Visible=PC->ProjectWorldLocationToScreen(F->GetActorLocation(),Start)&&PC->ProjectWorldLocationToScreen(F->GetActorLocation()+HorizontalStep*100,End);
        const FVector2D Delta=(End-Start).GetSafeNormal();
        const float InputError=Visible&&!Step.IsNearlyZero()?FMath::RadiansToDegrees(FMath::Acos(FMath::Clamp(FVector2D::DotProduct(Delta,ScreenDirections[FacingCase%4]),-1.,1.))):180;
        S.MaxInputError=FMath::Max(S.MaxInputError,InputError);
    }
    ++S.Frames;
    if(S.Frames==12)
    {
        FHitResult Hit;FCollisionQueryParams Params;Params.AddIgnoredActor(F);
        GetWorld()->SweepSingleByChannel(Hit,F->GetActorLocation(),F->GetActorLocation()+F->MoveDirection*100,FQuat::Identity,ECC_Pawn,FCollisionShape::MakeCapsule(F->GetCapsuleComponent()->GetScaledCapsuleRadius(),F->GetCapsuleComponent()->GetScaledCapsuleHalfHeight()),Params);
        UE_LOG(LogTemp,Display,TEXT("FACING_SAMPLE case=%d pos=%s velocity=%s clip=%d blocked=%s normal=%s"),FacingCase,*F->GetActorLocation().ToString(),*F->GetVelocity().ToString(),F->ActiveClip,*GetNameSafe(Hit.GetActor()),*Hit.Normal.ToString());
    }
    if(S.Frames==12&&(FacingCase<4||FacingCase==13||FacingCase==16))PC->ConsoleCommand(TEXT("HighResShot 1"));
}

void AGameDemoFighter::WriteFacingQA()
{
    auto O=MakeShared<FJsonObject>();TArray<TSharedPtr<FJsonValue>> Rows;
    bool Passed=FacingCalibrated&&Opponent&&Opponent->FacingCalibrated;
    for(int32 I=0;I<FacingSamples.Num();++I)
    {
        const auto& S=FacingSamples[I];auto Row=MakeShared<FJsonObject>();
        const float Mean=S.BodyErrorSum/FMath::Max(1,S.Frames);
        const bool Good=S.Frames>=12&&Mean<30&&S.MaxBodyError<50&&(I>=16||(S.MaxInputError<8&&S.Travel>60));Passed&=Good;
        Row->SetNumberField(TEXT("case"),I);Row->SetStringField(TEXT("mode"),I<12?TEXT("free_move"):I<16?TEXT("locked_strafe"):TEXT("boss_tracking"));
        Row->SetStringField(TEXT("direction"),Directions[I%4].ToString());Row->SetNumberField(TEXT("camera_yaw"),CameraYaw+(I<12?(I/4)*83.f:0));
        Row->SetNumberField(TEXT("frames"),S.Frames);Row->SetNumberField(TEXT("travel_cm"),S.Travel);
        Row->SetNumberField(TEXT("max_screen_input_error_deg"),S.MaxInputError);Row->SetNumberField(TEXT("mean_body_facing_error_deg"),Mean);Row->SetNumberField(TEXT("max_body_facing_error_deg"),S.MaxBodyError);Row->SetBoolField(TEXT("passed"),Good);
        Rows.Add(MakeShared<FJsonValueObject>(Row));
    }
    O->SetArrayField(TEXT("cases"),Rows);O->SetBoolField(TEXT("facing_and_input_consistent"),Passed);
    for(auto* F:{this,Opponent.Get()})if(F)
    {
        auto C=MakeShared<FJsonObject>();C->SetBoolField(TEXT("calibrated"),F->FacingCalibrated);C->SetNumberField(TEXT("mesh_yaw_correction_deg"),F->MeshFacingYaw);
        C->SetNumberField(TEXT("imported_forward_x"),F->ImportedForward.X);C->SetNumberField(TEXT("imported_forward_y"),F->ImportedForward.Y);
        O->SetObjectField(F->IsBoss?TEXT("boss"):TEXT("player"),C);
    }
    SaveQA(O,TEXT("GameDemoFacingQA.json"));
}

void AGameDemoFighter::UpdateArtQA()
{
    auto* PC=Cast<APlayerController>(GetController());if(!PC)return;
    if(FParse::Param(FCommandLine::Get(),TEXT("PipelinePlaceReview")))
    {
        // This is an environmental camera anchor, not the physical route test.
        // A landmark center can lie inside a fountain or a garden structure.
        // Prevent depenetration from silently moving its observation camera.
        GetCharacterMovement()->DisableMovement();
        GetCapsuleComponent()->SetCollisionEnabled(ECollisionEnabled::NoCollision);
        const bool Oblique=FParse::Param(FCommandLine::Get(),TEXT("PipelinePlaceOblique"));
        const int32 PlaceCount=ExplorationPlaces.Num(),Count=Oblique?PlaceCount:PlaceCount*2,Index=ArtQAStage/2;
        if(Index>=Count)
        {
            if(WorldAge>6+(Count-1)*4)
            {
                auto O=MakeShared<FJsonObject>();O->SetBoolField(TEXT("current_runtime_views"),ArtQAFramingValid);O->SetBoolField(TEXT("view_centres_verified"),ArtQAFramingValid);O->SetBoolField(TEXT("ground_camera_clearance_verified"),ArtQAFramingValid);O->SetBoolField(TEXT("environment_camera_only"),true);O->SetNumberField(TEXT("view_count"),ArtQAProjectedFocus.Num());
                O->SetBoolField(TEXT("oblique_perspective"),Oblique);
                TArray<TSharedPtr<FJsonValue>> Rows;
                for(int32 I=0;I<ArtQAProjectedFocus.Num();++I){auto Row=MakeShared<FJsonObject>();Row->SetNumberField(TEXT("view"),I);Row->SetNumberField(TEXT("place_index"),I%PlaceCount);Row->SetStringField(TEXT("condition"),I<PlaceCount?TEXT("elevated"):TEXT("ground"));Row->SetStringField(TEXT("normalized_projected_focus"),ArtQAProjectedFocus[I].ToString());Row->SetStringField(TEXT("place_cm"),ExplorationPlaces[I%PlaceCount].ToString());Rows.Add(MakeShared<FJsonValueObject>(Row));}
                O->SetArrayField(TEXT("view_focus"),Rows);SaveQA(O,TEXT("GameDemoArtQA.json"));
                if(FParse::Param(FCommandLine::Get(),TEXT("PipelineExit")))FPlatformMisc::RequestExit(false);
            }
            return;
        }
        if(ArtQAStage%2==0)
        {
            const bool Ground=!Oblique&&Index>=PlaceCount;const FVector Center=ExplorationPlaces[Index%PlaceCount];
            // UE's automatic ortho-plane correction centres the owning view
            // target, not a displaced spring-arm pivot. Move the QA-only anchor
            // to the requested place; the separate route test still walks there.
            SetActorLocation(Center+FVector(0,0,CharacterHeightCm*.49f+2.5f),false,nullptr,ETeleportType::TeleportPhysics);
            GetCharacterMovement()->StopMovementImmediately();
            SetViewMode((Ground||Oblique)?1:2);CameraBoom->bDoCollisionTest=false;
            GetMesh()->SetVisibility(false,true);
            CameraBoom->TargetOffset=(Ground||Oblique)?Center-GetActorLocation()+FVector(0,0,Oblique?320:160):FVector::ZeroVector;
            CameraBoom->TargetArmLength=Oblique?2100:Ground?700:15000;
            FRotator ObservationRotation(Oblique?-30:Ground?-5:-82,CameraYaw+(Oblique?215:180),0);
            if(Oblique)
            {
                const FVector Focus=Center+FVector(0,0,320);
                const float Offsets[]={0,45,-45,90,-90,135,-135,180};
                FCollisionQueryParams Query(SCENE_QUERY_STAT(ObliqueCameraClearance),true,this);
                if(Opponent)Query.AddIgnoredActor(Opponent.Get());
                bool Clear=false;
                for(float Pitch:{-30.f,-38.f,-45.f})
                {
                    for(float Offset:Offsets)
                    {
                        const FRotator Candidate(Pitch,CameraYaw+215+Offset,0);
                        const FVector Eye=Focus-Candidate.Vector()*2100;
                        const FVector End=Eye+Candidate.Vector()*600;
                        FHitResult Hit;
                        if(GetWorld()->SweepSingleByChannel(Hit,Eye,End,FQuat::Identity,ECC_Visibility,FCollisionShape::MakeSphere(25),Query))continue;
                        if(GetWorld()->SweepSingleByChannel(Hit,End,Eye,FQuat::Identity,ECC_Visibility,FCollisionShape::MakeSphere(25),Query))continue;
                        ObservationRotation=Candidate;Clear=true;break;
                    }
                    if(Clear)break;
                }
                ArtQAFramingValid&=Clear;
                UE_LOG(LogTemp,Display,TEXT("OBLIQUE_CAMERA index=%d foreground_clear=%d rotation=%s"),Index,Clear,*ObservationRotation.ToString());
            }
            if(Ground)
            {
                // Centering a place does not prove that the eye is outside a
                // building. Search bounded azimuths at the same lens/radius.
                // Keep the final 1.8m around the focus available to a landmark
                // itself (for example a fountain bowl), but require a clear
                // camera and foreground. This does not alter gameplay cameras.
                const FVector Focus=Center+FVector(0,0,160);
                const float Offsets[]={0,30,-30,60,-60,90,-90,120,-120,150,-150,180};
                FCollisionQueryParams Query(SCENE_QUERY_STAT(PlaceCameraClearance),true,this);
                if(Opponent)Query.AddIgnoredActor(Opponent.Get());
                bool Clear=false;
                for(float Offset:Offsets)
                {
                    const FRotator Candidate(-5,CameraYaw+180+Offset,0);
                    const FVector Eye=Focus-Candidate.Vector()*700;
                    const FVector ForegroundEnd=Focus+(Eye-Focus).GetSafeNormal()*180;
                    FHitResult Hit;
                    if(GetWorld()->SweepSingleByChannel(Hit,Eye,ForegroundEnd,FQuat::Identity,ECC_Visibility,FCollisionShape::MakeSphere(25),Query))continue;
                    // Reverse testing also detects an eye embedded behind a
                    // single-sided collision panel; keep authored winding.
                    if(GetWorld()->SweepSingleByChannel(Hit,ForegroundEnd,Eye,FQuat::Identity,ECC_Visibility,FCollisionShape::MakeSphere(25),Query))continue;
                    ObservationRotation=Candidate;Clear=true;
                    UE_LOG(LogTemp,Display,TEXT("PLACE_CAMERA index=%d offset=%.0f eye=%s foreground_clear=1"),Index,Offset,*Eye.ToString());
                    break;
                }
                ArtQAFramingValid&=Clear;
                if(!Clear)UE_LOG(LogTemp,Warning,TEXT("PLACE_CAMERA index=%d no unobstructed ground view"),Index);
            }
            CameraBoom->SetWorldRotation(ObservationRotation);
            if(!Ground&&!Oblique)Camera->SetOrthoWidth(4000);else Camera->SetFieldOfView(Oblique?80:90);
            ++ArtQAStage;return;
        }
        if(WorldAge>4+Index*4)
        {
            const FVector Focus=Oblique?ExplorationPlaces[Index%PlaceCount]+FVector(0,0,320):Index>=PlaceCount?ExplorationPlaces[Index%PlaceCount]+FVector(0,0,160):GetActorLocation();
            int32 W=0,H=0;PC->GetViewportSize(W,H);FVector2D P(-1,-1);
            const bool Visible=PC->ProjectWorldLocationToScreen(Focus,P);
            const FVector2D UV(W>0?P.X/W:-1,H>0?P.Y/H:-1);
            const float CameraDistance=FVector::Distance(Camera->GetComponentLocation(),Focus);
            if(Oblique)ArtQAFramingValid&=FMath::Abs(CameraDistance-2100)<2;
            UE_LOG(LogTemp,Display,TEXT("ART_CAMERA_DISTANCE index=%d oblique=%d actual_cm=%.4f"),Index,Oblique,CameraDistance);
            ArtQAFramingValid&=Visible&&FMath::Abs(UV.X-.5)<.025&&FMath::Abs(UV.Y-.5)<.025;
            ArtQAProjectedFocus.Add(UV);
            UE_LOG(LogTemp,Display,TEXT("PLACE_VIEW index=%d focus=%s projected=%s valid=%d"),Index,*Focus.ToString(),*UV.ToString(),ArtQAFramingValid);
            PC->ConsoleCommand(TEXT("HighResShot 1"));++ArtQAStage;
        }
        return;
    }
    if(ArtQAStage==0)
    {
        // Overview is evidence of the district, distinct from the player camera.
        // Size it to the authored itinerary instead of a fixed court-only crop.
        float Extent=CameraWidthCm*.65f;
        for(const FVector& P:ExplorationWaypoints)Extent=FMath::Max(Extent,FVector::Dist2D(P,GetActorLocation()));
        Camera->SetOrthoWidth(FMath::Max(CameraWidthCm*1.65f,Extent*2.6f));
        CameraBoom->TargetArmLength=FMath::Max(7000.f,Extent*2.8f);
        CameraBoom->SetWorldRotation(FRotator(-60,CameraYaw+25,0));ArtQAStage=1;
    }
    if(ArtQAStage==1&&WorldAge>4){PC->ConsoleCommand(TEXT("HighResShot 1"));ArtQAStage=2;}
    if(ArtQAStage==2&&WorldAge>5){CameraBoom->SetWorldRotation(FRotator(-65,CameraYaw+125,0));ArtQAStage=3;}
    if(ArtQAStage==3&&WorldAge>8){PC->ConsoleCommand(TEXT("HighResShot 1"));ArtQAStage=4;}
    if(ArtQAStage==4&&WorldAge>10)
    {
        auto O=MakeShared<FJsonObject>();O->SetBoolField(TEXT("current_runtime_views"),true);O->SetNumberField(TEXT("view_count"),2);SaveQA(O,TEXT("GameDemoArtQA.json"));
        ArtQAStage=5;if(FParse::Param(FCommandLine::Get(),TEXT("PipelineExit")))FPlatformMisc::RequestExit(false);
    }
}
