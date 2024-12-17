# TODO
# AUTO UPDATE TEST
# done Translations of a new buttons
# maybe done Fix settings icon

# IHateThisIdeaCounter = 291

import sys
import subprocess
import os
import random
import json
import zipfile
import tempfile
import webbrowser
import hashlib
import time
import traceback
import platform
import shutil
import logging
import requests

from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Tuple

from PyQt5 import QtWidgets, QtGui, QtCore, QtMultimedia
from PyQt5.QtMultimedia import QSoundEffect
from PyQt5.QtWidgets import (
    QApplication, QDialog, QHBoxLayout, QVBoxLayout, QWidget,
    QListWidget, QLabel, QPushButton, QStackedWidget, QLineEdit,
    QComboBox, QSlider, QProgressBar, QCheckBox,
    QSizePolicy, QSpinBox, QScrollArea, QGridLayout,
    QMessageBox, QFileDialog
)
from PyQt5.QtCore import Qt, QPoint, QTimer
from PyQt5.QtGui import QFont, QIcon, QPixmap, QColor, QMouseEvent

if sys.platform == 'win32':
    import winreg

import numpy as np
import sounddevice as sd

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

APP_NAME = 'QuackDuck'
APP_EXECUTABLE = 'quackduck.exe'  # or another file name on the corresponding platform

CURRENT_DIR = 'current'   # Directory with the currently installed version
BACKUP_DIR = 'backup'     # Directory for backup

os.makedirs(CURRENT_DIR, exist_ok=True)
os.makedirs(BACKUP_DIR, exist_ok=True)

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

def check_for_updates_github():
    try:
        response = requests.get('https://api.github.com/repos/KristopherZlo/quackduck/releases/latest')
        if response.status_code == 200:
            latest_release = response.json()
            latest_version = latest_release['tag_name'].lstrip('v')
            logging.info(f"✨ LATEST VERSION: {latest_version}")
            logging.info(f"🔧 CURRENT VERSION: {PROJECT_VERSION}")
            if latest_version > PROJECT_VERSION:
                return latest_release
        else:
            logging.error(f"❌ Failed to fetch latest release info. Status code: {response.status_code}")
    except Exception as e:
        logging.error(f"⚠️ Error checking for updates: {e}")
    return None

def notify_user_about_update(duck, latest_release, manual_trigger=False):
    """
    Show an update dialog with three buttons: Yes, No, Skip version.
    - If the user chooses Skip version, remember this version and do not prompt again automatically.
    - If the user chooses No, just close the dialog.
    - If the user chooses Yes, proceed to the update.
    manual_trigger = True if the user manually clicked 'Check for updates'.

    Modification:
    - If the version was previously skipped but the check is manual, ignore the skipped state and still show the dialog.
    """

    latest_version = latest_release['tag_name'].lstrip('v')
    release_notes = latest_release.get('body', '')

    # If the version was previously skipped and this is an automatic check, do not prompt again.
    # If this is a manual check, ignore the skipped state and show the dialog again.
    if duck.skipped_version == latest_version and not manual_trigger:
        # Automatically checked updates, version previously skipped: do nothing.
        return

    msg = QMessageBox(duck)
    msg.setWindowTitle(translations.get("update_available", "Update available"))

    # Use .format() to insert variables into translation strings.
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
        # User chose to install the update.
        download_and_install_update(duck, latest_release)
    elif clicked_button == skip_button:
        # User chose to skip this version.
        duck.set_skipped_version(latest_version)
        if manual_trigger:
            # If the user manually checked for updates and decided to skip, inform them.
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
    # If clicked_button == no_button, do nothing.

def download_and_install_update(duck, latest_release):
    assets = latest_release.get('assets', [])
    if not assets:
        QMessageBox.warning(
            duck, 
            translations.get("update_error_title", "Update Error"), 
            translations.get("no_files_for_update", "No files available for update.")
        )
        return

    # Assumed that the release contains one ZIP with the update
    asset = assets[0]
    download_url = asset['browser_download_url']
    file_name = asset['name']

    temp_dir = tempfile.mkdtemp()
    temp_zip_path = os.path.join(temp_dir, file_name)

    try:
        # Download ZIP
        with requests.get(download_url, stream=True) as r:
            r.raise_for_status()
            with open(temp_zip_path, 'wb') as f:
                shutil.copyfileobj(r.raw, f)

        # Backupcurrent version before upgrading
        backup_current_version()

        # Unpack ZIP
        extract_dir = os.path.join(temp_dir, "extracted")
        os.makedirs(extract_dir, exist_ok=True)
        with zipfile.ZipFile(temp_zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)

        # Copy files from the unpacked archive to CURRENT_DIR
        update_success = install_new_version(extract_dir)
        if update_success:
            QMessageBox.information(
                duck,
                translations.get("update_success", "Successfully updated"),
                translations.get("update_success_app_will_be_restarted", "The update has been installed successfully. The application will be restarted.")
            )
            restart_application(duck)
        else:
            # If failed to install, roll back
            QMessageBox.critical(
                duck, 
                translations.get("update_error_title", "Update Error"), 
                translations.get("update_failed_rollback", "Failed to install the update. Rolling back to the previous version.")
            )
            restore_backup_version()
    except Exception as e:
        logging.error(f"Error updating: {e}")
        message = translations.get("update_failed_message", f"Failed to update: {e}\nRolling back to the previous version.")
        message = message.format(e=e)
        QMessageBox.critical(
            duck, 
            translations.get("update_error_title", "Update Error"), 
            message
        )
        restore_backup_version()
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

def backup_current_version():
    # Clearing the backup directory
    for f in os.listdir(BACKUP_DIR):
        p = os.path.join(BACKUP_DIR, f)
        if os.path.isfile(p) or os.path.islink(p):
            os.unlink(p)
        elif os.path.isdir(p):
            shutil.rmtree(p)

    # Copy everything from current to backup
    for item in os.listdir(CURRENT_DIR):
        s = os.path.join(CURRENT_DIR, item)
        d = os.path.join(BACKUP_DIR, item)
        if os.path.isdir(s):
            shutil.copytree(s, d, dirs_exist_ok=True)
        else:
            shutil.copy2(s, d)

def restore_backup_version():
    # Clear current
    for f in os.listdir(CURRENT_DIR):
        p = os.path.join(CURRENT_DIR, f)
        if os.path.isfile(p) or os.path.islink(p):
            os.unlink(p)
        elif os.path.isdir(p):
            shutil.rmtree(p)

    # Copy everything from backup back to current
    for item in os.listdir(BACKUP_DIR):
        s = os.path.join(BACKUP_DIR, item)
        d = os.path.join(CURRENT_DIR, item)
        if os.path.isdir(s):
            shutil.copytree(s, d, dirs_exist_ok=True)
        else:
            shutil.copy2(s, d)

def install_new_version(extract_dir):
    try:
        # Clear current before copying the new version
        for f in os.listdir(CURRENT_DIR):
            p = os.path.join(CURRENT_DIR, f)
            if os.path.isfile(p) or os.path.islink(p):
                os.unlink(p)
            elif os.path.isdir(p):
                shutil.rmtree(p)

        # Copy files from extract_dir to CURRENT_DIR
        for item in os.listdir(extract_dir):
            s = os.path.join(extract_dir, item)
            d = os.path.join(CURRENT_DIR, item)
            if os.path.isdir(s):
                shutil.copytree(s, d, dirs_exist_ok=True)
            else:
                shutil.copy2(s, d)
        return True
    except Exception as e:
        logging.error(f"Error installing new version: {e}")
        return False

def restart_application(duck):
    # APP_EXECUTABLE is assumed to be in current/
    exe_path = os.path.join(CURRENT_DIR, APP_EXECUTABLE)
    try:
        subprocess.Popen([exe_path])  # Launching a new version
        duck.close()  # Close the current application
    except Exception as e:
        logging.error(f"Error restarting application: {e}")
        message = translations.get("restart_failed", f"Failed to restart the application: {e}")
        message = message.format(e=e)
        QMessageBox.critical(
            duck, 
            translations.get("restart_error_title", "Error"), 
            message
        )
        # In case of a restart error, you can roll back, but this is optional

