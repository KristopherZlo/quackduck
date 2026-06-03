using QuackDuck.Domain.Interactions;
using QuackDuck.Domain.Pets;

namespace QuackDuck.Application.States;

internal sealed class SleepApproachState : PetStateBase
{
    public SleepApproachState(PetEngine engine) : base(engine)
    {
    }

    public override PetStateKind Kind => PetStateKind.SleepApproach;

    public override void Enter()
    {
        CurrentAnimation = ResolveAnimation("walk", "idle");
        FrameIndex = 0;
        Engine.SetRandomDestination();
        Engine.SetFacing(Engine.Direction >= 0);
        Engine.RefreshPoseSize();
        PublishFrame();
    }

    protected override void UpdatePosition(TimeSpan delta)
    {
        if (Engine.DestinationX == null)
        {
            Engine.SetRandomDestination();
        }

        if (Engine.DestinationX is not double target)
        {
            Engine.TransitionTo(new SleepingState(Engine));
            return;
        }

        var factor = StepFactor(delta);
        var dx = target - Engine.Pose.X;
        var direction = Math.Sign(dx);
        var step = Engine.BaseSpeed * factor;

        if (Math.Abs(dx) <= step + 1)
        {
            Engine.SetPose(target, Engine.Pose.Y);
            Engine.ClearDestination();
            Engine.TransitionTo(new SleepingState(Engine));
            return;
        }

        FaceDirection(direction);
        MoveHorizontally(step * direction);
    }

    public override void HandlePointer(PointerInteraction interaction)
    {
        Engine.ClearDestination();
        Engine.RegisterInteraction();
        base.HandlePointer(interaction);
    }
}
