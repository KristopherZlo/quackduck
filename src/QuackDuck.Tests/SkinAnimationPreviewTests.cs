using System.Windows.Media;
using System.Windows.Media.Imaging;
using QuackDuck.Domain.Skins;
using QuackDuck.Infrastructure.Skins;

namespace QuackDuck.Tests;

public sealed class SkinAnimationPreviewTests
{
    [Fact]
    public void Build_ReturnsOneAnimatedPreviewPerSkin_UsingAnimationFramesNotWholeSheet()
    {
        var root = CreateTempDirectory();
        var skinA = CreatePreviewSkin(root, "skin-a");
        var skinB = CreatePreviewSkin(root, "skin-b");

        var previews = new SkinAnimationPreviewBuilder().Build(
            new[] { skinA, skinB },
            selectedSkinPath: skinB.SourcePath);

        Assert.Equal(2, previews.Count);
        Assert.All(previews, preview =>
        {
            Assert.True(preview.Frames.Count >= 4);
            Assert.All(preview.Frames, frame => Assert.StartsWith("data:image/png;base64,", frame));
            Assert.DoesNotContain("spritesheet", string.Join("|", preview.Frames), StringComparison.OrdinalIgnoreCase);
        });
        Assert.False(previews[0].IsSelected);
        Assert.True(previews[1].IsSelected);
    }

    [Fact]
    public void Build_EmitsNativeFrameSizeSoBrowserCanScalePixelated()
    {
        var root = CreateTempDirectory();
        var skin = CreatePreviewSkin(root, "skin-a");

        var frame = new SkinAnimationPreviewBuilder().Build(new[] { skin }, selectedSkinPath: null)[0].Frames[0];
        var base64 = frame["data:image/png;base64,".Length..];
        using var stream = new MemoryStream(Convert.FromBase64String(base64));
        var decoded = BitmapDecoder.Create(stream, BitmapCreateOptions.None, BitmapCacheOption.OnLoad).Frames[0];

        Assert.Equal(16, decoded.PixelWidth);
        Assert.Equal(16, decoded.PixelHeight);
    }

    private static SkinDefinition CreatePreviewSkin(string root, string id)
    {
        var skinRoot = Path.Combine(root, id);
        Directory.CreateDirectory(skinRoot);
        var sheetPath = Path.Combine(skinRoot, "spritesheet.png");
        WriteSpriteSheet(sheetPath);

        return new SkinDefinition(
            id,
            sheetPath,
            16,
            16,
            new Dictionary<string, AnimationSequence>
            {
                ["idle"] = new("idle", new[] { new FrameCoordinate(0, 0), new FrameCoordinate(0, 1) }),
                ["walk"] = new("walk", new[] { new FrameCoordinate(1, 0), new FrameCoordinate(1, 1) })
            },
            isDefault: false,
            sourcePath: skinRoot);
    }

    private static void WriteSpriteSheet(string path)
    {
        const int width = 32;
        const int height = 32;
        var pixels = new byte[width * height * 4];
        for (var y = 0; y < height; y++)
        {
            for (var x = 0; x < width; x++)
            {
                var index = (y * width + x) * 4;
                pixels[index + 0] = (byte)(x < 16 ? 40 : 220);
                pixels[index + 1] = (byte)(y < 16 ? 80 : 200);
                pixels[index + 2] = (byte)(x + y);
                pixels[index + 3] = 255;
            }
        }

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
