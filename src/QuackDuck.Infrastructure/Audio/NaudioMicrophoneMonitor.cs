using NAudio.Wave;
using QuackDuck.Application.Abstractions;

namespace QuackDuck.Infrastructure.Audio;

/// <summary>
/// Microphone monitor that reports RMS volume levels using NAudio.
/// </summary>
public sealed class NaudioMicrophoneMonitor : IMicrophoneMonitor
{
    private WaveInEvent? _waveIn;

    public event Action<int>? VolumeChanged;

    public Task StartAsync(CancellationToken cancellationToken = default)
    {
        if (_waveIn != null)
        {
            return Task.CompletedTask;
        }

        try
        {
            _waveIn = new WaveInEvent
            {
                BufferMilliseconds = 100,
                WaveFormat = new WaveFormat(44100, 1)
            };

            _waveIn.DataAvailable += OnDataAvailable;
            _waveIn.StartRecording();
        }
        catch
        {
            _waveIn?.Dispose();
            _waveIn = null;
        }

        return Task.CompletedTask;
    }

    public Task StopAsync(CancellationToken cancellationToken = default)
    {
        if (_waveIn != null)
        {
            _waveIn.DataAvailable -= OnDataAvailable;
            _waveIn.StopRecording();
            _waveIn.Dispose();
            _waveIn = null;
        }

        return Task.CompletedTask;
    }

    public ValueTask DisposeAsync() => new(StopAsync());

    private void OnDataAvailable(object? sender, WaveInEventArgs e)
    {
        if (e.BytesRecorded == 0)
        {
            return;
        }

        double sumSquares = 0;
        var sampleCount = e.BytesRecorded / 2; // 16-bit
        for (var index = 0; index < e.BytesRecorded; index += 2)
        {
            var sample = BitConverter.ToInt16(e.Buffer, index);
            sumSquares += sample * sample;
        }

        var rms = Math.Sqrt(sumSquares / sampleCount);
        var normalized = (int)Math.Min(100, rms / short.MaxValue * 100);

        VolumeChanged?.Invoke(normalized);
    }
}
