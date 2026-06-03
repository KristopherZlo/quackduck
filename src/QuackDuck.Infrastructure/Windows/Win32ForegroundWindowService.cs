using System.Diagnostics;
using System.Runtime.InteropServices;

namespace QuackDuck.Infrastructure.Windows;

public interface IForegroundWindowService
{
    ForegroundWindowSnapshot? Capture();
}

public sealed class Win32ForegroundWindowService : IForegroundWindowService
{
    public ForegroundWindowSnapshot? Capture()
    {
        var handle = NativeMethods.GetForegroundWindow();
        if (handle == IntPtr.Zero)
        {
            return null;
        }

        NativeMethods.GetWindowThreadProcessId(handle, out var processId);
        var className = GetClassName(handle);
        var processName = string.Empty;
        try
        {
            processName = Process.GetProcessById((int)processId).ProcessName;
        }
        catch
        {
            // Process may exit between foreground capture and lookup.
        }

        return new ForegroundWindowSnapshot(
            handle,
            (int)processId,
            processName,
            className,
            IsFullscreen(handle));
    }

    private static string GetClassName(IntPtr handle)
    {
        var buffer = new char[256];
        var length = NativeMethods.GetClassName(handle, buffer, buffer.Length);
        return length > 0 ? new string(buffer, 0, length) : string.Empty;
    }

    private static bool IsFullscreen(IntPtr handle)
    {
        if (!NativeMethods.GetWindowRect(handle, out var rect))
        {
            return false;
        }

        var monitor = NativeMethods.MonitorFromWindow(handle, NativeMethods.MonitorDefaultToNearest);
        if (monitor == IntPtr.Zero)
        {
            return false;
        }

        var info = new NativeMethods.MONITORINFO { cbSize = Marshal.SizeOf<NativeMethods.MONITORINFO>() };
        if (!NativeMethods.GetMonitorInfo(monitor, ref info))
        {
            return false;
        }

        return rect.Left <= info.rcMonitor.Left &&
               rect.Top <= info.rcMonitor.Top &&
               rect.Right >= info.rcMonitor.Right &&
               rect.Bottom >= info.rcMonitor.Bottom;
    }

    private static class NativeMethods
    {
        public const uint MonitorDefaultToNearest = 2;

        [DllImport("user32.dll")]
        public static extern IntPtr GetForegroundWindow();

        [DllImport("user32.dll")]
        public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint processId);

        [DllImport("user32.dll", CharSet = CharSet.Unicode)]
        public static extern int GetClassName(IntPtr hWnd, char[] lpClassName, int nMaxCount);

        [DllImport("user32.dll")]
        [return: MarshalAs(UnmanagedType.Bool)]
        public static extern bool GetWindowRect(IntPtr hWnd, out RECT lpRect);

        [DllImport("user32.dll")]
        public static extern IntPtr MonitorFromWindow(IntPtr hwnd, uint dwFlags);

        [DllImport("user32.dll", CharSet = CharSet.Auto)]
        [return: MarshalAs(UnmanagedType.Bool)]
        public static extern bool GetMonitorInfo(IntPtr hMonitor, ref MONITORINFO lpmi);

        [StructLayout(LayoutKind.Sequential)]
        public struct RECT
        {
            public int Left;
            public int Top;
            public int Right;
            public int Bottom;
        }

        [StructLayout(LayoutKind.Sequential)]
        public struct MONITORINFO
        {
            public int cbSize;
            public RECT rcMonitor;
            public RECT rcWork;
            public uint dwFlags;
        }
    }
}
