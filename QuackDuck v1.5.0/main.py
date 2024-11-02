import sys
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
import logging

from abc import ABC, abstractmethod

from PyQt5 import QtWidgets, QtGui, QtCore, QtMultimedia
from PyQt5.QtWidgets import (
    QApplication, QDialog, QHBoxLayout, QVBoxLayout, QWidget,
    QListWidget, QLabel, QPushButton, QStackedWidget, QLineEdit,
    QComboBox, QSlider, QProgressBar, QCheckBox,
    QSizePolicy, QSpinBox, QScrollArea, QGridLayout,
    QMessageBox, QFileDialog
)
from PyQt5.QtCore import Qt, QPoint, QTimer
from PyQt5.QtGui import QFont, QIcon, QPixmap, QColor

if sys.platform == 'win32':
    import winreg

import numpy as np
import sounddevice as sd

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s %(levelname)s:%(message)s',
    handlers=[
        logging.FileHandler(os.path.join(os.path.expanduser('~'), 'quackduck.log')),
        logging.StreamHandler(sys.stdout)
    ]
)

# PROJECT VERSION
PROJECT_VERSION = '1.5.0'

def load_translation(lang_code):
    try:
        lang_path = os.path.join('languages', f'lang_{lang_code}.json')
        with open(lang_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        logging.error(f"File {lang_path} not found.")
        return {}


# Languages: de / en / es / fr / ja / ko / ru / fi
current_language = 'ru'
translations = load_translation(current_language)

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
            # Return the color by default if it was not possible to get from the registry
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

def resource_path(relative_path):
    """Receives an absolute path to a resource file, works both in development mode and after packaging with Pyinstaller."""
    try:
        # Pyinstaller creates a temporary folder and keeps the way to _meipass
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

class DebugWindow(QtWidgets.QWidget):
    def __init__(self, duck):
        super().__init__()
        self.duck = duck
        self.setWindowTitle("QuackDuck Debug Mode")
        self.setGeometry(100, 100, 400, 300)
        self.init_ui()
    
    def init_ui(self):
        layout = QtWidgets.QVBoxLayout()

        # Section to Trigger States
        state_group = QtWidgets.QGroupBox("Trigger States")
        state_layout = QtWidgets.QHBoxLayout()

        btn_sleep = QtWidgets.QPushButton("Sleep")
        btn_sleep.clicked.connect(lambda: self.duck.change_state(SleepingState(self.duck)))

        btn_jump = QtWidgets.QPushButton("Jump")
        btn_jump.clicked.connect(lambda: self.duck.change_state(JumpingState(self.duck)))

        btn_idle = QtWidgets.QPushButton("Idle")
        btn_idle.clicked.connect(lambda: self.duck.change_state(IdleState(self.duck)))

        btn_walk = QtWidgets.QPushButton("Walk")
        btn_walk.clicked.connect(lambda: self.duck.change_state(WalkingState(self.duck)))

        btn_playful = QtWidgets.QPushButton("Playful")
        btn_playful.clicked.connect(lambda: self.duck.change_state(PlayfulState(self.duck)))

        state_layout.addWidget(btn_playful)
        state_layout.addWidget(btn_sleep)
        state_layout.addWidget(btn_jump)
        state_layout.addWidget(btn_idle)
        state_layout.addWidget(btn_walk)
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

        # Section to Reset Parameters
        btn_reset = QtWidgets.QPushButton("Reset Parameters")
        btn_reset.clicked.connect(self.reset_parameters)
        layout.addWidget(btn_reset)

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
        self.duck.settings.setValue('idle_duration', self.duck.idle_duration)
        logging.info(f"Idle duration updated to {value} seconds.")

    def update_sleep_timeout(self, value):
        self.duck.sleep_timeout = value
        self.duck.settings.setValue('sleep_timeout', self.duck.sleep_timeout)
        logging.info(f"Sleep timeout updated to {value} seconds.")

    def update_direction_interval(self, value):
        self.duck.direction_change_interval = value
        self.duck.settings.setValue('direction_change_interval', self.duck.direction_change_interval)
        logging.info(f"Direction change interval updated to {value} seconds.")

        # Restart the timer with a new interval
        self.duck.direction_change_timer.stop()
        self.duck.direction_change_timer.start(self.duck.direction_change_interval * 1000)

    def update_activation_threshold(self, value):
        self.duck.activation_threshold = value
        self.duck.settings.setValue('activation_threshold', self.duck.activation_threshold)
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
        self.duck.settings.setValue('sleep_timeout', self.duck.sleep_timeout)
        self.duck.settings.setValue('direction_change_interval', self.duck.direction_change_interval)
        self.duck.settings.setValue('activation_threshold', self.duck.activation_threshold)

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

class State(ABC):
    def __init__(self, duck):
        self.duck = duck

    @abstractmethod
    def enter(self):
        pass

    @abstractmethod
    def update_animation(self):
        pass

    @abstractmethod
    def update_position(self):
        pass

    @abstractmethod
    def exit(self):
        pass

    def handle_mouse_press(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self.duck.change_state(DraggingState(self.duck), event)
        elif event.button() == QtCore.Qt.RightButton:
            self.duck.change_state(JumpingState(self.duck))

    def handle_mouse_release(self, event):
        pass

    def handle_mouse_move(self, event):
        pass

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

    def update_animation(self):
        if self.frames and self.frame_index < len(self.frames) - 1:
            self.frame_index += 1
            self.update_frame()

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

    def handle_mouse_press(self, event):
        self.offset = event.pos()

    def handle_mouse_move(self, event):
        new_pos = event.globalPos() - self.offset
        self.duck.duck_x = new_pos.x()
        self.duck.duck_y = new_pos.y()
        self.duck.move(int(self.duck.duck_x), int(self.duck.duck_y))

    def handle_mouse_release(self, event):
        self.duck.change_state(FallingState(self.duck, play_animation=False, return_state=WalkingState(self.duck)))

class JumpingState(State):
    def __init__(self, duck, return_state=None):
        super().__init__(duck)
        self.return_state = return_state
        self.vertical_speed = -15
        self.is_falling = False  # Flag for tracking fall

    def enter(self):
        self.duck.facing_right = self.duck.direction == 1  # Set the direction of the look
        self.jump_frames = self.duck.resources.get_animation_frames_by_name('jump') or \
                           self.duck.resources.get_animation_frames_by_name('idle') or \
                           [self.duck.resources.get_default_frame()]
        self.fall_frames = self.duck.resources.get_animation_frames_by_name('fall') or \
                           self.duck.resources.get_animation_frames_by_name('idle') or \
                           [self.duck.resources.get_default_frame()]
        self.frames = self.jump_frames  # Start with a jump frame
        self.frame_index = 0
        self.update_frame()

    def update_animation(self):
        if self.frames and self.frame_index < len(self.frames) - 1:
            self.frame_index += 1
        else:
            # If you reach the end of the frames and the duck falls, we stay in the last frame
            if self.is_falling:
                self.frame_index = len(self.frames) - 1  # Stay in the last frame of the fall
            else:
                self.frame_index = 0  # Throw or stop on the last frame of the jump

        self.update_frame()

    def update_position(self):
        self.vertical_speed += 1
        self.duck.duck_y += self.vertical_speed

        # Check if the duck began to fall
        if not self.is_falling and self.vertical_speed >= 0:
            self.is_falling = True
            self.frames = self.fall_frames  # Switching to the falling frames
            self.frame_index = 0  # Drop off the frame for falling

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

    def update_animation(self):
        if self.frames:
            self.frame_index = (self.frame_index + 1) % len(self.frames)
            self.update_frame()

    def update_position(self):
        pass

    def exit(self):
        pass

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
        # Restore the previous values ​​of the direction and gaze
        self.duck.direction = self.previous_direction
        self.duck.facing_right = self.previous_facing_right

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
    def __init__(self):
        self.assets_dir = resource_path('assets')
        self.skins_dir = os.path.join(self.assets_dir, 'skins')
        self.current_skin = 'default'
        self.animations = {}
        self.sounds = []
        self.scale_factor = 3

        self.default_animations_config = {
            "idle": ["0:0"],
            "walk": ["1:0", "1:1", "1:2", "1:3", "1:4", "1:5"],
            "listen": ["2:1"],
            "fall": ["2:3"],
            "jump": ["2:0", "2:1", "2:2", "2:3"],
            "sleep": ["0:1"],
            "sleep_transition": ["2:1"]
        }

        self.load_default_skin()

    def load_idle_frames_from_skin(self, skin_file):
        try:
            with zipfile.ZipFile(skin_file, 'r') as zip_ref:
                if 'config.json' not in zip_ref.namelist():
                    logging.error(f"Skin {skin_file} does not contain config.json.")
                    return None

                temp_dir = tempfile.mkdtemp()
                zip_ref.extractall(temp_dir)

                config_path = os.path.join(temp_dir, 'config.json')
                with open(config_path, 'r') as f:
                    config = json.load(f)

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
                if not spritesheet_name or not frame_width or not frame_height:
                    logging.error(f"Config file is not complete {skin_file}.")
                    return None

                spritesheet_path = os.path.join(temp_dir, spritesheet_name)

                spritesheet = QtGui.QPixmap(spritesheet_path)
                frames = []
                for frame_str in frame_list:
                    row_col = frame_str.split(':')
                    if len(row_col) == 2:
                        try:
                            row = int(row_col[0])
                            col = int(row_col[1])
                            frame = spritesheet.copy(col * frame_width, row * frame_height, frame_width, frame_height)
                            frames.append(frame)
                        except ValueError:
                            logging.error(f"Incorrect frame format: {frame_str}")
                return frames
        except Exception as e:
            logging.error(f"Failed to load skin {skin_file}: {e}")
            return None

    def get_idle_animations(self):
        return [name for name in self.animations.keys() if name.startswith('idle')]

    def load_default_skin(self):
        skin_path = os.path.join(self.skins_dir, 'default')
        self.spritesheet_path = os.path.join(skin_path, 'spritesheet.png')
        self.frame_width = 32
        self.frame_height = 32
        self.animations_config = self.default_animations_config.copy()
        self.sound_files = [os.path.join(skin_path, 'wuak.mp3')]
        self.load_sprites()
        self.load_sounds()

    def load_skin(self, skin_path):
        if os.path.isfile(skin_path) and skin_path.endswith('.zip'):
            try:
                skin_name = os.path.splitext(os.path.basename(skin_path))[0]
                skin_dir = os.path.join(self.skins_dir, skin_name)
                if not os.path.exists(skin_dir):
                    os.makedirs(skin_dir)
                    with zipfile.ZipFile(skin_path, 'r') as zip_ref:
                        zip_ref.extractall(skin_dir)
            except Exception as e:
                logging.error(f"Error extracting skin: {e}")
                self.load_default_skin()
                return False
        elif os.path.isdir(skin_path):
            skin_dir = skin_path
            skin_name = os.path.basename(skin_dir)
        else:
            self.load_default_skin()
            return False

        json_path = os.path.join(skin_dir, 'config.json')
        if not os.path.exists(json_path):
            self.load_default_skin()
            return False

        try:
            with open(json_path, 'r') as f:
                config = json.load(f)
            spritesheet_name = config.get('spritesheet')
            frame_width = config.get('frame_width')
            frame_height = config.get('frame_height')
            animations = config.get('animations', {})

            if not spritesheet_name or not frame_width or not frame_height:
                self.load_default_skin()
                return False

            spritesheet_path = os.path.join(skin_dir, spritesheet_name)
            if not os.path.exists(spritesheet_path):
                self.load_default_skin()
                return False

            sound_names = config.get('sound', [])
            if isinstance(sound_names, str):
                sound_names = [sound_names]

            sound_paths = []
            for sound_name in sound_names:
                sound_path = os.path.join(skin_dir, sound_name)
                if os.path.exists(sound_path):
                    sound_paths.append(sound_path)

            self.spritesheet_path = spritesheet_path
            self.sound_files = sound_paths
            self.frame_width = frame_width
            self.frame_height = frame_height
            self.animations_config = animations

            self.load_sprites()
            self.load_sounds()

            self.current_skin = skin_name

            return True

        except Exception as e:
            logging.error(f"Error loading skin: {e}")
            self.load_default_skin()
            return False

    def load_sprites(self):
        if not os.path.exists(self.spritesheet_path):
            return

        spritesheet = QtGui.QPixmap(self.spritesheet_path)
        if spritesheet.isNull():
            return

        frame_width = self.frame_width
        frame_height = self.frame_height
        scale_factor = self.scale_factor

        def get_frame(row, col):
            frame = spritesheet.copy(col * frame_width, row * frame_height, frame_width, frame_height)
            size = frame.size()
            frame = frame.scaled(
                size.width() * scale_factor,
                size.height() * scale_factor,
                QtCore.Qt.KeepAspectRatio,
                QtCore.Qt.FastTransformation,
            )
            return frame

        self.animations.clear()

        for anim_name, frame_list in self.animations_config.items():
            frames = self.get_animation_frames(get_frame, frame_list)
            self.animations[anim_name] = frames

    def get_animation_frames(self, get_frame_func, frame_list):
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

    def load_sounds(self):
        self.sounds = self.sound_files.copy()

    def get_animation_frames_by_name(self, animation_name):
        return self.animations.get(animation_name, [])

    def get_animation_frame(self, animation_name, frame_index):
        frames = self.get_animation_frames_by_name(animation_name)
        if frames and 0 <= frame_index < len(frames):
            return frames[frame_index]
        return None

    def get_default_frame(self):
        frame = self.get_animation_frame('idle', 0)
        if frame:
            return frame
        for frames in self.animations.values():
            if frames:
                return frames[0]
        return None

    def get_random_sound(self):
        return random.choice(self.sounds) if self.sounds else None

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
        self.resources = ResourceManager()
        self.settings = QtCore.QSettings('zl0yxp', 'QuackDuck')
        self.load_settings()

        self.cursor_positions = []
        self.cursor_shake_timer = QtCore.QTimer()
        self.cursor_shake_timer.timeout.connect(self.check_cursor_shake)

        # Initialize attributes from settings
        self.selected_mic_index = self.settings.value('selected_mic_index', type=int, defaultValue=None)
        self.activation_threshold = self.settings.value('activation_threshold', type=int, defaultValue=10)
        self.sound_enabled = self.settings.value('sound_enabled', type=bool, defaultValue=True)
        self.autostart_enabled = self.settings.value('autostart_enabled', type=bool, defaultValue=True)
        self.playful_behavior_probability = self.settings.value('playful_behavior_probability', type=float, defaultValue=0.1)
        self.ground_level_setting = self.settings.value('ground_level', type=int, defaultValue=0)
        self.pet_size = self.settings.value('pet_size', type=int, defaultValue=3)
        self.skin_folder = self.settings.value('skin_folder', type=str, defaultValue=None)
        self.selected_skin = self.settings.value('selected_skin', type=str, defaultValue=None)
        self.base_duck_speed = self.settings.value('duck_speed', type=float, defaultValue=2.0)
        self.duck_speed = self.base_duck_speed * self.pet_size
        self.random_behavior = self.settings.value('random_behavior', type=bool, defaultValue=True)
        self.idle_duration = self.settings.value('idle_duration', type=float, defaultValue=5.0)  # Idle duration in seconds
        self.direction_change_interval = self.settings.value('direction_change_interval', type=float, defaultValue=20.0)
        # self.listening_scheduled = False
        self.is_listening = False
        self.listening_entry_timer = None
        self.listening_exit_timer = None
        self.exit_listening_timer = None

        self.facing_right = True

        # Get the size of the screen
        screen_rect = QtWidgets.QApplication.desktop().screenGeometry()
        self.screen_width = screen_rect.width()
        self.screen_height = screen_rect.height()

        # Load the current frame and set the duck dimensions
        self.current_frame = self.resources.get_animation_frame('idle', 0)
        if self.current_frame:
            self.duck_width = self.current_frame.width()
            self.duck_height = self.current_frame.height()
        else:
            self.duck_width = self.duck_height = 64
        self.resize(self.duck_width, self.duck_height)

        # Initialize the position of the duck
        self.duck_x = (self.screen_width - self.duck_width) // 2
        self.duck_y = -self.duck_height

        self.has_jumped = False
        self.direction = 1

        # Initialize Ground_level
        self.ground_level = self.get_ground_level()

        # We initialize the condition of the duck before the Apply_Settings call
        self.state = FallingState(self)
        self.state.enter()

        # ** set the timers before using settings **
        self.setup_timers()

        self.apply_settings()

        # Initialize Microphone_Listener
        self.microphone_listener = MicrophoneListener(
            device_index=self.selected_mic_index,
            activation_threshold=self.activation_threshold
        )
        self.microphone_listener.volume_signal.connect(self.on_volume_updated)
        self.microphone_listener.start()

        # Initialize DebugWindow
        self.debug_window = DebugWindow(self)

        self.init_ui()
        self.setup_random_behavior()

        self.last_interaction_time = time.time()
        self.last_sound_time = QtCore.QTime.currentTime()

        self.tray_icon = SystemTrayIcon(self)
        self.tray_icon.show()

        self.current_volume = 0
        self.media_player = QtMultimedia.QMediaPlayer()
        self.media_player.setVolume(50)

        self.pet_name = self.settings.value('pet_name', '', type=str)
        if self.pet_name:
            self.seed = get_seed_from_name(self.pet_name)
            self.random_gen = random.Random(self.seed)
            self.generate_characteristics()
        else:
            self.seed = None
            self.random_gen = random.Random()
            self.set_default_characteristics()

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
            return
        sound_file = self.resources.get_random_sound()
        if sound_file:
            url = QtCore.QUrl.fromLocalFile(sound_file)
            self.media_player.setMedia(QtMultimedia.QMediaContent(url))
            self.media_player.play()
            logging.info(f"Played sound: {sound_file}")

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
        self.movement_speed = self.random_gen.uniform(1.5, 2)
        self.base_duck_speed = self.movement_speed
        self.sound_interval_min = 60 + self.random_gen.random() * (300 - 60)
        self.sound_interval_max = 301 + self.random_gen.random() * (900 - 301)
        if self.sound_interval_min >= self.sound_interval_max:
            self.sound_interval_min, self.sound_interval_max = self.sound_interval_max, self.sound_interval_min
        self.sound_response_probability = 0.01 + self.random_gen.random() * (0.25 - 0.01)
        self.playful_behavior_probability = 0.1 + self.random_gen.random() * (0.5 - 0.1)
        self.sleep_timeout = (5 + self.random_gen.random() * 10) * 60 # 5 to 15 minutes

    def set_default_characteristics(self):
        self.movement_speed = 2
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

        self.last_interaction_time = time.time()
        self.sleep_timer = QtCore.QTimer()
        self.sleep_timer.timeout.connect(self.check_sleep)
        self.sleep_timer.start(10000)  # Check every 10 seconds

        self.direction_change_timer = QtCore.QTimer()
        self.direction_change_timer.timeout.connect(self.change_direction)
        self.direction_change_timer.start(self.direction_change_interval * 1000)  # Interval in milliseconds

        self.playful_timer = QtCore.QTimer()
        self.playful_timer.timeout.connect(self.check_playful_state)
        self.playful_timer.start(10 * 60 * 1000)  # Check every 10 minutes

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

    def enter_random_idle_state(self):
        if not isinstance(self.state, IdleState):
            self.change_state(IdleState(self))

    def change_direction(self):
        self.direction *= -1
        self.facing_right = self.direction == 1

    def change_state(self, new_state, event=None):
        allowed_wake_states = (DraggingState, PlayfulState, ListeningState, JumpingState)
        
        if isinstance(self.state, SleepingState):
            if isinstance(new_state, allowed_wake_states):
                logging.info(f"Transition from SleepingState to {new_state.__class__.__name__}")
                self.state.exit()
                self.state = new_state
                self.state.enter()
                if event:
                    self.state.handle_mouse_press(event)
            else:
                # Stay in Sleepingstate
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
        
        # Detection "shaking" cursor
        if isinstance(self.state, (IdleState, WalkingState)):
            self.start_cursor_shake_detection()
            logging.info("Starting cursor shake detection.")
        else:
            self.stop_cursor_shake_detection()
            logging.info("Stop detecting cursor shake.")

    def start_cursor_shake_detection(self):
        self.cursor_positions = []
        self.cursor_shake_timer.start(50)  # Check every 50 ms

    def stop_cursor_shake_detection(self):
        self.cursor_shake_timer.stop()
        self.cursor_positions = []

    def check_cursor_shake(self):
        cursor_pos = QtGui.QCursor.pos()
        duck_pos = self.pos()
        duck_rect = self.rect()
        duck_center = duck_pos + duck_rect.center()
        dx = cursor_pos.x() - duck_center.x()
        dy = cursor_pos.y() - duck_center.y()
        distance = (dx**2 + dy**2)**0.5

        # The basic distance for activation at the size of the duck 3 (standard)
        base_distance = 50
        # Scale the distance depending on the size of the duck
        distance_threshold = base_distance * (self.pet_size / 3)

        if distance <= distance_threshold:
            current_time = time.time()
            self.cursor_positions.append((current_time, cursor_pos))
            # Keep positions over the past 1 second
            self.cursor_positions = [(t, pos) for t, pos in self.cursor_positions if current_time - t <= 1.0]
            if len(self.cursor_positions) >= 8:
                # Check the changes in the direction of movement
                direction_changes = 0
                for i in range(2, len(self.cursor_positions)):
                    prev_dx = self.cursor_positions[i-1][1].x() - self.cursor_positions[i-2][1].x()
                    prev_dy = self.cursor_positions[i-1][1].y() - self.cursor_positions[i-2][1].y()
                    curr_dx = self.cursor_positions[i][1].x() - self.cursor_positions[i-1][1].x()
                    curr_dy = self.cursor_positions[i][1].y() - self.cursor_positions[i-1][1].y()
                    if (prev_dx * curr_dx < 0) or (prev_dy * curr_dy < 0):
                        direction_changes += 1
                if direction_changes >= 2:
                    # The shaking of the cursor was detected
                    self.stop_cursor_shake_detection()
                    self.change_state(PlayfulState(self))
        else:
            self.cursor_positions = []  # Drop an array if the cursor is far away

    def update_animation(self):
        self.state.update_animation()

    def update_position(self):
        self.state.update_position()

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
        self.settings.setValue('ground_level', new_ground_level)
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
        # logging.debug(f"Volume update: {volume}%")
        
        if volume > self.activation_threshold:
            self.last_interaction_time = time.time()
            if self.listening_exit_timer:
                self.listening_exit_timer.stop()
                self.listening_exit_timer = None
                logging.debug("ListeningState exit timer stopped.")
            
            if not self.is_listening and not self.listening_entry_timer:
                self.listening_entry_timer = QtCore.QTimer()
                self.listening_entry_timer.setSingleShot(True)
                self.listening_entry_timer.timeout.connect(self.enter_listening_state)
                self.listening_entry_timer.start(100)  # 100 ms delay to enter a listening state
                logging.debug("The ListeningState entry timer has been started for 100ms.")
        else:
            if self.listening_entry_timer:
                self.listening_entry_timer.stop()
                self.listening_entry_timer = None
                logging.debug("The ListeningState entry timer has stopped.")
            
            if self.is_listening and not self.listening_exit_timer:
                self.listening_exit_timer = QtCore.QTimer()
                self.listening_exit_timer.setSingleShot(True)
                self.listening_exit_timer.timeout.connect(self.exit_listening_state)
                self.listening_exit_timer.start(1000)  # 1 second (1000 ms) of exit delay from a listening state
                logging.debug("The ListeningState exit timer has been started for 1 second.")

    def stop_current_state(self):
        if self.state:
            self.state.exit()
            self.state = None

    def on_sound_detected(self):
        if not self.sound_enabled:
            self.schedule_next_sound()
            return

        if random.random() < self.sound_response_probability:
            # Check if a duck in Fallingstate
            if isinstance(self.state, FallingState):
                # Set the flag to enter lineingstate after landing
                self.listening_entry_scheduled = True
            else:
                # Check if a duck on the floor
                is_on_ground = self.duck_y + self.duck_height >= self.ground_level - 1  # Permissible error

                if is_on_ground:
                    if not self.is_listening and not self.listening_entry_scheduled:
                        self.listening_entry_scheduled = True
                        # Plan a transition to ListeningState through 100ms
                        QtCore.QTimer.singleShot(100, self.enter_listening_state)

        self.schedule_next_sound()

    def enter_listening_state(self):
        logging.info("Entering to ListeningState.")
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

    def play_random_sound(self):
        if not self.sound_enabled:
            self.schedule_next_sound()
            return
        sound_file = self.resources.get_random_sound()
        if sound_file:
            url = QtCore.QUrl.fromLocalFile(sound_file)
            self.media_player.setMedia(QtMultimedia.QMediaContent(url))
            self.media_player.play()
        self.schedule_next_sound()

    def open_settings(self):
        if hasattr(self, 'settings_window') and self.settings_window.isVisible():
            self.settings_window.raise_()
            self.settings_window.activateWindow()
        else:
            self.settings_window = SettingsWindow(self)  # Transfer the link to Duck
            self.settings_window.show()

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

    def load_settings(self):
        self.pet_name = self.settings.value('pet_name', type=str, defaultValue="")
        self.selected_mic_index = self.settings.value('selected_mic_index', type=int, defaultValue=None)
        self.activation_threshold = self.settings.value('activation_threshold', type=int, defaultValue=1)
        self.sound_response_probability = self.settings.value('sound_response_probability', type=float, defaultValue=0.01)
        self.sound_enabled = self.settings.value('sound_enabled', type=bool, defaultValue=True)
        self.autostart_enabled = self.settings.value('autostart_enabled', type=bool, defaultValue=True)
        self.playful_behavior_probability = self.settings.value('playful_behavior_probability', type=float, defaultValue=0.1)
        self.ground_level_setting = self.settings.value('ground_level', type=int, defaultValue=0)
        self.ground_level = self.get_ground_level()
        self.pet_size = self.settings.value('pet_size', type=int, defaultValue=3)
        self.skin_folder = self.settings.value('skin_folder', type=str, defaultValue=None)
        self.selected_skin = self.settings.value('selected_skin', type=str, defaultValue=None)
        self.base_duck_speed = self.settings.value('duck_speed', type=float, defaultValue=2.0)
        self.duck_speed = self.base_duck_speed * self.pet_size
        self.random_behavior = self.settings.value('random_behavior', type=bool, defaultValue=True)
        self.idle_duration = self.settings.value('idle_duration', type=float, defaultValue=5.0)
        self.sleep_timeout = self.settings.value('sleep_timeout', type=float, defaultValue=300.0)  # Default 5 minutes (enter sleep mode timer)
        self.direction_change_interval = self.settings.value('direction_change_interval', type=float, defaultValue=20.0)
        if not self.pet_name:
            self.sleep_timeout = self.settings.value('sleep_timeout', type=float, defaultValue=300.0)
        else:
            self.generate_characteristics()

    def save_settings(self):
        self.settings.setValue('pet_name', self.pet_name)
        self.settings.setValue('selected_mic_index', self.selected_mic_index)
        self.settings.setValue('activation_threshold', self.activation_threshold)
        self.settings.setValue('sound_enabled', self.sound_enabled)
        self.settings.setValue('autostart_enabled', self.autostart_enabled)
        self.settings.setValue('ground_level', self.ground_level_setting)
        self.settings.setValue('pet_size', self.pet_size)
        self.settings.setValue('skin_folder', self.skin_folder)
        self.settings.setValue('selected_skin', self.selected_skin)
        self.settings.setValue('duck_speed', self.base_duck_speed)
        self.settings.setValue('random_behavior', self.random_behavior)
        self.settings.setValue('idle_duration', self.idle_duration)
        self.settings.setValue('sleep_timeout', self.sleep_timeout)
        self.settings.setValue('direction_change_interval', self.direction_change_interval)
        if not self.pet_name:
            self.settings.setValue('sleep_timeout', self.sleep_timeout)

    def apply_settings(self):
        self.update_duck_name()
        self.update_pet_size(self.pet_size)
        self.update_ground_level(self.ground_level_setting)

        # Only reload the skin if it has changed
        if self.selected_skin != self.resources.current_skin:
            if self.selected_skin:
                self.resources.load_skin(self.selected_skin)
            else:
                self.resources.load_default_skin()

        # Update the current frame and resize only if necessary
        if self.current_frame != self.resources.get_animation_frame('idle', 0):
            self.current_frame = self.resources.get_animation_frame('idle', 0)
            if self.current_frame:
                self.duck_width = self.current_frame.width()
                self.duck_height = self.current_frame.height()
                self.resize(self.duck_width, self.duck_height)
                self.update()

        self.state.enter()

        if self.autostart_enabled:
            self.enable_autostart()
        else:
            self.disable_autostart()

        self.save_settings()

        # Update other settings as needed
        self.duck_speed = self.base_duck_speed * (self.pet_size / 3)
        self.animation_timer.setInterval(100)

        self.direction_change_timer.stop()
        self.direction_change_timer.start(self.direction_change_interval * 1000)

    def update_pet_size(self, size_factor):
        self.pet_size = size_factor
        self.duck_speed = self.base_duck_speed * (self.pet_size / 3)  # The speed of the duck

        self.resources.scale_factor = self.pet_size
        self.resources.load_sprites()

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

    def update_duck_skin(self):
        if self.selected_skin:
            self.resources.load_skin(self.selected_skin)
        else:
            self.resources.load_default_skin()
        self.current_frame = self.resources.get_animation_frame('idle', 0)
        if self.current_frame:
            self.duck_width = self.current_frame.width()
            self.duck_height = self.current_frame.height()
            self.resize(self.duck_width, self.duck_height)
            self.update()
        self.state.enter()  # Reload the current condition

    def reset_settings(self):
        self.settings.clear()
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
        icon_path = resource_path("assets/images/duck_icon.png")
        if not os.path.exists(icon_path):
            logging.error(f"Icon file {icon_path} not found.")
            QtWidgets.QMessageBox.critical(parent, translations.get("error_title", "Error!"), translations.get("file_not_found", "File not found:")+ f": '{icon_path}'")
            super().__init__()  # Initialize without an icon
        else:
            icon = QtGui.QIcon(icon_path)
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

        show_action.triggered.connect(self.parent.show)
        hide_action.triggered.connect(self.parent.hide)
        exit_action.triggered.connect(QtWidgets.qApp.quit)

        menu.addSeparator()

        # ** New option Debug Mode **
        debug_action = menu.addAction(translations.get("debug_mode", "🛠️ Debug mode"))
        debug_action.triggered.connect(self.parent.show_debug_window)  # Connect to Duck method

        self.setContextMenu(menu)

    def check_for_updates(self):
        QtWidgets.QMessageBox.information(
            self.parent,
            translations.get("check_updates_title", "Updates"),
            "The update functionality has not yet been implemented.",
            QtWidgets.QMessageBox.Ok
        )

    def show_about(self):
        about_text = f"QuackDuck\nDeveloped with 💜 by zl0yxp\nDiscord: zl0yxp\nTelegram: t.me/quackduckapp"
        QtWidgets.QMessageBox.information(
            self.parent,
            translations.get("about_title", "About"),
            about_text,
            QtWidgets.QMessageBox.Ok
        )

    def icon_activated(self, reason):
        if reason == self.Trigger:
            if self.parent.isVisible():
                self.parent.hide()
            else:
                self.parent.show()

class TitleBar(QWidget):
    def __init__(self, parent):
        super().__init__()
        self.parent = parent
        self.init_ui()
        self.start = QPoint(0, 0)
        self.pressing = False

    def init_ui(self):
        self.setFixedHeight(40)
        self.setStyleSheet("""
            QWidget {
                background-color: #1e1e1e;
            }
            QLabel {
                color: white;
                font-size: 16px;
            }
            QPushButton {
                background-color: transparent;
                border: none;
                color: white;
                font-size: 16px;
                width: 40px;
                height: 40px;
            }
            QPushButton:hover {
                background-color: #3a3a3a;
                border-radius: 5px;
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 10, 0)
        layout.setSpacing(0)

        self.title = QLabel(translations.get("settings_title", "Settings"))
        self.title.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        self.title.setStyleSheet("background-color: transparent;")

        layout.addWidget(self.title)
        layout.addStretch()

        # Window closing button
        self.close_button = QPushButton("✖")
        self.close_button.setToolTip(translations.get("close_tooltip", "Close"))
        self.close_button.clicked.connect(self.parent.close)

        layout.addWidget(self.close_button)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.start = event.globalPos()
            self.pressing = True

    def mouseMoveEvent(self, event):
        if self.pressing:
            delta = event.globalPos() - self.start
            self.parent.move(self.parent.pos() + delta)
            self.start = event.globalPos()

    def mouseReleaseEvent(self, event):
        self.pressing = False

class SettingsWindow(QDialog):
    def __init__(self, duck):
        super().__init__()
        self.skin_preview_timers = []
        self.duck = duck  # Link to the main class Duck
        self.setWindowTitle(translations.get("settings_title", "Settings"))
        self.resize(900, 700)
        self.setWindowFlag(Qt.FramelessWindowHint)  # Without a frame for style
        self.setAttribute(Qt.WA_TranslucentBackground, False)

        self.accent_qcolor = get_system_accent_color()
        self.accent_color = self.accent_qcolor.name()

        self.init_ui()
        self.apply_styles()

        # Timer for updating the level of microphone
        self.mic_preview_timer = QTimer()
        self.mic_preview_timer.timeout.connect(self.update_mic_preview)
        self.mic_preview_timer.start(10)  # Update every 10 ms

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Heading panel
        self.title_bar = TitleBar(self)
        main_layout.addWidget(self.title_bar)

        # Basic content
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
        self.list_widget.addItems([translations.get("page_button_general", "General"), translations.get("page_button_appearance", "Appearance"), translations.get("page_button_advanced", "Advanced"), translations.get("page_button_about", "About")])
        self.list_widget.setCurrentRow(0)
        left_layout.addWidget(self.list_widget)

        left_layout.addStretch()

        version_label = QLabel(translations.get("version", "Version") + f" {PROJECT_VERSION}")
        version_label.setAlignment(Qt.AlignCenter)
        version_label.setStyleSheet("color: gray; font-size: 12px;")
        left_layout.addWidget(version_label)

        # Stack pages
        self.stacked_widget = QStackedWidget()
        self.stacked_widget.addWidget(self.create_general_page())
        self.stacked_widget.addWidget(self.create_appearance_page())
        self.stacked_widget.addWidget(self.create_advanced_page())
        self.stacked_widget.addWidget(self.create_about_page())

        # The connection of the choice in the list of pages
        self.list_widget.currentRowChanged.connect(self.stacked_widget.setCurrentIndex)

        # Adding panels to the main content
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

        # The name of the pet
        pet_name_label = QLabel(translations.get("pet_name", "Pets name:"))
        name_layout = QHBoxLayout()
        pet_name_edit = QLineEdit()
        pet_name_edit.setPlaceholderText(translations.get("enter_name_placeholder", "Name..."))
        pet_name_edit.setText(self.duck.pet_name)
        name_info_button = QPushButton("ℹ️")
        name_info_button.setFixedSize(30, 30)
        name_info_button.setToolTip(translations.get("info_about_pet_name_tooltip", "Information about pets name"))
        name_info_button.clicked.connect(self.show_name_characteristics)
        name_layout.addWidget(pet_name_edit)
        name_layout.addWidget(name_info_button)

        # Choosing a microphone
        mic_label = QLabel(translations.get("input_device_selection", "Input device:"))
        mic_combo = QComboBox()
        self.populate_microphones(mic_combo)
        mic_combo.setCurrentIndex(self.get_current_mic_index(mic_combo))

        # Activation threshold
        threshold_label = QLabel(translations.get("activation_threshold", "Activation threshold:"))
        threshold_layout = QHBoxLayout()

        threshold_slider = QSlider(Qt.Horizontal)
        threshold_slider.setObjectName("activationThresholdSlider")  # Purpose of the name for the slider
        threshold_slider.setRange(0, 100)
        threshold_slider.setValue(self.duck.activation_threshold)

        threshold_value_label = QLabel(str(self.duck.activation_threshold))
        threshold_value_label.setFixedWidth(40)
        threshold_value_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        threshold_slider.valueChanged.connect(lambda value: threshold_value_label.setText(str(value)))

        threshold_slider_layout = QHBoxLayout()
        threshold_slider_layout.addWidget(threshold_slider)
        threshold_slider_layout.addWidget(threshold_value_label)

        # The level of the microphone
        mic_level_preview = QProgressBar()
        mic_level_preview.setRange(0, 100)
        mic_level_preview.setValue(self.duck.current_volume if hasattr(self.duck, 'current_volume') else 50)
        mic_level_preview.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        # Sound settings
        enable_sound_checkbox = QCheckBox(translations.get("turn_on_sound", "Sound on/off"))
        enable_sound_checkbox.setChecked(self.duck.sound_enabled)
        autostart_checkbox = QCheckBox(translations.get("run_at_system_startup", "Run at system startup"))
        autostart_checkbox.setChecked(self.duck.autostart_enabled)

        # Buttons
        buttons_layout = QHBoxLayout()
        save_button = QPushButton(translations.get("save_button", "Save"))
        cancel_button = QPushButton(translations.get("cancel_button", "Cancel"))
        buttons_layout.addStretch()
        buttons_layout.addWidget(save_button)
        buttons_layout.addWidget(cancel_button)

        # Connection of buttons to action
        save_button.clicked.connect(lambda: self.save_settings(
            pet_name_edit.text(),
            mic_combo.currentData(),
            threshold_slider.value(),
            enable_sound_checkbox.isChecked(),
            autostart_checkbox.isChecked()
        ))
        cancel_button.clicked.connect(self.close)

        # Adding widgets to the common Layout
        layout.addWidget(pet_name_label)
        layout.addLayout(name_layout)
        layout.addWidget(mic_label)
        layout.addWidget(mic_combo)
        layout.addWidget(threshold_label)
        layout.addLayout(threshold_slider_layout)
        layout.addWidget(QLabel(translations.get("mic_level", "Sound level:")))
        layout.addWidget(mic_level_preview)
        layout.addWidget(enable_sound_checkbox)
        layout.addWidget(autostart_checkbox)
        layout.addStretch()
        layout.addLayout(buttons_layout)

        # Preservation of links to elements for updating
        self.general_page_widgets = {
            "pet_name_edit": pet_name_edit,
            "mic_combo": mic_combo,
            "threshold_slider": threshold_slider,
            "threshold_value_label": threshold_value_label,
            "mic_level_preview": mic_level_preview,
            "enable_sound_checkbox": enable_sound_checkbox,
            "autostart_checkbox": autostart_checkbox
        }

        return page

    def create_appearance_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)

        # Floor level
        floor_level_label = QLabel(translations.get("floor_level", "Floor level (pixels from bottom):"))
        floor_level_spin = QSpinBox()
        floor_level_spin.setRange(0, 1000)
        floor_level_spin.setValue(self.duck.ground_level_setting)

        # The size of the pet
        pet_size_label = QLabel(translations.get("pet_size", "Pet size:"))
        pet_size_combo = QComboBox()
        size_options = {1: "x1", 2: "x2", 3: "x3", 5: "x5", 7: "x7", 10: "x10"}
        for size, label_text in size_options.items():
            pet_size_combo.addItem(label_text, size)
        current_size_index = pet_size_combo.findData(self.duck.pet_size)
        if current_size_index != -1:
            pet_size_combo.setCurrentIndex(current_size_index)
        else:
            pet_size_combo.setCurrentIndex(1)  # Average default

        # Buttons "choose a skin" and "select a folder with skins" on one line
        skin_buttons_layout = QHBoxLayout()
        skin_selection_button = QPushButton(translations.get("select_skin_button", "Select skin"))
        skin_folder_button = QPushButton(translations.get("select_skin_folder_button", "Select skin folder"))
        skin_buttons_layout.addWidget(skin_selection_button)
        skin_buttons_layout.addWidget(skin_folder_button)

        skin_selection_button.clicked.connect(self.open_skin_selection)
        skin_folder_button.clicked.connect(self.select_skins_folder)

        # Prevertent of skins
        skins_label = QLabel(translations.get("skins_preview", "Skins preview:"))
        skins_scroll = QScrollArea()
        skins_scroll.setObjectName('skinsScroll')
        skins_scroll.setWidgetResizable(True)
        skins_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)  # Disconnect horizontal scrolling

        skins_container = QWidget()
        skins_container.setStyleSheet("background-color: #121212; border-radius: 10px;")
        skins_grid = QGridLayout(skins_container)
        skins_grid.setSpacing(15)

        # Loading and display of skins from the selected folder
        self.skins_scroll = skins_scroll
        self.skins_container = skins_container
        self.skins_grid = skins_grid
        skins_scroll.setWidget(skins_container)

        # Line with the folder with the skins
        skins_path_label = QLabel(translations.get("skin_folder_path", "Path to the skins folder:") + f" {self.duck.skin_folder if self.duck.skin_folder else 'Not selected'}")
        skins_path_label.setStyleSheet("color: gray; font-size: 12px;")
        skins_path_label.setAlignment(Qt.AlignLeft)
        self.skins_path_label = skins_path_label

        # Buttons
        buttons_layout = QHBoxLayout()
        save_button = QPushButton(translations.get("save_button", "Save"))
        cancel_button = QPushButton(translations.get("cancel_button", "Cancel"))
        buttons_layout.addStretch()
        buttons_layout.addWidget(save_button)
        buttons_layout.addWidget(cancel_button)

        # Connection of buttons to action
        save_button.clicked.connect(lambda: self.save_appearance_settings(
            floor_level_spin.value(),
            pet_size_combo.currentData()
        ))
        cancel_button.clicked.connect(self.close)

        # Adding widgets to the common Layout
        layout.addWidget(floor_level_label)
        layout.addWidget(floor_level_spin)
        layout.addWidget(pet_size_label)
        layout.addWidget(pet_size_combo)
        layout.addLayout(skin_buttons_layout)
        layout.addWidget(skins_label)
        layout.addWidget(skins_scroll)
        layout.addWidget(skins_path_label)
        layout.addStretch()
        layout.addLayout(buttons_layout)

        # Initialize the list of timers within the method
        self.skin_preview_timers = []

        # Loading of skins if the folder is selected
        if self.duck.skin_folder:
            self.load_skins_from_folder(self.duck.skin_folder)

        return page

    def create_advanced_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)

        # Settlement reset button
        reset_button = QPushButton(translations.get("reset_to_default_button", "Reset all settings"))
        reset_button.setObjectName('resetButton')
        reset_button.clicked.connect(self.reset_settings)

        # Buttons
        buttons_layout = QHBoxLayout()
        save_button = QPushButton(translations.get("save_button", "Save"))
        cancel_button = QPushButton(translations.get("cancel_button", "Cancel"))
        buttons_layout.addStretch()
        buttons_layout.addWidget(save_button)
        buttons_layout.addWidget(cancel_button)

        cancel_button.clicked.connect(self.close)

        # Adding widgets to the common Layout
        layout.addWidget(reset_button)
        layout.addStretch()
        layout.addLayout(buttons_layout)

        return page

    def create_about_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)

        # Information about the application
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

        # Support buttons
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

        # Buttons
        buttons_layout = QHBoxLayout()
        save_button = QPushButton(translations.get("save_button", "Save"))
        cancel_button = QPushButton(translations.get("cancel_button", "Cancel"))
        buttons_layout.addStretch()
        buttons_layout.addWidget(save_button)
        buttons_layout.addWidget(cancel_button)

        # Connection of buttons to action
        save_button.clicked.connect(lambda: self.save_about_settings())
        cancel_button.clicked.connect(self.close)

        # Adding widgets to the common Layout
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
            QApplication.instance().beep()  # The sound of the notification has been added
            QMessageBox.information(self, translations.get("characteristics_title", "Characteristics"), info_text)
        else:
            QMessageBox.information(self, translations.get("characteristics_title", "Characteristics"), translations.get("characteristics_text", "Enter a name to see the characteristics."))

    def save_settings(self, pet_name, mic_index, threshold, sound_enabled, autostart_enabled):
        # Update duck settings
        self.duck.pet_name = pet_name
        self.duck.selected_mic_index = mic_index
        self.duck.activation_threshold = threshold
        self.duck.sound_enabled = sound_enabled
        self.duck.autostart_enabled = autostart_enabled

        # Microphone update
        self.duck.microphone_listener.update_settings(
            device_index=mic_index,
            activation_threshold=threshold
        )
        self.duck.restart_microphone_listener()

        # Application of settings
        self.duck.apply_settings()

        # Closing the settings window
        self.close()

    def save_appearance_settings(self, floor_level, pet_size):
        # Updating the floor level and the size of the pet
        self.duck.update_ground_level(floor_level)
        self.duck.update_pet_size(pet_size)

        # Application of settings
        self.duck.apply_settings()

        # Closing the settings window
        self.close()

    def save_advanced_settings(self, direction_change_interval, idle_duration):
        # Update duck settings
        self.duck.direction_change_interval = direction_change_interval
        self.duck.idle_duration = idle_duration

        # Application of settings
        self.duck.apply_settings()

        # Closing the settings window
        self.close()

    def save_about_settings(self):
        self.close()

    def reset_settings(self):
        # Confirmation of the reset of settings
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
                translations.get("select_skin_file", "Save"),
                "",
                "Zip Archives (*.zip);;All Files (*)"
            )
            if filename:
                success = self.duck.resources.load_skin(filename)
                if success:
                    self.duck.selected_skin = filename  # Update the selected skin
                    self.duck.save_settings()  # Save the settings
                    QMessageBox.information(self, translations.get("success", "Success!"), translations.get("skin_loaded_successfully", "Skin uploaded successfully."))
                    self.duck.update_duck_skin()
                else:
                    QMessageBox.warning(self, translations.get("error_title", "Error!"), translations.get("failed_to_load_skin", "Failed to load skin."))
        except Exception as e:
            QMessageBox.critical(self, translations.get("error_title", "Error!"), translations.get("error_while_loading_skin", "There was an error loading the skin:")
 +f" {e}")

    def select_skins_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self,
            translations.get("select_skin_folder", "Select the folder with skins"),
            "",
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )
        if folder:
            self.skins_path_label.setText(translations.get("skin_folder_path", "Path to the skins folder:")
+ f" {folder}")
            self.duck.skin_folder = folder
            self.duck.save_settings()
            self.load_skins_from_folder(folder)

    def load_skins_from_folder(self, folder):
        # Stop all timers
        for timer in self.skin_preview_timers:
            if timer.isActive():
                timer.stop()
        self.skin_preview_timers.clear()

        # Clear the grid layout
        while self.skins_grid.count():
            item = self.skins_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        # Cleaning current skins in a grid
        while self.skins_grid.count():
            item = self.skins_grid.takeAt(0)
            if item.widget():
                widget = item.widget()
                # Stop timers inside the widget, if they are
                for child in widget.findChildren(QLabel):
                    if hasattr(child, 'timer') and child.timer.isActive():
                        child.timer.stop()
                widget.deleteLater()

        row = 0
        col = 0
        max_columns = 3  # Maximum 3 skins in a line

        has_skins = False  # The flag of the presence of skins

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

        if not has_skins:
            QMessageBox.warning(self, translations.get("warning_title", "Warning"), translations.get("no_skins_in_folder", "There are no skins in the selected folder."))

    def display_skin_preview(self, skin_file, idle_frames, row, col):
        animation_label = QLabel()
        animation_label.setStyleSheet("background-color: transparent;")  # Transparent background for Qlabel

        # Setting the size of the card
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
        # Store the timer
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

        # Preservation of the path of the skin
        skin_widget.skin_file = skin_file

        # The use of skin when pressed
        skin_widget.mousePressEvent = lambda event, skin_file=skin_file: self.apply_skin(skin_file)

        self.skins_grid.addWidget(skin_widget, row, col)

    def apply_skin(self, skin_file):
        if not os.path.exists(skin_file):
            QMessageBox.warning(self, translations.get("error_title", "Error!"), translations.get("file_not_found", "File not found: ")+ f" '{skin_file}'")
            return

        success = self.duck.resources.load_skin(skin_file)
        if success:
            self.duck.selected_skin = skin_file
            self.duck.save_settings()  # Save the settings
            QMessageBox.information(
                self,
                translations.get("success", "Success!"),
                translations.get("skin_applied_successfully", "Skin applied successfully:") + f" '{os.path.basename(skin_file)}'"
            )
            self.duck.update_duck_skin()
        else:
            QMessageBox.warning(
                self,
                translations.get("error_title", "Error!"),
                translations.get("failed_apply_skin", "Failed to apply skin:")+ f" '{os.path.basename(skin_file)}'."
            )

    def open_link(self, url):
        webbrowser.open(url)

    def update_mic_preview(self):
        if hasattr(self.duck, 'current_volume') and hasattr(self, 'general_page_widgets'):
            level = self.duck.current_volume
            self.general_page_widgets["mic_level_preview"].setValue(int(level))

def main():
    app = QtWidgets.QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    sys.excepthook = exception_handler
    duck = Duck()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()