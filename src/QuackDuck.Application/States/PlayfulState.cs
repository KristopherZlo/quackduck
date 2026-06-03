using QuackDuck.Domain.Interactions;
using QuackDuck.Domain.Pets;

namespace QuackDuck.Application.States;

internal sealed class PlayfulState : PetStateBase
{
    private readonly TimeSpan _duration;
    private TimeSpan _elapsed = TimeSpan.Zero;
    private bool _hasJumped;

    public PlayfulState(PetEngine engine) : base(engine)
    {
        _duration = TimeSpan.FromSeconds(engine.Random.Next(20, 121));
    }

    public override PetStateKind Kind => PetStateKind.Playful;

    public override void Enter()
    {
        CurrentAnimation = ResolveAnimation("walk", "idle");
        FrameIndex = 0;
        _elapsed = TimeSpan.Zero;
        _hasJumped = false;
        Engine.IsPlayful = true;
        Engine.RefreshPoseSize();
        PublishFrame();
    }

    public override void Exit()
    {
        Engine.IsPlayful = false;
    }

    protected override void UpdatePosition(TimeSpan delta)
    {
        var factor = StepFactor(delta);
        var cursorX = Engine.LastPointerScreenX;
        if (cursorX <= 0)
        {
            // Fallback to walking behavior if cursor position is unknown.
            MoveHorizontally(Engine.BaseSpeed * factor * Engine.Direction);
            return;
        }

        var duckCenterX = Engine.Pose.X + Engine.ScaledWidth / 2;
        var desiredDirection = cursorX > duckCenterX ? 1 : (cursorX < duckCenterX ? -1 : Engine.Direction);
        FaceDirection(desiredDirection);

        var step = Engine.BaseSpeed * 2 * factor;
        MoveHorizontally(step * Engine.Direction);

        var distance = Math.Abs(cursorX - duckCenterX);
        if (distance < 50 && !_hasJumped)
        {
            _hasJumped = true;
            Engine.TransitionTo(new JumpingState(Engine, returnState: this));
        }
        else if (distance >= 100)
        {
            _hasJumped = false;
        }
    }

    protected override void OnUpdate(TimeSpan delta)
    {
        _elapsed += delta;
        if (_elapsed >= _duration && Engine.CurrentState.Kind == PetStateKind.Playful)
        {
            Engine.TransitionTo(new IdleState(Engine));
        }
    }

    public override void HandlePointer(PointerInteraction interaction)
    {
        Engine.RegisterInteraction();
        base.HandlePointer(interaction);
    }
}
