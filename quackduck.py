# Standard library imports
import sys
import os
import traceback
import zipfile
import json
import tempfile
import shutil
import webbrowser
import platform
import hashlib
import subprocess
import threading
import time
import random
from pathlib import Path

# Third-party imports
import requests
import numpy as np
from PyQt5 import QtWidgets, QtGui, QtCore
from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtCore import QSettings, pyqtSignal, QThread
import pygame
import pyaudio
import sounddevice as sd

# Global Constants
PROJECT_VERSION = "1.4.0"  # Project version

# Global exception handler
def exception_handler(exctype, value, tb):
    error_message = ''.join(traceback.format_exception(exctype, value, tb))
    crash_log_path = Path(os.path.expanduser('~')) / 'crash.log'

    # Collect system information
    system_info = (
        f"System Information:\n"
        f"OS: {platform.system()} {platform.release()} ({platform.version()})\n"
        f"Machine: {platform.machine()}\n"
        f"Processor: {platform.processor()}\n"
        f"Python Version: {platform.python_version()}\n\n"
    )

    # Write to crash log
    with open(crash_log_path, 'w') as f:
        f.write(system_info)
        f.write(error_message)

    # Show error message to user
    msg = QMessageBox()
    msg.setIcon(QMessageBox.Critical)
    msg.setWindowTitle("Error!")
    msg.setText(f"The application encountered an error:\n{value}")
    msg.setDetailedText(system_info + error_message)
    msg.exec_()
    sys.exit(1)

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

class MicrophoneListener(QThread):
    volume_signal = pyqtSignal(int)

    def __init__(self, input_device_index, mic_sensitivity):
        super().__init__()
        self.input_device_index = input_device_index
        self.mic_sensitivity = mic_sensitivity
        self.running = True

    def run(self):
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
        self.running = False

