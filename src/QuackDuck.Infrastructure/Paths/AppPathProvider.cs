using System.IO;
using QuackDuck.Application.Abstractions;

namespace QuackDuck.Infrastructure.Paths;

public sealed class AppPathProvider : IAppPathProvider
{
    public string AssetsRoot { get; }
    public string LanguagesRoot { get; }
    public string DataRoot { get; }
    public string TempRoot { get; }

    public AppPathProvider()
    {
        var baseDir = AppContext.BaseDirectory;
        AssetsRoot = Path.Combine(baseDir, "assets");
        LanguagesRoot = Path.Combine(baseDir, "languages");

        var userHome = Environment.GetFolderPath(Environment.SpecialFolder.UserProfile);
        DataRoot = Path.Combine(userHome, "quackduck");
        TempRoot = Path.Combine(DataRoot, "temp");

        Directory.CreateDirectory(DataRoot);
        Directory.CreateDirectory(TempRoot);
    }
}
