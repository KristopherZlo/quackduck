using System.IO;
using Microsoft.Win32;
using QuackDuck.Application.Abstractions;

namespace QuackDuck.Infrastructure.Paths;

public interface IRunKeyStore
{
    string? GetValue(string name);
    void SetValue(string name, string value);
    void DeleteValue(string name);
}

/// <summary>
/// Configures Windows autostart using the HKCU Run key.
/// </summary>
public sealed class RegistryAutostartService : IAutostartService
{
    private readonly string _appName;
    private readonly string _executablePath;
    private readonly IRunKeyStore _runKeyStore;

    public RegistryAutostartService(string appName, string executablePath)
        : this(appName, executablePath, new WindowsRunKeyStore())
    {
    }

    public RegistryAutostartService(string appName, string executablePath, IRunKeyStore runKeyStore)
    {
        _appName = appName;
        _executablePath = NormalizeExecutablePath(executablePath);
        _runKeyStore = runKeyStore;
    }

    public Task<bool> IsEnabledAsync(CancellationToken cancellationToken = default) =>
        Task.FromResult(IsEnabled());

    public Task SetAsync(bool enabled, CancellationToken cancellationToken = default)
    {
        try
        {
            if (enabled)
            {
                _runKeyStore.SetValue(_appName, QuoteExecutablePath(_executablePath));
            }
            else
            {
                _runKeyStore.DeleteValue(_appName);
            }
        }
        catch
        {
            // ignore registry failures; caller can handle/log if needed
        }

        return Task.CompletedTask;
    }

    private bool IsEnabled()
    {
        var current = _runKeyStore.GetValue(_appName);
        return string.Equals(NormalizeExecutablePath(current), _executablePath, StringComparison.OrdinalIgnoreCase);
    }

    public static string QuoteExecutablePath(string executablePath)
    {
        var normalized = NormalizeExecutablePath(executablePath);
        return normalized.Contains(' ') ? $"\"{normalized}\"" : normalized;
    }

    public static string NormalizeExecutablePath(string? value)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            return string.Empty;
        }

        var trimmed = value.Trim();
        if (trimmed.StartsWith('"'))
        {
            var closingQuote = trimmed.IndexOf('"', 1);
            if (closingQuote > 1)
            {
                trimmed = trimmed[1..closingQuote];
            }
        }
        else
        {
            var exeIndex = trimmed.IndexOf(".exe", StringComparison.OrdinalIgnoreCase);
            if (exeIndex >= 0)
            {
                trimmed = trimmed[..(exeIndex + 4)];
            }
        }

        try
        {
            trimmed = Path.GetFullPath(trimmed);
        }
        catch
        {
            // Keep the normalized textual value when the path is not parseable.
        }

        return trimmed.Trim();
    }
}

internal sealed class WindowsRunKeyStore : IRunKeyStore
{
    private const string RunKeyPath = @"Software\Microsoft\Windows\CurrentVersion\Run";

    public string? GetValue(string name)
    {
        using var runKey = Registry.CurrentUser.OpenSubKey(RunKeyPath, writable: false);
        return runKey?.GetValue(name) as string;
    }

    public void SetValue(string name, string value)
    {
        using var runKey = Registry.CurrentUser.OpenSubKey(RunKeyPath, writable: true) ??
                           Registry.CurrentUser.CreateSubKey(RunKeyPath);
        runKey?.SetValue(name, value);
    }

    public void DeleteValue(string name)
    {
        using var runKey = Registry.CurrentUser.OpenSubKey(RunKeyPath, writable: true);
        runKey?.DeleteValue(name, false);
    }
}
