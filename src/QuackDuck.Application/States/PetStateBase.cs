using QuackDuck.Domain.Interactions;
using QuackDuck.Domain.Pets;
using QuackDuck.Domain.Skins;
using QuackDuck.Domain.States;
using QuackDuck.Application.Rendering;

namespace QuackDuck.Application.States;

/// <summary>
/// Shared helpers for concrete pet states: animation ticking, frame publishing, and pointer defaults.
/// </summary>
internal abstract class PetStateBase : IPetState
{
    protected readonly PetEngine Engine;
    private TimeSpan _animationElapsed = TimeSpan.Zero;
    private TimeSpan _movementElapsed = TimeSpan.Zero;

    protected int FrameIndex;
    protected string CurrentAnimation = "idle";

    protected virtual TimeSpan AnimationInterval => TimeSpan.FromMilliseconds(140);
    protected virtual TimeSpan MovementInterval => TimeSpan.FromMilliseconds(20);  // ~50 FPS for window/physics

    protected PetStateBase(PetEngine engine)
    {
        Engine = engine;
    }

    protected PetSettings Settings => Engine.Settings;
    protected SkinDefinition Skin => Engine.CurrentSkin;
    protected Random Random => Engine.Random;

    public abstract PetStateKind Kind { get; }

    public virtual void Enter()
    {
        _animationElapsed = TimeSpan.Zero;
        _movementElapsed = TimeSpan.Zero;
        FrameIndex = 0;
        Engine.RefreshPoseSize();
        PublishFrame();
    }

    public virtual void Exit() { }

    public void Update(TimeSpan delta)
    {
        _animationElapsed += delta;
        while (_animationElapsed >= AnimationInterval)
        {
            _animationElapsed -= AnimationInterval;
            AdvanceAnimation();
        }

        var moved = false;
        _movementElapsed += delta;
        while (_movementElapsed >= MovementInterval)
        {
            _movementElapsed -= MovementInterval;
            UpdatePosition(MovementInterval);
            moved = true;
        }

        if (moved)
        {
            PublishFrame();
        }

        OnUpdate(delta);
    }

    public virtual void HandlePointer(PointerInteraction interaction)
    {
        if (interaction.Kind == PointerInteractionKind.Down && interaction.Button == PointerButton.Left)
        {
            Engine.RegisterInteraction();
            Engine.TransitionTo(new DraggingState(Engine, interaction));
        }
        else if (interaction.Kind == PointerInteractionKind.Down && interaction.Button == PointerButton.Right)
        {
            Engine.RegisterInteraction();
            Engine.TransitionTo(new JumpingState(Engine, returnState: this));
        }
    }

    public virtual void HandleMicLevel(int level) { }

    protected abstract void UpdatePosition(TimeSpan delta);

    protected virtual void OnUpdate(TimeSpan delta) { }

    protected virtual void AdvanceAnimation()
    {
        var frameCount = GetFrameCount(CurrentAnimation);
        if (frameCount > 0)
        {
            FrameIndex = (FrameIndex + 1) % frameCount;
        }
        PublishFrame();
    }

    protected int GetFrameCount(string animationName)
    {
        if (Skin.Animations.TryGetValue(animationName, out var sequence) && sequence.Frames.Count > 0)
        {
            return sequence.Frames.Count;
        }

        if (Skin.Animations.TryGetValue("idle", out var idle) && idle.Frames.Count > 0)
        {
            return idle.Frames.Count;
        }

        return 0;
    }

    protected string ResolveAnimation(string preferred, params string[] fallbacks)
    {
        if (Skin.Animations.TryGetValue(preferred, out var seq) && seq.Frames.Count > 0)
        {
            return preferred;
        }

        foreach (var candidate in fallbacks)
        {
            if (Skin.Animations.TryGetValue(candidate, out var fallbackSeq) && fallbackSeq.Frames.Count > 0)
            {
                return candidate;
            }
        }

        return "idle";
    }

    protected void PublishFrame()
    {
        Engine.PublishFrame(new PetFrameUpdate(
            Skin.Id,
            CurrentAnimation,
            FrameIndex,
            Engine.Pose with { Width = Engine.ScaledWidth, Height = Engine.ScaledHeight },
            FlipX: !Engine.Pose.FacingRight));
    }

    protected void FaceDirection(int direction)
    {
        Engine.Direction = Math.Sign(direction) == 0 ? Engine.Direction : Math.Sign(direction);
        Engine.SetFacing(Engine.Direction >= 0);
    }

    /// <summary>
    /// Normalizes delta to the 20ms baseline used by the Python version for movement/physics.
    /// </summary>
    protected double StepFactor(TimeSpan delta)
    {
        var factor = delta.TotalMilliseconds / 20.0;
        return double.IsFinite(factor) && factor > 0 ? factor : 0.001;
    }

    protected void MoveHorizontally(double deltaPixels)
    {
        var targetX = Engine.ClampX(Engine.Pose.X + deltaPixels);
        Engine.SetPose(targetX, Engine.Pose.Y);
    }

    protected void MoveVertically(double deltaPixels)
    {
        var targetY = Engine.ClampY(Engine.Pose.Y + deltaPixels);
        Engine.SetPose(Engine.Pose.X, targetY);
    }
}
