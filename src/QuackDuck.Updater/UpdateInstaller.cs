using System.Diagnostics;

namespace QuackDuck.Updater;

public sealed class UpdateInstallOptions
{
    public int? ParentProcessId { get; init; }
    public string SourceDirectory { get; init; } = string.Empty;
    public string AppDirectory { get; init; } = string.Empty;
    public string MainExecutablePath { get; init; } = string.Empty;
    public bool RestartAfterInstall { get; init; } = true;
    public string CleanupArgument { get; init; } = "--cleanup-bak";
}

public readonly record struct UpdateInstallResult(bool Succeeded, IReadOnlyList<string> BakPaths);

public sealed class UpdateInstaller
{
    private readonly Func<string, bool> _simulateDeleteFailure;

    public UpdateInstaller()
        : this(_ => false)
    {
    }

    public UpdateInstaller(Func<string, bool> simulateDeleteFailure)
    {
        _simulateDeleteFailure = simulateDeleteFailure;
    }

    public async Task<UpdateInstallResult> InstallAsync(UpdateInstallOptions options, CancellationToken cancellationToken = default)
    {
        ValidateOptions(options);
        await WaitForParentExitAsync(options.ParentProcessId, cancellationToken);

        var bakPaths = new List<string>();
        CopyDirectory(options.SourceDirectory, options.AppDirectory, bakPaths);

        if (options.RestartAfterInstall)
        {
            Process.Start(new ProcessStartInfo
            {
                FileName = options.MainExecutablePath,
                Arguments = options.CleanupArgument,
                UseShellExecute = true
            });
        }

        return new UpdateInstallResult(true, bakPaths);
    }

    private static async Task WaitForParentExitAsync(int? parentProcessId, CancellationToken cancellationToken)
    {
        if (parentProcessId == null || parentProcessId <= 0)
        {
            return;
        }

        try
        {
            using var process = Process.GetProcessById(parentProcessId.Value);
            while (!process.HasExited)
            {
                cancellationToken.ThrowIfCancellationRequested();
                await Task.Delay(200, cancellationToken);
            }
        }
        catch (ArgumentException)
        {
            // Parent already exited.
        }
    }

    private void CopyDirectory(string sourceDirectory, string targetDirectory, List<string> bakPaths)
    {
        Directory.CreateDirectory(targetDirectory);

        foreach (var directory in Directory.EnumerateDirectories(sourceDirectory, "*", SearchOption.AllDirectories))
        {
            var relative = Path.GetRelativePath(sourceDirectory, directory);
            Directory.CreateDirectory(Path.Combine(targetDirectory, relative));
        }

        foreach (var sourceFile in Directory.EnumerateFiles(sourceDirectory, "*", SearchOption.AllDirectories))
        {
            var relative = Path.GetRelativePath(sourceDirectory, sourceFile);
            var targetFile = Path.Combine(targetDirectory, relative);
            Directory.CreateDirectory(Path.GetDirectoryName(targetFile)!);
            PrepareFileTarget(targetFile, bakPaths);
            File.Copy(sourceFile, targetFile, overwrite: true);
        }
    }

    private void PrepareFileTarget(string targetFile, List<string> bakPaths)
    {
        if (Directory.Exists(targetFile))
        {
            DeleteOrBakDirectory(targetFile, bakPaths);
            return;
        }

        if (!File.Exists(targetFile))
        {
            return;
        }

        try
        {
            if (_simulateDeleteFailure(targetFile))
            {
                throw new IOException("Simulated locked file.");
            }

            File.Delete(targetFile);
        }
        catch (IOException)
        {
            bakPaths.Add(MoveFileToBak(targetFile));
        }
        catch (UnauthorizedAccessException)
        {
            bakPaths.Add(MoveFileToBak(targetFile));
        }
    }

    private static void DeleteOrBakDirectory(string targetDirectory, List<string> bakPaths)
    {
        try
        {
            Directory.Delete(targetDirectory, recursive: true);
        }
        catch (IOException)
        {
            bakPaths.Add(MoveDirectoryToBak(targetDirectory));
        }
        catch (UnauthorizedAccessException)
        {
            bakPaths.Add(MoveDirectoryToBak(targetDirectory));
        }
    }

    private static string MoveFileToBak(string path)
    {
        var bakPath = NextBakPath(path);
        File.Move(path, bakPath);
        return bakPath;
    }

    private static string MoveDirectoryToBak(string path)
    {
        var bakPath = NextBakPath(path);
        Directory.Move(path, bakPath);
        return bakPath;
    }

    private static string NextBakPath(string path)
    {
        var candidate = $"{path}.bak";
        var index = 1;
        while (File.Exists(candidate) || Directory.Exists(candidate))
        {
            candidate = $"{path}.bak.{index++}";
        }

        return candidate;
    }

    private static void ValidateOptions(UpdateInstallOptions options)
    {
        if (string.IsNullOrWhiteSpace(options.SourceDirectory) || !Directory.Exists(options.SourceDirectory))
        {
            throw new DirectoryNotFoundException(options.SourceDirectory);
        }

        if (string.IsNullOrWhiteSpace(options.AppDirectory))
        {
            throw new ArgumentException("App directory is required.", nameof(options));
        }

        if (string.IsNullOrWhiteSpace(options.MainExecutablePath))
        {
            throw new ArgumentException("Main executable path is required.", nameof(options));
        }
    }
}
