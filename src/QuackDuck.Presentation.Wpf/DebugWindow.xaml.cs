using System;
using System.Collections.Generic;
using System.Windows;
using System.Windows.Threading;
using QuackDuck.Application;
using QuackDuck.Domain.Pets;
using QuackDuck.Domain.States;

namespace QuackDuck.Presentation.Wpf;

public partial class DebugWindow : Window
{
    private readonly PetEngine _engine;
    private readonly DispatcherTimer _timer;
    private readonly Queue<string> _history = new();
    private const int MaxHistory = 30;

    public DebugWindow(PetEngine engine)
    {
        _engine = engine;
        InitializeComponent();

        _engine.StateChanged += OnStateChanged;
        _timer = new DispatcherTimer
        {
            Interval = TimeSpan.FromMilliseconds(200)
        };
        _timer.Tick += (_, _) => Refresh();
        _timer.Start();

        Loaded += (_, _) => Refresh();
        Closed += OnClosed;
    }

    private void Refresh()
    {
        var pose = _engine.Pose;
        StateText.Text = $"State: {_engine.CurrentState.Kind}";
        PoseText.Text = $"Pose: X={pose.X:0.0}, Y={pose.Y:0.0}, W={pose.Width:0.0}, H={pose.Height:0.0}";
        EnergyText.Text = $"Energy: {_engine.Energy}";
        MicText.Text = $"Mic level: {_engine.LastMicLevel}";
        MicBar.Value = Math.Clamp(_engine.LastMicLevel, 0, 100);
        DestinationText.Text = $"Destination: {(_engine.DestinationX.HasValue ? _engine.DestinationX.Value.ToString("0.0") : "none")}";
    }

    private void OnStateChanged(IPetState state)
    {
        Dispatcher.InvokeAsync(() =>
        {
            var entry = $"{DateTime.Now:HH:mm:ss} {_engine.CurrentState.Kind}";
            _history.Enqueue(entry);
            while (_history.Count > MaxHistory)
            {
                _history.Dequeue();
            }

            StateHistory.ItemsSource = null;
            StateHistory.ItemsSource = _history.ToArray();
        });
    }

    private void OnClosed(object? sender, EventArgs e)
    {
        _engine.StateChanged -= OnStateChanged;
        _timer.Stop();
    }

    private void Force(PetStateKind kind) => _engine.ForceState(kind);

    private void OnForceIdle(object sender, RoutedEventArgs e) => Force(PetStateKind.Idle);
    private void OnForceWalk(object sender, RoutedEventArgs e) => Force(PetStateKind.Walking);
    private void OnForceRun(object sender, RoutedEventArgs e) => Force(PetStateKind.Run);
    private void OnForcePlayful(object sender, RoutedEventArgs e) => Force(PetStateKind.Playful);
    private void OnForceJump(object sender, RoutedEventArgs e) => Force(PetStateKind.Jumping);
    private void OnForceAttack(object sender, RoutedEventArgs e) => Force(PetStateKind.Attack);
    private void OnForceSleep(object sender, RoutedEventArgs e) => Force(PetStateKind.Sleeping);
    private void OnForceListen(object sender, RoutedEventArgs e) => Force(PetStateKind.Listening);
    private void OnForceFall(object sender, RoutedEventArgs e) => Force(PetStateKind.Falling);
    private void OnForceLand(object sender, RoutedEventArgs e) => Force(PetStateKind.Landing);
    private void OnForceDrag(object sender, RoutedEventArgs e) => Force(PetStateKind.Dragging);
    private void OnForceHunt(object sender, RoutedEventArgs e) => Force(PetStateKind.CursorHunt);
    private void OnForceWallgrab(object sender, RoutedEventArgs e) => Force(PetStateKind.Wallgrab);

    private void OnUnstuck(object sender, RoutedEventArgs e) => _engine.Unstuck();

    private async void OnPlaySound(object sender, RoutedEventArgs e)
    {
        try
        {
            var played = await _engine.PlayTestSoundAsync();
            if (!played)
            {
                System.Windows.MessageBox.Show(this, "Current skin has no sound files.", "QuackDuck Debug", MessageBoxButton.OK, MessageBoxImage.Information);
            }
        }
        catch (Exception ex)
        {
            System.Windows.MessageBox.Show(this, $"Failed to play sound: {ex.Message}", "QuackDuck Debug", MessageBoxButton.OK, MessageBoxImage.Error);
        }
    }
}
