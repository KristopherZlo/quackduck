using System.IO;
using NAudio.Wave;
using QuackDuck.Application.Abstractions;

namespace QuackDuck.Infrastructure.Audio;

/// <summary>
/// Audio playback backed by NAudio with volume control and MP3/WAV support.
/// </summary>
public sealed class MediaAudioService : IAudioService
{
    private readonly object _sync = new();
    private IWavePlayer? _outputDevice;
    private AudioFileReader? _reader;
    private double _volume = 0.5;

    public bool Enabled { get; set; } = true;

    public double Volume
    {
        get => _volume;
        set
        {
            _volume = Math.Clamp(value, 0, 1);
            lock (_sync)
            {
                if (_reader != null)
                {
                    _reader.Volume = (float)_volume;
                }
            }
        }
    }

    public Task PlayAsync(string filePath, CancellationToken cancellationToken = default)
    {
        if (!Enabled)
        {
            return Task.CompletedTask;
        }

        if (string.IsNullOrWhiteSpace(filePath) || !File.Exists(filePath))
        {
            return Task.CompletedTask;
        }

        lock (_sync)
        {
            _outputDevice?.Stop();
            _outputDevice?.Dispose();
            _reader?.Dispose();

            _reader = new AudioFileReader(filePath)
            {
                Volume = (float)_volume
            };

            _outputDevice = new WaveOutEvent();
            _outputDevice.Init(_reader);
            _outputDevice.Play();
        }

        return Task.CompletedTask;
    }

    public Task StopAsync(CancellationToken cancellationToken = default)
    {
        lock (_sync)
        {
            _outputDevice?.Stop();
            _outputDevice?.Dispose();
            _reader?.Dispose();
            _outputDevice = null;
            _reader = null;
        }

        return Task.CompletedTask;
    }
}
