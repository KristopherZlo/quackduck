namespace QuackDuck.Application.Abstractions;

public interface IAutostartService
{
    Task<bool> IsEnabledAsync(CancellationToken cancellationToken = default);
    Task SetAsync(bool enabled, CancellationToken cancellationToken = default);
}
