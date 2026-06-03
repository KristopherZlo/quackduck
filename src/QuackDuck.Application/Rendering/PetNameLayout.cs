using QuackDuck.Domain.Pets;

namespace QuackDuck.Application.Rendering;

public readonly record struct PetNameLayout(
    double WindowLeft,
    double WindowTop,
    double RootWidth,
    double RootHeight,
    double PetLeft,
    double PetTop,
    double NameLeft,
    double NameTop,
    bool NameVisible)
{
    public static PetNameLayout Calculate(
        PetPose pose,
        bool showName,
        string? name,
        double labelWidth,
        double labelHeight,
        int nameOffsetY)
    {
        var nameVisible = showName && !string.IsNullOrWhiteSpace(name) && labelWidth > 0 && labelHeight > 0;
        var topInset = nameVisible ? Math.Max(0, nameOffsetY) : 0;
        var rootWidth = nameVisible ? Math.Max(pose.Width, labelWidth) : pose.Width;
        var rootHeight = pose.Height + topInset;
        var petLeft = Math.Max(0, (rootWidth - pose.Width) / 2.0);
        var petTop = topInset;
        var nameLeft = nameVisible ? Math.Max(0, (rootWidth - labelWidth) / 2.0) : 0;
        var nameTop = nameVisible ? Math.Max(0, topInset - Math.Max(0, nameOffsetY)) : 0;

        return new PetNameLayout(
            WindowLeft: pose.X - petLeft,
            WindowTop: pose.Y - petTop,
            RootWidth: rootWidth,
            RootHeight: rootHeight,
            PetLeft: petLeft,
            PetTop: petTop,
            NameLeft: nameLeft,
            NameTop: nameTop,
            NameVisible: nameVisible);
    }
}
