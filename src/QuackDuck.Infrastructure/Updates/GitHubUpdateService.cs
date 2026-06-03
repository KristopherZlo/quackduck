using System.Diagnostics;
using System.IO;
using System.IO.Compression;
using System.Net.Http;
using System.Net.Http.Headers;
using System.Text.Json;
using QuackDuck.Application.Abstractions;

namespace QuackDuck.Infrastructure.Updates;

public sealed class GitHubUpdateOptions
{
    public string Owner { get; init; } = "KristopherZlo";
    public string Repository { get; init; } = "quackduck";
    public string CurrentVersion { get; init; } = "0.0.0";
    public string SkippedVersion { get; init; } = string.Empty;
    public bool InstallEnabled { get; init; }
    public string AppDirectory { get; init; } = AppContext.BaseDirectory;
    public string MainExecutablePath { get; init; } = string.Empty;
    public string UpdaterExecutablePath { get; init; } = string.Empty;
    public string TempDirectory { get; init; } = Path.Combine(Path.GetTempPath(), "quackduck-update");
}

public interface IUpdateInstallerLauncher
{
    Task LaunchAsync(
        string sourceDirectory,
        string appDirectory,
        string mainExecutablePath,
        int parentProcessId,
        CancellationToken cancellationToken = default);
}

public sealed class GitHubUpdateService : IUpdateService
{
    private readonly GitHubUpdateOptions _options;
    private readonly HttpClient _httpClient;
    private readonly IUpdateInstallerLauncher _launcher;

    public GitHubUpdateService(GitHubUpdateOptions options, HttpClient? httpClient = null, IUpdateInstallerLauncher? launcher = null)
    {
        _options = options;
        _httpClient = httpClient ?? new HttpClient();
        _launcher = launcher ?? new ProcessUpdateInstallerLauncher(options.UpdaterExecutablePath);

        if (_httpClient.DefaultRequestHeaders.UserAgent.Count == 0)
        {
            _httpClient.DefaultRequestHeaders.UserAgent.Add(new ProductInfoHeaderValue("QuackDuck", "1.0"));
        }
    }

    public async Task<UpdateInfo?> CheckForUpdatesAsync(CancellationToken cancellationToken = default)
    {
        var uri = $"https://api.github.com/repos/{_options.Owner}/{_options.Repository}/releases/latest";
        using var response = await _httpClient.GetAsync(uri, cancellationToken);
        if (!response.IsSuccessStatusCode)
        {
            return null;
        }

        await using var stream = await response.Content.ReadAsStreamAsync(cancellationToken);
        using var document = await JsonDocument.ParseAsync(stream, cancellationToken: cancellationToken);
        var root = document.RootElement;

        var latest = NormalizeVersion(ReadString(root, "tag_name"));
        var current = NormalizeVersion(_options.CurrentVersion);
        if (!IsNewerVersion(latest, current))
        {
            return null;
        }

        if (string.Equals(latest, NormalizeVersion(_options.SkippedVersion), StringComparison.OrdinalIgnoreCase))
        {
            return null;
        }

        if (!TryGetZipAsset(root, out var assetName, out var downloadUrl))
        {
            return null;
        }

        return new UpdateInfo(
            latest,
            ReadString(root, "body"),
            ReadString(root, "html_url"),
            assetName,
            downloadUrl);
    }

    public async Task<bool> DownloadAndApplyAsync(UpdateInfo info, IProgress<int>? progress = null, CancellationToken cancellationToken = default)
    {
        if (!_options.InstallEnabled ||
            string.IsNullOrWhiteSpace(info.DownloadUrl) ||
            string.IsNullOrWhiteSpace(_options.MainExecutablePath) ||
            string.IsNullOrWhiteSpace(_options.AppDirectory))
        {
            return false;
        }

        Directory.CreateDirectory(_options.TempDirectory);
        var zipPath = Path.Combine(_options.TempDirectory, info.AssetName);
        var extractDirectory = Path.Combine(_options.TempDirectory, "extracted");
        if (Directory.Exists(extractDirectory))
        {
            Directory.Delete(extractDirectory, recursive: true);
        }

        progress?.Report(5);
        await using (var input = await _httpClient.GetStreamAsync(info.DownloadUrl, cancellationToken))
        await using (var output = File.Create(zipPath))
        {
            await input.CopyToAsync(output, cancellationToken);
        }

        progress?.Report(65);
        ZipFile.ExtractToDirectory(zipPath, extractDirectory, overwriteFiles: true);
        progress?.Report(85);

        await _launcher.LaunchAsync(
            extractDirectory,
            _options.AppDirectory,
            _options.MainExecutablePath,
            Environment.ProcessId,
            cancellationToken);

        progress?.Report(100);
        return true;
    }

