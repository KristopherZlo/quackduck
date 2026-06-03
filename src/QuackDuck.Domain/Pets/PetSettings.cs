namespace QuackDuck.Domain.Pets;

/// <summary>
/// User-configurable settings for the pet. Mirrors the Python version to preserve behavior.
/// </summary>
public record class PetSettings
{
    public string PetName { get; init; } = string.Empty;
    public bool ShowName { get; init; } = false;
    public int NameOffsetY { get; init; } = 60;
    public int FontBaseSize { get; init; } = 14;

    public int? SelectedMicIndex { get; init; }
    public int ActivationThreshold { get; init; } = 10;
    public double SoundResponseProbability { get; init; } = 0.01;
    public bool SoundEnabled { get; init; } = true;
    public double SoundVolume { get; init; } = 0.5;

    public bool AutostartEnabled { get; init; } = false;
    public int GroundLevelOffset { get; init; } = 0;
    public int PetSize { get; init; } = 3;

    public string? SkinFolder { get; init; }
    public string? SelectedSkin { get; init; }

    public double DuckSpeed { get; init; } = 2.0;
    public bool RandomBehaviorEnabled { get; init; } = true;
    public double IdleDurationSeconds { get; init; } = 5.0;
    public double SleepTimeoutSeconds { get; init; } = 300.0;
    public double DirectionChangeIntervalSeconds { get; init; } = 20.0;
    public double PlayfulBehaviorProbability { get; init; } = 0.1;

    public string CurrentLanguage { get; init; } = "en";
    public string SkippedVersion { get; init; } = string.Empty;

    public static PetSettings Default => new();
}