class FlowLayout(QtWidgets.QLayout):
    def __init__(self, parent=None, margin=0, spacing=-1):
        super(FlowLayout, self).__init__(parent)
        self.itemList = []
        self.setContentsMargins(margin, margin, margin, margin)
        self.setSpacing(spacing if spacing >= 0 else self.spacing())

    def __del__(self):
        while self.count():
            item = self.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

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
        return QtCore.Qt.Orientations(QtCore.Qt.Orientation(0))

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self.doLayout(QtCore.QRect(0, 0, width, 0), True)

    def setGeometry(self, rect):
        super(FlowLayout, self).setGeometry(rect)
        self.doLayout(rect, False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QtCore.QSize()
        for item in self.itemList:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        size += QtCore.QSize(margins.left() + margins.right(), margins.top() + margins.bottom())
        return size

    def doLayout(self, rect, testOnly):
        x = rect.x()
        y = rect.y()
        lineHeight = 0

        for item in self.itemList:
            wid = item.widget()
            spaceX = self.spacing()
            spaceY = self.spacing()
            nextX = x + wid.sizeHint().width() + spaceX
            if nextX - spaceX > rect.right() and lineHeight > 0:
                x = rect.x()
                y = y + lineHeight + spaceY
                nextX = x + wid.sizeHint().width() + spaceX
                lineHeight = 0
            if not testOnly:
                item.setGeometry(QtCore.QRect(QtCore.QPoint(x, y), wid.sizeHint()))
            x = nextX
            lineHeight = max(lineHeight, wid.sizeHint().height())
        return y + lineHeight - rect.y()

class DuckWidget(QtWidgets.QWidget):
    volume_updated = pyqtSignal(int)

    def __init__(self):
        super().__init__()

        # Initializing settings and parameters
        self.settings = QSettings()

        self.setWindowFlags(
            QtCore.Qt.FramelessWindowHint
            | QtCore.Qt.WindowStaysOnTopHint
            | QtCore.Qt.Tool
        )
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))

        self.setAttribute(QtCore.Qt.WA_Hover, True)

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
        self.is_jumping = False

        # Playful state
        self.is_playful = False
        self.playful_timer = None
        self.playful_duration = 0
        self.last_playful_check = time.time()
        self.has_jumped = False

        # Timer to check mouse position
        self.mouse_check_timer = QtCore.QTimer()
        self.mouse_check_timer.timeout.connect(self.check_mouse_over)
        self.mouse_check_timer.start(300)

        # Initializing input devices
        self.input_devices = self.get_input_devices()
        self.load_settings()

        self.current_volume = 0

        # Initialize the stream to listen to the microphone
        self.microphone_listener = MicrophoneListener(self.selected_input_device_index, self.mic_sensitivity)
        self.microphone_listener.volume_signal.connect(self.on_volume_updated)
        self.microphone_listener.start()

        # Define default animation configuration
        self.default_animations_config = {
            "idle": ["0:0"],
            "walk": ["1:0", "1:1", "1:2", "1:3", "1:4", "1:5"],
            "listen": ["2:1"],
            "fall": ["2:3"],
            "jump": ["2:0", "2:1", "2:2", "2:3"],
            "sleep": ["0:1"],
            "sleep_transition": ["2:1"]
        }

        # Load skin or set default animations
        if self.custom_skin_path:
            success = self.load_skin(self.custom_skin_path)
            if not success:
                self.animations_config = self.default_animations_config
                self.load_sprites()
                self.load_sound()
        else:
            self.animations_config = self.default_animations_config
            self.load_sprites()
            self.load_sound()

        # Set current frame
        if hasattr(self, 'fall_frames') and self.fall_frames:
            self.current_frame = self.fall_frames[0]
        elif hasattr(self, 'idle_frames') and self.idle_frames:
            self.current_frame = self.idle_frames[0]
        else:
            raise AttributeError("Failed to initialize animation frames.")

        # Initializing frame indices for animations
        self.frame_index = 0
        self.jump_index = 0
        self.idle_frame_index = 0
        self.sleep_frame_index = 0
        self.listen_frame_index = 0
        self.fall_frame_index = 0
        self.land_frame_index = 0

        # Initialize parameters based on duck name
        if self.duck_name:
            self.seed = get_seed_from_name(self.duck_name)
            self.random_gen = random.Random(self.seed)
            self.generate_parameters()
        else:
            self.seed = None
            self.random_gen = random.Random()
            self.movement_speed = 2
            self.animation_speed = 100
            self.sound_interval = random.randint(120000, 600000) / 1000
            self.sound_response_chance = 0.01
            self.playful_chance = 0.1
            self.sleep_timeout = 300
            self.sound_interval_min = 120
            self.sound_interval_max = 600

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

        # Add a label to display the duck's name
        self.name_label = QtWidgets.QLabel(self.duck_name, self)
        self.name_label.setStyleSheet("""
            QLabel {
                background-color: rgba(0, 0, 0, 180);
                color: white;
                border-radius: 5px;
                padding: 5px;
                font-size: 18px;
            }
        """)
        self.name_label.setAlignment(QtCore.Qt.AlignCenter)
        self.name_label.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.name_label.hide()

        # Set initial opacity to 0
        self.name_label_opacity_effect = QtWidgets.QGraphicsOpacityEffect()
        self.name_label_opacity_effect.setOpacity(0)
        self.name_label.setGraphicsEffect(self.name_label_opacity_effect)

        # Creating an animation for opacity
        self.name_label_animation = QtCore.QPropertyAnimation(self.name_label_opacity_effect, b"opacity")
        self.name_label_animation.setDuration(200)
        self.name_label_animation.finished.connect(self.on_name_label_animation_finished)

        # Enable mouse tracking to receive hover events
        self.setMouseTracking(True)

    def check_mouse_over(self):
        cursor_pos = QtGui.QCursor.pos()
        duck_rect = self.geometry()
        if duck_rect.contains(cursor_pos):
            local_pos = self.mapFromGlobal(cursor_pos)
            x = local_pos.x()
            y = local_pos.y()
            if 0 <= x < self.current_frame.width() and 0 <= y < self.current_frame.height():
                image = self.current_frame_image  # Use cached image
                pixel_color = image.pixelColor(int(x), int(y))
                if pixel_color.alpha() > 0:
                    if not self.name_label.isVisible():
                        label_width = self.name_label.sizeHint().width()
                        # label_height = self.name_label.sizeHint().height()
                        label_x = (self.width() - label_width) / 2
                        label_y = -10
                        self.name_label.move(int(label_x), int(label_y))
                        self.name_label.show()
                        self.name_label.raise_()
                        self.name_label_animation.stop()
                        self.name_label_animation.setStartValue(self.name_label_opacity_effect.opacity())
                        self.name_label_animation.setEndValue(1.0)
                        self.name_label_animation.start()
                    return
        if self.name_label.isVisible():
            self.name_label_animation.stop()
            self.name_label_animation.setStartValue(self.name_label_opacity_effect.opacity())
            self.name_label_animation.setEndValue(0.0)
            self.name_label_animation.start()

    def on_name_label_animation_finished(self):
        if self.name_label_opacity_effect.opacity() == 0.0:
            self.name_label.hide()

    def update_duck_name(self):
        self.name_label.setText(self.duck_name)

    def update_position(self):
        current_time = time.time()

        # Check playfulness status every 10 minutes
        if not self.is_playful and current_time - self.last_playful_check > 600:
            self.last_playful_check = current_time
            if self.random_gen.random() < self.playful_chance:
                self.start_playful_state()

        if self.is_playful:
            if current_time - self.playful_start_time > self.playful_duration:
                self.is_playful = False
                self.has_jumped = False
            else:
                self.chase_cursor()

                # Checking proximity to cursor for jumping
                cursor_x = QtGui.QCursor.pos().x()
                duck_center_x = self.duck_x + self.current_frame.width() / 2
                distance_x = abs(cursor_x - duck_center_x)

                if distance_x < 50 and self.on_ground and not self.has_jumped:
                    self.start_jump()
                    self.has_jumped = True
                elif distance_x >= 100:
                    self.has_jumped = False
        else:
            # Check for sleep mode transition
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
                # Handling a fall
                if self.vertical_speed == 0:
                    self.vertical_speed = 10
                    self.fall_frame_index = 0
                self.vertical_speed += 0.5
                self.duck_y += self.vertical_speed
                if self.duck_y >= self.get_floor_level():
                    self.duck_y = self.get_floor_level()
                    self.on_ground = True
                    self.vertical_speed = 0

                    if self.land_frames:
                        self.is_landing = True
                        self.land_frame_index = 0
                    else:
                        self.landed = True
            elif not self.is_listening and not self.is_sleeping and not self.is_paused and not self.is_jumping and not self.is_landing:
                movement_speed = self.movement_speed
                if self.is_playful:
                    movement_speed *= self.playful_speed_multiplier
                self.duck_x += self.duck_direction * movement_speed

                # Checking screen boundaries
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

        # Jump handling
        if self.is_jumping:
            self.vertical_speed += 0.5
            self.duck_y += self.vertical_speed
            if self.duck_y >= self.get_floor_level():
                self.duck_y = self.get_floor_level()
                self.on_ground = True
                self.is_jumping = False
                self.vertical_speed = 0

                if self.land_frames:
                    self.is_landing = True
                    self.land_frame_index = 0
                else:
                    self.landed = True

        # Duck Position Update
        self.move(int(self.duck_x), int(self.duck_y))

        # Update the position of the name label if it is visible
        if self.name_label.isVisible():
            label_width = self.name_label.sizeHint().width()
            # label_height = self.name_label.sizeHint().height()
            label_x = (self.width() - label_width) / 2
            label_y = -10
            self.name_label.move(int(label_x), int(label_y))
            self.name_label.raise_()

    def get_name_characteristics(self, name):
        seed = get_seed_from_name(name)
        random_gen = random.Random(seed)
        movement_speed = random_gen.uniform(1.5, 2)
        animation_speed = 100 / (movement_speed / 2)
        sound_interval_min = 60 + random_gen.random() * (300 - 60)
        sound_interval_max = 301 + random_gen.random() * (900 - 301)
        if sound_interval_min >= sound_interval_max:
            sound_interval_min, sound_interval_max = sound_interval_max, sound_interval_min
        sound_response_chance = 0.01 + random_gen.random() * (0.25 - 0.01)
        playful_chance = 0.1 + random_gen.random() * (0.5 - 0.1)
        sleep_timeout = (5 + random_gen.random() * 10) * 60

        characteristics = {
            "Movement speed": f"{movement_speed:.2f}",
            "Animation speed": f"{animation_speed:.2f}",
            "Min. sound interval": f"{sound_interval_min/60:.2f} min",
            "Max. sound interval": f"{sound_interval_max/60:.2f} min",
            "Sound response chance": f"{sound_response_chance*100:.2f}%",
            "A chance to be playful": f"{playful_chance*100:.2f}%",
            "Sleep timeout": f"{sleep_timeout/60:.2f} min",
        }

        return characteristics

    def reset_settings_to_default(self):
        # Remove custom skins if any
        skins_dir = os.path.join(os.path.expanduser('~'), '.quackduck_skins')
        if os.path.exists(skins_dir):
            shutil.rmtree(skins_dir)

        # Set default values
        self.mic_sensitivity = 10
        self.floor_level = 40
        self.floor_default = True
        self.scale_factor = 3
        self.sound_enabled = True
        self.selected_input_device_index = self.input_devices[0][0] if self.input_devices else None
        self.autostart_enabled = self.check_autostart()
        self.duck_stuck_bug = True
        self.custom_skin_path = None

        # Remove attributes associated with a custom skin
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

        # Update current wait animation
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
        self.movement_speed = self.random_gen.uniform(1.5, 2)
        self.animation_speed = 100 / (self.movement_speed / 2)
        self.sound_interval_min = 60 + self.random_gen.random() * (300 - 60)
        self.sound_interval_max = 301 + self.random_gen.random() * (900 - 301)
        if self.sound_interval_min >= self.sound_interval_max:
            self.sound_interval_min, self.sound_interval_max = self.sound_interval_max, self.sound_interval_min
        self.sound_response_chance = 0.01 + self.random_gen.random() * (0.25 - 0.01)
        self.playful_chance = 0.1 + self.random_gen.random() * (0.5 - 0.1)
        self.sleep_timeout = (5 + self.random_gen.random() * 10) * 60

    def update_application(self):
        current_version = PROJECT_VERSION
        try:
            url = "https://api.github.com/repos/KristopherZlo/quackduck/releases/latest"
            response = requests.get(url)
            if response.status_code == 200:
                data = response.json()
                latest_version = data['tag_name'].lstrip('v')
                if latest_version > current_version:
                    download_url = None
                    archive_name = None
                    # Search only .zip archives
                    for asset in data['assets']:
                        if asset['name'].endswith('.zip'):
                            download_url = asset['browser_download_url']
                            archive_name = asset['name']
                            break
                    if download_url:
                        # Download the archive
                        temp_archive_path = os.path.join(tempfile.gettempdir(), archive_name)
                        with requests.get(download_url, stream=True) as r:
                            with open(temp_archive_path, 'wb') as f:
                                shutil.copyfileobj(r.raw, f)
                        # Unpack the .zip archive
                        extracted_path = os.path.join(tempfile.gettempdir(), "quackduck_update")
                        if os.path.exists(extracted_path):
                            shutil.rmtree(extracted_path)
                        os.makedirs(extracted_path)
                        with zipfile.ZipFile(temp_archive_path, 'r') as zip_ref:
                            zip_ref.extractall(extracted_path)
                        # Get the path to 'updater.exe'
                        updater_exe_source = resource_path('updater.exe')
                        # Copy 'updater.exe' to extracted_path
                        updater_exe_path = os.path.join(extracted_path, 'updater.exe')
                        shutil.copy2(updater_exe_source, updater_exe_path)
                        # Launch updater and exit
                        subprocess.Popen([updater_exe_path, os.getcwd(), extracted_path])
                        # Inform the user
                        QMessageBox.information(
                            self,
                            "Update",
                            f"The app is being updated to version {latest_version}. It will be restarted after the update is complete.",
                            QMessageBox.Ok
                        )
                        # Exit the application
                        QtWidgets.qApp.quit()
                    else:
                        QMessageBox.information(
                            self,
                            "Update",
                            "There is no .zip archive in the latest release. Please wait for the next update.",
                            QMessageBox.Ok
                        )
                else:
                    QMessageBox.information(
                        self,
                        "Update",
                        "You are using the latest version.",
                        QMessageBox.Ok
                    )
            else:
                QMessageBox.warning(self, "Error", f"Failed to check for updates: HTTP {response.status_code}")
        except Exception as e:
            QMessageBox.warning(
                self,
                "Error",
                f"Failed to update the application: {e}",
                QMessageBox.Ok
            )

    def replace_files(self, extracted_path):
        try:
            # Define paths to files
            app_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
            internal_folder = os.path.join(app_dir, "_internal")
            exe_file = os.path.join(app_dir, "quackduck.exe")
            # Delete old files
            if os.path.exists(internal_folder):
                shutil.rmtree(internal_folder)
            if os.path.exists(exe_file):
                os.remove(exe_file)
            # Copy new files
            new_internal_folder = os.path.join(extracted_path, "_internal")
            new_exe_file = os.path.join(extracted_path, "quackduck.exe")
            if os.path.exists(new_internal_folder):
                shutil.copytree(new_internal_folder, internal_folder)
            else:
                QMessageBox.warning(self, "Error", "New '_internal' folder not found in the archive.")

            if os.path.exists(new_exe_file):
                shutil.copy2(new_exe_file, exe_file)
            else:
                QMessageBox.warning(self, "Error", "New 'quackduck.exe' not found in the archive.")

        except Exception as e:
            QMessageBox.warning(
                self,
                "Error",
                f"Failed to replace files: {e}",
                QMessageBox.Ok
            )

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

        self.settings.beginGroup('Skins')
        self.skins_folder_path = self.settings.value('skins_folder_path', '', type=str) or None
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

        self.settings.beginGroup('Skins')
        self.settings.setValue('skins_folder_path', self.skins_folder_path or '')
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
            # Save current skin settings
            previous_spritesheet_path = self.spritesheet_path if hasattr(self, 'spritesheet_path') else None
            previous_sound_files = self.sound_files if hasattr(self, 'sound_files') else None
            previous_frame_width = self.frame_width if hasattr(self, 'frame_width') else None
            previous_frame_height = self.frame_height if hasattr(self, 'frame_height') else None
            previous_animations_config = self.animations_config if hasattr(self, 'animations_config') else None
            previous_custom_skin_path = self.custom_skin_path if hasattr(self, 'custom_skin_path') else None

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

            # Extract the new skin
            skin_name = os.path.splitext(os.path.basename(zip_path))[0]
            skin_dir = os.path.join(skins_dir, skin_name)

            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(skin_dir)

            # Load configuration
            json_path = os.path.join(skin_dir, 'config.json')
            if not os.path.exists(json_path):
                QtWidgets.QMessageBox.warning(self, "Error", "config.json is missing in the skin.")
                return False

            with open(json_path, 'r') as f:
                config = json.load(f)

            # Read configuration
            spritesheet_name = config.get('spritesheet')
            frame_width = config.get('frame_width')
            frame_height = config.get('frame_height')
            animations = config.get('animations', {})

            if not spritesheet_name or not frame_width or not frame_height:
                QtWidgets.QMessageBox.warning(self, "Error", "Incomplete configuration in config.json.")
                return False

            spritesheet_path = os.path.join(skin_dir, spritesheet_name)
            if not os.path.exists(spritesheet_path):
                QtWidgets.QMessageBox.warning(self, "Error", f"Spritesheet '{spritesheet_name}' not found.")
                return False

            # Load sound files
            sound_names = config.get('sound')
            if not sound_names:
                QtWidgets.QMessageBox.warning(self, "Error", "Sound file(s) not specified in config.json.")
                return False

            if isinstance(sound_names, str):
                sound_names = [sound_names]  # Convert to list if a single file is specified

            sound_paths = []
            for sound_name in sound_names:
                sound_path = os.path.join(skin_dir, sound_name)
                if not os.path.exists(sound_path):
                    QtWidgets.QMessageBox.warning(self, "Error", f"Sound file '{sound_name}' not found.")
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

            # Update current frame
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
            else:
                self.current_frame = self.idle_frames[0]
                self.update()

            return True
        except Exception as e:
            # Restore previous skin settings
            if previous_spritesheet_path is not None:
                self.spritesheet_path = previous_spritesheet_path
                self.sound_files = previous_sound_files
                self.frame_width = previous_frame_width
                self.frame_height = previous_frame_height
                self.animations_config = previous_animations_config
                self.custom_skin_path = previous_custom_skin_path

                # Reload previous sprites and sounds
                self.load_sprites()
                self.load_sound()

                # Update current frame
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
                else:
                    self.current_frame = self.idle_frames[0]
                    self.update()
            else:
                # If previous skin settings are not available, load default skin
                self.custom_skin_path = None
                self.animations_config = self.default_animations_config
                self.load_sprites()
                self.load_sound()
                self.current_frame = self.idle_frames[0]
                self.update()

            QtWidgets.QMessageBox.warning(self, "Error", f"Failed to load skin: {e}")
            print(f"Failed to load skin: {e}")
            return False

    def load_sprites(self):
        if hasattr(self, 'spritesheet_path'):
            spritesheet = QtGui.QPixmap(str(self.spritesheet_path))
            frame_width = self.frame_width
            frame_height = self.frame_height
        else:
            # Standard behavior
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
            raise AttributeError("Failed to initialize animation frames.")

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
        """
        Paint the current frame of the duck onto the widget.
        Ensures that there is a valid frame to draw.
        """
        painter = QtGui.QPainter(self)
        try:
            painter.setRenderHint(QtGui.QPainter.SmoothPixmapTransform, True)
            if self.current_frame:
                painter.drawPixmap(0, 0, self.current_frame)
            else:
                # Do nothing :)
                pass
        except Exception as e:
            print(f"Exception in paintEvent: {e}")
        finally:
            painter.end()


    def update_animation(self):
        """
        Update the duck's animation based on its current state.
        Ensures that animation frames are available before accessing them.
        """
        try:
            if self.is_jumping:
                frames = self.jump_frames
                if frames:
                    if self.jump_index < len(frames):
                        frame = frames[self.jump_index]
                        self.jump_index += 1
                    else:
                        frame = frames[-1]
                    if self.duck_direction < 0:
                        frame = frame.transformed(QtGui.QTransform().scale(-1, 1))
                    self.current_frame = frame
                else:
                    # No jump frames available
                    pass

            elif self.is_landing:
                frames = self.land_frames
                if frames:
                    if self.land_frame_index < len(frames):
                        frame = frames[self.land_frame_index]
                        self.land_frame_index += 1
                    else:
                        self.is_landing = False
                        self.land_frame_index = 0
                        self.landed = True
                        return
                    if self.duck_direction < 0:
                        frame = frame.transformed(QtGui.QTransform().scale(-1, 1))
                    self.current_frame = frame
                else:
                    # No landing frames available
                    self.is_landing = False
                    self.landed = True

            elif not self.on_ground and not self.is_jumping:
                frames = self.fall_frames
                if frames:
                    if self.fall_frame_index < len(frames):
                        frame = frames[self.fall_frame_index]
                        self.fall_frame_index += 1
                    else:
                        frame = frames[-1]
                    if self.duck_direction < 0:
                        frame = frame.transformed(QtGui.QTransform().scale(-1, 1))
                    self.current_frame = frame
                else:
                    # No falling frames available
                    pass

            elif self.is_playful:
                # Accelerate animation speed during playful state
                self.animation_timer.start(int(self.animation_speed / 2))
                frames = self.walk_frames
                if frames:
                    frame = frames[self.frame_index % len(frames)]
                    if self.duck_direction < 0:
                        frame = frame.transformed(QtGui.QTransform().scale(-1, 1))
                    self.current_frame = frame
                    self.frame_index += 1
                else:
                    # No walking frames available
                    pass

            else:
                # Standard animations
                self.animation_timer.start(int(self.animation_speed))
                if self.landed:
                    frames = self.idle_frames
                    if frames:
                        frame = frames[self.idle_frame_index % len(frames)]
                        if self.duck_direction < 0:
                            frame = frame.transformed(QtGui.QTransform().scale(-1, 1))
                        self.current_frame = frame
                        self.landed = False
                        self.idle_frame_index = 0
                    else:
                        # No idle frames available
                        pass

                elif self.is_sleeping:
                    frames = self.sleep_frames
                    if frames:
                        frame = frames[self.sleep_frame_index % len(frames)]
                        self.current_frame = frame
                        self.sleep_frame_index += 1
                    else:
                        # No sleeping frames available
                        pass

                elif self.is_listening:
                    frames = self.listen_frames
                    if frames:
                        frame = frames[self.listen_frame_index % len(frames)]
                        self.current_frame = frame
                        self.listen_frame_index += 1
                    else:
                        # No listening frames available
                        pass

                elif self.is_paused:
                    if not self.current_idle_animation:
                        if self.idle_animations:
                            self.current_idle_animation = random.choice(list(self.idle_animations.values()))
                            self.idle_frame_index = 0
                        else:
                            self.current_idle_animation = []
                    frames = self.current_idle_animation
                    if frames:
                        frame = frames[self.idle_frame_index % len(frames)]
                        if self.duck_direction < 0:
                            frame = frame.transformed(QtGui.QTransform().scale(-1, 1))
                        self.current_frame = frame
                        self.idle_frame_index += 1
                    else:
                        # No current idle animation frames available
                        pass

                else:
                    frames = self.walk_frames
                    if frames:
                        frame = frames[self.frame_index % len(frames)]
                        if self.duck_direction < 0:
                            frame = frame.transformed(QtGui.QTransform().scale(-1, 1))
                        self.current_frame = frame
                        self.frame_index += 1
                    else:
                        # No walking frames available
                        pass

            # Update the cached image for hit detection
            if self.current_frame:
                self.current_frame_image = self.current_frame.toImage()
                self.resize(self.current_frame.size())
                self.update()
        except Exception as e:
            print(f"Exception in update_animation: {e}")

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
        # We select a random time from the interval [X; Y]
        interval = self.random_gen.uniform(self.sound_interval_min, self.sound_interval_max) * 1000  # in milliseconds
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
        
        try:
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
            """)
        except Exception as e:
            print(f"Error applying styles: {e}")

        self.parent = parent

        self.skin_previews = []

        # Main layout
        main_layout = QtWidgets.QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Left navigation (like tabs)
        self.list_widget = QtWidgets.QListWidget()
        self.list_widget.setFixedWidth(150)
        self.list_widget.addItem("General")
        self.list_widget.addItem("Appearance")
        self.list_widget.addItem("Skins")
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
        self.skins_page = QtWidgets.QWidget()
        self.advanced_page = QtWidgets.QWidget()

        # Add pages to stack
        self.stack.addWidget(self.general_page)
        self.stack.addWidget(self.appearance_page)
        self.stack.addWidget(self.skins_page)
        self.stack.addWidget(self.advanced_page)

        # Add to main layout
        main_layout.addWidget(left_panel_widget)
        main_layout.addWidget(self.stack)

        # Initialize pages
        self.init_general_page()
        self.init_appearance_page()
        self.init_skins_page()
        self.init_advanced_page()

        # Set default selection
        self.list_widget.setCurrentRow(0)

        # Start microphone preview thread
        self.preview_thread_running = True
        self.preview_thread = threading.Thread(target=self.mic_preview)
        self.preview_thread.daemon = True
        self.preview_thread.start()

    def init_skins_page(self):
        layout = QtWidgets.QVBoxLayout()
        layout.setAlignment(QtCore.Qt.AlignTop)
        self.skins_page.setLayout(layout)

        # Button to select skins folder
        self.select_skins_folder_button = QtWidgets.QPushButton("Specify Skins Folder")
        self.select_skins_folder_button.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        self.select_skins_folder_button.clicked.connect(self.select_skins_folder)
        self.select_skins_folder_button.setToolTip("Select a folder containing skins")

        # Label to display the selected path
        self.skins_folder_path_label = QtWidgets.QLabel("No folder selected")
        self.skins_folder_path_label.setStyleSheet("font-size: 10pt; color: #888888;")
        self.skins_folder_path_label.setWordWrap(True)

        # Scroll area to display skin previews
        self.skins_scroll_area = QtWidgets.QScrollArea()
        self.skins_scroll_area.setWidgetResizable(True)
        self.skins_scroll_area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)  # Disable horizontal scroll
        self.skins_container = QtWidgets.QWidget()
        # Use FlowLayout instead of GridLayout
        self.skins_layout = FlowLayout()
        self.skins_container.setLayout(self.skins_layout)
        self.skins_scroll_area.setWidget(self.skins_container)

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
        layout.addWidget(self.select_skins_folder_button)
        layout.addWidget(self.skins_folder_path_label)
        layout.addSpacing(10)
        layout.addWidget(self.skins_scroll_area)
        layout.addStretch()
        layout.addLayout(buttons_layout)

        # Load saved skins folder path if available
        if hasattr(self.parent, 'skins_folder_path') and self.parent.skins_folder_path:
            if os.path.exists(self.parent.skins_folder_path):
                self.skins_folder_path = self.parent.skins_folder_path
                self.skins_folder_path_label.setText(f"Skins Folder: {self.skins_folder_path}")
                self.load_skins_from_folder(self.skins_folder_path)
            else:
                # Skins folder does not exist
                self.skins_folder_path = None
                self.skins_folder_path_label.setText("No folder selected")
                QtWidgets.QMessageBox.warning(self, "Skins Folder Missing", "The skins folder was moved or deleted. Please select a new folder.")
        else:
            self.skins_folder_path_label.setText("No folder selected")

    def select_skins_folder(self):
        options = QtWidgets.QFileDialog.Options()
        folder = QtWidgets.QFileDialog.getExistingDirectory(
            self,
            "Select Skins Folder",
            "",
            options=options
        )
        if folder:
            self.skins_folder_path = folder
            self.skins_folder_path_label.setText(f"Skins Folder: {folder}")
            self.load_skins_from_folder(folder)

    def display_skin_preview(self, skin_file, idle_frames):
        """
        Displays a skin preview in the settings interface.

        Args:
            skin_file (str): Path to the skin file (.zip archive).
            idle_frames (List[QPixmap]): List of frames for the idle animation.
        """
        # Create a QLabel to display the animation
        animation_label = QtWidgets.QLabel()
        original_size = 64  # Original skin size (assumed to be 64x64 pixels)
        scale_factor = 2     # Scaling factor (e.g., x2 for 128x128)
        preview_size = original_size * scale_factor
        animation_label.setFixedSize(preview_size, preview_size)
        animation_label.setAlignment(QtCore.Qt.AlignCenter)

        # Set the preview size to keep pixels sharp
        animation_label.setScaledContents(False)

        # Setup animation frames
        frames = idle_frames  # List of QPixmap frames
        frame_count = len(frames)
        if frame_count == 0:
            return  # Exit the method if there are no frames

        # Save the list of frames and the current frame index in QLabel for access in the update function
        animation_label.frames = frames
        animation_label.frame_index = 0

        # Function to update the frame
        def update_frame():
            if frame_count == 0:
                return  # Additional check in case there are no frames
            frame = animation_label.frames[animation_label.frame_index]
            # Scale the QPixmap using FastTransformation to maintain sharp pixels
            scaled_frame = frame.scaled(
                animation_label.size(),
                QtCore.Qt.KeepAspectRatio,
                QtCore.Qt.FastTransformation
            )
            animation_label.setPixmap(scaled_frame)
            # Update the frame index for the next display
            animation_label.frame_index = (animation_label.frame_index + 1) % frame_count

        # Setup a timer for the animation
        timer = QtCore.QTimer()
        timer.timeout.connect(update_frame)
        timer.start(150)  # Frame refresh interval in milliseconds (approximately 6 FPS)
        update_frame()    # Immediately display the first frame

        # Save the timer as an attribute of QLabel to prevent it from being garbage collected
        animation_label.timer = timer

        # Preserve references to prevent garbage collection
        self.skin_previews.append((animation_label, timer))

        # Create a widget to hold the QLabel with the animation
        skin_widget = QtWidgets.QWidget()
        skin_layout = QtWidgets.QVBoxLayout()
        skin_layout.setContentsMargins(0, 0, 0, 0)
        skin_layout.addWidget(animation_label)
        skin_widget.setLayout(skin_layout)
        skin_widget.setFixedSize(preview_size, preview_size)

        # Set tooltip with the skin file name
        skin_name = os.path.basename(skin_file)
        skin_widget.setToolTip(skin_name)

        # Make skin_widget clickable to apply the skin when clicked
        skin_widget.mousePressEvent = lambda event, skin_file=skin_file: self.apply_skin(skin_file)

        # Add skin_widget to FlowLayout to automatically wrap to a new line when necessary
        self.skins_layout.addWidget(skin_widget)

    def load_skins_from_folder(self, folder):
        for animation_label, timer in self.skin_previews:
            timer.stop()
            timer.deleteLater()
            animation_label.deleteLater()
        self.skin_previews.clear()

        # Clear existing previews
        while self.skins_layout.count():
            item = self.skins_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        self.skin_previews = []

        # Find all skin archives in the folder (e.g., .zip files)
        import glob
        import tempfile
        skin_files = glob.glob(os.path.join(folder, "*.zip"))

        # Load and display skins
        self.skin_previews = []  # Keep references to prevent garbage collection
        for skin_file in skin_files:
            # Check if the .zip contains a config.json file
            with zipfile.ZipFile(skin_file, 'r') as zip_ref:
                if 'config.json' in zip_ref.namelist():
                    # Attempt to load the skin's idle animation frames
                    idle_frames = self.load_idle_frames_from_skin(skin_file)
                    if idle_frames:
                        # Proceed to display the skin preview
                        self.display_skin_preview(skin_file, idle_frames)
                else:
                    print(f"Skipped {skin_file}: No config.json found.")

        # Check if any skins were loaded
        if self.skins_layout.count() == 0:
            QtWidgets.QMessageBox.information(self, "No Skins Found", "No valid skins were found in the selected folder.")

    def load_idle_frames_from_skin(self, skin_file):
        import zipfile
        import tempfile
        idle_frames = []
        try:
            with zipfile.ZipFile(skin_file, 'r') as zip_ref:
                # Check for config.json
                if 'config.json' not in zip_ref.namelist():
                    print(f"Skin {skin_file} does not contain config.json.")
                    return None

                # Extract config.json to temporary directory
                temp_dir = os.path.join(tempfile.gettempdir(), 'quackduck_skin_preview', os.path.basename(skin_file))
                os.makedirs(temp_dir, exist_ok=True)
                zip_ref.extract('config.json', temp_dir)

                # Load configuration
                config_path = os.path.join(temp_dir, 'config.json')
                with open(config_path, 'r') as f:
                    config = json.load(f)

                # Read animations configuration
                animations = config.get('animations', {})
                idle_animation_keys = [key for key in animations.keys() if key.startswith('idle')]
                if not idle_animation_keys:
                    print(f"No idle animations found in {skin_file}.")
                    return None

                # For simplicity, we'll use the first idle animation
                idle_animation_key = idle_animation_keys[0]
                frame_list = animations[idle_animation_key]

                # Read spritesheet information
                spritesheet_name = config.get('spritesheet')
                frame_width = config.get('frame_width')
                frame_height = config.get('frame_height')
                if not spritesheet_name or not frame_width or not frame_height:
                    print(f"Incomplete configuration in {skin_file}.")
                    return None

                # Extract spritesheet
                zip_ref.extract(spritesheet_name, temp_dir)
                spritesheet_path = os.path.join(temp_dir, spritesheet_name)

                # Load frames based on the frame_list
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
                            print(f"Incorrect frame format: {frame_str}")
                return frames
        except Exception as e:
            print(f"Failed to load skin {skin_file}: {e}")
            return None
        
    def display_skin_preview(self, skin_file, idle_frames):
        # Create a QLabel to display the animation
        animation_label = QtWidgets.QLabel()
        original_size = 64  # Original skin size (assumed to be 64x64 pixels)
        scale_factor = 2     # Scaling factor (eg x2 for 128x128)
        preview_size = original_size * scale_factor
        animation_label.setFixedSize(preview_size, preview_size)
        animation_label.setAlignment(QtCore.Qt.AlignCenter)

        # Set the preview size to keep pixels sharp
        animation_label.setScaledContents(False)

        # Setting up animation frames
        frames = idle_frames  # List of QPixmap frames
        frame_count = len(frames)
        if frame_count == 0:
            return

        # Save frames and current frame index
        animation_label.frames = frames
        animation_label.frame_index = 0

        # Function to update the frame
        def update_frame():
            frame = animation_label.frames[animation_label.frame_index]
            # Scale the QPixmap using FastTransformation to maintain pixel sharpness
            scaled_frame = frame.scaled(
                animation_label.size(),
                QtCore.Qt.KeepAspectRatio,
                QtCore.Qt.FastTransformation
            )
            animation_label.setPixmap(scaled_frame)
            animation_label.frame_index = (animation_label.frame_index + 1) % frame_count

        # Setting up a timer for animation
        timer = QtCore.QTimer()
        timer.timeout.connect(update_frame)
        timer.start(150)  # Frame refresh interval (in milliseconds)
        update_frame()    # Display the first frame immediately

        # Save the timer so it won't be garbage collected
        animation_label.timer = timer

        # Preserve references to prevent garbage collection
        self.skin_previews.append((animation_label, timer))

        # Create a widget to hold the QLabel
        skin_widget = QtWidgets.QWidget()
        skin_layout = QtWidgets.QVBoxLayout()
        skin_layout.setContentsMargins(0, 0, 0, 0)
        skin_layout.addWidget(animation_label)
        skin_widget.setLayout(skin_layout)
        skin_widget.setFixedSize(preview_size, preview_size)

        # Set tooltip with skin file name
        skin_name = os.path.basename(skin_file)
        skin_widget.setToolTip(skin_name)

        # Make skin_widget clickable to apply skin
        skin_widget.mousePressEvent = lambda event, skin_file=skin_file: self.apply_skin(skin_file)

        # Add skin_widget to FlowLayout to automatically wrap to a new line
        self.skins_layout.addWidget(skin_widget)

    def apply_skin(self, skin_file):
        if not os.path.exists(skin_file):
            QtWidgets.QMessageBox.warning(self, "Error", f"Skin file '{skin_file}' does not exist.")
            # Check if the skins folder still exists
            if os.path.exists(self.skins_folder_path):
                # Refresh the skins list
                self.load_skins_from_folder(self.skins_folder_path)
            else:
                # Skins folder is missing, reset the path and update UI
                self.skins_folder_path = None
                self.skins_folder_path_label.setText("No folder selected")
                QtWidgets.QMessageBox.warning(
                    self,
                    "Skins Folder Missing",
                    "The skins folder was moved or deleted. Please select a new folder."
                )
            return

        success = self.parent.load_skin(skin_file)
        if success:
            self.parent.custom_skin_path = skin_file  # Save the skin path
            QtWidgets.QMessageBox.information(
                self,
                "Success",
                f"Skin '{os.path.basename(skin_file)}' applied successfully."
            )
        else:
            QtWidgets.QMessageBox.warning(
                self,
                "Error",
                f"Failed to apply skin '{os.path.basename(skin_file)}'."
            )

    def display(self, index):
        self.stack.setCurrentIndex(index)

    def init_general_page(self):
        layout = QtWidgets.QVBoxLayout()
        layout.setAlignment(QtCore.Qt.AlignTop)
        self.general_page.setLayout(layout)

        # Pet Name
        pet_name_label = QtWidgets.QLabel("Pet Name:")
        self.duck_name_edit = QtWidgets.QLineEdit()
        self.duck_name_edit.setText(self.parent.duck_name)
        self.duck_name_edit.setPlaceholderText("Enter your pet's name")
        self.duck_name_edit.setClearButtonEnabled(True)
        self.duck_name_edit.setToolTip("Enter your pet's name")

        # Question mark button to display name characteristics
        self.name_info_button = QtWidgets.QPushButton()
        self.name_info_button.setFixedSize(20, 20)
        self.name_info_button.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_MessageBoxQuestion))
        self.name_info_button.setFlat(True)
        self.name_info_button.setStyleSheet("QPushButton { border: none; }")
        self.name_info_button.setToolTip("Enter name to see characteristics")

        # Horizontal layout for name input field and button
        name_layout = QtWidgets.QHBoxLayout()
        name_layout.addWidget(self.duck_name_edit)
        name_layout.addWidget(self.name_info_button)
        name_layout.addStretch()

        self.name_info_button.clicked.connect(self.show_name_characteristics)

        # Update tooltip with characteristics when name is changed
        self.duck_name_edit.textChanged.connect(self.update_name_info_tooltip)
        self.update_name_info_tooltip()

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
        layout.addLayout(name_layout)
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
        size_factors = [1, 2, 3, 5, 7, 10]
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
        <p>Coded with 💜 by zl0yxp</p>
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

    def show_name_characteristics(self):
        name = self.duck_name_edit.text()
        if name:
            characteristics = self.parent.get_name_characteristics(name)
            info_text = "\n".join([f"{key}: {value}" for key, value in characteristics.items()])
            QtWidgets.QMessageBox.information(self, "Characteristics", info_text)
        else:
            QtWidgets.QMessageBox.information(self, "Characteristics", "Enter a name to see the characteristics.")

    def update_name_info_tooltip(self):
        name = self.duck_name_edit.text()
        if name:
            characteristics = self.parent.get_name_characteristics(name)
            tooltip_text = "\n".join([f"{key}: {value}" for key, value in characteristics.items()])
            self.name_info_button.setToolTip(tooltip_text)
        else:
            self.name_info_button.setToolTip("Enter a name to see the characteristics.")

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
        QMessageBox.information(self, "Settings reset", "The settings have been reset to default values.")

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
            "Select skin archive",
            "",
            "Zip Archives (*.zip);;All Files (*)",
            options=options
        )
        if filename:
            success = self.parent.load_skin(filename)
            if success:
                QMessageBox.information(self, "Success", "Skin loaded successfully.")
            else:
                QMessageBox.warning(self, "Error", "Failed to load skin.")

    def save_settings(self):
        """
        Save the settings from the SettingsWindow back to the main DuckWidget.
        This includes microphone settings, appearance settings, behavior settings, and the duck's name.
        """
        try:
            # Save microphone selection
            self.parent.selected_input_device_index = self.mic_combo.currentData()

            # Restart the microphone listener thread with the new settings
            self.parent.microphone_listener.stop()
            self.parent.microphone_listener.wait()
            self.parent.microphone_listener = MicrophoneListener(
                self.parent.selected_input_device_index,
                self.parent.mic_sensitivity
            )
            self.parent.microphone_listener.volume_signal.connect(self.parent.on_volume_updated)
            self.parent.microphone_listener.start()

            # Save microphone sensitivity
            self.parent.mic_sensitivity = self.sensitivity_slider.value()

            # Save skins folder path
            if hasattr(self, 'skins_folder_path'):
                self.parent.skins_folder_path = self.skins_folder_path

            # Save floor level
            if self.floor_default_checkbox.isChecked():
                self.parent.floor_level = 40  # Reset to default
                self.parent.floor_default = True
            else:
                self.parent.floor_level = self.floor_spinbox.value()
                self.parent.floor_default = False

            # Save duck size (scale factor)
            self.parent.scale_factor = self.size_combo.currentData()

            # Apply new skin size by reloading sprites
            old_duck_width = self.parent.current_frame.width()
            old_duck_height = self.parent.current_frame.height()

            self.parent.load_sprites()  # Reload sprites with new scale factor

            new_duck_width = self.parent.current_frame.width()
            new_duck_height = self.parent.current_frame.height()

            # Adjust duck position based on size change and floor level
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

            # Resize and reposition the duck widget
            self.parent.resize(new_duck_width, new_duck_height)
            self.parent.move(int(self.parent.duck_x), int(self.parent.duck_y))
            self.parent.update()

            # Save sound enabled setting
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
            self.parent.update_duck_name()

            # Regenerate parameters if duck name changed
            if self.parent.duck_name:
                self.parent.seed = get_seed_from_name(self.parent.duck_name)
                self.parent.random_gen = random.Random(self.parent.seed)
                self.parent.generate_parameters()
            else:
                # Use default parameters
                self.parent.seed = None
                self.parent.random_gen = random.Random()
                self.parent.movement_speed = 2
                self.parent.animation_speed = 100
                self.parent.sound_interval_min = 120  # Minimum interval in seconds
                self.parent.sound_interval_max = 600  # Maximum interval in seconds
                self.parent.sound_response_chance = 0.01
                self.parent.playful_chance = 0.1
                self.parent.sleep_timeout = 300  # in seconds

            # Reset frame indices to ensure animations start correctly
            self.parent.frame_index = 0
            self.parent.jump_index = 0
            self.parent.idle_frame_index = 0
            self.parent.sleep_frame_index = 0
            self.parent.listen_frame_index = 0
            self.parent.fall_frame_index = 0
            self.parent.land_frame_index = 0

            # Set current_frame to a valid frame
            if self.parent.idle_frames:
                if self.parent.duck_direction < 0:
                    self.parent.current_frame = self.parent.idle_frames[0].transformed(
                        QtGui.QTransform().scale(-1, 1)
                    )
                else:
                    self.parent.current_frame = self.parent.idle_frames[0]
                self.parent.update()
            else:
                # Handle case when idle_frames is empty (optional: set to a default frame or handle gracefully)
                pass

            # Restart animation timer with new animation speed
            self.parent.animation_timer.start(int(self.parent.animation_speed))

            # Save all settings to QSettings
            self.parent.save_settings()

            # Close the settings window
            self.close()

        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self,
                "Error saving settings",
                f"There was an error saving settings:\n{e}",
                QtWidgets.QMessageBox.Ok
            )
            print(f"Exception in save_settings: {e}")

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

    sys.excepthook = exception_handler

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
