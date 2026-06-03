using QuackDuck.Domain.Pets;
using QuackDuck.Domain.States;

namespace QuackDuck.Application.States;

internal sealed class JumpingState : PetStateBase
{
    private readonly IPetState? _returnState;
    private double _verticalSpeed;
    private bool _isFalling;

    public JumpingState(PetEngine engine, IPetState? returnState = null) : base(engine)
    {
        _returnState = returnState;
        _verticalSpeed = -15 * 1.5;
        _isFalling = false;
    }

    public override PetStateKind Kind => PetStateKind.Jumping;

    public override void Enter()
    {
        CurrentAnimation = ResolveAnimation("jump", "idle");
        FrameIndex = 0;
        _isFalling = false;
        Engine.SpendEnergy(2);
        Engine.SetFacing(Engine.Direction >= 0);
        Engine.RefreshPoseSize();
        PublishFrame();
    }

    protected override void UpdatePosition(TimeSpan delta)
    {
        var factor = StepFactor(delta);
        _verticalSpeed += Engine.Gravity * factor;
        var newY = Engine.Pose.Y + _verticalSpeed * factor;
        Engine.SetPose(Engine.Pose.X, newY);

        if (!_isFalling && _verticalSpeed >= 0)
        {
            _isFalling = true;
            CurrentAnimation = ResolveAnimation("fall", "jump", "idle");
            FrameIndex = 0;
        }

        if (Engine.Pose.Y + Engine.ScaledHeight >= Engine.GroundLevel)
        {
            Engine.SetPose(Engine.Pose.X, Engine.GroundLevel - Engine.ScaledHeight);
            _verticalSpeed = 0;
            Engine.TransitionTo(new LandingState(Engine, _returnState));
        }
    }
}
