namespace QuackDuck.Application.Rendering;

public static class DisplayScalePolicy
{
    private const double ReferenceWidth = 1920.0;
    private const double ReferenceHeight = 1080.0;

    public static double Calculate(double workAreaWidth, double workAreaHeight)
    {
        if (!double.IsFinite(workAreaWidth) || !double.IsFinite(workAreaHeight) ||
            workAreaWidth <= 0 || workAreaHeight <= 0)
        {
            return 1.0;
        }

        var raw = Math.Min(workAreaWidth / ReferenceWidth, workAreaHeight / ReferenceHeight);
        var stepped = Math.Floor(Math.Max(1.0, raw) * 4.0) / 4.0;
        return Math.Clamp(stepped, 1.0, 2.5);
    }
}
