using System.Xml.Linq;

namespace QuackDuck.Tests;

public sealed class PresentationManifestTests
{
    [Fact]
    public void AppManifest_DoesNotRequireAdministratorForNormalRun()
    {
        var manifestPath = Path.Combine(FindRepositoryRoot(), "app.manifest");
        var document = XDocument.Load(manifestPath);
        XNamespace manifestV3 = "urn:schemas-microsoft-com:asm.v3";

        var level = document
            .Descendants(manifestV3 + "requestedExecutionLevel")
            .Single()
            .Attribute("level")
            ?.Value;

        Assert.Equal("asInvoker", level);
    }

    private static string FindRepositoryRoot()
    {
        var directory = new DirectoryInfo(Directory.GetCurrentDirectory());
        while (directory != null)
        {
            if (File.Exists(Path.Combine(directory.FullName, "QuackDuck.sln")))
            {
                return directory.FullName;
            }

            directory = directory.Parent;
        }

        throw new DirectoryNotFoundException("Could not find QuackDuck.sln.");
    }
}
