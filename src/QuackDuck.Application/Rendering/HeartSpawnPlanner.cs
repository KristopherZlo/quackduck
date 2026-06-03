using QuackDuck.Domain.Pets;

namespace QuackDuck.Application.Rendering;

public readonly record struct HeartSpawn(double Left, double Top, double Size);

public sealed class HeartSpawnPlanner
{
    private readonly double _minSize;
    private readonly double _maxSize;
    private readonly double _minOffsetX;
    private readonly double _maxOffsetX;
    private readonly double _minOffsetY;
    private readonly double _maxOffsetY;
    private readonly Random _random;

    public HeartSpawnPlanner(
        double minSize = 14,
        double maxSize = 34,
        double minOffsetX = -24,
        double maxOffsetX = 24,
        double minOffsetY = 8,
        double maxOffsetY = 40,
        Random? random = null)
    {
        _minSize = Math.Min(minSize, maxSize);
        _maxSize = Math.Max(minSize, maxSize);
        _minOffsetX = Math.Min(minOffsetX, maxOffsetX);
        _maxOffsetX = Math.Max(minOffsetX, maxOffsetX);
        _minOffsetY = Math.Min(minOffsetY, maxOffsetY);
        _maxOffsetY = Math.Max(minOffsetY, maxOffsetY);
        _random = random ?? new Random();
    }

    public HeartSpawn Create(PetPose pose)
    {
        var size = Next(_minSize, _maxSize);
        var offsetX = Next(_minOffsetX, _maxOffsetX);
        var offsetY = Next(_minOffsetY, _maxOffsetY);
        var centerX = pose.X + pose.Width / 2.0 + offsetX;
        var left = centerX - size / 2.0;
        var top = pose.Y - offsetY;
        return new HeartSpawn(left, top, size);
    }

    private double Next(double min, double max) => min + _random.NextDouble() * (max - min);
}
