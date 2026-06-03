using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using System.Windows.Media.Imaging;
using ModernWpf.Controls;
using Microsoft.Win32;
using QuackDuck.Application;
using QuackDuck.Domain.Skins;
using QuackDuck.Infrastructure.Skins;
using Forms = System.Windows.Forms;

namespace QuackDuck.Presentation.Wpf;

public partial class SettingsWindow : Window
{
    private readonly PetEngine _engine;
    private readonly SkinBitmapCache _skinCache = new();
    private readonly List<SkinPreviewItem> _skinItems = new();
    private bool _syncingNavigation;
    private bool _loadingSkins;

    public SettingsWindow(PetEngine engine)
    {
        _engine = engine;
        InitializeComponent();
        Loaded += OnLoaded;
        LoadSettings();
        HookEvents();
        ApplyLocalization();
        VersionText.Text = $"v{Assembly.GetExecutingAssembly().GetName().Version}";
        Nav.SelectedItem = NavGeneral;
    }

    private async void OnLoaded(object sender, RoutedEventArgs e)
    {
        await RefreshSkinListAsync();
    }

    private void LoadSettings()
    {
        var s = _engine.Settings;
        PetNameBox.Text = s.PetName;
        ShowNameSwitch.IsOn = s.ShowName;
        PetSizeBox.Value = s.PetSize;
        WalkSpeedBox.Value = s.DuckSpeed;
        FontSizeBox.Value = s.FontBaseSize;
        NameOffsetBox.Value = s.NameOffsetY;

        SoundSwitch.IsOn = s.SoundEnabled;
        VolumeSlider.Value = s.SoundVolume;
        ActivationSlider.Value = s.ActivationThreshold;
        SoundResponseSlider.Value = s.SoundResponseProbability;
        UpdateVolumeLabel();
        UpdateActivationLabel();
        UpdateSoundResponseLabel();

        AutostartSwitch.IsOn = s.AutostartEnabled;
        GroundOffsetBox.Value = s.GroundLevelOffset;
        RandomBehaviorSwitch.IsOn = s.RandomBehaviorEnabled;
        SleepTimeoutBox.Value = s.SleepTimeoutSeconds;
        DirectionIntervalBox.Value = s.DirectionChangeIntervalSeconds;
        IdleDurationBox.Value = s.IdleDurationSeconds;
        PlayfulChanceSlider.Value = Math.Clamp(s.PlayfulBehaviorProbability, 0, 1);
        UpdatePlayfulChanceLabel();

        SkinFolderBox.Text = s.SkinFolder ?? string.Empty;
        SelectedSkinBox.Text = s.SelectedSkin ?? string.Empty;

        var selectedLanguage = s.CurrentLanguage?.ToLowerInvariant() ?? "en";
        foreach (ComboBoxItem item in LanguageCombo.Items)
        {
            if (string.Equals(item.Content?.ToString(), selectedLanguage, StringComparison.OrdinalIgnoreCase))
            {
                LanguageCombo.SelectedItem = item;
                break;
            }
        }
    }

    private void HookEvents()
    {
        VolumeSlider.ValueChanged += (_, _) => UpdateVolumeLabel();
        ActivationSlider.ValueChanged += (_, _) => UpdateActivationLabel();
        SoundResponseSlider.ValueChanged += (_, _) => UpdateSoundResponseLabel();
        PlayfulChanceSlider.ValueChanged += (_, _) => UpdatePlayfulChanceLabel();
        LanguageCombo.SelectionChanged += OnLanguageChanged;
    }

    private string T(string key, string fallback) => _engine.Localization.Translate(key, fallback);

