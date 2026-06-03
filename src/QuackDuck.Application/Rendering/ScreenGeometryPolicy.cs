namespace QuackDuck.Application.Rendering;

public readonly record struct ScreenGeometry(
    double ViewportWidth,
    double ViewportHeight,
    int DefaultGroundOffset);

public static class ScreenGeometryPolicy
{
    public static ScreenGeometry Calculate(
        double primaryWidth,
        double primaryHeight,
        double workAreaLeft,
        double workAreaTop,
        double workAreaWidth,
        double workAreaHeight)
    {
        var viewportWidth = Math.Max(1, primaryWidth);
        var viewportHeight = Math.Max(1, primaryHeight);
        var workAreaBottom = workAreaTop + Math.Max(0, workAreaHeight);
        var bottomInset = Math.Max(0, viewportHeight - workAreaBottom);

        return new ScreenGeometry(
            viewportWidth,
            viewportHeight,
            (int)Math.Round(bottomInset));
    }
}
