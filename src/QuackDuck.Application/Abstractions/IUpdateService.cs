namespace QuackDuck.Application.Abstractions;

public record UpdateInfo(
    string Version,
    string Notes,
    string ReleaseUrl,
    string AssetName,
    string DownloadUrl);

public interface IUpdateService
{
    Task<UpdateInfo?> CheckForUpdatesAsync(CancellationToken cancellationToken = default);
    Task<bool> DownloadAndApplyAsync(UpdateInfo info, IProgress<int>? progress = null, CancellationToken cancellationToken = default);
}
