using QuackDuck.Domain.Interactions;
using QuackDuck.Domain.Pets;

namespace QuackDuck.Application.States;

internal sealed class DraggingState : PetStateBase
{
    private double _offsetX;
    private double _offsetY;

    public DraggingState(PetEngine engine, PointerInteraction? initialInteraction = null) : base(engine)
    {
        if (initialInteraction.HasValue)
        {
            _offsetX = initialInteraction.Value.X;
            _offsetY = initialInteraction.Value.Y;
        }
    }

    public override PetStateKind Kind => PetStateKind.Dragging;

    public override void Enter()
    {
        CurrentAnimation = ResolveAnimation("fall", "idle");
        FrameIndex = 0;
        Engine.RefreshPoseSize();
        PublishFrame();
    }

    protected override void UpdatePosition(TimeSpan delta)
    {
        // Movement is driven directly by pointer events.
    }

    public override void HandlePointer(PointerInteraction interaction)
    {
        Engine.RegisterInteraction();

        switch (interaction.Kind)
        {
            case PointerInteractionKind.Down:
                _offsetX = interaction.X;
                _offsetY = interaction.Y;
                break;
            case PointerInteractionKind.Move:
                var targetX = (interaction.ScreenX > 0 ? interaction.ScreenX : interaction.X) - _offsetX;
                var targetY = (interaction.ScreenY > 0 ? interaction.ScreenY : interaction.Y) - _offsetY;
                Engine.SetPose(Engine.ClampX(targetX), Engine.ClampY(targetY));
                PublishFrame();
                break;
            case PointerInteractionKind.Up:
                Engine.TransitionTo(new FallingState(Engine, playAnimation: false, returnState: new WalkingState(Engine)));
                break;
        }
    }
}
