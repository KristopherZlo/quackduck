using System.IO;
using System.Text.Json;
using System.Text.Json.Serialization;
using System.Windows;
using Microsoft.Web.WebView2.Core;
using Microsoft.Win32;
using QuackDuck.Application;
using QuackDuck.Application.Rendering;
using QuackDuck.Domain.Pets;
using QuackDuck.Presentation.Wpf.SettingsWeb;
using Forms = System.Windows.Forms;

namespace QuackDuck.Presentation.Wpf;

public partial class WebSettingsWindow : Window
{
    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
        DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull
    };

    private readonly PetEngine _engine;
    private readonly double _uiScale;

    public WebSettingsWindow(PetEngine engine)
    {
        _engine = engine;
        InitializeComponent();
        var workArea = SystemParameters.WorkArea;
        _uiScale = DisplayScalePolicy.Calculate(workArea.Width, workArea.Height);
        Width = Math.Min(1180 * _uiScale, workArea.Width * 0.94);
        Height = Math.Min(820 * _uiScale, workArea.Height * 0.94);
        Loaded += OnLoaded;
        Closed += OnClosed;
    }

    private async void OnLoaded(object sender, RoutedEventArgs e)
    {
        try
        {
            await SettingsWebView.EnsureCoreWebView2Async();
            SettingsWebView.ZoomFactor = _uiScale;
            await SettingsWebView.CoreWebView2.AddScriptToExecuteOnDocumentCreatedAsync(BuildBridgeShim());
            SettingsWebView.CoreWebView2.WebMessageReceived += OnWebMessageReceived;

            var htmlPath = Path.Combine(AppContext.BaseDirectory, "settings-ui-html-template", "index.html");
            if (!File.Exists(htmlPath))
            {
                htmlPath = Path.Combine(AppContext.BaseDirectory, "..", "..", "..", "..", "settings-ui-html-template", "index.html");
            }

            SettingsWebView.Source = new Uri(Path.GetFullPath(htmlPath));
        }
        catch (Exception ex)
        {
            System.Windows.MessageBox.Show(this, ex.Message, "Settings", MessageBoxButton.OK, MessageBoxImage.Error);
        }
    }

    private void OnClosed(object? sender, EventArgs e)
    {
        if (SettingsWebView.CoreWebView2 != null)
        {
            SettingsWebView.CoreWebView2.WebMessageReceived -= OnWebMessageReceived;
        }

        SettingsWebView.Dispose();
    }

    private async void OnWebMessageReceived(object? sender, CoreWebView2WebMessageReceivedEventArgs e)
    {
        var id = 0;
        try
        {
            var request = JsonSerializer.Deserialize<BridgeRequest>(e.WebMessageAsJson, JsonOptions)
                          ?? throw new InvalidOperationException("Invalid bridge request.");
            id = request.Id;
            var result = await HandleRequestAsync(request);
            PostResponse(new SettingsBridgeResponse(request.Id, true, result, null));
        }
        catch (Exception ex)
        {
            PostResponse(new SettingsBridgeResponse(id, false, null, ex.Message));
        }
    }

    private async Task<object?> HandleRequestAsync(BridgeRequest request)
    {
        return request.Method switch
        {
            "get_state" => await SettingsStateDto.CreateAsync(_engine),
            "get_mic_level" => _engine.LastMicLevel,
            "update_settings" => await UpdateSettingsAsync(request.Payload),
            "choose_skin_folder" => await ChooseSkinFolderAsync(),
            "choose_skin_file" => await ChooseSkinFileAsync(),
            "reset_settings" => await ResetSettingsAsync(),
            "check_updates" => await CheckUpdatesAsync(),
            _ => throw new InvalidOperationException($"Unknown settings bridge method: {request.Method}")
        };
    }

    private async Task<SettingsStateDto> UpdateSettingsAsync(JsonElement payload)
    {
        var update = JsonSerializer.Deserialize<SettingsUpdateDto>(payload.GetRawText(), JsonOptions)
                     ?? new SettingsUpdateDto();
        await _engine.ApplySettingsAsync(update.ApplyTo(_engine.Settings));
        return await SettingsStateDto.CreateAsync(_engine);
    }

    private async Task<SettingsStateDto> ChooseSkinFolderAsync()
    {
        using var dialog = new Forms.FolderBrowserDialog
        {
            SelectedPath = Directory.Exists(_engine.Settings.SkinFolder) ? _engine.Settings.SkinFolder : string.Empty,
            UseDescriptionForTitle = true,
            Description = "Choose skins folder"
        };

        if (dialog.ShowDialog() == Forms.DialogResult.OK)
        {
            await _engine.ApplySettingsAsync(_engine.Settings with
            {
                SkinFolder = dialog.SelectedPath
            });
        }

        return await SettingsStateDto.CreateAsync(_engine);
    }

    private async Task<SettingsStateDto> ChooseSkinFileAsync()
    {
        var dialog = new Microsoft.Win32.OpenFileDialog
        {
            Filter = "QuackDuck skins (*.zip;*.json)|*.zip;*.json|All files (*.*)|*.*",
            CheckFileExists = true,
            InitialDirectory = Directory.Exists(_engine.Settings.SkinFolder) ? _engine.Settings.SkinFolder : string.Empty
        };

        if (dialog.ShowDialog(this) == true)
        {
            await _engine.ApplySettingsAsync(_engine.Settings with
            {
                SkinFolder = Path.GetDirectoryName(dialog.FileName) ?? _engine.Settings.SkinFolder,
                SelectedSkin = dialog.FileName
            });
        }

        return await SettingsStateDto.CreateAsync(_engine);
    }

    private async Task<SettingsStateDto> ResetSettingsAsync()
    {
        await _engine.ApplySettingsAsync(PetSettings.Default);
        return await SettingsStateDto.CreateAsync(_engine);
    }

    private async Task<object> CheckUpdatesAsync()
    {
        var update = await _engine.CheckForUpdatesAsync();
        if (update == null)
        {
            return new { message = "No updates available." };
        }

        return new
        {
            message = $"New version {update.Version} available.",
            version = update.Version,
            notes = update.Notes,
            releaseUrl = update.ReleaseUrl,
            assetName = update.AssetName
        };
    }

    private void PostResponse(SettingsBridgeResponse response)
    {
        SettingsWebView.CoreWebView2.PostWebMessageAsJson(JsonSerializer.Serialize(response, JsonOptions));
    }

    private static string BuildBridgeShim()
    {
        return """
            (() => {
              if (window.pywebview && window.pywebview.api) return;
              const pending = new Map();
              let nextId = 1;
              const invoke = (method, payload) => new Promise((resolve, reject) => {
                const id = nextId++;
                pending.set(id, { resolve, reject });
                window.chrome.webview.postMessage({ id, method, payload: payload ?? {} });
              });
              window.chrome.webview.addEventListener('message', (event) => {
                const message = event.data || {};
                const task = pending.get(message.id);
                if (!task) return;
                pending.delete(message.id);
                if (message.ok) {
                  task.resolve(message.result);
                } else {
                  task.reject(new Error(message.error || 'Settings bridge error'));
                }
              });
              window.pywebview = {
                api: {
                  get_state: () => invoke('get_state'),
                  update_settings: (payload) => invoke('update_settings', payload),
                  get_mic_level: () => invoke('get_mic_level'),
                  choose_skin_folder: () => invoke('choose_skin_folder'),
                  choose_skin_file: () => invoke('choose_skin_file'),
                  reset_settings: () => invoke('reset_settings'),
                  check_updates: () => invoke('check_updates')
                }
              };
              window.dispatchEvent(new Event('pywebviewready'));
              document.dispatchEvent(new Event('pywebviewready'));
            })();
            """;
    }

    private sealed class BridgeRequest
    {
        public int Id { get; init; }
        public string Method { get; init; } = string.Empty;
        public JsonElement Payload { get; init; }
    }
}