def get_system_accent_color():
    """
    Gets the system accent color.
    For Windows, reads the value from the registry.
    For other OSs, returns a predefined color.
    """
    if sys.platform == 'win32':
        try:
            registry = winreg.ConnectRegistry(None, winreg.HKEY_CURRENT_USER)
            key = winreg.OpenKey(registry, r'SOFTWARE\Microsoft\Windows\DWM', 0, winreg.KEY_READ)
            accent_color, regtype = winreg.QueryValueEx(key, 'AccentColor')
            winreg.CloseKey(key)
            # AccentColor stored as an ARGB (DWORD)
            a = (accent_color >> 24) & 0xFF
            r = (accent_color >> 16) & 0xFF
            g = (accent_color >> 8) & 0xFF
            b = accent_color & 0xFF
            return QColor(r, g, b, a)
        except Exception as e:
            logging.error(f"Failed to get system accent color: {e}")
            # Return the color by default if it was not possible to get from the dregistry
            return QColor('#05B8CC')
    else:
        # For MacOS, Linux and other OS, we return the default color
        return QColor('#05B8CC')

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

class SettingsManager:
    def __init__(self, organization: str = 'zl0yxp', application: str = 'QuackDuck') -> None:
        self._settings = QtCore.QSettings(organization, application)

    def get_value(self, key: str, default=None, value_type=None):
        return self._settings.value(key, defaultValue=default, type=value_type)

    def set_value(self, key: str, value) -> None:
        self._settings.setValue(key, value)

    def clear(self) -> None:
        self._settings.clear()

    def sync(self) -> None:
        self._settings.sync()

class DebugWindow(QtWidgets.QWidget):
    def __init__(self, duck):
        super().__init__()
        self.duck = duck
        self.setWindowTitle("QuackDuck Debug Mode")
        self.setGeometry(100, 100, 600, 400)
        self.init_ui()
    
    def init_ui(self):
        layout = QtWidgets.QVBoxLayout()

        # Section to Trigger States
        state_group = QtWidgets.QGroupBox("Trigger States")
        state_layout = QtWidgets.QHBoxLayout()

        btn_playful = QtWidgets.QPushButton("Playful")
        btn_playful.clicked.connect(lambda: self.duck.change_state(PlayfulState(self.duck)))

        btn_sleep = QtWidgets.QPushButton("Sleep")
        btn_sleep.clicked.connect(lambda: self.duck.change_state(SleepingState(self.duck)))

        btn_jump = QtWidgets.QPushButton("Jump")
        btn_jump.clicked.connect(lambda: self.duck.change_state(JumpingState(self.duck)))

        btn_idle = QtWidgets.QPushButton("Idle")
        btn_idle.clicked.connect(lambda: self.duck.change_state(IdleState(self.duck)))

        btn_walk = QtWidgets.QPushButton("Walk")
        btn_walk.clicked.connect(lambda: self.duck.change_state(WalkingState(self.duck)))

        btn_run = QtWidgets.QPushButton("Run")
        btn_run.clicked.connect(lambda: self.duck.change_state(RunState(self.duck)))

        btn_attack = QtWidgets.QPushButton("Attack")
        btn_attack.clicked.connect(lambda: self.duck.change_state(AttackState(self.duck)))

        state_layout.addWidget(btn_playful)
        state_layout.addWidget(btn_sleep)
        state_layout.addWidget(btn_jump)
        state_layout.addWidget(btn_idle)
        state_layout.addWidget(btn_walk)
        state_layout.addWidget(btn_run)
        state_layout.addWidget(btn_attack)

        state_group.setLayout(state_layout)
        layout.addWidget(state_group)

        # Section to Play Sounds
        sound_group = QtWidgets.QGroupBox("Sound Controls")
        sound_layout = QtWidgets.QHBoxLayout()

        btn_play_sound = QtWidgets.QPushButton("Play Random Sound")
        btn_play_sound.clicked.connect(self.duck.play_random_sound)

        sound_layout.addWidget(btn_play_sound)
        sound_group.setLayout(sound_layout)
        layout.addWidget(sound_group)

        # Section to Edit Parameters
        params_group = QtWidgets.QGroupBox("Edit Parameters")
        params_layout = QtWidgets.QFormLayout()

        # Section for displaying the remaining time
        remaining_group = QtWidgets.QGroupBox("Time remaining until next event")
        remaining_layout = QtWidgets.QFormLayout()

        self.sleep_remaining_label = QtWidgets.QLabel()
        self.sound_remaining_label = QtWidgets.QLabel()
        self.idle_remaining_label = QtWidgets.QLabel()

        remaining_layout.addRow("Until Sleep:", self.sleep_remaining_label)
        remaining_layout.addRow("Until PlaySound:", self.sound_remaining_label)
        remaining_layout.addRow("Until end of Idle:", self.idle_remaining_label)

        remaining_group.setLayout(remaining_layout)
        layout.addWidget(remaining_group)

        # Idle Duration
        self.idle_duration_spin = QtWidgets.QDoubleSpinBox()
        self.idle_duration_spin.setRange(1.0, 60.0)
        self.idle_duration_spin.setValue(self.duck.idle_duration)
        self.idle_duration_spin.setSuffix(" sec")
        self.idle_duration_spin.valueChanged.connect(self.update_idle_duration)

        # Timer to update the rest of the time
        self.update_timer = QtCore.QTimer()
        self.update_timer.timeout.connect(self.update_remaining_times)
        self.update_timer.start(1000)  # Update every second

        params_layout.addRow("Idle duration:", self.idle_duration_spin)

        # Sleep Timeout
        self.sleep_timeout_spin = QtWidgets.QSpinBox()
        self.sleep_timeout_spin.setRange(60, 1800)  # From 1 min to 30 min
        self.sleep_timeout_spin.setValue(int(self.duck.sleep_timeout))
        self.sleep_timeout_spin.setSuffix(" sec")
        self.sleep_timeout_spin.valueChanged.connect(self.update_sleep_timeout)

        # Direction Change Interval
        self.direction_interval_spin = QtWidgets.QSpinBox()
        self.direction_interval_spin.setRange(1, 60)  # 1 sec to 60 sec
        self.direction_interval_spin.setValue(getattr(self.duck, 'direction_change_interval', 20))
        self.direction_interval_spin.setSuffix(" sec")
        self.direction_interval_spin.valueChanged.connect(self.update_direction_interval)

        # Activation Threshold
        self.activation_threshold_spin = QtWidgets.QSpinBox()
        self.activation_threshold_spin.setRange(1, 100)
        self.activation_threshold_spin.setValue(self.duck.activation_threshold)
        self.activation_threshold_spin.setSuffix(" %")
        self.activation_threshold_spin.valueChanged.connect(self.update_activation_threshold)

        params_layout.addRow("Sleep Timeout:", self.sleep_timeout_spin)
        params_layout.addRow("Direction Change Interval:", self.direction_interval_spin)
        params_layout.addRow("Activation Threshold:", self.activation_threshold_spin)
        params_group.setLayout(params_layout)
        layout.addWidget(params_group)

        btn_reset = QtWidgets.QPushButton("Reset Parameters")
        btn_reset.clicked.connect(self.reset_parameters)
        layout.addWidget(btn_reset)

        states_info_group = QtWidgets.QGroupBox("States Info")
        states_info_layout = QtWidgets.QVBoxLayout()

        states_info_label = QtWidgets.QLabel()
        states_info = [
            "IdleState: The duck stands still, periodically changing animations.",
            "WalkingState: The duck walks across the screen.",
            "SleepingState: The duck sleeps without moving.",
            "JumpingState: The duck makes a jump.",
            "FallingState: The duck falls down.",
            "DraggingState: The duck is dragged with the mouse.",
            "ListeningState: The duck listens to the microphone input.",
            "PlayfulState: The duck is playful and runs after the cursor faster.",
            "RunState: The duck runs quickly (if the running animation is available).",
            "AttackState: The duck makes a one-time attack, freezing in place.",
            "LandingState: The duck lands after falling."
        ]
        states_info_label.setText("\n".join(states_info))
        states_info_label.setWordWrap(True)
        states_info_layout.addWidget(states_info_label)
        states_info_group.setLayout(states_info_layout)
        layout.addWidget(states_info_group)

        self.setLayout(layout)

    def update_remaining_times(self):
        # The remaining time to Sleep
        elapsed_since_interaction = time.time() - self.duck.last_interaction_time
        time_until_sleep = self.duck.sleep_timeout - elapsed_since_interaction
        if time_until_sleep < 0:
            time_until_sleep = 0
        self.sleep_remaining_label.setText(f"{int(time_until_sleep)} sec")

        # The remaining time to PlaySound
        if self.duck.sound_timer.isActive():
            time_remaining_sound = self.duck.sound_timer.remainingTime() / 1000.0
            self.sound_remaining_label.setText(f"{int(time_remaining_sound)} sec")
        else:
            self.sound_remaining_label.setText("N/A")

        # The remaining time until the end of IDLE
        if isinstance(self.duck.state, IdleState):
            elapsed_in_idle = time.time() - self.duck.state.start_time
            time_until_idle_end = self.duck.idle_duration - elapsed_in_idle
            if time_until_idle_end < 0:
                time_until_idle_end = 0
            self.idle_remaining_label.setText(f"{int(time_until_idle_end)} sec")
        else:
            self.idle_remaining_label.setText("N/A")

    def update_idle_duration(self, value):
        self.duck.idle_duration = value
        self.duck.settings_manager.set_value('idle_duration', self.duck.idle_duration)
        logging.info(f"Idle duration updated to {value} seconds.")

    def update_sleep_timeout(self, value):
        self.duck.sleep_timeout = value
        self.duck.settings_manager.set_value('sleep_timeout', self.duck.sleep_timeout)
        logging.info(f"Sleep timeout updated to {value} seconds.")

    def update_direction_interval(self, value):
        self.duck.direction_change_interval = value
        self.duck.settings_manager.set_value('direction_change_interval', self.duck.direction_change_interval)
        logging.info(f"Direction change interval updated to {value} seconds.")

        # Restart the timer with a new interval
        self.duck.direction_change_timer.stop()
        self.duck.direction_change_timer.start(self.duck.direction_change_interval * 1000)

    def update_activation_threshold(self, value):
        self.duck.activation_threshold = value
        self.duck.settings_manager.set_value('activation_threshold', self.duck.activation_threshold)
        logging.info(f"Activation threshold updated to {value}%.")

    def reset_parameters(self):
        # Reset parameters to default values
        default_sleep_timeout = 300  # 5 minutes
        default_direction_interval = 20  # 20 seconds
        default_activation_threshold = 1  # 1%

        self.sleep_timeout_spin.setValue(default_sleep_timeout)
        self.direction_interval_spin.setValue(default_direction_interval)
        self.activation_threshold_spin.setValue(default_activation_threshold)

        # Reset the Duck's parameters
        self.duck.sleep_timeout = default_sleep_timeout
        self.duck.direction_change_interval = default_direction_interval
        self.duck.activation_threshold = default_activation_threshold

        # Update settings
        self.duck.settings_manager.set_value('sleep_timeout', self.duck.sleep_timeout)
        self.duck.settings_manager.set_value('direction_change_interval', self.duck.direction_change_interval)
        self.duck.settings_manager.set_value('activation_threshold', self.duck.activation_threshold)

        logging.info("Parameters reset to default values.")

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

        offset_y = self.duck.name_offset_y
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

        # CHANGED: If returning to PlayfulState, jump higher (1.5x)
        if isinstance(self.return_state, PlayfulState):
            self.vertical_speed = -15 * 1.5  # 1.5 times higher jump

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
    def __init__(self, scale_factor: float, pet_size: int = 3) -> None:
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

    # def restart_stream(self):
    #     if self.stream is not None:
    #         self.stream.stop_stream()
    #         self.stream.close()
    #     try:
    #         self.stream = self.audio.open(format=pyaudio.paInt16,
    #                                       channels=1,
    #                                       rate=self.rate,
    #                                       input=True,
    #                                       frames_per_buffer=self.chunk,
    #                                       input_device_index=self.device_index)
    #     except Exception as e:
    #         print(f"Error reopening audio stream: {e}")
    #         self.running = False

