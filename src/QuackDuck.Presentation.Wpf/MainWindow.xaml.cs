using System;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Reflection;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;
using System.Windows.Media.Imaging;
using System.Windows.Media;
using System.Windows.Media.Animation;
using System.Windows.Threading;
using Forms = System.Windows.Forms;
using QuackDuck.Application;
using QuackDuck.Application.Rendering;
using QuackDuck.Domain.Interactions;
using QuackDuck.Domain.Pets;
using QuackDuck.Infrastructure.Skins;
using QuackDuck.Infrastructure.Windows;
using WpfMouseEventArgs = System.Windows.Input.MouseEventArgs;
using WpfMouseButtonEventArgs = System.Windows.Input.MouseButtonEventArgs;

namespace QuackDuck.Presentation.Wpf;

public partial class MainWindow : Window
{
    private readonly PetEngine _engine;
    private readonly SkinBitmapCache _skinCache = new();
    private readonly HeartSpawnPlanner _heartSpawnPlanner = new();
    private Forms.NotifyIcon? _trayIcon;
    private Forms.ContextMenuStrip? _trayMenu;
    private Forms.ToolStripMenuItem? _trayShow;
    private Forms.ToolStripMenuItem? _trayHide;
    private Forms.ToolStripMenuItem? _traySettings;
    private Forms.ToolStripMenuItem? _trayUnstuck;
    private Forms.ToolStripMenuItem? _trayCheckUpdates;
    private Forms.ToolStripMenuItem? _trayAbout;
    private Forms.ToolStripMenuItem? _trayDebug;
    private Forms.ToolStripMenuItem? _trayExit;
    private DebugWindow? _debugWindow;
    private WebSettingsWindow? _settingsWindow;
    private readonly Stopwatch _clock = Stopwatch.StartNew();
    private readonly DispatcherTimer _fullscreenTimer;
    private readonly IForegroundWindowService _foregroundWindowService = new Win32ForegroundWindowService();
    private readonly FullscreenPauseDetector _fullscreenPauseDetector = new(Process.GetCurrentProcess().Id);
    private Icon? _visibleTrayIcon;
    private Icon? _hiddenTrayIcon;
    private TimeSpan _lastFrame;
    private PetVisibilityState _visibilityState = PetVisibilityState.Visible;

    public MainWindow(PetEngine engine)
    {
        _engine = engine;
        InitializeComponent();

        Loaded += OnLoaded;
        Unloaded += OnUnloaded;

        _engine.FrameUpdated += OnFrameUpdated;
        _engine.SettingsChanged += OnSettingsChanged;
        CompositionTarget.Rendering += OnRendering;

        _fullscreenTimer = new DispatcherTimer
        {
            Interval = TimeSpan.FromSeconds(4)
        };
        _fullscreenTimer.Tick += (_, _) => EvaluateFullscreenPause();
    }

    private void OnLoaded(object sender, RoutedEventArgs e)
    {
        var geometry = CaptureScreenGeometry();
        _engine.SetViewport(geometry.ViewportWidth, geometry.ViewportHeight);
        _engine.SetDisplayScale(DisplayScalePolicy.Calculate(geometry.ViewportWidth, geometry.ViewportHeight));
        UpdateWindowFromPose(_engine.Pose);
        InitializeTrayIcon();
        _fullscreenTimer.Start();
    }

    private void OnUnloaded(object sender, RoutedEventArgs e)
    {
        _engine.FrameUpdated -= OnFrameUpdated;
        _engine.SettingsChanged -= OnSettingsChanged;
        CompositionTarget.Rendering -= OnRendering;
        _fullscreenTimer.Stop();
    }

    private void OnRendering(object? sender, EventArgs e)
    {
        var now = _clock.Elapsed;
        var delta = now - _lastFrame;
        _lastFrame = now;
        if (!_visibilityState.ShouldTick)
        {
            return;
        }

        if (delta <= TimeSpan.Zero)
        {
            return;
        }

        // Clamp excessively large gaps (e.g., when window was paused) to avoid freezing/jumps.
        if (delta > TimeSpan.FromMilliseconds(250))
        {
            delta = TimeSpan.FromMilliseconds(250);
        }

        _engine.Tick(delta);
    }

    private void OnFrameUpdated(PetFrameUpdate frame)
    {
        Dispatcher.InvokeAsync(() => ApplyFrame(frame), DispatcherPriority.Render);
    }

