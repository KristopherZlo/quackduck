using QuackDuck.Domain.Pets;
using QuackDuck.Domain.States;

namespace QuackDuck.Application.States;

internal sealed class CursorHuntState : PetStateBase
{
    private readonly double _targetX;
    private readonly double _targetY;
    private readonly bool _run;

    public CursorHuntState(PetEngine engine) : base(engine)
    {
        // capture cursor position when entering hunt
        _targetX = engine.LastPointerScreenX > 0 ? engine.LastPointerScreenX : engine.ClampX(engine.Pose.X);
        _targetY = engine.LastPointerScreenY;
        _run = _targetY > 0 ? true : engine.Random.NextDouble() > 0.5;
    }

    public override PetStateKind Kind => PetStateKind.CursorHunt;

    public override void Enter()
    {
        CurrentAnimation = ResolveAnimation(_run ? "running" : "walk", "idle");
        FrameIndex = 0;
        Engine.SetDestination(_targetX);
        Engine.SetFacing(Engine.Direction >= 0);
        PublishFrame();
    }

    protected override void UpdatePosition(TimeSpan delta)
    {
        if (Engine.DestinationX == null)
        {
            Engine.SetDestination(_targetX);
        }

        var factor = StepFactor(delta);
        var speed = Engine.BaseSpeed * (_run ? 2 : 1.2) * factor;
        var dx = (_targetX - Engine.Pose.X);
        var dir = Math.Sign(dx);
        if (dir != 0)
        {
            Engine.Direction = dir;
            Engine.SetFacing(dir > 0);
            MoveHorizontally(speed * dir);
        }

        var distance = Math.Abs(_targetX - Engine.Pose.X);
        if (distance < Engine.BaseSpeed * 2 * factor + 2)
        {
            Engine.SpendEnergy(5);
            // pick finish action
            if (_targetY > 10 && distance < 300)
            {
                Engine.TransitionTo(new JumpingState(Engine, new AttackState(Engine, new WalkingState(Engine))));
            }
            else
            {
                Engine.TransitionTo(new AttackState(Engine, new WalkingState(Engine)));
            }
        }
    }

    protected override void OnUpdate(TimeSpan delta)
    {
        // no-op beyond movement
    }
}
