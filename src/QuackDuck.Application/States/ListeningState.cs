using QuackDuck.Domain.Pets;

namespace QuackDuck.Application.States;

internal sealed class ListeningState : PetStateBase
{
    public ListeningState(PetEngine engine) : base(engine)
    {
    }

    public override PetStateKind Kind => PetStateKind.Listening;

    public override void Enter()
    {
        Engine.MarkListening(true);
        CurrentAnimation = ResolveAnimation("listen", "idle");
        FrameIndex = 0;
        Engine.RefreshPoseSize();
        PublishFrame();
    }

    public override void Exit()
    {
        Engine.MarkListening(false);
    }

    protected override void UpdatePosition(TimeSpan delta)
    {
        // No movement while listening.
    }

    protected override void OnUpdate(TimeSpan delta)
    {
        // exit is handled by engine-level timers when mic quiets down
    }

    public override void HandleMicLevel(int level)
    {
        if (level > Settings.ActivationThreshold)
        {
            Engine.RegisterInteraction();
        }
    }
}
