using QuackDuck.Application.Rendering;

namespace QuackDuck.Tests;

public sealed class PetVisibilityStateTests
{
    [Fact]
    public void ToggleManualHide_PausesPetAndUsesHiddenTrayIcon()
    {
        var state = PetVisibilityState.Visible.ToggleManualHide();

        Assert.True(state.ManuallyHidden);
        Assert.False(state.ShouldTick);
        Assert.True(state.UseHiddenTrayIcon);
    }

    [Fact]
    public void ToggleManualHide_WhenAlreadyHidden_ShowsAndResumesPet()
    {
        var state = PetVisibilityState.Visible.ToggleManualHide().ToggleManualHide();

        Assert.False(state.ManuallyHidden);
        Assert.True(state.ShouldTick);
        Assert.False(state.UseHiddenTrayIcon);
    }

    [Fact]
    public void FullscreenPause_UsesHiddenIconButDoesNotOverrideManualHidden()
    {
        var state = PetVisibilityState.Visible.ToggleManualHide().SetFullscreenPaused(false);

        Assert.True(state.ManuallyHidden);
        Assert.False(state.ShouldTick);
        Assert.True(state.UseHiddenTrayIcon);
    }
}
