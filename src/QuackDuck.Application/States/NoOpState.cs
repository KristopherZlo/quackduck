using QuackDuck.Domain.Interactions;
using QuackDuck.Domain.Pets;
using QuackDuck.Domain.States;

namespace QuackDuck.Application.States;

/// <summary>
/// Safe placeholder state used before the real state graph is wired.
/// </summary>
public sealed class NoOpState : IPetState
{
    public PetStateKind Kind => PetStateKind.None;

    public void Enter() { }
    public void Exit() { }
    public void Update(TimeSpan delta) { }
    public void HandlePointer(PointerInteraction interaction) { }
    public void HandleMicLevel(int level) { }
}
