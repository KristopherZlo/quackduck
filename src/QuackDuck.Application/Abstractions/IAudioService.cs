namespace QuackDuck.Application.Abstractions;

public interface IAudioService
{
    bool Enabled { get; set; }
    double Volume { get; set; }

    Task PlayAsync(string filePath, CancellationToken cancellationToken = default);
    Task StopAsync(CancellationToken cancellationToken = default);
}
