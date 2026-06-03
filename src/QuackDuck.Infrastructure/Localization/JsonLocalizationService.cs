using System.IO;
using System.Text.Json;
using QuackDuck.Application.Abstractions;

namespace QuackDuck.Infrastructure.Localization;

public sealed class JsonLocalizationService : ILocalizationService
{
    private readonly IAppPathProvider _paths;
    private readonly Dictionary<string, string> _translations = new(StringComparer.OrdinalIgnoreCase);
    private const string DefaultLanguage = "en";

    public JsonLocalizationService(IAppPathProvider paths)
    {
        _paths = paths;
        CurrentLanguage = DefaultLanguage;
    }

    public string CurrentLanguage { get; private set; }

    public async Task<IDictionary<string, string>> LoadAsync(string languageCode, CancellationToken cancellationToken = default)
    {
        var safeCode = Normalize(languageCode);
        var loaded = await LoadFileAsync(safeCode, cancellationToken)
                     ?? await LoadFileAsync(DefaultLanguage, cancellationToken)
                     ?? new Dictionary<string, string>();

        _translations.Clear();
        foreach (var pair in loaded)
        {
            _translations[pair.Key] = pair.Value;
        }
        CurrentLanguage = safeCode;
        return _translations;
    }

    public string Translate(string key, string fallback = "")
    {
        if (string.IsNullOrWhiteSpace(key))
        {
            return fallback;
        }

        return _translations.TryGetValue(key, out var value) ? value : fallback;
    }

    private static string Normalize(string languageCode)
    {
        var safe = (languageCode ?? DefaultLanguage).Split('.')[0].Trim().ToLowerInvariant();
        return string.IsNullOrWhiteSpace(safe) ? DefaultLanguage : safe;
    }

    private async Task<Dictionary<string, string>?> LoadFileAsync(string languageCode, CancellationToken cancellationToken)
    {
        var filePath = Path.Combine(_paths.LanguagesRoot, $"lang_{languageCode}.json");
        if (!File.Exists(filePath))
        {
            return null;
        }

        await using var stream = File.OpenRead(filePath);
        return await JsonSerializer.DeserializeAsync<Dictionary<string, string>>(stream, cancellationToken: cancellationToken);
    }
}
