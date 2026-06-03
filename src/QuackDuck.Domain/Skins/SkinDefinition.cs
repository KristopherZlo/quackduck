using System.Collections.ObjectModel;

namespace QuackDuck.Domain.Skins;

/// <summary>
/// Describes a skin spritesheet and its animations independent of rendering technology.
/// </summary>
public class SkinDefinition
{
    public string Id { get; }
    public string SpriteSheetPath { get; }
    public int FrameWidth { get; }
    public int FrameHeight { get; }
    public IReadOnlyDictionary<string, AnimationSequence> Animations { get; }
    public IReadOnlyList<string> SoundFiles { get; }
    public bool IsDefault { get; }
    public string? SourcePath { get; }

    public SkinDefinition(
        string id,
        string spriteSheetPath,
        int frameWidth,
        int frameHeight,
        IDictionary<string, AnimationSequence> animations,
        IEnumerable<string>? soundFiles = null,
        bool isDefault = false,
        string? sourcePath = null)
    {
        if (frameWidth <= 0) throw new ArgumentOutOfRangeException(nameof(frameWidth));
        if (frameHeight <= 0) throw new ArgumentOutOfRangeException(nameof(frameHeight));

        Id = string.IsNullOrWhiteSpace(id)
            ? throw new ArgumentException("Skin id is required.", nameof(id))
            : id;
        SpriteSheetPath = string.IsNullOrWhiteSpace(spriteSheetPath)
            ? throw new ArgumentException("Spritesheet path is required.", nameof(spriteSheetPath))
            : spriteSheetPath;
        FrameWidth = frameWidth;
        FrameHeight = frameHeight;
        Animations = new ReadOnlyDictionary<string, AnimationSequence>(
            animations ?? new Dictionary<string, AnimationSequence>());
        SoundFiles = new ReadOnlyCollection<string>((soundFiles ?? Array.Empty<string>()).ToArray());
        IsDefault = isDefault;
        SourcePath = sourcePath;
    }
}
