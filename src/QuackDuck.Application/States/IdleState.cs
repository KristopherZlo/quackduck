using System.Linq;
using QuackDuck.Domain.Interactions;
using QuackDuck.Domain.Pets;

namespace QuackDuck.Application.States;

internal sealed class IdleState : PetStateBase
{
    private TimeSpan _timeInState = TimeSpan.Zero;

    public IdleState(PetEngine engine) : base(engine)
    {
    }

    public override PetStateKind Kind => PetStateKind.Idle;

    public override void Enter()
    {
        CurrentAnimation = PickIdleAnimation();
        FrameIndex = 0;
        _timeInState = TimeSpan.Zero;
        Engine.SetFacing(Engine.Direction >= 0);
        Engine.RefreshPoseSize();
        PublishFrame();
    }

    protected override void UpdatePosition(TimeSpan delta)
    {
        // Idle does not move.
    }

    protected override void OnUpdate(TimeSpan delta)
    {
        _timeInState += delta;
        if (_timeInState >= TimeSpan.FromSeconds(Settings.IdleDurationSeconds) &&
            Engine.CurrentState.Kind == PetStateKind.Idle)
        {
            Engine.TransitionTo(new WalkingState(Engine));
        }
    }

    private string PickIdleAnimation()
    {
        var idleAnimations = Skin.Animations
            .Where(pair => pair.Key.StartsWith("idle", StringComparison.OrdinalIgnoreCase) && pair.Value.Frames.Count > 0)
            .Select(pair => pair.Key)
            .ToList();

        if (idleAnimations.Count == 0)
        {
            idleAnimations.Add("idle");
        }

        var index = Random.Next(idleAnimations.Count);
        return idleAnimations[index];
    }

    public override void HandlePointer(PointerInteraction interaction)
    {
        Engine.RegisterInteraction();
        base.HandlePointer(interaction);
    }

    public override void HandleMicLevel(int level)
    {
        if (level > Settings.ActivationThreshold)
        {
            Engine.RegisterInteraction();
            Engine.TransitionTo(new ListeningState(Engine));
        }
    }
}
