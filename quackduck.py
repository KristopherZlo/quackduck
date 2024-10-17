# Standard library imports
import sys
import threading
import time
import random
import os
import traceback
import zipfile
import json
import tempfile
import shutil
import webbrowser
import urllib.request
import platform
import hashlib
import zipfile
import subprocess
import requests
from pathlib import Path

# Third-party imports
import numpy as np
from PyQt5 import QtWidgets, QtGui, QtCore
from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtCore import QSettings, pyqtSignal, QThread
import pygame
import pyaudio
import sounddevice as sd

# Local imports
# (None in this case)

PROJECT_VERSION = "1.4.0"  # Project version

# Global exception handler
def exception_handler(exctype, value, tb):
    error_message = ''.join(traceback.format_exception(exctype, value, tb))
    crash_log_path = Path(os.path.expanduser('~')) / 'crash.log'

    # Collect system information
    system_info = f"System Information:\n" \
                  f"OS: {platform.system()} {platform.release()} ({platform.version()})\n" \
                  f"Machine: {platform.machine()}\n" \
                  f"Processor: {platform.processor()}\n" \
                  f"Python Version: {platform.python_version()}\n\n"

    # Write to crash log
    with open(crash_log_path, 'w') as f:
        f.write(system_info)
        f.write(error_message)

    # Show error message to user
    msg = QMessageBox()
    msg.setIcon(QMessageBox.Critical)
    msg.setWindowTitle("Yikes!")
    msg.setText(f"One of the critters tripped! :(\nError: {value}")
    msg.setDetailedText(system_info + error_message)
    msg.exec_()
    sys.exit(1)

sys.excepthook = exception_handler

def resource_path(relative_path):
    """Get absolute path to resource, works for dev and PyInstaller"""
    base_path = getattr(sys, "_MEIPASS", Path(__file__).resolve().parent)
    return Path(base_path) / relative_path

