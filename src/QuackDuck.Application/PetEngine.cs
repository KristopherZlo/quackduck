using QuackDuck.Application.Abstractions;
using QuackDuck.Application.Rendering;
using QuackDuck.Application.StateMachine;
using QuackDuck.Application.States;
using QuackDuck.Domain.Interactions;
using QuackDuck.Domain.Pets;
using QuackDuck.Domain.Skins;
using QuackDuck.Domain.States;

namespace QuackDuck.Application;

/// <summary>
/// Coordinates settings, resources, state machine, and IO services for the pet.
/// </summary>
public sealed class PetEngine : IAsyncDisposable
{
    private readonly Random _random = new();
    private readonly Queue<(DateTime Timestamp, double X, double Y)> _pointerHistory = new();
    private readonly ISettingsStore _settingsStore;
    private readonly ISkinService _skinService;
    private readonly IAudioService _audioService;
    private readonly IMicrophoneMonitor _microphoneMonitor;
    private readonly ILocalizationService _localization;
    private readonly IUpdateService _updateService;
    private readonly IAutostartService _autostartService;
    private readonly PetBehaviorScheduler _behaviorScheduler;
    private readonly PetStateMachine _stateMachine;
    private double? _destinationX;
    private TimeSpan _attackElapsed = TimeSpan.Zero;
    private TimeSpan _runElapsed = TimeSpan.Zero;
    private TimeSpan _playfulElapsed = TimeSpan.Zero;
    private TimeSpan? _listeningEntryCountdown = null;
    private TimeSpan? _listeningExitCountdown = null;

    public PetSettings Settings { get; private set; } = PetSettings.Default;
    public SkinDefinition CurrentSkin { get; private set; }
    public PetPose Pose { get; private set; } = PetPose.Empty;
    public ILocalizationService Localization => _localization;
    public double ViewportWidth { get; private set; } = 800;
    public double ViewportHeight { get; private set; } = 600;
    public double DisplayScale { get; private set; } = 1.0;
    public double GroundLevel => ViewportHeight - Settings.GroundLevelOffset;
    public double ScaledWidth => CurrentSkin.FrameWidth * Settings.PetSize * DisplayScale;
    public double ScaledHeight => CurrentSkin.FrameHeight * Settings.PetSize * DisplayScale;
    public double BaseSpeed => Settings.DuckSpeed * (Settings.PetSize / 3.0) * DisplayScale;
    public double Gravity => Math.Max(0.5, Settings.PetSize / 3.0) * DisplayScale;
    public int Direction { get; set; } = 1;
    public bool IsListening { get; private set; }
    public bool IsPlayful { get; set; }
    public double LastPointerScreenX { get; private set; }
    public double LastPointerScreenY { get; private set; }
    public Random Random => _random;
    public int Energy { get; private set; } = 1000;
    public double? DestinationX => _destinationX;

    public event Action<PetFrameUpdate>? FrameUpdated;
    public event Action<PetSettings>? SettingsChanged;
    public event Action<IPetState>? StateChanged;

    public IPetState CurrentState => _stateMachine.Current;
    public int LastMicLevel { get; private set; }

    public PetEngine(
        ISettingsStore settingsStore,
        ISkinService skinService,
        IAudioService audioService,
        IMicrophoneMonitor microphoneMonitor,
        ILocalizationService localization,
        IUpdateService updateService,
        IAutostartService autostartService)
    {
        _settingsStore = settingsStore;
        _skinService = skinService;
        _audioService = audioService;
        _microphoneMonitor = microphoneMonitor;
        _localization = localization;
        _updateService = updateService;
        _autostartService = autostartService;

        CurrentSkin = _skinService.DefaultSkin;
        _stateMachine = new PetStateMachine(new NoOpState());
        _stateMachine.StateChanged += state => StateChanged?.Invoke(state);
        _microphoneMonitor.VolumeChanged += OnVolumeChanged;
        _behaviorScheduler = new PetBehaviorScheduler(_random, Settings);
    }

