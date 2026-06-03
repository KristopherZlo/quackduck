using System.Windows.Media;
using System.Windows.Media.Imaging;
using QuackDuck.Infrastructure.Skins;

namespace QuackDuck.Tests;

public sealed class SkinFileServiceDiscoveryTests
{
    [Fact]
    public async Task DiscoverAsync_IncludesRootSkinFolderAndChildSkinFolders()
    {
        var root = CreateTempDirectory();
        var paths = new FakePathProvider(root);
        Directory.CreateDirectory(paths.AssetsRoot);
        Directory.CreateDirectory(paths.TempRoot);
        var skinsRoot = Path.Combine(root, "skins");
        var childSkin = Path.Combine(skinsRoot, "child-skin");
        CreateSkinFolder(skinsRoot, "root-skin");
        CreateSkinFolder(childSkin, "child-skin");

        var service = new SkinFileService(paths);

        var skins = await service.DiscoverAsync(skinsRoot);

        Assert.Contains(skins, skin => string.Equals(skin.SourcePath, skinsRoot, StringComparison.OrdinalIgnoreCase));
        Assert.Contains(skins, skin => string.Equals(skin.SourcePath, childSkin, StringComparison.OrdinalIgnoreCase));
    }

    [Fact]
    public async Task LoadSkinAsync_LoadsFolderSkinWhenSelectedSkinIsDirectory()
    {
        var root = CreateTempDirectory();
        var paths = new FakePathProvider(root);
        Directory.CreateDirectory(paths.AssetsRoot);
        Directory.CreateDirectory(paths.TempRoot);
        var skinFolder = Path.Combine(root, "selected-skin");
        CreateSkinFolder(skinFolder, "selected-skin");
        var service = new SkinFileService(paths);

        var skin = await service.LoadSkinAsync(skinFolder);

        Assert.Equal("selected-skin", skin.Id);
        Assert.Equal(skinFolder, skin.SourcePath);
    }

    private static void CreateSkinFolder(string folder, string id)
    {
        Directory.CreateDirectory(folder);
        WriteSpriteSheet(Path.Combine(folder, "spritesheet.png"));
        File.WriteAllText(
            Path.Combine(folder, "config.json"),
            $$"""
              {
                "frame_width": 16,
                "frame_height": 16,
                "spritesheet": "spritesheet.png",
                "animations": {
                  "idle": ["0:0", "0:1"],
                  "walk": ["1:0", "1:1"]
                },
                "id": "{{id}}"
              }
              """);
    }

    private static void WriteSpriteSheet(string path)
    {
        const int width = 32;
        const int height = 32;
        var pixels = Enumerable.Repeat((byte)255, width * height * 4).ToArray();
        var bitmap = BitmapSource.Create(width, height, 96, 96, PixelFormats.Bgra32, null, pixels, width * 4);
        var encoder = new PngBitmapEncoder();
        encoder.Frames.Add(BitmapFrame.Create(bitmap));
        using var stream = File.Create(path);
        encoder.Save(stream);
    }

    private static string CreateTempDirectory()
    {
        var path = Path.Combine(Path.GetTempPath(), "quackduck-tests", Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(path);
        return path;
    }
}
