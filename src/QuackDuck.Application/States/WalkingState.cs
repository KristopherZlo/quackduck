using QuackDuck.Domain.Pets;

namespace QuackDuck.Application.States;

internal sealed class WalkingState : PetStateBase
{
    private TimeSpan _timeInState = TimeSpan.Zero;
    private TimeSpan _walkDuration = TimeSpan.Zero;

    public WalkingState(PetEngine engine) : base(engine)
    {
    }

    public override PetStateKind Kind => PetStateKind.Walking;

    public override void Enter()
    {
        CurrentAnimation = ResolveAnimation("walk", "idle");
        FrameIndex = 0;
        _timeInState = TimeSpan.Zero;
        _walkDuration = TimeSpan.FromSeconds(Random.NextDouble() * 10 + 5); // 5-15s
        if (Engine.DestinationX == null)
        {
            Engine.SetRandomDestination();
        }
        Engine.SetFacing(Engine.Direction >= 0);
        Engine.RefreshPoseSize();
        PublishFrame();
    }

    protected override void UpdatePosition(TimeSpan delta)
    {
        if (Engine.IsListening)
        {
            return;
        }

        var factor = StepFactor(delta);
        if (Engine.DestinationX == null)
        {
            Engine.SetRandomDestination();
        }

        if (Engine.DestinationX is double target)
        {
            var dx = target - Engine.Pose.X;
            var direction = Math.Sign(dx);
            if (direction != 0)
            {
                Engine.Direction = direction;
                Engine.SetFacing(direction > 0);
                var step = Engine.BaseSpeed * factor * direction;
                MoveHorizontally(step);
            }

            var remaining = Math.Abs(target - Engine.Pose.X);
            if (remaining < Engine.BaseSpeed * factor + 1)
            {
                Engine.SpendEnergy(1);
                Engine.SetRandomDestination();
            }
        }
    }

    protected override void OnUpdate(TimeSpan delta)
    {
        _timeInState += delta;
        if (_timeInState >= _walkDuration && Engine.CurrentState.Kind == PetStateKind.Walking)
        {
            Engine.TransitionTo(new IdleState(Engine));
        }
    }
}
