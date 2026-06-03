using QuackDuck.Domain.Interactions;
using QuackDuck.Domain.States;

namespace QuackDuck.Application.StateMachine;

public class PetStateMachine : IPetStateMachine
{
    public IPetState Current { get; private set; }

    public event Action<IPetState>? StateChanged;

    public PetStateMachine(IPetState initialState)
    {
        Current = initialState ?? throw new ArgumentNullException(nameof(initialState));
        Current.Enter();
        StateChanged?.Invoke(Current);
    }

    public void ChangeState(IPetState nextState)
    {
        if (nextState == null) throw new ArgumentNullException(nameof(nextState));
        if (ReferenceEquals(Current, nextState))
        {
            return;
        }

        Current.Exit();
        Current = nextState;
        Current.Enter();
        StateChanged?.Invoke(Current);
    }

    public void Update(TimeSpan delta) => Current.Update(delta);

    public void HandlePointer(PointerInteraction interaction) => Current.HandlePointer(interaction);

    public void HandleMicLevel(int level) => Current.HandleMicLevel(level);
}