def get_seed_from_name(name):
    hash_object = hashlib.sha256(name.encode())
    hex_dig = hash_object.hexdigest()
    seed = int(hex_dig, 16) % (2**32)
    return seed

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

        self.image = QtGui.QPixmap(str(resource_path("heart.png"))).scaled(
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
        painter.setOpacity(self.opacity)
        painter.drawPixmap(0, 0, self.image)

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

class MicrophoneListener(QThread):
    # Signal to emit the current volume
    volume_signal = pyqtSignal(int)

    def __init__(self, input_device_index, mic_sensitivity):
        super().__init__()
        self.input_device_index = input_device_index
        self.mic_sensitivity = mic_sensitivity
        self.running = True

    def run(self):
        """Thread entry point."""
        CHUNK = 1024
        RATE = 44100
        p = pyaudio.PyAudio()

        while self.running:
            try:
                stream = p.open(
                    format=pyaudio.paInt16,
                    channels=1,
                    rate=RATE,
                    input=True,
                    input_device_index=self.input_device_index,
                    frames_per_buffer=CHUNK,
                )
            except Exception as e:
                print("Microphone access error:", e)
                time.sleep(1)
                continue

            while self.running:
                data = np.frombuffer(
                    stream.read(CHUNK, exception_on_overflow=False), dtype=np.int16
                )
                volume = np.linalg.norm(data) / CHUNK
                volume = volume * 100  # Increase sensitivity
                volume = min(int((volume / 32768) * 100), 100)  # Normalize volume
                self.volume_signal.emit(volume)
                time.sleep(0.01)

            stream.stop_stream()
            stream.close()

        p.terminate()

    def stop(self):
        """Stop the thread."""
        self.running = False

class DuckWidget(QtWidgets.QWidget):
    # Signal to update the microphone volume
    volume_updated = pyqtSignal(int)

    def __init__(self):
        super().__init__()

        # Initializing QSettings and other parameters
        self.settings = QSettings()

        self.setWindowFlags(
            QtCore.Qt.FramelessWindowHint
            | QtCore.Qt.WindowStaysOnTopHint
            | QtCore.Qt.Tool
        )
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))

        screen = QtWidgets.QApplication.primaryScreen()
        size = screen.size()
        self.screen_width = size.width()
        self.screen_height = size.height()

        self.duck_x = self.screen_width / 2
        self.duck_y = 0

        self.dragging = False
        self.offset_x = 0
        self.offset_y = 0

        self.duck_direction = random.choice([-1, 1])
        self.is_listening = False
        self.last_listen_time = time.time()
        self.is_sleeping = False
        self.last_sound_time = time.time()
        self.on_ground = False
        self.vertical_speed = 10
        self.current_idle_animation = []
        self.is_paused = False
        self.sleep_timer = None
        self.sleep_stage = 0
        self.landed = False
        self.is_stuck = False
        self.is_landing = False

        # Initialize missing attribute
        self.is_jumping = False

        # Playful state
        self.is_playful = False
        self.playful_timer = None
        self.playful_duration = 0  # Will be set when playful state starts
        self.last_playful_check = time.time()
        self.has_jumped = False  # New flag to prevent continuous jumping

        # Loading settings
        self.input_devices = self.get_input_devices()
        self.load_settings()

        self.current_volume = 0  # Current microphone volume level

        # Initialize microphone listener thread
        self.microphone_listener = MicrophoneListener(self.selected_input_device_index, self.mic_sensitivity)
        self.microphone_listener.volume_signal.connect(self.on_volume_updated)
        self.microphone_listener.start()

        # Defining the default animation configuration
        self.default_animations_config = {
            "idle": ["0:0"],
            "walk": ["1:0", "1:1", "1:2", "1:3", "1:4", "1:5"],
            "listen": ["2:1"],
            "fall": ["2:3"],
            "jump": ["2:0", "2:1", "2:2", "2:3"],
            "sleep": ["0:1"],
            "sleep_transition": ["2:1"]
        }

        # Loading a skin or installing default animations
        if self.custom_skin_path:
            success = self.load_skin(self.custom_skin_path)
            if not success:
                # If loading the skin failed, set the default configuration
                self.animations_config = self.default_animations_config
                self.load_sprites()
                self.load_sound()
        else:
            # Setting the default configuration
            self.animations_config = self.default_animations_config
            self.load_sprites()
            self.load_sound()

        # Make sure fall_frames and idle_frames are initialized
        if hasattr(self, 'fall_frames') and self.fall_frames:
            self.current_frame = self.fall_frames[0]
        elif hasattr(self, 'idle_frames') and self.idle_frames:
            self.current_frame = self.idle_frames[0]
        else:
            raise AttributeError("Failed to initialize animation frames.")

        # Initialize frame indices for animations
        self.frame_index = 0  # For walking frames
        self.jump_index = 0  # For jump frames
        self.idle_frame_index = 0  # For idle frames
        self.sleep_frame_index = 0  # For sleep frames
        self.listen_frame_index = 0  # For listening frames
        self.fall_frame_index = 0  # For fall frames
        self.land_frame_index = 0  # For landing frames

        # Initialize random seed and parameters based on duck's name
        if self.duck_name:
            self.seed = get_seed_from_name(self.duck_name)
        else:
            self.seed = None

        if self.seed is not None:
            self.random_gen = random.Random(self.seed)
            self.generate_parameters()
        else:
            self.random_gen = random.Random()
            # Установка значений по умолчанию
            self.movement_speed = 2  # Default movement speed
            self.animation_speed = 100  # Default animation speed
            self.sound_interval = random.randint(120000, 600000) / 1000  # in seconds
            self.sound_response_chance = 0.01  # Default chance to respond to mic
            self.playful_chance = 0.1  # Default chance to become playful
            self.sleep_timeout = 300  # Default sleep timeout in seconds

            # **Добавляем установку sound_interval_min и sound_interval_max**
            self.sound_interval_min = 120  # Минимальный интервал звука в секундах
            self.sound_interval_max = 600  # Максимальный интервал звука в секундах

        # Initializing timers and other components
        self.animation_timer = QtCore.QTimer()
        self.animation_timer.timeout.connect(self.update_animation)
        self.animation_timer.start(int(self.animation_speed))

        self.movement_timer = QtCore.QTimer()
        self.movement_timer.timeout.connect(self.update_position)
        self.movement_timer.start(20)

        self.direction_timer = QtCore.QTimer()
        self.direction_timer.timeout.connect(self.change_direction)
        self.reset_direction_timer()

        self.sound_timer = QtCore.QTimer()
        self.sound_timer.timeout.connect(self.play_sound)
        self.reset_sound_timer()

        self.pause_timer = QtCore.QTimer()
        self.pause_timer.timeout.connect(self.toggle_pause)
        self.reset_pause_timer()

        self.resize(self.current_frame.size())

        self.show()

        self.move(int(self.duck_x), int(self.duck_y))

    def reset_settings_to_default(self):
        # Remove custom skin files if any
        skins_dir = os.path.join(os.path.expanduser('~'), '.quackduck_skins')
        if os.path.exists(skins_dir):
            shutil.rmtree(skins_dir)

        # Установка значений по умолчанию
        self.mic_sensitivity = 10
        self.floor_level = 40
        self.floor_default = True
        self.scale_factor = 3
        self.sound_enabled = True
        self.selected_input_device_index = self.input_devices[0][0] if self.input_devices else None
        self.autostart_enabled = self.check_autostart()
        self.duck_stuck_bug = True
        self.custom_skin_path = None  # Сбросить пользовательскую тему

        # Do not reset duck_name
        # Remove attributes related to custom skin
        if hasattr(self, 'sound_files'):
            del self.sound_files
        if hasattr(self, 'sound_file'):
            del self.sound_file
        if hasattr(self, 'spritesheet_path'):
            del self.spritesheet_path
        if hasattr(self, 'frame_width'):
            del self.frame_width
        if hasattr(self, 'frame_height'):
            del self.frame_height
        if hasattr(self, 'animations_config'):
            del self.animations_config

        # Reset skin to default
        self.animations_config = self.default_animations_config
        self.load_sprites()
        self.load_sound()

        # Update current_idle_animation
        self.current_idle_animation = random.choice(list(self.idle_animations.values()))
        self.idle_frame_index = 0

        if self.duck_direction < 0:
            self.current_frame = self.current_idle_animation[0].transformed(
                QtGui.QTransform().scale(-1, 1)
            )
        else:
            self.current_frame = self.current_idle_animation[0]
        self.update()

        # Save default settings
        self.save_settings()

    def generate_parameters(self):
        # Movement speed between 1.5 and 2.5
        self.movement_speed = self.random_gen.uniform(1.5, 2)

        # Adjust animation speed inversely proportional to movement speed
        self.animation_speed = 100 / (self.movement_speed / 2)

        # Timing for sounds (2 to 15 minutes)
        self.sound_interval_min = 60 + self.random_gen.random() * (300 - 60)  # от 60 до 300 секунд
        self.sound_interval_max = 301 + self.random_gen.random() * (900 - 301)  # от 301 до 900 секунд
        if self.sound_interval_min >= self.sound_interval_max:
            self.sound_interval_min, self.sound_interval_max = self.sound_interval_max, self.sound_interval_min

        # Chance to respond to microphone interaction (0.01 to 0.25)
        self.sound_response_chance = 0.01 + self.random_gen.random() * (0.25 - 0.01)

        # Chance to enter "is_playful" state (0.1 to 0.5)
        self.playful_chance = 0.1 + self.random_gen.random() * (0.5 - 0.1)

        # Timing for sleep (5 to 15 minutes)
        self.sleep_timeout = (5 + self.random_gen.random() * 10) * 60  # in seconds

    def update_application(self):
        # Existing code for updating the application
        pass  # For brevity, omitted here

    def replace_files(self, extracted_path):
        # Existing code for replacing files
        pass  # For brevity, omitted here

    def on_volume_updated(self, volume):
        """Slot to handle volume updates from the microphone listener."""
        self.current_volume = volume
        if volume > self.mic_sensitivity:
            self.is_listening = True
            self.last_sound_time = time.time()

    def closeEvent(self, event):
        """Override the closeEvent to properly terminate threads."""
        self.microphone_listener.stop()
        self.microphone_listener.wait()
        super().closeEvent(event)

    def get_input_devices(self):
        input_devices = []
        seen_devices = set()
        try:
            devices = sd.query_devices()
            for idx, device in enumerate(devices):
                if device["max_input_channels"] > 0:
                    device_name = device["name"]
                    if device_name not in seen_devices:
                        input_devices.append((idx, device_name))
                        seen_devices.add(device_name)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to get input devices: {e}")
            print(f"Failed to get input devices: {e}")
        return input_devices

    def load_settings(self):
        # Load settings or set default values
        self.settings.beginGroup('Audio')
        self.mic_sensitivity = self.settings.value('mic_sensitivity', 10, type=int)
        self.selected_input_device_index = self.settings.value('selected_input_device_index', None, type=int)
        self.settings.endGroup()

        self.settings.beginGroup('Appearance')
        self.floor_level = self.settings.value('floor_level', 40, type=int)
        self.floor_default = self.settings.value('floor_default', True, type=bool)
        self.scale_factor = self.settings.value('scale_factor', 3, type=int)
        self.custom_skin_path = self.settings.value('custom_skin_path', '', type=str) or None
        self.settings.endGroup()

        self.settings.beginGroup('Behavior')
        self.sound_enabled = self.settings.value('sound_enabled', True, type=bool)
        self.autostart_enabled = self.settings.value('autostart_enabled', self.check_autostart(), type=bool)
        self.duck_stuck_bug = self.settings.value('duck_stuck_bug', True, type=bool)
        self.settings.endGroup()

        self.settings.beginGroup('Duck')
        self.duck_name = self.settings.value('duck_name', '', type=str)
        self.settings.endGroup()

        # If no microphone is selected, select the first available one
        if self.selected_input_device_index is None and self.input_devices:
            self.selected_input_device_index = self.input_devices[0][0]

    def save_settings(self):
        # Saving settings
        self.settings.beginGroup('Audio')
        self.settings.setValue('mic_sensitivity', self.mic_sensitivity)
        self.settings.setValue('selected_input_device_index', self.selected_input_device_index)
        self.settings.endGroup()

        self.settings.beginGroup('Appearance')
        self.settings.setValue('floor_level', self.floor_level)
        self.settings.setValue('floor_default', self.floor_default)
        self.settings.setValue('scale_factor', self.scale_factor)
        self.settings.setValue('custom_skin_path', self.custom_skin_path or '')
        self.settings.endGroup()

        self.settings.beginGroup('Behavior')
        self.settings.setValue('sound_enabled', self.sound_enabled)
        self.settings.setValue('autostart_enabled', self.autostart_enabled)
        self.settings.setValue('duck_stuck_bug', self.duck_stuck_bug)
        self.settings.endGroup()

        self.settings.beginGroup('Duck')
        self.settings.setValue('duck_name', self.duck_name)
        self.settings.endGroup()

    def load_skin(self, zip_path):
        try:
            # Define persistent directory for skins
            skins_dir = os.path.join(os.path.expanduser('~'), '.quackduck_skins')
            if not os.path.exists(skins_dir):
                os.makedirs(skins_dir)

            # Before extracting the new skin, delete all existing skins in skins_dir
            for item in os.listdir(skins_dir):
                item_path = os.path.join(skins_dir, item)
                if os.path.isdir(item_path):
                    shutil.rmtree(item_path)
                else:
                    os.remove(item_path)

            # Proceed with extracting the new skin
            skin_name = os.path.splitext(os.path.basename(zip_path))[0]
            skin_dir = os.path.join(skins_dir, skin_name)

            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(skin_dir)

            # Load configuration
            json_path = os.path.join(skin_dir, 'config.json')
            if not os.path.exists(json_path):
                QMessageBox.warning(self, "Error", "Файл config.json отсутствует в скине.")
                return False

            with open(json_path, 'r') as f:
                config = json.load(f)

            # Read configuration
            spritesheet_name = config.get('spritesheet')
            sound_names = config.get('sound')
            frame_width = config.get('frame_width')
            frame_height = config.get('frame_height')
            animations = config.get('animations', {})

            spritesheet_path = os.path.join(skin_dir, spritesheet_name)

            if not os.path.exists(spritesheet_path):
                QMessageBox.warning(self, "Error", f"Файл спрайтов '{spritesheet_name}' не найден.")
                return False

            if not sound_names:
                QMessageBox.warning(self, "Error", "Звуковой файл(ы) не указан.")
                return False

            if isinstance(sound_names, str):
                sound_names = [sound_names]  # Преобразуем в список, если указан один файл

            sound_paths = []
            for sound_name in sound_names:
                sound_path = os.path.join(skin_dir, sound_name)
                if not os.path.exists(sound_path):
                    QMessageBox.warning(self, "Error", f"Звуковой файл '{sound_name}' не найден.")
                    return False
                sound_paths.append(sound_path)

            # Update paths and configurations
            self.spritesheet_path = spritesheet_path
            self.sound_files = sound_paths
            self.frame_width = frame_width
            self.frame_height = frame_height
            self.animations_config = animations

            self.custom_skin_path = zip_path  # Save skin path

            # Reload sprites and sounds
            self.load_sprites()
            self.load_sound()

            # If duck is in idle state, update current_idle_animation
            if self.is_paused:
                self.current_idle_animation = random.choice(list(self.idle_animations.values()))
                self.idle_frame_index = 0

                if self.duck_direction < 0:
                    self.current_frame = self.current_idle_animation[0].transformed(
                        QtGui.QTransform().scale(-1, 1)
                    )
                else:
                    self.current_frame = self.current_idle_animation[0]
                self.update()

            return True
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Не удалось загрузить скин: {e}")
            print(f"Не удалось загрузить скин: {e}")
            return False

    def load_sprites(self):
        if hasattr(self, 'spritesheet_path'):
            spritesheet = QtGui.QPixmap(str(self.spritesheet_path))
            frame_width = self.frame_width
            frame_height = self.frame_height
        else:
            # Стандартное поведение
            spritesheet = QtGui.QPixmap(str(resource_path('ducky_spritesheet.png')))
            frame_width = 32
            frame_height = 32

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

        # Reset all animation attributes
        self.walk_frames = []
        self.idle_frames = []
        self.jump_frames = []
        self.fall_frames = []
        self.land_frames = []
        self.sleep_frames = []
        self.sleep_transition_frames = []
        self.listen_frames = []
        self.idle_animations = {}

        # Load animations based on configuration
        for anim_name, frame_list in self.animations_config.items():
            frames = self.get_animation_frames(get_frame, frame_list)
            if anim_name.startswith('idle'):
                self.idle_animations[anim_name] = frames
            elif anim_name == 'walk':
                self.walk_frames = frames
            elif anim_name == 'listen':
                self.listen_frames = frames
            elif anim_name == 'fall':
                self.fall_frames = frames
            elif anim_name == 'jump':
                self.jump_frames = frames
            elif anim_name == 'land':
                self.land_frames = frames
            elif anim_name == 'sleep':
                self.sleep_frames = frames
            elif anim_name == 'sleep_transition':
                self.sleep_transition_frames = frames
            # Add other animations if necessary

        # For compatibility, set self.idle_frames
        if 'idle' in self.idle_animations:
            self.idle_frames = self.idle_animations['idle']
        else:
            # If idle animation is missing, use the first frame of the spritesheet
            default_frame = get_frame(0, 0)
            self.idle_animations['idle'] = [default_frame]
            self.idle_frames = [default_frame]

        # Set current frame
        if self.fall_frames:
            self.current_frame = self.fall_frames[0]
        elif self.idle_frames:
            self.current_frame = self.idle_frames[0]
        else:
            raise AttributeError("Не удалось инициализировать кадры анимации.")

        # Initialize frame indices for animations
        self.frame_index = 0  # For walking frames
        self.jump_index = 0  # For jump frames
        self.idle_frame_index = 0  # For idle frames
        self.sleep_frame_index = 0  # For sleep frames
        self.listen_frame_index = 0  # For listening frames
        self.fall_frame_index = 0  # For fall frames
        self.land_frame_index = 0  # For landing frames

        # If duck is in idle state, update current_idle_animation
        if self.is_paused:
            self.current_idle_animation = random.choice(list(self.idle_animations.values()))
            self.idle_frame_index = 0

            if self.duck_direction < 0:
                self.current_frame = self.current_idle_animation[0].transformed(
                    QtGui.QTransform().scale(-1, 1)
                )
            else:
                self.current_frame = self.current_idle_animation[0]
            self.update()

    def get_animation_frames(self, get_frame_func, frame_list):
        frames = []
        for frame_str in frame_list:
            row_col = frame_str.split(':')
            if len(row_col) == 2:
                try:
                    row = int(row_col[0])
                    col = int(row_col[1])
                    frames.append(get_frame_func(row, col))
                except ValueError:
                    print(f"Incorrect frame format: {frame_str}")
        return frames

    def load_sound(self):
        pygame.mixer.init()
        if hasattr(self, 'sound_files') and self.sound_files:
            self.sounds = [pygame.mixer.Sound(sound_file) for sound_file in self.sound_files]
        else:
            sound_file_path = str(resource_path("wuak.mp3"))
            self.sounds = [pygame.mixer.Sound(sound_file_path)]

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.SmoothPixmapTransform, True)
        painter.drawPixmap(0, 0, self.current_frame)

    def update_animation(self):
        if self.is_jumping:
            # Play jump animation once
            frames = self.jump_frames
            if self.jump_index < len(frames):
                frame = frames[self.jump_index]
                self.jump_index += 1
            else:
                frame = frames[-1]  # Stay on the last frame until landing
            if self.duck_direction < 0:
                frame = frame.transformed(QtGui.QTransform().scale(-1, 1))
            self.current_frame = frame
        elif self.is_landing:
            # Check if there are LAND animation frames
            if self.land_frames:
                frames = self.land_frames
                if self.land_frame_index < len(frames):
                    frame = frames[self.land_frame_index]
                    self.land_frame_index += 1
                else:
                    # After landing animation ends, reset state
                    self.is_landing = False
                    self.land_frame_index = 0
                    self.landed = True  # Mark that the duck has landed
                    return  # Exit method, next animation will be handled in the next cycle
                if self.duck_direction < 0:
                    frame = frame.transformed(QtGui.QTransform().scale(-1, 1))
                self.current_frame = frame
            else:
                # If no frames, reset landing state
                self.is_landing = False
                self.landed = True
        elif not self.on_ground and not self.is_jumping:
            # Falling animation, play once and stay on the last frame
            frames = self.fall_frames
            if self.fall_frame_index < len(frames):
                frame = frames[self.fall_frame_index]
                self.fall_frame_index += 1
            else:
                frame = frames[-1]  # Stay on the last frame
            if self.duck_direction < 0:
                frame = frame.transformed(QtGui.QTransform().scale(-1, 1))
            self.current_frame = frame
        elif self.is_playful:
            # Running animation in playful state
            animation_speed = self.animation_speed / 2  # Accelerated animation
            self.animation_timer.start(int(animation_speed))
            frames = self.walk_frames
            frame = frames[self.frame_index % len(frames)]
            if self.duck_direction < 0:
                frame = frame.transformed(QtGui.QTransform().scale(-1, 1))
            self.current_frame = frame
            self.frame_index += 1
        else:
            # Standard animations
            animation_speed = self.animation_speed
            self.animation_timer.start(int(animation_speed))

            if self.landed:
                frames = self.idle_frames
                frame = frames[self.idle_frame_index % len(frames)]
                if self.duck_direction < 0:
                    frame = frame.transformed(QtGui.QTransform().scale(-1, 1))
                self.current_frame = frame
                self.landed = False
                self.idle_frame_index = 0
            elif self.is_sleeping:
                frames = self.sleep_frames
                frame = frames[self.sleep_frame_index % len(frames)]
                self.current_frame = frame
                self.sleep_frame_index += 1
            elif self.is_listening:
                frames = self.listen_frames
                frame = frames[self.listen_frame_index % len(frames)]
                self.current_frame = frame
                self.listen_frame_index += 1
            elif self.is_paused:
                # Check if current_idle_animation is initialized
                if not self.current_idle_animation:
                    self.current_idle_animation = random.choice(list(self.idle_animations.values()))
                    self.idle_frame_index = 0

                frames = self.current_idle_animation
                frame = frames[self.idle_frame_index % len(frames)]
                if self.duck_direction < 0:
                    frame = frame.transformed(QtGui.QTransform().scale(-1, 1))
                self.current_frame = frame
                self.idle_frame_index += 1
            else:
                frames = self.walk_frames
                frame = frames[self.frame_index % len(frames)]
                if self.duck_direction < 0:
                    frame = frame.transformed(QtGui.QTransform().scale(-1, 1))
                self.current_frame = frame
                self.frame_index += 1

        self.resize(self.current_frame.size())
        self.update()

    def update_position(self):
        current_time = time.time()

        # Check playful state every 10 minutes
        if not self.is_playful and current_time - self.last_playful_check > 600:
            self.last_playful_check = current_time
            if self.random_gen.random() < self.playful_chance:
                self.start_playful_state()

        if self.is_playful:
            if current_time - self.playful_start_time > self.playful_duration:
                self.is_playful = False
                self.has_jumped = False  # Reset jump flag when exiting playful state
            else:
                self.chase_cursor()

                # Check proximity to cursor for jumping
                cursor_x = QtGui.QCursor.pos().x()
                duck_center_x = self.duck_x + self.current_frame.width() / 2
                distance_x = abs(cursor_x - duck_center_x)

                if distance_x < 50 and self.on_ground and not self.has_jumped:
                    self.start_jump()
                    self.has_jumped = True  # Prevent repeated jumps
                elif distance_x >= 100:
                    self.has_jumped = False
        else:
            # Check for sleep transition
            if current_time - self.last_sound_time > self.sleep_timeout:
                if not self.is_sleeping and self.sleep_timer is None:
                    self.start_sleep_transition()
            else:
                self.is_sleeping = False
                if self.sleep_timer:
                    self.sleep_timer.stop()
                    self.sleep_timer = None
                    self.sleep_stage = 0
                    self.is_paused = False

            # Listening mode
            if self.is_listening:
                if current_time - self.last_sound_time > 1:
                    self.is_listening = False
                    if self.random_gen.random() < self.sound_response_chance:
                        self.play_sound_immediately()

            if self.dragging:
                cursor_pos = QtGui.QCursor.pos()
                self.duck_x = cursor_pos.x() - self.offset_x
                self.duck_y = cursor_pos.y() - self.offset_y
                self.on_ground = False
            elif not self.on_ground and not self.is_jumping:
                # Handle falling
                if self.vertical_speed == 0:
                    self.vertical_speed = 10  # Initial falling speed
                    self.fall_frame_index = 0  # Reset fall frame index
                self.vertical_speed += 0.5
                self.duck_y += self.vertical_speed
                if self.duck_y >= self.get_floor_level():
                    self.duck_y = self.get_floor_level()
                    self.on_ground = True
                    self.vertical_speed = 0

                    # If there is a LAND animation, set landing state
                    if self.land_frames:
                        self.is_landing = True
                        self.land_frame_index = 0
                    else:
                        self.landed = True  # If no LAND animation, enter landed state
            elif not self.is_listening and not self.is_sleeping and not self.is_paused and not self.is_jumping and not self.is_landing:
                movement_speed = self.movement_speed
                if self.is_playful:
                    movement_speed *= self.playful_speed_multiplier  # Increase speed in playful state
                self.duck_x += self.duck_direction * movement_speed

                # Screen edge checking
                if self.duck_x <= 10:
                    if self.duck_stuck_bug:
                        self.is_stuck = False
                        self.duck_direction = 1
                    else:
                        self.is_stuck = True
                        self.duck_x = 0
                        if random.random() < 0.01:
                            self.play_sound_immediately()
                elif self.duck_x >= self.screen_width - self.current_frame.width() - 10:
                    if self.duck_stuck_bug:
                        self.is_stuck = False
                        self.duck_direction = -1
                    else:
                        self.is_stuck = True
                        self.duck_x = self.screen_width - self.current_frame.width()
                        if random.random() < 0.01:
                            self.play_sound_immediately()
                else:
                    self.is_stuck = False

        # Handle jumping
        if self.is_jumping:
            self.vertical_speed += 0.5
            self.duck_y += self.vertical_speed
            if self.duck_y >= self.get_floor_level():
                self.duck_y = self.get_floor_level()
                self.on_ground = True
                self.is_jumping = False  # Reset jumping state
                self.vertical_speed = 0

                # If there is a LAND animation, set landing state
                if self.land_frames:
                    self.is_landing = True
                    self.land_frame_index = 0
                else:
                    self.landed = True  # If no LAND animation, enter landed state

        # Update duck position
        self.move(int(self.duck_x), int(self.duck_y))

    def start_playful_state(self):
        if self.is_sleeping:
            self.is_sleeping = False
            self.last_sound_time = time.time()  # Reset time to prevent immediate sleep
        self.is_playful = True
        self.playful_start_time = time.time()
        self.playful_duration = random.randint(20, 60)  # Duration between 20 and 60 seconds
        self.playful_speed_multiplier = 2  # Speed multiplier for animations and movement
        self.has_jumped = False  # Reset jump flag when entering playful state

        # Ensure duck is on the floor to prevent flying
        self.duck_y = self.get_floor_level()
        self.move(int(self.duck_x), int(self.duck_y))

    def chase_cursor(self):
        cursor_pos = QtGui.QCursor.pos()
        cursor_x = cursor_pos.x()
        duck_center_x = self.duck_x + self.current_frame.width() / 2

        # Determine the direction to move towards the cursor's X-coordinate
        if cursor_x > duck_center_x + 10:
            desired_direction = 1
        elif cursor_x < duck_center_x - 10:
            desired_direction = -1
        else:
            desired_direction = self.duck_direction  # Maintain current direction if within threshold

        # Only change direction if it's different from the current direction
        if desired_direction != self.duck_direction:
            self.duck_direction = desired_direction

        # Move towards the cursor's X-coordinate with doubled speed
        movement_speed = self.movement_speed * self.playful_speed_multiplier
        self.duck_x += self.duck_direction * movement_speed

        # Ensure the duck stays within screen bounds
        self.duck_x = max(0, min(self.duck_x, self.screen_width - self.current_frame.width()))

        # Maintain the duck's Y-coordinate on the floor only if not jumping
        if not self.is_jumping:
            self.duck_y = self.get_floor_level()

        self.move(int(self.duck_x), int(self.duck_y))

    def get_floor_level(self):
        if self.floor_level is not None:
            return self.screen_height - self.current_frame.height() - self.floor_level
        else:
            return self.screen_height - self.current_frame.height() - 40  # Default value

    def start_sleep_transition(self):
        self.is_paused = True
        self.sleep_stage = 1
        self.sleep_timer = QtCore.QTimer()
        self.sleep_timer.timeout.connect(self.update_sleep_transition)
        self.sleep_timer.start(1000)

    def update_sleep_transition(self):
        if self.sleep_stage == 1:
            self.sleep_stage = 2
            self.current_frame = self.sleep_frames[0]
        elif self.sleep_stage == 2:
            self.is_sleeping = True
            self.is_paused = False
            self.sleep_timer.stop()
            self.sleep_timer = None
            self.sleep_stage = 0

    def change_direction(self):
        if self.on_ground and not self.dragging and not self.is_stuck:
            self.duck_direction *= -1
        self.reset_direction_timer()

    def reset_direction_timer(self):
        interval = random.randint(2000, 10000)
        self.direction_timer.start(interval)

    def play_sound(self):
        if not self.is_sleeping and self.sound_enabled and self.sounds:
            sound = random.choice(self.sounds)
            sound.play()
        self.reset_sound_timer()

    def play_sound_immediately(self):
        if not self.is_sleeping and self.sound_enabled and self.sounds:
            sound = random.choice(self.sounds)
            sound.play()

    def reset_sound_timer(self):
        # Выбираем случайное время из интервала [X; Y]
        interval = self.random_gen.uniform(self.sound_interval_min, self.sound_interval_max) * 1000  # в миллисекундах
        self.sound_timer.start(int(interval))

    def toggle_pause(self):
        if not self.is_sleeping and not self.is_listening and not self.dragging:
            self.is_paused = not self.is_paused

            if self.is_paused:
                # Choose a random idle animation
                self.current_idle_animation = random.choice(list(self.idle_animations.values()))
                self.idle_frame_index = 0
                if self.duck_direction < 0:
                    self.current_frame = self.current_idle_animation[0].transformed(
                        QtGui.QTransform().scale(-1, 1)
                    )
                else:
                    self.current_frame = self.current_idle_animation[0]
                self.update()
        self.reset_pause_timer()

    def reset_pause_timer(self):
        if self.is_paused:
            interval = random.randint(5000, 20000)
        else:
            interval = random.randint(5000, 20000)
        self.pause_timer.start(interval)

    # Mouse event handlers
    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            if self.is_playful:
                self.is_playful = False  # Calm the pet
                self.has_jumped = False  # Reset jump flag
            else:
                self.dragging = True
                self.offset_x = event.pos().x()
                self.offset_y = event.pos().y()
                self.is_sleeping = False
                self.last_sound_time = time.time()
                if self.is_jumping:
                    self.is_jumping = False
                    self.vertical_speed = 0  # Reset vertical speed
        elif event.button() == QtCore.Qt.RightButton:
            if self.is_sleeping:
                self.is_sleeping = False
                self.last_sound_time = time.time()  # Reset time to prevent immediate sleep
            self.start_jump()

    def mouseMoveEvent(self, event):
        if self.dragging:
            cursor_pos = QtGui.QCursor.pos()
            self.duck_x = cursor_pos.x() - self.offset_x
            self.duck_y = cursor_pos.y() - self.offset_y
            self.move(int(self.duck_x), int(self.duck_y))

    def mouseReleaseEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self.dragging = False
            self.on_ground = False
            self.vertical_speed = 0  # Reset vertical speed
            self.landed = False

    def mouseDoubleClickEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self.create_heart()

    def start_jump(self):
        if self.on_ground and not self.is_jumping:
            self.is_jumping = True
            self.jump_index = 0
            jump_speed = -10 * self.playful_speed_multiplier if self.is_playful else -10
            self.vertical_speed = jump_speed
            self.on_ground = False

    def create_heart(self):
        heart_x = self.duck_x + self.current_frame.width() / 2
        heart_y = self.duck_y
        self.heart_window = HeartWindow(heart_x, heart_y)

    def open_settings(self):
        self.settings_window = SettingsWindow(self)
        self.settings_window.show()

    def respawn_duck(self):
        self.duck_x = self.screen_width / 2
        self.duck_y = self.get_floor_level()
        self.move(int(self.duck_x), int(self.duck_y))
        self.duck_direction = random.choice([-1, 1])
        self.is_stuck = False

    # Autostart methods for Windows
    def check_autostart(self):
        try:
            import winreg
            reg_key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0, winreg.KEY_READ)
            value, _ = winreg.QueryValueEx(reg_key, "DuckApp")
            winreg.CloseKey(reg_key)
            return True
        except Exception:
            return False

    def enable_autostart(self):
        try:
            import winreg
            exe_path = sys.executable  # Path to the executable
            reg_key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0, winreg.KEY_SET_VALUE)
            winreg.SetValueEx(reg_key, "DuckApp", 0, winreg.REG_SZ, exe_path)
            winreg.CloseKey(reg_key)
            self.autostart_enabled = True
            # Save setting
            self.settings.beginGroup('Behavior')
            self.settings.setValue('autostart_enabled', True)
            self.settings.endGroup()
        except Exception as e:
            print(f"Failed to enable autostart: {e}")

    def disable_autostart(self):
        try:
            import winreg
            reg_key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0, winreg.KEY_SET_VALUE)
            winreg.DeleteValue(reg_key, "DuckApp")
            winreg.CloseKey(reg_key)
            self.autostart_enabled = False
            # Save setting
            self.settings.beginGroup('Behavior')
            self.settings.setValue('autostart_enabled', False)
            self.settings.endGroup()
        except Exception:
            pass

