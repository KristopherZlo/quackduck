using System.Text.Json.Serialization;
using QuackDuck.Domain.Pets;

namespace QuackDuck.Presentation.Wpf.SettingsWeb;

internal sealed class SettingsUpdateDto
{
    [JsonPropertyName("pet_name")]
    public string? PetName { get; init; }

    [JsonPropertyName("show_name")]
    public bool? ShowName { get; init; }

    [JsonPropertyName("pet_size")]
    public int? PetSize { get; init; }

    [JsonPropertyName("skin_folder")]
    public string? SkinFolder { get; init; }

    [JsonPropertyName("selected_skin")]
    public string? SelectedSkin { get; init; }

    [JsonPropertyName("language")]
    public string? Language { get; init; }

    [JsonPropertyName("floor_level")]
    public int? FloorLevel { get; init; }

    [JsonPropertyName("name_offset")]
    public int? NameOffset { get; init; }

    [JsonPropertyName("font_size")]
    public int? FontSize { get; init; }

    [JsonPropertyName("autostart")]
    public bool? Autostart { get; init; }

    [JsonPropertyName("random_behavior")]
    public bool? RandomBehavior { get; init; }

    [JsonPropertyName("idle_duration")]
    public double? IdleDuration { get; init; }

    [JsonPropertyName("sleep_timeout")]
    public double? SleepTimeout { get; init; }

    [JsonPropertyName("direction_interval")]
    public double? DirectionInterval { get; init; }

    [JsonPropertyName("playful_chance")]
    public double? PlayfulChance { get; init; }

    [JsonPropertyName("sound_enabled")]
    public bool? SoundEnabled { get; init; }

    [JsonPropertyName("sound_volume")]
    public double? SoundVolume { get; init; }

    [JsonPropertyName("activation_threshold")]
    public int? ActivationThreshold { get; init; }

    [JsonPropertyName("sound_response_probability")]
    public double? SoundResponseProbability { get; init; }

    [JsonPropertyName("skipped_version")]
    public string? SkippedVersion { get; init; }

    public PetSettings ApplyTo(PetSettings settings)
    {
        return settings with
        {
            PetName = PetName ?? settings.PetName,
            ShowName = ShowName ?? settings.ShowName,
            PetSize = PetSize.HasValue ? Math.Clamp(PetSize.Value, 1, 8) : settings.PetSize,
            SkinFolder = SkinFolder ?? settings.SkinFolder,
            SelectedSkin = SelectedSkin ?? settings.SelectedSkin,
            CurrentLanguage = NormalizeLanguage(Language ?? settings.CurrentLanguage),
            GroundLevelOffset = FloorLevel.HasValue ? Math.Max(0, FloorLevel.Value) : settings.GroundLevelOffset,
            NameOffsetY = NameOffset.HasValue ? Math.Max(0, NameOffset.Value) : settings.NameOffsetY,
            FontBaseSize = FontSize.HasValue ? Math.Clamp(FontSize.Value, 8, 64) : settings.FontBaseSize,
            AutostartEnabled = Autostart ?? settings.AutostartEnabled,
            RandomBehaviorEnabled = RandomBehavior ?? settings.RandomBehaviorEnabled,
            IdleDurationSeconds = IdleDuration.HasValue ? Math.Max(1, IdleDuration.Value) : settings.IdleDurationSeconds,
            SleepTimeoutSeconds = SleepTimeout.HasValue ? Math.Max(5, SleepTimeout.Value) : settings.SleepTimeoutSeconds,
            DirectionChangeIntervalSeconds = DirectionInterval.HasValue ? Math.Max(1, DirectionInterval.Value) : settings.DirectionChangeIntervalSeconds,
            PlayfulBehaviorProbability = PlayfulChance.HasValue ? ToUnit(PlayfulChance.Value) : settings.PlayfulBehaviorProbability,
            SoundEnabled = SoundEnabled ?? settings.SoundEnabled,
            SoundVolume = SoundVolume.HasValue ? ToUnit(SoundVolume.Value) : settings.SoundVolume,
            ActivationThreshold = ActivationThreshold.HasValue ? Math.Clamp(ActivationThreshold.Value, 0, 100) : settings.ActivationThreshold,
            SoundResponseProbability = SoundResponseProbability.HasValue ? ToUnit(SoundResponseProbability.Value) : settings.SoundResponseProbability,
            SkippedVersion = SkippedVersion ?? settings.SkippedVersion
        };
    }

    private static string NormalizeLanguage(string language)
    {
        return language.Equals("Russian", StringComparison.OrdinalIgnoreCase) ? "ru" :
            language.Equals("English", StringComparison.OrdinalIgnoreCase) ? "en" :
            language;
    }

    private static double ToUnit(double value)
    {
        var normalized = value > 1 ? value / 100.0 : value;
        return Math.Clamp(normalized, 0, 1);
    }
}
