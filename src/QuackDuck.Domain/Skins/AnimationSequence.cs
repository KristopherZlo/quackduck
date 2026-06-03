using System.Collections.ObjectModel;

namespace QuackDuck.Domain.Skins;

public class AnimationSequence
{
    public string Name { get; }
    public IReadOnlyList<FrameCoordinate> Frames { get; }

    public AnimationSequence(string name, IEnumerable<FrameCoordinate> frames)
    {
        Name = string.IsNullOrWhiteSpace(name)
            ? throw new ArgumentException("Animation name is required.", nameof(name))
            : name;

        Frames = new ReadOnlyCollection<FrameCoordinate>((frames ?? Array.Empty<FrameCoordinate>()).ToArray());
    }
}
