# TODO
# Test updater

# Anticipating the question, 'Why is all the code in one file?'
# I'll give a straightforward answer:
# When you're working solo on a large project, you don't want to crawl through
# tons of folders and files just to fix a single function.
# It's easier when you can see the whole picture in one place.

# I set the variable value higher whenever negative thoughts about this project come up.
# IHateThisIdeaCounter: int = int("".join(map(str, [9] * len(str(9))))) // len(str(9))

import hashlib
import inspect
import json
import logging
import os
import platform
import random
import shutil
import sounddevice as sd
import sys
import tempfile
import time
import traceback
import webbrowser
import zipfile
import numpy as np

if sys.platform == 'win32':
    import winreg
    import win32api
    import win32con
    import win32gui

from abc import ABC, abstractmethod
from autoupdater import AutoUpdater
from typing import Dict, List, Optional, Tuple

from PyQt5 import QtCore, QtGui, QtMultimedia, QtWidgets
from PyQt5.QtCore import QPoint, QRect, QSize, Qt, QTimer, QUrl
from PyQt5.QtGui import QColor, QDesktopServices, QFont, QIcon, QMouseEvent, QPixmap
from PyQt5.QtMultimedia import QSoundEffect
from PyQt5.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QDoubleSpinBox, QFileDialog,
    QFrame, QFormLayout, QGridLayout, QGroupBox, QHBoxLayout, QLabel,
    QLayout, QLineEdit, QListWidget, QMainWindow, QMessageBox, 
    QPushButton, QProgressBar, QScrollArea, QSlider, QSpinBox, QStackedWidget,
    QTabWidget, QTextEdit, QVBoxLayout, QWidget, QSizePolicy
)

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s %(levelname)s:%(message)s',
    handlers=[
        logging.FileHandler(os.path.join(os.path.expanduser('~'), 'quackduck.log'), encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

# PROJECT VERSION
PROJECT_VERSION = '1.5.0'

GLOBAL_DEBUG_MODE = False

APP_NAME = 'QuackDuck'
APP_EXECUTABLE = 'quackduck.exe'

CURRENT_DIR = os.path.join(os.path.expanduser('~'), 'quackduck', 'current')
BACKUP_DIR = os.path.join(os.path.expanduser('~'), 'quackduck', 'backup')

os.makedirs(CURRENT_DIR, exist_ok=True)
os.makedirs(BACKUP_DIR, exist_ok=True)

def log_call_stack():
    stack = inspect.stack()
    for frame in stack[1:]:
        logging.info(f"Called by {frame.function} in {frame.filename} at line {frame.lineno}")

def resource_path(relative_path):
    """Receives an absolute path to a resource file, works both in development mode and after packaging with Pyinstaller."""
    try:
        # Pyinstaller creates a temporary folder and keeps the way to _meipass
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def load_translation(lang_code):
    try:
        lang_path = resource_path(os.path.join('languages', f'lang_{lang_code}.json'))
        with open(lang_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        logging.error(f"File {lang_path} not found.")
        return {}

# Languages: en / ru
current_language = 'en'
translations = load_translation(current_language)

def notify_user_about_update(duck, latest_release, manual_trigger=False):
    """
    Show a window with a suggestion to update or skip the version.
    When "Yes" is click > launch a new autoupdater.
    """
    latest_version = latest_release['tag_name'].lstrip('v')
    release_notes = latest_release.get('body', '')

    # If the version was previously skipped and this is NOT a manual check, we leave
    if duck.skipped_version == latest_version and not manual_trigger:
        return

    msg = QMessageBox(duck)
    msg.setWindowTitle(translations.get("update_available", "Update available"))

    message_template = translations.get(
        "new_version_available_text",
        f"A new version {latest_version} is available\n\nWhat's new:\n{release_notes}\n\nDo you want to install the new update?"
    )
    message = message_template.format(latest_version=latest_version, release_notes=release_notes)
    msg.setText(message)

    yes_button = msg.addButton(translations.get("yes", "Yes"), QMessageBox.YesRole)
    no_button = msg.addButton(translations.get("no", "No"), QMessageBox.NoRole)
    skip_button = msg.addButton(translations.get("skip_this_version", "Skip this version"), QMessageBox.ActionRole)
    msg.setDefaultButton(yes_button)

    msg.exec_()

    clicked_button = msg.clickedButton()
    if clicked_button == yes_button:
        success = duck.updater.download_and_install(latest_release, CURRENT_DIR, BACKUP_DIR)
        if success:
            QMessageBox.information(
                duck,
                translations.get("update_success", "Successfully updated"),
                translations.get("update_success_app_will_be_restarted", 
                                 "The update has been installed successfully. The application will be restarted.")
            )
            exe_path = os.path.join(CURRENT_DIR, APP_EXECUTABLE)
            duck.updater.restart_app(exe_path)
            duck.close()
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

def get_system_accent_color():
    if sys.platform == 'win32':
        try:
            registry = winreg.ConnectRegistry(None, winreg.HKEY_CURRENT_USER)
            key = winreg.OpenKey(registry, r'SOFTWARE\Microsoft\Windows\DWM', 0, winreg.KEY_READ)
            accent_color, regtype = winreg.QueryValueEx(key, 'AccentColor')
            winreg.CloseKey(key)
            a = (accent_color >> 24) & 0xFF
            r = (accent_color >> 16) & 0xFF
            g = (accent_color >> 8) & 0xFF
            b = accent_color & 0xFF
            return QColor(r, g, b, a)
        except Exception as e:
            logging.error(f"Failed to get system accent color: {e}")
            return QColor(5, 184, 204)
    else:
        return QColor(5, 184, 204)

def exception_handler(exctype, value, tb):
    error_message = ''.join(traceback.format_exception(exctype, value, tb))
    crash_log_path = os.path.join(os.path.expanduser('~'), 'quackduck_crash.log')

    # Collect information about the system
    system_info = (
        f"System Information:\n"
        f"OS: {platform.system()} {platform.release()} ({platform.version()})\n"
        f"Machine: {platform.machine()}\n"
        f"Processor: {platform.processor()}\n"
        f"Python Version: {platform.python_version()}\n\n"
    )

    # Record to the log file
    with open(crash_log_path, 'w') as f:
        f.write(system_info)
        f.write(error_message)

    # Record in the system log
    logging.error(system_info + error_message)

    # Check if there is a QApplication copy
    if QtWidgets.QApplication.instance() is not None:
        # Show the message to the user via QMessagebox
        msg = QtWidgets.QMessageBox()
        msg.setIcon(QtWidgets.QMessageBox.Critical)
        msg.setWindowTitle(translations.get("error_title", "Error!"))
        msg.setText(translations.get("application_error", "The application encountered an error:") + f" \n{value}")
        msg.setDetailedText(system_info + error_message)
        msg.exec_()
    else:
        # If QApplication is not created, we display an error to the console
        logging.error(f"An error occurred before QApplication was initialized:")
        logging.error(system_info + error_message)

    sys.exit(1)

def get_seed_from_name(name):
    hash_object = hashlib.sha256(name.encode())
    hex_dig = hash_object.hexdigest()
    seed = int(hex_dig, 16) % (2**32)
    return seed

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
        self.setWindowFlags(self.windowFlags() | QtCore.Qt.Window)

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

        self.sound_effect = QSoundEffect()
        self.sound_effect.setVolume(0.5)

        self.selected_mic_index = self.settings_manager.get_value('selected_mic_index', default=None, value_type=int)
        self.activation_threshold = self.settings_manager.get_value('activation_threshold', default=10, value_type=int)
        self.sound_enabled = self.settings_manager.get_value('sound_enabled', default=True, value_type=bool)
        self.autostart_enabled = self.settings_manager.get_value('autostart_enabled', default=True, value_type=bool)
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

        screen_rect = QtWidgets.QApplication.desktop().screenGeometry()
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
        Check if the foreground window is truly fullscreen using WinAPI
        (GetForegroundWindow, GetWindowRect, MonitorFromWindow, etc.).
        If it is fullscreen (and not our own window), pause the duck.
        Otherwise resume.
        """
        # Only do this on Windows. If on other OS, skip.
        if not sys.platform.startswith("win"):
            return

        hwnd_foreground = win32gui.GetForegroundWindow()
        if not hwnd_foreground:
            # No foreground window at all -> likely desktop or something else
            if self.is_paused_for_fullscreen:
                self.resume_duck()
                self.is_paused_for_fullscreen = False
            return

        left, top, right, bottom = win32gui.GetWindowRect(hwnd_foreground)

        monitor = win32api.MonitorFromWindow(hwnd_foreground, win32con.MONITOR_DEFAULTTONEAREST)
        monitor_info = win32api.GetMonitorInfo(monitor)
        mon_left, mon_top, mon_right, mon_bottom = monitor_info["Monitor"]

        is_foreground_fullscreen = (
            left == mon_left and
            top == mon_top and
            right == mon_right and
            bottom == mon_bottom
        )

        if is_foreground_fullscreen:
            if not self.is_paused_for_fullscreen:
                logging.info("A fullscreen application is detected via WinAPI -> Pausing duck.")
                self.pause_duck()
                self.is_paused_for_fullscreen = True
        else:
            # Not fullscreen
            if self.is_paused_for_fullscreen:
                logging.info("Fullscreen application is closed or minimized -> Resuming duck.")
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
        self.debug_mode = True
        self.debug_window.show()
        self.debug_window.raise_()
        self.debug_window.activateWindow()

    def play_random_sound(self):
        """
        Play a random duck sound, if sound is enabled. 
        Also schedule the next random sound after a random interval.
        """
        if not self.sound_enabled:
            self.schedule_next_sound()
            return
        sound_file = self.resources.get_random_sound()
        if sound_file:
            url = QtCore.QUrl.fromLocalFile(sound_file)
            self.sound_effect.setSource(url)
            self.sound_effect.play()
            logging.info(f"Played sound: {sound_file}")
        else:
            logging.warning("No sound files available to play.")
        self.schedule_next_sound()

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
        if event.button() == QtCore.Qt.LeftButton:
            self.create_heart()

    def create_heart(self):
        """
        Spawn a small heart sprite above the duck.
        """
        heart_x = self.duck_x + self.current_frame.width() / 2
        heart_y = self.duck_y
        self.heart_window = HeartWindow(heart_x, heart_y)

    def init_ui(self):
        """
        Set up window flags (frameless, top-most, etc.) and show the duck.
        """
        self.setWindowFlags(
            QtCore.Qt.FramelessWindowHint |
            QtCore.Qt.WindowStaysOnTopHint |
            QtCore.Qt.Tool
        )
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
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
        """
        Change the duck's state machine to a new state, 
        respecting some constraints (e.g. can't run if falling).
        """
        old_state_name = self.state.__class__.__name__ if self.state else "None"

        allowed_wake_states = (DraggingState, PlayfulState, ListeningState, JumpingState, WalkingState)

        # Prevent certain transitions if the duck is in mid-air or playful.
        if isinstance(self.state, PlayfulState) and isinstance(new_state, IdleState) and isinstance(self.state, (FallingState, JumpingState)):
            logging.info("Cannot transition from PlayfulState to IdleState directly while in mid-air.")
            return
        if isinstance(new_state, (RunState, AttackState)) and isinstance(self.state, (FallingState, JumpingState)):
            logging.info(f"Cannot transition to {new_state.__class__.__name__} while in mid-air.")
            return
        if isinstance(new_state, ListeningState) and isinstance(self.state, PlayfulState):
            logging.info("Transition to ListeningState is rejected because the duck is in PlayfulState.")
            return

        if isinstance(self.state, SleepingState):
            # If duck is sleeping, only certain states can wake it up.
            if isinstance(new_state, allowed_wake_states):
                logging.info(f"Transition from SleepingState to {new_state.__class__.__name__}")
                self.state.exit()
                self.state = new_state
                self.state.enter()
                if event:
                    self.state.handle_mouse_press(event)
            else:
                logging.info(f"Staying in SleepingState, attempt to move to {new_state.__class__.__name__} rejected.")
                return
        else:
            # Normal state change
            if self.state:
                logging.info(f"Transition from {self.state.__class__.__name__} to {new_state.__class__.__name__}")
                self.state.exit()
            else:
                logging.info(f"Transition to {new_state.__class__.__name__}")
            self.state = new_state
            self.state.enter()
            if event:
                self.state.handle_mouse_press(event)

        # Start or stop cursor shake detection based on whether we are in Idle/Walking.
        if isinstance(self.state, (IdleState, WalkingState)):
            self.start_cursor_shake_detection()
            logging.info("Starting cursor shake detection.")
        else:
            self.stop_cursor_shake_detection()
            logging.info("Stopping cursor shake detection.")

        new_state_name = self.state.__class__.__name__ if self.state else "None"
        self.state_history.append((time.strftime("%H:%M:%S"), old_state_name, new_state_name))
        if len(self.state_history) > 10:
            self.state_history.pop(0)

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
        self.state.update_animation()

    def update_position(self):
        """
        Called by self.position_timer. Moves the duck according to current state logic. 
        Also updates the name window if it's visible.
        """
        self.state.update_position()
        if self.name_window and self.show_name and self.pet_name.strip():
            self.name_window.update_position()

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        if self.current_frame:
            painter.drawPixmap(0, 0, self.current_frame)

        # If in debug mode, draw a bounding box and coordinates.
        if self.debug_mode:
            painter.setPen(QtGui.QPen(QtGui.QColor("red"), 2, QtCore.Qt.SolidLine))
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
        screen_rect = QtWidgets.QApplication.desktop().screenGeometry()
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
            self.state.exit()
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
        if hasattr(self, 'settings_window') and self.settings_manager_window.isVisible():
            self.settings_manager_window.raise_()
            self.settings_manager_window.activateWindow()
        else:
            self.settings_manager_window = SettingsWindow(self)
            self.settings_manager_window.show()

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
        self.autostart_enabled = self.settings_manager.get_value('autostart_enabled', default=True, value_type=bool)
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
        global translations
        translations = load_translation(self.current_language)

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
        if self.show_name and self.pet_name.strip():
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

        self.resources.load_sprites_now()

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

class DebugWindow(QtWidgets.QWidget):
    """
    A window for debugging the QuackDuck application.

    Attributes:
        duck: The main Duck instance being debugged.
        update_timer: A QTimer to periodically update debug information.
    """
    def __init__(self, duck):
        """
        Initializes the debug window.

        Args:
            duck: The main Duck instance.
        """
        super().__init__()
        self.duck = duck
        self.setWindowTitle("QuackDuck Ultimate Debug Mode")
        self.setGeometry(100, 100, 1200, 800)
        self.init_ui()
        self.update_timer = QtCore.QTimer(self)
        self.update_timer.timeout.connect(self.update_debug_info)
        self.update_timer.start(500)

    def init_ui(self):
        """Initializes the user interface for the debug window."""
        self.setStyleSheet("""
        QWidget {
            background-color: #2a2a2a;
            color: #ccc;
            font-size: 14px;
        }
        QGroupBox {
            border: 1px solid #444;
            margin-top: 20px;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            subcontrol-position: top left;
            padding: 5px;
        }
        QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QCheckBox, QPushButton {
            background-color: #3a3a3a;
            border: 1px solid #555;
            border-radius:3px;
            padding:4px;
            color:#ccc;
        }
        QScrollArea, QTextEdit, QListWidget {
            background-color: #1e1e1e;
            border:1px solid #444;
            color:#ccc;
        }
        QTabWidget::pane {
            border: 1px solid #444;
        }
        QTabBar::tab {
            background: #3a3a3a;
            padding:5px;
        }
        QTabBar::tab:selected {
            background: #444;
        }
        """)

        main_layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        self.params_widget = QWidget()
        self.params_layout = QVBoxLayout(self.params_widget)

        # General settings
        general_group = QGroupBox("General Settings (No Limits)")
        general_form = QFormLayout()

        # Pet name
        self.petNameEdit = QLineEdit(self.duck.pet_name)
        self.petNameEdit.editingFinished.connect(self.update_pet_name)
        general_form.addRow("Pet Name:", self.petNameEdit)

        # Pet size
        self.petSizeSpin = QSpinBox()
        self.petSizeSpin.setRange(-1000, 1000)
        self.petSizeSpin.setValue(self.duck.pet_size)
        self.petSizeSpin.valueChanged.connect(self.update_pet_size_spin)
        general_form.addRow("Pet Size:", self.petSizeSpin)

        # Activation Threshold
        self.activationSpin = QSpinBox()
        self.activationSpin.setRange(0,9999)
        self.activationSpin.setValue(self.duck.activation_threshold)
        self.activationSpin.valueChanged.connect(self.update_activation_threshold)
        general_form.addRow("Activation Threshold:", self.activationSpin)

        # Sleep Timeout (sec)
        self.sleepTimeoutSpin = QSpinBox()
        self.sleepTimeoutSpin.setRange(0, 999999)
        self.sleepTimeoutSpin.setValue(int(self.duck.sleep_timeout))
        self.sleepTimeoutSpin.valueChanged.connect(self.update_sleep_timeout)
        general_form.addRow("Sleep Timeout (sec):", self.sleepTimeoutSpin)

        # Idle duration (sec)
        self.idleDurationSpin = QDoubleSpinBox()
        self.idleDurationSpin.setRange(0.0,999999.0)
        self.idleDurationSpin.setValue(self.duck.idle_duration)
        self.idleDurationSpin.setSuffix(" sec")
        self.idleDurationSpin.valueChanged.connect(self.update_idle_duration)
        general_form.addRow("Idle Duration:", self.idleDurationSpin)

        # Sound enabled
        self.soundCheck = QCheckBox("Sound Enabled")
        self.soundCheck.setChecked(self.duck.sound_enabled)
        self.soundCheck.stateChanged.connect(self.update_sound_enabled)
        general_form.addRow(self.soundCheck)

        # Show name
        self.showNameCheck = QCheckBox("Show Name Above Duck")
        self.showNameCheck.setChecked(self.duck.show_name)
        self.showNameCheck.stateChanged.connect(self.update_show_name)
        general_form.addRow(self.showNameCheck)

        # Ground level
        self.groundLevelSpin = QSpinBox()
        self.groundLevelSpin.setRange(-999999,999999)
        self.groundLevelSpin.setValue(self.duck.ground_level_setting)
        self.groundLevelSpin.valueChanged.connect(self.update_ground_level)
        general_form.addRow("Ground Level (px):", self.groundLevelSpin)

        # Direction change interval
        self.directionIntervalSpin = QDoubleSpinBox()
        self.directionIntervalSpin.setRange(0,999999)
        self.directionIntervalSpin.setValue(float(self.duck.direction_change_interval))
        self.directionIntervalSpin.valueChanged.connect(self.update_direction_interval)
        general_form.addRow("Direction Change Interval (sec):", self.directionIntervalSpin)

        # Font base size
        self.fontBaseSizeSpin = QSpinBox()
        self.fontBaseSizeSpin.setRange(1,9999)
        self.fontBaseSizeSpin.setValue(self.duck.font_base_size)
        self.fontBaseSizeSpin.valueChanged.connect(self.update_font_base_size)
        general_form.addRow("Font Base Size:", self.fontBaseSizeSpin)

        # Autostart
        self.autostartCheck = QCheckBox("Run at system startup")
        self.autostartCheck.setChecked(self.duck.autostart_enabled)
        self.autostartCheck.stateChanged.connect(self.update_autostart)
        general_form.addRow(self.autostartCheck)

        # Current language (no limit)
        self.languageEdit = QLineEdit(self.duck.current_language)
        self.languageEdit.editingFinished.connect(self.update_language_line)
        general_form.addRow("Language (string):", self.languageEdit)

        # Name offset y
        self.nameOffsetSpin = QSpinBox()
        self.nameOffsetSpin.setRange(-999999,999999)
        self.nameOffsetSpin.setValue(self.duck.name_offset_y)
        self.nameOffsetSpin.valueChanged.connect(self.update_name_offset)
        general_form.addRow("Name Offset Y:", self.nameOffsetSpin)

        self.soundIntervalMinSpin = QDoubleSpinBox()
        self.soundIntervalMinSpin.setRange(0,999999)
        self.soundIntervalMinSpin.setValue(getattr(self.duck,'sound_interval_min',60.0))
        self.soundIntervalMinSpin.valueChanged.connect(self.update_sound_interval_min)
        general_form.addRow("Sound Interval Min (sec):", self.soundIntervalMinSpin)

        self.soundIntervalMaxSpin = QDoubleSpinBox()
        self.soundIntervalMaxSpin.setRange(0,999999)
        self.soundIntervalMaxSpin.setValue(getattr(self.duck,'sound_interval_max',600.0))
        self.soundIntervalMaxSpin.valueChanged.connect(self.update_sound_interval_max)
        general_form.addRow("Sound Interval Max (sec):", self.soundIntervalMaxSpin)

        # Probability of playfulness
        self.playfulProbSpin = QDoubleSpinBox()
        self.playfulProbSpin.setRange(0.0,1.0)
        self.playfulProbSpin.setDecimals(4)
        self.playfulProbSpin.setValue(self.duck.playful_behavior_probability)
        self.playfulProbSpin.valueChanged.connect(self.update_playful_probability)
        general_form.addRow("Playful Behavior Probability:", self.playfulProbSpin)

        # Add the group to params_layout
        general_group.setLayout(general_form)
        self.params_layout.addWidget(general_group)

        # Additional buttons for artificial events
        extra_group = QGroupBox("Extra Controls")
        extra_layout = QHBoxLayout()

        # Trigger double click
        double_click_btn = QPushButton("Trigger Double Click")
        double_click_btn.clicked.connect(self.trigger_double_click)
        extra_layout.addWidget(double_click_btn)

        # Play sound manually
        play_sound_btn = QPushButton("Play Random Sound")
        play_sound_btn.clicked.connect(self.duck.play_random_sound)
        extra_layout.addWidget(play_sound_btn)

        # Force interface methods (like open settings window)
        open_settings_btn = QPushButton("Open Settings Window")
        open_settings_btn.clicked.connect(self.duck.open_settings)
        extra_layout.addWidget(open_settings_btn)

        # Let's allow calling any method by name
        self.methodEdit = QLineEdit()
        self.methodEdit.setPlaceholderText("Enter method name with no args, e.g. 'unstuck_duck'")
        call_method_btn = QPushButton("Call Method")
        call_method_btn.clicked.connect(self.call_method_by_name)
        extra_layout.addWidget(self.methodEdit)
        extra_layout.addWidget(call_method_btn)

        extra_group.setLayout(extra_layout)
        self.params_layout.addWidget(extra_group)

        self.params_layout.addStretch()
        self.tabs.addTab(self.params_widget, "Parameters & Extra")

        # Log, state and state management merge tab
        self.logs_states_widget = QWidget()
        logs_states_layout = QVBoxLayout(self.logs_states_widget)

        # Last 100 states
        state_history_group = QGroupBox("Last 100 States + State Control")
        state_history_vlayout = QVBoxLayout()

        # State control panel
        state_control_layout = QHBoxLayout()
        # Buttons to trigger states
        self.add_state_button(state_control_layout, "Idle", IdleState)
        self.add_state_button(state_control_layout, "Walk", WalkingState)
        self.add_state_button(state_control_layout, "Sleep", SleepingState)
        self.add_state_button(state_control_layout, "Jump", JumpingState)
        self.add_state_button(state_control_layout, "Fall", FallingState)
        self.add_state_button(state_control_layout, "Drag", DraggingState)
        self.add_state_button(state_control_layout, "Listen", ListeningState)
        self.add_state_button(state_control_layout, "Playful", PlayfulState)
        self.add_state_button(state_control_layout, "Run", RunState)
        self.add_state_button(state_control_layout, "Attack", AttackState)
        self.add_state_button(state_control_layout, "Land", LandingState)
        state_history_vlayout.addLayout(state_control_layout)

        # State history list
        self.state_history_list = QListWidget()
        state_history_vlayout.addWidget(self.state_history_list)

        state_history_group.setLayout(state_history_vlayout)
        logs_states_layout.addWidget(state_history_group)

        # Logs
        logs_group = QGroupBox("Logs")
        logs_group_layout = QVBoxLayout()
        self.log_viewer = QTextEdit()
        self.log_viewer.setReadOnly(True)
        logs_group_layout.addWidget(self.log_viewer)
        logs_group.setLayout(logs_group_layout)
        logs_states_layout.addWidget(logs_group)

        logs_states_layout.addStretch()
        self.tabs.addTab(self.logs_states_widget, "Logs & States")

    def add_state_button(self, layout, name, state_class):
        btn = QPushButton(name)
        btn.clicked.connect(lambda: self.duck.change_state(state_class(self.duck)))
        layout.addWidget(btn)

    def update_debug_info(self):
        """Updates the debug information displayed in the window."""
        self.state_history_list.clear()
        history_slice = self.duck.state_history[-100:]
        for t, old_st, new_st in history_slice:
            self.state_history_list.addItem(f"{t}: {old_st} -> {new_st}")

        try:
            log_path = os.path.join(os.path.expanduser('~'), 'quackduck.log')
            if os.path.exists(log_path):
                with open(log_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                last_lines = lines[-200:]
                self.log_viewer.setPlainText(''.join(last_lines))
                self.log_viewer.verticalScrollBar().setValue(self.log_viewer.verticalScrollBar().maximum())
        except:
            pass

    def trigger_double_click(self):
        event = QtGui.QMouseEvent(QtCore.QEvent.MouseButtonDblClick,
                                  QtCore.QPointF(self.duck.duck_x,self.duck.duck_y),
                                  QtCore.Qt.LeftButton,
                                  QtCore.Qt.LeftButton,
                                  QtCore.Qt.NoModifier)
        self.duck.mouseDoubleClickEvent(event)

    def call_method_by_name(self):
        method_name = self.methodEdit.text().strip()
        if method_name and hasattr(self.duck, method_name):
            m = getattr(self.duck, method_name)
            if callable(m):
                try:
                    m()
                except Exception as e:
                    QtWidgets.QMessageBox.warning(self, "Error calling method", str(e))
            else:
                QtWidgets.QMessageBox.warning(self, "Not callable", f"{method_name} is not callable.")
        else:
            QtWidgets.QMessageBox.warning(self, "Method not found", f"No method {method_name} found on duck.")

    def update_pet_name(self):
        self.duck.pet_name = self.petNameEdit.text().strip()
        self.duck.apply_settings()

    def update_pet_size_spin(self, v):
        self.duck.update_pet_size(v)
        self.duck.apply_settings()

    def update_activation_threshold(self, v):
        self.duck.activation_threshold = v
        self.duck.apply_settings()

    def update_sleep_timeout(self, v):
        self.duck.sleep_timeout = v
        self.duck.apply_settings()

    def update_idle_duration(self, v):
        self.duck.idle_duration = v
        self.duck.apply_settings()

    def update_sound_enabled(self, state):
        self.duck.sound_enabled = (state == Qt.Checked)
        self.duck.apply_settings()

    def update_show_name(self, state):
        self.duck.show_name = (state == Qt.Checked)
        self.duck.apply_settings()

    def update_ground_level(self, v):
        self.duck.update_ground_level(v)
        self.duck.apply_settings()

    def update_direction_interval(self, v):
        self.duck.direction_change_interval = v
        self.duck.apply_settings()

    def update_font_base_size(self, v):
        self.duck.font_base_size = v
        self.duck.apply_settings()

    def update_autostart(self, state):
        self.duck.autostart_enabled = (state == Qt.Checked)
        if self.duck.autostart_enabled:
            self.duck.enable_autostart()
        else:
            self.duck.disable_autostart()
        self.duck.apply_settings()

    def update_language_line(self):
        lang_code = self.languageEdit.text().strip()
        self.duck.current_language = lang_code
        self.duck.apply_settings()

    def update_name_offset(self, v):
        self.duck.name_offset_y = v
        self.duck.apply_settings()

    def update_sound_interval_min(self, val):
        self.duck.sound_interval_min = val
        self.duck.apply_settings()

    def update_sound_interval_max(self, val):
        self.duck.sound_interval_max = val
        self.duck.apply_settings()

    def update_playful_probability(self, val):
        self.duck.playful_behavior_probability = val
        self.duck.apply_settings()

    def closeEvent(self, event):
        self.duck.debug_mode = False
        event.accept()
        super().closeEvent(event)

class HeartWindow(QtWidgets.QWidget):
    def __init__(self, x, y):
        super().__init__()
        self.setWindowFlags(
            QtCore.Qt.FramelessWindowHint
            | QtCore.Qt.WindowStaysOnTopHint
            | QtCore.Qt.Tool
        )
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        self.opacity = 1.0
        self.start_time = time.time()
        self.duration = 2.0

        self.size = random.uniform(20, 50)
        self.dx = random.uniform(-20, 20)
        self.dy = random.uniform(-50, -100)

        # Use resource_path to get an absolute path to heart.png
        heart_image_path = resource_path("assets/images/heart.png")  # Update the path if necessary

        if not os.path.exists(heart_image_path):
            logging.error(f"Error: File {heart_image_path} not found.")
            QtWidgets.QMessageBox.critical(self, translations.get("error_title", "Error!"), translations.get("file_not_found", "File not found:") + f" '{heart_image_path}'")
            self.close()
            return

        self.image = QtGui.QPixmap(heart_image_path).scaled(
            int(self.size),
            int(self.size),
            QtCore.Qt.KeepAspectRatio,
            QtCore.Qt.FastTransformation,
        )

        self.x = x - self.size / 2
        self.y = y - self.size / 2
        self.move(int(self.x), int(self.y))

        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update_position)
        self.timer.start(30)

        self.resize(int(self.size), int(self.size))

        self.show()

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        try:
            painter.setOpacity(self.opacity)
            painter.drawPixmap(0, 0, self.image)
        finally:
            painter.end()

    def update_position(self):
        elapsed = time.time() - self.start_time
        if elapsed > self.duration:
            self.close()
            return

        progress = elapsed / self.duration
        self.x += self.dx * 0.02
        self.y += self.dy * 0.02
        self.opacity = 1.0 - progress
        self.move(int(self.x), int(self.y))
        self.update()

class NameWindow(QtWidgets.QWidget):
    """
    A small top-level window that displays the duck's name above the duck's head.
    """
    def __init__(self, duck):
        super().__init__()
        self.duck = duck
        self.setWindowFlags(
            QtCore.Qt.FramelessWindowHint
            | QtCore.Qt.WindowStaysOnTopHint
            | QtCore.Qt.Tool
        )
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose, False)

        self.label = QtWidgets.QLabel(self)
        self.label.setStyleSheet("QLabel { color: white; font-weight: bold; }")
        self.label.setAlignment(Qt.AlignCenter)
        self.update_label()
        self.show()

    def update_label(self):
        base_size = getattr(self.duck, 'font_base_size', 14)
        scaled_size = int(base_size * (self.duck.pet_size / 3))
        if scaled_size < 8:
            scaled_size = 8
        font = QtGui.QFont("Segoe UI", scaled_size)
        self.label.setFont(font)
        self.label.setText(self.duck.pet_name)
        self.label.adjustSize()
        self.adjustSize()

    def update_position(self):
        duck_x = self.duck.duck_x
        duck_y = self.duck.duck_y
        duck_w = self.duck.duck_width
        name_width = self.width()
        name_height = self.height()

        # Get top offset from duck
        top_offset = self.duck.get_top_non_opaque_offset()  # returns a negative or zero offset
        offset_y = self.duck.name_offset_y + top_offset
        x = duck_x + (duck_w - name_width) / 2
        y = duck_y - offset_y

        screen = QtWidgets.QApplication.primaryScreen()
        screen_rect = screen.geometry()

        if x < 0:
            x = 0
        if y < 0:
            y = 0
        if x + name_width > screen_rect.width():
            x = screen_rect.width() - name_width
        if y + name_height > screen_rect.height():
            y = screen_rect.height() - name_height

        self.move(int(x), int(y))

class State(ABC):
    def __init__(self, duck: 'Duck') -> None:
        self.duck = duck

    @abstractmethod
    def enter(self) -> None:
        pass

    @abstractmethod
    def update_animation(self) -> None:
        pass

    @abstractmethod
    def update_position(self) -> None:
        pass

    @abstractmethod
    def exit(self) -> None:
        pass

    def handle_mouse_press(self, event: QMouseEvent) -> None:
        if event.button() == QtCore.Qt.LeftButton:
            self.duck.change_state(DraggingState(self.duck), event)
        elif event.button() == QtCore.Qt.RightButton:
            self.duck.change_state(JumpingState(self.duck))

    def handle_mouse_release(self, event: QMouseEvent) -> None:
        pass

    def handle_mouse_move(self, event: QMouseEvent) -> None:
        pass

class RunState(State):
    def __init__(self, duck):
        super().__init__(duck)
        self.start_time = None
        self.duration = random.uniform(60, 120)  # 60-120 sec
        self.speed_multiplier = 2  # same as in PlayfulState

    def enter(self):
        self.start_time = time.time()
        # If there is a running animation, use it, otherwise fallback to walk or idle
        self.frames = self.duck.resources.get_animation_frames_by_name('running') or \
                      self.duck.resources.get_animation_frames_by_name('walk') or \
                      self.duck.resources.get_animation_frames_by_name('idle')
        self.frame_index = 0

        # Increase speed like in PlayfulState
        self.prev_speed = self.duck.duck_speed
        self.duck.duck_speed = self.duck.base_duck_speed * self.speed_multiplier * (self.duck.pet_size / 3)

        self.update_frame()

    def update_animation(self):
        if self.frames:
            self.frame_index = (self.frame_index + 1) % len(self.frames)
            self.update_frame()

    def update_position(self):
        elapsed = time.time() - self.start_time
        if elapsed > self.duration:
            self.duck.change_state(WalkingState(self.duck))
            return

        if self.duck.is_listening:
            return

        self.duck.duck_x += self.duck.duck_speed * self.duck.direction
        if self.duck.duck_x < 0 or self.duck.duck_x + self.duck.duck_width > self.duck.screen_width:
            self.duck.change_direction()
        self.duck.move(int(self.duck.duck_x), int(self.duck.duck_y))

    def exit(self):
        self.duck.duck_speed = self.prev_speed

    def update_frame(self):
        if self.frames:
            frame = self.frames[self.frame_index]
            if not self.duck.facing_right:
                frame = frame.transformed(QtGui.QTransform().scale(-1, 1))
            self.duck.current_frame = frame
            self.duck.update()

class AttackState(State):
    def __init__(self, duck, return_state=None):
        super().__init__(duck)
        self.return_state = return_state
        self.animation_finished = False

    def enter(self):
        """
        Entering attack state.
        Load attack animation frames if available, otherwise fall back to idle.
        Set initial frame index and update.
        """
        self.frames = self.duck.resources.get_animation_frames_by_name('attack') or \
                      self.duck.resources.get_animation_frames_by_name('idle')
        self.frame_index = 0
        self.update_frame()
        # During attack, the duck does not move
        self.animation_finished = False

    def update_animation(self):
        """
        Update attack animation frames once, then return to previous or walking state.
        """
        if self.frames:
            if self.frame_index < len(self.frames) - 1:
                self.frame_index += 1
                self.update_frame()
            else:
                # Animation finished
                if not self.animation_finished:
                    self.animation_finished = True
                    if self.return_state:
                        self.duck.change_state(self.return_state)
                    else:
                        self.duck.change_state(WalkingState(self.duck))

    def update_position(self):
        """
        Duck does not move during attack.
        """
        pass

    def exit(self):
        """
        On exiting attack state, synchronize facing direction with current movement direction.
        Update animation frame of the new state (if walking or idle).
        """
        self.duck.facing_right = (self.duck.direction == 1)
        if isinstance(self.duck.state, (WalkingState, IdleState)):
            self.duck.state.frame_index = 0
            self.duck.state.update_frame()

    def update_frame(self):
        """
        Update the current attack frame.
        Flip frame if duck is facing left.
        """
        if self.frames:
            frame = self.frames[self.frame_index]
            if not self.duck.facing_right:
                frame = frame.transformed(QtGui.QTransform().scale(-1, 1))
            self.duck.current_frame = frame
            self.duck.update()

    def handle_mouse_press(self, event):
        """
        If user presses the left mouse button during attack,
        cancel attack and go to dragging state.
        """
        if event.button() == QtCore.Qt.LeftButton:
            # Stop attack and enter dragging state
            self.duck.stop_current_state()
            self.duck.change_state(DraggingState(self.duck), event)

    def handle_mouse_move(self, event):
        """
        If user moves mouse while holding left button during attack,
        it means user tries to drag. Cancel attack and go to dragging state.
        """
        if event.buttons() & QtCore.Qt.LeftButton:
            self.duck.stop_current_state()
            self.duck.change_state(DraggingState(self.duck), event)

class LandingState(State):
    def __init__(self, duck, next_state=None):
        super().__init__(duck)
        self.next_state = next_state or WalkingState(duck)

    def enter(self):
        self.frames = self.duck.resources.get_animation_frames_by_name('land') or \
                      self.duck.resources.get_animation_frames_by_name('idle') or \
                      [self.duck.resources.get_default_frame()]
        self.frame_index = 0
        self.update_frame()

    def update_animation(self):
        if not self.frames:
            self.duck.change_state(self.next_state)
            return
        if self.frame_index < len(self.frames) - 1:
            self.frame_index += 1
            self.update_frame()
        else:
            self.duck.change_state(self.next_state)

    def update_position(self):
        pass

    def exit(self):
        pass

    def update_frame(self):
        if self.frames:
            frame = self.frames[self.frame_index]
            if not self.duck.facing_right:
                frame = frame.transformed(QtGui.QTransform().scale(-1, 1))
            self.duck.current_frame = frame
            self.duck.update()

class ListeningState(State):
    def enter(self):
        self.duck.is_listening = True
        self.frames = self.duck.resources.get_animation_frames_by_name('listen') or \
                      self.duck.resources.get_animation_frames_by_name('idle')
        self.frame_index = 0
        self.update_frame()
        logging.info("ListeningState: Entered.")

    def update_animation(self):
        if self.frames:
            self.frame_index = (self.frame_index + 1) % len(self.frames)
            self.update_frame()

    def update_position(self):
        pass

    def exit(self):
        self.duck.is_listening = False
        logging.info("ListeningState: Exited.")

    def update_frame(self):
        if self.frames:
            frame = self.frames[self.frame_index]
            if not self.duck.facing_right:
                frame = frame.transformed(QtGui.QTransform().scale(-1, 1))
            self.duck.current_frame = frame
            self.duck.update()
            logging.debug(f"ListeningState: Frame updated {self.frame_index}.")

    def handle_mouse_press(self, event):
        super().handle_mouse_press(event)

    def handle_mouse_move(self, event):
        if event.buttons() & QtCore.Qt.LeftButton:
            # User began to move the duck
            self.duck.is_listening = False
            self.duck.change_state(DraggingState(self.duck), event)
            logging.info("ListeningState: Entering DraggingState due to moving.")

    def handle_mouse_release(self, event):
        pass

class WalkingState(State):
    def enter(self):
        self.frames = self.duck.resources.get_animation_frames_by_name('walk') or \
                      self.duck.resources.get_animation_frames_by_name('idle')
        self.frame_index = 0
        self.update_frame()
        self.start_time = time.time()
        self.walk_duration = random.uniform(5, 15)  # The duck will walk from 5 to 15 seconds

    def update_animation(self):
        if self.frames:
            self.frame_index = (self.frame_index + 1) % len(self.frames)
            self.update_frame()

    def update_position(self):
        if self.duck.is_listening:
            return

        self.duck.duck_x += self.duck.duck_speed * self.duck.direction
        if self.duck.duck_x < 0 or self.duck.duck_x + self.duck.duck_width > self.duck.screen_width:
            self.duck.change_direction()
        self.duck.move(int(self.duck.duck_x), int(self.duck.duck_y))

        # Check if it's time to go to Idlestate
        elapsed_time = time.time() - self.start_time
        if elapsed_time > self.walk_duration:
            # Check if current state is still walking and not falling/dragging
            if not isinstance(self.duck.state, (FallingState, DraggingState)):
                self.duck.change_state(IdleState(self.duck))

    def exit(self):
        if hasattr(self, 'cursor_shake_timer'):
            self.cursor_shake_timer.stop()
            self.cursor_shake_timer = None
        pass

    def update_frame(self):
        if self.frames:
            frame = self.frames[self.frame_index]
            if not self.duck.facing_right:
                frame = frame.transformed(QtGui.QTransform().scale(-1, 1))
            self.duck.current_frame = frame
            self.duck.update()

class FallingState(State):
    def __init__(self, duck, play_animation=True, return_state=None):
        super().__init__(duck)
        self.play_animation = play_animation
        self.return_state = return_state or WalkingState(duck)

    def enter(self):
        if self.play_animation:
            self.frames = self.duck.resources.get_animation_frames_by_name('fall') or \
                          self.duck.resources.get_animation_frames_by_name('idle')
        else:
            # Use the last frame from the previous state
            self.frames = [self.duck.current_frame]
        self.frame_index = 0
        self.vertical_speed = 0
        self.update_frame()

    def update_animation(self):
        if self.play_animation and self.frames and self.frame_index < len(self.frames) - 1:
            self.frame_index += 1
            self.update_frame()
        # If the animation should not play or the last frame is reached, we do nothing

    def update_position(self):
        self.vertical_speed += 1
        self.duck.duck_y += self.vertical_speed

        if self.duck.duck_y + self.duck.duck_height >= self.duck.ground_level:
            self.duck.duck_y = self.duck.ground_level - self.duck.duck_height
            self.vertical_speed = 0
            self.duck.move(int(self.duck.duck_x), int(self.duck.duck_y))
            self.duck.change_state(LandingState(self.duck, next_state=self.return_state))
        else:
            self.duck.move(int(self.duck.duck_x), int(self.duck.duck_y))

    def exit(self):
        pass

    def update_frame(self):
        if self.frames:
            frame = self.frames[self.frame_index]
            if not self.duck.facing_right:
                frame = frame.transformed(QtGui.QTransform().scale(-1, 1))
            self.duck.current_frame = frame
            self.duck.update()

class DraggingState(State):
    def enter(self):
        self.frames = self.duck.resources.get_animation_frames_by_name('fall') or \
                      self.duck.resources.get_animation_frames_by_name('idle')
        self.frame_index = 0
        self.update_frame()
        # Hide the name window when starting to drag
        if self.duck.name_window:
            self.duck.name_window.hide()

    def update_animation(self):
        if self.frames and self.frame_index < len(self.frames) - 1:
            self.frame_index += 1
            self.update_frame()

    def update_position(self):
        pass

    def exit(self):
        # Show the name window again if needed
        if self.duck.name_window and self.duck.show_name and self.duck.pet_name.strip():
            self.duck.name_window.show()

    def update_frame(self):
        if self.frames:
            frame = self.frames[self.frame_index]
            if not self.duck.facing_right:
                frame = frame.transformed(QtGui.QTransform().scale(-1, 1))
            self.duck.current_frame = frame
            self.duck.update()

    def handle_mouse_press(self, event):
        self.offset = event.pos()

    def handle_mouse_move(self, event):
        new_pos = event.globalPos() - self.offset
        self.duck.duck_x = new_pos.x()
        self.duck.duck_y = new_pos.y()
        self.duck.move(int(self.duck.duck_x), int(self.duck.duck_y))

        # Update name position immediately
        if self.duck.name_window and self.duck.show_name and self.duck.pet_name.strip():
            self.duck.name_window.update_position()

    def handle_mouse_release(self, event):
        self.duck.change_state(FallingState(self.duck, play_animation=False, return_state=WalkingState(self.duck)))

class JumpingState(State):
    def __init__(self, duck, return_state=None):
        super().__init__(duck)
        self.return_state = return_state
        self.vertical_speed = -15
        self.is_falling = False  # Flag for tracking fall

    def enter(self):
        self.duck.facing_right = self.duck.direction == 1
        self.jump_frames = self.duck.resources.get_animation_frames_by_name('jump') or \
                           self.duck.resources.get_animation_frames_by_name('idle') or \
                           [self.duck.resources.get_default_frame()]
        self.fall_frames = self.duck.resources.get_animation_frames_by_name('fall') or \
                           self.duck.resources.get_animation_frames_by_name('idle') or \
                           [self.duck.resources.get_default_frame()]
        self.frames = self.jump_frames
        self.frame_index = 0

        if isinstance(self.return_state, PlayfulState):
            self.vertical_speed = -15 * 1.5

        self.update_frame()

    def update_animation(self):
        if self.frames and self.frame_index < len(self.frames) - 1:
            self.frame_index += 1
        else:
            if self.is_falling:
                self.frame_index = len(self.frames) - 1
            else:
                self.frame_index = 0
        self.update_frame()

    def update_position(self):
        self.vertical_speed += 1
        self.duck.duck_y += self.vertical_speed

        if not self.is_falling and self.vertical_speed >= 0:
            self.is_falling = True
            self.frames = self.fall_frames
            self.frame_index = 0

        if self.duck.duck_y + self.duck.duck_height >= self.duck.ground_level:
            self.duck.duck_y = self.duck.ground_level - self.duck.duck_height
            self.vertical_speed = 0
            self.duck.move(int(self.duck.duck_x), int(self.duck.duck_y))
            if self.return_state:
                self.duck.change_state(LandingState(self.duck, next_state=self.return_state))
            else:
                self.duck.change_state(LandingState(self.duck))
        else:
            self.duck.move(int(self.duck.duck_x), int(self.duck.duck_y))

    def exit(self):
        pass

    def update_frame(self):
        if self.frames:
            frame = self.frames[self.frame_index]
            if not self.duck.facing_right:
                frame = frame.transformed(QtGui.QTransform().scale(-1, 1))
            self.duck.current_frame = frame
            self.duck.update()

class SleepingState(State):
    def enter(self):
        self.frames = self.duck.resources.get_animation_frames_by_name('sleep') or \
                      self.duck.resources.get_animation_frames_by_name('idle')
        self.frame_index = 0
        self.update_frame()

        # Start the wake-up timer
        self.wake_up_timer = QtCore.QTimer()
        self.wake_up_timer.setSingleShot(True)
        random_interval = random.randint(900000, 3600000)
        # Test interval timer before waking up:
        # random_interval = 30000
        self.wake_up_timer.timeout.connect(self.wake_up)
        self.wake_up_timer.start(random_interval)
        logging.info(f"SleepingState: Wake up timer started for {random_interval / 1000} seconds.")

    def update_animation(self):
        if self.frames:
            self.frame_index = (self.frame_index + 1) % len(self.frames)
            self.update_frame()

    def update_position(self):
        pass

    def exit(self):
        # Stopping the wakeup timer when exiting a state
        if hasattr(self, 'wake_up_timer') and self.wake_up_timer.isActive():
            self.wake_up_timer.stop()
            self.wake_up_timer = None
            logging.info("SleepingState: Wake up timer stopped.")

    def update_frame(self):
        if self.frames:
            self.duck.current_frame = self.frames[self.frame_index]
            self.duck.update()

    def handle_mouse_press(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self.duck.last_interaction_time = time.time()
            self.duck.change_state(DraggingState(self.duck), event)
        else:
            super().handle_mouse_press(event)

    def wake_up(self):
        logging.info("SleepingState: The wake-up timer has expired, the duck is waking up.")
        self.duck.last_interaction_time = time.time()
        self.duck.change_state(WalkingState(self.duck))

class IdleState(State):
    def __init__(self, duck):
        super().__init__(duck)
        self.start_time = time.time()
        self.cursor_positions = []

    def enter(self):
        idle_animations = self.duck.resources.get_idle_animations()
        selected_idle = random.choice(idle_animations) if idle_animations else 'idle'
        self.frames = self.duck.resources.get_animation_frames_by_name(selected_idle)
        self.frame_index = 0
        self.update_frame()

    def update_animation(self):
        if self.frames:
            self.frame_index = (self.frame_index + 1) % len(self.frames)
            self.update_frame()

    def update_position(self):
        if self.duck.is_listening:
            return

        elapsed_time = time.time() - self.start_time
        if elapsed_time > self.duck.idle_duration:
            self.duck.change_state(WalkingState(self.duck))

    def exit(self):
        if hasattr(self, 'cursor_shake_timer'):
            self.cursor_shake_timer.stop()
            self.cursor_shake_timer = None
        pass

    def update_frame(self):
        if self.frames:
            self.duck.current_frame = self.frames[self.frame_index]
            self.duck.update()

class PlayfulState(State):
    def __init__(self, duck):
        super().__init__(duck)
        self.start_time = time.time()
        self.duration = random.randint(20, 120)  # Duration from 20 to 120 seconds
        self.speed_multiplier = 2  # Speed ​​acceleration
        self.has_jumped = False  # Flag so that the duck does not jump constantly
        self.previous_direction = duck.direction
        self.previous_facing_right = duck.facing_right

    def enter(self):
        self.duck.duck_speed = self.duck.base_duck_speed * self.speed_multiplier * (self.duck.pet_size / 3)
        self.duck.animation_timer.setInterval(100)
        self.duck.playful = True
        self.frames = self.duck.resources.get_animation_frames_by_name('walk') or \
                      self.duck.resources.get_animation_frames_by_name('idle')
        self.frame_index = 0
        self.update_frame()

    def update_animation(self):
        if self.frames:
            self.frame_index = (self.frame_index + 1) % len(self.frames)
            frame = self.frames[self.frame_index]
            if not self.duck.facing_right:
                frame = frame.transformed(QtGui.QTransform().scale(-1, 1))
            self.duck.current_frame = frame
            self.duck.update()

    def update_position(self):
        current_time = time.time()
        if current_time - self.start_time > self.duration:
            self.duck.change_state(IdleState(self.duck))
            return

        self.chase_cursor()

    def chase_cursor(self):
        cursor_pos = QtGui.QCursor.pos()
        cursor_x = cursor_pos.x()
        duck_center_x = self.duck.duck_x + self.duck.current_frame.width() / 2

        # Determine the direction of movement
        if cursor_x > duck_center_x + 10:
            desired_direction = 1
        elif cursor_x < duck_center_x - 10:
            desired_direction = -1
        else:
            desired_direction = self.duck.direction  # Continue in the current direction

        if desired_direction != self.duck.direction:
            self.duck.direction = desired_direction
            self.duck.facing_right = desired_direction == 1

        # Duck movement
        movement_speed = self.duck.duck_speed
        self.duck.duck_x += desired_direction * movement_speed

        # Checking the boundaries of the screen
        screen = QtWidgets.QApplication.primaryScreen()
        screen_rect = screen.geometry()
        self.duck.duck_x = max(0, min(self.duck.duck_x, screen_rect.width() - self.duck.current_frame.width()))

        self.duck.move(int(self.duck.duck_x), int(self.duck.duck_y))

        # Check the proximity to the curser for the jump
        distance_x = abs(cursor_x - duck_center_x)
        if distance_x < 50 and not self.has_jumped:
            self.duck.change_state(JumpingState(self.duck, return_state=self))
            self.has_jumped = True
        elif distance_x >= 100:
            self.has_jumped = False

    def exit(self):
        self.duck.playful = False
        self.duck.duck_speed = self.duck.base_duck_speed * (self.duck.pet_size / 3)
        self.duck.animation_timer.setInterval(100)
        self.duck.direction = self.previous_direction
        self.duck.facing_right = self.previous_facing_right
        # After exiting PlayfulState, update the frame of the duck's current state,
        # so that there is no backward movement
        if isinstance(self.duck.state, WalkingState):
            self.duck.state.frame_index = 0
            self.duck.state.update_frame()
        elif isinstance(self.duck.state, IdleState):
            self.duck.state.frame_index = 0
            self.duck.state.update_frame()

    def handle_mouse_press(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            # Leave Playfulstate and go to Dragingstate
            self.duck.change_state(DraggingState(self.duck), event)
        else:
            super().handle_mouse_press(event)

    def update_frame(self):
        if self.frames:
            frame = self.frames[self.frame_index]
            if not self.duck.facing_right:
                frame = frame.transformed(QtGui.QTransform().scale(-1, 1))
            self.duck.current_frame = frame
            self.duck.update()

class ResourceManager:
    """
    Manages resources such as animations, sounds, and skins for the duck.

    Attributes:
        scale_factor: The scale factor for resizing resources.
        pet_size: The size of the pet.
        animations: A dictionary storing animation frames.
        sounds: A list of sound file paths.
    """
    def __init__(self, scale_factor: float, pet_size: int = 3) -> None:
        """
        Initializes the resource manager.

        Args:
            scale_factor (float): The scale factor for resizing resources.
            pet_size (int): The size of the pet.
        """
        self.assets_dir = resource_path('assets')
        self.skins_dir = os.path.join(self.assets_dir, 'skins')
        self.current_skin = 'default'
        self.current_skin_temp_dir = None
        self.animations: Dict[str, List[QPixmap]] = {}
        self.sounds: List[str] = []
        self.scale_factor = scale_factor
        self.pet_size = pet_size

        # Default animations configuration
        self.default_animations_config = {
            "idle": ["0:0"],
            "walk": ["1:0", "1:1", "1:2", "1:3", "1:4", "1:5"],
            "listen": ["2:1"],
            "fall": ["2:3"],
            "jump": ["2:0", "2:1", "2:2", "2:3"],
            "sleep": ["0:1"],
            "sleep_transition": ["2:1"]
        }

        # New lazy loading fields
        self.spritesheet_path: Optional[str] = None
        self.frame_width = 32
        self.frame_height = 32
        self.animations_config = self.default_animations_config.copy()
        self.sound_files: List[str] = []
        self.loaded_spritesheet: Optional[QPixmap] = None
        self.loaded_frames_cache: Dict[Tuple[int,int], QPixmap] = {}
        self.sprites_loaded = False
        self.sounds_loaded = False

        self.load_default_skin(lazy=True)

    def load_skin_frames_for_preview(self, is_default=False, skin_path=None):
        try:
            if is_default:
                animations_config = self.default_animations_config
                spritesheet_path = os.path.join(self.skins_dir, 'default', 'spritesheet.png')
                frame_width, frame_height = 32, 32
            else:
                with zipfile.ZipFile(skin_path, 'r') as zip_ref:
                    temp_dir = tempfile.mkdtemp()
                    zip_ref.extractall(temp_dir)

                    config_path = os.path.join(temp_dir, 'config.json')
                    with open(config_path, 'r') as f:
                        config = json.load(f)

                    frame_width = config.get('frame_width')
                    frame_height = config.get('frame_height')
                    animations_config = config.get('animations', {})
                    spritesheet_path = os.path.join(temp_dir, config.get('spritesheet', ''))

            if not os.path.exists(spritesheet_path):
                logging.error(f"Spritesheet not found: {spritesheet_path}")
                return []

            spritesheet = QtGui.QPixmap(spritesheet_path)
            if spritesheet.isNull():
                logging.error(f"Failed to load spritesheet: {spritesheet_path}")
                return []

            idle_frames = []
            for frame_str in animations_config.get('idle', []):
                try:
                    row, col = map(int, frame_str.split(':'))
                    x = col * frame_width
                    y = row * frame_height
                    frame = spritesheet.copy(x, y, frame_width, frame_height)
                    idle_frames.append(frame)
                except Exception as e:
                    logging.error(f"Error extracting frame {frame_str}: {e}")
            return idle_frames
        except Exception as e:
            logging.error(f"Error loading frames for preview: {e}")
            return []

    def cleanup_temp_dir(self) -> None:
        if self.current_skin_temp_dir and os.path.exists(self.current_skin_temp_dir):
            try:
                shutil.rmtree(self.current_skin_temp_dir)
                logging.info(f"Temporary skin directory {self.current_skin_temp_dir} removed.")
            except Exception as e:
                logging.error(f"Failed to remove temporary skin directory {self.current_skin_temp_dir}: {e}")
            self.current_skin_temp_dir = None
        # Clearing animations and sounds (cache)
        self.animations.clear()
        self.sounds.clear()
        self.loaded_spritesheet = None
        self.loaded_frames_cache.clear()
        self.sprites_loaded = False
        self.sounds_loaded = False

    def validate_config(self, config: dict) -> bool:
        required_keys = ["spritesheet", "frame_width", "frame_height", "animations"]
        for k in required_keys:
            if k not in config:
                logging.error(f"Config is invalid: missing '{k}'")
                return False
        if not isinstance(config['animations'], dict):
            logging.error("Config is invalid: 'animations' is not a dict")
            return False
        return True

    def load_default_skin(self, lazy: bool = False) -> None:
        """
        Loads the default skin resources.

        Args:
            lazy (bool): If True, loads resources lazily.
        """
        logging.info("Default skin loading triggered.")
        log_call_stack()

        self.cleanup_temp_dir()
        self.current_skin = 'default'
        skin_path = os.path.join(self.skins_dir, 'default')
        self.spritesheet_path = os.path.join(skin_path, 'spritesheet.png')
        self.frame_width = 32
        self.frame_height = 32
        self.animations_config = self.default_animations_config.copy()
        self.sound_files = [os.path.join(skin_path, 'wuak.wav')]

        if not lazy:
            self.load_sprites_now()
            self.load_sounds_now()

    def load_spritesheet_if_needed(self) -> None:
        if self.loaded_spritesheet is None and self.spritesheet_path:
            spritesheet = QtGui.QPixmap(self.spritesheet_path)
            if spritesheet.isNull():
                logging.error(f"Failed to load spritesheet image: {self.spritesheet_path}")
                # fallback to default
                self.load_default_skin(lazy=False)
                return
            self.loaded_spritesheet = spritesheet

    def load_sprites_now(self) -> None:
        # Full sprites download on request
        if self.sprites_loaded:
            return
        self.load_spritesheet_if_needed()
        if self.loaded_spritesheet is None:
            return

        self.animations.clear()
        for anim_name, frame_list in self.animations_config.items():
            frames = self.get_animation_frames(lambda r,c: self.get_frame(r,c), frame_list)
            self.animations[anim_name] = frames
            logging.info(f"Loaded animation '{anim_name}' with {len(frames)} frames.")
        self.sprites_loaded = True

    def load_sounds_now(self) -> None:
        if self.sounds_loaded:
            return
        self.sounds = self.sound_files.copy()
        logging.info(f"Loaded {len(self.sounds)} sound files.")
        self.sounds_loaded = True

    def load_skin(self, skin_file: str) -> bool:
        self.cleanup_temp_dir()

        if not (os.path.isfile(skin_file) and skin_file.endswith('.zip')):
            logging.error(f"Invalid skin file: {skin_file}")
            self.load_default_skin(lazy=True)
            return False

        try:
            with zipfile.ZipFile(skin_file, 'r') as zip_ref:
                if 'config.json' not in zip_ref.namelist():
                    logging.error(f"Skin {skin_file} does not contain config.json.")
                    self.load_default_skin(lazy=True)
                    return False

                temp_dir = tempfile.mkdtemp()
                self.current_skin_temp_dir = temp_dir
                logging.info(f"Temporary skin files extracted to: {temp_dir}")
                zip_ref.extractall(temp_dir)

                config_path = os.path.join(temp_dir, 'config.json')
                with open(config_path, 'r') as f:
                    config = json.load(f)

                if not self.validate_config(config):
                    logging.error("Skin config is invalid, fallback to default skin.")
                    self.load_default_skin(lazy=True)
                    return False

                spritesheet_name = config.get('spritesheet')
                frame_width = config.get('frame_width')
                frame_height = config.get('frame_height')
                animations = config.get('animations', {})

                spritesheet_path = os.path.join(temp_dir, spritesheet_name)
                if not os.path.exists(spritesheet_path):
                    logging.error(f"Spritesheet {spritesheet_name} does not exist.")
                    self.load_default_skin(lazy=True)
                    return False

                sound_names = config.get('sound', [])
                if isinstance(sound_names, str):
                    sound_names = [sound_names]

                sound_paths = []
                for sname in sound_names:
                    spath = os.path.join(temp_dir, sname)
                    if os.path.exists(spath) and sname.endswith('.wav'):
                        sound_paths.append(spath)
                    else:
                        logging.warning(f"Sound file {sname} is not in WAV format or does not exist.")

                self.spritesheet_path = spritesheet_path
                self.sound_files = sound_paths
                self.frame_width = frame_width
                self.frame_height = frame_height
                self.animations_config = animations
                self.current_skin = skin_file
                # Lazily load, without full call load_sprites_now / load_sounds_now

                return True
        except Exception as e:
            logging.error(f"Failed to load skin {skin_file}: {e}")
            self.load_default_skin(lazy=True)
            return False

    def set_pet_size(self, pet_size: int) -> None:
        self.pet_size = pet_size
        # Reset cache
        self.loaded_frames_cache.clear()
        self.sprites_loaded = False
        self.animations.clear()
        self.loaded_spritesheet = None

    def get_frame(self, row: int, col: int) -> QPixmap:
        if self.loaded_spritesheet is None:
            self.load_spritesheet_if_needed()
            if self.loaded_spritesheet is None:
                return QPixmap()

        # Use frame cache
        key = (row, col)
        if key in self.loaded_frames_cache:
            return self.loaded_frames_cache[key]

        spritesheet = self.loaded_spritesheet
        frame = spritesheet.copy(col * self.frame_width, row * self.frame_height, self.frame_width, self.frame_height)

        # Scale by pet_size directly, without KeepAspectRatio:
        # With pet_size=1 the frame size will be the original (frame_width x frame_height).
        # With pet_size=2 it will be 2 times bigger, etc.
        new_width = self.frame_width * self.pet_size
        new_height = self.frame_height * self.pet_size
        frame = frame.scaled(
            new_width,
            new_height,
            QtCore.Qt.IgnoreAspectRatio,
            QtCore.Qt.FastTransformation
        )

        self.loaded_frames_cache[key] = frame
        return frame

    def get_animation_frames_by_name(self, animation_name: str) -> List[QPixmap]:
        if animation_name in self.animations:
            return self.animations[animation_name]
        if not self.sprites_loaded:
            self.load_sprites_now()
        return self.animations.get(animation_name, [])

    def get_animation_frame(self, animation_name: str, frame_index: int) -> Optional[QPixmap]:
        frames = self.get_animation_frames_by_name(animation_name)
        if frames and 0 <= frame_index < len(frames):
            return frames[frame_index]
        return None

    def get_default_frame(self) -> Optional[QPixmap]:
        frame = self.get_animation_frame('idle', 0)
        if frame:
            return frame
        for frames in self.animations.values():
            if frames:
                return frames[0]
        return None

    def get_idle_animations(self) -> List[str]:
        # idle animations will be known only after loading
        if not self.sprites_loaded:
            self.load_sprites_now()
        return [name for name in self.animations.keys() if name.startswith('idle')]

    def load_idle_frames_from_skin(self, skin_file: str) -> Optional[List[QPixmap]]:
        try:
            with zipfile.ZipFile(skin_file, 'r') as zip_ref:
                if 'config.json' not in zip_ref.namelist():
                    logging.error(f"Skin {skin_file} does not contain config.json.")
                    return None

                with tempfile.TemporaryDirectory() as temp_dir:
                    logging.info(f"Temporary skin files extracted to: {temp_dir}")
                    zip_ref.extractall(temp_dir)

                    config_path = os.path.join(temp_dir, 'config.json')
                    with open(config_path, 'r') as f:
                        config = json.load(f)

                    # Checking the config
                    if not all(k in config for k in ('spritesheet','frame_width','frame_height','animations')):
                        logging.error(f"Config file is incomplete in {skin_file}.")
                        return None

                    animations = config.get('animations', {})
                    idle_animation_keys = [key for key in animations.keys() if key.startswith('idle')]
                    if not idle_animation_keys:
                        logging.error(f"No idle animation in {skin_file}.")
                        return None

                    idle_animation_key = idle_animation_keys[0]
                    frame_list = animations[idle_animation_key]

                    spritesheet_name = config.get('spritesheet')
                    frame_width = config.get('frame_width')
                    frame_height = config.get('frame_height')

                    spritesheet_path = os.path.join(temp_dir, spritesheet_name)
                    spritesheet = QtGui.QPixmap(spritesheet_path)
                    if spritesheet.isNull():
                        logging.error("Failed to load spritesheet for preview.")
                        return None

                    frames = []
                    for frame_str in frame_list:
                        row_col = frame_str.split(':')
                        if len(row_col) == 2:
                            try:
                                row = int(row_col[0])
                                col = int(row_col[1])
                                frame = spritesheet.copy(col*frame_width, row*frame_height, frame_width, frame_height)
                                # When previewing, you can choose not to scale or scale as desired
                                frames.append(frame)
                            except ValueError:
                                logging.error(f"Incorrect frame format: {frame_str}")
                    return frames
        except Exception as e:
            logging.error(f"Failed to load skin {skin_file}: {e}")
            return None

    def get_animation_frames(self, get_frame_func, frame_list: List[str]) -> List[QPixmap]:
        frames = []
        for frame_str in frame_list:
            row_col = frame_str.split(':')
            if len(row_col) == 2:
                try:
                    row = int(row_col[0])
                    col = int(row_col[1])
                    frame = get_frame_func(row, col)
                    if not frame.isNull():
                        frames.append(frame)
                except ValueError:
                    logging.error(f"Incorrect frame format: {frame_str}")
        return frames

    def get_random_sound(self) -> Optional[str]:
        if not self.sounds_loaded:
            self.load_sounds_now()
        return random.choice(self.sounds) if self.sounds else None

    def __del__(self):
        self.cleanup_temp_dir()

class MicrophoneListener(QtCore.QThread):
    volume_signal = QtCore.pyqtSignal(int)

    def __init__(self, device_index=None, activation_threshold=10, parent=None):
        super().__init__(parent)
        self.device_index = device_index
        self.activation_threshold = activation_threshold
        self.running = True

    def run(self):
        def audio_callback(indata, frames, time, status):
            try:
                if status:
                    logging.warning(f"Status: {status}")
                volume_norm = np.linalg.norm(indata) * 10
                volume_percentage = min(int(volume_norm), 100)
                self.volume_signal.emit(volume_percentage)
            except Exception as e:
                logging.error(f"Error in audio_callback: {e}")

        try:
            with sd.InputStream(device=self.device_index,
                                channels=1,
                                samplerate=44100,
                                callback=audio_callback):
                while self.running:
                    self.msleep(100)
        except Exception as e:
            logging.error(f"Error opening audio stream: {e}")
            self.running = False

    def stop(self):
        self.running = False
        self.wait()

    def update_settings(self, device_index=None, activation_threshold=None):
        if device_index is not None:
            self.device_index = device_index
        if activation_threshold is not None:
            self.activation_threshold = activation_threshold

class SystemTrayIcon(QtWidgets.QSystemTrayIcon):
    def __init__(self, parent=None):
        self.visible_icon_path = resource_path("assets/images/white-quackduck-visible.ico")
        self.hidden_icon_path = resource_path("assets/images/white-quackduck-hidden.ico")

        if not os.path.exists(self.visible_icon_path):
            logging.error(f"Icon file {self.visible_icon_path} not found.")
            QtWidgets.QMessageBox.critical(
                parent, 
                translations.get("error_title", "Error!"), 
                translations.get("file_not_found", "File not found:") + f": '{self.visible_icon_path}'"
            )
            super().__init__()  # Initialize without an icon
        else:
            icon = QtGui.QIcon(self.visible_icon_path)
            super().__init__(icon, parent)

        self.parent = parent
        self.setup_menu()
        self.activated.connect(self.icon_activated)

    def setup_menu(self):
        menu = QtWidgets.QMenu()
        
        # Existing Menu Actions
        settings_action = menu.addAction(translations.get("settings", "⚙️ Settings"))
        settings_action.triggered.connect(self.parent.open_settings)

        unstuck_action = menu.addAction(translations.get("unstuck", "🔄 Unstuck"))
        unstuck_action.triggered.connect(self.parent.unstuck_duck)

        about_action = menu.addAction(translations.get("about", "👋 About"))
        about_action.triggered.connect(self.show_about)

        check_updates_action = menu.addAction(translations.get("check_updates", "🔄 Update"))
        check_updates_action.triggered.connect(self.check_for_updates)

        menu.addSeparator()
        
        show_action = menu.addAction(translations.get("show", "👀 Show"))
        hide_action = menu.addAction(translations.get("hide", "🙈 Hide"))

        menu.addSeparator()

        coffee_action = menu.addAction(translations.get("buy_me_a_coffee", "☕ Buy me a coffee"))
        coffee_action.triggered.connect(lambda: webbrowser.open("https://buymeacoffee.com/zl0yxp"))

        exit_action = menu.addAction(translations.get("exit", "🚪 Close"))

        show_action.triggered.connect(self.show_duck)
        hide_action.triggered.connect(self.hide_duck)
        exit_action.triggered.connect(QtWidgets.qApp.quit)

        menu.addSeparator()

        if GLOBAL_DEBUG_MODE:
            debug_action = menu.addAction(translations.get("debug_mode", "🛠️ Debug mode"))
            debug_action.triggered.connect(self.parent.show_debug_window)  # Connect to Duck method

        self.setContextMenu(menu)

        self.contextMenu().setStyleSheet("""
            QMenu {
                background-color: #2a2a2a;
                color: white;
                border: 1px solid #444;
            }
            QMenu::item:selected {
                background-color: #3a3a3a;
            }
            QMenu::separator {
                height: 1px;
                background: #444;
                margin: 5px 0;
            }
        """)

    def hide_duck(self):
        self.parent.hide()
        if os.path.exists(self.hidden_icon_path):
            self.setIcon(QtGui.QIcon(self.hidden_icon_path))
        # force_idle=False, so as not to switch states
        self.parent.pause_duck(force_idle=False)

    def show_duck(self):
        self.parent.show()
        self.parent.raise_()
        self.parent.activateWindow()
        if os.path.exists(self.visible_icon_path):
            self.setIcon(QtGui.QIcon(self.visible_icon_path))
        self.parent.resume_duck()

    def icon_activated(self, reason):
        if reason == QtWidgets.QSystemTrayIcon.DoubleClick:
            self.parent.open_settings()
            self.show_duck()
        elif reason == QtWidgets.QSystemTrayIcon.Trigger:
            if self.parent.isVisible():
                self.hide_duck()
            else:
                self.show_duck()

    def check_for_updates(self):
        """
        Called when user clicks 'Check for updates' in the tray menu.
        We call duck.check_for_updates_manual() to handle the logic.
        """
        self.parent.check_for_updates_manual()

    def show_about(self):
        about_text = "QuackDuck\nDeveloped with 💜 by zl0yxp\nDiscord: zl0yxp\nTelegram: t.me/quackduckapp"
        QtWidgets.QMessageBox.information(
            self.parent,
            translations.get("about_title", "About"),
            about_text,
            QtWidgets.QMessageBox.Ok
        )

class SettingsManager:
    """
    Manages application settings using Qt's QSettings.

    Attributes:
        _settings: An instance of QSettings for handling key-value pairs.
    """
    def __init__(self, organization: str = 'zl0yxp', application: str = 'QuackDuck') -> None:
        """
        Initializes the SettingsManager with the given organization and application name.

        Args:
            organization (str): Organization name for QSettings.
            application (str): Application name for QSettings.
        """
        self._settings = QtCore.QSettings(organization, application)

    def get_value(self, key: str, default=None, value_type=None):
        """
        Retrieves a value from the settings.

        Args:
            key (str): The settings key to retrieve.
            default: The default value if the key does not exist.
            value_type: The type of the value to return.

        Returns:
            The value associated with the key, or the default value if the key does not exist.
        """
        return self._settings.value(key, defaultValue=default, type=value_type)

    def set_value(self, key: str, value) -> None:
        """
        Sets a value in the settings.

        Args:
            key (str): The settings key.
            value: The value to set.
        """
        self._settings.setValue(key, value)

    def clear(self) -> None:
        """Clears all settings."""
        self._settings.clear()

    def sync(self) -> None:
        """Synchronizes the settings with the underlying storage."""
        self._settings.sync()

class FlowLayout(QLayout):
    def __init__(self, parent=None, scale_factor=1.0):
        super().__init__(parent)
        self.itemList = []
        self.scale_factor = scale_factor

        # Step between elements - scaling.
        self.setContentsMargins(0, 0, 0, 0)
        self.setSpacing(int(10 * self.scale_factor))

    def addItem(self, item):
        self.itemList.append(item)

    def count(self):
        return len(self.itemList)

    def itemAt(self, index):
        if 0 <= index < len(self.itemList):
            return self.itemList[index]
        return None

    def takeAt(self, index):
        if 0 <= index < len(self.itemList):
            return self.itemList.pop(index)
        return None

    def expandingDirections(self):
        return Qt.Orientations(Qt.Orientation(0))

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self.doLayout(QRect(0, 0, width, 0), True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self.doLayout(rect, False)

    def sizeHint(self):
        return QSize(0,0)

    def doLayout(self, rect, testOnly):
        left, top, right, bottom = self.getContentsMargins()
        space = self.spacing()

        x = rect.x() + left
        y = rect.y() + top
        lineHeight = 0

        for item in self.itemList:
            w = item.widget()
            hint = w.sizeHint()

            if x + hint.width() > rect.right() - right and (x > rect.x() + left):
                x = rect.x() + left
                y = y + lineHeight + space
                lineHeight = 0

            if not testOnly:
                item.setGeometry(QRect(x, y, hint.width(), hint.height()))

            x = x + hint.width() + space
            lineHeight = max(lineHeight, hint.height())

        return y + lineHeight + bottom - rect.y()

class SidebarButton(QPushButton):
    def __init__(self, text, parent=None, scale_factor=1.0):
        super().__init__(text, parent)
        self.scale_factor = scale_factor
        s = lambda val: int(val * self.scale_factor)

        self.setFixedHeight(s(40))

        accent_rgb = globals()['get_system_accent_color']()
        self.accent_qcolor = get_system_accent_color()
        self.accent_color = self.accent_qcolor.name()

        self.setCursor(Qt.PointingHandCursor)
        self.setCheckable(True)

        base_font_size = 14
        scaled_font_size = max(1, int(base_font_size * self.scale_factor))

        self.setStyleSheet(f"""
            QPushButton {{
                text-align: left;
                padding-left: {s(16)}px;
                border: none;
                font-size: {scaled_font_size}px;
                color: #ccc;
            }}
            QPushButton:hover {{
                background-color: #3a3a3a;
            }}
            QPushButton:checked {{
                background-color: #3a3a3a;
                color: #e0e0e0;
                border-left: {s(4)}px solid {self.accent_color};
                padding-left: {s(12)}px;
            }}
        """)

class SettingsWindow(QMainWindow):
    def __init__(self, duck):
        super().__init__()
        self.duck = duck

        self.scale_factor = getattr(self.duck, 'scale_factor', 1.0)
        s = lambda val: int(val * self.scale_factor)

        self.translations = globals()['translations']

        accent_rgb = globals()['get_system_accent_color']()
        self.accent_qcolor = get_system_accent_color()
        self.accent_color = self.accent_qcolor.name()

        self.setWindowTitle(self.translations.get("settings_title", "Settings"))
        icon_path = os.path.join(self.duck.resources.assets_dir, "images", "settings.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        base_w, base_h = 1000, 600
        self.resize(s(base_w), s(base_h))

        container = QWidget()
        self.setCentralWidget(container)

        main_layout = QHBoxLayout(container)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.sidebar = QVBoxLayout()
        self.sidebar.setContentsMargins(s(0), s(0), s(0), s(10))
        self.sidebar.setSpacing(0)

        self.app_title = QHBoxLayout()
        self.app_title.setContentsMargins(s(20), s(20), s(20), s(20))
        self.app_title.setSpacing(s(10))

        self.app_label = QLabel(self.translations.get("settings_title","Settings"))
        title_font_size = max(1, int(16 * self.scale_factor))
        self.app_label.setStyleSheet(f"font-weight:600;font-size:{title_font_size}px;color:#fff;")
        self.app_title.addWidget(self.app_label)
        self.app_title.addStretch()
        self.sidebar.addLayout(self.app_title)

        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        line.setStyleSheet("color:#3a3a3a;")
        self.sidebar.addWidget(line)

        self.btn_general = SidebarButton(self.translations.get("page_button_general","General"), scale_factor=self.scale_factor)
        self.btn_general.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        self.btn_appearance = SidebarButton(self.translations.get("page_button_appearance","Appearance"), scale_factor=self.scale_factor)
        self.btn_appearance.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        self.btn_advanced = SidebarButton(self.translations.get("page_button_advanced","Advanced"), scale_factor=self.scale_factor)
        self.btn_advanced.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        self.btn_about = SidebarButton(self.translations.get("page_button_about","About"), scale_factor=self.scale_factor)
        self.btn_about.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))

        self.btn_general.setChecked(True)
        for btn in [self.btn_general, self.btn_appearance, self.btn_advanced, self.btn_about]:
            btn.clicked.connect(self.change_tab)
            self.sidebar.addWidget(btn)

        self.sidebar.addStretch()

        version_label = QLabel(self.translations.get("version","Version") + f" {globals()['PROJECT_VERSION']}")
        version_label_font_size = max(1, int(12 * self.scale_factor))
        version_label.setStyleSheet(f"color:#aaa;font-size:{version_label_font_size}px;")
        version_label.setAlignment(Qt.AlignCenter)
        self.sidebar.addWidget(version_label)

        self.stack = QStackedWidget()
        self.stack.setStyleSheet("QWidget { color: #ccc; }")

        self.stack.addWidget(self.general_tab())
        self.stack.addWidget(self.appearance_tab())
        self.stack.addWidget(self.advanced_tab())
        self.stack.addWidget(self.about_tab())

        main_layout.addWidget(self.sidebar_container())
        main_layout.addWidget(self.stack, 1)

        self.apply_stylesheet()

        self.mic_preview_timer = QTimer(self)
        self.mic_preview_timer.timeout.connect(self.update_mic_preview)
        self.mic_preview_timer.start(100)

    def sidebar_container(self):
        s = lambda val: int(val * self.scale_factor)
        w = QWidget()
        w.setLayout(self.sidebar)

        w.setFixedWidth(s(220))
        w.setStyleSheet("background-color:#2a2a2a;")
        return w

    def apply_stylesheet(self):
        s = lambda val: int(val * self.scale_factor)
        base_font_size = 14
        scaled_font_size = max(1, int(base_font_size * self.scale_factor))
        self.setStyleSheet(f"""
            QMainWindow {{
                background: #1e1e1e;
            }}
            QCheckBox, QRadioButton, QLabel, QComboBox, QSpinBox, QLineEdit {{
                font-size:{scaled_font_size}px;
            }}
            QLineEdit, QSpinBox, QComboBox {{
                background: #2f2f2f;
                border:1px solid #444;
                border-radius:3px;
                padding:{s(4)}px;
                color:#ccc;
            }}
            QComboBox QAbstractItemView {{
                background: #2f2f2f;
                border:1px solid #444;
                color:#ccc;
                selection-background-color:#3a3a3a;
                selection-color:#fff;
            }}

            QLineEdit:focus, QComboBox:focus, QSpinBox:focus {{
                border:1px solid {self.accent_color};
                outline: none;
            }}
            QPushButton {{
                background-color: {self.accent_color};
                color:#fff;
                border:none;
                border-radius:3px;
                padding:{s(8)}px {s(14)}px;
                font-size:{scaled_font_size}px;
            }}
            QPushButton:hover {{
                background-color: {self.accent_qcolor.lighter(120).name()};
            }}
            QSlider::groove:horizontal {{
                background:#444;
                height:{s(6)}px;
                border-radius:{s(3)}px;
            }}
            QSlider::handle:horizontal {{
                background:{self.accent_color};
                width:{s(14)}px;
                height:{s(14)}px;
                margin:-{s(4)}px 0;
                border-radius:{s(7)}px;
            }}
            QSlider::sub-page:horizontal {{
                background:{self.accent_color};
                border-radius:{s(3)}px;
            }}
            QProgressBar {{
                background:#444;
                border:1px solid #555555;
                border-radius:{s(3)}px;
                height:{s(12)}px;
                text-align:center;
                color:white;
                font-size:{scaled_font_size}px;
                padding:{s(5)}px;
            }}
            QProgressBar::chunk {{
                background:{self.accent_color};
                border-radius:{s(3)}px;
            }}
            QScrollBar:vertical {{
                background:#2f2f2f; width:{s(8)}px;
            }}
            QScrollBar::handle:vertical {{
                background: {self.accent_color};
                border-radius:{s(3)}px;
                min-height:{s(20)}px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height:0;
                background:none;
            }}
            QPushButton#cancelButton {{
                background-color: #444;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                transition: background-color 0.3s ease;
            }}
            QPushButton#cancelButton:hover {{
                background-color: #555;
            }}
        """)

        if hasattr(self, 'skins_container'):
            self.skins_container.setStyleSheet("background-color: #1e1e1e; ")

        if hasattr(self, 'skins_scroll'):
            self.skins_scroll.setStyleSheet("QScrollArea { background-color: #1e1e1e; border: 1px solid #444; border-radius: 3px; }")

    def change_tab(self):
        sender = self.sender()
        if sender == self.btn_general:
            self.btn_general.setChecked(True)
            self.btn_appearance.setChecked(False)
            self.btn_advanced.setChecked(False)
            self.btn_about.setChecked(False)
            self.stack.setCurrentIndex(0)
        elif sender == self.btn_appearance:
            self.btn_general.setChecked(False)
            self.btn_appearance.setChecked(True)
            self.btn_advanced.setChecked(False)
            self.btn_about.setChecked(False)
            self.stack.setCurrentIndex(1)
        elif sender == self.btn_advanced:
            self.btn_general.setChecked(False)
            self.btn_appearance.setChecked(False)
            self.btn_advanced.setChecked(True)
            self.btn_about.setChecked(False)
            self.stack.setCurrentIndex(2)
        elif sender == self.btn_about:
            self.btn_general.setChecked(False)
            self.btn_appearance.setChecked(False)
            self.btn_advanced.setChecked(False)
            self.btn_about.setChecked(True)
            self.stack.setCurrentIndex(3)

    # General tab in a settings
    def general_tab(self):
        s = lambda val: int(val * self.scale_factor)

        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(s(20), s(20), s(20), s(20))
        layout.setSpacing(s(20))

        title_font_size = max(1, int(20 * self.scale_factor))
        title = QLabel(self.translations.get("page_button_general","General"))
        title.setStyleSheet(f"font-size:{title_font_size}px;font-weight:bold;color:#fff;border-bottom:1px solid #3a3a3a;padding-bottom:{s(10)}px;")
        layout.addWidget(title)

        # Pet Name
        pet_name_box = QVBoxLayout()
        lbl_petname = QLabel(self.translations.get("pet_name","Pet Name:"))
        h_name = QHBoxLayout()
        self.petName = QLineEdit()
        self.petName.setPlaceholderText(self.translations.get("enter_name_placeholder","Name..."))
        self.petName.setText(self.duck.pet_name)

        name_info_button = QPushButton("❓")
        name_info_button.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        name_info_button.setFixedSize(s(36), s(36))
        name_button_font = name_info_button.font()
        name_button_font.setPointSize(max(1,int(16 * self.scale_factor)))
        name_info_button.setFont(name_button_font)
        name_info_button.setToolTip(self.translations.get("info_about_pet_name_tooltip","Information about pet name"))
        name_info_button.setStyleSheet(f"QPushButton {{ padding:{s(4)}px; }}")
        name_info_button.clicked.connect(self.show_name_characteristics)

        h_name.addWidget(self.petName)
        h_name.addWidget(name_info_button)

        pet_name_box.addWidget(lbl_petname)
        pet_name_box.addLayout(h_name)
        layout.addLayout(pet_name_box)

        # Input Device
        mic_box = QVBoxLayout()
        lbl_mic = QLabel(self.translations.get("input_device_selection","Input Device:"))
        self.micDevice = QComboBox()
        devices = self.duck.get_input_devices()
        for idx,name in devices:
            self.micDevice.addItem(name,idx)
        if self.duck.selected_mic_index is not None:
            mic_idx = self.micDevice.findData(self.duck.selected_mic_index)
            if mic_idx>=0:self.micDevice.setCurrentIndex(mic_idx)
        mic_box.addWidget(lbl_mic)
        mic_box.addWidget(self.micDevice)
        layout.addLayout(mic_box)

        # Activation Threshold
        lbl_thresh = QLabel(self.translations.get("activation_threshold","Activation Threshold:"))
        self.thresholdValue = QLabel(f"{self.duck.activation_threshold}%")
        self.thresholdSlider = QSlider(Qt.Horizontal)
        self.thresholdSlider.setRange(0,100)
        self.thresholdSlider.setValue(self.duck.activation_threshold)
        self.thresholdSlider.valueChanged.connect(lambda v: self.thresholdValue.setText(f"{v}%"))

        thresh_layout = QVBoxLayout()
        thresh_layout.addWidget(lbl_thresh)
        h_thresh = QHBoxLayout()
        h_thresh.addWidget(self.thresholdValue)
        h_thresh.addWidget(self.thresholdSlider)
        thresh_layout.addLayout(h_thresh)

        # Mic volume preview
        lbl_mic_level = QLabel(self.translations.get("mic_level","Sound Level:"))
        thresh_layout.addWidget(lbl_mic_level)
        self.mic_level_preview = QProgressBar()
        self.mic_level_preview.setRange(0,100)
        self.mic_level_preview.setValue(self.duck.current_volume if hasattr(self.duck,'current_volume') else 0)
        thresh_layout.addWidget(self.mic_level_preview)
        layout.addLayout(thresh_layout)

        # Enable Sound + volume
        cb_layout = QVBoxLayout()
        self.enableSound = QCheckBox(self.translations.get("turn_on_sound","Enable Sound"))
        self.enableSound.setChecked(self.duck.sound_enabled)
        self.enableSound.stateChanged.connect(self.toggle_volume_slider)
        cb_layout.addWidget(self.enableSound)

        self.volumeLabel = QLabel(self.translations.get("volume","Volume:"))
        self.volumeValue = QLabel("50%")
        self.volumeSlider = QSlider(Qt.Horizontal)
        self.volumeSlider.setRange(0,100)
        volume_from_settings = self.duck.settings_manager.get_value('sound_volume',0.5,float)
        initial_vol = int(volume_from_settings*100)
        self.volumeSlider.setValue(initial_vol)
        self.volumeValue.setText(f"{initial_vol}%")

        def update_volume(v):
            self.volumeValue.setText(f"{v}%")
            vol = v/100.0
            self.soundEffect.setVolume(vol)
            self.duck.sound_effect.setVolume(vol)
            self.duck.sound_volume = vol
            self.duck.settings_manager.set_value('sound_volume', vol)
            self.duck.settings_manager.sync()

        self.volumeSlider.valueChanged.connect(update_volume)
        self.volumeSlider.sliderReleased.connect(self.play_random_sound_on_volume_release)

        from PyQt5.QtMultimedia import QSoundEffect
        self.soundEffect = QSoundEffect()
        default_skin_path = self.duck.skin_folder if self.duck.skin_folder else os.path.join(self.duck.resources.skins_dir,'default')
        sound_path = os.path.join(default_skin_path, 'wuak.wav')
        self.soundEffect.setSource(QUrl.fromLocalFile(sound_path))
        self.soundEffect.setVolume(initial_vol/100.0)

        vol_layout = QVBoxLayout()
        vol_layout.addWidget(self.volumeLabel)
        h_vol = QHBoxLayout()
        h_vol.addWidget(self.volumeValue)
        h_vol.addWidget(self.volumeSlider)
        vol_layout.addLayout(h_vol)
        cb_layout.addLayout(vol_layout)

        self.showName = QCheckBox(self.translations.get("show_name_checkbox","Show name above duck"))
        self.showName.setChecked(self.duck.show_name)
        cb_layout.addWidget(self.showName)
        layout.addLayout(cb_layout)

        layout.addStretch()

        act_box = QHBoxLayout()
        act_box.addStretch()
        cancel_btn = QPushButton(self.translations.get("cancel_button","Cancel"))
        cancel_btn.clicked.connect(self.close)
        cancel_btn.setObjectName("cancelButton")
        cancel_btn.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        save_btn = QPushButton(self.translations.get("save_button","Save"))
        save_btn.clicked.connect(self.save_general_settings)
        save_btn.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        act_box.addWidget(cancel_btn)
        act_box.addWidget(save_btn)
        layout.addLayout(act_box)

        self.toggle_volume_slider()
        return w

    def play_random_sound_on_volume_release(self):
        if self.enableSound.isChecked():
            self.duck.play_random_sound()

    def toggle_volume_slider(self):
        enabled = self.enableSound.isChecked()
        self.volumeLabel.setVisible(enabled)
        self.volumeValue.setVisible(enabled)
        self.volumeSlider.setVisible(enabled)

    def play_quack_sound(self):
        self.soundEffect.play()

    def show_name_characteristics(self):
        name = self.petName.text().strip()
        if name:
            characteristics = self.duck.get_name_characteristics(name)
            info_text = "\n".join([f"{key}: {value}" for key, value in characteristics.items()])
            QMessageBox.information(self, self.translations.get("characteristics_title","Characteristics"), info_text)
        else:
            QMessageBox.information(
                self,
                self.translations.get("characteristics_title","Characteristics"),
                self.translations.get("characteristics_text","Enter a name to see characteristics.")
            )

    def save_general_settings(self):
        self.duck.pet_name = self.petName.text()
        idx = self.micDevice.currentIndex()
        self.duck.selected_mic_index = self.micDevice.itemData(idx)
        self.duck.activation_threshold = self.thresholdSlider.value()
        self.duck.sound_enabled = self.enableSound.isChecked()
        self.duck.show_name = self.showName.isChecked()
        self.duck.apply_settings()
        self.close()

    # Appearance tab in a settings
    def appearance_tab(self):
        s = lambda val: int(val * self.scale_factor)

        w = QWidget()
        self.appearance_layout = QVBoxLayout(w)
        self.appearance_layout.setContentsMargins(s(20), s(20), s(20), s(20))
        self.appearance_layout.setSpacing(s(20))

        title_font_size = max(1, int(20 * self.scale_factor))
        title = QLabel(self.translations.get("page_button_appearance","Appearance"))
        title.setStyleSheet(f"font-size:{title_font_size}px;font-weight:bold;color:#fff;border-bottom:1px solid #3a3a3a;padding-bottom:{s(10)}px;")
        self.appearance_layout.addWidget(title)

        skins_help_box = QHBoxLayout()
        where_to_get_skins_label = QLabel(self.translations.get("where_to_get_skins","Don't know where to get skins?"))
        f = where_to_get_skins_label.font()
        f.setBold(True)
        where_to_get_skins_label.setFont(f)
        skin_shop_btn = QPushButton("QD Skin Shop")
        skin_shop_btn.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        skin_shop_btn.clicked.connect(lambda: self.open_link("https://test.test"))
        skins_help_box.addWidget(where_to_get_skins_label)
        skins_help_box.addStretch()
        skins_help_box.addWidget(skin_shop_btn)
        self.appearance_layout.addLayout(skins_help_box)

        # Pet Size
        size_box = QVBoxLayout()
        lbl_size = QLabel(self.translations.get("pet_size","Pet size:"))
        self.petSize = QComboBox()
        size_map = {1:"x1",2:"x2",3:"x3",5:"x5",10:"x10"}
        for v,txt in size_map.items():
            self.petSize.addItem(txt,v)
        idx = self.petSize.findData(self.duck.pet_size)
        if idx>=0:
            self.petSize.setCurrentIndex(idx)
        size_box.addWidget(lbl_size)
        size_box.addWidget(self.petSize)
        self.appearance_layout.addLayout(size_box)

        folder_box = QVBoxLayout()
        lbl_folder = QLabel(self.translations.get("skin_folder_path","Skins folder path:"))
        f_hbox = QHBoxLayout()
        self.folderPath = QLineEdit()
        self.folderPath.setPlaceholderText(self.translations.get("not_selected","Not selected"))
        self.folderPath.setReadOnly(True)
        if self.duck.skin_folder:
            self.folderPath.setText(self.duck.skin_folder)
        choose_btn = QPushButton(self.translations.get("select_skin_folder_button","Select Skins Folder"))
        choose_btn.clicked.connect(self.select_skins_folder)
        choose_btn.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        f_hbox.addWidget(self.folderPath)
        f_hbox.addWidget(choose_btn)
        folder_box.addWidget(lbl_folder)
        folder_box.addLayout(f_hbox)
        self.appearance_layout.addLayout(folder_box)

        lbl_skins_font_size = max(1, int(16 * self.scale_factor))
        lbl_skins = QLabel(self.translations.get("skins_preview","Skins Preview:"))
        lbl_skins.setStyleSheet(f"font-size:{lbl_skins_font_size}px;color:#ddd;")
        self.appearance_layout.addWidget(lbl_skins)

        self.skins_scroll = QScrollArea()
        self.skins_scroll.setWidgetResizable(True)
        self.skins_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.skins_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        self.skins_container = QWidget()
        self.skins_layout = FlowLayout(scale_factor=self.scale_factor)
        self.skins_container.setLayout(self.skins_layout)

        self.skins_scroll.setWidget(self.skins_container)
        self.skins_scroll.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.appearance_layout.addWidget(self.skins_scroll)

        self.load_skins_from_folder(self.duck.skin_folder)

        act_box = QHBoxLayout()
        act_box.addStretch()
        cancel_btn = QPushButton(self.translations.get("cancel_button","Cancel"))
        cancel_btn.clicked.connect(self.close)
        cancel_btn.setObjectName("cancelButton")
        cancel_btn.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        save_btn = QPushButton(self.translations.get("save_button","Save"))
        save_btn.clicked.connect(self.save_appearance_settings)
        save_btn.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        act_box.addWidget(cancel_btn)
        act_box.addWidget(save_btn)
        self.appearance_layout.addLayout(act_box)

        return w

    def select_skins_folder(self):
        """
        Called when user clicks the 'Select Skins Folder' button.
        Opens a directory dialog for the user to pick a folder,
        then calls load_skins_from_folder(...) with show_warning_on_empty=True.
        """
        folder = QFileDialog.getExistingDirectory(
            self,
            self.translations.get("select_skin_folder","Select skins folder")
        )
        if folder:
            self.folderPath.setText(folder)
            self.duck.skin_folder = folder
            self.duck.save_settings()

            self.load_skins_from_folder(folder, show_warning_on_empty=True)

    def load_skins_from_folder(self, folder, show_warning_on_empty=False):
        """
        Loads all available skin .zip files from the given folder into the UI preview.
        If show_warning_on_empty=True and no skins found, shows a messagebox warning.
        Otherwise, stays silent if no skins are found.

        Args:
            folder (str): path to the folder containing the .zip skin files
            show_warning_on_empty (bool): whether to display a warning if no skins are found.
        """
        # Clear current skin previews in the UI
        while self.skins_layout.count() > 0:
            item = self.skins_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        # If folder is None or doesn't exist, just return; no warnings unless we want them
        if not folder or not os.path.exists(folder):
            logging.warning("No folder provided or folder does not exist.")
            return

        # Load the default skin preview (if you do that by default)
        frames = self.duck.resources.load_skin_frames_for_preview(is_default=True)
        default_item = self.create_default_skin_item(frames)
        if default_item:
            self.skins_layout.addWidget(default_item)

        has_skins = False

        # Scan for .zip files
        for file in os.listdir(folder):
            if file.lower().endswith(".zip"):
                # If you want to skip 'default' zip
                if 'default' in file.lower():
                    continue

                skin_path = os.path.join(folder, file)
                skin_item = self.create_skin_item(skin_path)
                if skin_item:
                    self.skins_layout.addWidget(skin_item)
                    has_skins = True

        if not has_skins and show_warning_on_empty:
            QMessageBox.warning(
                self,
                self.translations.get("warning_title", "Warning"),
                self.translations.get("no_skins_in_folder", "No skins in the selected folder.")
            )

    def create_default_skin_item(self, frames):
        s = lambda val: int(val * self.scale_factor)
        item = QFrame()
        item.setCursor(Qt.PointingHandCursor)
        item.setStyleSheet("""
            QFrame {
                background:#2f2f2f; border-radius:3px;
            }
            QFrame:hover {
                background:#3a3a3a;
            }
        """)
        item_layout = QVBoxLayout(item)
        item_layout.setContentsMargins(0,0,0,0)

        animation_label = QLabel()
        animation_label.setAlignment(Qt.AlignCenter)
        animation_label.frames = frames
        animation_label.frame_index = 0
        animation_label.setFixedSize(s(128), s(128))

        def update_frame():
            if not animation_label.frames:
                logging.error("No frames available for animation.")
                return
            frm = animation_label.frames[animation_label.frame_index]
            frm_scaled = frm.scaled(s(128), s(128), Qt.KeepAspectRatio, Qt.FastTransformation)
            animation_label.setPixmap(frm_scaled)
            animation_label.frame_index = (animation_label.frame_index + 1) % len(animation_label.frames)

        timer = QTimer(animation_label)
        timer.timeout.connect(update_frame)
        timer.start(150)
        update_frame()
        animation_label.timer = timer

        item_layout.addWidget(animation_label, alignment=Qt.AlignCenter)
        item.setToolTip("default")

        def on_click(event):
            try:
                self.duck.selected_skin = None
                self.duck.resources.load_default_skin(lazy=False)
                self.duck.update_duck_skin()
                self.duck.apply_settings()
                QMessageBox.information(
                    self,
                    self.translations.get("success", "Success!"),
                    self.translations.get("skin_applied_successfully", "Skin successfully applied: Default")
                )
            except Exception as e:
                logging.error(f"Error applying default skin: {e}")
                QMessageBox.warning(
                    self,
                    self.translations.get("error_title", "Error"),
                    self.translations.get("failed_apply_skin", "Failed to apply skin: Default")
                )

        item.mousePressEvent = on_click
        return item

    def create_skin_item(self, skin_file):
        s = lambda val: int(val * self.scale_factor)

        if skin_file == "Default":
            frames = self.duck.resources.load_skin_frames_for_preview(is_default=True)
            frame_width = self.duck.resources.frame_width
            frame_height = self.duck.resources.frame_height
        else:
            frames = self.duck.resources.load_skin_frames_for_preview(skin_path=skin_file)
            frame_width = self.duck.resources.frame_width
            frame_height = self.duck.resources.frame_height
        if not frames:
            return None

        item = QFrame()
        item.setCursor(Qt.PointingHandCursor)
        item.setStyleSheet("""
            QFrame {
                background:#2f2f2f; border-radius:3px;
            }
            QFrame:hover {
                background:#3a3a3a;
            }
        """)
        item_layout = QVBoxLayout(item)
        item_layout.setContentsMargins(0, 0, 0, 0)

        animation_label = QLabel()
        animation_label.setAlignment(Qt.AlignCenter)
        animation_label.frames = frames
        animation_label.frame_index = 0
        animation_label.setFixedSize(s(128), s(128))

        def update_frame():
            if not animation_label.frames:
                logging.error("No frames available for animation.")
                return
            frm = animation_label.frames[animation_label.frame_index]
            frm_scaled = frm.scaled(
                int(frame_width * (animation_label.width() / frame_width)),
                int(frame_height * (animation_label.height() / frame_height)),
                Qt.KeepAspectRatio,
                Qt.FastTransformation
            )
            animation_label.setPixmap(frm_scaled)
            animation_label.frame_index = (animation_label.frame_index + 1) % len(animation_label.frames)

        timer = QTimer(animation_label)
        timer.timeout.connect(update_frame)
        timer.start(150)
        update_frame()
        animation_label.timer = timer

        skin_name_text = "Default" if skin_file == "Default" else os.path.basename(skin_file)
        item.setToolTip(skin_name_text)
        item_layout.addWidget(animation_label, alignment=Qt.AlignCenter)

        def on_click(event):
            if skin_file == "Default":
                self.duck.resources.load_default_skin()
            else:
                success = self.duck.resources.load_skin(skin_file)
                if success:
                    self.duck.selected_skin = skin_file
                    self.duck.save_settings()
                    self.duck.update_duck_skin()
                    QMessageBox.information(
                        self,
                        self.translations.get("success", "Success!"),
                        self.translations.get("skin_applied_successfully", "Skin successfully applied:") + f" {skin_name_text}"
                    )
                else:
                    QMessageBox.warning(
                        self,
                        self.translations.get("error_title", "Error!"),
                        self.translations.get("failed_apply_skin", "Failed to apply skin:") + f" {skin_name_text}"
                    )
        item.mousePressEvent = on_click
        return item

    def save_appearance_settings(self):
        idx = self.petSize.currentIndex()
        pet_size = self.petSize.itemData(idx)
        self.duck.update_pet_size(pet_size)
        self.duck.apply_settings()
        self.close()

    # Advanced tab in a settings
    def advanced_tab(self):
        s = lambda val: int(val * self.scale_factor)

        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(s(20), s(20), s(20), s(20))
        layout.setSpacing(s(20))

        title_font_size = max(1, int(20 * self.scale_factor))
        title = QLabel(self.translations.get("page_button_advanced","Advanced"))
        title.setStyleSheet(f"font-size:{title_font_size}px;font-weight:bold;color:#fff;border-bottom:1px solid #3a3a3a;padding-bottom:{s(10)}px;")
        layout.addWidget(title)

        # Floor Level
        floor_box = QVBoxLayout()
        lbl_floor = QLabel(self.translations.get("floor_level","Floor level (pixels from bottom):"))
        self.floorLevel = QSpinBox()
        self.floorLevel.setRange(0,10000)
        self.floorLevel.setValue(self.duck.ground_level_setting)
        floor_box.addWidget(lbl_floor)
        floor_box.addWidget(self.floorLevel)
        layout.addLayout(floor_box)

        # Name Offset
        offset_box = QVBoxLayout()
        lbl_offset = QLabel(self.translations.get("name_offset_y","Name Offset Y (pixels):"))
        self.nameOffset = QSpinBox()
        self.nameOffset.setRange(-10000,10000)
        self.nameOffset.setValue(self.duck.name_offset_y)
        offset_box.addWidget(lbl_offset)
        offset_box.addWidget(self.nameOffset)
        layout.addLayout(offset_box)

        # Base Font Size
        font_box = QVBoxLayout()
        lbl_font = QLabel(self.translations.get("font_base_size","Base font size:"))
        self.fontBaseSize = QSpinBox()
        self.fontBaseSize.setRange(6,200)
        base_fs = getattr(self.duck,'font_base_size',14)
        self.fontBaseSize.setValue(base_fs)
        font_box.addWidget(lbl_font)
        font_box.addWidget(self.fontBaseSize)
        layout.addLayout(font_box)

        # Language
        lang_box = QVBoxLayout()
        lbl_lang = QLabel(self.translations.get("language_selection","Language:"))
        self.language = QComboBox()
        langs = {'en':'English','ru':'Русский'}
        for code,name in langs.items():
            self.language.addItem(name,code)
        idx = self.language.findData(self.duck.current_language)
        if idx>=0:
            self.language.setCurrentIndex(idx)
        lang_box.addWidget(lbl_lang)
        lang_box.addWidget(self.language)
        layout.addLayout(lang_box)

        # Autostart
        auto_box = QHBoxLayout()
        self.autostart = QCheckBox(self.translations.get("run_at_system_startup","Run at system startup"))
        self.autostart.setChecked(self.duck.autostart_enabled)
        auto_box.addWidget(self.autostart)
        auto_box.addStretch()
        layout.addLayout(auto_box)

        reset_btn = QPushButton(self.translations.get("reset_to_default_button","Reset all settings"))
        reset_btn.setStyleSheet("background:#a00;color:#fff;")
        reset_btn.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        reset_btn.clicked.connect(self.reset_settings_clicked)
        layout.addWidget(reset_btn)

        layout.addStretch()

        act_box = QHBoxLayout()
        act_box.addStretch()
        cancel_btn = QPushButton(self.translations.get("cancel_button","Cancel"))
        cancel_btn.clicked.connect(self.close)
        cancel_btn.setObjectName("cancelButton")
        cancel_btn.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        save_btn = QPushButton(self.translations.get("save_button","Save"))
        save_btn.clicked.connect(self.save_advanced_settings)
        save_btn.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        act_box.addWidget(cancel_btn)
        act_box.addWidget(save_btn)
        layout.addLayout(act_box)

        return w

    def reset_settings_clicked(self):
        reply = QMessageBox.question(
            self,
            self.translations.get("reset_to_default_title","Reset settings"),
            self.translations.get("reset_to_default_conformation","Are you sure you want to reset all settings?"),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.duck.reset_settings()
            self.duck.selected_skin = None
            self.duck.update_duck_skin()
            self.duck.apply_settings()
            self.close()

    def save_advanced_settings(self):
        floor_level = self.floorLevel.value()
        name_offset = self.nameOffset.value()
        font_base_size = self.fontBaseSize.value()
        lang_code = self.language.itemData(self.language.currentIndex())
        autostart_enabled = self.autostart.isChecked()

        self.duck.update_ground_level(floor_level)
        self.duck.name_offset_y = name_offset
        self.duck.font_base_size = font_base_size
        self.duck.current_language = lang_code
        self.duck.autostart_enabled = autostart_enabled

        if autostart_enabled:
            self.duck.enable_autostart()
        else:
            self.duck.disable_autostart()

        self.duck.apply_settings()
        self.close()

    # About tab in a settings
    def about_tab(self):
        s = lambda val: int(val * self.scale_factor)

        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(s(20), s(20), s(20), s(20))
        layout.setSpacing(s(20))

        title_font_size = max(1, int(20 * self.scale_factor))
        title = QLabel(self.translations.get("page_button_about","About"))
        title.setStyleSheet(f"font-size:{title_font_size}px;font-weight:bold;color:#fff;border-bottom:1px solid #3a3a3a;padding-bottom:{s(10)}px;")
        layout.addWidget(title)

        info_label = QLabel(f"""
            <style>
                a {{
                    color: {self.accent_color};
                    text-decoration: none;
                }}
                a:hover {{
                    text-decoration: underline;
                }}
            </style>
            <h2>QuackDuck</h2>
            <p>Developed with 💜 by zl0yxp</p>
            <p>Discord: zl0yxp</p>
            <p>Telegram: <a href="https://t.me/quackduckapp">t.me/quackduckapp</a></p>
            <p>GitHub: <a href="https://github.com/KristopherZlo/quackduck">KristopherZlo/quackduck</a></p>
        """)
        info_label.setWordWrap(True)
        info_label.setOpenExternalLinks(True)
        info_label.setAlignment(Qt.AlignLeft)
        layout.addWidget(info_label)

        support_buttons_layout = QHBoxLayout()
        support_button = QPushButton(self.translations.get("buy_me_a_coffee_button_settings_window","Buy me a coffee ☕"))
        support_button.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        telegram_button = QPushButton("Telegram")
        telegram_button.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        github_button = QPushButton("GitHub")
        github_button.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        support_button.setStyleSheet("background:#444;")
        telegram_button.setStyleSheet("background:#444;")
        github_button.setStyleSheet("background:#444;")
        support_buttons_layout.addWidget(support_button)
        support_buttons_layout.addWidget(telegram_button)
        support_buttons_layout.addWidget(github_button)

        support_button.clicked.connect(lambda: self.open_link("https://buymeacoffee.com/zl0yxp"))
        telegram_button.clicked.connect(lambda: self.open_link("https://t.me/quackduckapp"))
        github_button.clicked.connect(lambda: self.open_link("https://github.com/KristopherZlo/quackduck"))

        layout.addLayout(support_buttons_layout)

        layout.addStretch()
        act_box = QHBoxLayout()
        act_box.addStretch()
        cancel_btn = QPushButton(self.translations.get("cancel_button","Cancel"))
        cancel_btn.setObjectName("cancelButton")
        cancel_btn.clicked.connect(self.close)
        cancel_btn.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        act_box.addWidget(cancel_btn)
        layout.addLayout(act_box)

        return w

    def open_link(self, url):
        QDesktopServices.openUrl(QUrl(url))

    def update_mic_preview(self):
        if hasattr(self.duck,'current_volume'):
            self.mic_level_preview.setValue(int(self.duck.current_volume))

def main():
    app = QtWidgets.QApplication(sys.argv)

    icon_path = resource_path("assets/images/white-quackduck-visible.ico")
    if os.path.exists(icon_path):
        app.setWindowIcon(QtGui.QIcon(icon_path))
    else:
        logging.error(f"File icons not found: {icon_path}")

    app.setQuitOnLastWindowClosed(False)
    sys.excepthook = exception_handler

    duck = Duck()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()