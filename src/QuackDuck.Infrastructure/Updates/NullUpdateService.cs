using QuackDuck.Application.Abstractions;

namespace QuackDuck.Infrastructure.Updates;

/// <summary>
/// Stub update service. Real GitHub-based updater will be added later.
/// </summary>
public sealed class NullUpdateService : IUpdateService
{
    public Task<UpdateInfo?> CheckForUpdatesAsync(CancellationToken cancellationToken = default) =>
        Task.FromResult<UpdateInfo?>(null);

    public Task<bool> DownloadAndApplyAsync(UpdateInfo info, IProgress<int>? progress = null, CancellationToken cancellationToken = default) =>
        Task.FromResult(false);
}
