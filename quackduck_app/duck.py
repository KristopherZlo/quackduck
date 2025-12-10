import logging
import os
import random
import shutil
import sys
import time

import sounddevice as sd
from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtMultimedia import QSoundEffect
from PyQt6.QtWidgets import QMessageBox

from autoupdater import AutoUpdater, UpdateWindow
from .audio import MicrophoneListener
from .core import GLOBAL_DEBUG_MODE, PROJECT_VERSION, get_seed_from_name, resource_path
from .i18n import translations, set_language
from .resources import ResourceManager
from .settings_store import SettingsManager
from .states import (
    AttackState,
    DraggingState,
    FallingState,
    IdleState,
    JumpingState,
    LandingState,
    ListeningState,
    PlayfulState,
    RunState,
    SleepingState,
    WalkingState,
)
from .ui import DebugWindow, HeartWindow, NameWindow, SettingsWindow, SystemTrayIcon

if sys.platform == "win32":
    import winreg
    import win32api
    import win32con
    import win32gui
    import win32process


def notify_user_about_update(duck, latest_release, manual_trigger=False):
    """
    Show a window with a suggestion to update or skip the version.
    When "Yes" is clicked > launch a new autoupdater.
    """
    latest_version = latest_release['tag_name'].lstrip('v')
    release_notes = latest_release.get('body', '')
    github_url = latest_release.get('html_url', '#')  # Link to the release

    # Limit the release notes length to 600 characters
    if len(release_notes) > 600:
        release_notes = release_notes[:600] + '...'

    # Append a link to the full changelog
    release_notes += f"\n\nGithub Change log: {github_url}"

    # If the version was previously skipped and this is NOT a manual check, we leave
    if duck.skipped_version == latest_version and not manual_trigger:
        return

    msg = QMessageBox(duck)
    msg.setWindowTitle(translations.get("update_available", "Update available"))

    message_template = translations.get(
        "new_version_available_text",
        f"A new version {latest_version} is available\n\nWhat's new:\n{{release_notes}}\n\nDo you want to install the new update?"
    )
    message = message_template.format(latest_version=latest_version, release_notes=release_notes)
    msg.setText(message)

    yes_button = msg.addButton(translations.get("yes", "Yes"), QMessageBox.YesRole)
    no_button = msg.addButton(translations.get("no", "No"), QMessageBox.NoRole)
    skip_button = msg.addButton(translations.get("skip_this_version", "Skip this version"), QMessageBox.ActionRole)
    msg.setDefaultButton(yes_button)

    msg.exec()

    clicked_button = msg.clickedButton()
    if clicked_button == yes_button:
        app_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
        upd_win = UpdateWindow(
            autoupdater=duck.updater,
            current_version=PROJECT_VERSION,
            app_dir=app_dir,
            exe_name="quackduck.exe",
            parent=duck
        )
        upd_win.exec()
    elif clicked_button == skip_button:
        duck.set_skipped_version(latest_version)
        if manual_trigger:
            skip_message_template = translations.get(
                "version_skipped_message",
                f"Version {latest_version} will be skipped. It will not be offered again."
            )
            skip_message = skip_message_template.format(latest_version=latest_version)
            QMessageBox.information(
                duck,
                translations.get("skipped_version_title", "Version Skipped"),
                skip_message
            )