    public async Task InitializeAsync(CancellationToken cancellationToken = default)
    {
        Settings = await _settingsStore.LoadAsync(cancellationToken);

        await _localization.LoadAsync(Settings.CurrentLanguage, cancellationToken);
        CurrentSkin = await _skinService.LoadSkinAsync(Settings.SelectedSkin, cancellationToken);

        _audioService.Enabled = Settings.SoundEnabled;
        _audioService.Volume = Settings.SoundVolume;

        RefreshPoseSize();
        EnsureInitialPose();
        _behaviorScheduler.ResetFromSettings(Settings);
        await _autostartService.SetAsync(Settings.AutostartEnabled, cancellationToken);
        SettingsChanged?.Invoke(Settings);
    }

    public async Task StartAsync(CancellationToken cancellationToken = default)
    {
        await InitializeAsync(cancellationToken);
        if (CurrentState.Kind == PetStateKind.None)
        {
            TransitionTo(new FallingState(this));
        }
        await _microphoneMonitor.StartAsync(cancellationToken);
    }

    public void Tick(TimeSpan delta)
    {
        _behaviorScheduler.Advance(delta);
        _attackElapsed += delta;
        _runElapsed += delta;
        _playfulElapsed += delta;
        ProcessListeningTimers(delta);
        _stateMachine.Update(delta);
        CheckAttackTrigger();
        CheckRunTrigger();
        CheckPlayfulTrigger();

        var triggers = _behaviorScheduler.Evaluate(CurrentState.Kind, IsListening);
        if (triggers.ShouldSleep)
        {
            TransitionTo(new SleepApproachState(this));
        }

        if (triggers.ShouldChangeDirection)
        {
            FlipDirection();
        }

        if (triggers.ShouldTriggerRandomBehavior)
        {
            TriggerRandomBehavior();
        }

        if (triggers.ShouldPlayAmbientSound)
        {
            _ = PlayRandomSoundAsync();
        }

        if (triggers.ShouldHuntCursor)
        {
            TransitionTo(new CursorHuntState(this));
        }
    }

    public void HandlePointer(PointerInteraction interaction)
    {
        LastPointerScreenX = interaction.ScreenX;
        LastPointerScreenY = interaction.ScreenY;
        RegisterInteraction();
        TrackPointer(interaction);
        _stateMachine.HandlePointer(interaction);
    }

    public void TransitionTo(IPetState state) => _stateMachine.ChangeState(state);

    public void PublishFrame(PetFrameUpdate frame) => FrameUpdated?.Invoke(frame);

    public void SetViewport(double width, double height)
    {
        ViewportWidth = Math.Max(1, width);
        ViewportHeight = Math.Max(1, height);
    }

    public void SetDisplayScale(double scale)
    {
        if (!double.IsFinite(scale) || scale <= 0)
        {
            scale = 1.0;
        }

        DisplayScale = Math.Clamp(scale, 0.5, 4.0);
        RefreshPoseSize();
        SetPose(Pose.X, Pose.Y);
    }

    public void RefreshPoseSize() => Pose = Pose with { Width = ScaledWidth, Height = ScaledHeight };

    public void SetPose(double x, double y)
    {
        Pose = new PetPose(
            ClampX(x),
            ClampY(y),
            Pose.FacingRight,
            ScaledWidth,
            ScaledHeight);
    }

    public void SetFacing(bool facingRight) => Pose = Pose with { FacingRight = facingRight };

    public void RegisterInteraction() => _behaviorScheduler.RegisterInteraction();

    public void MarkListening(bool listening) => IsListening = listening;

    public void FlipDirection()
    {
        Direction = -Direction;
        SetFacing(Direction >= 0);
    }

    public double ClampX(double x)
    {
        var maxX = Math.Max(0, ViewportWidth - ScaledWidth);
        return Math.Max(0, Math.Min(x, maxX));
    }

