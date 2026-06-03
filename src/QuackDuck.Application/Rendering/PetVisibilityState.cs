namespace QuackDuck.Application.Rendering;

public readonly record struct PetVisibilityState(bool ManuallyHidden, bool FullscreenPaused)
{
    public static PetVisibilityState Visible => new(false, false);

    public bool ShouldTick => !ManuallyHidden && !FullscreenPaused;
    public bool UseHiddenTrayIcon => ManuallyHidden || FullscreenPaused;

    public PetVisibilityState ToggleManualHide() =>
        ManuallyHidden ? new PetVisibilityState(false, false) : new PetVisibilityState(true, false);

    public PetVisibilityState SetManualHidden(bool hidden) =>
        hidden ? new PetVisibilityState(true, false) : new PetVisibilityState(false, false);

    public PetVisibilityState SetFullscreenPaused(bool paused) =>
        ManuallyHidden ? this : this with { FullscreenPaused = paused };
}
