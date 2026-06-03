using QuackDuck.Domain.Pets;

namespace QuackDuck.Application.Abstractions;

public interface ISettingsStore
{
    Task<PetSettings> LoadAsync(CancellationToken cancellationToken = default);
    Task SaveAsync(PetSettings settings, CancellationToken cancellationToken = default);
}