    public double ClampY(double y)
    {
        var maxY = Math.Max(0, GroundLevel - ScaledHeight);
        var minY = -ScaledHeight * 2;
        return Math.Max(minY, Math.Min(y, maxY));
    }

    public void ClearDestination() => _destinationX = null;

    public void SetRandomDestination()
    {
        var maxX = Math.Max(0, ViewportWidth - ScaledWidth);
        _destinationX = _random.NextDouble() * maxX;
    }

    public void SetDestination(double x) => _destinationX = ClampX(x);

    private void EnsureInitialPose()
    {
        if (Pose.Width <= 0 || Pose.Height <= 0)
        {
            RefreshPoseSize();
        }

        if (Pose == PetPose.Empty || Pose.Height <= 0)
        {
            var startX = ClampX((ViewportWidth - ScaledWidth) / 2);
            var startY = -ScaledHeight;
            Pose = new PetPose(startX, startY, true, ScaledWidth, ScaledHeight);
        }
    }

    private void TriggerRandomBehavior()
    {
        var behaviors = new List<Action>
        {
            () =>
            {
                if (CurrentState.Kind != PetStateKind.Idle &&
                    CurrentState.Kind != PetStateKind.Falling &&
                    CurrentState.Kind != PetStateKind.Dragging)
                {
                    TransitionTo(new IdleState(this));
                }
            },
            FlipDirection
        };

        var choice = _random.Next(behaviors.Count);
        behaviors[choice]();
    }

    public Task SaveSettingsAsync(CancellationToken cancellationToken = default) =>
        _settingsStore.SaveAsync(Settings, cancellationToken);

    public async Task<UpdateInfo?> CheckForUpdatesAsync(CancellationToken cancellationToken = default)
    {
        var update = await _updateService.CheckForUpdatesAsync(cancellationToken);
        if (update == null)
        {
            return null;
        }

        return string.Equals(NormalizeVersion(update.Version), NormalizeVersion(Settings.SkippedVersion), StringComparison.OrdinalIgnoreCase)
            ? null
            : update;
    }

    public Task<bool> DownloadAndApplyUpdateAsync(UpdateInfo info, IProgress<int>? progress = null, CancellationToken cancellationToken = default) =>
        _updateService.DownloadAndApplyAsync(info, progress, cancellationToken);

    public Task<IReadOnlyList<SkinDefinition>> DiscoverSkinsAsync(string? rootFolder = null, CancellationToken cancellationToken = default) =>
        _skinService.DiscoverAsync(rootFolder ?? Settings.SkinFolder, cancellationToken);

    public Task<SkinDefinition> LoadSkinDefinitionAsync(string? skinPath, CancellationToken cancellationToken = default) =>
        _skinService.LoadSkinAsync(skinPath, cancellationToken);

    public async Task ApplySettingsAsync(PetSettings updated, CancellationToken cancellationToken = default)
    {
        var previousStateKind = CurrentState.Kind;
        Settings = updated;
        _audioService.Enabled = Settings.SoundEnabled;
        _audioService.Volume = Settings.SoundVolume;
        await _localization.LoadAsync(Settings.CurrentLanguage, cancellationToken);
        CurrentSkin = await _skinService.LoadSkinAsync(Settings.SelectedSkin, cancellationToken);
        RefreshPoseSize();
        SetPose(Pose.X, Pose.Y);
        var shouldFallToLowerGround =
            Pose.Y + ScaledHeight < GroundLevel - 0.5 &&
            previousStateKind is not (PetStateKind.Falling or PetStateKind.Jumping or PetStateKind.Dragging);
        _behaviorScheduler.ResetFromSettings(Settings);
        await _autostartService.SetAsync(Settings.AutostartEnabled, cancellationToken);
        await _settingsStore.SaveAsync(Settings, cancellationToken);
        SettingsChanged?.Invoke(Settings);
        if (shouldFallToLowerGround)
        {
            TransitionTo(new FallingState(this, returnState: CreateState(previousStateKind)));
        }
        else
        {
            RecreateCurrentState();
        }
    }

