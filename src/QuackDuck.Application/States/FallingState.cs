using QuackDuck.Domain.Pets;
using QuackDuck.Domain.States;

namespace QuackDuck.Application.States;

internal sealed class FallingState : PetStateBase
{
    private readonly bool _playAnimation;
    private readonly IPetState? _returnState;
    private double _verticalSpeed;

    public FallingState(PetEngine engine, bool playAnimation = true, IPetState? returnState = null)
        : base(engine)
    {
        _playAnimation = playAnimation;
        _returnState = returnState;
    }

    public override PetStateKind Kind => PetStateKind.Falling;

    public override void Enter()
    {
        CurrentAnimation = _playAnimation ? ResolveAnimation("fall", "idle") : CurrentAnimation;
        FrameIndex = 0;
        _verticalSpeed = 0;
        Engine.RefreshPoseSize();
        PublishFrame();
    }

    protected override void UpdatePosition(TimeSpan delta)
    {
        var factor = StepFactor(delta);
        _verticalSpeed += Engine.Gravity * factor;
        Engine.SetPose(Engine.Pose.X, Engine.Pose.Y + _verticalSpeed * factor);

        if (Engine.Pose.Y + Engine.ScaledHeight >= Engine.GroundLevel)
        {
            Engine.SetPose(Engine.Pose.X, Engine.GroundLevel - Engine.ScaledHeight);
            Engine.TransitionTo(new LandingState(Engine, _returnState));
        }
    }
}