    private void ApplyLocalization()
    {
        Title = T("settings_title", "Settings");
        HeaderTitleText.Text = T("settings", "Settings");
        HeaderSubtitleText.Text = T("settings_subtitle", "Customize QuackDuck");

        NavGeneral.Content = T("page_button_general", "General");
        NavAppearance.Content = T("page_button_appearance", "Appearance");
        NavAudio.Content = T("page_button_audio", "Audio");
        NavSkins.Content = T("page_button_skins", "Skins");
        NavStore.Content = T("page_button_store", "Skin Store");
        NavAbout.Content = T("page_button_about", "About");

        TabGeneral.Header = NavGeneral.Content;
        TabAppearance.Header = NavAppearance.Content;
        TabAudio.Header = NavAudio.Content;
        TabSkins.Header = NavSkins.Content;
        TabStore.Header = NavStore.Content;
        TabAbout.Header = NavAbout.Content;

        SaveButton.Content = T("save_button", "Save");
        CancelButton.Content = T("cancel_button", "Cancel");

        SessionHeader.Text = T("session_header", "Session");
        AutostartSwitch.Header = T("run_at_system_startup", "Start with Windows");
        RandomBehaviorSwitch.Header = T("random_behaviors", "Random behaviors");
        SleepTimeoutLabel.Text = T("sleep_timeout", "Sleep timeout (s)");
        DirectionIntervalLabel.Text = T("direction_change", "Direction change (s)");
        IdleDurationLabel.Text = T("idle_duration", "Idle duration (s)");

        LocalizationHeader.Text = T("localization_header", "Localization & layout");
        LanguageLabel.Text = T("language_selection", "Language");
        GroundOffsetLabel.Text = T("floor_level", "Ground offset (px)");
        PlayfulChanceLabel.Text = T("probability_of_playfulness", "Playful chance");

        IdentityHeader.Text = T("identity_header", "Identity");
        PetNameLabel.Text = T("pet_name", "Pet name");
        ShowNameSwitch.Header = T("show_name_checkbox", "Show name above pet");
        PetSizeLabel.Text = T("pet_size", "Pet size");
        WalkSpeedLabel.Text = T("movement_speed", "Walk speed");
        FontSizeLabel.Text = T("font_base_size", "Font size");

        NameOverlayHeader.Text = T("name_overlay", "Name overlay");
        NameOffsetLabel.Text = T("name_offset_y", "Name offset Y (px)");
        PreviewLabel.Text = T("preview_label", "Preview");

        MicrophoneHeader.Text = T("microphone_header", "Microphone");
        InputDeviceLabel.Text = T("input_device_selection", "Input device");
        ActivationLabel.Text = T("activation_threshold", "Activation threshold");
        ResponseProbabilityLabel.Text = T("probability_response_to_sound", "Response probability");

        SoundHeader.Text = T("sound_effects_header", "Sound effects");
        SoundSwitch.Header = T("turn_on_sound", "Enable sound effects");
        VolumeLabel.Text = T("volume", "Volume");

        SourcesHeader.Text = T("sources_header", "Sources");
        BrowseSkinFolderButton.Content = T("select_skin_folder_button", "Browse");
        ReloadSkinsButton.Content = T("reload_skins", "Reload skins");
        BrowseSkinFileButton.Content = T("select_skin_file", "Select file");
        PreviewFramesHeader.Text = T("skins_preview", "Preview frames");
        FeaturedSkinsHeader.Text = T("featured_skins", "Featured skins");

        AboutTitleText.Text = T("about_title", "About");
        AboutDescriptionText.Text = T("about_description", "Interactive desktop pet with native-like settings on Windows 11.");
        AboutAuthorText.Text = T("about_author", "Developed by ZloyXP");
    }

    private async void OnLanguageChanged(object sender, SelectionChangedEventArgs e)
    {
        var selectedLanguage = (LanguageCombo.SelectedItem as ComboBoxItem)?.Content?.ToString();
        if (string.IsNullOrWhiteSpace(selectedLanguage))
        {
            return;
        }

        try
        {
            await _engine.Localization.LoadAsync(selectedLanguage);
            ApplyLocalization();
        }
        catch
        {
            // ignore preview localization failures
        }
    }

    private void UpdateVolumeLabel()
    {
        VolumeValue.Text = $"{VolumeSlider.Value:P0}";
    }

    private void UpdateActivationLabel()
    {
        ActivationValue.Text = $"{(int)ActivationSlider.Value}";
    }

    private void UpdateSoundResponseLabel()
    {
        SoundResponseValue.Text = $"{SoundResponseSlider.Value:P0}";
    }

    private void UpdatePlayfulChanceLabel()
    {
        PlayfulChanceValue.Text = $"{PlayfulChanceSlider.Value:P0}";
    }

