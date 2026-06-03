using System.Net;
using QuackDuck.Infrastructure.Updates;

namespace QuackDuck.Tests;

public sealed class GitHubUpdateServiceTests
{
    [Fact]
    public async Task CheckForUpdatesAsync_ReturnsLatestZipAsset_WhenVersionIsNewer()
    {
        var service = CreateService("""
            {
              "tag_name": "v1.5.3",
              "body": "Release notes",
              "html_url": "https://github.com/KristopherZlo/quackduck/releases/tag/v1.5.3",
              "assets": [
                { "name": "readme.txt", "browser_download_url": "https://example.test/readme.txt" },
                { "name": "quackduck-1.5.3.zip", "browser_download_url": "https://example.test/quackduck.zip" }
              ]
            }
            """);

        var update = await service.CheckForUpdatesAsync();

        Assert.NotNull(update);
        Assert.Equal("1.5.3", update.Version);
        Assert.Equal("Release notes", update.Notes);
        Assert.Equal("quackduck-1.5.3.zip", update.AssetName);
        Assert.Equal("https://example.test/quackduck.zip", update.DownloadUrl);
    }

    [Fact]
    public async Task CheckForUpdatesAsync_ReturnsNull_WhenReleaseVersionWasSkipped()
    {
        var service = CreateService("""
            {
              "tag_name": "v1.5.3",
              "body": "",
              "html_url": "https://example.test/release",
              "assets": [
                { "name": "quackduck.zip", "browser_download_url": "https://example.test/quackduck.zip" }
              ]
            }
            """, skippedVersion: "1.5.3");

        var update = await service.CheckForUpdatesAsync();

        Assert.Null(update);
    }

    [Theory]
    [InlineData(HttpStatusCode.NotFound, "{}", null)]
    [InlineData(HttpStatusCode.OK, "{\"tag_name\":\"v1.5.1\",\"assets\":[]}", null)]
    [InlineData(HttpStatusCode.OK, "{\"tag_name\":\"v1.5.3\",\"assets\":[{\"name\":\"quackduck.exe\",\"browser_download_url\":\"https://example.test/app.exe\"}]}", null)]
    public async Task CheckForUpdatesAsync_ReturnsNull_WhenNoInstallableReleaseExists(
        HttpStatusCode statusCode,
        string json,
        string? skippedVersion)
    {
        var service = CreateService(json, statusCode, skippedVersion);

        var update = await service.CheckForUpdatesAsync();

        Assert.Null(update);
    }

    private static GitHubUpdateService CreateService(
        string responseJson,
        HttpStatusCode statusCode = HttpStatusCode.OK,
        string? skippedVersion = null)
    {
        var httpClient = new HttpClient(new StaticJsonHandler(responseJson, statusCode));
        return new GitHubUpdateService(
            new GitHubUpdateOptions
            {
                Owner = "KristopherZlo",
                Repository = "quackduck",
                CurrentVersion = "1.5.2",
                SkippedVersion = skippedVersion ?? string.Empty,
                InstallEnabled = false
            },
            httpClient);
    }

    private sealed class StaticJsonHandler : HttpMessageHandler
    {
        private readonly string _json;
        private readonly HttpStatusCode _statusCode;

        public StaticJsonHandler(string json, HttpStatusCode statusCode)
        {
            _json = json;
            _statusCode = statusCode;
        }

        protected override Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken cancellationToken)
        {
            var response = new HttpResponseMessage(_statusCode)
            {
                Content = new StringContent(_json)
            };
            return Task.FromResult(response);
        }
    }
}
