using QuackDuck.Domain.Pets;

namespace QuackDuck.Application.Rendering;

/// <summary>
/// UI-facing data describing which frame to show and where to position it.
/// </summary>
public readonly record struct PetFrameUpdate(
    string SkinId,
    string Animation,
    int FrameIndex,
    PetPose Pose,
    bool FlipX);