    private async Task RefreshSkinListAsync()
    {
        if (_loadingSkins)
        {
            return;
        }

        try
        {
            _loadingSkins = true;
            SkinsStatusText.Text = "Loading skins...";

            var folder = string.IsNullOrWhiteSpace(SkinFolderBox.Text) ? _engine.Settings.SkinFolder : SkinFolderBox.Text;
            var discovered = await _engine.DiscoverSkinsAsync(folder);
            var skins = new List<SkinDefinition>(discovered);

            var manualPath = GetManualSkinPath() ?? _engine.Settings.SelectedSkin;
            if (!string.IsNullOrWhiteSpace(manualPath) &&
                File.Exists(manualPath) &&
                !skins.Any(s => PathEquals(s.SourcePath, manualPath)))
            {
                var loaded = await _engine.LoadSkinDefinitionAsync(manualPath);
                if (loaded != null)
                {
                    skins.Add(loaded);
                }
            }

            var seen = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
            _skinItems.Clear();
            foreach (var skin in skins)
            {
                var key = NormalizeSkinKey(skin);
                if (!seen.Add(key))
                {
                    continue;
                }

                _skinItems.Add(BuildSkinPreview(skin));
            }

            SkinList.ItemsSource = null;
            SkinList.ItemsSource = _skinItems;
            SelectSkinByPath(manualPath);
            SkinsStatusText.Text = _skinItems.Count == 0
                ? "No skins found."
                : $"Loaded {_skinItems.Count} skin(s).";
        }
        finally
        {
            _loadingSkins = false;
        }
    }

    private void SelectSkinByPath(string? path)
    {
        SkinPreviewItem? selected = null;
        if (!string.IsNullOrWhiteSpace(path))
        {
            selected = _skinItems.FirstOrDefault(item => PathEquals(item.Skin.SourcePath, path));
        }

        selected ??= _skinItems.FirstOrDefault(item => item.Skin.IsDefault) ?? _skinItems.FirstOrDefault();
        if (selected != null)
        {
            SkinList.SelectedItem = selected;
            SelectedSkinBox.Text = selected.Skin.IsDefault ? string.Empty : selected.Skin.SourcePath ?? string.Empty;
        }
    }

    private SkinPreviewItem BuildSkinPreview(SkinDefinition skin)
    {
        var frames = _skinCache.GetFrames(skin, "idle", 1.0, "walk", "running", "sleep");
        BitmapSource? preview = frames.FirstOrDefault();
        if (preview == null)
        {
            var cached = _skinCache.GetOrAdd(skin);
            if (cached.SpriteSheet is BitmapSource sheet &&
                skin.FrameWidth > 0 &&
                skin.FrameHeight > 0 &&
                sheet.PixelWidth >= skin.FrameWidth &&
                sheet.PixelHeight >= skin.FrameHeight)
            {
                try
                {
                    preview = new CroppedBitmap(sheet, new Int32Rect(0, 0, skin.FrameWidth, skin.FrameHeight));
                    if (preview.CanFreeze)
                    {
                        preview.Freeze();
                    }
                }
                catch
                {
                    preview = null;
                }
            }
        }

        preview ??= BitmapSource.Create(
            1,
            1,
            96,
            96,
            PixelFormats.Bgra32,
            null,
            new byte[] { 0, 0, 0, 0 },
            4);

        var displayName = skin.IsDefault ? "Default" : (string.IsNullOrWhiteSpace(skin.Id) ? "Skin" : skin.Id);
        var sourceLabel = skin.IsDefault
            ? "Built-in"
            : Path.GetFileName(skin.SourcePath ?? skin.SpriteSheetPath);

        return new SkinPreviewItem(skin, preview, displayName, sourceLabel);
    }

    private static string NormalizeSkinKey(SkinDefinition skin) =>
        NormalizePath(skin.SourcePath) ?? skin.Id.ToLowerInvariant();

    private static bool PathEquals(string? a, string? b) => string.Equals(NormalizePath(a), NormalizePath(b), StringComparison.OrdinalIgnoreCase);

    private static string? NormalizePath(string? path)
    {
        if (string.IsNullOrWhiteSpace(path))
        {
            return null;
        }

        try
        {
            return Path.GetFullPath(path).Trim().ToLowerInvariant();
        }
        catch
        {
            return path.Trim().ToLowerInvariant();
        }
    }

    private string? GetManualSkinPath() =>
        string.IsNullOrWhiteSpace(SelectedSkinBox.Text) ? null : SelectedSkinBox.Text.Trim();

    private async void OnReloadSkinsClicked(object sender, RoutedEventArgs e)
    {
        await RefreshSkinListAsync();
    }

    private async void OnBrowseSkinFolderClicked(object sender, RoutedEventArgs e)
    {
        var initial = Directory.Exists(SkinFolderBox.Text)
            ? SkinFolderBox.Text
            : Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments);

