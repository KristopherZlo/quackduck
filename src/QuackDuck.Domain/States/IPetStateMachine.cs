using QuackDuck.Domain.Interactions;

namespace QuackDuck.Domain.States;

public interface IPetStateMachine
{
    IPetState Current { get; }

    void ChangeState(IPetState nextState);
    void Update(TimeSpan delta);
    void HandlePointer(PointerInteraction interaction);
    void HandleMicLevel(int level);
}
