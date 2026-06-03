# QuackDuck C# porting TODO

- Rendering and state loop
  - [x] Implement sprite rendering in WPF (Image/Canvas) driven by `PetFrameUpdate`; support flip X.
  - [x] Port state machine behaviors from Python (`quackduck_app/states.py`): Idle/Walking/Run/Jumping/Falling/Landing/Dragging/Playful/Attack/Listening/Sleeping and transitions/timers.
  - [x] Cursor shake detection → trigger Playful; attack trigger near cursor; heart spawn on double-click; random behaviors (idle/direction change/run).
  - [ ] Ground-level logic and gravity/jump physics parity.

- Resources/skins
  - [x] Use `SkinFileService` to load spritesheet frames into WPF-compatible bitmaps; add caching & scaling by pet size.
  - [x] Support idle animation selection (idle* keys) and skin previews; handle default skin fallback.
  - [x] Wire random quack sound selection per skin.

- Audio/microphone
  - [x] Replace `MediaAudioService` with real audio backend (e.g., NAudio) supporting volume + WAV/MP3.
  - [x] Implement mic listener (NAudio/WinRT) emitting RMS volume; tie to ListeningState entry/exit thresholds.

- Settings/persistence
  - [x] Map `PetSettings` to UI controls; enable live update of pet (size, speed, name, show_name, offsets, language, ground level, skin selection, volumes, thresholds, autostart).
  - [x] Implement autostart via registry on Windows (parity with Python).
  - [ ] Persist skipped_version, random_behavior toggles, sleep_timeout, direction change interval.

- Localization
  - [x] Bind translations from `JsonLocalizationService` to UI; add language switcher and reload resources.
  - [ ] Validate `languages/lang_en.json` and `lang_ru.json` coverage.

- UI/UX
  - [x] Replace placeholder window with transparent overlay showing pet; add name label overlay with font scaling and offset.
  - [x] Add system tray icon/menu (show/hide, settings, unstuck, about, check updates, exit, debug).
  - [x] Implement settings UI (native WPF or reuse `settings-ui-html-template`) with two-way binding to `PetEngine`.
  - [x] Ship standalone Avalonia settings app with dark layout and sidebar navigation; launch from WPF when available.
  - [x] Debug window parity (state history, sliders) optional.

- Update system
  - [ ] Port AutoUpdater (GitHub releases) with temp download/extract and restart; UI for progress.

- Logging and crash handling
  - [ ] Add logging to `%UserProfile%/quackduck/quackduck.log` with rolling/levels.
  - [ ] Crash handler to write details to `%UserProfile%/quackduck_crash.log` and show a dialog.

- Packaging
  - [ ] Publish profile (single-file? self-contained?), include assets/languages/templates, ensure temp directories cleanup.
  - [ ] Document migration/usage in README/ARCHITECTURE.

- Testing
  - [ ] Unit tests for settings store, skin loader, localization, state transitions, and mic/audio adapters (where feasible via abstractions).
