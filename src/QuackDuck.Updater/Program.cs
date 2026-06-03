namespace QuackDuck.Updater;

internal static class Program
{
    private static async Task<int> Main(string[] args)
    {
        try
        {
            var options = ParseArgs(args);
            await new UpdateInstaller().InstallAsync(options);
            return 0;
        }
        catch
        {
            return 1;
        }
    }

    private static UpdateInstallOptions ParseArgs(string[] args)
    {
        var values = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        for (var i = 0; i < args.Length; i++)
        {
            var arg = args[i];
            if (!arg.StartsWith("--", StringComparison.Ordinal))
            {
                continue;
            }

            var key = arg;
            var value = string.Empty;
            var equalsIndex = arg.IndexOf('=');
            if (equalsIndex >= 0)
            {
                key = arg[..equalsIndex];
                value = arg[(equalsIndex + 1)..];
            }
            else if (i + 1 < args.Length)
            {
                value = args[++i];
            }

            values[key] = value;
        }

        return new UpdateInstallOptions
        {
            ParentProcessId = values.TryGetValue("--parent-pid", out var pid) && int.TryParse(pid, out var parsedPid)
                ? parsedPid
                : null,
            SourceDirectory = values.TryGetValue("--source", out var source) ? source : string.Empty,
            AppDirectory = values.TryGetValue("--app-dir", out var appDir) ? appDir : string.Empty,
            MainExecutablePath = values.TryGetValue("--main-exe", out var mainExe) ? mainExe : string.Empty
        };
    }
}
