using QuackDuck.Application.Rendering;

namespace QuackDuck.Tests;

public sealed class DisplayScalePolicyTests
{
    [Theory]
    [InlineData(1920, 1080, 1.0)]
    [InlineData(2560, 1440, 1.25)]
    [InlineData(3840, 2160, 2.0)]
    public void Calculate_ReturnsResolutionRelativeScale(double width, double height, double expected)
    {
        Assert.Equal(expected, DisplayScalePolicy.Calculate(width, height));
    }
}
