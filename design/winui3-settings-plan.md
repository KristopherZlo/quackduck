# WinUI 3 settings redesign

Draft UI lives in `design/WinUI3SettingsPage.xaml` (NavigationView shell + TabView content). It keeps every element from the legacy WPF/HTML menus but in a new layout.

## Sections and carried-over features
- General: autostart, random behaviors toggle, language picker (en/ru), ground offset, sleep timeout, direction-change interval, reset all settings.
- Appearance: pet name, show name toggle, pet size, walk speed, name offset Y, font size, preview block for name placement.
- Audio & Mic: input device selection, mic activation threshold slider, live mic level preview, sound effects toggle, effects volume, response probability (sound response).
- Skins: skin folder path with browse, selected skin picker, reload skins action, frame preview grid (idle/walk/sleep placeholders).
- Skin Store: featured skin cards (apply/preview placeholders) mirroring the old store mock.
- About: version/info text and external links (GitHub, Telegram, support).

## Integration notes
- Wire controls to `PetSettings` and `PetEngine.ApplySettingsAsync` (autostart, random behavior, sleep/direction timers, language, offsets, size/speed, sound flags/volume, activation threshold, skin folder/selection).
- Replace placeholders with real data: mic device list from `IMicrophoneMonitor`, skin list from `ISkinService`, version from assembly, previews from loaded frames.
- Hook NavigationView to drive TabView selection (or swap TabView for page navigation) and add Save/Cancel commands that commit settings and close the window.
