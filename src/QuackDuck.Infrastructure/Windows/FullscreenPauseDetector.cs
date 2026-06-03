namespace QuackDuck.Infrastructure.Windows;

public readonly record struct ForegroundWindowSnapshot(
    IntPtr Handle,
    int ProcessId,
    string ProcessName,
    string ClassName,
    bool IsFullscreen);

public sealed class FullscreenPauseDetector
{
    private readonly int _ownProcessId;

    public FullscreenPauseDetector(int ownProcessId)
    {
        _ownProcessId = ownProcessId;
    }

    public bool ShouldPause(ForegroundWindowSnapshot? snapshot)
    {
        if (snapshot == null || !snapshot.Value.IsFullscreen)
        {
            return false;
        }

        var window = snapshot.Value;
        if (window.ProcessId == _ownProcessId)
        {
            return false;
        }

        if (string.Equals(window.ProcessName, "explorer", StringComparison.OrdinalIgnoreCase))
        {
            return false;
        }

        if (window.ClassName is "Progman" or "WorkerW" or "Shell_TrayWnd")
        {
            return false;
        }

        return true;
    }
}
