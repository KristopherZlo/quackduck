using QuackDuck.Domain.Pets;
using QuackDuck.Domain.States;

namespace QuackDuck.Application.States;

internal sealed class LandingState : PetStateBase
{
    private readonly IPetState _nextState;

    public LandingState(PetEngine engine, IPetState? nextState = null) : base(engine)
    {
        _nextState = nextState ?? new WalkingState(engine);
    }

    public override PetStateKind Kind => PetStateKind.Landing;

    public override void Enter()
    {
        CurrentAnimation = ResolveAnimation("land", "idle");
        FrameIndex = 0;
        Engine.RefreshPoseSize();
        PublishFrame();
    }

    protected override void UpdatePosition(TimeSpan delta)
    {
        // Landing animation plays in place.
    }

    protected override void AdvanceAnimation()
    {
        var frameCount = GetFrameCount(CurrentAnimation);
        if (frameCount == 0)
        {
            Engine.TransitionTo(_nextState);
            return;
        }

        if (FrameIndex < frameCount - 1)
        {
            FrameIndex++;
            PublishFrame();
        }
        else
        {
            Engine.TransitionTo(_nextState);
        }
    }
}