    private static bool TryGetZipAsset(JsonElement release, out string assetName, out string downloadUrl)
    {
        assetName = string.Empty;
        downloadUrl = string.Empty;

        if (!release.TryGetProperty("assets", out var assets) || assets.ValueKind != JsonValueKind.Array)
        {
            return false;
        }

        foreach (var asset in assets.EnumerateArray())
        {
            var name = ReadString(asset, "name");
            var url = ReadString(asset, "browser_download_url");
            if (name.EndsWith(".zip", StringComparison.OrdinalIgnoreCase) && !string.IsNullOrWhiteSpace(url))
            {
                assetName = name;
                downloadUrl = url;
                return true;
            }
        }

        return false;
    }

    private static bool IsNewerVersion(string latest, string current)
    {
        var latestVersion = ParseVersion(latest);
        var currentVersion = ParseVersion(current);
        if (latestVersion == null || currentVersion == null)
        {
            return string.Compare(latest, current, StringComparison.OrdinalIgnoreCase) > 0;
        }

        return latestVersion > currentVersion;
    }

    private static Version? ParseVersion(string value)
    {
        var normalized = NormalizeVersion(value);
        if (string.IsNullOrWhiteSpace(normalized))
        {
            return null;
        }

        var parts = normalized.Split('.', StringSplitOptions.RemoveEmptyEntries).ToList();
        while (parts.Count < 3)
        {
            parts.Add("0");
        }

        return Version.TryParse(string.Join('.', parts), out var version) ? version : null;
    }

    private static string NormalizeVersion(string? version)
    {
        if (string.IsNullOrWhiteSpace(version))
        {
            return string.Empty;
        }

        var normalized = version.Trim();
        if (normalized.StartsWith('v') || normalized.StartsWith('V'))
        {
            normalized = normalized[1..];
        }

        var prereleaseIndex = normalized.IndexOf('-', StringComparison.Ordinal);
        if (prereleaseIndex >= 0)
        {
            normalized = normalized[..prereleaseIndex];
        }

        return normalized;
    }

    private static string ReadString(JsonElement element, string propertyName)
    {
        return element.TryGetProperty(propertyName, out var property) && property.ValueKind == JsonValueKind.String
            ? property.GetString() ?? string.Empty
            : string.Empty;
    }
}

internal sealed class ProcessUpdateInstallerLauncher : IUpdateInstallerLauncher
{
    private readonly string _updaterExecutablePath;

    public ProcessUpdateInstallerLauncher(string updaterExecutablePath)
    {
        _updaterExecutablePath = updaterExecutablePath;
    }

    public Task LaunchAsync(
        string sourceDirectory,
        string appDirectory,
        string mainExecutablePath,
        int parentProcessId,
        CancellationToken cancellationToken = default)
    {
        if (string.IsNullOrWhiteSpace(_updaterExecutablePath) || !File.Exists(_updaterExecutablePath))
        {
            return Task.FromResult(false);
        }

        Process.Start(new ProcessStartInfo
        {
            FileName = _updaterExecutablePath,
            ArgumentList =
            {
                "--parent-pid", parentProcessId.ToString(),
                "--source", sourceDirectory,
                "--app-dir", appDirectory,
                "--main-exe", mainExecutablePath
            },
            UseShellExecute = true
        });

        return Task.CompletedTask;
    }
}
