namespace QuackDuck.Application.Abstractions;

public interface ILocalizationService
{
    string CurrentLanguage { get; }

    Task<IDictionary<string, string>> LoadAsync(string languageCode, CancellationToken cancellationToken = default);
    string Translate(string key, string fallback = "");
}
