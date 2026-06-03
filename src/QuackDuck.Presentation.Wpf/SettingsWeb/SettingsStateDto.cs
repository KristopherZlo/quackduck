using System.Reflection;
using System.IO;
using System.Text.Json.Serialization;
using QuackDuck.Application;
using QuackDuck.Infrastructure.Skins;

namespace QuackDuck.Presentation.Wpf.SettingsWeb;

internal sealed class SettingsStateDto
{
    [JsonPropertyName("version")]
    public string Version { get; init; } = string.Empty;

    [JsonPropertyName("pet_name")]
    public string PetName { get; init; } = string.Empty;

    [JsonPropertyName("show_name")]
    public bool ShowName { get; init; }

    [JsonPropertyName("pet_size")]
    public int PetSize { get; init; }

    [JsonPropertyName("skin_folder")]
    public string SkinFolder { get; init; } = string.Empty;

    [JsonPropertyName("selected_skin")]
    public string SelectedSkin { get; init; } = string.Empty;

    [JsonPropertyName("language")]
    public string Language { get; init; } = "en";

    [JsonPropertyName("floor_level")]
    public int FloorLevel { get; init; }

    [JsonPropertyName("name_offset")]
    public int NameOffset { get; init; }

    [JsonPropertyName("font_size")]
    public int FontSize { get; init; }

    [JsonPropertyName("autostart")]
    public bool Autostart { get; init; }

    [JsonPropertyName("random_behavior")]
    public bool RandomBehavior { get; init; }

    [JsonPropertyName("idle_duration")]
    public double IdleDuration { get; init; }

    [JsonPropertyName("sleep_timeout")]
    public double SleepTimeout { get; init; }

    [JsonPropertyName("direction_interval")]
    public double DirectionInterval { get; init; }

    [JsonPropertyName("playful_chance")]
    public int PlayfulChance { get; init; }

    [JsonPropertyName("sound_enabled")]
    public bool SoundEnabled { get; init; }

    [JsonPropertyName("sound_volume")]
    public int SoundVolume { get; init; }

    [JsonPropertyName("activation_threshold")]
    public int ActivationThreshold { get; init; }

    [JsonPropertyName("sound_response_probability")]
    public int SoundResponseProbability { get; init; }

    [JsonPropertyName("mic_level")]
    public int MicLevel { get; init; }

    [JsonPropertyName("idle_frames")]
    public IReadOnlyList<string> IdleFrames { get; init; } = Array.Empty<string>();

    [JsonPropertyName("skin_previews")]
    public IReadOnlyList<SkinAnimationPreview> SkinPreviews { get; init; } = Array.Empty<SkinAnimationPreview>();

    public static async Task<SettingsStateDto> CreateAsync(PetEngine engine, CancellationToken cancellationToken = default)
    {
        var settings = engine.Settings;
        var skins = await engine.DiscoverSkinsAsync(settings.SkinFolder, cancellationToken);
        var skinPreviews = new SkinAnimationPreviewBuilder().Build(skins, settings.SelectedSkin);
        var idleFrames = skinPreviews.FirstOrDefault(preview => preview.IsSelected)?.Frames ??
                         skinPreviews.FirstOrDefault()?.Frames ??
                         Array.Empty<string>();

        return new SettingsStateDto
        {
            Version = Assembly.GetEntryAssembly()?.GetName().Version?.ToString() ?? "1.5.3",
            PetName = settings.PetName,
            ShowName = settings.ShowName,
            PetSize = settings.PetSize,
            SkinFolder = settings.SkinFolder ?? string.Empty,
            SelectedSkin = settings.SelectedSkin ?? string.Empty,
            Language = settings.CurrentLanguage,
            FloorLevel = settings.GroundLevelOffset,
            NameOffset = settings.NameOffsetY,
            FontSize = settings.FontBaseSize,
            Autostart = settings.AutostartEnabled,
            RandomBehavior = settings.RandomBehaviorEnabled,
            IdleDuration = settings.IdleDurationSeconds,
            SleepTimeout = settings.SleepTimeoutSeconds,
            DirectionInterval = settings.DirectionChangeIntervalSeconds,
            PlayfulChance = Percent(settings.PlayfulBehaviorProbability),
            SoundEnabled = settings.SoundEnabled,
            SoundVolume = Percent(settings.SoundVolume),
            ActivationThreshold = settings.ActivationThreshold,
            SoundResponseProbability = Percent(settings.SoundResponseProbability),
            MicLevel = engine.LastMicLevel,
            IdleFrames = idleFrames,
            SkinPreviews = skinPreviews
        };
    }

    private static int Percent(double value) => (int)Math.Round(Math.Clamp(value, 0, 1) * 100);
}