class Duck(QtWidgets.QWidget):
    """
    The main class representing the duck pet.
    Handles states, animations, and interactions.
    """
    def __init__(self):
        super().__init__()
        self.settings_manager = SettingsManager()
        self.setWindowFlags(self.windowFlags() | QtCore.Qt.Window)
        self.load_settings()

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
        self.name_offset_y = self.settings_manager.get_value('name_offset_y', default=0, value_type=int)
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

        self.debug_window = DebugWindow(self)

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

        # Timer to check cursor attack every 5 seconds, regardless of state
        self.attack_timer = QtCore.QTimer()
        self.attack_timer.timeout.connect(self.check_attack_trigger)
        self.attack_timer.start(5000)

        self.run_timer = QtCore.QTimer()
        self.run_timer.timeout.connect(self.check_run_state_trigger)
        self.run_timer.start(5 * 60 * 1000)

        latest_release = check_for_updates_github()
        if latest_release:
            # False means this is not a manual call but an auto-check
            notify_user_about_update(self, latest_release, manual_trigger=False)

    def check_for_updates(self):
        """
        Automatically check for updates and notify if available.
        This can be called internally. Just do what we did in constructor.
        """
        latest_release = check_for_updates_github()
        if latest_release:
            notify_user_about_update(self, latest_release, manual_trigger=False)
        else:
            # If no updates, do nothing special automatically.
            pass

    def check_for_updates_manual(self):
        """
        Called when user clicks 'Check for updates' in the tray menu.
        Show user a message if no new updates or the same skipped version.
        """
        latest_release = check_for_updates_github()
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
        Set the skipped version so that we do not prompt the user again
        for this particular version. 
        """
        self.skipped_version = version
        self.settings_manager.set_value('skipped_version', version)
        self.settings_manager.sync()

    def get_scale_factor(self):
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
        if random.random() < self.playful_behavior_probability:
            if not isinstance(self.state, (FallingState, DraggingState, ListeningState, JumpingState, PlayfulState)):
                self.stop_current_state()
                self.change_state(PlayfulState(self))

    def show_debug_window(self):
        """Displays the Debug Window."""
        self.debug_window.show()
        self.debug_window.raise_()
        self.debug_window.activateWindow()

    def play_random_sound(self):
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
        seed = get_seed_from_name(name)
        random_gen = random.Random(seed)
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
        self.movement_speed = self.random_gen.uniform(0.8, 1.5)
        self.base_duck_speed = self.movement_speed
        self.sound_interval_min = 60 + self.random_gen.random() * (300 - 60)
        self.sound_interval_max = 301 + self.random_gen.random() * (900 - 301)
        if self.sound_interval_min >= self.sound_interval_max:
            self.sound_interval_min, self.sound_interval_max = self.sound_interval_max, self.sound_interval_min
        self.sound_response_probability = 0.01 + self.random_gen.random() * (0.25 - 0.01)
        self.playful_behavior_probability = 0.1 + self.random_gen.random() * (0.5 - 0.1)
        self.sleep_timeout = (5 + self.random_gen.random() * 10) * 60  # 5 to 15 minutes

    def set_default_characteristics(self):
        self.movement_speed = 1.25
        self.base_duck_speed = self.movement_speed
        self.sound_interval_min = 120  # Minimum interval in seconds
        self.sound_interval_max = 600  # Maximum interval in seconds
        self.sound_response_probability = 0.01
        self.playful_behavior_probability = 0.1
        self.sleep_timeout = 300

    def mouseDoubleClickEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self.create_heart()

    def create_heart(self):
        heart_x = self.duck_x + self.current_frame.width() / 2
        heart_y = self.duck_y
        self.heart_window = HeartWindow(heart_x, heart_y)

    def init_ui(self):
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
        self.direction_change_timer.start(self.direction_change_interval * 1000)

        self.playful_timer = QtCore.QTimer()
        self.playful_timer.timeout.connect(self.check_playful_state)
        self.playful_timer.start(10 * 60 * 1000)

    def setup_random_behavior(self):
        self.random_behavior_timer = QtCore.QTimer()
        self.random_behavior_timer.timeout.connect(self.perform_random_behavior)
        self.schedule_next_random_behavior()

    def schedule_next_random_behavior(self):
        interval = random.randint(20000, 40000)
        self.random_behavior_timer.start(interval)

    def perform_random_behavior(self):
        behaviors = [self.enter_random_idle_state, self.change_direction]
        behavior = random.choice(behaviors)
        behavior()
        self.schedule_next_random_behavior()

    def check_run_state_trigger(self):
        # If there is a running animation, then once every 5 minutes with a chance of 1% to 5% we enter RunState
        running_frames = self.resources.get_animation_frames_by_name('running')
        if running_frames:
            chance = self.random_gen.uniform(0.01, 0.05)
            if random.random() < chance:
                if not isinstance(self.state, (FallingState, DraggingState, ListeningState, JumpingState, PlayfulState, RunState, AttackState)):
                    self.change_state(RunState(self))

    def can_attack(self):
        # Attack is only allowed if current state is either WalkingState or IdleState
        if not isinstance(self.state, (WalkingState, IdleState)):
            return False
        
        # If there is an attack animation in the config
        attack_frames = self.resources.get_animation_frames_by_name('attack')
        if attack_frames:
            cursor_pos = QtGui.QCursor.pos()
            duck_pos = self.pos()
            duck_center = duck_pos + self.rect().center()

            # Base attack range, scaled relative to pet_size
            base_attack_distance = 50
            attack_distance = base_attack_distance * (self.pet_size / 3)

            dist = ((cursor_pos.x() - duck_center.x())**2 + (cursor_pos.y() - duck_center.y())**2)**0.5

            if dist < attack_distance:
                chance = self.random_gen.uniform(0.01, 0.2)
                if random.random() < chance:
                    # Determine the attack side
                    if cursor_pos.x() < duck_center.x():
                        self.facing_right = False
                    else:
                        self.facing_right = True
                    return True
        return False

    def check_attack_trigger(self):
        # Don't attack if the duck is in FallingState, JumpingState or AttackState
        if not isinstance(self.state, (FallingState, JumpingState, AttackState)):
            if self.can_attack():
                self.change_state(AttackState(self))

    def enter_random_idle_state(self):
        if not isinstance(self.state, IdleState) and not isinstance(self.state, (FallingState, DraggingState)):
            self.change_state(IdleState(self))

    def change_direction(self):
        self.direction *= -1
        self.facing_right = self.direction == 1

    def change_state(self, new_state, event=None):
        allowed_wake_states = (DraggingState, PlayfulState, ListeningState, JumpingState, WalkingState)

        # Prevent transition to RunState or AttackState if the duck is in the air
        if isinstance(new_state, (RunState, AttackState)) and isinstance(self.state, (FallingState, JumpingState)):
            logging.info(f"Cannot transition to {new_state.__class__.__name__} while in mid-air.")
            return

        if isinstance(new_state, ListeningState) and isinstance(self.state, PlayfulState):
            logging.info("Transition to ListeningState is rejected because the duck is in PlayfulState.")
            return

        if isinstance(self.state, SleepingState):
            if isinstance(new_state, allowed_wake_states):
                logging.info(f"Transition from SleepingState to {new_state.__class__.__name__}")
                self.state.exit()
                self.state = new_state
                self.state.enter()
                if event:
                    self.state.handle_mouse_press(event)
            else:
                logging.info(f"Remaining in SleepingState, attempt to move to {new_state.__class__.__name__} rejected")
                return
        else:
            if self.state:
                logging.info(f"Transition from {self.state.__class__.__name__} to {new_state.__class__.__name__}")
                self.state.exit()
            else:
                logging.info(f"Transition to {new_state.__class__.__name__}")
            self.state = new_state
            self.state.enter()
            if event:
                self.state.handle_mouse_press(event)

        if isinstance(self.state, (IdleState, WalkingState)):
            self.start_cursor_shake_detection()
            logging.info("Starting cursor shake detection.")
        else:
            self.stop_cursor_shake_detection()
            logging.info("Stopping cursor shake detection.")

        # Determine whether to enable cursor shake tracking
        if isinstance(self.state, (IdleState, WalkingState)):
            self.start_cursor_shake_detection()
            logging.info("Starting cursor shake detection.")
        else:
            self.stop_cursor_shake_detection()
            logging.info("Stopping cursor shake detection.")

    def start_cursor_shake_detection(self):
        self.cursor_positions = []
        self.cursor_shake_timer.start(50)  # Check every 50 ms

    def stop_cursor_shake_detection(self):
        self.cursor_shake_timer.stop()
        self.cursor_positions = []

    def check_cursor_shake(self):
        # Checking the cursor shaking. The attack has been removed from here, now it is on the timer check_attack_trigger()
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
                    # We just enter PlayfulState, without attack (attack by timer separately)
                    self.change_state(PlayfulState(self))
        else:
            self.cursor_positions = []

    def update_animation(self):
        self.state.update_animation()

    def update_position(self):
        self.state.update_position()
        if self.name_window and self.show_name and self.pet_name.strip():
            self.name_window.update_position()

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        if self.current_frame:
            painter.drawPixmap(0, 0, self.current_frame)
        painter.end()

    def mousePressEvent(self, event):
        self.last_interaction_time = time.time()
        self.state.handle_mouse_press(event)

    def mouseReleaseEvent(self, event):
        self.state.handle_mouse_release(event)

    def mouseMoveEvent(self, event):
        self.state.handle_mouse_move(event)

    def get_ground_level(self):
        screen_rect = QtWidgets.QApplication.desktop().screenGeometry()
        ground_offset = self.ground_level_setting
        return screen_rect.height() - ground_offset

    def update_ground_level(self, new_ground_level):
        self.ground_level_setting = new_ground_level
        self.settings_manager.set_value('ground_level', new_ground_level)
        self.ground_level = self.get_ground_level()

        if self.duck_y + self.duck_height > self.ground_level:
            self.duck_y = self.ground_level - self.duck_height
            self.move(int(self.duck_x), int(self.duck_y))
        elif self.duck_y + self.duck_height < self.ground_level:
            self.change_state(FallingState(self))

    def check_sleep(self):
        elapsed = time.time() - self.last_interaction_time
        if elapsed >= self.sleep_timeout:
            if not isinstance(self.state, SleepingState):
                if not isinstance(self.state, (FallingState, DraggingState, ListeningState, JumpingState, PlayfulState)):
                    self.stop_current_state()
                    self.change_state(SleepingState(self))

    def on_volume_updated(self, volume):
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
                    logging.debug("The ListeningState entry timer has been started for 100ms.")
                else:
                    logging.info("The duck is in PlayfulState. No entry into ListeningState.")
        else:
            if self.listening_entry_timer:
                self.listening_entry_timer.stop()
                self.listening_entry_timer = None
                logging.debug("The ListeningState entry timer has stopped.")

            if self.is_listening and not self.listening_exit_timer:
                self.listening_exit_timer = QtCore.QTimer()
                self.listening_exit_timer.setSingleShot(True)
                self.listening_exit_timer.timeout.connect(self.exit_listening_state)
                self.listening_exit_timer.start(1000)  # 1 second (1000 ms) exit delay from a listening state
                logging.debug("The ListeningState exit timer has been started for 1 second.")

    def stop_current_state(self):
        if self.state:
            self.state.exit()
            self.state = None

    def enter_listening_state(self):
        logging.info("Entering ListeningState.")
        self.listening_entry_timer = None
        if not self.is_listening:
            if isinstance(self.state, (JumpingState, FallingState, DraggingState)):
                logging.info("Entry to ListeningState was rejected from the current state.")
                return
            self.stop_current_state()
            self.change_state(ListeningState(self))
            self.is_listening = True
            logging.info("The duck is in ListeningState.")

    def exit_listening_state(self):
        logging.info("Exiting ListeningState.")
        self.listening_exit_timer = None
        if self.is_listening:
            self.is_listening = False
            self.change_state(WalkingState(self))
            logging.info("The duck entered the WalkingState after leaving the ListeningState.")

    def schedule_next_sound(self):
        interval = random.randint(120000, 600000)
        self.sound_timer.start(interval)

    def open_settings(self):
        if hasattr(self, 'settings_window') and self.settings_manager_window.isVisible():
            self.settings_manager_window.raise_()
            self.settings_manager_window.activateWindow()
        else:
            self.settings_manager_window = SettingsWindow(self, self.scale_factor)
            self.settings_manager_window.show()

    def unstuck_duck(self):
        self.duck_x = (self.screen_width - self.duck_width) // 2
        self.duck_y = self.ground_level - self.duck_height
        self.move(int(self.duck_x), int(self.duck_y))
        if not isinstance(self.state, FallingState):
            self.change_state(WalkingState(self))

    def closeEvent(self, event):
        self.microphone_listener.stop()
        self.microphone_listener.wait()
        event.accept()

    def load_settings(self) -> None:
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
        self.current_language = self.settings_manager.get_value('current_language', default='en', value_type=str)
        self.skipped_version = self.settings_manager.get_value('skipped_version', default="", value_type=str)
        self.show_name = self.settings_manager.get_value('show_name', default=False, value_type=bool)

        global translations
        translations = load_translation(self.current_language)

        # Important: First, let's set up random_gen depending on pet_name
        if self.pet_name.strip():
            self.seed = get_seed_from_name(self.pet_name)
            self.random_gen = random.Random(self.seed)
            self.generate_characteristics()
        else:
            self.seed = None
            self.random_gen = random.Random()
            self.set_default_characteristics()

    def save_settings(self) -> None:
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
        self.update_duck_name()
        self.update_pet_size(self.pet_size)
        self.update_ground_level(self.ground_level_setting)

        if self.selected_skin != self.resources.current_skin:
            if self.selected_skin:
                self.resources.load_skin(self.selected_skin)
            else:
                self.resources.load_default_skin()
            self.resources.set_pet_size(self.pet_size)

        self.current_frame = self.resources.get_animation_frame('idle', 0)
        if self.current_frame:
            self.duck_width = self.current_frame.width()
            self.duck_height = self.current_frame.height()
            self.resize(self.duck_width, self.duck_height)
            self.update()

        if self.autostart_enabled:
            self.enable_autostart()
        else:
            self.disable_autostart()

        self.update_name_offset(getattr(self, 'name_offset_y', 0))
        self.update_font_base_size(getattr(self, 'font_base_size', 14))

        self.save_settings()
        self.duck_speed = self.base_duck_speed * (self.pet_size / 3)
        self.animation_timer.setInterval(100)

        self.direction_change_timer.stop()
        self.direction_change_timer.start(self.direction_change_interval * 1000)

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
        self.pet_size = size_factor
        self.duck_speed = self.base_duck_speed * (self.pet_size / 3)  # The speed of the duck

        # Update the pet size in ResourceManager
        self.resources.set_pet_size(self.pet_size)

        # Preservation of old sizes and positions
        old_width = self.duck_width
        old_height = self.duck_height
        old_x = self.duck_x
        old_y = self.duck_y

        self.current_frame = self.resources.get_animation_frame('idle', 0)
        if self.current_frame:
            self.duck_width = self.current_frame.width()
            self.duck_height = self.current_frame.height()
        else:
            self.duck_width = self.duck_height = 64

        # Calculate the change in size
        delta_width = self.duck_width - old_width
        delta_height = self.duck_height - old_height

        # Adjust the position of the duck
        self.duck_x -= delta_width / 2
        self.duck_y -= delta_height / 2

        self.resize(self.duck_width, self.duck_height)
        self.move(int(self.duck_x), int(self.duck_y))

        if self.name_window:
            self.name_window.update_label()

    def update_duck_skin(self):
        if self.selected_skin:
            self.resources.load_skin(self.selected_skin)
        else:
            self.resources.load_default_skin()
        self.resources.set_pet_size(self.pet_size)
        self.current_frame = self.resources.get_animation_frame('idle', 0)
        if self.current_frame:
            self.duck_width = self.current_frame.width()
            self.duck_height = self.current_frame.height()
            self.resize(self.duck_width, self.duck_height)
            self.update()
        self.state.enter()  # Reload the current state

    def reset_settings(self):
        self.settings_manager.clear()
        self.load_settings()
        self.apply_settings()

    def enable_autostart(self):
        if sys.platform == 'win32':
            exe_path = os.path.realpath(sys.argv[0])
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0, winreg.KEY_SET_VALUE
            )
            winreg.SetValueEx(key, 'QuackDuck', 0, winreg.REG_SZ, exe_path)
            winreg.CloseKey(key)

    def disable_autostart(self):
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

    def update_duck_name(self):
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
            logging.error(f"No input devices found.")
        return input_devices

    def restart_microphone_listener(self):
        self.microphone_listener.stop()
        self.microphone_listener.wait()
        self.microphone_listener = MicrophoneListener(
            device_index=self.selected_mic_index,
            activation_threshold=self.activation_threshold
        )
        self.microphone_listener.volume_signal.connect(self.on_volume_updated)
        self.microphone_listener.start()

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

    def icon_activated(self, reason):
        if reason == self.Trigger:
            if self.parent.isVisible():
                # The duck is visible - we hide it
                self.parent.hide()
                # Change the icon to "hidden"
                if os.path.exists(self.hidden_icon_path):
                    self.setIcon(QtGui.QIcon(self.hidden_icon_path))
            else:
                # Duck is hidden - we show
                self.parent.show()
                self.parent.raise_()
                self.parent.activateWindow()
                # Change the icon to "visible"
                if os.path.exists(self.visible_icon_path):
                    self.setIcon(QtGui.QIcon(self.visible_icon_path))

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
        self.parent.hide

        if os.path.exists(self.hidden_icon_path):
            self.setIcon(QtGui.QIcon(self.hidden_icon_path))

    def show_duck(self):
        self.parent.show
        self.parent.raise_()
        self.parent.activateWindow()

        if os.path.exists(self.visible_icon_path):
            self.setIcon(QtGui.QIcon(self.visible_icon_path))

    def check_for_updates(self):
        """
        Called when user clicks 'Check for updates' in the tray menu.
        We call duck.check_for_updates_manual() to handle the logic.
        """
        self.parent.check_for_updates_manual()

    def show_about(self):
        about_text = f"QuackDuck\nDeveloped with 💜 by zl0yxp\nDiscord: zl0yxp\nTelegram: t.me/quackduckapp"
        QtWidgets.QMessageBox.information(
            self.parent,
            translations.get("about_title", "About"),
            about_text,
            QtWidgets.QMessageBox.Ok
        )

# class TitleBar(QWidget):
#     def __init__(self, parent, scale_factor):
#         super().__init__()
#         self.parent = parent
#         self.scale_factor = scale_factor
#         self.init_ui()
#         self.start = QPoint(0, 0)
#         self.pressing = False

#     def init_ui(self):
#         self.setFixedHeight(int(40 * self.scale_factor))
#         self.setStyleSheet("""
#             QWidget {
#                 background-color: #1e1e1e;
#             }
#             QLabel {
#                 color: white;
#                 font-size: 16px;
#             }
#             QPushButton {
#                 background-color: transparent;
#                 border: none;
#                 color: white;
#                 font-size: 16px;
#                 width: 40px;
#                 height: 40px;
#             }
#             QPushButton:hover {
#                 background-color: #3a3a3a;
#                 border-radius: 5px;
#             }
#         """)

