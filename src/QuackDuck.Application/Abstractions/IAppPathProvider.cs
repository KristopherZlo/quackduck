namespace QuackDuck.Application.Abstractions;

public interface IAppPathProvider
{
    string AssetsRoot { get; }
    string LanguagesRoot { get; }
    string DataRoot { get; }
    string TempRoot { get; }
}
