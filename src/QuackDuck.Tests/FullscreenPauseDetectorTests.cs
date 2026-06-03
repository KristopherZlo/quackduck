using QuackDuck.Infrastructure.Windows;

namespace QuackDuck.Tests;

public sealed class FullscreenPauseDetectorTests
{
    [Fact]
    public void ShouldPause_WhenForegroundWindowIsFullscreenAndNotOwnProcess()
    {
        var detector = new FullscreenPauseDetector(ownProcessId: 42);
        var snapshot = new ForegroundWindowSnapshot(
            Handle: new IntPtr(100),
            ProcessId: 1000,
            ProcessName: "game",
            ClassName: "UnityWndClass",
            IsFullscreen: true);

        Assert.True(detector.ShouldPause(snapshot));
    }

    [Theory]
    [InlineData(42, "quackduck", "Window", true)]
    [InlineData(1000, "explorer", "CabinetWClass", true)]
    [InlineData(1000, "explorer", "Progman", true)]
    [InlineData(1000, "game", "UnityWndClass", false)]
    public void ShouldPause_IgnoresOwnShellDesktopAndNonFullscreenWindows(
        int processId,
        string processName,
        string className,
        bool fullscreen)
    {
        var detector = new FullscreenPauseDetector(ownProcessId: 42);
        var snapshot = new ForegroundWindowSnapshot(
            Handle: new IntPtr(100),
            ProcessId: processId,
            ProcessName: processName,
            ClassName: className,
            IsFullscreen: fullscreen);

        Assert.False(detector.ShouldPause(snapshot));
    }
}
