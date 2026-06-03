namespace QuackDuck.Presentation.Wpf.SettingsWeb;

internal sealed record SettingsBridgeResponse(
    int Id,
    bool Ok,
    object? Result,
    string? Error);