    private void OnVolumeChanged(int volume)
    {
        LastMicLevel = volume;
        if (volume > Settings.ActivationThreshold)
        {
            RegisterInteraction();

            // cancel any pending exit when loud input is detected
            _listeningExitCountdown = null;

            // schedule listening entry after a short delay if allowed
            if (!IsListening &&
                _listeningEntryCountdown == null &&
                !IsListeningBlocked())
            {
                _listeningEntryCountdown = TimeSpan.FromMilliseconds(100);
            }

            if (Settings.SoundEnabled && _random.NextDouble() < Settings.SoundResponseProbability)
            {
                _ = PlayRandomSoundAsync();
            }

            return;
        }

        // quiet input: stop pending entry and schedule exit if already listening
        _listeningEntryCountdown = null;

        if (IsListening && _listeningExitCountdown == null)
        {
            _listeningExitCountdown = TimeSpan.FromSeconds(1);
        }

        _stateMachine.HandleMicLevel(volume);
    }

    public async ValueTask DisposeAsync()
    {
        _microphoneMonitor.VolumeChanged -= OnVolumeChanged;
        await _microphoneMonitor.StopAsync();
        await _audioService.StopAsync();
    }

    public void Unstuck()
    {
        var centerX = ClampX((ViewportWidth - ScaledWidth) / 2);
        var groundY = GroundLevel - ScaledHeight;
        SetPose(centerX, groundY);
        RegisterInteraction();
        TransitionTo(new WalkingState(this));
    }

    private void TrackPointer(PointerInteraction interaction)
    {
        if (interaction.Kind != PointerInteractionKind.Move)
        {
            return;
        }

        if (interaction.ScreenX <= 0 && interaction.ScreenY <= 0)
        {
            return;
        }

        var now = DateTime.UtcNow;
        _pointerHistory.Enqueue((now, interaction.ScreenX, interaction.ScreenY));

        while (_pointerHistory.Count > 40 ||
               (now - _pointerHistory.Peek().Timestamp) > TimeSpan.FromSeconds(1))
        {
            _pointerHistory.Dequeue();
        }

        CheckCursorShake();
    }

    private void CheckCursorShake()
    {
        if (!Settings.RandomBehaviorEnabled || _pointerHistory.Count < 4)
        {
            return;
        }

        var entries = _pointerHistory.ToArray();
        var newest = entries[^1];
        var window = newest.Timestamp - entries[0].Timestamp;
        if (window > TimeSpan.FromSeconds(1))
        {
            return;
        }

        // Only consider shakes when the cursor is near the duck (Python uses ~50px*size/3)
        var centerX = Pose.X + ScaledWidth / 2.0;
        var centerY = Pose.Y + ScaledHeight / 2.0;
        var dx = newest.X - centerX;
        var dy = newest.Y - centerY;
        var dist = Math.Sqrt(dx * dx + dy * dy);
        var threshold = 50 * (Settings.PetSize / 3.0);
        if (dist > threshold)
        {
            return;
        }

        var directionChanges = 0;
        for (var i = 2; i < entries.Length; i++)
        {
            var prevDx = entries[i - 1].X - entries[i - 2].X;
            var prevDy = entries[i - 1].Y - entries[i - 2].Y;
            var curDx = entries[i].X - entries[i - 1].X;
            var curDy = entries[i].Y - entries[i - 1].Y;

            if ((prevDx * curDx < 0) || (prevDy * curDy < 0))
            {
                directionChanges++;
            }
        }

        if (directionChanges >= 4 &&
            CurrentState.Kind != PetStateKind.Playful &&
            CurrentState.Kind != PetStateKind.Dragging &&
            CurrentState.Kind != PetStateKind.Falling &&
            CurrentState.Kind != PetStateKind.Jumping)
        {
            TransitionTo(new PlayfulState(this));
        }
    }