    private void OnSettingsChanged(PetSettings settings)
    {
        Dispatcher.InvokeAsync(UpdateTrayLabels, DispatcherPriority.Background);
    }

    private void ApplyFrame(PetFrameUpdate frame)
    {
        var bitmaps = _skinCache.GetFrames(
            _engine.CurrentSkin,
            frame.Animation,
            "idle");

        BitmapSource? bitmap = null;
        if (bitmaps.Count > 0)
        {
            var index = Math.Clamp(frame.FrameIndex, 0, bitmaps.Count - 1);
            bitmap = bitmaps[index];
        }

        PetImage.Width = frame.Pose.Width;
        PetImage.Height = frame.Pose.Height;

        if (bitmap != null)
        {
            PetImage.Source = bitmap;
        }

        FlipTransform.ScaleX = frame.FlipX ? -1 : 1;
        UpdateNameLabelAndWindow(frame.Pose);
    }

    private void UpdateWindowFromPose(PetPose pose)
    {
        Left = pose.X;
        Top = pose.Y;
    }

    protected override void OnMouseDown(WpfMouseButtonEventArgs e)
    {
        base.OnMouseDown(e);
        CaptureMouse();
        _engine.HandlePointer(BuildInteraction(PointerInteractionKind.Down, e));
    }

    protected override void OnMouseUp(WpfMouseButtonEventArgs e)
    {
        base.OnMouseUp(e);
        ReleaseMouseCapture();
        _engine.HandlePointer(BuildInteraction(PointerInteractionKind.Up, e));
    }

    protected override void OnMouseMove(WpfMouseEventArgs e)
    {
        base.OnMouseMove(e);
        _engine.HandlePointer(BuildInteraction(PointerInteractionKind.Move, e));
    }

    protected override void OnMouseDoubleClick(WpfMouseButtonEventArgs e)
    {
        base.OnMouseDoubleClick(e);
        _engine.HandlePointer(BuildInteraction(PointerInteractionKind.DoubleClick, e));
        SpawnHeart();
    }

    protected override void OnClosed(EventArgs e)
    {
        if (_trayIcon != null)
        {
            _trayIcon.Visible = false;
            _trayIcon.Dispose();
            _trayIcon = null;
        }
        _visibleTrayIcon?.Dispose();
        _hiddenTrayIcon?.Dispose();
        _trayMenu?.Dispose();
        _fullscreenTimer.Stop();
        CompositionTarget.Rendering -= OnRendering;
        base.OnClosed(e);
    }

    private PointerInteraction BuildInteraction(PointerInteractionKind kind, WpfMouseEventArgs e)
    {
        var relative = e.GetPosition(this);
        var petLeft = Canvas.GetLeft(PetImage);
        var petTop = Canvas.GetTop(PetImage);
        if (double.IsNaN(petLeft)) petLeft = 0;
        if (double.IsNaN(petTop)) petTop = 0;
        var petRelativeX = relative.X - petLeft;
        var petRelativeY = relative.Y - petTop;
        var screen = PointToScreen(relative);
        var button = PointerButton.None;
        if (e is MouseButtonEventArgs mbe)
        {
            button = mbe.ChangedButton switch
            {
                MouseButton.Left => PointerButton.Left,
                MouseButton.Right => PointerButton.Right,
                MouseButton.Middle => PointerButton.Middle,
                _ => PointerButton.None
            };
        }
        else if (e.LeftButton == MouseButtonState.Pressed)
        {
            button = PointerButton.Left;
        }

        return new PointerInteraction(
            kind,
            petRelativeX,
            petRelativeY,
            button,
            screen.X,
            screen.Y);
    }

    private void SpawnHeart()
    {
        var spawn = _heartSpawnPlanner.Create(_engine.Pose);
        var heartWindow = new HeartWindow(spawn.Left, spawn.Top, spawn.Size, HeartImagePath);
        heartWindow.Show();
    }


    private void UpdateNameLabelAndWindow(PetPose pose)
    {
        var labelSize = MeasureNameLabel();
        var layout = PetNameLayout.Calculate(
            pose,
            _engine.Settings.ShowName,
            _engine.Settings.PetName,
            labelSize.Width,
            labelSize.Height,
            _engine.Settings.NameOffsetY);

        RootCanvas.Width = layout.RootWidth;
        RootCanvas.Height = layout.RootHeight;
        Canvas.SetLeft(PetImage, layout.PetLeft);
        Canvas.SetTop(PetImage, layout.PetTop);

        if (layout.NameVisible)
        {
            Canvas.SetLeft(NameLabel, layout.NameLeft);
            Canvas.SetTop(NameLabel, layout.NameTop);
        }

        Left = layout.WindowLeft;
        Top = layout.WindowTop;
    }