#         layout = QHBoxLayout(self)
#         layout.setContentsMargins(10, 0, 10, 0)
#         layout.setSpacing(0)

#         self.title = QLabel(translations.get("settings_title", "Settings"))
#         self.title.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
#         self.title.setStyleSheet("background-color: transparent;")

#         layout.addWidget(self.title)
#         layout.addStretch()

#         # Window closing button
#         self.close_button = QPushButton("✖")
#         self.close_button.setToolTip(translations.get("close_tooltip", "Close"))
#         self.close_button.setFixedSize(int(40 * self.scale_factor), int(40 * self.scale_factor))
#         self.close_button.clicked.connect(self.parent.close)

#         layout.addWidget(self.close_button)

#     def mousePressEvent(self, event):
#         if event.button() == Qt.LeftButton:
#             self.start = event.globalPos()
#             self.pressing = True

#     def mouseMoveEvent(self, event):
#         if self.pressing:
#             delta = event.globalPos() - self.start
#             self.parent.move(self.parent.pos() + delta)
#             self.start = event.globalPos()

#     def mouseReleaseEvent(self, event):
#         self.pressing = False

class SettingsWindow(QDialog):
    def __init__(self, duck, scale_factor):
        super().__init__()
        icon_path = resource_path("assets/images/settings.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QtGui.QIcon(icon_path))
        else:
            logging.error(f"Icon file not found: {icon_path}")

        self.duck = duck
        self.scale_factor = scale_factor
        self.setWindowTitle(translations.get("settings_title", "Settings"))
        window_scaled_width = 900 * self.scale_factor
        window_scaled_height = 700 * self.scale_factor
        self.resize(int(window_scaled_width), int(window_scaled_height))
        # self.setWindowFlag(Qt.FramelessWindowHint)
        # self.setAttribute(Qt.WA_TranslucentBackground, False)

        self.accent_qcolor = get_system_accent_color()
        self.accent_color = self.accent_qcolor.name()

        self.scale_factor = self.duck.scale_factor

        self.mic_preview_timer = QTimer()
        self.mic_preview_timer.timeout.connect(self.update_mic_preview)
        self.mic_preview_timer.start(10)

        self.init_ui()
        self.apply_styles()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # custom title bar
        # main_layout.addWidget(self.title_bar)

        # Main content
        content_layout = QHBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        # Left panel
        left_panel = QWidget()
        left_panel.setFixedWidth(220)

        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 20, 0, 20)
        left_layout.setSpacing(10)

        self.list_widget = QListWidget()
        self.list_widget.addItems([
            translations.get("page_button_general", "General"),
            translations.get("page_button_appearance", "Appearance"),
            translations.get("page_button_advanced", "Advanced"),
            translations.get("page_button_about", "About")
        ])
        self.list_widget.setCurrentRow(0)
        left_layout.addWidget(self.list_widget)

        left_layout.addStretch()

        version_label = QLabel(translations.get("version", "Version") + f" {PROJECT_VERSION}")
        version_label.setAlignment(Qt.AlignCenter)
        version_label.setStyleSheet("color: gray; font-size: 12px;")
        left_layout.addWidget(version_label)

        self.stacked_widget = QStackedWidget()
        self.stacked_widget.addWidget(self.create_general_page())
        self.stacked_widget.addWidget(self.create_appearance_page())
        self.stacked_widget.addWidget(self.create_advanced_page())
        self.stacked_widget.addWidget(self.create_about_page())

        self.list_widget.currentRowChanged.connect(self.stacked_widget.setCurrentIndex)

        content_layout.addWidget(left_panel)
        content_layout.addWidget(self.stacked_widget)

        main_layout.addLayout(content_layout)

    def apply_styles(self):
        accent_color = self.accent_qcolor
        self.setStyleSheet(f"""
            QDialog {{
                background-color: #121212;
                color: white;
                font-family: "Segoe UI", sans-serif;
                font-size: 14px;
            }}
            QListWidget {{
                background: transparent;
                color: white;
                border: none;
                font-size: 14px;
            }}
            QListWidget::item {{
                padding: 12px;
                background-color: transparent;
                color: white;
            }}
            QListWidget::item:hover {{
                background-color: {accent_color.darker(120).name()};
                border-radius: 5px;
            }}
            QListWidget::item:selected {{
                background-color: {accent_color.name()};
                color: white;
                border-radius: 5px;
                padding-left: 20px;
            }}
            QListWidget::item:selected:hover {{
                background-color: {accent_color.name()};
            }}
            QListWidget::item:focus {{
                outline: none;
            }}
            QLabel {{
                color: white;
                font-size: 14px;
            }}
            QLabel a {{
                color: {accent_color.name()};
                text-decoration: none;
            }}
            QLabel a:hover {{
                text-decoration: underline;
            }}
            QPushButton {{
                background-color: #3c3c3c;
                border: none;
                padding: 10px 20px;
                color: white;
                border-radius: 5px;
                font-size: 14px;
            }}
            QPushButton:hover {{
                background-color: #505050;
            }}
            QPushButton:pressed {{
                background-color: #606060;
            }}
            QLineEdit, QComboBox, QSlider, QSpinBox {{
                background-color: #3c3c3c;
                border: 1px solid #555555;
                border-radius: 5px;
                padding: 5px;
                color: white;
                font-size: 14px;
            }}
            QComboBox::drop-down {{
                border: none;
                background-color: transparent;
            }}
            QComboBox QAbstractItemView {{
                background-color: #2a2a2a;
                color: white;
                selection-background-color: #444444;
                selection-color: white;
            }}
            QCheckBox {{
                color: white;
                font-size: 14px;
            }}
            QProgressBar {{
                border: 1px solid #555555;
                border-radius: 6px;
                text-align: center;
                padding: 5px;
                background-color: #3c3c3c;
                height: 12px;
                color: white;
                font-size: 14px;
            }}
            QProgressBar::chunk {{
                background-color: {accent_color.name()};
                border-radius: 4px;
            }}
            #activationThresholdSlider::groove:horizontal {{
                height: 4px;
                background: transparent;
                border: none;
                border-bottom: 2px solid #555555;
            }}
            #activationThresholdSlider::handle:horizontal {{
                background: {accent_color.name()};
                border: 1px solid {accent_color.name()};
                width: 16px;
                height: 16px;
                margin: -6px 0;
                border-radius: 8px;
            }}
            #activationThresholdSlider::handle:horizontal:hover {{
                background: {accent_color.name()};
                border: 1px solid {accent_color.name()};
            }}
            #activationThresholdSlider::handle:horizontal:pressed {{
                background: {accent_color.darker(120).name()};
                border: 1px solid {accent_color.darker(120).name()};
            }}
            QScrollBar:vertical {{
                background: transparent;
                width: 12px;
                margin: 0px;
            }}
            QScrollBar::handle:vertical {{
                background: {accent_color.name()};
                min-height: 20px;
                border-radius: 6px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {accent_color.darker(120).name()};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                background: none;
            }}
            QScrollArea {{
                background-color: #121212;
                border: none;
            }}
            QScrollArea#skinsScroll {{
                background-color: #121212;
                border: none;
            }}
            QScrollArea#skinsScroll QScrollBar:vertical {{
                background: #2a2a2a;
                width: 10px;
                margin: 0px;
            }}
            QScrollArea#skinsScroll QScrollBar::handle:vertical {{
                background: #555555;
                min-height: 20px;
                border-radius: 5px;
            }}
            QScrollArea#skinsScroll QScrollBar::handle:vertical:hover {{
                background: #666666;
            }}
            QScrollArea#skinsScroll QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
            QWidget#skinWidget {{
                background-color: #0f0f0f;
                border: 1px solid #444444;
                border-radius: 10px;
            }}
            QPushButton#resetButton {{
                background-color: #a00;
            }}
            QPushButton#resetButton:hover {{
                background-color: #c00;
            }}
            QPushButton#resetButton:pressed {{
                background-color: #e00;
            }}
        """)

    def create_general_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)

        # Pet name
        pet_name_label = QLabel(translations.get("pet_name", "Pet Name:"))
        name_layout = QHBoxLayout()
        pet_name_edit = QLineEdit()
        pet_name_edit.setPlaceholderText(translations.get("enter_name_placeholder", "Name..."))
        pet_name_edit.setText(self.duck.pet_name)
        name_info_button = QPushButton("ℹ️")
        name_info_button.setFixedSize(30, 30)
        name_info_button.setToolTip(translations.get("info_about_pet_name_tooltip", "Information about pet name"))
        name_info_button.clicked.connect(self.show_name_characteristics)
        name_layout.addWidget(pet_name_edit)
        name_layout.addWidget(name_info_button)

        # Input device
        mic_label = QLabel(translations.get("input_device_selection", "Input Device:"))
        mic_combo = QComboBox()
        self.populate_microphones(mic_combo)
        mic_combo.setCurrentIndex(self.get_current_mic_index(mic_combo))

        # Activation threshold
        threshold_label = QLabel(translations.get("activation_threshold", "Activation Threshold:"))
        threshold_slider = QSlider(Qt.Horizontal)
        threshold_slider.setObjectName("activationThresholdSlider")
        threshold_slider.setRange(0, 100)
        threshold_slider.setValue(self.duck.activation_threshold)
        threshold_value_label = QLabel(str(self.duck.activation_threshold))
        threshold_value_label.setFixedWidth(40)
        threshold_value_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        threshold_slider.valueChanged.connect(lambda value: threshold_value_label.setText(str(value)))
        threshold_slider_layout = QHBoxLayout()
        threshold_slider_layout.addWidget(threshold_slider)
        threshold_slider_layout.addWidget(threshold_value_label)

        # Microphone level
        mic_level_preview = QProgressBar()
        mic_level_preview.setRange(0, 100)
        mic_level_preview.setValue(self.duck.current_volume if hasattr(self.duck, 'current_volume') else 50)
        mic_level_preview.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        # Turn on sound
        enable_sound_checkbox = QCheckBox(translations.get("turn_on_sound", "Enable Sound"))
        enable_sound_checkbox.setChecked(self.duck.sound_enabled)

        # Show duck's name
        show_name_checkbox = QCheckBox(translations.get("show_name_checkbox", "Show name above duck"))
        show_name_checkbox.setChecked(self.duck.show_name)

        buttons_layout = QHBoxLayout()
        save_button = QPushButton(translations.get("save_button", "Save"))
        cancel_button = QPushButton(translations.get("cancel_button", "Cancel"))
        buttons_layout.addStretch()
        buttons_layout.addWidget(save_button)
        buttons_layout.addWidget(cancel_button)

        save_button.clicked.connect(lambda: self.save_general_settings(
            pet_name_edit.text(),
            mic_combo.currentData(),
            threshold_slider.value(),
            enable_sound_checkbox.isChecked(),
            show_name_checkbox.isChecked()
        ))
        cancel_button.clicked.connect(self.close)

        layout.addWidget(pet_name_label)
        layout.addLayout(name_layout)
        layout.addWidget(mic_label)
        layout.addWidget(mic_combo)
        layout.addWidget(threshold_label)
        layout.addLayout(threshold_slider_layout)
        layout.addWidget(QLabel(translations.get("mic_level", "Sound Level:")))
        layout.addWidget(mic_level_preview)
        layout.addWidget(enable_sound_checkbox)
        layout.addWidget(show_name_checkbox)
        layout.addStretch()
        layout.addLayout(buttons_layout)

        self.general_page_widgets = {
            "pet_name_edit": pet_name_edit,
            "mic_combo": mic_combo,
            "threshold_slider": threshold_slider,
            "threshold_value_label": threshold_value_label,
            "mic_level_preview": mic_level_preview,
            "enable_sound_checkbox": enable_sound_checkbox,
            "show_name_checkbox": show_name_checkbox
        }

        return page

    def create_appearance_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)

        # Pet size
        pet_size_label = QLabel(translations.get("pet_size", "Pet size:"))
        pet_size_combo = QComboBox()
        size_options = {1: "x1", 2: "x2", 3: "x3", 5: "x5", 7: "x7", 10: "x10"}
        for size, label_text in size_options.items():
            pet_size_combo.addItem(label_text, size)
        current_size_index = pet_size_combo.findData(self.duck.pet_size)
        if current_size_index != -1:
            pet_size_combo.setCurrentIndex(current_size_index)
        else:
            pet_size_combo.setCurrentIndex(1)

        # Select Skin & Select Skin Folder
        skin_buttons_layout = QHBoxLayout()
        skin_selection_button = QPushButton(translations.get("select_skin_button", "Select Skin"))
        skin_folder_button = QPushButton(translations.get("select_skin_folder_button", "Select Skins Folder"))
        skin_buttons_layout.addWidget(skin_selection_button)
        skin_buttons_layout.addWidget(skin_folder_button)
        skin_selection_button.clicked.connect(self.open_skin_selection)
        skin_folder_button.clicked.connect(self.select_skins_folder)

        # Skin preview
        skins_label = QLabel(translations.get("skins_preview", "Skins Preview:"))
        skins_scroll = QScrollArea()
        skins_scroll.setObjectName('skinsScroll')
        skins_scroll.setWidgetResizable(True)
        skins_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        skins_container = QWidget()
        skins_container.setStyleSheet("background-color: #121212; border-radius: 10px;")
        skins_grid = QGridLayout(skins_container)
        skins_grid.setSpacing(15)

        self.skins_scroll = skins_scroll
        self.skins_container = skins_container
        self.skins_grid = skins_grid
        skins_scroll.setWidget(skins_container)

        skins_folder_path = self.duck.skin_folder if self.duck.skin_folder else translations.get("not_selected", "Not selected")
        skins_path_label = QLabel(translations.get("skin_folder_path", "Skins folder path:") + f" {skins_folder_path}")
        skins_path_label.setStyleSheet("color: gray; font-size: 12px;")
        skins_path_label.setAlignment(Qt.AlignLeft)
        self.skins_path_label = skins_path_label

        buttons_layout = QHBoxLayout()
        save_button = QPushButton(translations.get("save_button", "Save"))
        cancel_button = QPushButton(translations.get("cancel_button", "Cancel"))
        buttons_layout.addStretch()
        buttons_layout.addWidget(save_button)
        buttons_layout.addWidget(cancel_button)

        save_button.clicked.connect(lambda: self.save_appearance_settings(pet_size_combo.currentData()))
        cancel_button.clicked.connect(self.close)

        layout.addWidget(pet_size_label)
        layout.addWidget(pet_size_combo)
        layout.addLayout(skin_buttons_layout)
        layout.addWidget(skins_label)
        layout.addWidget(skins_scroll)
        layout.addWidget(skins_path_label)
        layout.addStretch()
        layout.addLayout(buttons_layout)

        self.skin_preview_timers = []
        if self.duck.skin_folder:
            self.load_skins_from_folder(self.duck.skin_folder)

        self.appearance_page_widgets = {
            "pet_size_combo": pet_size_combo
        }

        return page

    def create_advanced_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)

        # Floor level
        floor_level_label = QLabel(translations.get("floor_level", "Floor level (pixels from bottom):"))
        floor_level_spin = QSpinBox()
        floor_level_spin.setRange(0, 1000)
        floor_level_spin.setValue(self.duck.ground_level_setting)

        # Name offset
        name_offset_label = QLabel(translations.get("name_offset_y", "Name Offset Y (pixels):"))
        name_offset_spin = QSpinBox()
        name_offset_spin.setRange(-1000, 1000)
        name_offset_spin.setValue(self.duck.name_offset_y)

        # Base font size
        font_base_size_label = QLabel(translations.get("font_base_size", "Base font size:"))
        font_base_size_spin = QSpinBox()
        font_base_size_spin.setRange(6, 50)
        if not hasattr(self.duck, 'font_base_size'):
            self.duck.font_base_size = 14
        font_base_size_spin.setValue(self.duck.font_base_size)

        # Language
        language_label = QLabel(translations.get("language_selection", "Language:"))
        language_combo = QComboBox()
        language_options = {
            'en': 'English',
            'ru': 'Русский'
        }
        for code, name in language_options.items():
            language_combo.addItem(name, code)
        current_language_index = language_combo.findData(self.duck.current_language)
        if current_language_index != -1:
            language_combo.setCurrentIndex(current_language_index)
        else:
            language_combo.setCurrentIndex(0)

        # Run at system startup
        autostart_checkbox = QCheckBox(translations.get("run_at_system_startup", "Run at system startup"))
        autostart_checkbox.setChecked(self.duck.autostart_enabled)

        # Reset to default
        reset_button = QPushButton(translations.get("reset_to_default_button", "Reset all settings"))
        reset_button.setObjectName('resetButton')
        reset_button.clicked.connect(self.reset_settings)

        buttons_layout = QHBoxLayout()
        save_button = QPushButton(translations.get("save_button", "Save"))
        cancel_button = QPushButton(translations.get("cancel_button", "Cancel"))
        buttons_layout.addStretch()
        buttons_layout.addWidget(save_button)
        buttons_layout.addWidget(cancel_button)

        save_button.clicked.connect(lambda: self.save_advanced_settings(
            floor_level_spin.value(),
            name_offset_spin.value(),
            font_base_size_spin.value(),
            language_combo.currentData(),
            autostart_checkbox.isChecked()
        ))
        cancel_button.clicked.connect(self.close)

        layout.addWidget(floor_level_label)
        layout.addWidget(floor_level_spin)
        layout.addWidget(name_offset_label)
        layout.addWidget(name_offset_spin)
        layout.addWidget(font_base_size_label)
        layout.addWidget(font_base_size_spin)
        layout.addWidget(language_label)
        layout.addWidget(language_combo)
        layout.addWidget(autostart_checkbox)
        layout.addWidget(reset_button)
        layout.addStretch()
        layout.addLayout(buttons_layout)

        self.advanced_page_widgets = {
            "floor_level_spin": floor_level_spin,
            "name_offset_spin": name_offset_spin,
            "font_base_size_spin": font_base_size_spin,
            "language_combo": language_combo,
            "autostart_checkbox": autostart_checkbox
        }

        return page

    def create_about_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)

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

        support_buttons_layout = QHBoxLayout()
        support_button = QPushButton(translations.get("buy_me_a_coffee_button_settings_window", "Buy me a coffee ☕"))
        telegram_button = QPushButton("Telegram")
        github_button = QPushButton("GitHub")
        support_buttons_layout.addWidget(support_button)
        support_buttons_layout.addWidget(telegram_button)
        support_buttons_layout.addWidget(github_button)

        support_button.clicked.connect(lambda: self.open_link("https://buymeacoffee.com/zl0yxp"))
        telegram_button.clicked.connect(lambda: self.open_link("https://t.me/quackduckapp"))
        github_button.clicked.connect(lambda: self.open_link("https://github.com/KristopherZlo/quackduck"))

        buttons_layout = QHBoxLayout()
        save_button = QPushButton(translations.get("save_button", "Save"))
        cancel_button = QPushButton(translations.get("cancel_button", "Cancel"))
        buttons_layout.addStretch()
        buttons_layout.addWidget(save_button)
        buttons_layout.addWidget(cancel_button)

        save_button.clicked.connect(lambda: self.save_about_settings())
        cancel_button.clicked.connect(self.close)

        layout.addWidget(info_label)
        layout.addLayout(support_buttons_layout)
        layout.addStretch()
        layout.addLayout(buttons_layout)

        return page

    def populate_microphones(self, mic_combo):
        mic_combo.clear()
        input_devices = self.duck.get_input_devices()
        for idx, name in input_devices:
            mic_combo.addItem(name, idx)
        if self.duck.selected_mic_index is not None:
            current_index = mic_combo.findData(self.duck.selected_mic_index)
            if current_index != -1:
                mic_combo.setCurrentIndex(current_index)
            else:
                mic_combo.setCurrentIndex(0)
        else:
            mic_combo.setCurrentIndex(0)

    def get_current_mic_index(self, mic_combo):
        if self.duck.selected_mic_index is not None:
            index = mic_combo.findData(self.duck.selected_mic_index)
            return index if index != -1 else 0
        return 0

    def show_name_characteristics(self):
        name = self.general_page_widgets["pet_name_edit"].text()
        if name:
            characteristics = self.duck.get_name_characteristics(name)
            info_text = "\n".join([f"{key}: {value}" for key, value in characteristics.items()])
            QApplication.instance().beep()
            QMessageBox.information(self, translations.get("characteristics_title", "Characteristics"), info_text)
        else:
            QMessageBox.information(self, translations.get("characteristics_title", "Characteristics"), translations.get("characteristics_text", "Enter a name to see characteristics."))

    def save_general_settings(self, pet_name, mic_index, threshold, sound_enabled, show_name_checkbox):
        self.duck.pet_name = pet_name
        self.duck.selected_mic_index = mic_index
        self.duck.activation_threshold = threshold
        self.duck.sound_enabled = sound_enabled
        self.duck.show_name = show_name_checkbox
        self.duck.settings_manager.set_value('show_name', self.duck.show_name)

        # Updating the microphone
        self.duck.microphone_listener.update_settings(
            device_index=mic_index,
            activation_threshold=threshold
        )
        self.duck.restart_microphone_listener()

        self.duck.apply_settings()
        self.close()

    def save_appearance_settings(self, pet_size):
        self.duck.update_pet_size(pet_size)
        self.duck.apply_settings()
        self.close()

    def save_advanced_settings(self, floor_level, name_offset, font_base_size, language_code, autostart_enabled):
        self.duck.update_ground_level(floor_level)
        self.duck.name_offset_y = name_offset
        self.duck.font_base_size = font_base_size
        self.duck.current_language = language_code
        self.duck.autostart_enabled = autostart_enabled

        self.duck.settings_manager.set_value('name_offset_y', name_offset)
        self.duck.settings_manager.set_value('font_base_size', font_base_size)
        self.duck.settings_manager.set_value('current_language', language_code)

        if autostart_enabled:
            self.duck.enable_autostart()
        else:
            self.duck.disable_autostart()

        global translations
        translations = load_translation(language_code)

        self.duck.apply_settings()
        self.close()

    def save_about_settings(self):
        self.close()

    def reset_settings(self):
        reply = QMessageBox.question(self, translations.get("reset_to_default_title", "Reset settings"),
                                     translations.get("reset_to_default_conformation", "Are you sure you want to reset all settings?"),
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.duck.reset_settings()
            self.duck.apply_settings()
            self.close()

    def open_skin_selection(self):
        try:
            filename, _ = QFileDialog.getOpenFileName(
                self,
                translations.get("select_skin_file", "Select skin"),
                "",
                "Zip Archives (*.zip);;All Files (*)"
            )
            if filename:
                success = self.duck.resources.load_skin(filename)
                if success:
                    self.duck.selected_skin = filename
                    self.duck.save_settings()
                    QMessageBox.information(self, translations.get("success", "Success!"), translations.get("skin_loaded_successfully", "Skin loaded successfully."))
                    self.duck.update_duck_skin()
                else:
                    QMessageBox.warning(self, translations.get("error_title", "Error!"), translations.get("failed_to_load_skin", "Failed to load skin."))
        except Exception as e:
            QMessageBox.critical(self, translations.get("error_title", "Error!"), translations.get("error_while_loading_skin", "An error occurred while loading skin:") + f" {e}")

    def select_skins_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self,
            translations.get("select_skin_folder", "Select skins folder"),
            "",
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )
        if folder:
            self.skins_path_label.setText(translations.get("skin_folder_path", "Skins folder path:") + f" {folder}")
            self.duck.skin_folder = folder
            self.duck.save_settings()
            self.load_skins_from_folder(folder)

    def load_skins_from_folder(self, folder):
        if not os.path.exists(folder):
            return

        for timer in getattr(self, 'skin_preview_timers', []):
            if timer.isActive():
                timer.stop()
        self.skin_preview_timers = []

        while self.skins_grid.count():
            item = self.skins_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        row = 0
        col = 0
        max_columns = 3
        has_skins = False

        try:
            for skin_file in os.listdir(folder):
                skin_path = os.path.join(folder, skin_file)
                if os.path.isfile(skin_path) and skin_file.endswith('.zip'):
                    idle_frames = self.duck.resources.load_idle_frames_from_skin(skin_path)
                    if idle_frames:
                        self.display_skin_preview(skin_path, idle_frames, row, col)
                        has_skins = True
                        col += 1
                        if col >= max_columns:
                            col = 0
                            row += 1
                    else:
                        logging.error(f"Skipped {skin_file}: No valid idle frames.")
        except Exception as e:
            logging.error(f"Error loading skins from folder '{folder}': {e}")
            QMessageBox.warning(
                self,
                translations.get("error_title", "Error!"),
                translations.get("error_loading_skins", "An error occurred while loading skins from the folder.")
            )
            return

        if not has_skins:
            QMessageBox.warning(
                self,
                translations.get("warning_title", "Warning"),
                translations.get("no_skins_in_folder", "No skins in the selected folder.")
            )

    def display_skin_preview(self, skin_file, idle_frames, row, col):
        animation_label = QLabel()
        animation_label.setStyleSheet("background-color: transparent;")

        original_size = 64
        scale_factor = 2
        preview_size = int(original_size * scale_factor)

        animation_label.setFixedSize(preview_size, preview_size)
        animation_label.setAlignment(Qt.AlignCenter)
        animation_label.setScaledContents(False)

        frames = idle_frames
        frame_count = len(frames)
        if frame_count == 0:
            return

        animation_label.frames = frames
        animation_label.frame_index = 0

        def update_frame():
            frame = animation_label.frames[animation_label.frame_index]
            scaled_frame = frame.scaled(
                animation_label.size(),
                Qt.KeepAspectRatio,
                Qt.FastTransformation
            )
            animation_label.setPixmap(scaled_frame)
            animation_label.frame_index = (animation_label.frame_index + 1) % frame_count

        timer = QTimer()
        self.skin_preview_timers.append(timer)
        timer.timeout.connect(update_frame)
        timer.start(150)
        update_frame()

        animation_label.timer = timer

        skin_widget = QWidget()
        skin_layout = QVBoxLayout()
        skin_layout.setContentsMargins(0, 0, 0, 0)
        skin_layout.addWidget(animation_label)
        skin_widget.setLayout(skin_layout)
        skin_widget.setFixedSize(preview_size, preview_size)
        skin_widget.setStyleSheet("""
            background-color: #0f0f0f;
            border: 1px solid #444444;
            border-radius: 10px;
        """)

        skin_name = os.path.basename(skin_file)
        skin_widget.setToolTip(skin_name)
        skin_widget.skin_file = skin_file

        skin_widget.mousePressEvent = lambda event, sf=skin_file: self.apply_skin(sf)

        self.skins_grid.addWidget(skin_widget, row, col)

    def apply_skin(self, skin_file):
        if not os.path.exists(skin_file):
            QMessageBox.warning(self, translations.get("error_title", "Error!"), translations.get("file_not_found", "File not found: ") + f" '{skin_file}'")
            return

        success = self.duck.resources.load_skin(skin_file)
        if success:
            self.duck.selected_skin = skin_file
            self.duck.save_settings()
            QMessageBox.information(
                self,
                translations.get("success", "Success!"),
                translations.get("skin_applied_successfully", "Skin successfully applied:") + f" '{os.path.basename(skin_file)}'"
            )
            self.duck.update_duck_skin()
        else:
            QMessageBox.warning(
                self,
                translations.get("error_title", "Error!"),
                translations.get("failed_apply_skin", "Failed to apply skin:") + f" '{os.path.basename(skin_file)}'."
            )

    def open_link(self, url):
        webbrowser.open(url)

    def update_mic_preview(self):
        if hasattr(self.duck, 'current_volume') and hasattr(self, 'general_page_widgets'):
            level = self.duck.current_volume
            self.general_page_widgets["mic_level_preview"].setValue(int(level))

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