        using var dialog = new Forms.FolderBrowserDialog
        {
            SelectedPath = initial,
            Description = "Choose a folder containing skin .zip files"
        };

        if (dialog.ShowDialog() == Forms.DialogResult.OK)
        {
            SkinFolderBox.Text = dialog.SelectedPath;
            await RefreshSkinListAsync();
        }
    }

    private async void OnBrowseSkinFileClicked(object sender, RoutedEventArgs e)
    {
        var initialDir = Directory.Exists(SkinFolderBox.Text)
            ? SkinFolderBox.Text
            : Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments);

        var dialog = new Microsoft.Win32.OpenFileDialog
        {
            Filter = "Skin archives (*.zip)|*.zip|All files (*.*)|*.*",
            InitialDirectory = initialDir,
            Title = "Select skin archive"
        };

        if (dialog.ShowDialog() == true)
        {
            SelectedSkinBox.Text = dialog.FileName;
            await RefreshSkinListAsync();
        }
    }

    private void OnSkinSelectionChanged(object sender, SelectionChangedEventArgs e)
    {
        if (SkinList.SelectedItem is SkinPreviewItem item)
        {
            SelectedSkinBox.Text = item.Skin.IsDefault ? string.Empty : item.Skin.SourcePath ?? string.Empty;
        }
    }

    private async void OnSaveClicked(object sender, RoutedEventArgs e)
    {
        var current = _engine.Settings;
        var selectedLanguage = (LanguageCombo.SelectedItem as ComboBoxItem)?.Content?.ToString() ?? current.CurrentLanguage;

        var updated = current with
        {
            PetName = PetNameBox.Text,
            ShowName = ShowNameSwitch.IsOn,
            PetSize = (int)PetSizeBox.Value,
            DuckSpeed = WalkSpeedBox.Value,
            FontBaseSize = (int)FontSizeBox.Value,
            NameOffsetY = (int)NameOffsetBox.Value,
            SoundEnabled = SoundSwitch.IsOn,
            SoundVolume = VolumeSlider.Value,
            ActivationThreshold = (int)ActivationSlider.Value,
            AutostartEnabled = AutostartSwitch.IsOn,
            GroundLevelOffset = (int)GroundOffsetBox.Value,
            RandomBehaviorEnabled = RandomBehaviorSwitch.IsOn,
            SleepTimeoutSeconds = SleepTimeoutBox.Value,
            DirectionChangeIntervalSeconds = DirectionIntervalBox.Value,
            IdleDurationSeconds = IdleDurationBox.Value,
            PlayfulBehaviorProbability = PlayfulChanceSlider.Value,
            SoundResponseProbability = SoundResponseSlider.Value,
            SkinFolder = string.IsNullOrWhiteSpace(SkinFolderBox.Text) ? null : SkinFolderBox.Text,
            SelectedSkin = string.IsNullOrWhiteSpace(SelectedSkinBox.Text) ? null : SelectedSkinBox.Text,
            CurrentLanguage = selectedLanguage
        };

        await _engine.ApplySettingsAsync(updated);
        Close();
    }

    private void OnCancelClicked(object sender, RoutedEventArgs e)
    {
        Close();
    }

    private void OnNavSelectionChanged(object sender, NavigationViewSelectionChangedEventArgs e)
    {
        if (_syncingNavigation)
        {
            return;
        }

        _syncingNavigation = true;
        if (e.SelectedItem is NavigationViewItem item)
        {
            ContentTabs.SelectedIndex = item.Tag?.ToString() switch
            {
                "general" => 0,
                "appearance" => 1,
                "audio" => 2,
                "skins" => 3,
                "store" => 4,
                "about" => 5,
                _ => ContentTabs.SelectedIndex
            };
        }
        _syncingNavigation = false;
    }

    private void OnTabSelectionChanged(object sender, SelectionChangedEventArgs e)
    {
        if (_syncingNavigation)
        {
            return;
        }

        _syncingNavigation = true;
        var target = ContentTabs.SelectedIndex switch
        {
            0 => NavGeneral,
            1 => NavAppearance,
            2 => NavAudio,
            3 => NavSkins,
            4 => NavStore,
            5 => NavAbout,
            _ => null
        };

        if (target != null)
        {
            Nav.SelectedItem = target;
        }
        _syncingNavigation = false;
    }

    private sealed record SkinPreviewItem(SkinDefinition Skin, BitmapSource Preview, string DisplayName, string SourceLabel);
}
