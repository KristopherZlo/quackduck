using QuackDuck.Updater;

namespace QuackDuck.Tests;

public sealed class UpdateInstallerTests
{
    [Fact]
    public async Task InstallAsync_CopiesReleaseFiles_AndRenamesLockedTargetsToBak()
    {
        var root = Path.Combine(Path.GetTempPath(), "quackduck-tests", Guid.NewGuid().ToString("N"));
        var source = Path.Combine(root, "source");
        var app = Path.Combine(root, "app");
        Directory.CreateDirectory(source);
        Directory.CreateDirectory(app);
        File.WriteAllText(Path.Combine(source, "quackduck.exe"), "new exe");
        File.WriteAllText(Path.Combine(source, "locked.dll"), "new dll");
        File.WriteAllText(Path.Combine(app, "quackduck.exe"), "old exe");
        File.WriteAllText(Path.Combine(app, "locked.dll"), "old dll");

        var installer = new UpdateInstaller(path => Path.GetFileName(path).Equals("locked.dll", StringComparison.OrdinalIgnoreCase));

        var result = await installer.InstallAsync(new UpdateInstallOptions
        {
            SourceDirectory = source,
            AppDirectory = app,
            MainExecutablePath = Path.Combine(app, "quackduck.exe"),
            RestartAfterInstall = false
        });

        Assert.True(result.Succeeded);
        Assert.Equal("new exe", File.ReadAllText(Path.Combine(app, "quackduck.exe")));
        Assert.Equal("new dll", File.ReadAllText(Path.Combine(app, "locked.dll")));
        Assert.Contains(Directory.EnumerateFiles(app, "locked.dll*.bak"), path => File.ReadAllText(path) == "old dll");
    }
}
