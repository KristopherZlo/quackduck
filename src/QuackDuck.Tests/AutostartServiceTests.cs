using QuackDuck.Infrastructure.Paths;

namespace QuackDuck.Tests;

public sealed class AutostartServiceTests
{
    [Fact]
    public async Task SetAsync_WritesQuotedExecutablePath_AndIsEnabledComparesNormalizedPaths()
    {
        var runKey = new InMemoryRunKeyStore();
        var service = new RegistryAutostartService(
            "QuackDuck",
            @"C:\Program Files\QuackDuck\quackduck.exe",
            runKey);

        await service.SetAsync(true);

        Assert.Equal("\"C:\\Program Files\\QuackDuck\\quackduck.exe\"", runKey.Values["QuackDuck"]);
        Assert.True(await service.IsEnabledAsync());

        runKey.Values["QuackDuck"] = @"C:\Program Files\QuackDuck\quackduck.exe";

        Assert.True(await service.IsEnabledAsync());
    }

    [Fact]
    public async Task SetAsync_Disabled_RemovesRunValue()
    {
        var runKey = new InMemoryRunKeyStore();
        var service = new RegistryAutostartService("QuackDuck", @"C:\QuackDuck\quackduck.exe", runKey);

        await service.SetAsync(true);
        await service.SetAsync(false);

        Assert.False(runKey.Values.ContainsKey("QuackDuck"));
    }

    private sealed class InMemoryRunKeyStore : IRunKeyStore
    {
        public Dictionary<string, string> Values { get; } = new(StringComparer.OrdinalIgnoreCase);

        public string? GetValue(string name) => Values.TryGetValue(name, out var value) ? value : null;
        public void SetValue(string name, string value) => Values[name] = value;
        public void DeleteValue(string name) => Values.Remove(name);
    }
}
