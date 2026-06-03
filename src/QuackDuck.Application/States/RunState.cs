using QuackDuck.Domain.Pets;

namespace QuackDuck.Application.States;

internal sealed class RunState : PetStateBase
{
    private TimeSpan _timeInState = TimeSpan.Zero;
    private TimeSpan _runDuration = TimeSpan.Zero;

    public RunState(PetEngine engine) : base(engine)
    {
    }

    public override PetStateKind Kind => PetStateKind.Run;

    public override void Enter()
    {
        CurrentAnimation = ResolveAnimation("running", "run", "walk", "idle");
        FrameIndex = 0;
        _timeInState = TimeSpan.Zero;
        _runDuration = TimeSpan.FromSeconds(Random.NextDouble() * 60 + 60); // 60-120s
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
                var step = Engine.BaseSpeed * 2 * factor * direction;
                MoveHorizontally(step);
            }

            var remaining = Math.Abs(target - Engine.Pose.X);
            if (remaining < Engine.BaseSpeed * 2 * factor + 1)
            {
                Engine.SpendEnergy(2);
                Engine.SetRandomDestination();
            }
        }
    }

    protected override void OnUpdate(TimeSpan delta)
    {
        _timeInState += delta;
        if (_timeInState >= _runDuration && Engine.CurrentState.Kind == PetStateKind.Run)
        {
            Engine.TransitionTo(new WalkingState(Engine));
        }
    }
}
