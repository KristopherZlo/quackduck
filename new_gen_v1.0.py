# -*- coding: utf-8 -*-
"""
Полный код на PyQt6:
 - Добавлен PlayfulState (курсором "дразним" утку).
 - JumpingState не зависает (логика падения и перехода в LandingState).
 - При двойном клике на утку появляется сердечко (HeartWindow).
 - Отображается имя утки (NameWindow).
"""

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
import requests
import base64
import io

if sys.platform == 'win32':
    import winreg
    import win32api
    import win32con
    import win32gui
    import win32process

from abc import ABC, abstractmethod
from autoupdater import AutoUpdater, UpdateWindow
from typing import Dict, List, Optional, Tuple

from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtCore import (
    QPoint, QRect, QSize, Qt, QTimer, QUrl, QBuffer, QIODevice
)
from PyQt6.QtGui import (
    QColor, QDesktopServices, QFont, QIcon, QMouseEvent, QPixmap, QMovie, QCursor, QTransform
)
from PyQt6.QtMultimedia import QSoundEffect, QMediaPlayer, QAudioOutput
from PyQt6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QFileDialog,
    QFrame, QFormLayout, QGridLayout, QGroupBox, QHBoxLayout, QLabel,
    QLayout, QLineEdit, QListWidget, QMainWindow, QMessageBox,
    QPushButton, QProgressBar, QScrollArea, QSlider, QSpinBox, QStackedWidget,
    QTabWidget, QTextEdit, QVBoxLayout, QWidget, QSizePolicy, QSpacerItem, QDoubleSpinBox
)

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s %(levelname)s:%(message)s',
    handlers=[
        logging.FileHandler(os.path.join(os.path.expanduser('~'), 'quackduck.log'), encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

PROJECT_VERSION = '1.5.2'
GLOBAL_DEBUG_MODE = True
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

def resource_path(relative_path: str) -> str:
    try:
        if getattr(sys, 'frozen', False):
            base_path = os.path.dirname(sys.executable)
        else:
            base_path = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(base_path, relative_path)
    except Exception as e:
        logging.error(f"Error with path {relative_path}: {e}")
        return relative_path

def load_translation(lang_code: str) -> dict:
    try:
        lang_path = resource_path(os.path.join('languages', f'lang_{lang_code}.json'))
        with open(lang_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        logging.error(f"Translation file not found for {lang_code}.")
        return {}

def cleanup_bak_files(app_dir: str):
    for item in os.listdir(app_dir):
        if item.endswith('.bak'):
            bak_path= os.path.join(app_dir,item)
            try:
                if os.path.isfile(bak_path) or os.path.islink(bak_path):
                    os.unlink(bak_path)
                elif os.path.isdir(bak_path):
                    shutil.rmtree(bak_path)
                logging.info(f"Removed leftover .bak: {bak_path}")
            except Exception as e:
                logging.error(f"Could not remove leftover .bak: {bak_path}, error={e}")

# Текущий язык
current_language = 'en'
translations = load_translation(current_language)

def notify_user_about_update(duck, latest_release, manual_trigger=False):
    latest_version= latest_release['tag_name'].lstrip('v')
    release_notes= latest_release.get('body','')
    github_url= latest_release.get('html_url','#')
    if len(release_notes)>600:
        release_notes= release_notes[:600]+'...'
    release_notes+=f"\n\nGithub Change log: {github_url}"
    if getattr(duck,'skipped_version','')== latest_version and not manual_trigger:
        return
    msg= QMessageBox(duck)
    msg.setWindowTitle(translations.get("update_available","Update available"))
    template= translations.get("new_version_available_text",
        f"A new version {latest_version} is available\n\nWhat's new:\n{{release_notes}}\n\nInstall new update?")
    text= template.format(latest_version=latest_version,release_notes=release_notes)
    msg.setText(text)
    yes_btn= msg.addButton(translations.get("yes","Yes"), QMessageBox.YesRole)
    no_btn= msg.addButton(translations.get("no","No"), QMessageBox.NoRole)
    skip_btn= msg.addButton(translations.get("skip_this_version","Skip"), QMessageBox.ActionRole)
    msg.setDefaultButton(yes_btn)
    msg.exec()
    clicked= msg.clickedButton()
    if clicked== yes_btn:
        app_dir= os.path.dirname(os.path.abspath(sys.argv[0]))
        upd= UpdateWindow(
            autoupdater= duck.updater,
            current_version= PROJECT_VERSION,
            app_dir= app_dir,
            exe_name="quackduck.exe",
            parent= duck
        )
        upd.exec_()
    elif clicked== skip_btn:
        duck.set_skipped_version(latest_version)
        if manual_trigger:
            skip_tpl= translations.get("version_skipped_message",
                f"Version {latest_version} will be skipped. Not offered again.")
            skip_msg= skip_tpl.format(latest_version=latest_version)
            QMessageBox.information(duck,
                translations.get("skipped_version_title","Version Skipped"), skip_msg)

def get_system_accent_color():
    if sys.platform=='win32':
        try:
            registry= winreg.ConnectRegistry(None, winreg.HKEY_CURRENT_USER)
            key= winreg.OpenKey(registry, r'SOFTWARE\Microsoft\Windows\DWM',0,winreg.KEY_READ)
            accent_color, _= winreg.QueryValueEx(key,'AccentColor')
            winreg.CloseKey(key)
            a= (accent_color>>24)&0xFF
            r= (accent_color>>16)&0xFF
            g= (accent_color>>8)&0xFF
            b= accent_color&0xFF
            return QColor(r,g,b,a)
        except Exception as e:
            logging.error(f"Failed get accent color: {e}")
            return QColor(5,184,204)
    else:
        return QColor(5,184,204)

def exception_handler(exctype, value, tb):
    err_msg= ''.join(traceback.format_exception(exctype,value,tb))
    crash_log_path= os.path.join(os.path.expanduser('~'),'quackduck_crash.log')
    sys_info=(
        f"System Information:\n"
        f"OS: {platform.system()} {platform.release()} ({platform.version()})\n"
        f"Machine: {platform.machine()}\n"
        f"Processor: {platform.processor()}\n"
        f"Python: {platform.python_version()}\n\n"
    )
    with open(crash_log_path,'w') as f:
        f.write(sys_info)
        f.write(err_msg)
    logging.error(sys_info+err_msg)
    if QtWidgets.QApplication.instance():
        m= QMessageBox()
        m.setIcon(QMessageBox.Icon.Critical)
        m.setWindowTitle(translations.get("error_title","Error!"))
        m.setText(translations.get("application_error","Application error:")+f" \n{value}")
        m.setDetailedText(sys_info+err_msg)
        m.exec()
    else:
        logging.error("Crash before QApplication init.")
    sys.exit(1)

def get_seed_from_name(name:str)->int:
    hobj= hashlib.sha256(name.encode())
    hex_dig= hobj.hexdigest()
    return int(hex_dig,16)%(2**32)

def fill_purple(w=40,h=40)->QPixmap:
    pm= QPixmap(w,h)
    pm.fill(QtGui.QColor(255,0,255))
    return pm

def extract_frames_full(spritesheet: QPixmap, fw:int, fh:int, coords:List[str], pet_size:int)->List[QPixmap]:
    res=[]
    if spritesheet.isNull():
        logging.error("Spritesheet is null => can't extract frames.")
        return res
    for cstr in coords:
        parts= cstr.split(':')
        if len(parts)!=2:
            continue
        try:
            row= int(parts[0])
            col= int(parts[1])
        except:
            continue
        x= col*fw
        y= row*fh
        piece= spritesheet.copy(x,y,fw,fh)
        if piece.isNull():
            logging.warning(f"Null piece row={row},col={col}")
            continue
        w2= fw* pet_size
        h2= fh* pet_size
        piece= piece.scaled(w2,h2, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.FastTransformation)
        res.append(piece)
    return res

ENERGY_COST= {
    "walking":1,
    "running":2,
    "jumping":2,
    "attacking":1,
    "crouching":1,
    "dragging":0,
    "wallgrab":2,
    "cursorHunt":5
}


class ResourceManager:
    def __init__(self, scale_factor: float, pet_size:int=3):
        self.assets_dir= resource_path('assets')
        self.skins_dir= os.path.join(self.assets_dir,'skins')
        self.current_skin= 'default'
        self.current_skin_temp_dir= None
        self.animations: Dict[str, List[QPixmap]]= {}
        self.sounds: List[str]= []
        self.scale_factor= scale_factor
        self.pet_size= pet_size

        self.spritesheet_path= None
        self.frame_width= 32
        self.frame_height= 32
        self.animations_config= {}
        self.sound_files= []
        self.loaded_spritesheet= None

        self.default_animations_config= {
            "idle": ["0:0"],
            "walk": ["1:0","1:1","1:2","1:3","1:4","1:5"],
            "listen": ["2:1"],
            "fall": ["2:3"],
            "jump": ["2:0","2:1","2:2","2:3"],
            "sleep": ["0:1"],
            "sleep_transition": ["2:1"]
        }
        self.sprites_loaded= False
        self.sounds_loaded= False
        self._sprites_failed= False
        self._loading_failed= False
        self._load_attempts=0

        self.load_default_skin(lazy=False)

    def load_default_skin(self, lazy=False):
        logging.info("Load default skin triggered.")
        log_call_stack()
        self.cleanup_temp_dir()
        self.current_skin= 'default'
        skin_path= os.path.join(self.skins_dir,'default')
        self.spritesheet_path= os.path.join(skin_path,'spritesheet.png')
        self.frame_width= 32
        self.frame_height= 32
        self.animations_config= self.default_animations_config.copy()
        self.sound_files= [os.path.join(skin_path,'wuak.wav')]
        if not lazy:
            self.load_sprites_now(force_reload=True)
            self.load_sounds_now()

    def load_skin(self, skin_file:str)->bool:
        self.cleanup_temp_dir()
        if not (os.path.isfile(skin_file) and skin_file.lower().endswith('.zip')):
            logging.error(f"Invalid skin file: {skin_file}")
            self.load_default_skin(lazy=True)
            return False
        try:
            with zipfile.ZipFile(skin_file,'r') as z:
                if 'config.json' not in z.namelist():
                    logging.error(f"Skin missing config.json => fallback.")
                    self.load_default_skin(lazy=True)
                    return False
                temp_dir= tempfile.mkdtemp()
                self.current_skin_temp_dir= temp_dir
                logging.info(f"Extract to {temp_dir}")
                z.extractall(temp_dir)
                cfg_path= os.path.join(temp_dir,'config.json')
                with open(cfg_path,'r',encoding='utf-8') as f:
                    config= json.load(f)
                if not isinstance(config,dict) or "spritesheet" not in config or "frame_width" not in config or "frame_height" not in config or "animations" not in config:
                    logging.error("Skin config invalid => fallback.")
                    self.load_default_skin(lazy=True)
                    return False
                self.spritesheet_path= os.path.join(temp_dir, config["spritesheet"])
                self.frame_width= config["frame_width"]
                self.frame_height= config["frame_height"]
                self.animations_config= config["animations"]
                if not os.path.exists(self.spritesheet_path):
                    logging.error("Spritesheet not found => fallback.")
                    self.load_default_skin(lazy=True)
                    return False
                snd_list= config.get("sound",[])
                if isinstance(snd_list,str):
                    snd_list= [snd_list]
                self.sound_files=[]
                for s in snd_list:
                    sp= os.path.join(temp_dir,s)
                    if os.path.exists(sp) and s.lower().endswith('.wav'):
                        self.sound_files.append(sp)
                self.current_skin= skin_file
                return True
        except Exception as e:
            logging.error(f"Fail load skin {skin_file}: {e}")
            self.load_default_skin(lazy=True)
            return False

    def cleanup_temp_dir(self):
        if self.current_skin_temp_dir and os.path.exists(self.current_skin_temp_dir):
            try:
                shutil.rmtree(self.current_skin_temp_dir)
                logging.info(f"Removed {self.current_skin_temp_dir}")
            except Exception as e:
                logging.error(f"Cannot remove {self.current_skin_temp_dir}: {e}")
            self.current_skin_temp_dir= None
        self.animations.clear()
        self.sounds.clear()
        self.loaded_spritesheet= None
        self.sprites_loaded= False
        self.sounds_loaded= False
        self._sprites_failed= False
        self._loading_failed= False
        self._load_attempts=0

    def load_sprites_now(self, force_reload=False):
        if self.sprites_loaded and not force_reload:
            logging.info("Sprites already loaded => skip.")
            return
        if self._sprites_failed and not force_reload:
            logging.error("Sprites previously failed => skip.")
            return
        if self._load_attempts>=3 and not force_reload:
            logging.error("Max attempts => skip.")
            self._sprites_failed= True
            return
        self._load_attempts+=1
        logging.info(f"Loading sprites attempt {self._load_attempts}...")

        pm= QPixmap(self.spritesheet_path) if self.spritesheet_path else QPixmap()
        if pm.isNull():
            logging.error(f"Spritesheet is null: {self.spritesheet_path}")
            self._sprites_failed= True
            return
        self.animations.clear()
        for aname, coords in self.animations_config.items():
            frames= extract_frames_full(pm,self.frame_width,self.frame_height, coords,self.pet_size)
            if not frames:
                frames= [fill_purple(self.frame_width*self.pet_size,self.frame_height*self.pet_size)]
            self.animations[aname]= frames
        self.sprites_loaded= True
        logging.info(f"Loaded {len(self.animations)} animations for skin {self.current_skin}")

    def load_sounds_now(self):
        if self.sounds_loaded:
            return
        self.sounds= self.sound_files.copy()
        self.sounds_loaded= True
        logging.info(f"Loaded {len(self.sounds)} sounds for {self.current_skin}")

    def get_animation_frames_by_name(self, anim_name:str)->List[QPixmap]:
        if anim_name not in self.animations and not self.sprites_loaded:
            self.load_sprites_now()
        return self.animations.get(anim_name,[])

    def get_animation_frame(self, anim_name:str, frame_idx:int)->Optional[QPixmap]:
        frames= self.get_animation_frames_by_name(anim_name)
        if 0<= frame_idx< len(frames):
            return frames[frame_idx]
        return None

    def get_default_frame(self)->Optional[QPixmap]:
        if "idle" in self.animations:
            frs= self.animations["idle"]
            if frs:
                return frs[0]
        for v in self.animations.values():
            if v:
                return v[0]
        return fill_purple(40,40)

    def get_idle_animations(self)->List[str]:
        if not self.sprites_loaded:
            self.load_sprites_now()
        return [k for k in self.animations.keys() if k.startswith("idle")]

    def get_random_sound(self)->Optional[str]:
        if not self.sounds_loaded:
            self.load_sounds_now()
        if not self.sounds:
            logging.error("No sound files loaded.")
            return None
        return random.choice(self.sounds)

    def set_pet_size(self, pet_size:int):
        self.pet_size= pet_size
        self.animations.clear()
        self.loaded_spritesheet= None
        self.sprites_loaded= False
        self._sprites_failed= False
        self._load_attempts=0

    def __del__(self):
        self.cleanup_temp_dir()


class SettingsManager:
    def __init__(self, organization:str='zl0yxp', application:str='QuackDuck'):
        self._settings= QtCore.QSettings(organization, application)
    def get_value(self, key:str, default=None, value_type=None):
        return self._settings.value(key, defaultValue=default, type=value_type)
    def set_value(self, key:str, value):
        self._settings.setValue(key,value)
    def clear(self):
        self._settings.clear()
    def sync(self):
        self._settings.sync()

class MicrophoneListener(QtCore.QThread):
    volume_signal= QtCore.pyqtSignal(int)
    def __init__(self, device_index=None, activation_threshold=10, parent=None):
        super().__init__(parent)
        self.device_index= device_index
        self.activation_threshold= activation_threshold
        self.running= True

    def run(self):
        def audio_cb(indata, frames, time_info, status):
            if status:
                logging.warning(f"Mic status: {status}")
            vol= np.linalg.norm(indata)*10
            self.volume_signal.emit(min(int(vol),100))
        try:
            with sd.InputStream(
                device=self.device_index,
                channels=1,
                samplerate=22050,
                blocksize=1024,
                callback=audio_cb
            ):
                while self.running:
                    sd.sleep(200)
        except Exception as e:
            logging.error(f"Error open mic: {e}")
            self.running=False

    def stop(self):
        self.running= False
        self.wait()

    def update_settings(self, device_index=None, activation_threshold=None):
        if device_index is not None:
            self.device_index= device_index
        if activation_threshold is not None:
            self.activation_threshold= activation_threshold


class SystemTrayIcon(QtWidgets.QSystemTrayIcon):
    def __init__(self, parent=None):
        self.visible_icon_path= resource_path("assets/images/white-quackduck-visible.ico")
        self.hidden_icon_path= resource_path("assets/images/white-quackduck-hidden.ico")

        if not os.path.exists(self.visible_icon_path):
            logging.error(f"Icon file not found: {self.visible_icon_path}")
            super().__init__()
        else:
            icon= QtGui.QIcon(self.visible_icon_path)
            super().__init__(icon, parent)

        self.parent= parent
        self.setup_menu()
        self.activated.connect(self.icon_activated)

    def setup_menu(self):
        m= QtWidgets.QMenu()
        st= m.addAction(translations.get("settings","⚙️ Settings"))
        st.triggered.connect(self.parent.open_settings)
        un= m.addAction(translations.get("unstuck","🔄 Unstuck"))
        un.triggered.connect(self.parent.unstuck_duck)
        ab= m.addAction(translations.get("about","👋 About"))
        ab.triggered.connect(self.show_about)
        upd= m.addAction(translations.get("check_updates","🔄 Update"))
        upd.triggered.connect(self.check_for_updates)
        m.addSeparator()
        s= m.addAction(translations.get("show","👀 Show"))
        h= m.addAction(translations.get("hide","🙈 Hide"))
        m.addSeparator()
        c= m.addAction(translations.get("buy_me_a_coffee","☕ Buy me a coffee"))
        c.triggered.connect(lambda: webbrowser.open("https://buymeacoffee.com/zl0yxp"))
        e= m.addAction(translations.get("exit","🚪 Close"))
        s.triggered.connect(self.show_duck)
        h.triggered.connect(self.hide_duck)
        e.triggered.connect(QtWidgets.QApplication.instance().quit)
        m.addSeparator()
        if GLOBAL_DEBUG_MODE:
            dbg= m.addAction(translations.get("debug_mode","🛠️ Debug mode"))
            dbg.triggered.connect(self.parent.show_debug_window)
        self.setContextMenu(m)
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
                height:1px;
                background:#444;
                margin:5px 0;
            }
        """)

    def icon_activated(self, reason):
        if reason== QtWidgets.QSystemTrayIcon.ActivationReason.DoubleClick:
            self.parent.open_settings()
            self.show_duck()
        elif reason== QtWidgets.QSystemTrayIcon.ActivationReason.Trigger:
            if self.parent.isVisible():
                self.hide_duck()
            else:
                self.show_duck()

    def hide_duck(self):
        self.parent.hide()
        if hasattr(self.parent,'name_window') and self.parent.name_window and self.parent.name_window.isVisible():
            self.parent.name_window.hide()
        if os.path.exists(self.hidden_icon_path):
            self.setIcon(QtGui.QIcon(self.hidden_icon_path))
        self.parent.pause_duck(force_idle=False)

    def show_duck(self):
        self.parent.show()
        if hasattr(self.parent,'name_window') and self.parent.name_window and self.parent.show_name:
            self.parent.name_window.show()
        self.parent.raise_()
        self.parent.activateWindow()
        if os.path.exists(self.visible_icon_path):
            self.setIcon(QtGui.QIcon(self.visible_icon_path))
        self.parent.resume_duck()

    def check_for_updates(self):
        self.parent.check_for_updates_manual()

    def show_about(self):
        about_text= "QuackDuck\nDeveloped with 💜 by zl0yxp\nDiscord: zl0yxp\nTelegram: t.me/quackduckapp"
        QMessageBox.information(self.parent,
            translations.get("about_title","About"),
            about_text, 
            QMessageBox.StandardButton.Ok
        )

class HeartWindow(QtWidgets.QWidget):
    def __init__(self, x, y):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint| Qt.WindowType.WindowStaysOnTopHint|Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose)
        self.opacity=1.0
        self.start_time= time.time()
        self.duration=2.0
        self.size= random.uniform(20,50)
        self.dx= random.uniform(-20,20)
        self.dy= random.uniform(-50,-100)
        heart= resource_path("assets/images/heart.png")
        if not os.path.exists(heart):
            logging.error(f"Heart image not found: {heart}")
            self.close()
            return
        pm= QPixmap(heart)
        pm= pm.scaled(int(self.size),int(self.size), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.FastTransformation)
        self.image= pm
        self.x= x- self.size/2
        self.y= y- self.size/2
        self.move(int(self.x),int(self.y))

        self.timer= QTimer()
        self.timer.timeout.connect(self.update_position)
        self.timer.start(30)
        self.resize(int(self.size), int(self.size))
        self.show()

    def closeEvent(self, e):
        if self.timer.isActive():
            self.timer.stop()
        self.timer=None
        logging.info("HeartWindow closed.")
        super().closeEvent(e)

    def paintEvent(self, e):
        p= QtGui.QPainter(self)
        p.setOpacity(self.opacity)
        p.drawPixmap(0,0,self.image)

    def update_position(self):
        el= time.time()- self.start_time
        if el> self.duration:
            self.close()
            return
        pr= el/self.duration
        self.x+= self.dx*0.02
        self.y+= self.dy*0.02
        self.opacity= 1.0- pr
        self.move(int(self.x),int(self.y))
        self.update()

class NameWindow(QtWidgets.QWidget):
    def __init__(self, duck):
        super().__init__()
        self.duck= duck
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint| Qt.WindowType.WindowStaysOnTopHint|Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose, False)

        self.label= QtWidgets.QLabel(self)
        self.label.setStyleSheet("QLabel { color:white; font-weight:bold; }")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.update_label()
        self.show()

    def update_label(self):
        base= getattr(self.duck,'font_base_size',14)
        sc= int(base* (self.duck.pet_size/3))
        if sc<8:
            sc=8
        f= QtGui.QFont("Segoe UI", sc)
        self.label.setFont(f)
        self.label.setText(self.duck.pet_name)
        self.label.adjustSize()
        self.adjustSize()

    def update_position(self):
        dx= self.duck.duck_x
        dy= self.duck.duck_y
        dw= self.duck.duck_width
        w= self.width()
        h= self.height()
        top_off= self.duck.get_top_non_opaque_offset()
        offset_y= self.duck.name_offset_y+ top_off
        xx= dx+ (dw- w)/2
        yy= dy- offset_y
        scr= QtWidgets.QApplication.primaryScreen().geometry()
        if xx<0: xx=0
        if yy<0: yy=0
        if xx+ w> scr.width():
            xx= scr.width()- w
        if yy+ h> scr.height():
            yy= scr.height()- h
        self.move(int(xx),int(yy))

class DebugWindow(QtWidgets.QWidget):
    def __init__(self, duck):
        super().__init__()
        self.duck= duck
        self.setWindowTitle("Debug Window")
        self.setGeometry(100,100,400,300)
        ly= QVBoxLayout(self)
        ly.addWidget(QLabel("Debug placeholder."))

class SettingsWindow(QtWidgets.QWidget):
    def __init__(self, duck):
        super().__init__()
        self.duck= duck
        self.setWindowTitle("Settings Window")
        self.setGeometry(200,200,500,400)
        ly= QVBoxLayout(self)
        ly.addWidget(QLabel("Settings placeholder."))

# Абстракт State
class State(ABC):
    def __init__(self, duck:'Duck'):
        self.duck= duck
    @abstractmethod
    def enter(self)->None:
        pass
    @abstractmethod
    def update_animation(self)->None:
        pass
    @abstractmethod
    def update_position(self)->None:
        pass
    @abstractmethod
    def exit(self)->None:
        pass
    def handle_mouse_press(self, event:QMouseEvent)->None:
        pass
    def handle_mouse_release(self, event:QMouseEvent)->None:
        pass
    def handle_mouse_move(self, event:QMouseEvent)->None:
        pass


# =========================================
# Определяем все необходимые 11+ состояний
# =========================================

class IdleState(State):
    def __init__(self, duck):
        super().__init__(duck)
        self.frames=[]
        self.frame_index=0
        self.start_time=0

    def enter(self):
        possible= self.duck.resources.get_idle_animations()
        if not possible:
            possible= ["idle"]
        chosen= random.choice(possible)
        self.frames= self.duck.resources.get_animation_frames_by_name(chosen)
        if not self.frames:
            self.frames= [fill_purple(40,40)]
        self.frame_index=0
        self.start_time= time.time()
        self.update_frame()
        self.duck.check_energy_and_maybe_sleep()

    def update_animation(self):
        if self.frames:
            self.frame_index= (self.frame_index+1)% len(self.frames)
            self.update_frame()

    def update_position(self):
        elapsed= time.time()- self.start_time
        if elapsed> self.duck.idle_duration:
            self.duck.change_state(WalkingState(self.duck))

    def exit(self):
        pass

    def update_frame(self):
        frm= self.frames[self.frame_index]
        if not self.duck.facing_right:
            frm= frm.transformed(QTransform().scale(-1,1))
        self.duck.current_frame= frm
        self.duck.update()

    def handle_mouse_press(self, event):
        if event.button()== Qt.MouseButton.LeftButton:
            self.duck.change_state(DraggingState(self.duck), event)
        elif event.button()== Qt.MouseButton.RightButton:
            self.duck.change_state(JumpingState(self.duck))

class WalkingState(State):
    def __init__(self, duck):
        super().__init__(duck)
        self.frames=[]
        self.frame_index=0
        self.target_x=0
        self.start_time=0

    def enter(self):
        self.frames= self.duck.resources.get_animation_frames_by_name("walk")
        if not self.frames:
            self.frames= self.duck.resources.get_animation_frames_by_name("idle")
        self.frame_index=0
        sw= self.duck.screen_width
        w= self.duck.duck_width
        self.target_x= random.randint(0, sw- w)
        self.start_time= time.time()
        self.update_frame()
        self.duck.check_energy_and_maybe_sleep()

    def update_animation(self):
        if self.frames:
            self.frame_index= (self.frame_index+1)% len(self.frames)
            self.update_frame()

    def update_position(self):
        dx= self.target_x- self.duck.duck_x
        sp= self.duck.duck_speed
        if abs(dx)<= sp:
            self.duck.duck_x= self.target_x
            self.duck.use_energy( ENERGY_COST["walking"] )
            self.duck.check_energy_and_maybe_sleep()
            self.duck.change_state(IdleState(self.duck))
            return
        sign= 1 if dx>0 else -1
        self.duck.facing_right= (sign>0)
        self.duck.duck_x+= sp* sign
        if self.duck.duck_x<0:
            self.duck.duck_x=0
        elif self.duck.duck_x+ self.duck.duck_width> self.duck.screen_width:
            self.duck.duck_x= self.duck.screen_width- self.duck.duck_width
        self.duck.move(int(self.duck.duck_x),int(self.duck.duck_y))

    def exit(self):
        pass

    def update_frame(self):
        if not self.frames:
            return
        frm= self.frames[self.frame_index]
        if not self.duck.facing_right:
            frm= frm.transformed(QTransform().scale(-1,1))
        self.duck.current_frame= frm
        self.duck.update()

    def handle_mouse_press(self, event):
        if event.button()== Qt.MouseButton.LeftButton:
            self.duck.change_state(DraggingState(self.duck), event)
        elif event.button()== Qt.MouseButton.RightButton:
            self.duck.change_state(JumpingState(self.duck))

class RunningState(State):
    def __init__(self, duck):
        super().__init__(duck)
        self.frames=[]
        self.frame_index=0
        self.target_x=0

    def enter(self):
        self.frames= self.duck.resources.get_animation_frames_by_name("running")
        if not self.frames:
            self.frames= self.duck.resources.get_animation_frames_by_name("walk")
        if not self.frames:
            self.frames= self.duck.resources.get_animation_frames_by_name("idle")
        self.frame_index=0
        sw= self.duck.screen_width
        w= self.duck.duck_width
        self.target_x= random.randint(0, sw- w)
        self.update_frame()
        self.duck.check_energy_and_maybe_sleep()

    def update_animation(self):
        if self.frames:
            self.frame_index= (self.frame_index+1)% len(self.frames)
            self.update_frame()

    def update_position(self):
        dx= self.target_x- self.duck.duck_x
        sp= self.duck.duck_speed*2
        if abs(dx)<= sp:
            self.duck.duck_x= self.target_x
            self.duck.use_energy( ENERGY_COST["running"] )
            self.duck.check_energy_and_maybe_sleep()
            self.duck.change_state(IdleState(self.duck))
            return
        sign= 1 if dx>0 else -1
        self.duck.facing_right= (sign>0)
        self.duck.duck_x+= sign* sp
        if self.duck.duck_x<0:
            self.duck.duck_x=0
        elif self.duck.duck_x+ self.duck.duck_width> self.duck.screen_width:
            self.duck.duck_x= self.duck.screen_width- self.duck.duck_width
        self.duck.move(int(self.duck.duck_x),int(self.duck.duck_y))

    def exit(self):
        pass

    def update_frame(self):
        if not self.frames:
            return
        frm= self.frames[self.frame_index]
        if not self.duck.facing_right:
            frm= frm.transformed(QTransform().scale(-1,1))
        self.duck.current_frame= frm
        self.duck.update()

    def handle_mouse_press(self, event):
        if event.button()== Qt.MouseButton.LeftButton:
            self.duck.change_state(DraggingState(self.duck), event)
        elif event.button()== Qt.MouseButton.RightButton:
            self.duck.change_state(JumpingState(self.duck))

class JumpingState(State):
    def __init__(self, duck):
        super().__init__(duck)
        self.frames=[]
        self.frame_index=0
        self.vspeed=-15
        self.is_falling= False

    def enter(self):
        self.duck.use_energy( ENERGY_COST["jumping"] )
        j= self.duck.resources.get_animation_frames_by_name("jump")
        if not j:
            j= self.duck.resources.get_animation_frames_by_name("idle")
        self.frames= j
        self.frame_index=0
        self.vspeed= -15
        self.is_falling= False
        self.duck.check_energy_and_maybe_sleep()
        self.update_frame()

    def update_animation(self):
        if not self.is_falling:
            if self.frame_index< len(self.frames)-1:
                self.frame_index+=1
            else:
                # Переходим к "fall" анимации
                self.is_falling= True
                fall= self.duck.resources.get_animation_frames_by_name("fall")
                if not fall:
                    fall= self.frames
                self.frames= fall
                self.frame_index=0
        else:
            self.frame_index= (self.frame_index+1)% len(self.frames)
        self.update_frame()

    def update_position(self):
        self.vspeed+=1
        self.duck.duck_y+= self.vspeed
        if self.duck.duck_y + self.duck.duck_height>= self.duck.ground_level:
            self.duck.duck_y= self.duck.ground_level- self.duck.duck_height
            # Переходим в LandingState
            self.duck.change_state(LandingState(self.duck))
        else:
            self.duck.move(int(self.duck.duck_x),int(self.duck.duck_y))

    def exit(self):
        pass

    def update_frame(self):
        if not self.frames:
            return
        frm= self.frames[self.frame_index]
        if not self.duck.facing_right:
            frm= frm.transformed(QTransform().scale(-1,1))
        self.duck.current_frame= frm
        self.duck.update()

class AttackingState(State):
    def __init__(self, duck):
        super().__init__(duck)
        self.frames=[]
        self.frame_index=0

    def enter(self):
        self.duck.use_energy( ENERGY_COST["attacking"] )
        a= self.duck.resources.get_animation_frames_by_name("attack")
        if not a:
            a= self.duck.resources.get_animation_frames_by_name("idle")
        self.frames= a
        self.frame_index=0
        self.duck.check_energy_and_maybe_sleep()
        self.update_frame()

    def update_animation(self):
        if not self.frames:
            self.duck.change_state(IdleState(self.duck))
            return
        if self.frame_index< len(self.frames)-1:
            self.frame_index+=1
        else:
            self.duck.change_state(IdleState(self.duck))
            return
        self.update_frame()

    def update_position(self):
        pass

    def exit(self):
        pass

    def update_frame(self):
        frm= self.frames[self.frame_index]
        if not self.duck.facing_right:
            frm= frm.transformed(QTransform().scale(-1,1))
        self.duck.current_frame= frm
        self.duck.update()

    def handle_mouse_press(self, event):
        if event.button()== Qt.MouseButton.LeftButton:
            self.duck.stop_current_state()
            self.duck.change_state(DraggingState(self.duck), event)

class DraggingState(State):
    def __init__(self, duck):
        super().__init__(duck)
        self.frames=[]
        self.frame_index=0
        self.drag_offset= QPoint()

    def enter(self):
        f= self.duck.resources.get_animation_frames_by_name("fall")
        if not f:
            f= self.duck.resources.get_animation_frames_by_name("idle")
        self.frames= f
        self.frame_index=0
        if self.duck.name_window:
            self.duck.name_window.hide()
        self.update_frame()

    def update_animation(self):
        if self.frames and self.frame_index< len(self.frames)-1:
            self.frame_index+=1
            self.update_frame()

    def update_position(self):
        pass

    def exit(self):
        if self.duck.name_window and self.duck.show_name and self.duck.pet_name.strip():
            self.duck.name_window.show()

    def update_frame(self):
        if not self.frames:
            return
        frm= self.frames[self.frame_index]
        if not self.duck.facing_right:
            frm= frm.transformed(QTransform().scale(-1,1))
        self.duck.current_frame= frm
        self.duck.update()

    def handle_mouse_press(self, event):
        self.drag_offset= event.pos()

    def handle_mouse_move(self, event):
        new_pos= QtGui.QCursor.pos()- self.drag_offset
        self.duck.duck_x= new_pos.x()
        self.duck.duck_y= new_pos.y()
        self.duck.move(int(self.duck.duck_x),int(self.duck.duck_y))
        if self.duck.name_window and self.duck.show_name and self.duck.pet_name.strip():
            self.duck.name_window.update_position()

    def handle_mouse_release(self, event):
        self.duck.change_state(FallingState(self.duck,play_animation=False,return_state=WalkingState(self.duck)))

class FallingState(State):
    def __init__(self, duck, play_animation=True, return_state=None):
        super().__init__(duck)
        self.play_animation= play_animation
        self.return_state= return_state
        self.frames=[]
        self.frame_index=0
        self.vertical_speed=0

    def enter(self):
        if self.play_animation:
            fall= self.duck.resources.get_animation_frames_by_name("fall")
            if not fall:
                fall= self.duck.resources.get_animation_frames_by_name("idle")
            self.frames= fall
        else:
            if self.duck.current_frame:
                self.frames= [self.duck.current_frame]
            else:
                self.frames= []
        self.frame_index=0
        self.vertical_speed=0
        self.update_frame()

    def update_animation(self):
        if self.play_animation and self.frames:
            if self.frame_index< len(self.frames)-1:
                self.frame_index+=1
                self.update_frame()

    def update_position(self):
        self.vertical_speed+=1
        self.duck.duck_y+= self.vertical_speed
        if self.duck.duck_y+ self.duck.duck_height>= self.duck.ground_level:
            self.duck.duck_y= self.duck.ground_level- self.duck.duck_height
            self.duck.move(int(self.duck.duck_x),int(self.duck.duck_y))
            nxt= LandingState(self.duck, next_state= self.return_state or IdleState(self.duck))
            self.duck.change_state(nxt)
        else:
            self.duck.move(int(self.duck.duck_x),int(self.duck.duck_y))

    def exit(self):
        pass

    def update_frame(self):
        if not self.frames:
            return
        frm= self.frames[self.frame_index]
        if not self.duck.facing_right:
            frm= frm.transformed(QTransform().scale(-1,1))
        self.duck.current_frame= frm
        self.duck.update()

class LandingState(State):
    def __init__(self, duck, next_state=None):
        super().__init__(duck)
        self.next_state= next_state
        self.frames=[]
        self.frame_index=0

    def enter(self):
        lad= self.duck.resources.get_animation_frames_by_name("land")
        if not lad:
            lad= self.duck.resources.get_animation_frames_by_name("idle")
        self.frames= lad
        self.frame_index=0
        self.update_frame()

    def update_animation(self):
        if not self.frames:
            if self.next_state:
                self.duck.change_state(self.next_state)
            return
        if self.frame_index< len(self.frames)-1:
            self.frame_index+=1
            self.update_frame()
        else:
            if self.next_state:
                self.duck.change_state(self.next_state)

    def update_position(self):
        pass

    def exit(self):
        pass

    def update_frame(self):
        if not self.frames:
            return
        frm= self.frames[self.frame_index]
        if not self.duck.facing_right:
            frm= frm.transformed(QTransform().scale(-1,1))
        self.duck.current_frame= frm
        self.duck.update()

class SleepingState(State):
    def __init__(self, duck):
        super().__init__(duck)
        self.frames=[]
        self.frame_index=0
        self.transition_frames=[]
        self.transition_index=0

    def enter(self):
        st= self.duck.resources.get_animation_frames_by_name("sleep_transition")
        if not st:
            st= [fill_purple(40,40)]
        self.transition_frames= st
        self.transition_index=0

        main_sleep= self.duck.resources.get_animation_frames_by_name("sleep")
        if not main_sleep:
            main_sleep= [fill_purple(40,40)]
        self.frames= main_sleep
        self.frame_index=0
        self.update_transition_frame()

    def update_transition_frame(self):
        if self.transition_index< len(self.transition_frames)-1:
            frm= self.transition_frames[self.transition_index]
            self.duck.current_frame= frm
            self.duck.update()
            self.transition_index+=1
            QTimer.singleShot(150, self.update_transition_frame)
        else:
            self.update_frame()

    def update_frame(self):
        if not self.frames:
            return
        frm= self.frames[self.frame_index]
        self.duck.current_frame= frm
        self.duck.update()

    def update_animation(self):
        if self.transition_index< len(self.transition_frames):
            # ещё идёт transition
            return
        if self.frames:
            self.frame_index= (self.frame_index+1)% len(self.frames)
            self.update_frame()
        # +1 energy/sec
        if self.duck.energy< self.duck.energy_max:
            self.duck.energy+=1
        else:
            self.duck.energy= self.duck.energy_max

    def update_position(self):
        pass

    def exit(self):
        pass

    def handle_mouse_press(self, event):
        if event.button()== Qt.MouseButton.LeftButton:
            self.forced_wakeup()

    def forced_wakeup(self):
        self.duck.stop_current_state()
        self.duck.change_state(IdleState(self.duck))
        QTimer.singleShot(60_000, self.check_energy_after_wakeup)

    def check_energy_after_wakeup(self):
        if self.duck.energy< (0.25*self.duck.energy_max):
            self.duck.stop_current_state()
            self.duck.change_state(SleepingState(self.duck))

class ListeningState(State):
    def __init__(self, duck):
        super().__init__(duck)
        self.frames=[]
        self.frame_index=0

    def enter(self):
        self.duck.is_listening= True
        li= self.duck.resources.get_animation_frames_by_name("listen")
        if not li:
            li= self.duck.resources.get_animation_frames_by_name("idle")
        self.frames= li
        self.frame_index=0
        self.duck.check_energy_and_maybe_sleep()
        self.update_frame()

    def update_animation(self):
        if self.frames:
            self.frame_index= (self.frame_index+1)% len(self.frames)
            self.update_frame()

    def update_position(self):
        pass

    def exit(self):
        self.duck.is_listening= False

    def update_frame(self):
        frm= self.frames[self.frame_index]
        if not self.duck.facing_right:
            frm= frm.transformed(QTransform().scale(-1,1))
        self.duck.current_frame= frm
        self.duck.update()

    def handle_mouse_press(self, event):
        if event.button()== Qt.MouseButton.LeftButton:
            self.duck.is_listening= False
            self.duck.change_state(DraggingState(self.duck), event)


class CrouchingState(State):
    def __init__(self, duck):
        super().__init__(duck)
        self.frames=[]
        self.frame_index=0
        self.target_x=0

    def enter(self):
        c= self.duck.resources.get_animation_frames_by_name("crouching")
        if not c:
            c= self.duck.resources.get_animation_frames_by_name("idle")
        self.frames= c
        self.frame_index=0
        sw= self.duck.screen_width
        w= self.duck.duck_width
        self.target_x= random.randint(0, sw- w)
        self.duck.check_energy_and_maybe_sleep()
        self.update_frame()

    def update_animation(self):
        if self.frames:
            self.frame_index= (self.frame_index+1)% len(self.frames)
            self.update_frame()

    def update_position(self):
        dx= self.target_x- self.duck.duck_x
        sp= max(1,int(self.duck.base_duck_speed*0.5))
        if abs(dx)<= sp:
            self.duck.duck_x= self.target_x
            self.duck.use_energy( ENERGY_COST["crouching"] )
            self.duck.check_energy_and_maybe_sleep()
            self.duck.change_state(IdleState(self.duck))
            return
        sign= 1 if dx>0 else -1
        self.duck.facing_right= (sign>0)
        self.duck.duck_x+= sp* sign
        if self.duck.duck_x<0:
            self.duck.duck_x=0
        elif self.duck.duck_x+ self.duck.duck_width> self.duck.screen_width:
            self.duck.duck_x= self.duck.screen_width- self.duck.duck_width
        self.duck.move(int(self.duck.duck_x),int(self.duck.duck_y))

    def exit(self):
        pass

    def update_frame(self):
        frm= self.frames[self.frame_index]
        if not self.duck.facing_right:
            frm= frm.transformed(QTransform().scale(-1,1))
        self.duck.current_frame= frm
        self.duck.update()

    def handle_mouse_press(self, event):
        if event.button()== Qt.MouseButton.LeftButton:
            self.duck.change_state(DraggingState(self.duck), event)
        elif event.button()== Qt.MouseButton.RightButton:
            self.duck.change_state(JumpingState(self.duck))

class CursorHuntState(State):
    def __init__(self, duck):
        super().__init__(duck)
        self.frames=[]
        self.frame_index=0
        self.attack_started= False

    def enter(self):
        # cost=5 => при достижении курсора
        a= self.duck.resources.get_animation_frames_by_name("attack")
        if not a:
            a= self.duck.resources.get_animation_frames_by_name("idle")
        self.frames= a
        self.frame_index=0
        self.attack_started= False
        self.duck.check_energy_and_maybe_sleep()

    def update_animation(self):
        if self.frames:
            self.frame_index= (self.frame_index+1)% len(self.frames)
            frm= self.frames[self.frame_index]
            if not self.duck.facing_right:
                frm= frm.transformed(QTransform().scale(-1,1))
            self.duck.current_frame= frm
            self.duck.update()

    def update_position(self):
        cpos= QtGui.QCursor.pos()
        duck_center_x= self.duck.duck_x+ self.duck.duck_width/2
        dx= cpos.x()- duck_center_x
        dist= abs(dx)
        sign= 1 if dx>0 else -1
        self.duck.facing_right= (sign>0)
        # ~10px bottom => 50/50 walk or run
        screen_h= QtWidgets.QApplication.primaryScreen().geometry().height()
        dist_from_bottom= screen_h- cpos.y()
        if dist_from_bottom<10:
            if random.random()<0.5:
                speed= self.duck.duck_speed
            else:
                speed= self.duck.duck_speed*2
        else:
            speed= self.duck.duck_speed*2

        if dist>300 and not self.attack_started:
            self.duck.duck_x+= sign* speed
        else:
            if not self.attack_started:
                mode= random.choice(["jump","crouch","run"])
                if mode=="jump":
                    self.duck.change_state(JumpingState(self.duck))
                elif mode=="crouch":
                    self.duck.change_state(CrouchingState(self.duck))
                else:
                    self.duck.change_state(RunningState(self.duck))
                self.attack_started= True
            else:
                if dist<20:
                    self.duck.use_energy( ENERGY_COST["cursorHunt"] )
                    self.duck.check_energy_and_maybe_sleep()
                    self.duck.change_state(AttackingState(self.duck))

        if self.duck.duck_x<0:
            self.duck.duck_x=0
        elif self.duck.duck_x+ self.duck.duck_width> self.duck.screen_width:
            self.duck.duck_x= self.duck.screen_width- self.duck.duck_width
        self.duck.move(int(self.duck.duck_x),int(self.duck.duck_y))

    def exit(self):
        pass

# Добавим WallGrabState (минимальная реализация)
class WallGrabState(State):
    def __init__(self, duck):
        super().__init__(duck)
        self.frames=[]
        self.frame_index=0

    def enter(self):
        self.duck.use_energy( ENERGY_COST["wallgrab"] )
        wg= self.duck.resources.get_animation_frames_by_name("fall")
        if not wg:
            wg= self.duck.resources.get_animation_frames_by_name("idle")
        self.frames= wg
        self.frame_index=0
        self.duck.check_energy_and_maybe_sleep()
        self.update_frame()

    def update_animation(self):
        if self.frames:
            self.frame_index= (self.frame_index+1)% len(self.frames)
            self.update_frame()

    def update_position(self):
        pass

    def exit(self):
        pass

    def update_frame(self):
        frm= self.frames[self.frame_index]
        if not self.duck.facing_right:
            frm= frm.transformed(QTransform().scale(-1,1))
        self.duck.current_frame= frm
        self.duck.update()

    def handle_mouse_press(self, event):
        if event.button()== Qt.MouseButton.LeftButton:
            self.duck.change_state(DraggingState(self.duck), event)

# -- PlayfulState (пропавшее)
class PlayfulState(State):
    """
    Состояние, при котором утка "играется" около курсора, 
    бегает туда-сюда (ускоренно).
    """
    def __init__(self, duck):
        super().__init__(duck)
        self.frames=[]
        self.frame_index=0
        self.start_time= time.time()
        self.duration= random.randint(20,60)
        self.speed_multiplier= 2
        self.has_jumped= False
        self.prev_direction= duck.direction
        self.prev_facing_right= duck.facing_right

    def enter(self):
        self.duck.duck_speed= self.duck.base_duck_speed* self.speed_multiplier* (self.duck.pet_size/3)
        f= self.duck.resources.get_animation_frames_by_name("walk")
        if not f:
            f= self.duck.resources.get_animation_frames_by_name("idle")
        self.frames= f
        self.frame_index=0
        self.update_frame()

    def update_animation(self):
        if not self.frames:
            return
        self.frame_index= (self.frame_index+1)% len(self.frames)
        frm= self.frames[self.frame_index]
        if not self.duck.facing_right:
            frm= frm.transformed(QTransform().scale(-1,1))
        self.duck.current_frame= frm
        self.duck.update()

    def update_position(self):
        now= time.time()
        if now - self.start_time> self.duration:
            self.duck.change_state(IdleState(self.duck))
            return
        self.chase_cursor()

    def chase_cursor(self):
        cpos= QtGui.QCursor.pos()
        dx= cpos.x()- (self.duck.duck_x+ self.duck.current_frame.width()/2 if self.duck.current_frame else 64)
        if dx>10:
            desired_dir=1
        elif dx<-10:
            desired_dir=-1
        else:
            desired_dir= self.duck.direction
        if desired_dir!= self.duck.direction:
            self.duck.direction= desired_dir
            self.duck.facing_right= (desired_dir>0)

        sp= self.duck.duck_speed
        self.duck.duck_x+= desired_dir* sp
        # границы
        maxx= self.duck.screen_width- (self.duck.current_frame.width() if self.duck.current_frame else 64)
        if self.duck.duck_x<0:
            self.duck.duck_x=0
        elif self.duck.duck_x> maxx:
            self.duck.duck_x= maxx
        self.duck.move(int(self.duck.duck_x),int(self.duck.duck_y))

        distx= abs(dx)
        if distx< 50 and not self.has_jumped:
            # jump
            self.duck.change_state(JumpingState(self.duck))
            self.has_jumped= True
        elif distx>=100:
            self.has_jumped= False

    def exit(self):
        self.duck.duck_speed= self.duck.base_duck_speed* (self.duck.pet_size/3)
        self.duck.direction= self.prev_direction
        self.duck.facing_right= self.prev_facing_right

    def handle_mouse_press(self, event):
        if event.button()== Qt.MouseButton.LeftButton:
            self.duck.change_state(DraggingState(self.duck), event)


# ================= Duck class (поправленный) =================
class Duck(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.settings_manager= SettingsManager()
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.Window)

        self.sound_effect= QSoundEffect()
        self.sound_effect.setVolume(0.5)
        self.skipped_version= ""
        self.updater= AutoUpdater(
            current_version=PROJECT_VERSION,
            repo_owner="KristopherZlo",
            repo_name="quackduck"
        )

        self.debug_mode= False
        self.debug_window= None
        self.state_history= []

        icon_path= resource_path("assets/images/white-quackduck-visible.ico")
        if os.path.exists(icon_path):
            icon= QtGui.QIcon(icon_path)
            if icon.isNull():
                logging.error(f"Failed load icon {icon_path}")
            else:
                self.setWindowIcon(icon)
        else:
            logging.error(f"Icon not found: {icon_path}")

        # для логики микрофона
        self.is_listening= False
        self.listening_entry_timer= None
        self.listening_exit_timer= None

        # загрузка настроек
        self.load_settings()

        self.scale_factor= self.get_scale_factor()
        self.resources= ResourceManager(self.scale_factor, self.pet_size)

        self.cursor_positions=[]
        self.cursor_shake_timer= QtCore.QTimer()
        self.cursor_shake_timer.timeout.connect(self.check_cursor_shake)

        scr= QtGui.QGuiApplication.primaryScreen().geometry()
        self.screen_width= scr.width()
        self.screen_height= scr.height()

        self.show_name= self.settings_manager.get_value('show_name',False,bool)
        self.name_window= None

        if not self.pet_name.strip():
            self.pet_name= random.choice(["Кряква","Плуто","Клювик","Гамми","Додко"])
        self.energy_max= random.randint(1000,3000)
        self.energy= self.energy_max

        self.current_frame= self.resources.get_animation_frame('idle',0)
        if self.current_frame:
            self.duck_width= self.current_frame.width()
            self.duck_height= self.current_frame.height()
        else:
            self.duck_width=64
            self.duck_height=64
        self.resize(self.duck_width,self.duck_height)
        self.duck_x= (self.screen_width- self.duck_width)//2
        self.duck_y= -self.duck_height
        self.direction=1
        self.facing_right= True
        self.ground_level= self.get_ground_level()

        # Начальное состояние - falling
        st= FallingState(self,play_animation=True,return_state=None)
        self.state= st
        self.state.enter()

        self.setup_timers()
        self.apply_settings()

        self.microphone_listener= MicrophoneListener(
            device_index=self.selected_mic_index,
            activation_threshold=self.activation_threshold
        )
        self.microphone_listener.volume_signal.connect(self.on_volume_updated)
        self.microphone_listener.start()

        self.init_ui()
        self.setup_random_behavior()

        self.last_interaction_time= time.time()
        self.last_sound_time= QtCore.QTime.currentTime()

        self.tray_icon= SystemTrayIcon(self)
        self.tray_icon.show()
        self.current_volume=0

        if self.pet_name:
            s= get_seed_from_name(self.pet_name)
            self.random_gen= random.Random(s)
            self.generate_characteristics()
        else:
            self.random_gen= random.Random()
            self.set_default_characteristics()

        self.attack_timer= QTimer()
        self.attack_timer.timeout.connect(self.check_attack_trigger)
        self.attack_timer.start(5000)

        self.run_timer= QTimer()
        self.run_timer.timeout.connect(self.check_run_state_trigger)
        self.run_timer.start(5*60*1000)

        # Добавим также таймер на охоту cursorHunt
        self.hunt_timer= QTimer()
        self.hunt_timer.timeout.connect(self.check_cursor_hunt)
        self.hunt_timer.start(5*60*1000)

        latest_release= self.updater.check_for_updates()
        if latest_release:
            notify_user_about_update(self, latest_release, manual_trigger=False)

        self.is_paused_for_fullscreen= False
        self.fullscreen_check_timer= QTimer()
        self.fullscreen_check_timer.setInterval(4000)
        self.fullscreen_check_timer.timeout.connect(self.check_foreground_fullscreen_winapi)
        self.fullscreen_check_timer.start()

    def mouseDoubleClickEvent(self, event: QtGui.QMouseEvent):
        if event.button()== Qt.MouseButton.LeftButton:
            self.create_heart()

    def create_heart(self):
        # Появляется сердечко над уткой
        heart_x= self.duck_x + (self.current_frame.width() if self.current_frame else 64)//2
        heart_y= self.duck_y
        hw= HeartWindow(heart_x, heart_y)

    def use_energy(self, amount:int):
        self.energy-= amount
        if self.energy<0:
            self.energy=0

    def check_energy_and_maybe_sleep(self):
        if self.energy<=0:
            self.stop_current_state()
            self.change_state(SleepingState(self))

    def check_cursor_hunt(self):
        # раз в 5мин => chance ~30%
        chance= 30
        roll= random.randint(0,99)
        if roll< chance:
            if not isinstance(self.state,(JumpingState,FallingState,DraggingState,SleepingState)):
                self.stop_current_state()
                self.change_state(CursorHuntState(self))

    def check_foreground_fullscreen_winapi(self):
        if not sys.platform.startswith("win"):
            return
        hwnd= win32gui.GetForegroundWindow()
        if not hwnd:
            if self.is_paused_for_fullscreen:
                self.resume_duck()
                self.is_paused_for_fullscreen=False
            return
        cls= win32gui.GetClassName(hwnd)
        _, pid= win32process.GetWindowThreadProcessId(hwnd)
        process_name=""
        try:
            hp= win32api.OpenProcess(win32con.PROCESS_QUERY_INFORMATION|win32con.PROCESS_VM_READ,False,pid)
            en= win32process.GetModuleFileNameEx(hp,0)
            process_name= os.path.basename(en)
            win32api.CloseHandle(hp)
        except:
            pass
        if cls in {"Progman","WorkerW"} or process_name.lower()=="explorer.exe":
            if self.is_paused_for_fullscreen:
                self.resume_duck()
                self.is_paused_for_fullscreen=False
            return
        left, top, right, bottom= win32gui.GetWindowRect(hwnd)
        mon= win32api.MonitorFromWindow(hwnd, win32con.MONITOR_DEFAULTTONEAREST)
        mi= win32api.GetMonitorInfo(mon)
        ml, mt, mr, mb= mi["Monitor"]
        is_full= (left==ml and top==mt and right==mr and bottom==mb)
        if is_full:
            if not self.is_paused_for_fullscreen:
                logging.info("Fullscreen => pause duck.")
                self.pause_duck()
                self.is_paused_for_fullscreen= True
        else:
            if self.is_paused_for_fullscreen:
                logging.info("Fullscreen closed => resume.")
                self.resume_duck()
                self.is_paused_for_fullscreen= False

    def pause_duck(self, force_idle=False):
        if force_idle:
            if not isinstance(self.state, IdleState):
                self.stop_current_state()
                self.change_state(IdleState(self))

        self.animation_timer.stop()
        self.position_timer.stop()
        self.sound_timer.stop()
        self.sleep_timer.stop()
        self.direction_change_timer.stop()
        self.playful_timer.stop()
        self.random_behavior_timer.stop()
        self.hunt_timer.stop()
        self.hide()

    def resume_duck(self):
        self.animation_timer.start(100)
        self.position_timer.start(20)
        self.schedule_next_sound()
        self.sleep_timer.start(10000)
        self.direction_change_timer.start(int(self.direction_change_interval*1000))
        self.playful_timer.start(10*60*1000)
        self.schedule_next_random_behavior()
        self.hunt_timer.start(5*60*1000)
        self.show()

    def stop_current_state(self):
        if self.state:
            try:
                self.state.exit()
            except Exception as e:
                logging.error(f"Error exiting state: {e}")
            self.state=None

    def change_state(self, new_state, event=None):
        old_name= self.state.__class__.__name__ if self.state else "None"
        if getattr(self,"_is_changing_state",False):
            logging.warning("Already changing state => skip.")
            return
        self._is_changing_state= True
        try:
            if self.state:
                self.state.exit()
            self.state= new_state
            self.state.enter()
            if event:
                self.state.handle_mouse_press(event)

            if isinstance(self.state,(IdleState,WalkingState)):
                self.start_cursor_shake_detection()
            else:
                self.stop_cursor_shake_detection()

            new_name= self.state.__class__.__name__
            self.state_history.append((time.strftime("%H:%M:%S"), old_name,new_name))
            if len(self.state_history)>10:
                self.state_history.pop(0)
        except Exception as e:
            logging.error(f"Error changing state: {e}")
        finally:
            self._is_changing_state= False

    def setup_random_behavior(self):
        self.random_behavior_timer= QTimer()
        self.random_behavior_timer.timeout.connect(self.perform_random_behavior)
        self.schedule_next_random_behavior()

    def schedule_next_random_behavior(self):
        interval= random.randint(20000,40000)
        self.random_behavior_timer.start(interval)

    def perform_random_behavior(self):
        cands= [self.enter_random_idle_state, self.change_direction]
        r= random.choice(cands)
        r()
        self.schedule_next_random_behavior()

    def enter_random_idle_state(self):
        if not isinstance(self.state,IdleState) and not isinstance(self.state,(FallingState,DraggingState)):
            self.change_state(IdleState(self))

    def change_direction(self):
        self.direction*= -1
        self.facing_right= (self.direction==1)

    def load_settings(self):
        sm= self.settings_manager
        self.pet_name= sm.get_value('pet_name', default="", value_type=str)
        self.selected_mic_index= sm.get_value('selected_mic_index',default=None,value_type=int)
        self.activation_threshold= sm.get_value('activation_threshold',default=10,value_type=int)
        self.sound_enabled= sm.get_value('sound_enabled', True, bool)
        self.autostart_enabled= sm.get_value('autostart_enabled',False,bool)
        self.playful_behavior_probability= sm.get_value('playful_behavior_probability',0.1,float)
        self.ground_level_setting= sm.get_value('ground_level',0,int)
        self.skin_folder= sm.get_value('skin_folder',None,str)
        self.selected_skin= sm.get_value('selected_skin',None,str)
        self.base_duck_speed= sm.get_value('duck_speed',2.0,float)
        self.pet_size= sm.get_value('pet_size',3,int)
        self.idle_duration= sm.get_value('idle_duration',5.0,float)
        self.direction_change_interval= sm.get_value('direction_change_interval',20.0,float)
        self.name_offset_y= sm.get_value('name_offset_y',60,int)
        self.font_base_size= sm.get_value('font_base_size',14,int)
        self.show_name= sm.get_value('show_name',False,bool)
        self.sound_volume= sm.get_value('sound_volume',0.5,float)
        self.sound_effect.setVolume(self.sound_volume)
        self.current_language= sm.get_value('current_language','en',str)
        global translations
        translations= load_translation(self.current_language)

    def save_settings(self):
        sm= self.settings_manager
        sm.set_value('pet_name', self.pet_name)
        sm.set_value('selected_mic_index', self.selected_mic_index)
        sm.set_value('activation_threshold', self.activation_threshold)
        sm.set_value('sound_enabled', self.sound_enabled)
        sm.set_value('autostart_enabled', self.autostart_enabled)
        sm.set_value('ground_level', self.ground_level_setting)
        sm.set_value('pet_size', self.pet_size)
        sm.set_value('skin_folder', self.skin_folder)
        sm.set_value('selected_skin', self.selected_skin)
        sm.set_value('duck_speed', self.base_duck_speed)
        sm.set_value('idle_duration', self.idle_duration)
        sm.set_value('direction_change_interval', self.direction_change_interval)
        sm.set_value('current_language', self.current_language)
        sm.set_value('show_name', self.show_name)
        sm.sync()

    def apply_settings(self):
        self.update_duck_name()
        self.update_pet_size(self.pet_size)
        self.update_ground_level(self.ground_level_setting)

        if self.selected_skin is None:
            logging.info("Loading default skin (selected_skin=None).")
            self.resources.load_default_skin(lazy=False)
        elif self.selected_skin and self.selected_skin!= self.resources.current_skin:
            logging.info(f"Load selected skin: {self.selected_skin}")
            self.resources.load_skin(self.selected_skin)
        self.update_duck_skin()

        if self.autostart_enabled:
            self.enable_autostart()
        else:
            self.disable_autostart()

        self.update_name_offset(self.name_offset_y)
        self.update_font_base_size(self.font_base_size)
        self.save_settings()

        self.duck_speed= self.base_duck_speed* (self.pet_size/3)
        self.animation_timer.setInterval(100)

        self.direction_change_timer.stop()
        self.direction_change_timer.start(int(self.direction_change_interval*1000))

        if self.show_name and self.pet_name.strip() and self.isVisible():
            if not self.name_window:
                self.name_window= NameWindow(self)
            else:
                self.name_window.update_label()
                self.name_window.show()
        else:
            if self.name_window:
                self.name_window.hide()

    def update_duck_name(self):
        if not self.pet_name.strip():
            self.pet_name= random.choice(["Кряква","Плуто","Клювик","Гамми","Додко"])
        s= get_seed_from_name(self.pet_name)
        self.random_gen= random.Random(s)
        self.generate_characteristics()
        if self.name_window:
            self.name_window.update_label()

    def update_duck_skin(self):
        self.current_frame= self.resources.get_animation_frame('idle',0)
        if self.current_frame:
            self.duck_width= self.current_frame.width()
            self.duck_height= self.current_frame.height()
            self.resize(self.duck_width,self.duck_height)
            self.update()
        if self.state:
            self.state.exit()
            self.state.enter()

    def update_pet_size(self, ps:int):
        self.pet_size= ps
        self.duck_speed= self.base_duck_speed* (ps/3)
        self.resources.set_pet_size(ps)
        self.resources.load_sprites_now(force_reload=True)

        old_w= self.duck_width
        old_h= self.duck_height
        self.current_frame= self.resources.get_animation_frame('idle',0)
        if not self.current_frame:
            self.current_frame= self.resources.get_default_frame()
        if not self.current_frame:
            self.duck_width= self.duck_height=64
        else:
            self.duck_width= self.current_frame.width()
            self.duck_height= self.current_frame.height()
        dw= self.duck_width- old_w
        dh= self.duck_height- old_h
        self.duck_x-= dw/2
        self.duck_y-= dh/2
        self.resize(self.duck_width,self.duck_height)
        self.move(int(self.duck_x), int(self.duck_y))

        oldc= self.state.__class__ if self.state else IdleState
        self.stop_current_state()
        self.state= oldc(self)
        self.state.enter()
        if hasattr(self.state,"update_frame"):
            self.state.update_frame()

        if self.name_window:
            self.name_window.update_label()

    def update_name_offset(self, offset:int):
        self.name_offset_y= offset
        self.settings_manager.set_value('name_offset_y', offset)
        if self.name_window and self.show_name and self.pet_name.strip():
            self.name_window.update_position()

    def update_font_base_size(self, val:int):
        self.font_base_size= val
        self.settings_manager.set_value('font_base_size', val)
        if self.name_window and self.show_name and self.pet_name.strip():
            self.name_window.update_label()

    def enable_autostart(self):
        if sys.platform=='win32':
            exe_path= os.path.realpath(sys.argv[0])
            try:
                key= winreg.OpenKey(
                    winreg.HKEY_CURRENT_USER,
                    r"Software\Microsoft\Windows\CurrentVersion\Run",
                    0, winreg.KEY_SET_VALUE
                )
                winreg.SetValueEx(key, 'QuackDuck', 0, winreg.REG_SZ, exe_path)
                winreg.CloseKey(key)
            except Exception as e:
                logging.error(f"Failed to enable autostart: {e}")

    def disable_autostart(self):
        if sys.platform=='win32':
            try:
                key= winreg.OpenKey(
                    winreg.HKEY_CURRENT_USER,
                    r"Software\Microsoft\Windows\CurrentVersion\Run",
                    0, winreg.KEY_SET_VALUE
                )
                winreg.DeleteValue(key, 'QuackDuck')
                winreg.CloseKey(key)
            except:
                pass

    def set_skipped_version(self, version:str):
        self.skipped_version= version
        self.settings_manager.set_value('skipped_version', version)
        self.settings_manager.sync()

    def get_scale_factor(self)->float:
        basew, baseh= 1920,1080
        scr= QtWidgets.QApplication.primaryScreen()
        if not scr:
            return 1.0
        sz= scr.size()
        sf= min(sz.width()/basew, sz.height()/ baseh)
        if sf<1.0:
            sf=1.0
        logging.info(f"SCALE FACTOR= {sf}")
        return sf

    def generate_characteristics(self):
        self.movement_speed= random.uniform(0.8,1.5)
        self.base_duck_speed= self.movement_speed
        self.sound_interval_min= random.randint(60,300)
        self.sound_interval_max= random.randint(301,900)
        self.sound_response_probability= random.uniform(0.01,0.25)
        self.playful_behavior_probability= random.uniform(0.1,0.5)
        self.sleep_timeout= (5+ random.random()*10)*60

    def set_default_characteristics(self):
        self.movement_speed=1.25
        self.base_duck_speed=1.25
        self.sound_interval_min=120
        self.sound_interval_max=600
        self.sound_response_probability=0.01
        self.playful_behavior_probability=0.1
        self.sleep_timeout=300

    def check_run_state_trigger(self):
        runf= self.resources.get_animation_frames_by_name("running")
        if runf:
            chance= random.uniform(0.01,0.05)
            if random.random()< chance:
                forbid=(FallingState,DraggingState,ListeningState,JumpingState,PlayfulState,RunningState,AttackingState)
                if not isinstance(self.state, forbid):
                    self.change_state(RunningState(self))

    def can_attack(self)->bool:
        if not isinstance(self.state,(WalkingState, IdleState)):
            return False
        att= self.resources.get_animation_frames_by_name("attack")
        if not att:
            return False
        cpos= QtGui.QCursor.pos()
        center= self.pos()+ self.rect().center()
        base=50
        att_dist= base*(self.pet_size/3)
        dist= ((cpos.x()- center.x())**2+(cpos.y()- center.y())**2)**0.5
        if dist< att_dist:
            if random.random()<0.2:
                if cpos.x()< center.x():
                    self.facing_right= False
                else:
                    self.facing_right= True
                return True
        return False

    def check_attack_trigger(self):
        forbid=(FallingState,JumpingState,AttackingState)
        if not isinstance(self.state, forbid):
            if self.can_attack():
                self.change_state(AttackingState(self))

    def play_random_sound(self):
        if not self.sound_enabled:
            return
        try:
            sfile= self.resources.get_random_sound()
            if not sfile or not os.path.exists(sfile):
                return
            url= QtCore.QUrl.fromLocalFile(sfile)
            self.sound_effect.setSource(url)
            if not self.sound_effect.isLoaded():
                QTimer.singleShot(500, lambda: self.sound_effect.play())
            else:
                self.sound_effect.play()
        except Exception as e:
            logging.error(f"Error playing sound: {e}")

    def init_ui(self):
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint| Qt.WindowType.WindowStaysOnTopHint|Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setCursor(QtGui.QCursor(Qt.CursorShape.PointingHandCursor))
        self.resize(self.duck_width,self.duck_height)
        self.move(int(self.duck_x),int(self.duck_y))
        self.show()

    def setup_timers(self):
        self.animation_timer= QTimer()
        self.animation_timer.timeout.connect(self.update_animation)
        self.animation_timer.start(100)

        self.position_timer= QTimer()
        self.position_timer.timeout.connect(self.update_position)
        self.position_timer.start(20)

        self.sound_timer= QTimer()
        self.sound_timer.timeout.connect(self.play_random_sound)
        self.schedule_next_sound()

        self.sleep_timer= QTimer()
        self.sleep_timer.timeout.connect(self.check_sleep)
        self.sleep_timer.start(10000)

        self.direction_change_timer= QTimer()
        self.direction_change_timer.timeout.connect(self.change_direction)
        self.direction_change_timer.start(int(self.direction_change_interval*1000))

        self.playful_timer= QTimer()
        self.playful_timer.timeout.connect(self.check_playful_state)
        self.playful_timer.start(10*60*1000)

    def schedule_next_sound(self):
        interval= random.randint(120000,600000)
        self.sound_timer.start(interval)

    def update_animation(self):
        try:
            if self.state:
                self.state.update_animation()
        except Exception as e:
            logging.error(f"Error update_animation: {e}")

    def update_position(self):
        try:
            if self.state:
                self.state.update_position()
        except Exception as e:
            logging.error(f"Error update_position: {e}")
            return
        if self.name_window and self.show_name and self.pet_name.strip():
            self.name_window.update_position()

    def start_cursor_shake_detection(self):
        self.cursor_positions=[]
        self.cursor_shake_timer.start(50)

    def stop_cursor_shake_detection(self):
        self.cursor_shake_timer.stop()
        self.cursor_positions=[]

    def check_cursor_shake(self):
        cpos= QtGui.QCursor.pos()
        duck_pos= self.pos()
        duck_center= duck_pos+ self.rect().center()
        dx= cpos.x()- duck_center.x()
        dy= cpos.y()- duck_center.y()
        dist= (dx**2+ dy**2)**0.5
        base_dist=50
        threshold= base_dist*(self.pet_size/3)
        if dist<= threshold:
            now= time.time()
            self.cursor_positions.append((now,cpos))
            self.cursor_positions= [(t,p) for (t,p) in self.cursor_positions if now-t<=1.0]
            if len(self.cursor_positions)>=8:
                direction_changes=0
                for i in range(2,len(self.cursor_positions)):
                    pdx= self.cursor_positions[i-1][1].x()- self.cursor_positions[i-2][1].x()
                    pdy= self.cursor_positions[i-1][1].y()- self.cursor_positions[i-2][1].y()
                    cdx= self.cursor_positions[i][1].x()- self.cursor_positions[i-1][1].x()
                    cdy= self.cursor_positions[i][1].y()- self.cursor_positions[i-1][1].y()
                    if (pdx* cdx<0) or (pdy* cdy<0):
                        direction_changes+=1
                if direction_changes>=4:
                    self.stop_cursor_shake_detection()
                    self.change_state(PlayfulState(self))
        else:
            self.cursor_positions=[]

    def paintEvent(self, event):
        painter= QtGui.QPainter(self)
        if self.current_frame:
            painter.drawPixmap(0,0,self.current_frame)
        if self.debug_mode:
            painter.setPen(QtGui.QPen(QtGui.QColor("red"),2))
            painter.drawRect(0,0,self.duck_width-1,self.duck_height-1)
        painter.end()

    def mousePressEvent(self, event: QMouseEvent):
        self.last_interaction_time= time.time()
        if self.state:
            self.state.handle_mouse_press(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        if self.state:
            self.state.handle_mouse_release(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if self.state:
            self.state.handle_mouse_move(event)

    def get_top_non_opaque_offset(self):
        if not self.current_frame:
            return 0
        img= self.current_frame.toImage()
        w= img.width()
        h= img.height()
        for y in range(h):
            for x in range(w):
                px= img.pixelColor(x,y)
                if px.alpha()>0:
                    return -y
        return 0

    def get_ground_level(self):
        sc= QtGui.QGuiApplication.primaryScreen().geometry()
        off= self.ground_level_setting
        return sc.height()- off

    def update_ground_level(self, new_val:int):
        self.ground_level_setting= new_val
        self.settings_manager.set_value('ground_level',new_val)
        self.ground_level= self.get_ground_level()
        if self.duck_y+ self.duck_height> self.ground_level:
            self.duck_y= self.ground_level- self.duck_height
            self.move(int(self.duck_x),int(self.duck_y))
        elif self.duck_y+ self.duck_height< self.ground_level:
            self.change_state(FallingState(self))

    def check_sleep(self):
        elapsed= time.time()- self.last_interaction_time
        if elapsed>= self.sleep_timeout:
            forbid= (FallingState,DraggingState,ListeningState,JumpingState,PlayfulState)
            if not isinstance(self.state,SleepingState) and not isinstance(self.state, forbid):
                self.stop_current_state()
                self.change_state(SleepingState(self))

    def on_volume_updated(self, volume: int):
        self.current_volume= volume
        if volume> self.activation_threshold:
            self.last_interaction_time= time.time()
            if self.listening_exit_timer:
                self.listening_exit_timer.stop()
                self.listening_exit_timer= None
            if not self.is_listening and not self.listening_entry_timer:
                if not isinstance(self.state,(PlayfulState,JumpingState,LandingState)):
                    self.listening_entry_timer= QTimer()
                    self.listening_entry_timer.setSingleShot(True)
                    self.listening_entry_timer.timeout.connect(self.enter_listening_state)
                    self.listening_entry_timer.start(100)
                else:
                    logging.info("Duck is in playful/jump => skip listening.")
        else:
            if self.listening_entry_timer:
                self.listening_entry_timer.stop()
                self.listening_entry_timer= None
            if self.is_listening and not self.listening_exit_timer:
                self.listening_exit_timer= QTimer()
                self.listening_exit_timer.setSingleShot(True)
                self.listening_exit_timer.timeout.connect(self.exit_listening_state)
                self.listening_exit_timer.start(1000)

    def enter_listening_state(self):
        if not self.is_listening:
            forbid=(JumpingState,FallingState,DraggingState)
            if isinstance(self.state,forbid):
                logging.info("Rejected listening => current state not suitable.")
                return
            self.stop_current_state()
            self.change_state(ListeningState(self))
            self.is_listening= True

    def exit_listening_state(self):
        if self.is_listening:
            self.is_listening= False
            self.change_state(WalkingState(self))

    def open_settings(self):
        if hasattr(self,'settings_manager_window') and self.settings_manager_window:
            if self.settings_manager_window.isVisible():
                self.settings_manager_window.raise_()
                self.settings_manager_window.activateWindow()
            else:
                self.settings_manager_window.show()
        else:
            self.settings_manager_window= SettingsWindow(self)
            self.settings_manager_window.show()
            self.settings_manager_window.destroyed.connect(self.clear_settings_window)

    def clear_settings_window(self):
        self.settings_manager_window= None

    def unstuck_duck(self):
        self.duck_x= (self.screen_width- self.duck_width)//2
        self.duck_y= self.ground_level- self.duck_height
        self.move(int(self.duck_x),int(self.duck_y))
        if not isinstance(self.state,FallingState):
            self.change_state(WalkingState(self))

    def closeEvent(self, event):
        if hasattr(self,'heart_window') and self.heart_window:
            self.heart_window.deleteLater()
        self.microphone_listener.stop()
        self.microphone_listener.wait()
        event.accept()

    def generate_characteristics(self):
        self.movement_speed= random.uniform(0.8,1.5)
        self.base_duck_speed= self.movement_speed
        self.sound_interval_min= random.randint(60,300)
        self.sound_interval_max= random.randint(301,900)
        self.sound_response_probability= random.uniform(0.01,0.25)
        self.playful_behavior_probability= random.uniform(0.1,0.5)
        self.sleep_timeout= (5+ random.random()*10)*60

    def set_default_characteristics(self):
        self.movement_speed=1.25
        self.base_duck_speed=1.25
        self.sound_interval_min=120
        self.sound_interval_max=600
        self.sound_response_probability=0.01
        self.playful_behavior_probability=0.1
        self.sleep_timeout=300

    def check_run_state_trigger(self):
        runf= self.resources.get_animation_frames_by_name("running")
        if runf:
            chance= random.uniform(0.01,0.05)
            if random.random()< chance:
                forbid=(FallingState,DraggingState,ListeningState,JumpingState,PlayfulState,RunningState,AttackingState)
                if not isinstance(self.state, forbid):
                    self.change_state(RunningState(self))

    def can_attack(self)->bool:
        if not isinstance(self.state,(WalkingState, IdleState)):
            return False
        att= self.resources.get_animation_frames_by_name("attack")
        if not att:
            return False
        cpos= QtGui.QCursor.pos()
        center= self.pos()+ self.rect().center()
        base= 50
        att_dist= base*(self.pet_size/3)
        dist= ((cpos.x()- center.x())**2 + (cpos.y()- center.y())**2)**0.5
        if dist< att_dist:
            if random.random()<0.2:
                if cpos.x()< center.x():
                    self.facing_right= False
                else:
                    self.facing_right= True
                return True
        return False

    def check_attack_trigger(self):
        forbid=(FallingState,JumpingState,AttackingState)
        if not isinstance(self.state, forbid):
            if self.can_attack():
                self.change_state(AttackingState(self))

def main():
    app= QApplication(sys.argv)
    if '--cleanup-bak' in sys.argv:
        app_dir= os.path.dirname(os.path.abspath(sys.argv[0]))
        cleanup_bak_files(app_dir)
    app.setQuitOnLastWindowClosed(False)
    sys.excepthook= exception_handler

    duck= Duck()
    duck.show()
    sys.exit(app.exec())

if __name__=="__main__":
    main()
