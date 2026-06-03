# QuackDuck C# rewrite plan

Purpose: migrate the existing Python/PyQt QuackDuck virtual pet into a modular, OOP-first C# application while keeping feature parity (skins, states, sounds, mic reactions, localization, settings) and improving maintainability.

Guiding rules:
- Keep this file as the source of truth; update it after each completed step.
- Favor clear boundaries: domain logic separated from UI, infrastructure behind interfaces, testable services.
- Target modern .NET (>= 8.0) with WPF + MVVM for desktop UI, unless later constraints require a change.

Work plan (update with [x] as we go):
- [x] 1) Audit the current Python app: map features, assets, settings, state machine, localization, audio/mic usage, updater flow.
- [x] 2) Define C# architecture: solution layout (e.g., QuackDuck.Domain, .Application, .Infrastructure, .Presentation.Wpf, .Tests), key interfaces (state machine, skin provider, settings store, audio/mic services, localization), and data models.
- [x] 3) Build solution skeleton: create .NET solution, projects, DI wiring, shared contracts, base state machine, resource pipelines, and placeholder asset loading.
- [ ] 4) Port core features incrementally:
  - [ ] State system and behaviors (walk, sleep, play, etc.) with timers/animations.
  - [ ] Skin system (zip import, selection, caching) and asset management.
  - [ ] Localization loading (existing language files) and settings UI.
  - [ ] Audio playback and microphone reaction services.
  - [ ] Persistence (settings, skin paths) and logging.
- [ ] 5) Implement UI/UX: WPF views with MVVM, overlay behavior, drag/interaction, menus, settings dialogs, error surface.
- [ ] 6) Testing and quality: unit tests for domain/services, integration smoke for asset loading and settings, localization checks.
- [ ] 7) Packaging and delivery: publish profile, asset bundling, language/skin packaging, documentation on usage and migration from Python version.

Current state snapshot (Python app):
- Overlay pet built with PyQt6; frameless top-most window plus system tray menu (show/hide, settings, unstuck, about, update, exit) and debug window.
- State machine includes Idle, Walking, Run (chance), Jumping, Falling/Landing, Dragging, Playful (cursor shake chase), Attack (near cursor if animation exists), Listening (mic threshold), Sleeping (idle timeout). Timers drive animation/position/sleep/random behaviors; heart on double-click; unstuck centers pet.
- Resources: skins zipped with config.json (spritesheet path, frame_width, frame_height, animations mapping like "row:col", optional sound wav list). Default skin at assets/skins/default; scaling by pet_size; caches frames and sounds; preview support for settings.
- Settings persisted via QSettings: pet_name, show_name, name_offset_y, font_base_size, selected_mic_index, activation_threshold, sound_response_probability, sound_enabled, sound_volume, autostart_enabled, ground_level, pet_size, skin_folder, selected_skin, duck_speed, random_behavior, idle_duration, sleep_timeout, direction_change_interval, current_language, skipped_version.
- Audio/mic: QSoundEffect playback of random quack files on timer; MicrophoneListener (sounddevice) emitting volume to trigger ListeningState; activation threshold adjustable.
- Localization: JSON files in languages (en/ru), set_language swaps translation dict. Settings UI uses these strings.
- Updater: AutoUpdater checks GitHub releases, downloads zip, replaces app folder, restarts with --cleanup-bak; uses temp_updater dir; logging to quackduck.log and crash log at user home.
- UI/config: HTML-based settings window via webview (index.html template), also PyQt settings window; name label overlay; autostart via Windows registry; ground level offset; system accent color usage.

Open questions still to pin down:
- Do we keep an auto-updater in the first C# iteration or defer?
- Target OS scope (Windows-only with WPF assumed) and packaging expectations.
- Preferred UI stack for settings (native WPF vs embedded webview) and whether to keep existing HTML assets.

Architecture decisions for the C# rewrite:
- Tech stack: .NET 8.0 (net8.0-windows); WPF with MVVM for UI; System.Windows.Forms.NotifyIcon for tray; DispatcherTimer for animation/position; logging via Microsoft.Extensions.Logging to %AppData%\\QuackDuck\\quackduck.log.
- Solution layout: QuackDuck.Domain (states, models, interfaces), QuackDuck.Application (controllers/services/state machine orchestration), QuackDuck.Infrastructure (filesystem settings store, skin loader, localization loader, audio/mic impl, updater stub, logging adapters), QuackDuck.Presentation.Wpf (XAML views, viewmodels, assets, tray), QuackDuck.Tests (xUnit/nunit equivalent for domain/services).
- Core abstractions: IDuckState (Enter/Update/HandleInput/Exit), IStateMachineClock/ITickScheduler, IResourceProvider (spritesheet/animation frames, sounds), ISettingsStore, IAudioPlayer, IMicListener, ILocalizationService, IUpdater (initially stubbed), ITray/UI contracts so domain is UI-agnostic.
- Assets and data: reuse assets/skins + languages as content files; support skin zip config.json with fields spritesheet, frame_width, frame_height, animations map, optional sound list; extract to temp folder and cache frames; store user settings in JSON under %AppData%/QuackDuck/settings.json; keep crash log path parity.
- Feature mapping plan: overlay window (transparent, topmost, draggable), name label overlay, heart animation on double-click, ground-level offsets, random behaviors (idle/walk/run/attack/playful/listening/sleep), sound timer, mic-triggered listening, autostart toggle (Windows registry), system accent color usage for UI.
- Dependencies: prefer BCL-first; for mic RMS detection plan to use NAudio or Windows.Media.Audio (win10+)—need package restore approval; audio playback via MediaPlayer or SoundPlayer for wav; updater will be pluggable and can be implemented after core port.

Skeleton status (C#):
- Solution created under `src/` with projects: Domain, Application, Infrastructure (net8.0-windows), Presentation.Wpf, Tests; wired references and assets/languages/html copied to output.
- Domain: pet settings/state enums, interaction primitives, skin/animation definitions, state interfaces.
- Application: service abstractions (settings, localization, skins, audio, mic, updater, paths), PetEngine orchestrator, base PetStateMachine, NoOpState, render frame DTO.
- Infrastructure: path resolver, JSON settings store, localization loader, skin loader (config/zip), WAV-only audio stub, null mic monitor, placeholder update service.
- Presentation.Wpf: transparent topmost window placeholder with dispatcher tick loop, manual wiring of services/engine in App startup; assets linked for build output.
