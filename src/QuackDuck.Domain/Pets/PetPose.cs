namespace QuackDuck.Domain.Pets;

/// <summary>
/// Simple snapshot of the pet's position and facing for rendering.
/// </summary>
public readonly record struct PetPose(double X, double Y, bool FacingRight, double Width, double Height)
{
    public static PetPose Empty => new(0, 0, true, 0, 0);
}