    private System.Windows.Size MeasureNameLabel()
    {
        var name = _engine.Settings.PetName;
        if (!_engine.Settings.ShowName || string.IsNullOrWhiteSpace(name))
        {
            NameLabel.Visibility = Visibility.Collapsed;
            return System.Windows.Size.Empty;
        }

        NameLabel.Text = name;
        NameLabel.FontSize = _engine.Settings.FontBaseSize * (_engine.Settings.PetSize / 3.0);
        NameLabel.Visibility = Visibility.Visible;
        NameLabel.Measure(new System.Windows.Size(double.PositiveInfinity, double.PositiveInfinity));
        return NameLabel.DesiredSize;
    }

    private void InitializeTrayIcon()
    {
        _trayMenu = new Forms.ContextMenuStrip();
        _trayShow = new Forms.ToolStripMenuItem(string.Empty, null, (_, _) => ShowWindowFromTray());
        _trayHide = new Forms.ToolStripMenuItem(string.Empty, null, (_, _) => HideWindowFromTray());
        _traySettings = new Forms.ToolStripMenuItem(string.Empty, null, (_, _) => OpenSettingsWindow());
        _trayUnstuck = new Forms.ToolStripMenuItem(string.Empty, null, (_, _) => UnstuckPet());
        _trayCheckUpdates = new Forms.ToolStripMenuItem(string.Empty, null, async (_, _) => await CheckUpdatesAsync());
        _trayAbout = new Forms.ToolStripMenuItem(string.Empty, null, (_, _) => ShowAboutDialog());
        _trayDebug = new Forms.ToolStripMenuItem(string.Empty, null, (_, _) => ShowDebugWindow());
        _trayExit = new Forms.ToolStripMenuItem(string.Empty, null, (_, _) => Close());

        _trayMenu.Items.AddRange(new Forms.ToolStripItem[]
        {
            _trayShow,
            _trayHide,
            _traySettings,
            _trayUnstuck,
            _trayCheckUpdates,
            _trayAbout,
            _trayDebug,
            new Forms.ToolStripSeparator(),
            _trayExit
        });
        UpdateTrayLabels();

        _visibleTrayIcon = LoadTrayIcon(hidden: false);
        _hiddenTrayIcon = LoadTrayIcon(hidden: true);
        _trayIcon = new Forms.NotifyIcon
        {
            Icon = _visibleTrayIcon,
            Visible = true,
            Text = "QuackDuck",
            ContextMenuStrip = _trayMenu
        };
        _trayIcon.MouseClick += OnTrayIconMouseClick;
    }

    private Icon LoadTrayIcon(bool hidden)
    {
        var iconName = hidden ? "white-quackduck-hidden.ico" : "white-quackduck-visible.ico";
        var iconPath = Path.Combine(AppContext.BaseDirectory, "assets", "images", iconName);
        return File.Exists(iconPath) ? new Icon(iconPath) : (Icon)SystemIcons.Application.Clone();
    }

    private static string HeartImagePath => Path.Combine(AppContext.BaseDirectory, "assets", "images", "heart.png");

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

    private void OnTrayIconMouseClick(object? sender, Forms.MouseEventArgs e)
    {
        if (e.Button != Forms.MouseButtons.Left)
        {
            return;
        }

        if (_visibilityState.ManuallyHidden)
        {
            ShowWindowFromTray();
        }
        else
        {
            HideWindowFromTray();
        }
    }

    private void ShowWindowFromTray()
    {
        _visibilityState = _visibilityState.SetManualHidden(false);
        UpdateTrayIconImage();
        ShowPetWindow(activate: true);
    }

    private void ShowPetWindow(bool activate)
    {
        Show();
        WindowState = WindowState.Normal;
        if (activate)
        {
            Activate();
        }
    }

    private void HideWindowFromTray()
    {
        _visibilityState = _visibilityState.SetManualHidden(true);
        UpdateTrayIconImage();
        Hide();
    }

    private void EvaluateFullscreenPause()
    {
        if (_visibilityState.ManuallyHidden)
        {
            return;
        }

        var shouldPause = _fullscreenPauseDetector.ShouldPause(_foregroundWindowService.Capture());
        if (shouldPause && !_visibilityState.FullscreenPaused)
        {
            _visibilityState = _visibilityState.SetFullscreenPaused(true);
            UpdateTrayIconImage();
            Hide();
            return;
        }

        if (!shouldPause && _visibilityState.FullscreenPaused)
        {
            _visibilityState = _visibilityState.SetFullscreenPaused(false);
            UpdateTrayIconImage();
            ShowPetWindow(activate: false);
        }
    }

