using QuackDuck.Domain.Skins;

namespace QuackDuck.Application.Abstractions;

public interface ISkinService
{
    SkinDefinition DefaultSkin { get; }

    Task<SkinDefinition> LoadSkinAsync(string? skinPath, CancellationToken cancellationToken = default);
    Task<IReadOnlyList<SkinDefinition>> DiscoverAsync(string? rootFolder, CancellationToken cancellationToken = default);
}