class SystemTrayIcon(QtWidgets.QSystemTrayIcon):
    def __init__(self, icon, window, parent=None):
        super().__init__(icon, parent)
        self.window = window

        menu = QtWidgets.QMenu(parent)
        # Remove cursor stylesheets to avoid warnings
        # menu.setStyleSheet("""
        #     QMenu::item {
        #         cursor: pointer;
        #     }
        # """)

        settings_action = menu.addAction("⚙️ Settings")
        settings_action.triggered.connect(self.open_settings)

        unstuck_action = menu.addAction("🔄 Unstuck")
        unstuck_action.triggered.connect(self.unstuck_duck)

        about_action = menu.addAction("👋 About")
        about_action.triggered.connect(self.show_about)

        # Add 'Check for Updates' option
        check_updates_action = menu.addAction("🔄 Check for Updates")
        check_updates_action.triggered.connect(self.check_for_updates)

        menu.addSeparator()

        show_action = menu.addAction("👀 Show")
        hide_action = menu.addAction("🙈 Hide")

        menu.addSeparator()

        coffee_action = menu.addAction("☕ Buy me a coffee")
        coffee_action.triggered.connect(self.open_coffee_link)

        exit_action = menu.addAction("🚪 Exit")

        menu.addSeparator()

        show_action.triggered.connect(self.show_duck)
        hide_action.triggered.connect(self.hide_duck)
        exit_action.triggered.connect(self.exit_app)

        self.setContextMenu(menu)
        self.activated.connect(self.icon_activated)

    def check_for_updates(self):
        self.window.update_application()

    def open_coffee_link(self):
        webbrowser.open("https://buymeacoffee.com/zl0yxp")

    def open_settings(self):
        self.window.open_settings()

    def unstuck_duck(self):
        self.window.respawn_duck()

    def show_about(self):
        about_text = f"QuackDuck | Version {PROJECT_VERSION}\nCoded with 💜 by zl0yxp\nDiscord: zl0yxp\nTelegram: t.me/quackduckapp"
        QMessageBox.information(
            self.window,
            "About",
            about_text,
            QMessageBox.Ok
        )

    def show_duck(self):
        self.window.show()

    def hide_duck(self):
        self.window.hide()

    def exit_app(self):
        QtWidgets.qApp.quit()

    def icon_activated(self, reason):
        if reason == self.Trigger:
            if self.window.isVisible():
                self.window.hide()
            else:
                self.window.show()

