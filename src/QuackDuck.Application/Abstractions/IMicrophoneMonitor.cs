namespace QuackDuck.Application.Abstractions;

public interface IMicrophoneMonitor : IAsyncDisposable
{
    event Action<int>? VolumeChanged;

    Task StartAsync(CancellationToken cancellationToken = default);
    Task StopAsync(CancellationToken cancellationToken = default);
}
