using QuackDuck.Application.Rendering;
using QuackDuck.Domain.Pets;

namespace QuackDuck.Tests;

public sealed class HeartSpawnPlannerTests
{
    [Fact]
    public void Create_UsesRandomSizeAndOffsetsAbovePet()
    {
        var pose = new PetPose(300, 400, true, 96, 96);
        var planner = new HeartSpawnPlanner(
            minSize: 14,
            maxSize: 34,
            minOffsetX: -24,
            maxOffsetX: 24,
            minOffsetY: 8,
            maxOffsetY: 40,
            random: new Random(123));

        var first = planner.Create(pose);
        var second = planner.Create(pose);

        Assert.InRange(first.Size, 14, 34);
        Assert.InRange(first.Left, pose.X + pose.Width / 2 - 24 - first.Size / 2, pose.X + pose.Width / 2 + 24 - first.Size / 2);
        Assert.InRange(first.Top, pose.Y - 40, pose.Y - 8);
        Assert.NotEqual(first, second);
    }
}
