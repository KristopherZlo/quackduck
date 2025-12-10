import json
import logging
import os
import random
import shutil
import tempfile
import zipfile
from typing import Dict, List, Optional, Tuple

from PyQt6 import QtGui
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap

from .core import log_call_stack, resource_path


class ResourceManager:
    """
    Manages animations, sounds, and skins for the duck.
    """

    def __init__(self, scale_factor: float, pet_size: int = 3) -> None:
        self.assets_dir = resource_path("assets")
        self.skins_dir = os.path.join(self.assets_dir, "skins")
        self.current_skin = "default"
        self.current_skin_temp_dir = None
        self.animations: Dict[str, List[QPixmap]] = {}
        self.sounds: List[str] = []
        self.scale_factor = scale_factor
        self.pet_size = pet_size

        self.default_animations_config = {
            "idle": ["0:0"],
            "walk": ["1:0", "1:1", "1:2", "1:3", "1:4", "1:5"],
            "listen": ["2:1"],
            "fall": ["2:3"],
            "jump": ["2:0", "2:1", "2:2", "2:3"],
            "sleep": ["0:1"],
            "sleep_transition": ["2:1"],
        }

        self.spritesheet_path: Optional[str] = None
        self.frame_width = 32
        self.frame_height = 32
        self.animations_config = self.default_animations_config.copy()
        self.sound_files: List[str] = []
        self.loaded_spritesheet: Optional[QPixmap] = None
        self.loaded_frames_cache: Dict[Tuple[int, int], QPixmap] = {}
        self.sprites_loaded = False
        self.sounds_loaded = False

        self.load_default_skin(lazy=False)

    def load_skin_frames_for_preview(self, is_default=False, skin_path=None):
        try:
            if is_default:
                animations_config = self.default_animations_config
                spritesheet_path = os.path.join(self.skins_dir, "default", "spritesheet.png")
                frame_width, frame_height = 32, 32
            else:
                with zipfile.ZipFile(skin_path, "r") as zip_ref:
                    temp_dir = tempfile.mkdtemp()
                    zip_ref.extractall(temp_dir)

                    config_path = os.path.join(temp_dir, "config.json")
                    with open(config_path, "r") as f:
                        config = json.load(f)

                    frame_width = config.get("frame_width")
                    frame_height = config.get("frame_height")
                    animations_config = config.get("animations", {})
                    spritesheet_path = os.path.join(temp_dir, config.get("spritesheet", ""))

            if not os.path.exists(spritesheet_path):
                logging.error("Spritesheet not found: %s", spritesheet_path)
                return []

            spritesheet = QtGui.QPixmap(spritesheet_path)
            if spritesheet.isNull():
                logging.error("Failed to load spritesheet: %s", spritesheet_path)
                return []

            idle_frames = []
            for frame_str in animations_config.get("idle", []):
                try:
                    row, col = map(int, frame_str.split(":"))
                    x = col * frame_width
                    y = row * frame_height
                    frame = spritesheet.copy(x, y, frame_width, frame_height)
                    idle_frames.append(frame)
                except Exception as exc:
                    logging.error("Error extracting frame %s: %s", frame_str, exc)
            return idle_frames
        except Exception as exc:
            logging.error("Error loading frames for preview: %s", exc)
            return []

    def cleanup_temp_dir(self) -> None:
        if self.current_skin_temp_dir and os.path.exists(self.current_skin_temp_dir):
            try:
                shutil.rmtree(self.current_skin_temp_dir)
                logging.info("Temporary skin directory %s removed.", self.current_skin_temp_dir)
            except Exception as exc:
                logging.error("Failed to remove temporary skin directory %s: %s", self.current_skin_temp_dir, exc)
            self.current_skin_temp_dir = None
        self.animations.clear()
        self.sounds.clear()
        self.loaded_spritesheet = None
        self.loaded_frames_cache.clear()
        self.sprites_loaded = False
        self.sounds_loaded = False

    def validate_config(self, config: dict) -> bool:
        required_keys = ["spritesheet", "frame_width", "frame_height", "animations"]
        for key in required_keys:
            if key not in config:
                logging.error("Config is invalid: missing '%s'", key)
                return False
        if not isinstance(config["animations"], dict):
            logging.error("Config is invalid: 'animations' is not a dict")
            return False
        return True

    def load_default_skin(self, lazy: bool = False) -> None:
        logging.info("Default skin loading triggered.")
        log_call_stack()

        self.cleanup_temp_dir()
        self.current_skin = "default"
        skin_path = os.path.join(self.skins_dir, "default")
        self.spritesheet_path = os.path.join(skin_path, "spritesheet.png")
        self.frame_width = 32
        self.frame_height = 32
        self.animations_config = self.default_animations_config.copy()
        self.sound_files = [os.path.join(skin_path, "wuak.wav")]

        if not lazy:
            self.load_sprites_now()
            self.load_sounds_now()

    def load_spritesheet_if_needed(self) -> None:
        if self.loaded_spritesheet is None and self.spritesheet_path:
            if hasattr(self, "_loading_failed") and self._loading_failed:
                logging.error("Skipping spritesheet loading due to previous failures.")
                return

            if not os.path.exists(self.spritesheet_path):
                logging.error("Spritesheet path does not exist: %s", self.spritesheet_path)
                self._loading_failed = True
                return

            logging.info("Attempting to load spritesheet from: %s", self.spritesheet_path)
            spritesheet = QtGui.QPixmap(self.spritesheet_path)
            if spritesheet.isNull():
                logging.error("Failed to load spritesheet image: %s", self.spritesheet_path)
                self._loading_failed = True
                return

            self.loaded_spritesheet = spritesheet
            self._loading_failed = False

    def load_sprites_now(self, force_reload: bool = False) -> None:
        if self.sprites_loaded and not force_reload:
            logging.info("Sprites already loaded. Skipping reload.")
            return
        if getattr(self, "_sprites_failed", False) and not force_reload:
            logging.error("Sprites failed to load previously. Skipping further attempts.")
            return
        if force_reload:
            self._sprites_failed = False
            self._load_attempts = 0
        if hasattr(self, "_load_attempts") and self._load_attempts >= 3:
            logging.error("Maximum attempts to load sprites reached.")
            self._sprites_failed = True
            return

        self._load_attempts = getattr(self, "_load_attempts", 0) + 1
        logging.info("Loading sprites (attempt %s)...", self._load_attempts)

        self.load_spritesheet_if_needed()
        if self.loaded_spritesheet is None:
            logging.error("Spritesheet not loaded. Skipping animations.")
            self._sprites_failed = True
            return

        self.animations.clear()
        for anim_name, frame_list in self.animations_config.items():
            frames = self.get_animation_frames(lambda r, c: self.get_frame(r, c), frame_list)
            if frames:
                self.animations[anim_name] = frames
                logging.info("Loaded animation '%s' with %s frames.", anim_name, len(frames))
            else:
                logging.warning("No frames found for animation '%s'.", anim_name)

        if not self.animations:
            logging.error("No animations loaded. Marking sprites as failed.")
            self._sprites_failed = True
        else:
            self.sprites_loaded = True

    def load_sounds_now(self) -> None:
        if self.sounds_loaded:
            return
        self.sounds = self.sound_files.copy()
        logging.info("Loaded %s sound files.", len(self.sounds))
        self.sounds_loaded = True

    def load_skin(self, skin_file: str) -> bool:
        self.cleanup_temp_dir()

        if not (os.path.isfile(skin_file) and skin_file.endswith(".zip")):
            logging.error("Invalid skin file: %s", skin_file)
            self.load_default_skin(lazy=True)
            return False

        try:
            with zipfile.ZipFile(skin_file, "r") as zip_ref:
                if "config.json" not in zip_ref.namelist():
                    logging.error("Skin %s does not contain config.json.", skin_file)
                    self.load_default_skin(lazy=True)
                    return False

                temp_dir = tempfile.mkdtemp()
                self.current_skin_temp_dir = temp_dir
                logging.info("Temporary skin files extracted to: %s", temp_dir)
                zip_ref.extractall(temp_dir)

                config_path = os.path.join(temp_dir, "config.json")
                with open(config_path, "r") as file:
                    config = json.load(file)

                if not self.validate_config(config):
                    logging.error("Skin config is invalid, fallback to default skin.")
                    self.load_default_skin(lazy=True)
                    return False

                spritesheet_name = config.get("spritesheet")
                frame_width = config.get("frame_width")
                frame_height = config.get("frame_height")
                animations = config.get("animations", {})

                spritesheet_path = os.path.join(temp_dir, spritesheet_name)
                if not os.path.exists(spritesheet_path):
                    logging.error("Spritesheet %s does not exist.", spritesheet_name)
                    self.load_default_skin(lazy=True)
                    return False

                sound_names = config.get("sound", [])
                if isinstance(sound_names, str):
                    sound_names = [sound_names]

                sound_paths = []
                for sound_name in sound_names:
                    sound_path = os.path.join(temp_dir, sound_name)
                    if os.path.exists(sound_path) and sound_name.endswith(".wav"):
                        sound_paths.append(sound_path)
                    else:
                        logging.warning("Sound file %s is not in WAV format or does not exist.", sound_name)

                self.spritesheet_path = spritesheet_path
                self.sound_files = sound_paths
                self.frame_width = frame_width
                self.frame_height = frame_height
                self.animations_config = animations
                self.current_skin = skin_file
                return True
        except Exception as exc:
            logging.error("Failed to load skin %s: %s", skin_file, exc)
            self.load_default_skin(lazy=True)
            return False

    def set_pet_size(self, pet_size: int) -> None:
        self.pet_size = pet_size
        self.loaded_frames_cache.clear()
        self.sprites_loaded = False
        self.animations.clear()
        self.loaded_spritesheet = None

    def get_frame(self, row: int, col: int) -> QPixmap:
        if self.loaded_spritesheet is None:
            self.load_spritesheet_if_needed()
            if self.loaded_spritesheet is None:
                return QPixmap()

        key = (row, col)
        if key in self.loaded_frames_cache:
            return self.loaded_frames_cache[key]

        spritesheet = self.loaded_spritesheet
        frame = spritesheet.copy(col * self.frame_width, row * self.frame_height, self.frame_width, self.frame_height)
        new_width = self.frame_width * self.pet_size
        new_height = self.frame_height * self.pet_size
        frame = frame.scaled(
            new_width,
            new_height,
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.FastTransformation,
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
        frame = self.get_animation_frame("idle", 0)
        if frame:
            return frame
        for frames in self.animations.values():
            if frames:
                return frames[0]
        return None

    def get_idle_animations(self) -> List[str]:
        if not self.sprites_loaded:
            self.load_sprites_now()
        return [name for name in self.animations.keys() if name.startswith("idle")]

    def load_idle_frames_from_skin(self, skin_file: str) -> Optional[List[QPixmap]]:
        try:
            with zipfile.ZipFile(skin_file, "r") as zip_ref:
                if "config.json" not in zip_ref.namelist():
                    logging.error("Skin %s does not contain config.json.", skin_file)
                    return None

                with tempfile.TemporaryDirectory() as temp_dir:
                    logging.info("Temporary skin files extracted to: %s", temp_dir)
                    zip_ref.extractall(temp_dir)

                    config_path = os.path.join(temp_dir, "config.json")
                    with open(config_path, "r") as file:
                        config = json.load(file)

                    if not all(key in config for key in ("spritesheet", "frame_width", "frame_height", "animations")):
                        logging.error("Config file is incomplete in %s.", skin_file)
                        return None

                    animations = config.get("animations", {})
                    idle_animation_keys = [key for key in animations.keys() if key.startswith("idle")]
                    if not idle_animation_keys:
                        logging.error("No idle animation in %s.", skin_file)
                        return None

                    idle_animation_key = idle_animation_keys[0]
                    frame_list = animations[idle_animation_key]

                    spritesheet_name = config.get("spritesheet")
                    frame_width = config.get("frame_width")
                    frame_height = config.get("frame_height")

                    spritesheet_path = os.path.join(temp_dir, spritesheet_name)
                    spritesheet = QtGui.QPixmap(spritesheet_path)
                    if spritesheet.isNull():
                        logging.error("Failed to load spritesheet for preview.")
                        return None

                    frames = []
                    for frame_str in frame_list:
                        row_col = frame_str.split(":")
                        if len(row_col) == 2:
                            try:
                                row = int(row_col[0])
                                col = int(row_col[1])
                                frame = spritesheet.copy(col * frame_width, row * frame_height, frame_width, frame_height)
                                frames.append(frame)
                            except ValueError:
                                logging.error("Incorrect frame format: %s", frame_str)
                    return frames
        except Exception as exc:
            logging.error("Failed to load skin %s: %s", skin_file, exc)
            return None

    def get_animation_frames(self, get_frame_func, frame_list: List[str]) -> List[QPixmap]:
        frames = []
        for frame_str in frame_list:
            row_col = frame_str.split(":")
            if len(row_col) == 2:
                try:
                    row = int(row_col[0])
                    col = int(row_col[1])
                    frame = get_frame_func(row, col)
                    if not frame.isNull():
                        frames.append(frame)
                except ValueError:
                    logging.error("Incorrect frame format: %s", frame_str)
        return frames

    def get_random_sound(self) -> Optional[str]:
        if not self.sounds_loaded:
            self.load_sounds_now()
        if not self.sounds:
            logging.error("No sound files loaded.")
            return None

        sound_file = random.choice(self.sounds)
        if not os.path.exists(sound_file):
            logging.warning("Sound file %s does not exist.", sound_file)
            if self.current_skin_temp_dir:
                source_sound_path = os.path.join(self.current_skin_temp_dir, os.path.basename(sound_file))
                if os.path.exists(source_sound_path):
                    try:
                        shutil.copy(source_sound_path, sound_file)
                        logging.info("Copied sound file from %s to %s.", source_sound_path, sound_file)
                    except Exception as exc:
                        logging.error("Failed to copy sound file from skin: %s", exc)
                        return None
                else:
                    logging.error("Source sound file %s does not exist.", source_sound_path)
                    return None
            else:
                logging.error("Current skin temporary directory is not set.")
                return None

        return sound_file

    def __del__(self):
        self.cleanup_temp_dir()
