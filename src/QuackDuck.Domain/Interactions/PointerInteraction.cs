namespace QuackDuck.Domain.Interactions;

public enum PointerInteractionKind
{
    Down,
    Up,
    Move,
    DoubleClick
}

public enum PointerButton
{
    None,
    Left,
    Right,
    Middle
}

public readonly record struct PointerInteraction(
    PointerInteractionKind Kind,
    double X,
    double Y,
    PointerButton Button = PointerButton.None,
    double ScreenX = 0,
    double ScreenY = 0);
