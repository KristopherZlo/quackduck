using QuackDuck.Domain.Pets;

namespace QuackDuck.Application.States;

internal sealed class CrouchingState : PetStateBase
{
    private TimeSpan _elapsed;
    private readonly TimeSpan _duration = TimeSpan.FromMilliseconds(600);

    public CrouchingState(PetEngine engine) : base(engine)
    {
    }

    public override PetStateKind Kind => PetStateKind.Crouching;

    public override void Enter()
    {
        CurrentAnimation = ResolveAnimation("crouch", "idle");
        Engine.SpendEnergy(1);
        _elapsed = TimeSpan.Zero;
        FrameIndex = 0;
        PublishFrame();
    }

    protected override void UpdatePosition(TimeSpan delta)
    {
        // crouch in place
    }

    protected override void OnUpdate(TimeSpan delta)
    {
        _elapsed += delta;
        if (_elapsed >= _duration)
        {
            Engine.TransitionTo(new IdleState(Engine));
        }
    }
}
