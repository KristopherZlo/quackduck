using System.IO;
using System.Text.Json;
using QuackDuck.Application.Abstractions;
using QuackDuck.Domain.Pets;

namespace QuackDuck.Infrastructure.Settings;

public sealed class JsonSettingsStore : ISettingsStore
{
    private readonly IAppPathProvider _paths;
    private readonly string _settingsFile;
    private readonly JsonSerializerOptions _jsonOptions = new()
    {
        PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
        WriteIndented = true
    };

    public JsonSettingsStore(IAppPathProvider paths)
    {
        _paths = paths;
        _settingsFile = Path.Combine(_paths.DataRoot, "settings.json");
    }

    public async Task<PetSettings> LoadAsync(CancellationToken cancellationToken = default)
    {
        if (!File.Exists(_settingsFile))
        {
            return PetSettings.Default;
        }

        await using var stream = File.OpenRead(_settingsFile);
        var settings = await JsonSerializer.DeserializeAsync<PetSettings>(stream, _jsonOptions, cancellationToken);
        return settings ?? PetSettings.Default;
    }

    public async Task SaveAsync(PetSettings settings, CancellationToken cancellationToken = default)
    {
        Directory.CreateDirectory(_paths.DataRoot);
        await using var stream = File.Create(_settingsFile);
        await JsonSerializer.SerializeAsync(stream, settings, _jsonOptions, cancellationToken);
    }
}
