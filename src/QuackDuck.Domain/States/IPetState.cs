using QuackDuck.Domain.Interactions;
using QuackDuck.Domain.Pets;

namespace QuackDuck.Domain.States;

public interface IPetState
{
    PetStateKind Kind { get; }

    void Enter();
    void Exit();
    void Update(TimeSpan delta);
    void HandlePointer(PointerInteraction interaction);
    void HandleMicLevel(int level);
}