class SettingsWindow(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Settings")
        self.setWindowModality(QtCore.Qt.ApplicationModal)
        self.setFixedSize(600, 500)
        
        # Corrected stylesheet with proper URL formatting
        arrow_down_path = resource_path("icons/arrow_down.png")
        arrow_down_hover_path = resource_path("icons/arrow_down_hover.png")
        self.setStyleSheet(f"""
            QDialog {{
                background-color: #1e1e1e;
                color: #ffffff;
                font-family: 'Segoe UI', sans-serif;
            }}
            QLabel {{
                font-size: 12pt;
            }}
            QLineEdit, QComboBox, QSpinBox {{
                background-color: #2d2d2d;
                border: 1px solid #3c3c3c;
                padding: 6px;
                border-radius: 4px;
                font-size: 10pt;
                color: #ffffff;
            }}
            QLineEdit:focus, QComboBox:focus, QSpinBox:focus {{
                border: 1px solid #0078d7;
            }}
            QPushButton {{
                background-color: #2d2d2d;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-size: 10pt;
                color: #ffffff;
            }}
            QPushButton:hover {{
                background-color: #3e3e40;
            }}
            QPushButton:pressed {{
                background-color: #0078d7;
            }}
            QCheckBox {{
                padding: 4px;
                font-size: 10pt;
            }}
            QListWidget {{
                background-color: #2d2d2d;
                border-right: 1px solid #3c3c3c;
                font-size: 10pt;
                outline: 0;
            }}
            QListWidget::item {{
                padding: 10px;
                color: #ffffff;
            }}
            QListWidget::item:selected {{
                background-color: #0078d7;
                color: #ffffff;
            }}
            QListWidget::item:hover {{
                background-color: #3e3e40;
            }}
            QStackedWidget {{
                background-color: #1e1e1e;
            }}
            QSlider::groove:horizontal {{
                height: 6px;
                background: #3c3c3c;
                border-radius: 3px;
            }}
            QSlider::handle:horizontal {{
                background: #0078d7;
                width: 14px;
                margin: -4px 0;
                border-radius: 7px;
            }}
            QProgressBar {{
                text-align: center;
                border: 1px solid #3c3c3c;
                border-radius: 4px;
                background-color: #2d2d2d;
            }}
            QProgressBar::chunk {{
                background-color: #0078d7;
                border-radius: 4px;
            }}
            QScrollArea {{
                border: none;
            }}
            /* Style arrows in QComboBox and QSpinBox */
            QComboBox::drop-down, QSpinBox::up-button, QSpinBox::down-button {{
                background: transparent;
                border: none;
                width: 20px;
            }}
            QComboBox::down-arrow, QSpinBox::up-arrow, QSpinBox::down-arrow {{
                image: url('file:///{os.path.abspath(arrow_down_path).replace(os.sep, "/")}');
                width: 12px;
                height: 12px;
            }}
            QComboBox::down-arrow:hover, QSpinBox::up-arrow:hover, QSpinBox::down-arrow:hover {{
                image: url('file:///{os.path.abspath(arrow_down_hover_path).replace(os.sep, "/")}');
            }}
        """)

        self.parent = parent

        # Main layout
        main_layout = QtWidgets.QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Left navigation (like tabs)
        self.list_widget = QtWidgets.QListWidget()
        self.list_widget.setFixedWidth(150)
        self.list_widget.addItem("General")
        self.list_widget.addItem("Appearance")
        self.list_widget.addItem("Advanced")
        self.list_widget.currentRowChanged.connect(self.display)

        # Version label at bottom of left panel
        version_label = QtWidgets.QLabel(f"Version {PROJECT_VERSION}")
        version_label.setAlignment(QtCore.Qt.AlignCenter)
        version_label.setStyleSheet("font-size: 10pt; color: #555555;")
        version_label.setFixedHeight(30)

        # Left panel layout
        left_panel_layout = QtWidgets.QVBoxLayout()
        left_panel_layout.setContentsMargins(0, 0, 0, 0)
        left_panel_layout.addWidget(self.list_widget)
        # Removed left_panel_layout.addStretch()
        left_panel_layout.addWidget(version_label)

        # Left panel widget
        left_panel_widget = QtWidgets.QWidget()
        left_panel_widget.setLayout(left_panel_layout)
        left_panel_widget.setFixedWidth(150)

        # Stack for pages
        self.stack = QtWidgets.QStackedWidget(self)

        # Pages
        self.general_page = QtWidgets.QWidget()
        self.appearance_page = QtWidgets.QWidget()
        self.advanced_page = QtWidgets.QWidget()

        # Add pages to stack
        self.stack.addWidget(self.general_page)
        self.stack.addWidget(self.appearance_page)
        self.stack.addWidget(self.advanced_page)

        # Add to main layout
        main_layout.addWidget(left_panel_widget)
        main_layout.addWidget(self.stack)

        # Initialize pages
        self.init_general_page()
        self.init_appearance_page()
        self.init_advanced_page()

        # Set default selection
        self.list_widget.setCurrentRow(0)

        # Start microphone preview thread
        self.preview_thread_running = True
        self.preview_thread = threading.Thread(target=self.mic_preview)
        self.preview_thread.daemon = True
        self.preview_thread.start()

    def display(self, index):
        self.stack.setCurrentIndex(index)

    def init_general_page(self):
        layout = QtWidgets.QVBoxLayout()
        layout.setAlignment(QtCore.Qt.AlignTop)
        self.general_page.setLayout(layout)

        # Pet Name
        pet_name_label = QtWidgets.QLabel("Pet Name:")
        self.duck_name_edit = QtWidgets.QLineEdit()  # Changed back to 'duck_name_edit'
        self.duck_name_edit.setText(self.parent.duck_name)
        self.duck_name_edit.setPlaceholderText("Enter your pet's name")
        self.duck_name_edit.setClearButtonEnabled(True)
        self.duck_name_edit.setToolTip("Enter your pet's name")

        # Microphone selection
        mic_label = QtWidgets.QLabel("Select Microphone:")
        self.mic_combo = QtWidgets.QComboBox()
        self.populate_microphones()
        self.mic_combo.setToolTip("Select a microphone for sound detection")

        # Microphone sensitivity
        sensitivity_label = QtWidgets.QLabel("Microphone Sensitivity:")
        self.sensitivity_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.sensitivity_slider.setMinimum(1)
        self.sensitivity_slider.setMaximum(100)
        self.sensitivity_slider.setValue(self.parent.mic_sensitivity)
        self.sensitivity_slider.valueChanged.connect(self.update_sensitivity_label)
        self.sensitivity_label_value = QtWidgets.QLabel(f"{self.parent.mic_sensitivity}")
        self.sensitivity_label_value.setFixedWidth(30)

        sensitivity_layout = QtWidgets.QHBoxLayout()
        sensitivity_layout.addWidget(self.sensitivity_slider)
        sensitivity_layout.addWidget(self.sensitivity_label_value)

        # Microphone volume preview
        mic_preview_label = QtWidgets.QLabel("Microphone Level:")
        self.sensitivity_preview = QtWidgets.QProgressBar()
        self.sensitivity_preview.setMaximum(100)
        self.sensitivity_preview.setTextVisible(False)
        self.sensitivity_preview.setFixedHeight(10)

        # Sound enable/disable
        self.sound_checkbox = QtWidgets.QCheckBox("Enable Sounds")
        self.sound_checkbox.setChecked(self.parent.sound_enabled)
        self.sound_checkbox.setToolTip("Enable or disable pet sounds")

        # Autostart
        self.autostart_checkbox = QtWidgets.QCheckBox("Run at System Startup")
        self.autostart_checkbox.setChecked(self.parent.autostart_enabled)
        self.autostart_checkbox.setToolTip("Automatically run the application at system startup")

        # Disable 'Stuck Bug' Checkbox (Moved to General)
        self.duck_stuck_checkbox = QtWidgets.QCheckBox("Disable 'Stuck Bug'")
        self.duck_stuck_checkbox.setChecked(self.parent.duck_stuck_bug)
        self.duck_stuck_checkbox.setToolTip("Disable the pet's ability to get 'stuck' at screen edges")

        # Save and Cancel buttons
        buttons_layout = QtWidgets.QHBoxLayout()
        buttons_layout.setAlignment(QtCore.Qt.AlignRight)
        save_button = QtWidgets.QPushButton("Save")
        save_button.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        save_button.clicked.connect(self.save_settings)
        save_button.setToolTip("Save changes")
        cancel_button = QtWidgets.QPushButton("Cancel")
        cancel_button.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        cancel_button.clicked.connect(self.close)
        cancel_button.setToolTip("Discard changes")
        buttons_layout.addWidget(save_button)
        buttons_layout.addWidget(cancel_button)

        # Add widgets to layout
        layout.addWidget(pet_name_label)
        layout.addWidget(self.duck_name_edit)
        layout.addSpacing(10)
        layout.addWidget(mic_label)
        layout.addWidget(self.mic_combo)
        layout.addSpacing(10)
        layout.addWidget(sensitivity_label)
        layout.addLayout(sensitivity_layout)
        layout.addWidget(mic_preview_label)
        layout.addWidget(self.sensitivity_preview)
        layout.addSpacing(10)
        layout.addWidget(self.sound_checkbox)
        layout.addWidget(self.autostart_checkbox)
        layout.addWidget(self.duck_stuck_checkbox)
        layout.addStretch()
        layout.addLayout(buttons_layout)

    def init_appearance_page(self):
        layout = QtWidgets.QVBoxLayout()
        layout.setAlignment(QtCore.Qt.AlignTop)
        self.appearance_page.setLayout(layout)

        # Floor level
        floor_label = QtWidgets.QLabel("Floor Level (pixels from bottom):")
        floor_layout = QtWidgets.QHBoxLayout()
        self.floor_spinbox = QtWidgets.QSpinBox()
        self.floor_spinbox.setRange(0, self.parent.screen_height)
        self.floor_spinbox.setValue(self.parent.floor_level)
        self.floor_spinbox.setToolTip("Set the distance from the bottom of the screen to the pet's floor")
        self.floor_default_checkbox = QtWidgets.QCheckBox("Default")
        self.floor_default_checkbox.setChecked(self.parent.floor_default)
        self.floor_default_checkbox.stateChanged.connect(self.toggle_floor_default)
        self.floor_default_checkbox.setToolTip("Use default floor level")
        self.floor_spinbox.setDisabled(self.parent.floor_default)
        floor_layout.addWidget(self.floor_spinbox)
        floor_layout.addWidget(self.floor_default_checkbox)

        # Pet size
        size_label = QtWidgets.QLabel("Pet Size:")
        self.size_combo = QtWidgets.QComboBox()
        size_factors = [1, 2, 3, 5, 10]
        for factor in size_factors:
            self.size_combo.addItem(f"x{factor}", factor)
        index = self.size_combo.findData(self.parent.scale_factor)
        if index != -1:
            self.size_combo.setCurrentIndex(index)
        self.size_combo.setToolTip("Select the pet's size scale")

        # Skin Customization Button
        self.skin_button = QtWidgets.QPushButton("Select Skin")
        self.skin_button.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        self.skin_button.clicked.connect(self.open_skin_customization)
        self.skin_button.setToolTip("Choose a custom skin for the pet")

        # Save and Cancel buttons
        buttons_layout = QtWidgets.QHBoxLayout()
        buttons_layout.setAlignment(QtCore.Qt.AlignRight)
        save_button = QtWidgets.QPushButton("Save")
        save_button.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        save_button.clicked.connect(self.save_settings)
        save_button.setToolTip("Save changes")
        cancel_button = QtWidgets.QPushButton("Cancel")
        cancel_button.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        cancel_button.clicked.connect(self.close)
        cancel_button.setToolTip("Discard changes")
        buttons_layout.addWidget(save_button)
        buttons_layout.addWidget(cancel_button)

        # Add widgets to layout
        layout.addWidget(floor_label)
        layout.addLayout(floor_layout)
        layout.addSpacing(10)
        layout.addWidget(size_label)
        layout.addWidget(self.size_combo)
        layout.addSpacing(10)
        layout.addWidget(self.skin_button)
        layout.addStretch()
        layout.addLayout(buttons_layout)

    def init_advanced_page(self):
        layout = QtWidgets.QVBoxLayout()
        layout.setAlignment(QtCore.Qt.AlignTop)
        self.advanced_page.setLayout(layout)

        # About text
        about_text = f"""
        <h2>QuackDuck | Version {PROJECT_VERSION}</h2>
        <p>Coded with ❤ by zl0yxp</p>
        <p>Discord: zl0yxp</p>
        """
        about_label = QtWidgets.QLabel(about_text)
        about_label.setOpenExternalLinks(True)
        about_label.setTextFormat(QtCore.Qt.RichText)
        about_label.setAlignment(QtCore.Qt.AlignLeft)
        about_label.setStyleSheet("font-size: 10pt;")

        # Buttons
        buttons_layout = QtWidgets.QHBoxLayout()
        coffee_button = QtWidgets.QPushButton("Buy me a coffee ☕")
        coffee_button.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        coffee_button.clicked.connect(self.open_coffee_link)
        coffee_button.setToolTip("Support the developer")

        telegram_button = QtWidgets.QPushButton("Telegram")
        telegram_button.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        telegram_button.clicked.connect(self.open_telegram_link)
        telegram_button.setToolTip("Go to Telegram channel")

        github_button = QtWidgets.QPushButton("GitHub")
        github_button.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        github_button.clicked.connect(self.open_github_link)
        github_button.setToolTip("Go to GitHub repository")

        buttons_layout.addWidget(coffee_button)
        buttons_layout.addWidget(telegram_button)
        buttons_layout.addWidget(github_button)

        # Reset settings button
        reset_button = QtWidgets.QPushButton("Reset Settings")
        reset_button.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        reset_button.clicked.connect(self.reset_to_default)
        reset_button.setToolTip("Reset settings to default values")

        # Save and Cancel buttons
        save_cancel_layout = QtWidgets.QHBoxLayout()
        save_cancel_layout.setAlignment(QtCore.Qt.AlignRight)
        save_button = QtWidgets.QPushButton("Save")
        save_button.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        save_button.clicked.connect(self.save_settings)
        save_button.setToolTip("Save changes")
        cancel_button = QtWidgets.QPushButton("Cancel")
        cancel_button.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        cancel_button.clicked.connect(self.close)
        cancel_button.setToolTip("Discard changes")
        save_cancel_layout.addWidget(save_button)
        save_cancel_layout.addWidget(cancel_button)

        # Add widgets to layout
        layout.addWidget(about_label)
        layout.addSpacing(10)
        layout.addLayout(buttons_layout)
        layout.addSpacing(10)
        layout.addWidget(reset_button)
        layout.addStretch()
        layout.addLayout(save_cancel_layout)

    def reset_to_default(self):
        # Reset settings in the parent widget
        self.parent.reset_settings_to_default()

        # Update UI elements to reflect default values
        self.populate_microphones()
        self.sensitivity_slider.setValue(self.parent.mic_sensitivity)
        self.floor_spinbox.setValue(self.parent.floor_level)
        self.floor_default_checkbox.setChecked(self.parent.floor_default)
        self.floor_spinbox.setDisabled(self.parent.floor_default)
        self.size_combo.setCurrentIndex(self.size_combo.findData(self.parent.scale_factor))
        self.sound_checkbox.setChecked(self.parent.sound_enabled)
        self.autostart_checkbox.setChecked(self.parent.autostart_enabled)
        self.duck_stuck_checkbox.setChecked(self.parent.duck_stuck_bug)
        self.duck_name_edit.setText(self.parent.duck_name)

        # Optionally, show a message about the reset
        QMessageBox.information(self, "Настройки сброшены", "Настройки были сброшены до значений по умолчанию.")

    def closeEvent(self, event):
        self.preview_thread_running = False
        event.accept()

    def populate_microphones(self):
        self.mic_combo.clear()
        for index, name in self.parent.input_devices:
            self.mic_combo.addItem(name, index)
        current_index = self.mic_combo.findData(self.parent.selected_input_device_index)
        if current_index != -1:
            self.mic_combo.setCurrentIndex(current_index)

    def toggle_floor_default(self, state):
        self.floor_spinbox.setDisabled(state == QtCore.Qt.Checked)

    def update_sensitivity_label(self, value):
        self.sensitivity_label_value.setText(str(value))

    def mic_preview(self):
        while self.preview_thread_running:
            volume = self.parent.current_volume
            if volume is not None:
                volume = min(volume, 100)
                self.sensitivity_preview.setValue(int(volume))
            time.sleep(0.1)

    def open_coffee_link(self):
        webbrowser.open("https://buymeacoffee.com/zl0yxp")

    def open_telegram_link(self):
        webbrowser.open("https://t.me/quackduckapp")

    def open_github_link(self):
        webbrowser.open("https://github.com/KristopherZlo/quackduck")

    def open_skin_customization(self):
        options = QtWidgets.QFileDialog.Options()
        filename, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Выберите архив скина",
            "",
            "Zip Archives (*.zip);;All Files (*)",
            options=options
        )
        if filename:
            success = self.parent.load_skin(filename)
            if success:
                QMessageBox.information(self, "Успех", "Скин успешно загружен.")
            else:
                QMessageBox.warning(self, "Ошибка", "Не удалось загрузить скин.")

    def save_settings(self):
        # Save microphone selection
        self.parent.selected_input_device_index = self.mic_combo.currentData()
        # Restart the microphone listener thread
        self.parent.microphone_listener.stop()
        self.parent.microphone_listener.wait()
        self.parent.microphone_listener = MicrophoneListener(self.parent.selected_input_device_index, self.parent.mic_sensitivity)
        self.parent.microphone_listener.volume_signal.connect(self.parent.on_volume_updated)
        self.parent.microphone_listener.start()

        # Save microphone sensitivity
        self.parent.mic_sensitivity = self.sensitivity_slider.value()

        # Save floor level
        if self.floor_default_checkbox.isChecked():
            self.parent.floor_level = 40  # Reset to default
            self.parent.floor_default = True
        else:
            self.parent.floor_level = self.floor_spinbox.value()
            self.parent.floor_default = False

        # Save duck size
        self.parent.scale_factor = self.size_combo.currentData()
        old_duck_width = self.parent.current_frame.width()
        old_duck_height = self.parent.current_frame.height()

        self.parent.load_sprites()  # Reload sprites with new size

        new_duck_width = self.parent.current_frame.width()
        new_duck_height = self.parent.current_frame.height()

        # Adjust duck position based on size and floor level
        height_difference = new_duck_height - old_duck_height
        self.parent.duck_y -= height_difference

        desired_floor_y = self.parent.get_floor_level()
        self.parent.duck_y = desired_floor_y

        # Ensure duck stays within screen bounds
        if self.parent.duck_y + new_duck_height > self.parent.screen_height:
            self.parent.duck_y = self.parent.screen_height - new_duck_height
        if self.parent.duck_y < 0:
            self.parent.duck_y = 0

        if self.parent.duck_x + new_duck_width > self.parent.screen_width:
            self.parent.duck_x = self.parent.screen_width - new_duck_width
        if self.parent.duck_x < 0:
            self.parent.duck_x = 0

        self.parent.resize(new_duck_width, new_duck_height)
        self.parent.move(int(self.parent.duck_x), int(self.parent.duck_y))
        self.parent.update()

        # Save sound setting
        self.parent.sound_enabled = self.sound_checkbox.isChecked()

        # Save autostart setting
        if self.autostart_checkbox.isChecked():
            self.parent.enable_autostart()
        else:
            self.parent.disable_autostart()

        # Save Duck Stuck Bug setting
        self.parent.duck_stuck_bug = self.duck_stuck_checkbox.isChecked()

        # Save duck name
        self.parent.duck_name = self.duck_name_edit.text()

        # Regenerate parameters if duck name changed
        if self.parent.duck_name:
            self.parent.seed = get_seed_from_name(self.parent.duck_name)
            self.parent.random_gen = random.Random(self.parent.seed)
            self.parent.generate_parameters()
        else:
            # Use default parameters
            self.parent.random_gen = random.Random()
            self.parent.movement_speed = 2
            self.parent.animation_speed = 100
            self.parent.sound_interval = random.randint(120000, 600000) / 1000  # in seconds
            self.parent.sound_response_chance = 0.01
            self.parent.playful_chance = 0.1
            self.parent.sleep_timeout = 300  # in seconds

        # Restart animation timer with new animation speed
        self.parent.animation_timer.start(int(self.parent.animation_speed))

        # Save settings to QSettings
        self.parent.save_settings()

        self.close()