    private void CheckAttackTrigger()
    {
        if (_attackElapsed < TimeSpan.FromSeconds(5))
        {
            return;
        }

        _attackElapsed = TimeSpan.Zero;

        if ((CurrentState.Kind != PetStateKind.Walking && CurrentState.Kind != PetStateKind.Idle) ||
            !CurrentSkin.Animations.ContainsKey("attack") ||
            CurrentState.Kind == PetStateKind.Attack ||
            CurrentState.Kind == PetStateKind.Falling ||
            CurrentState.Kind == PetStateKind.Jumping)
        {
            return;
        }

        if (!TryGetCursorPosition(out var cursorX, out var cursorY))
        {
            return;
        }

        var centerX = Pose.X + ScaledWidth / 2.0;
        var centerY = Pose.Y + ScaledHeight / 2.0;
        var dx = cursorX - centerX;
        var dy = cursorY - centerY;
        var distance = Math.Sqrt(dx * dx + dy * dy);
        var attackDistance = 50 * (Settings.PetSize / 3.0);

        if (distance <= attackDistance)
        {
            Direction = dx >= 0 ? 1 : -1;
            SetFacing(Direction >= 0);
            var chance = _random.NextDouble() * (0.2 - 0.01) + 0.01;
            if (_random.NextDouble() < chance)
            {
                TransitionTo(new AttackState(this, new WalkingState(this)));
            }
        }
    }

    private static bool TryGetCursorPosition(out double x, out double y)
    {
        if (NativeMethods.GetCursorPos(out var point))
        {
            x = point.X;
            y = point.Y;
            return true;
        }

        x = 0;
        y = 0;
        return false;
    }

    private static class NativeMethods
    {
        [System.Runtime.InteropServices.StructLayout(System.Runtime.InteropServices.LayoutKind.Sequential)]
        public struct POINT
        {
            public int X;
            public int Y;
        }

        [System.Runtime.InteropServices.DllImport("user32.dll")]
        [return: System.Runtime.InteropServices.MarshalAs(System.Runtime.InteropServices.UnmanagedType.Bool)]
        public static extern bool GetCursorPos(out POINT lpPoint);
    }
    private void CheckRunTrigger()
    {
        if (_runElapsed < TimeSpan.FromMinutes(5))
        {
            return;
        }

        _runElapsed = TimeSpan.Zero;

        if (!CurrentSkin.Animations.ContainsKey("running"))
        {
            return;
        }

        if (CurrentState.Kind is PetStateKind.Falling
            or PetStateKind.Dragging
            or PetStateKind.Listening
            or PetStateKind.Jumping
            or PetStateKind.Playful
            or PetStateKind.Run
            or PetStateKind.Attack)
        {
            return;
        }

        var chance = _random.NextDouble() * (0.05 - 0.01) + 0.01;
        if (_random.NextDouble() < chance)
        {
            TransitionTo(new RunState(this));
        }
    }

    private void CheckPlayfulTrigger()
    {
        if (_playfulElapsed < TimeSpan.FromMinutes(10))
        {
            return;
        }

        _playfulElapsed = TimeSpan.Zero;

        if (!Settings.RandomBehaviorEnabled)
        {
            return;
        }

        if (CurrentState.Kind is PetStateKind.Playful or PetStateKind.Jumping or PetStateKind.Falling or PetStateKind.Dragging or PetStateKind.Listening or PetStateKind.Landing)
        {
            return;
        }

        if (_random.NextDouble() < Settings.PlayfulBehaviorProbability)
        {
            TransitionTo(new PlayfulState(this));
        }
    }

