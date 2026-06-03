using QuackDuck.Application.Rendering;

namespace QuackDuck.Tests;

public sealed class ScreenGeometryPolicyTests
{
    [Fact]
    public void Calculate_UsesFullScreenViewport_WhenTaskbarIsAtTop()
    {
        var geometry = ScreenGeometryPolicy.Calculate(
            primaryWidth: 1920,
            primaryHeight: 1080,
            workAreaLeft: 0,
            workAreaTop: 40,
            workAreaWidth: 1920,
            workAreaHeight: 1040);

        Assert.Equal(1920, geometry.ViewportWidth);
        Assert.Equal(1080, geometry.ViewportHeight);
        Assert.Equal(0, geometry.DefaultGroundOffset);
    }

    [Fact]
    public void Calculate_SuggestsDefaultGroundOffsetOnlyForBottomTaskbar()
    {
        var geometry = ScreenGeometryPolicy.Calculate(
            primaryWidth: 1920,
            primaryHeight: 1080,
            workAreaLeft: 0,
            workAreaTop: 0,
            workAreaWidth: 1920,
            workAreaHeight: 1040);

        Assert.Equal(40, geometry.DefaultGroundOffset);
    }
}
