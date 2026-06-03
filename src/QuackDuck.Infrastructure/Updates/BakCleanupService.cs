using System.IO;

namespace QuackDuck.Infrastructure.Updates;

public sealed class BakCleanupService
{
    public IReadOnlyList<string> Cleanup(string appDirectory)
    {
        if (string.IsNullOrWhiteSpace(appDirectory) || !Directory.Exists(appDirectory))
        {
            return Array.Empty<string>();
        }

        var deleted = new List<string>();
        foreach (var path in Directory.EnumerateFileSystemEntries(appDirectory, "*.bak", SearchOption.TopDirectoryOnly))
        {
            try
            {
                if (Directory.Exists(path))
                {
                    Directory.Delete(path, recursive: true);
                }
                else if (File.Exists(path))
                {
                    File.Delete(path);
                }

                deleted.Add(path);
            }
            catch
            {
                // Locked leftovers can be retried on the next startup.
            }
        }

        return deleted;
    }
}
