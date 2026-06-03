using QuackDuck.Application.Abstractions;

namespace QuackDuck.Infrastructure.Audio;

/// <summary>
/// Placeholder microphone monitor; emits nothing until a real backend is wired.
/// </summary>
public sealed class NullMicrophoneMonitor : IMicrophoneMonitor
{
    public event Action<int>? VolumeChanged
    {
        add { }
        remove { }
    }

    public Task StartAsync(CancellationToken cancellationToken = default) => Task.CompletedTask;

    public Task StopAsync(CancellationToken cancellationToken = default) => Task.CompletedTask;

    public ValueTask DisposeAsync() => ValueTask.CompletedTask;
}