    private void ProcessListeningTimers(TimeSpan delta)
    {
        if (_listeningEntryCountdown.HasValue)
        {
            if (IsListeningBlocked())
            {
                _listeningEntryCountdown = null;
            }
            else
            {
                var remaining = _listeningEntryCountdown.Value - delta;
                if (remaining <= TimeSpan.Zero)
                {
                    _listeningEntryCountdown = null;
                    if (!IsListening)
                    {
                        TransitionTo(new ListeningState(this));
                    }
                }
                else
                {
                    _listeningEntryCountdown = remaining;
                }
            }
        }

        if (_listeningExitCountdown.HasValue)
        {
            if (!IsListening || CurrentState.Kind != PetStateKind.Listening)
            {
                _listeningExitCountdown = null;
            }
            else
            {
                var remaining = _listeningExitCountdown.Value - delta;
                if (remaining <= TimeSpan.Zero)
                {
                    _listeningExitCountdown = null;
                    if (IsListening)
                    {
                        TransitionTo(new WalkingState(this));
                    }
                }
                else
                {
                    _listeningExitCountdown = remaining;
                }
            }
        }
    }

    private bool IsListeningBlocked() =>
        CurrentState.Kind == PetStateKind.Playful ||
        CurrentState.Kind == PetStateKind.Jumping ||
        CurrentState.Kind == PetStateKind.SleepApproach ||
        CurrentState.Kind == PetStateKind.Landing;

    private async Task PlayRandomSoundAsync()
    {
        var availableClips = CurrentSkin.SoundFiles.Where(File.Exists).ToArray();
        if (availableClips.Length == 0)
        {
            return;
        }

        var clip = availableClips[_random.Next(availableClips.Length)];
        _audioService.Volume = Settings.SoundVolume;
        await _audioService.PlayAsync(clip);
    }

    public async Task<bool> PlayTestSoundAsync(CancellationToken cancellationToken = default)
    {
        var clip = CurrentSkin.SoundFiles.FirstOrDefault(File.Exists);
        if (clip == null)
        {
            return false;
        }

        _audioService.Enabled = true;
        _audioService.Volume = Settings.SoundVolume;
        await _audioService.PlayAsync(clip, cancellationToken);
        return true;
    }

    public bool SpendEnergy(int amount)
    {
        if (amount <= 0)
        {
            return true;
        }

        Energy = Math.Max(0, Energy - amount);
        if (Energy <= 0 &&
            CurrentState.Kind != PetStateKind.Sleeping &&
            CurrentState.Kind != PetStateKind.Dragging)
        {
            TransitionTo(new SleepingState(this));
            return false;
        }

        return true;
    }

    public void RecoverEnergy(double amount)
    {
        if (amount <= 0)
        {
            return;
        }

        Energy = Math.Min(1000, Energy + (int)Math.Round(amount));
    }

    public void ForceState(PetStateKind kind)
    {
        var state = CreateState(kind);
        if (state.Kind != PetStateKind.None)
        {
            TransitionTo(state);
        }
    }

    private void RecreateCurrentState()
    {
        var recreated = CreateState(CurrentState.Kind);
        if (recreated.Kind != PetStateKind.None)
        {
            TransitionTo(recreated);
        }
    }

    private IPetState CreateState(PetStateKind kind) =>
        kind switch
        {
            PetStateKind.Idle => new IdleState(this),
            PetStateKind.Walking => new WalkingState(this),
            PetStateKind.Run => new RunState(this),
            PetStateKind.Jumping => new JumpingState(this),
            PetStateKind.Falling => new FallingState(this),
            PetStateKind.Landing => new LandingState(this),
            PetStateKind.Dragging => new DraggingState(this),
            PetStateKind.Playful => new PlayfulState(this),
            PetStateKind.Attack => new AttackState(this, new WalkingState(this)),
            PetStateKind.Listening => new ListeningState(this),
            PetStateKind.SleepApproach => new SleepApproachState(this),
            PetStateKind.Sleeping => new SleepingState(this),
            PetStateKind.Crouching => new CrouchingState(this),
            PetStateKind.CursorHunt => new CursorHuntState(this),
            PetStateKind.Wallgrab => new WallgrabState(this),
            _ => new NoOpState()
        };

    private static string NormalizeVersion(string? version)
    {
        if (string.IsNullOrWhiteSpace(version))
        {
            return string.Empty;
        }

        var normalized = version.Trim();
        return normalized.StartsWith('v') || normalized.StartsWith('V')
            ? normalized[1..]
            : normalized;
    }
}
