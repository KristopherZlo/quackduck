using QuackDuck.Infrastructure.Updates;

namespace QuackDuck.Tests;

public sealed class BakCleanupServiceTests
{
    [Fact]
    public void Cleanup_DeletesOnlyRootLevelBakFilesAndFolders()
    {
        var root = CreateTempDirectory();
        var rootBakFile = Path.Combine(root, "old.exe.bak");
        var rootBakFolder = Path.Combine(root, "old_assets.bak");
        var nested = Path.Combine(root, "nested");
        var nestedBakFile = Path.Combine(nested, "keep.dll.bak");
        var normalFile = Path.Combine(root, "quackduck.exe");

        Directory.CreateDirectory(rootBakFolder);
        Directory.CreateDirectory(nested);
        File.WriteAllText(rootBakFile, "old");
        File.WriteAllText(nestedBakFile, "nested");
        File.WriteAllText(normalFile, "current");

        var deleted = new BakCleanupService().Cleanup(root);

        Assert.Contains(rootBakFile, deleted);
        Assert.Contains(rootBakFolder, deleted);
        Assert.False(File.Exists(rootBakFile));
        Assert.False(Directory.Exists(rootBakFolder));
        Assert.True(File.Exists(nestedBakFile));
        Assert.True(File.Exists(normalFile));
    }

    private static string CreateTempDirectory()
    {
        var path = Path.Combine(Path.GetTempPath(), "quackduck-tests", Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(path);
        return path;
    }
}
