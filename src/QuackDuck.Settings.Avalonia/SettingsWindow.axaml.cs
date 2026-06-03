using Avalonia.Controls;
using Avalonia.Interactivity;
using System.Collections.ObjectModel;
using QuackDuck.Application;
using QuackDuck.Domain.Pets;
using QuackDuck.Infrastructure.Audio;
using QuackDuck.Infrastructure.Localization;
using QuackDuck.Infrastructure.Paths;
using QuackDuck.Infrastructure.Settings;
using QuackDuck.Infrastructure.Skins;
using QuackDuck.Infrastructure.Updates;

namespace QuackDuck.Settings.Avalonia;

public partial class SettingsWindow : Window
{
    private readonly PetEngine _engine;
    private readonly ObservableCollection<string> _discoveredSkins = new();

    public SettingsWindow()
    {
        InitializeComponent();

        // Build engine similar to WPF host but without microphone start/tick loop.
        var paths = new AppPathProvider();
        var settingsStore = new JsonSettingsStore(paths);
        var localization = new JsonLocalizationService(paths);
        var skinService = new SkinFileService(paths);
        var audioService = new MediaAudioService();
        var microphoneMonitor = new NullMicrophoneMonitor();
        var updateService = new NullUpdateService();
        var autostart = new RegistryAutostartService("QuackDuck", AppContext.BaseDirectory);

        _engine = new PetEngine(
            settingsStore,
            skinService,
            audioService,
            microphoneMonitor,
            localization,
            updateService,
            autostart);

        _ = _engine.InitializeAsync();
        LoadSettings();
        _ = RefreshSkinsAsync();
    }

    private void LoadSettings()
    {
        var s = _engine.Settings;
        PetNameBox.Text = s.PetName;
        ShowNameSwitch.IsChecked = s.ShowName;
        FontSizeBox.Value = (decimal)s.FontBaseSize;
        NameOffsetBox.Value = (decimal)s.NameOffsetY;
        PetSizeBox.Value = (decimal)s.PetSize;
        WalkSpeedBox.Value = (decimal)s.DuckSpeed;
        GroundOffsetBox.Value = (decimal)s.GroundLevelOffset;
        PlayfulChanceSlider.Value = s.PlayfulBehaviorProbability;

        SoundSwitch.IsChecked = s.SoundEnabled;
        VolumeSlider.Value = s.SoundVolume;
        ActivationBox.Value = (decimal)s.ActivationThreshold;
        SoundResponseSlider.Value = s.SoundResponseProbability;
        RandomBehaviorSwitch.IsChecked = s.RandomBehaviorEnabled;

        IdleDurationBox.Value = (decimal)s.IdleDurationSeconds;
        DirectionIntervalBox.Value = (decimal)s.DirectionChangeIntervalSeconds;
        SleepTimeoutBox.Value = (decimal)s.SleepTimeoutSeconds;

        SkinFolderBox.Text = s.SkinFolder ?? string.Empty;
        SelectedSkinBox.Text = s.SelectedSkin ?? string.Empty;

        AutostartSwitch.IsChecked = s.AutostartEnabled;

        foreach (ComboBoxItem item in LanguageCombo.Items)
        {
            if (string.Equals(item.Content?.ToString(), s.CurrentLanguage, StringComparison.OrdinalIgnoreCase))
            {
                LanguageCombo.SelectedItem = item;
                break;
            }
        }
    }

    private async Task RefreshSkinsAsync()
    {
        var skins = await _engine.DiscoverSkinsAsync(SkinFolderBox.Text);
        _discoveredSkins.Clear();
        foreach (var skin in skins)
        {
            _discoveredSkins.Add(skin.SourcePath ?? skin.Id);
        }
        SkinList.ItemsSource = _discoveredSkins;
    }

    private async void OnSaveClicked(object? sender, RoutedEventArgs e)
    {
        var current = _engine.Settings;
        var language = (LanguageCombo.SelectedItem as ComboBoxItem)?.Content?.ToString() ?? current.CurrentLanguage;

        var updated = current with
        {
            PetName = PetNameBox.Text ?? string.Empty,
            ShowName = ShowNameSwitch.IsChecked ?? false,
            FontBaseSize = (int)FontSizeBox.Value,
            NameOffsetY = (int)NameOffsetBox.Value,
            PetSize = (int)PetSizeBox.Value,
            DuckSpeed = (double)WalkSpeedBox.Value,
            GroundLevelOffset = (int)GroundOffsetBox.Value,
            PlayfulBehaviorProbability = PlayfulChanceSlider.Value,
            SoundEnabled = SoundSwitch.IsChecked ?? false,
            SoundVolume = VolumeSlider.Value,
            ActivationThreshold = (int)ActivationBox.Value,
            SoundResponseProbability = SoundResponseSlider.Value,
            RandomBehaviorEnabled = RandomBehaviorSwitch.IsChecked ?? false,
            IdleDurationSeconds = (double)IdleDurationBox.Value,
            DirectionChangeIntervalSeconds = (double)DirectionIntervalBox.Value,
            SleepTimeoutSeconds = (double)SleepTimeoutBox.Value,
            SkinFolder = string.IsNullOrWhiteSpace(SkinFolderBox.Text) ? null : SkinFolderBox.Text,
            SelectedSkin = string.IsNullOrWhiteSpace(SelectedSkinBox.Text) ? null : SelectedSkinBox.Text,
            AutostartEnabled = AutostartSwitch.IsChecked ?? false,
            CurrentLanguage = language
        };

        await _engine.ApplySettingsAsync(updated);
        StatusText.Text = "Saved";
    }

    private void OnCancelClicked(object? sender, RoutedEventArgs e) => Close();

    private async void OnBrowseSkinFolder(object? sender, RoutedEventArgs e)
    {
        var dialog = new OpenFolderDialog();
        var result = await dialog.ShowAsync(this);
        if (!string.IsNullOrWhiteSpace(result))
        {
            SkinFolderBox.Text = result;
            await RefreshSkinsAsync();
        }
    }

    private async void OnBrowseSkinFile(object? sender, RoutedEventArgs e)
    {
        var dialog = new OpenFileDialog
        {
            AllowMultiple = false,
            Filters = new List<FileDialogFilter>
            {
                new() { Name = "Skin archives", Extensions = { "zip" } },
                new() { Name = "All files", Extensions = { "*" } }
            }
        };
        var result = await dialog.ShowAsync(this);
        if (result != null && result.Length > 0)
        {
            SelectedSkinBox.Text = result[0];
            await RefreshSkinsAsync();
        }
    }

    private async void OnReloadSkins(object? sender, RoutedEventArgs e) => await RefreshSkinsAsync();
}
