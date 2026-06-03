using QuackDuck.Domain.Interactions;
using QuackDuck.Domain.Pets;

namespace QuackDuck.Application.States;

internal sealed class SleepingState : PetStateBase
{
    private readonly TimeSpan _wakeAfter;
    private TimeSpan _elapsed = TimeSpan.Zero;

    public SleepingState(PetEngine engine) : base(engine)
    {
        _wakeAfter = TimeSpan.FromSeconds(engine.Random.Next(900, 3601)); // 15-60 minutes
    }

    public override PetStateKind Kind => PetStateKind.Sleeping;

    public override void Enter()
    {
        CurrentAnimation = ResolveAnimation("sleep", "idle");
        FrameIndex = 0;
        _elapsed = TimeSpan.Zero;
        Engine.RefreshPoseSize();
        PublishFrame();
    }

    protected override void UpdatePosition(TimeSpan delta)
    {
        // Sleep in place.
    }

    protected override void OnUpdate(TimeSpan delta)
    {
        Engine.RecoverEnergy(delta.TotalSeconds);
        _elapsed += delta;
        if ((Engine.Energy >= 250 && _elapsed >= TimeSpan.FromSeconds(5)) ||
            (_elapsed >= _wakeAfter && Engine.CurrentState.Kind == PetStateKind.Sleeping))
        {
            Engine.TransitionTo(new WalkingState(Engine));
        }
    }

    public override void HandlePointer(PointerInteraction interaction)
    {
        Engine.RegisterInteraction();
        if (interaction.Button == PointerButton.Left && interaction.Kind == PointerInteractionKind.Down)
        {
            Engine.TransitionTo(new DraggingState(Engine, interaction));
        }
        else
        {
            base.HandlePointer(interaction);
        }
    }

    public override void HandleMicLevel(int level)
    {
        if (level > Engine.Settings.ActivationThreshold && Engine.Energy >= 250)
        {
            Engine.TransitionTo(new WalkingState(Engine));
        }
    }
}
