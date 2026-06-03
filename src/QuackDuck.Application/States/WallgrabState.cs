using QuackDuck.Domain.Pets;

namespace QuackDuck.Application.States;

internal sealed class WallgrabState : PetStateBase
{
    private TimeSpan _elapsed;
    private readonly TimeSpan _hold = TimeSpan.FromMilliseconds(800);

    public WallgrabState(PetEngine engine) : base(engine)
    {
    }

    public override PetStateKind Kind => PetStateKind.Wallgrab;

    public override void Enter()
    {
        CurrentAnimation = ResolveAnimation("wallgrab", "idle");
        Engine.SpendEnergy(2);
        _elapsed = TimeSpan.Zero;
        PublishFrame();
    }

    protected override void UpdatePosition(TimeSpan delta)
    {
        // stick to wall
    }

    protected override void OnUpdate(TimeSpan delta)
    {
        _elapsed += delta;
        if (_elapsed >= _hold)
        {
            Engine.TransitionTo(new FallingState(Engine, playAnimation: false, returnState: new LandingState(Engine, new IdleState(Engine))));
        }
    }
}
