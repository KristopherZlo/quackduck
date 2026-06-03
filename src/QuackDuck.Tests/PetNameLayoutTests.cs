using QuackDuck.Application.Rendering;
using QuackDuck.Domain.Pets;

namespace QuackDuck.Tests;

public sealed class PetNameLayoutTests
{
    [Fact]
    public void Calculate_ExpandsWindowAbovePetWithoutMovingPetScreenPose()
    {
        var pose = new PetPose(300, 400, true, 96, 96);

        var layout = PetNameLayout.Calculate(
            pose,
            showName: true,
            name: "Long Quack Name",
            labelWidth: 160,
            labelHeight: 24,
            nameOffsetY: 60);

        Assert.True(layout.RootWidth >= 160);
        Assert.Equal(pose.X, layout.WindowLeft + layout.PetLeft, precision: 3);
        Assert.Equal(pose.Y, layout.WindowTop + layout.PetTop, precision: 3);
        Assert.Equal(pose.Y - 60, layout.WindowTop + layout.NameTop, precision: 3);
        Assert.True(layout.NameVisible);
    }
}
