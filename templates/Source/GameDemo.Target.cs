using UnrealBuildTool;
public class GameDemoTarget : TargetRules
{
    public GameDemoTarget(TargetInfo Target) : base(Target)
    {
        Type = TargetType.Game;
        DefaultBuildSettings = BuildSettingsVersion.V7;
        IncludeOrderVersion = EngineIncludeOrderVersion.Latest;
        ExtraModuleNames.Add("GameDemo");
    }
}