def main():
    # Initialize application
    app = QtWidgets.QApplication(sys.argv)

    # Set organization and application names for QSettings
    app.setOrganizationName("zl0yxp")
    app.setApplicationName("QuackDuck")

    # Apply dark theme
    app.setStyle("Fusion")
    dark_palette = QtGui.QPalette()
    dark_palette.setColor(QtGui.QPalette.Window, QtGui.QColor(45, 45, 48))
    dark_palette.setColor(QtGui.QPalette.WindowText, QtCore.Qt.white)
    dark_palette.setColor(QtGui.QPalette.Base, QtGui.QColor(37, 37, 38))
    dark_palette.setColor(QtGui.QPalette.AlternateBase, QtGui.QColor(45, 45, 48))
    dark_palette.setColor(QtGui.QPalette.ToolTipBase, QtCore.Qt.white)
    dark_palette.setColor(QtGui.QPalette.ToolTipText, QtCore.Qt.white)
    dark_palette.setColor(QtGui.QPalette.Text, QtCore.Qt.white)
    dark_palette.setColor(QtGui.QPalette.Button, QtGui.QColor(45, 45, 48))
    dark_palette.setColor(QtGui.QPalette.ButtonText, QtCore.Qt.white)
    dark_palette.setColor(QtGui.QPalette.BrightText, QtCore.Qt.red)
    dark_palette.setColor(QtGui.QPalette.Highlight, QtGui.QColor(0, 120, 215))
    dark_palette.setColor(QtGui.QPalette.HighlightedText, QtCore.Qt.black)
    app.setPalette(dark_palette)

    try:
        icon_path = resource_path("duck_icon.png")
        app.setWindowIcon(QtGui.QIcon(str(icon_path)))

        duck_widget = DuckWidget()

        tray_icon = SystemTrayIcon(QtGui.QIcon(str(icon_path)), duck_widget)
        tray_icon.show()

        duck_widget.show()

        sys.exit(app.exec_())

    except Exception as e:
        exception_handler(type(e), e, e.__traceback__)

if __name__ == "__main__":
    main()
