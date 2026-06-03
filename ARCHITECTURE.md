# QuackDuck C# rewrite — structure and entrypoints

## Главный запускной файл
- `src/QuackDuck.Presentation.Wpf/App.xaml.cs` — точка входа WPF-приложения, создаёт `PetEngine` и открывает `MainWindow`. При сборке/запуске через `dotnet run --project src/QuackDuck.Presentation.Wpf/QuackDuck.Presentation.Wpf.csproj` стартует именно это приложение.

## Общая архитектура (слои)
- `src/QuackDuck.Domain` — чистые модели и контракты: настройки питомца (`PetSettings`), перечисление состояний (`PetStateKind`), поза (`PetPose`), взаимодействия указателя, описание скинов (`SkinDefinition`, `AnimationSequence`), интерфейсы состояний (`IPetState`, `IPetStateMachine`).
- `src/QuackDuck.Application` — логика без UI: абстракции сервисов (настройки, локализация, скины, аудио, микрофон, обновления, пути), `PetEngine` (координация сервисов и стейт-машины), базовая `PetStateMachine`, заглушечное состояние `NoOpState`, DTO `PetFrameUpdate` для UI.
- `src/QuackDuck.Infrastructure` — реализации абстракций: `AppPathProvider` (пути данных/ресурсов), `JsonSettingsStore`, `JsonLocalizationService`, `SkinFileService` (чтение config.json/zip), `MediaAudioService` (WAV-плеер), `NullMicrophoneMonitor` (заглушка микрофона), `NullUpdateService`.
- `src/QuackDuck.Presentation.Wpf` — UI/host: `App.xaml(.cs)` настраивает DI вручную, создаёт `PetEngine`; `MainWindow.xaml(.cs)` — прозрачное topmost окно (пока заглушка) с таймером, который вызывает `engine.Tick`. Проект линкует ресурсы `assets/`, `languages/`, `settings-ui-html-template/` как контент.
- `src/QuackDuck.Tests` — xUnit-проект для будущих тестов (пока пустой).

## Ресурсы и данные
- `assets/` — спрайты/звуки (скины), попадают в выходную папку WPF проекта.
- `languages/` — JSON с переводами (en/ru), копируются в выходную папку.
- `settings-ui-html-template/` — HTML для будущих настроек, также копируется.
- Пользовательские данные: будут храниться в `%UserProfile%/quackduck/settings.json` (JSON через `JsonSettingsStore`).

## Сборка и запуск
- Команда: `dotnet run --project src/QuackDuck.Presentation.Wpf/QuackDuck.Presentation.Wpf.csproj` (Debug по умолчанию).
- VS Code: профиль “Launch QuackDuck (WPF)” в `.vscode/launch.json` вызывает задачу `build QuackDuck` и запускает exe из `bin/Debug/net8.0-windows/`.

## Следующие шаги для полноты функционала
- Реализовать реальные состояния (Idle/Walk/Run/Jump/Fall/Drag/Playful/Attack/Listening/Sleep) поверх `PetEngine`.
- Подключить отрисовку спрайтов в WPF (Image/Canvas), обновление кадров по `PetFrameUpdate`.
- Заменить заглушки: микрофон (NAudio/WinRT), аудио с громкостью, автообновление, системный трей, автозапуск в реестре.
- Перенести UI настроек (нативный WPF или встроенный HTML-шаблон), связать с `PetSettings`.
