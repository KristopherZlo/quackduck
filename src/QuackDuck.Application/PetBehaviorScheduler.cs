using QuackDuck.Domain.Pets;

namespace QuackDuck.Application;

/// <summary>
/// Centralizes timing for idle/direction changes, random behaviors, ambient sounds, and hunts.
/// Keeps PetEngine slimmer and makes the cadence configurable via settings.
/// </summary>
internal sealed class PetBehaviorScheduler
{
    private readonly Random _random;
    private PetSettings _settings;

    private TimeSpan _sinceLastInteraction = TimeSpan.Zero;
    private TimeSpan _directionElapsed = TimeSpan.Zero;
    private TimeSpan _randomElapsed = TimeSpan.Zero;
    private TimeSpan _soundElapsed = TimeSpan.Zero;
    private TimeSpan _huntElapsed = TimeSpan.Zero;
    private TimeSpan _nextRandomInterval = TimeSpan.FromSeconds(30);
    private TimeSpan _nextSoundInterval = TimeSpan.FromMinutes(3);
    private TimeSpan _nextHuntInterval = TimeSpan.FromMinutes(5);

    public PetBehaviorScheduler(Random random, PetSettings settings)
    {
        _random = random ?? throw new ArgumentNullException(nameof(random));
        _settings = settings;
        ResetFromSettings(settings);
    }

    public void ResetFromSettings(PetSettings settings)
    {
        _settings = settings;
        _sinceLastInteraction = TimeSpan.Zero;
        _directionElapsed = TimeSpan.Zero;
        _randomElapsed = TimeSpan.Zero;
        _soundElapsed = TimeSpan.Zero;
        _huntElapsed = TimeSpan.Zero;

        _nextRandomInterval = NextRandomInterval();
        _nextSoundInterval = NextSoundInterval();
        _nextHuntInterval = TimeSpan.FromMinutes(5);
    }

    public void Advance(TimeSpan delta)
    {
        _sinceLastInteraction += delta;
        _directionElapsed += delta;
        _randomElapsed += delta;
        _soundElapsed += delta;
        _huntElapsed += delta;
    }

    public void RegisterInteraction() => _sinceLastInteraction = TimeSpan.Zero;

    public BehaviorTriggers Evaluate(PetStateKind currentState, bool isListening)
    {
        var shouldSleep = ShouldSleep(currentState);
        var shouldChangeDirection = ShouldChangeDirection(currentState);
        var shouldRandomBehavior = ShouldTriggerRandomBehavior(currentState);
        var shouldSound = ShouldPlayAmbientSound(isListening);
        var shouldHunt = ShouldHuntCursor(currentState);

        return new BehaviorTriggers(
            shouldSleep,
            shouldChangeDirection,
            shouldRandomBehavior,
            shouldSound,
            shouldHunt);
    }

    private bool ShouldSleep(PetStateKind currentState)
    {
        var timeout = TimeSpan.FromSeconds(Math.Max(5, _settings.SleepTimeoutSeconds));
        if (_sinceLastInteraction >= timeout &&
            currentState is not (PetStateKind.SleepApproach or PetStateKind.Sleeping or PetStateKind.Dragging or PetStateKind.Falling or PetStateKind.Jumping))
        {
            _sinceLastInteraction = TimeSpan.Zero;
            return true;
        }

        return false;
    }

    private bool ShouldChangeDirection(PetStateKind currentState)
    {
        if (currentState is not (PetStateKind.Walking or PetStateKind.Idle))
        {
            return false;
        }

        var interval = TimeSpan.FromSeconds(Math.Max(1, _settings.DirectionChangeIntervalSeconds));
        if (_directionElapsed >= interval)
        {
            _directionElapsed = TimeSpan.Zero;
            return true;
        }

        return false;
    }

    private bool ShouldTriggerRandomBehavior(PetStateKind currentState)
    {
        if (!_settings.RandomBehaviorEnabled ||
            currentState is not (PetStateKind.Walking or PetStateKind.Idle or PetStateKind.Run))
        {
            return false;
        }

        if (_randomElapsed >= _nextRandomInterval)
        {
            _randomElapsed = TimeSpan.Zero;
            _nextRandomInterval = NextRandomInterval();
            return true;
        }

        return false;
    }

    private bool ShouldPlayAmbientSound(bool isListening)
    {
        if (!_settings.SoundEnabled || isListening)
        {
            return false;
        }

        if (_soundElapsed >= _nextSoundInterval)
        {
            _soundElapsed = TimeSpan.Zero;
            _nextSoundInterval = NextSoundInterval();
            return true;
        }

        return false;
    }

    private bool ShouldHuntCursor(PetStateKind currentState)
    {
        if (currentState is PetStateKind.Sleeping or PetStateKind.Dragging)
        {
            return false;
        }

        if (_huntElapsed >= _nextHuntInterval)
        {
            _huntElapsed = TimeSpan.Zero;
            _nextHuntInterval = TimeSpan.FromMinutes(5);
            return _random.NextDouble() < 0.2;
        }

        return false;
    }

    private TimeSpan NextRandomInterval()
    {
        const int minMs = 20000;
        const int maxMs = 40000;
        return TimeSpan.FromMilliseconds(_random.Next(minMs, maxMs + 1));
    }

    private TimeSpan NextSoundInterval()
    {
        const int minSeconds = 120;
        const int maxSeconds = 600;
        return TimeSpan.FromSeconds(_random.Next(minSeconds, maxSeconds + 1));
    }
}

internal readonly record struct BehaviorTriggers(
    bool ShouldSleep,
    bool ShouldChangeDirection,
    bool ShouldTriggerRandomBehavior,
    bool ShouldPlayAmbientSound,
    bool ShouldHuntCursor);
