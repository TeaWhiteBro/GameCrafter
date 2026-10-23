using UnrealBuildTool;
public class GameDemoEditorTarget : TargetRules
{
    public GameDemoEditorTarget(TargetInfo Target) : base(Target)
    {
        Type = TargetType.Editor;
        DefaultBuildSettings = BuildSettingsVersion.V7;
        IncludeOrderVersion = EngineIncludeOrderVersion.Latest;
        ExtraModuleNames.Add("GameDemo");
    }
}
