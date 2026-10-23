using UnrealBuildTool;
public class GameDemo : ModuleRules
{
    public GameDemo(ReadOnlyTargetRules Target) : base(Target)
    {
        PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
        PublicDependencyModuleNames.AddRange(new string[] {"Core", "CoreUObject", "Engine", "InputCore", "Json", "JsonUtilities"});
        PrivateDependencyModuleNames.AddRange(new string[] {"MovieSceneCapture", "Slate", "SlateCore", "RenderCore", "RHI", "ImageCore"});
    }
}
