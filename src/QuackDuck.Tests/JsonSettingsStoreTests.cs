using QuackDuck.Domain.Pets;
using QuackDuck.Infrastructure.Settings;

namespace QuackDuck.Tests;

public sealed class JsonSettingsStoreTests
{
    [Fact]
    public async Task SaveAndLoad_RoundTripsEveryPetSettingsPropertyUsedByMenu()
    {
        var root = Path.Combine(Path.GetTempPath(), "quackduck-tests", Guid.NewGuid().ToString("N"));
        var store = new JsonSettingsStore(new FakePathProvider(root));
        var settings = new PetSettings
        {
            PetName = "Quacky",
            ShowName = true,
            NameOffsetY = 88,
            FontBaseSize = 21,
            SelectedMicIndex = 2,
            ActivationThreshold = 42,
            SoundResponseProbability = 0.37,
            SoundEnabled = false,
            SoundVolume = 0.77,
            AutostartEnabled = true,
            GroundLevelOffset = 24,
            PetSize = 5,
            SkinFolder = @"C:\skins",
            SelectedSkin = @"C:\skins\skin.zip",
            DuckSpeed = 3.5,
            RandomBehaviorEnabled = false,
            IdleDurationSeconds = 12,
            SleepTimeoutSeconds = 234,
            DirectionChangeIntervalSeconds = 45,
            PlayfulBehaviorProbability = 0.66,
            CurrentLanguage = "ru",
            SkippedVersion = "1.5.3"
        };

        await store.SaveAsync(settings);
        var loaded = await store.LoadAsync();

        foreach (var property in typeof(PetSettings).GetProperties())
        {
            Assert.Equal(property.GetValue(settings), property.GetValue(loaded));
        }
    }
}
