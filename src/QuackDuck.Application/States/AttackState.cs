using QuackDuck.Domain.Interactions;
using QuackDuck.Domain.Pets;
using QuackDuck.Domain.States;

namespace QuackDuck.Application.States;

internal sealed class AttackState : PetStateBase
{
    private readonly IPetState? _returnState;

    public AttackState(PetEngine engine, IPetState? returnState = null) : base(engine)
    {
        _returnState = returnState;
    }

    public override PetStateKind Kind => PetStateKind.Attack;

    public override void Enter()
    {
        CurrentAnimation = ResolveAnimation("attack", "idle");
        FrameIndex = 0;
        Engine.SpendEnergy(1);
        Engine.RefreshPoseSize();
        PublishFrame();
    }

    protected override void UpdatePosition(TimeSpan delta)
    {
        // Attack animation is stationary.
    }

    protected override void AdvanceAnimation()
    {
        var frameCount = GetFrameCount(CurrentAnimation);
        if (frameCount == 0)
        {
            Engine.TransitionTo(_returnState ?? new WalkingState(Engine));
            return;
        }

        if (FrameIndex < frameCount - 1)
        {
            FrameIndex++;
            PublishFrame();
        }
        else
        {
            Engine.TransitionTo(_returnState ?? new WalkingState(Engine));
        }
    }

    public override void HandlePointer(PointerInteraction interaction)
    {
        Engine.RegisterInteraction();
        base.HandlePointer(interaction);
    }
}
