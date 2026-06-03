using System.Collections.ObjectModel;
using System.IO;
using System.Linq;
using System.Windows;
using System.Windows.Media;
using System.Windows.Media.Imaging;
using QuackDuck.Domain.Skins;

namespace QuackDuck.Infrastructure.Skins;

/// <summary>
/// Converts SkinDefinition spritesheets into WPF bitmaps and caches them per pet size.
/// </summary>
public sealed class SkinBitmapCache
{
    private readonly object _sync = new();
    private readonly Dictionary<(string Key, double Scale), CachedSkin> _cache = new();

    public CachedSkin GetOrAdd(SkinDefinition skin, double scale = 1.0)
    {
        var key = skin.SourcePath ?? skin.Id;
        var normalizedScale = NormalizeScale(scale);
        var signature = ComputeSignature(skin, normalizedScale);
        lock (_sync)
        {
            if (_cache.TryGetValue((key, normalizedScale), out var cached) &&
                string.Equals(cached.SpriteSheetPath, skin.SpriteSheetPath, StringComparison.OrdinalIgnoreCase) &&
                cached.Signature == signature)
            {
                return cached;
            }

            var rebuilt = BuildSkinCache(skin, normalizedScale, signature);
            _cache[(key, normalizedScale)] = rebuilt;
            return rebuilt;
        }
    }

    public IReadOnlyList<BitmapSource> GetFrames(
        SkinDefinition skin,
        string animation,
        params string[] fallbacks)
    {
        return GetFramesInternal(skin, animation, 1.0, fallbacks);
    }

    public IReadOnlyList<BitmapSource> GetFrames(
        SkinDefinition skin,
        string animation,
        double scale,
        params string[] fallbacks)
    {
        return GetFramesInternal(skin, animation, scale, fallbacks);
    }

    private IReadOnlyList<BitmapSource> GetFramesInternal(
        SkinDefinition skin,
        string animation,
        double scale,
        params string[] fallbacks)
    {
        var cached = GetOrAdd(skin, scale);
        if (cached.Animations.TryGetValue(animation, out var frames) && frames.Count > 0)
        {
            return frames;
        }

        foreach (var candidate in fallbacks)
        {
            if (cached.Animations.TryGetValue(candidate, out var altFrames) && altFrames.Count > 0)
            {
                return altFrames;
            }
        }

        if (cached.Animations.TryGetValue("idle", out var idle) && idle.Count > 0)
        {
            return idle;
        }

        return Array.Empty<BitmapSource>();
    }

    private static CachedSkin BuildSkinCache(SkinDefinition skin, double scale, int signature)
    {
        var sheet = LoadSpriteSheet(skin.SpriteSheetPath);
        var animations = new Dictionary<string, IReadOnlyList<BitmapSource>>(StringComparer.OrdinalIgnoreCase);

        foreach (var pair in skin.Animations)
        {
            var frames = new List<BitmapSource>();
            if (sheet != null)
            {
                var scaleTransform = scale.Equals(1.0)
                    ? null
                    : new ScaleTransform(scale, scale);
                scaleTransform?.Freeze();

                foreach (var coord in pair.Value.Frames)
                {
                    var rect = new Int32Rect(
                        coord.Column * skin.FrameWidth,
                        coord.Row * skin.FrameHeight,
                        skin.FrameWidth,
                        skin.FrameHeight);

                    if (rect.X < 0 || rect.Y < 0 ||
                        rect.X + rect.Width > sheet.PixelWidth ||
                        rect.Y + rect.Height > sheet.PixelHeight)
                    {
                        continue;
                    }

                    var cropped = new CroppedBitmap(sheet, rect);
                    cropped.Freeze();

                    BitmapSource frame = cropped;
                    if (scaleTransform != null)
                    {
                        var scaled = new TransformedBitmap(cropped, scaleTransform);
                        scaled.Freeze();
                        frame = scaled;
                    }

                    frames.Add(frame);
                }
            }

            animations[pair.Key] = new ReadOnlyCollection<BitmapSource>(frames);
        }

        return new CachedSkin(
            skin,
            new ReadOnlyDictionary<string, IReadOnlyList<BitmapSource>>(animations),
            sheet,
            signature);
    }

    private static int ComputeSignature(SkinDefinition skin, double scale)
    {
        unchecked
        {
            var hash = HashCode.Combine(
                skin.SpriteSheetPath?.ToLowerInvariant(),
                skin.FrameWidth,
                skin.FrameHeight,
                skin.Animations.Count,
                scale);

            foreach (var pair in skin.Animations.OrderBy(p => p.Key, StringComparer.OrdinalIgnoreCase))
            {
                hash = HashCode.Combine(hash, pair.Key.ToLowerInvariant(), pair.Value.Frames.Count);
            }

            return hash;
        }
    }

    private static double NormalizeScale(double scale)
    {
        if (!double.IsFinite(scale) || scale <= 0)
        {
            return 1.0;
        }

        return Math.Round(Math.Clamp(scale, 0.25, 10.0), 2);
    }

    private static BitmapImage? LoadSpriteSheet(string spriteSheetPath)
    {
        if (string.IsNullOrWhiteSpace(spriteSheetPath) || !File.Exists(spriteSheetPath))
        {
            return null;
        }

        try
        {
            var image = new BitmapImage();
            image.BeginInit();
            image.CacheOption = BitmapCacheOption.OnLoad;
            image.CreateOptions = BitmapCreateOptions.IgnoreImageCache;
            image.UriSource = new Uri(Path.GetFullPath(spriteSheetPath));
            image.EndInit();
            image.Freeze();
            return image;
        }
        catch
        {
            return null;
        }
    }
}

public sealed record CachedSkin(
    SkinDefinition Skin,
    IReadOnlyDictionary<string, IReadOnlyList<BitmapSource>> Animations,
    BitmapSource? SpriteSheet,
    int Signature)
{
    public string SpriteSheetPath => Skin.SpriteSheetPath;
    public int Version => Skin.Animations.Count;
}
