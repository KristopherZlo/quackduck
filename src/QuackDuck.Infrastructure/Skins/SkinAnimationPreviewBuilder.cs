using System.IO;
using System.Windows.Media.Imaging;
using QuackDuck.Domain.Skins;

namespace QuackDuck.Infrastructure.Skins;

public sealed record SkinAnimationPreview(
    string Id,
    string DisplayName,
    string SourcePath,
    bool IsSelected,
    IReadOnlyList<string> Frames);

public sealed class SkinAnimationPreviewBuilder
{
    private static readonly string[] PreferredAnimations =
    {
        "idle",
        "walk",
        "walking",
        "running",
        "run",
        "jump",
        "fall",
        "land",
        "sleep",
        "attack",
        "crouch",
        "wallgrab"
    };

    private readonly SkinBitmapCache _cache = new();

    public IReadOnlyList<SkinAnimationPreview> Build(
        IEnumerable<SkinDefinition> skins,
        string? selectedSkinPath,
        int maxSkins = 24,
        int maxFramesPerSkin = 32)
    {
        var selected = NormalizePath(selectedSkinPath);
        var previews = new List<SkinAnimationPreview>();
        var seen = new HashSet<string>(StringComparer.OrdinalIgnoreCase);

        foreach (var skin in skins)
        {
            if (previews.Count >= maxSkins)
            {
                break;
            }

            var sourcePath = skin.SourcePath ?? skin.SpriteSheetPath;
            var key = NormalizePath(sourcePath) ?? skin.Id;
            if (!seen.Add(key))
            {
                continue;
            }

            var frames = BuildFrames(skin, maxFramesPerSkin);
            if (frames.Count == 0)
            {
                continue;
            }

            previews.Add(new SkinAnimationPreview(
                skin.Id,
                skin.IsDefault ? "Default" : Humanize(skin.Id),
                sourcePath,
                selected != null && string.Equals(selected, NormalizePath(sourcePath), StringComparison.OrdinalIgnoreCase),
                frames));
        }

        return previews;
    }

    private IReadOnlyList<string> BuildFrames(SkinDefinition skin, int maxFramesPerSkin)
    {
        var frames = new List<string>();
        foreach (var animationName in OrderedAnimationNames(skin))
        {
            foreach (var frame in _cache.GetFrames(skin, animationName, scale: 1.0))
            {
                frames.Add(EncodePng(frame));
                if (frames.Count >= maxFramesPerSkin)
                {
                    return frames;
                }
            }
        }

        return frames;
    }

    private static IEnumerable<string> OrderedAnimationNames(SkinDefinition skin)
    {
        var emitted = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        foreach (var preferred in PreferredAnimations)
        {
            if (skin.Animations.ContainsKey(preferred) && emitted.Add(preferred))
            {
                yield return preferred;
            }
        }

        foreach (var animationName in skin.Animations.Keys.OrderBy(name => name, StringComparer.OrdinalIgnoreCase))
        {
            if (emitted.Add(animationName))
            {
                yield return animationName;
            }
        }
    }

    private static string EncodePng(BitmapSource frame)
    {
        var encoder = new PngBitmapEncoder();
        encoder.Frames.Add(BitmapFrame.Create(frame));
        using var stream = new MemoryStream();
        encoder.Save(stream);
        return $"data:image/png;base64,{Convert.ToBase64String(stream.ToArray())}";
    }

    private static string Humanize(string value)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            return "Skin";
        }

        return value.Replace('_', ' ').Replace('-', ' ');
    }

    private static string? NormalizePath(string? path)
    {
        if (string.IsNullOrWhiteSpace(path))
        {
            return null;
        }

        try
        {
            return Path.GetFullPath(path).Trim();
        }
        catch
        {
            return path.Trim();
        }
    }
}