    private void UpdateTrayIconImage()
    {
        if (_trayIcon == null)
        {
            return;
        }

        _trayIcon.Icon = _visibilityState.UseHiddenTrayIcon
            ? _hiddenTrayIcon ?? SystemIcons.Application
            : _visibleTrayIcon ?? SystemIcons.Application;
    }

    private void UnstuckPet()
    {
        _engine.Unstuck();
    }

    private async Task CheckUpdatesAsync()
    {
        var update = await _engine.CheckForUpdatesAsync();
        if (update == null)
        {
            System.Windows.MessageBox.Show(
                this,
                T("no_updates", "No updates available"),
                T("check_updates_title", "Updates"),
                MessageBoxButton.OK,
                MessageBoxImage.Information);
            return;
        }

        var message = string.Format(
            T("new_version_available_text", "New version {0} available.\n\n{1}"),
            update.Version,
            update.Notes);
        var choice = System.Windows.MessageBox.Show(
            this,
            $"{message}\n\nYes: install now\nNo: remind later\nCancel: skip this version",
            T("update_available", "Update available"),
            MessageBoxButton.YesNoCancel,
            MessageBoxImage.Information);

        if (choice == MessageBoxResult.Cancel)
        {
            await _engine.ApplySettingsAsync(_engine.Settings with { SkippedVersion = update.Version });
            return;
        }

        if (choice != MessageBoxResult.Yes)
        {
            return;
        }

        var installed = await _engine.DownloadAndApplyUpdateAsync(update);
        if (!installed)
        {
            System.Windows.MessageBox.Show(
                this,
                "Update check succeeded, but installation is only enabled for published builds.",
                T("check_updates_title", "Updates"),
                MessageBoxButton.OK,
                MessageBoxImage.Information);
            return;
        }

        System.Windows.Application.Current.Shutdown();
    }

    private void OpenSettingsWindow()
    {
        try
        {
            if (_settingsWindow == null)
            {
                _settingsWindow = new WebSettingsWindow(_engine)
                {
                    Owner = this
                };
                _settingsWindow.Closed += (_, _) => _settingsWindow = null;
            }

            _settingsWindow.Show();
            _settingsWindow.Activate();
        }
        catch (Exception ex)
        {
            System.Windows.MessageBox.Show(this, $"Failed to launch settings: {ex.Message}", "QuackDuck", MessageBoxButton.OK, MessageBoxImage.Error);
        }
    }

    private string T(string key, string fallback) => _engine.Localization.Translate(key, fallback);

    private void UpdateTrayLabels()
    {
        if (_trayShow != null) _trayShow.Text = T("show", "Show");
        if (_trayHide != null) _trayHide.Text = T("hide", "Hide");
        if (_traySettings != null) _traySettings.Text = T("settings", "Settings");
        if (_trayUnstuck != null) _trayUnstuck.Text = T("unstuck", "Unstuck");
        if (_trayCheckUpdates != null) _trayCheckUpdates.Text = T("check_updates", "Check updates");
        if (_trayAbout != null) _trayAbout.Text = T("about", "About");
        if (_trayDebug != null) _trayDebug.Text = T("debug_mode", "Debug");
        if (_trayExit != null) _trayExit.Text = T("exit", "Exit");
        if (_trayIcon != null)
        {
            _trayIcon.Text = "QuackDuck";
            UpdateTrayIconImage();
        }
    }

    private void ShowAboutDialog()
    {
        var version = Assembly.GetExecutingAssembly().GetName().Version?.ToString() ?? "0.0.0";
        var message = $"QuackDuck\nVersion {version}\n\nC# port in progress.";
        System.Windows.MessageBox.Show(this, message, T("about_title", "About"), MessageBoxButton.OK, MessageBoxImage.Information);
    }

    private void ShowDebugStub()
    {
        ShowDebugWindow();
    }

    private void ShowDebugWindow()
    {
        if (_debugWindow == null)
        {
            _debugWindow = new DebugWindow(_engine);
            _debugWindow.Owner = this;
            _debugWindow.Closed += (_, _) => _debugWindow = null;
        }

        _debugWindow.Show();
        _debugWindow.Activate();
    }
}
