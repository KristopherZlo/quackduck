using System.Diagnostics;
using System.IO;
using System.Reflection;
using System.Windows;
using QuackDuck.Application;
using QuackDuck.Application.Rendering;
using QuackDuck.Infrastructure.Audio;
using QuackDuck.Infrastructure.Localization;
using QuackDuck.Infrastructure.Paths;
using QuackDuck.Infrastructure.Settings;
using QuackDuck.Infrastructure.Skins;
using QuackDuck.Infrastructure.Updates;

namespace QuackDuck.Presentation.Wpf;

public partial class App : System.Windows.Application
{
    private PetEngine? _engine;
    private string? _logPath;
    private string? _crashLogPath;

    protected override async void OnStartup(StartupEventArgs e)
    {
        base.OnStartup(e);

        var paths = new AppPathProvider();
        _logPath = Path.Combine(paths.DataRoot, "quackduck.log");
        _crashLogPath = Path.Combine(paths.DataRoot, "quackduck_crash.log");
        Log("QuackDuck starting.");

        if (e.Args.Any(arg => string.Equals(arg, "--cleanup-bak", StringComparison.OrdinalIgnoreCase)))
        {
            var deleted = new BakCleanupService().Cleanup(AppContext.BaseDirectory);
            Log($"Cleanup-bak removed {deleted.Count} entries.");
        }

        DispatcherUnhandledException += OnDispatcherUnhandledException;
        AppDomain.CurrentDomain.UnhandledException += OnUnhandledException;

        var settingsFileExists = File.Exists(Path.Combine(paths.DataRoot, "settings.json"));
        var settingsStore = new JsonSettingsStore(paths);
        var localization = new JsonLocalizationService(paths);
        var skinService = new SkinFileService(paths);
        var audioService = new MediaAudioService();
        var microphoneMonitor = new NaudioMicrophoneMonitor();
        var executablePath = Process.GetCurrentProcess().MainModule?.FileName ?? string.Empty;
        var updateService = new GitHubUpdateService(new GitHubUpdateOptions
        {
            Owner = "KristopherZlo",
            Repository = "quackduck",
            CurrentVersion = GetAppVersion(),
            AppDirectory = AppContext.BaseDirectory,
            MainExecutablePath = executablePath,
            UpdaterExecutablePath = Path.Combine(AppContext.BaseDirectory, "QuackDuck.Updater.exe"),
            TempDirectory = paths.TempRoot,
            InstallEnabled = IsPublishedRun(AppContext.BaseDirectory)
        });
        var autostart = new RegistryAutostartService("QuackDuck", executablePath);

        _engine = new PetEngine(
            settingsStore,
            skinService,
            audioService,
            microphoneMonitor,
            localization,
            updateService,
            autostart);

        var geometry = CaptureScreenGeometry();
        _engine.SetViewport(geometry.ViewportWidth, geometry.ViewportHeight);
        _engine.SetDisplayScale(DisplayScalePolicy.Calculate(geometry.ViewportWidth, geometry.ViewportHeight));
        await _engine.StartAsync();
        if (!settingsFileExists && geometry.DefaultGroundOffset > 0)
        {
            await _engine.ApplySettingsAsync(_engine.Settings with { GroundLevelOffset = geometry.DefaultGroundOffset });
        }

        var window = new MainWindow(_engine);
        MainWindow = window;
        window.Show();
    }

    protected override async void OnExit(ExitEventArgs e)
    {
        Log("Shutting down.");
        DispatcherUnhandledException -= OnDispatcherUnhandledException;
        AppDomain.CurrentDomain.UnhandledException -= OnUnhandledException;

        if (_engine != null)
        {
            await _engine.DisposeAsync();
        }
        base.OnExit(e);
    }

    private void Log(string message)
    {
        if (string.IsNullOrWhiteSpace(_logPath))
        {
            return;
        }

        try
        {
            File.AppendAllText(_logPath, $"{DateTime.Now:O} {message}{Environment.NewLine}");
        }
        catch
        {
            // ignore logging failures
        }
    }

    private void OnDispatcherUnhandledException(object sender, System.Windows.Threading.DispatcherUnhandledExceptionEventArgs e)
    {
        WriteCrashLog(e.Exception);
        System.Windows.MessageBox.Show("The application encountered an error and needs to close.", "QuackDuck", MessageBoxButton.OK, MessageBoxImage.Error);
        e.Handled = true;
        Shutdown();
    }

    private void OnUnhandledException(object sender, UnhandledExceptionEventArgs e)
    {
        if (e.ExceptionObject is Exception ex)
        {
            WriteCrashLog(ex);
        }
    }

    private void WriteCrashLog(Exception ex)
    {
        if (string.IsNullOrWhiteSpace(_crashLogPath))
        {
            return;
        }

        try
        {
            var details = $"{DateTime.Now:O}{Environment.NewLine}{ex}{Environment.NewLine}";
            File.AppendAllText(_crashLogPath, details);
        }
        catch
        {
            // ignore logging failures
        }
    }

    private static string GetAppVersion()
    {
        return Assembly.GetExecutingAssembly()
                   .GetCustomAttribute<AssemblyInformationalVersionAttribute>()
                   ?.InformationalVersion
               ?? Assembly.GetExecutingAssembly().GetName().Version?.ToString(3)
               ?? "0.0.0";
    }

    private static ScreenGeometry CaptureScreenGeometry()
    {
        var workArea = SystemParameters.WorkArea;
        return ScreenGeometryPolicy.Calculate(
            SystemParameters.PrimaryScreenWidth,
            SystemParameters.PrimaryScreenHeight,
            workArea.Left,
            workArea.Top,
            workArea.Width,
            workArea.Height);
    }

    private static bool IsPublishedRun(string baseDirectory)
    {
        var normalized = baseDirectory.TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
        return !normalized.Contains($"{Path.DirectorySeparatorChar}bin{Path.DirectorySeparatorChar}Debug", StringComparison.OrdinalIgnoreCase) &&
               !normalized.Contains($"{Path.DirectorySeparatorChar}bin{Path.DirectorySeparatorChar}Release", StringComparison.OrdinalIgnoreCase) &&
               File.Exists(Path.Combine(baseDirectory, "QuackDuck.Updater.exe"));
    }
}