class Duck(QtWidgets.QWidget):
    """
    Represents the main duck pet in the application.
    Uses AutoUpdater for checking and installing updates,
    and preserves user notification via notify_user_about_update(...).
    Now it also checks if a fullscreen application is active via WinAPI.
    """

    def __init__(self):
        super().__init__()
        self.settings_manager = SettingsManager()
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.Window)

        self.sound_effect = QSoundEffect()
        self.sound_effect.setVolume(0.5)

        self.load_settings()

        self.updater = AutoUpdater(
            current_version=PROJECT_VERSION,
            repo_owner="KristopherZlo",
            repo_name="quackduck"
        )

        self.sound_effect.setVolume(self.sound_volume)

        self.debug_mode = False
        self.debug_window = None
        self.state_history = []

        icon_path = resource_path("assets/images/white-quackduck-visible.ico")
        if os.path.exists(icon_path):
            icon = QtGui.QIcon(icon_path)
            if icon.isNull():
                logging.error(f"Failed to load icon from {icon_path}")
            else:
                self.setWindowIcon(icon)
        else:
            logging.error(f"Icon file not found: {icon_path}")

        self.scale_factor = self.get_scale_factor()

        self.pet_size = self.settings_manager.get_value('pet_size', default=3, value_type=int)
        self.resources = ResourceManager(self.scale_factor, self.pet_size)

        self.cursor_positions = []
        self.cursor_shake_timer = QtCore.QTimer()
        self.cursor_shake_timer.timeout.connect(self.check_cursor_shake)

        self.selected_mic_index = self.settings_manager.get_value('selected_mic_index', default=None, value_type=int)
        self.activation_threshold = self.settings_manager.get_value('activation_threshold', default=10, value_type=int)
        self.sound_enabled = self.settings_manager.get_value('sound_enabled', default=True, value_type=bool)
        self.autostart_enabled = self.settings_manager.get_value('autostart_enabled', default=False, value_type=bool)
        self.playful_behavior_probability = self.settings_manager.get_value('playful_behavior_probability', default=0.1, value_type=float)
        self.ground_level_setting = self.settings_manager.get_value('ground_level', default=0, value_type=int)
        self.skin_folder = self.settings_manager.get_value('skin_folder', default=None, value_type=str)
        self.selected_skin = self.settings_manager.get_value('selected_skin', default=None, value_type=str)
        self.base_duck_speed = self.settings_manager.get_value('duck_speed', default=2.0, value_type=float)
        self.duck_speed = self.base_duck_speed * (self.pet_size / 3)
        self.random_behavior = self.settings_manager.get_value('random_behavior', default=True, value_type=bool)
        self.idle_duration = self.settings_manager.get_value('idle_duration', default=5.0, value_type=float)
        self.direction_change_interval = self.settings_manager.get_value('direction_change_interval', default=20.0, value_type=float)
        self.name_offset_y = self.settings_manager.get_value('name_offset_y', default=60, value_type=int)
        self.font_base_size = self.settings_manager.get_value('font_base_size', default=14, value_type=int)
        self.is_listening = False
        self.listening_entry_timer = None
        self.listening_exit_timer = None
        self.exit_listening_timer = None
        self.facing_right = True

        screen = QtGui.QGuiApplication.primaryScreen()
        screen_rect = screen.geometry()
        self.screen_width = screen_rect.width()
        self.screen_height = screen_rect.height()

        self.show_name = self.settings_manager.get_value('show_name', default=False, value_type=bool)
        self.name_window = None

        self.current_frame = self.resources.get_animation_frame('idle', 0)
        if self.current_frame:
            self.duck_width = self.current_frame.width()
            self.duck_height = self.current_frame.height()
        else:
            self.duck_width = self.duck_height = 64

        self.resize(self.duck_width, self.duck_height)
        self.duck_x = (self.screen_width - self.duck_width) // 2
        self.duck_y = -self.duck_height

        self.has_jumped = False
        self.direction = 1
        self.ground_level = self.get_ground_level()

        self.state = FallingState(self)
        self.state.enter()

        self.setup_timers()
        self.apply_settings()

        self.microphone_listener = MicrophoneListener(
            device_index=self.selected_mic_index,
            activation_threshold=self.activation_threshold
        )
        self.microphone_listener.volume_signal.connect(self.on_volume_updated)
        self.microphone_listener.start()

        self.init_ui()
        self.setup_random_behavior()

        self.last_interaction_time = time.time()
        self.last_sound_time = QtCore.QTime.currentTime()

        self.tray_icon = SystemTrayIcon(self)
        self.tray_icon.show()

        self.current_volume = 0

        self.pet_name = self.settings_manager.get_value('pet_name', default="", value_type=str)
        if self.pet_name:
            self.seed = get_seed_from_name(self.pet_name)
            self.random_gen = random.Random(self.seed)
            self.generate_characteristics()
        else:
            self.seed = None
            self.random_gen = random.Random()
            self.set_default_characteristics()

        self.attack_timer = QtCore.QTimer()
        self.attack_timer.timeout.connect(self.check_attack_trigger)
        self.attack_timer.start(5000)

        self.run_timer = QtCore.QTimer()
        self.run_timer.timeout.connect(self.check_run_state_trigger)
        self.run_timer.start(5 * 60 * 1000)

        latest_release = self.updater.check_for_updates()
        if latest_release:
            notify_user_about_update(self, latest_release, manual_trigger=False)

        self.is_paused_for_fullscreen = False
        self.fullscreen_check_timer = QtCore.QTimer()
        self.fullscreen_check_timer.setInterval(4000)
        self.fullscreen_check_timer.timeout.connect(self.check_foreground_fullscreen_winapi)
        self.fullscreen_check_timer.start()

    def check_foreground_fullscreen_winapi(self):
        """
        Checks if the foreground window is truly fullscreen using WinAPI
        (GetForegroundWindow, GetWindowRect, MonitorFromWindow, etc.).
        If it is fullscreen (and not our own window), the duck is paused.
        Otherwise, it resumes.
        """
        if not sys.platform.startswith("win"):
            return

        hwnd_foreground = win32gui.GetForegroundWindow()
        if not hwnd_foreground:
            # No foreground window detected -> likely the desktop or similar
            if self.is_paused_for_fullscreen:
                self.resume_duck()
                self.is_paused_for_fullscreen = False
            return

        # Retrieve the class name and process name of the active window
        class_name = win32gui.GetClassName(hwnd_foreground)
        _, process_id = win32process.GetWindowThreadProcessId(hwnd_foreground)
        process_name = ""
        try:
            h_process = win32api.OpenProcess(win32con.PROCESS_QUERY_INFORMATION | win32con.PROCESS_VM_READ, False, process_id)
            exe_name = win32process.GetModuleFileNameEx(h_process, 0)
            process_name = os.path.basename(exe_name)
            win32api.CloseHandle(h_process)
        except Exception as e:
            logging.error(f"Failed to retrieve process name: {e}")

        # Check if the active window is the desktop (Explorer)
        if class_name in {"Progman", "WorkerW"} or process_name.lower() == "explorer.exe":
            # Resume the duck if paused for fullscreen
            if self.is_paused_for_fullscreen:
                self.resume_duck()
                self.is_paused_for_fullscreen = False
            return

        # Get window and monitor dimensions
        left, top, right, bottom = win32gui.GetWindowRect(hwnd_foreground)
        monitor = win32api.MonitorFromWindow(hwnd_foreground, win32con.MONITOR_DEFAULTTONEAREST)
        monitor_info = win32api.GetMonitorInfo(monitor)
        mon_left, mon_top, mon_right, mon_bottom = monitor_info["Monitor"]

        # Determine if the foreground window is fullscreen
        is_foreground_fullscreen = (
            left == mon_left and
            top == mon_top and
            right == mon_right and
            bottom == mon_bottom
        )

        if is_foreground_fullscreen:
            if not self.is_paused_for_fullscreen:
                logging.info("Fullscreen application detected — pausing the duck.")
                self.pause_duck()
                self.is_paused_for_fullscreen = True
        else:
            # Not fullscreen
            if self.is_paused_for_fullscreen:
                logging.info("Fullscreen application closed or minimized — resuming the duck.")
                self.resume_duck()
                self.is_paused_for_fullscreen = False

    def pause_duck(self, force_idle=False):
        """
        Stop all duck timers and optionally force duck to IdleState.
        If force_idle=False, we keep the existing state (Falling, Jumping, etc.)
        """
        if force_idle:
            if not isinstance(self.state, IdleState):
                self.stop_current_state()
                self.change_state(IdleState(self))

        # Stop timers so as not to load the CPU and not to update the duck
        self.animation_timer.stop()
        self.position_timer.stop()
        self.sound_timer.stop()
        self.sleep_timer.stop()
        self.direction_change_timer.stop()
        self.playful_timer.stop()
        self.random_behavior_timer.stop()
        self.hide()

    def resume_duck(self):
        """
        Resume the duck's normal timers after a pause.
        """
        self.animation_timer.start(100)
        self.position_timer.start(20)
        self.schedule_next_sound()
        self.sleep_timer.start(10000)
        self.direction_change_timer.start(int(self.direction_change_interval * 1000))
        self.playful_timer.start(10 * 60 * 1000)
        self.schedule_next_random_behavior()
        self.show()

    def get_top_non_opaque_offset(self):
        """
        Find the highest non-transparent pixel in the duck's current frame. 
        Returns a negative offset to show the name on top of the sprite.
        """
        if not self.current_frame:
            return 0
        image = self.current_frame.toImage()
        w = image.width()
        h = image.height()
        for y in range(h):
            for x in range(w):
                pixel = image.pixelColor(x, y)
                if pixel.alpha() > 0:
                    return -y
        return 0

    def check_for_updates(self):
        """
        Automatic check for updates using our AutoUpdater. 
        If a new release is available, notify the user.
        """
        latest_release = self.updater.check_for_updates()
        if latest_release:
            notify_user_about_update(self, latest_release, manual_trigger=False)
        else:
            logging.info("No new updates found automatically.")

    def check_for_updates_manual(self):
        """
        Manual check for updates (e.g. from a tray menu).
        """
        latest_release = self.updater.check_for_updates()
        if latest_release:
            notify_user_about_update(self, latest_release, manual_trigger=True)
        else:
            QMessageBox.information(
                self, 
                translations.get("no_updates_title", "No Updates"),
                translations.get("latest_version_message", "You already have the latest version installed.")
            )

    def set_skipped_version(self, version: str):
        """
        Store a 'skipped version' to avoid showing the update prompt 
        for this version in automatic checks.
        """
        self.skipped_version = version
        self.settings_manager.set_value('skipped_version', version)
        self.settings_manager.sync()

    def get_scale_factor(self):
        """
        Compute a scale factor based on a reference screen size (1920x1080).
        If the user has a bigger screen, the factor might be >1; 
        if smaller, we clamp it to 1.0 (no downscaling).
        """
        base_width = 1920
        base_height = 1080
        screen = QtWidgets.QApplication.primaryScreen()
        if screen is None:
            logging.warning("Could not get primary screen. Defaulting scale factor to 1.0.")
            return 1.0
        screen_rect = screen.size()
        scale_x = screen_rect.width() / base_width
        scale_y = screen_rect.height() / base_height
        scale_factor = min(scale_x, scale_y)
        if scale_factor < 1.0:
            scale_factor = 1.0
        logging.info(f"SCALE FACTOR: {scale_factor}")
        return scale_factor

    def check_playful_state(self):
        """
        Random chance to switch into PlayfulState (chasing the cursor), 
        unless the duck is jumping/falling/dragging/listening.
        """
        if random.random() < self.playful_behavior_probability:
            if not isinstance(self.state, (FallingState, DraggingState, ListeningState, JumpingState, PlayfulState)):
                self.stop_current_state()
                self.change_state(PlayfulState(self))

    def show_debug_window(self):
        """
        Show or create the debug window to tweak duck parameters in real time.
        """
        if self.debug_window is None:
            self.debug_window = DebugWindow(self)
            self.debug_window.destroyed.connect(self.on_debug_window_closed)
        self.debug_mode = True
        self.debug_window.show()
        self.debug_window.raise_()
        self.debug_window.activateWindow()

    def on_debug_window_closed(self):
        self.debug_window = None
        self.debug_mode = False

    def play_random_sound(self):
        """
        Plays a random sound file using the ResourceManager with proper error handling.
        Ensures that the sound file exists by copying it from the skin resource if necessary.
        """
        try:
            # Retrieve a random sound from the ResourceManager
            sound_file = self.resources.get_random_sound()
            if not sound_file:
                logging.warning("No sound files available to play.")
                return

            # Проверяем, что файл существует на диске
            if not os.path.exists(sound_file):
                logging.warning(f"Sound file {sound_file} not found. Attempting to copy from skin resources.")
                # Пытаемся найти исходный файл звука в директории скина
                # Предполагается, что ResourceManager хранит путь к текущему скину
                source_skin_dir = self.resources.current_skin_temp_dir
                if not source_skin_dir:
                    logging.error("Source skin directory is not set. Cannot copy sound file.")
                    return

                # Извлекаем имя файла звука из пути
                sound_filename = os.path.basename(sound_file)
                source_sound_path = os.path.join(source_skin_dir, sound_filename)

                if not os.path.exists(source_sound_path):
                    logging.error(f"Source sound file {source_sound_path} does not exist. Cannot copy.")
                    return

                try:
                    shutil.copy(source_sound_path, sound_file)
                    logging.info(f"Copied sound file from {source_sound_path} to {sound_file}.")
                except Exception as e:
                    logging.error(f"Failed to copy sound file: {e}")
                    return

            logging.info(f"Attempting to play sound: {sound_file}")
            url = QtCore.QUrl.fromLocalFile(sound_file)
            self.sound_effect.setSource(url)

            def play_if_ready():
                status = self.sound_effect.status()
                if status == QSoundEffect.Status.Ready:
                    self.sound_effect.play()
                    logging.info("Sound playback started successfully.")
                    try:
                        self.sound_effect.statusChanged.disconnect(play_if_ready)
                    except Exception:
                        pass
                elif status == QSoundEffect.Status.Error:
                    logging.error(f"Sound effect failed to load for {sound_file}")
                    try:
                        self.sound_effect.statusChanged.disconnect(play_if_ready)
                    except Exception:
                        pass

            self.sound_effect.statusChanged.connect(lambda *_: play_if_ready())
            play_if_ready()
            if self.sound_effect.status() != QSoundEffect.Status.Ready:
                logging.warning("Sound not yet loaded, will retry in 500ms.")
                QTimer.singleShot(500, play_if_ready)

        except Exception as e:
            logging.error(f"Error playing sound: {e}")

    def mouseReleaseEvent(self, event):
        self.state.handle_mouse_release(event)

    def mouseMoveEvent(self, event):
        self.state.handle_mouse_move(event)

    def get_name_characteristics(self, name):
        """
        Generate and return random duck characteristics based on a user-provided name.
        Used for a user info tooltip in the settings.
        """
        seed_val = get_seed_from_name(name)
        random_gen = random.Random(seed_val)
        movement_speed = random_gen.uniform(1.5, 2)
        sound_interval_min = 60 + random_gen.random() * (300 - 60)
        sound_interval_max = 301 + random_gen.random() * (900 - 301)
        if sound_interval_min >= sound_interval_max:
            sound_interval_min, sound_interval_max = sound_interval_max, sound_interval_min

        sound_response_probability = 0.01 + random_gen.random() * (0.25 - 0.01)
        playful_behavior_probability = 0.1 + random_gen.random() * (0.5 - 0.1)
        sleep_timeout = (5 + random_gen.random() * 10) * 60

        characteristics = {
            translations.get("movement_speed", "Movement speed"): f"{movement_speed:.2f}",
            translations.get("minimal_sound_interval", "Min. sound interval"): f"{sound_interval_min/60:.2f} " + translations.get("minutes", "min."),
            translations.get("miximal_sound_interval", "Max. sound interval"): f"{sound_interval_max/60:.2f} " + translations.get("minutes", "min."),
            translations.get("probability_response_to_sound", "Probability of response to sound"): f"{sound_response_probability*100:.2f}%",
            translations.get("probability_of_playfulness", "Probability of playfulness"): f"{playful_behavior_probability*100:.2f}%",
            translations.get("sleep_timeout", "Sleep timeout"): f"{sleep_timeout/60:.2f} " + translations.get("minutes", "min."),
        }
        return characteristics

    def generate_characteristics(self):
        """
        Generate random duck characteristics based on self.random_gen. 
        Called when the user enters a pet name, or loads from settings.
        """
        self.movement_speed = self.random_gen.uniform(0.8, 1.5)
        self.base_duck_speed = self.movement_speed
        self.sound_interval_min = 60 + self.random_gen.random() * (300 - 60)
        self.sound_interval_max = 301 + self.random_gen.random() * (900 - 301)
        if self.sound_interval_min >= self.sound_interval_max:
            self.sound_interval_min, self.sound_interval_max = self.sound_interval_max, self.sound_interval_min

        self.sound_response_probability = 0.01 + self.random_gen.random() * (0.25 - 0.01)
        self.playful_behavior_probability = 0.1 + self.random_gen.random() * (0.5 - 0.1)
        self.sleep_timeout = (5 + self.random_gen.random() * 10) * 60

    def set_default_characteristics(self):
        """
        If no pet name is set, we use default duck characteristics.
        """
        self.movement_speed = 1.25
        self.base_duck_speed = self.movement_speed
        self.sound_interval_min = 120
        self.sound_interval_max = 600
        self.sound_response_probability = 0.01
        self.playful_behavior_probability = 0.1
        self.sleep_timeout = 300

    def mouseDoubleClickEvent(self, event):
        """
        On left mouse double-click, create a small "heart" animation.
        """
        if event.button() == Qt.MouseButton.LeftButton:
            self.create_heart()

    def create_heart(self):
        """
        Spawn a small heart sprite above the duck.
        """
        if hasattr(self, 'heart_window') and self.heart_window:
            try:
                self.heart_window.close()
                self.heart_window.deleteLater()
            except Exception as e:
                logging.warning(f"Failed to safely delete HeartWindow: {e}")
            finally:
                self.heart_window = None

        heart_x = self.duck_x + self.current_frame.width() / 2
        heart_y = self.duck_y
        self.heart_window = HeartWindow(heart_x, heart_y)

    def init_ui(self):
        """
        Set up window flags (frameless, top-most, etc.) and show the duck.
        """
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setCursor(QtGui.QCursor(Qt.CursorShape.PointingHandCursor))
        self.resize(self.duck_width, self.duck_height)
        self.move(int(self.duck_x), int(self.duck_y))
        self.show()

    def setup_timers(self):
        """
        Create the main QTimers for animation updates, position updates, sound triggers, etc.
        """
        self.animation_timer = QtCore.QTimer()
        self.animation_timer.timeout.connect(self.update_animation)
        self.animation_timer.start(100)

        self.position_timer = QtCore.QTimer()
        self.position_timer.timeout.connect(self.update_position)
        self.position_timer.start(20)

        self.sound_timer = QtCore.QTimer()
        self.sound_timer.timeout.connect(self.play_random_sound)
        self.schedule_next_sound()

        self.sleep_timer = QtCore.QTimer()
        self.sleep_timer.timeout.connect(self.check_sleep)
        self.sleep_timer.start(10000)

        self.direction_change_timer = QtCore.QTimer()
        self.direction_change_timer.timeout.connect(self.change_direction)
        self.direction_change_timer.start(int(self.direction_change_interval * 1000))

        self.playful_timer = QtCore.QTimer()
        self.playful_timer.timeout.connect(self.check_playful_state)
        self.playful_timer.start(10 * 60 * 1000)

    def setup_random_behavior(self):
        """
        Prepare the random behavior timer for occasional idle and direction changes.
        """
        self.random_behavior_timer = QtCore.QTimer()
        self.random_behavior_timer.timeout.connect(self.perform_random_behavior)
        self.schedule_next_random_behavior()

    def schedule_next_random_behavior(self):
        interval = random.randint(20000, 40000)
        self.random_behavior_timer.start(interval)

    def perform_random_behavior(self):
        """
        Perform a random behavior from a small list, e.g. random Idle or direction change.
        """
        behaviors = [self.enter_random_idle_state, self.change_direction]
        behavior = random.choice(behaviors)
        behavior()
        self.schedule_next_random_behavior()

    def check_run_state_trigger(self):
        """
        Occasionally switch to RunState if there's a 'running' animation defined, with a small chance.
        """
        running_frames = self.resources.get_animation_frames_by_name('running')
        if running_frames:
            chance = self.random_gen.uniform(0.01, 0.05)
            if random.random() < chance:
                if not isinstance(self.state, (FallingState, DraggingState, ListeningState, JumpingState, PlayfulState, RunState, AttackState)):
                    self.change_state(RunState(self))

    def can_attack(self):
        """
        Decide if the duck can attack the cursor based on current state, 
        presence of an 'attack' animation, and distance to cursor.
        """
        if not isinstance(self.state, (WalkingState, IdleState)):
            return False
        attack_frames = self.resources.get_animation_frames_by_name('attack')
        if attack_frames:
            cursor_pos = QtGui.QCursor.pos()
            duck_pos = self.pos()
            duck_center = duck_pos + self.rect().center()

            base_attack_distance = 50
            attack_distance = base_attack_distance * (self.pet_size / 3)

            dist = ((cursor_pos.x() - duck_center.x())**2 + (cursor_pos.y() - duck_center.y())**2)**0.5
            if dist < attack_distance:
                chance = self.random_gen.uniform(0.01, 0.2)
                if random.random() < chance:
                    if cursor_pos.x() < duck_center.x():
                        self.facing_right = False
                    else:
                        self.facing_right = True
                    return True
        return False

    def check_attack_trigger(self):
        """
        Timer-based check for attacks. If duck can attack, we switch state to AttackState.
        """
        if not isinstance(self.state, (FallingState, JumpingState, AttackState)):
            if self.can_attack():
                self.change_state(AttackState(self))

    def enter_random_idle_state(self):
        """
        Switch to IdleState if not currently falling/dragging, 
        for some random variation in duck behavior.
        """
        if not isinstance(self.state, IdleState) and not isinstance(self.state, (FallingState, DraggingState)):
            self.change_state(IdleState(self))

    def change_direction(self):
        """
        Flip duck direction horizontally.
        """
        self.direction *= -1
        self.facing_right = (self.direction == 1)

    def change_state(self, new_state, event=None):
        old_state_name = self.state.__class__.__name__ if self.state else "None"

        # Protection against repeated calls
        if getattr(self, "_is_changing_state", False):
            logging.warning("The previous state change has not yet completed, skip it.")
            return
        self._is_changing_state = True

        try:
            if self.state:
                self.state.exit()
            self.state = new_state
            self.state.enter()
            if event:
                self.state.handle_mouse_press(event)

            # Start/stop cursor_shake_timer
            if isinstance(self.state, (IdleState, WalkingState)):
                self.start_cursor_shake_detection()
            else:
                self.stop_cursor_shake_detection()

            new_state_name = self.state.__class__.__name__ if self.state else "None"
            self.state_history.append((time.strftime("%H:%M:%S"), old_state_name, new_state_name))
            if len(self.state_history) > 10:
                self.state_history.pop(0)
        except Exception as e:
            logging.error(f"Error while changing state: {e}")
        finally:
            self._is_changing_state = False

    def start_cursor_shake_detection(self):
        self.cursor_positions = []
        self.cursor_shake_timer.start(50)

    def stop_cursor_shake_detection(self):
        self.cursor_shake_timer.stop()
        self.cursor_positions = []

    def check_cursor_shake(self):
        """
        Accumulate the last second of cursor positions to see 
        if there's rapid back-and-forth movement near the duck 
        -> triggers PlayfulState.
        """
        cursor_pos = QtGui.QCursor.pos()
        duck_pos = self.pos()
        duck_rect = self.rect()
        duck_center = duck_pos + duck_rect.center()
        dx = cursor_pos.x() - duck_center.x()
        dy = cursor_pos.y() - duck_center.y()
        distance = (dx**2 + dy**2)**0.5

        base_distance = 50
        distance_threshold = base_distance * (self.pet_size / 3)

        if distance <= distance_threshold:
            current_time = time.time()
            self.cursor_positions.append((current_time, cursor_pos))
            # Keep only positions within 1 second.
            self.cursor_positions = [(t, pos) for t, pos in self.cursor_positions if current_time - t <= 1.0]
            if len(self.cursor_positions) >= 8:
                direction_changes = 0
                for i in range(2, len(self.cursor_positions)):
                    prev_dx = self.cursor_positions[i-1][1].x() - self.cursor_positions[i-2][1].x()
                    prev_dy = self.cursor_positions[i-1][1].y() - self.cursor_positions[i-2][1].y()
                    curr_dx = self.cursor_positions[i][1].x() - self.cursor_positions[i-1][1].x()
                    curr_dy = self.cursor_positions[i][1].y() - self.cursor_positions[i-1][1].y()
                    if (prev_dx * curr_dx < 0) or (prev_dy * curr_dy < 0):
                        direction_changes += 1
                if direction_changes >= 4:
                    self.stop_cursor_shake_detection()
                    self.change_state(PlayfulState(self))
        else:
            self.cursor_positions = []

    def update_animation(self):
        """
        Called by self.animation_timer. Tells current state to update its frames.
        """
        try:
            if self.state:
                self.state.update_animation()
        except Exception as e:
            logging.error(f"Error in update_animation: {e}")

    def update_position(self):
        try:
            if self.state:
                self.state.update_position()
        except Exception as e:
            logging.error(f"Error in update_position: {e}")
            return

        if hasattr(self, 'heart_window') and self.heart_window:
            try:
                self.heart_window.update()
            except RuntimeError:
                logging.warning("HeartWindow has been deleted already.")
                self.heart_window = None

        if self.name_window and self.show_name and self.pet_name.strip():
            self.name_window.update_position()

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        if self.current_frame:
            painter.drawPixmap(0, 0, self.current_frame)

        # If in debug mode, draw a bounding box and coordinates.
        if self.debug_mode:
            painter.setPen(QtGui.QPen(QtGui.QColorConstants.Red, 2, Qt.PenStyle.SolidLine))
            painter.drawRect(0, 0, self.duck_width-1, self.duck_height-1)
            painter.setPen(QtGui.QPen(QtGui.QColor("yellow"), 1))
            coord_text = f"X:{self.duck_x}, Y:{self.duck_y}"
            painter.drawText(5, 15, coord_text)
        painter.end()

    def mousePressEvent(self, event):
        """
        Save last interaction time (for auto-sleep logic),
        then pass the mouse press event to the current state.
        """
        self.last_interaction_time = time.time()
        self.state.handle_mouse_press(event)

    def mouseReleaseEvent(self, event):
        """
        The duck's current state can handle mouse release, e.g. in DraggingState.
        """
        self.state.handle_mouse_release(event)

    def mouseMoveEvent(self, event):
        """
        The duck's current state can handle mouse dragging, etc.
        """
        self.state.handle_mouse_move(event)

    def get_ground_level(self):
        """
        Calculate the ground level (bottom screen minus user-specified ground_level_setting).
        """
        screen = QtGui.QGuiApplication.primaryScreen()
        screen_rect = screen.geometry()
        ground_offset = self.ground_level_setting
        return screen_rect.height() - ground_offset

    def update_ground_level(self, new_ground_level):
        """
        Update ground level and handle if the duck is above or below it.
        """
        self.ground_level_setting = new_ground_level
        self.settings_manager.set_value('ground_level', new_ground_level)
        self.ground_level = self.get_ground_level()

        if self.duck_y + self.duck_height > self.ground_level:
            self.duck_y = self.ground_level - self.duck_height
            self.move(int(self.duck_x), int(self.duck_y))
        elif self.duck_y + self.duck_height < self.ground_level:
            self.change_state(FallingState(self))

    def check_sleep(self):
        """
        If the duck is idle for too long, it enters SleepingState (unless it's jumping, dragging, etc.).
        """
        elapsed = time.time() - self.last_interaction_time
        if elapsed >= self.sleep_timeout:
            if not isinstance(self.state, SleepingState):
                if not isinstance(self.state, (FallingState, DraggingState, ListeningState, JumpingState, PlayfulState)):
                    self.stop_current_state()
                    self.change_state(SleepingState(self))

    def on_volume_updated(self, volume):
        """
        Called from MicrophoneListener's volume_signal.
        If volume is above threshold, potentially switch to ListeningState.
        """
        self.current_volume = volume

        if volume > self.activation_threshold:
            self.last_interaction_time = time.time()
            if self.listening_exit_timer:
                self.listening_exit_timer.stop()
                self.listening_exit_timer = None
                logging.debug("ListeningState exit timer stopped.")

            if not self.is_listening and not self.listening_entry_timer:
                if not isinstance(self.state, PlayfulState) and not isinstance(self.state, JumpingState) and not isinstance(self.state, LandingState):
                    self.listening_entry_timer = QtCore.QTimer()
                    self.listening_entry_timer.setSingleShot(True)
                    self.listening_entry_timer.timeout.connect(self.enter_listening_state)
                    self.listening_entry_timer.start(100)
                    logging.debug("ListeningState entry timer started for 100ms.")
                else:
                    logging.info("Duck is in PlayfulState. Will not enter ListeningState.")
        else:
            # If volume is below threshold, stop any pending entry to listening:
            if self.listening_entry_timer:
                self.listening_entry_timer.stop()
                self.listening_entry_timer = None
                logging.debug("ListeningState entry timer stopped.")

            # If we are in ListeningState, start an exit timer if not set.
            if self.is_listening and not self.listening_exit_timer:
                self.listening_exit_timer = QtCore.QTimer()
                self.listening_exit_timer.setSingleShot(True)
                self.listening_exit_timer.timeout.connect(self.exit_listening_state)
                self.listening_exit_timer.start(1000)
                logging.debug("ListeningState exit timer started for 1 second.")

    def stop_current_state(self):
        """
        Cleanly exit the current state before switching or resetting.
        """
        if self.state:
            try:
                self.state.exit()
            except Exception as e:
                logging.error(f"Error exiting current state: {e}")
            self.state = None

    def enter_listening_state(self):
        logging.info("Entering ListeningState.")
        self.listening_entry_timer = None
        if not self.is_listening:
            if isinstance(self.state, (JumpingState, FallingState, DraggingState)):
                logging.info("Rejected entering ListeningState due to current state.")
                return
            self.stop_current_state()
            self.change_state(ListeningState(self))
            self.is_listening = True
            logging.info("Duck is now in ListeningState.")

    def exit_listening_state(self):
        logging.info("Exiting ListeningState.")
        self.listening_exit_timer = None
        if self.is_listening:
            self.is_listening = False
            self.change_state(WalkingState(self))
            logging.info("Duck switched to WalkingState after leaving ListeningState.")

    def schedule_next_sound(self):
        """
        Randomly schedule the next quack in 2-10 minutes if sound is enabled.
        """
        interval = random.randint(120000, 600000)
        self.sound_timer.start(interval)

    def open_settings(self):
        """
        If the settings window is already open, bring it to the front; otherwise create and show it.
        """
        if hasattr(self, 'settings_manager_window') and self.settings_manager_window is not None:
            if self.settings_manager_window.isVisible():
                self.settings_manager_window.raise_()
                self.settings_manager_window.activateWindow()
            else:
                self.settings_manager_window.show()
        else:
            self.settings_manager_window = SettingsWindow(self)
            self.settings_manager_window.show()

            self.settings_manager_window.destroyed.connect(self.clear_settings_window)

    def clear_settings_window(self):
        """
        Clear the reference to the settings window when it is closed.
        """
        self.settings_manager_window = None

    def unstuck_duck(self):
        """
        Center the duck horizontally at the ground level. 
        Useful if the duck goes off-screen or behind other windows.
        """
        self.duck_x = (self.screen_width - self.duck_width) // 2
        self.duck_y = self.ground_level - self.duck_height
        self.move(int(self.duck_x), int(self.duck_y))
        if not isinstance(self.state, FallingState):
            self.change_state(WalkingState(self))

    def closeEvent(self, event):
        """
        Stop microphone listener and then allow the app to close.
        """
        if hasattr(self, 'heart_window') and self.heart_window:
            self.heart_window.deleteLater()
        self.microphone_listener.stop()
        self.microphone_listener.wait()
        event.accept()

    def load_settings(self) -> None:
        """
        Load user settings from SettingsManager to the Duck's fields.
        """
        self.pet_name = self.settings_manager.get_value('pet_name', default="", value_type=str)
        self.selected_mic_index = self.settings_manager.get_value('selected_mic_index', default=None, value_type=int)
        self.activation_threshold = self.settings_manager.get_value('activation_threshold', default=1, value_type=int)
        self.sound_response_probability = self.settings_manager.get_value('sound_response_probability', default=0.01, value_type=float)
        self.sound_enabled = self.settings_manager.get_value('sound_enabled', default=True, value_type=bool)
        self.autostart_enabled = self.settings_manager.get_value('autostart_enabled', default=False, value_type=bool)
        self.playful_behavior_probability = self.settings_manager.get_value('playful_behavior_probability', default=0.1, value_type=float)
        self.ground_level_setting = self.settings_manager.get_value('ground_level', default=0, value_type=int)
        self.ground_level = self.get_ground_level()
        self.pet_size = self.settings_manager.get_value('pet_size', default=3, value_type=int)
        self.skin_folder = self.settings_manager.get_value('skin_folder', default=None, value_type=str)
        self.selected_skin = self.settings_manager.get_value('selected_skin', default=None, value_type=str)
        self.base_duck_speed = self.settings_manager.get_value('duck_speed', default=2.0, value_type=float)
        self.duck_speed = self.base_duck_speed * (self.pet_size / 3)
        self.random_behavior = self.settings_manager.get_value('random_behavior', default=True, value_type=bool)
        self.idle_duration = self.settings_manager.get_value('idle_duration', default=5.0, value_type=float)
        self.sleep_timeout = self.settings_manager.get_value('sleep_timeout', default=300.0, value_type=float)
        self.direction_change_interval = self.settings_manager.get_value('direction_change_interval', default=20.0, value_type=float)
        self.name_offset_y = self.settings_manager.get_value('name_offset_y', default=60, value_type=int)
        self.font_base_size = self.settings_manager.get_value('font_base_size', default=14, value_type=int)
        self.current_language = self.settings_manager.get_value('current_language', default='en', value_type=str)
        self.skipped_version = self.settings_manager.get_value('skipped_version', default="", value_type=str)
        self.show_name = self.settings_manager.get_value('show_name', default=False, value_type=bool)
        self.sound_volume = self.settings_manager.get_value('sound_volume', default=0.5, value_type=float)
        self.sound_effect.setVolume(self.sound_volume)

        # Reload translations after we know the user language.
        set_language(self.current_language)

        # If there's a pet name, generate random characteristics from that. Otherwise defaults.
        if self.pet_name.strip():
            self.seed = get_seed_from_name(self.pet_name)
            self.random_gen = random.Random(self.seed)
            self.generate_characteristics()
        else:
            self.seed = None
            self.random_gen = random.Random()
            self.set_default_characteristics()

    def save_settings(self) -> None:
        """
        Persist all current Duck settings to the SettingsManager.
        """
        self.settings_manager.set_value('pet_name', self.pet_name)
        self.settings_manager.set_value('selected_mic_index', self.selected_mic_index)
        self.settings_manager.set_value('activation_threshold', self.activation_threshold)
        self.settings_manager.set_value('sound_enabled', self.sound_enabled)
        self.settings_manager.set_value('autostart_enabled', self.autostart_enabled)
        self.settings_manager.set_value('ground_level', self.ground_level_setting)
        self.settings_manager.set_value('pet_size', self.pet_size)
        self.settings_manager.set_value('skin_folder', self.skin_folder)
        self.settings_manager.set_value('selected_skin', self.selected_skin)
        self.settings_manager.set_value('duck_speed', self.base_duck_speed)
        self.settings_manager.set_value('random_behavior', self.random_behavior)
        self.settings_manager.set_value('idle_duration', self.idle_duration)
        self.settings_manager.set_value('sleep_timeout', self.sleep_timeout)
        self.settings_manager.set_value('direction_change_interval', self.direction_change_interval)
        self.settings_manager.set_value('current_language', self.current_language)
        self.settings_manager.set_value('show_name', self.show_name)

        if not self.pet_name:
            self.settings_manager.set_value('sleep_timeout', self.sleep_timeout)
        self.settings_manager.sync()

    def apply_settings(self):
        """
        Apply the duck's settings (like skin, size, speed, name) 
        and update the UI if necessary.
        """
        self.update_duck_name()
        self.update_pet_size(self.pet_size)
        self.update_ground_level(self.ground_level_setting)

        # Load the selected skin, or default if none is chosen.
        if self.selected_skin is None:
            logging.info("Loading default skin because selected_skin is None.")
            self.resources.load_default_skin(lazy=False)
        elif self.selected_skin and self.selected_skin != self.resources.current_skin:
            logging.info(f"Loading selected skin: {self.selected_skin}")
            self.resources.load_skin(self.selected_skin)

        # Update the duck's visual appearance (e.g. force re-check of the idle frame).
        self.update_duck_skin()

        # Autostart logic
        if self.autostart_enabled:
            self.enable_autostart()
        else:
            self.disable_autostart()

        self.update_name_offset(self.name_offset_y)
        self.update_font_base_size(self.font_base_size)

        # Save so changes persist.
        self.save_settings()

        # Update speed and timers after applying new settings.
        self.duck_speed = self.base_duck_speed * (self.pet_size / 3)
        self.animation_timer.setInterval(100)

        self.direction_change_timer.stop()
        self.direction_change_timer.start(int(self.direction_change_interval * 1000))

        # Update name window if needed.
        if self.show_name and self.pet_name.strip() and self.isVisible():
            if not self.name_window:
                self.name_window = NameWindow(self)
            else:
                self.name_window.update_label()
                self.name_window.show()
        else:
            if self.name_window:
                self.name_window.hide()

    def update_name_offset(self, offset):
        self.name_offset_y = offset
        self.settings_manager.set_value('name_offset_y', offset)
        if self.name_window and self.show_name and self.pet_name.strip():
            self.name_window.update_position()

    def update_font_base_size(self, base_size):
        self.font_base_size = base_size
        self.settings_manager.set_value('font_base_size', base_size)
        if self.name_window and self.show_name and self.pet_name.strip():
            self.name_window.update_label()

    def update_pet_size(self, size_factor):
        """
        Change the duck's sprite scale and re-initialize frames, 
        so we forcibly exit and re-enter the current state to fix the animation frames.
        """
        self.pet_size = size_factor
        self.duck_speed = self.base_duck_speed * (self.pet_size / 3)
        self.resources.set_pet_size(self.pet_size)

        self.resources.load_sprites_now(force_reload=True)

        old_width = self.duck_width
        old_height = self.duck_height

        self.current_frame = self.resources.get_animation_frame('idle', 0)
        if not self.current_frame:
            self.current_frame = self.resources.get_default_frame()
        if not self.current_frame:
            self.duck_width = self.duck_height = 64
        else:
            self.duck_width = self.current_frame.width()
            self.duck_height = self.current_frame.height()

        delta_width = self.duck_width - old_width
        delta_height = self.duck_height - old_height

        self.duck_x -= delta_width / 2
        self.duck_y -= delta_height / 2

        self.resize(self.duck_width, self.duck_height)
        self.move(int(self.duck_x), int(self.duck_y))

        current_state_class = self.state.__class__
        self.state.exit()
        self.state = current_state_class(self)
        self.state.enter()

        if hasattr(self.state, 'update_frame'):
            self.state.update_frame()

        if self.name_window:
            self.name_window.update_label()

    def update_duck_skin(self):
        """
        Reload frames for the currently selected skin, re-enter the state to refresh animations.
        """
        self.current_frame = self.resources.get_animation_frame('idle', 0)
        if self.current_frame:
            self.duck_width = self.current_frame.width()
            self.duck_height = self.current_frame.height()
            self.resize(self.duck_width, self.duck_height)
            self.update()

        if self.state:
            self.state.exit()
            self.state.enter()

    def reset_settings(self):
        """
        Clear all settings from SettingsManager, then reload default or from new user input.
        """
        self.settings_manager.clear()
        self.load_settings()
        self.apply_settings()

    def enable_autostart(self):
        """
        Register the application to run at system startup (Windows-only).
        """
        if sys.platform == 'win32':
            exe_path = os.path.realpath(sys.argv[0])
            try:
                key = winreg.OpenKey(
                    winreg.HKEY_CURRENT_USER,
                    r"Software\Microsoft\Windows\CurrentVersion\Run",
                    0, winreg.KEY_SET_VALUE
                )
                winreg.SetValueEx(key, 'QuackDuck', 0, winreg.REG_SZ, exe_path)
                winreg.CloseKey(key)
            except Exception as e:
                logging.error(f"Failed to enable autostart: {e}")

    def disable_autostart(self):
        """
        Remove the application from system startup (Windows-only).
        """
        if sys.platform == 'win32':
            try:
                key = winreg.OpenKey(
                    winreg.HKEY_CURRENT_USER,
                    r"Software\Microsoft\Windows\CurrentVersion\Run",
                    0, winreg.KEY_SET_VALUE
                )
                winreg.DeleteValue(key, 'QuackDuck')
                winreg.CloseKey(key)
            except FileNotFoundError:
                pass
            except Exception as e:
                logging.error(f"Failed to disable autostart: {e}")

    def update_duck_name(self):
        """
        If there's a pet name, generate random characteristics from it; 
        otherwise default to standard values. Also update the name label if visible.
        """
        if self.pet_name:
            self.seed = get_seed_from_name(self.pet_name)
            self.random_gen = random.Random(self.seed)
            self.generate_characteristics()
        else:
            self.seed = None
            self.random_gen = random.Random()
            self.set_default_characteristics()

        if self.name_window:
            self.name_window.update_label()

    def get_input_devices(self):
        """
        Query available audio input devices via sounddevice.
        """
        input_devices = []
        try:
            devices = sd.query_devices()
            for idx, device in enumerate(devices):
                if device['max_input_channels'] > 0:
                    device_name = device['name']
                    input_devices.append((idx, device_name))
        except Exception as e:
            logging.error(f"Error querying devices: {e}")
        if not input_devices:
            logging.error("No input devices found.")
        return input_devices

    def restart_microphone_listener(self):
        """
        Stop and restart the microphone listener, e.g. if the user changes the input device.
        """
        self.microphone_listener.stop()
        self.microphone_listener.wait()
        self.microphone_listener = MicrophoneListener(
            device_index=self.selected_mic_index,
            activation_threshold=self.activation_threshold
        )
        self.microphone_listener.volume_signal.connect(self.on_volume_updated)
        self.microphone_listener.start()
