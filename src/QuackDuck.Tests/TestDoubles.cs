using QuackDuck.Application;
using QuackDuck.Application.Abstractions;
using QuackDuck.Domain.Skins;
using QuackDuck.Domain.Pets;

namespace QuackDuck.Tests;

internal sealed class InMemorySettingsStore : ISettingsStore
{
    private PetSettings _settings;

    public InMemorySettingsStore(PetSettings settings)
    {
        _settings = settings;
    }

    public PetSettings SavedSettings => _settings;

    public Task<PetSettings> LoadAsync(CancellationToken cancellationToken = default) =>
        Task.FromResult(_settings);

    public Task SaveAsync(PetSettings settings, CancellationToken cancellationToken = default)
    {
        _settings = settings;
        return Task.CompletedTask;
    }
}

internal sealed class FakeSkinService : ISkinService
{
    private readonly SkinDefinition _skin;

    public FakeSkinService(SkinDefinition skin)
    {
        _skin = skin;
    }

    public SkinDefinition DefaultSkin => _skin;

    public Task<SkinDefinition> LoadSkinAsync(string? skinPath, CancellationToken cancellationToken = default) =>
        Task.FromResult(_skin);

    public Task<IReadOnlyList<SkinDefinition>> DiscoverAsync(string? rootFolder, CancellationToken cancellationToken = default) =>
        Task.FromResult<IReadOnlyList<SkinDefinition>>(new[] { _skin });
}

internal sealed class FakeAudioService : IAudioService
{
    public bool Enabled { get; set; }
    public double Volume { get; set; }
    public List<string> PlayedFiles { get; } = new();

    public Task PlayAsync(string filePath, CancellationToken cancellationToken = default)
    {
        PlayedFiles.Add(filePath);
        return Task.CompletedTask;
    }
    public Task StopAsync(CancellationToken cancellationToken = default) => Task.CompletedTask;
}

internal sealed class FakeMicrophoneMonitor : IMicrophoneMonitor
{
    public event Action<int>? VolumeChanged;

    public Task StartAsync(CancellationToken cancellationToken = default) => Task.CompletedTask;
    public Task StopAsync(CancellationToken cancellationToken = default) => Task.CompletedTask;
    public ValueTask DisposeAsync() => ValueTask.CompletedTask;

    public void Emit(int level) => VolumeChanged?.Invoke(level);
}

internal sealed class FakeLocalizationService : ILocalizationService
{
    public string CurrentLanguage { get; private set; } = "en";

    public Task<IDictionary<string, string>> LoadAsync(string languageCode, CancellationToken cancellationToken = default)
    {
        CurrentLanguage = languageCode;
        return Task.FromResult<IDictionary<string, string>>(new Dictionary<string, string>());
    }

    public string Translate(string key, string fallback = "") => fallback;
}

internal sealed class FakeUpdateService : IUpdateService
{
    public UpdateInfo? Update { get; set; }

    public Task<UpdateInfo?> CheckForUpdatesAsync(CancellationToken cancellationToken = default) =>
        Task.FromResult(Update);

    public Task<bool> DownloadAndApplyAsync(UpdateInfo info, IProgress<int>? progress = null, CancellationToken cancellationToken = default) =>
        Task.FromResult(false);
}

internal sealed class FakeAutostartService : IAutostartService
{
    public bool Enabled { get; private set; }

    public Task<bool> IsEnabledAsync(CancellationToken cancellationToken = default) =>
        Task.FromResult(Enabled);

    public Task SetAsync(bool enabled, CancellationToken cancellationToken = default)
    {
        Enabled = enabled;
        return Task.CompletedTask;
    }
}

internal sealed class FakePathProvider : IAppPathProvider
{
    public FakePathProvider(string root)
    {
        AssetsRoot = Path.Combine(root, "assets");
        LanguagesRoot = Path.Combine(root, "languages");
        DataRoot = Path.Combine(root, "data");
        TempRoot = Path.Combine(root, "temp");
    }

    public string AssetsRoot { get; }
    public string LanguagesRoot { get; }
    public string DataRoot { get; }
    public string TempRoot { get; }
}

internal sealed class PetEngineFixture
{
    public PetEngineFixture(PetEngine engine, InMemorySettingsStore settingsStore, FakeAudioService audioService)
    {
        Engine = engine;
        SettingsStore = settingsStore;
        AudioService = audioService;
    }

    public PetEngine Engine { get; }
    public InMemorySettingsStore SettingsStore { get; }
    public FakeAudioService AudioService { get; }
}

internal static class TestPetEngineFactory
{
    public static async Task<PetEngineFixture> CreateStartedAsync(PetSettings? settings = null, SkinDefinition? skin = null)
    {
        var store = new InMemorySettingsStore(settings ?? PetSettings.Default);
        var audioService = new FakeAudioService();
        var engine = new PetEngine(
            store,
            new FakeSkinService(skin ?? CreateSkin()),
            audioService,
            new FakeMicrophoneMonitor(),
            new FakeLocalizationService(),
            new FakeUpdateService(),
            new FakeAutostartService());

        engine.SetViewport(800, 600);
        await engine.StartAsync();
        return new PetEngineFixture(engine, store, audioService);
    }

    public static SkinDefinition CreateSkin(bool includeMotionAnimations = true, IEnumerable<string>? soundFiles = null)
    {
        var animations = new Dictionary<string, AnimationSequence>
        {
            ["idle"] = new("idle", new[] { new FrameCoordinate(0, 0), new FrameCoordinate(0, 1) })
        };

        if (includeMotionAnimations)
        {
            animations["walk"] = new("walk", new[] { new FrameCoordinate(1, 0), new FrameCoordinate(1, 1) });
            animations["jump"] = new("jump", new[] { new FrameCoordinate(2, 0), new FrameCoordinate(2, 1) });
            animations["fall"] = new("fall", new[] { new FrameCoordinate(3, 0), new FrameCoordinate(3, 1) });
            animations["land"] = new("land", new[] { new FrameCoordinate(4, 0), new FrameCoordinate(4, 1) });
            animations["sleep"] = new("sleep", new[] { new FrameCoordinate(5, 0), new FrameCoordinate(5, 1) });
        }

        return new SkinDefinition(
            "test",
            "spritesheet.png",
            frameWidth: 32,
            frameHeight: 32,
            animations,
            soundFiles: soundFiles ?? new[] { "test-quack.wav" },
            isDefault: true);
    }
}
