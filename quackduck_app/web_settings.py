import base64
import os
from pathlib import Path
from typing import Dict, List, Optional

import webview
from PyQt6 import QtCore, QtGui

from .core import PROJECT_VERSION, resource_path
from .i18n import DEFAULT_LANGUAGE, set_language


def _pixmap_to_data_url(pixmap: QtGui.QPixmap) -> Optional[str]:
    """
    Convert QPixmap to base64 data URL for use in the web UI.
    """
    if pixmap is None or pixmap.isNull():
        return None
    buffer = QtCore.QBuffer()
    buffer.open(QtCore.QIODevice.OpenModeFlag.WriteOnly)
    pixmap.save(buffer, "PNG")
    encoded = base64.b64encode(buffer.data()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


class SettingsAPI:
    """
    Bridge between the web UI and the running duck instance.
    """

    __slots__ = ("_duck", "window", "_main_loop")

    def __init__(self, duck):
        self._duck = duck
        self.window: Optional[webview.Window] = None
        self._main_loop = QtCore.QEventLoop()

    def __dir__(self):
        # Limit reflected members to callable API only.
        return ["get_state", "get_mic_level", "update_settings", "choose_skin_folder"]

    # --- Fetching state ---
    def get_state(self) -> Dict:
        return self._invoke_main(self._collect_state)

    def get_mic_level(self) -> int:
        return self._invoke_main(lambda: int(getattr(self._duck, "current_volume", 0) or 0))

    # --- Updates from UI ---
    def update_settings(self, payload: Dict) -> Dict:
        """
        Apply incoming settings changes and return the new state.
        """
        return self._invoke_main(lambda: self._update_settings(payload))

    def _collect_state(self) -> Dict:
        self._ensure_duck_settings()
        return {
            "version": PROJECT_VERSION,
            "pet_name": getattr(self._duck, "pet_name", ""),
            "show_name": bool(getattr(self._duck, "show_name", False)),
            "pet_size": int(getattr(self._duck, "pet_size", 3)),
            "skin_folder": getattr(self._duck, "skin_folder", "") or "",
            "language": getattr(self._duck, "current_language", DEFAULT_LANGUAGE) or DEFAULT_LANGUAGE,
            "floor_level": int(getattr(self._duck, "ground_level_setting", 0)),
            "name_offset": int(getattr(self._duck, "name_offset_y", 0)),
            "font_size": int(getattr(self._duck, "font_base_size", 16)),
            "autostart": bool(getattr(self._duck, "autostart_enabled", False)),
            "activation_threshold": int(getattr(self._duck, "activation_threshold", 50)),
            "sound_enabled": bool(getattr(self._duck, "sound_enabled", True)),
            "sound_volume": int(float(getattr(self._duck, "sound_volume", 0.5)) * 100),
            "mic_level": int(getattr(self._duck, "current_volume", 0) or 0),
            "idle_frames": self._get_idle_frames(),
        }

    def _update_settings(self, payload: Dict) -> Dict:
        if not isinstance(payload, dict):
            return self._collect_state()

        if "pet_name" in payload:
            self._duck.pet_name = payload["pet_name"] or ""
            if hasattr(self._duck, "update_duck_name"):
                self._duck.update_duck_name()

        if "show_name" in payload:
            self._duck.show_name = bool(payload["show_name"])
            if hasattr(self._duck, "apply_settings"):
                self._duck.apply_settings()

        if "pet_size" in payload:
            try:
                size = int(payload["pet_size"])
                if hasattr(self._duck, "update_pet_size"):
                    self._duck.update_pet_size(size)
            except Exception:
                pass

        if "skin_folder" in payload:
            self._duck.skin_folder = payload["skin_folder"] or ""

        if "language" in payload:
            lang = payload["language"] or DEFAULT_LANGUAGE
            set_language(lang)
            self._duck.current_language = lang

        if "floor_level" in payload:
            try:
                value = int(payload["floor_level"])
                if hasattr(self._duck, "update_ground_level"):
                    self._duck.update_ground_level(value)
            except Exception:
                pass

        if "name_offset" in payload:
            try:
                value = int(payload["name_offset"])
                if hasattr(self._duck, "update_name_offset"):
                    self._duck.update_name_offset(value)
            except Exception:
                pass

        if "font_size" in payload:
            try:
                value = int(payload["font_size"])
                if hasattr(self._duck, "update_font_base_size"):
                    self._duck.update_font_base_size(value)
            except Exception:
                pass

        if "autostart" in payload:
            self._duck.autostart_enabled = bool(payload["autostart"])
            if self._duck.autostart_enabled and hasattr(self._duck, "enable_autostart"):
                self._duck.enable_autostart()
            elif hasattr(self._duck, "disable_autostart"):
                self._duck.disable_autostart()

        if "activation_threshold" in payload:
            try:
                self._duck.activation_threshold = int(payload["activation_threshold"])
            except Exception:
                pass

        if "sound_enabled" in payload:
            self._duck.sound_enabled = bool(payload["sound_enabled"])
            if hasattr(self._duck, "sound_effect"):
                self._duck.sound_effect.setMuted(not self._duck.sound_enabled)

        if "sound_volume" in payload:
            try:
                vol = int(payload["sound_volume"]) / 100.0
                self._duck.sound_volume = vol
                if hasattr(self._duck, "sound_effect"):
                    self._duck.sound_effect.setVolume(vol)
            except Exception:
                pass

        if hasattr(self._duck, "save_settings"):
            self._duck.save_settings()
        if hasattr(self._duck, "apply_settings"):
            self._duck.apply_settings()

        return self._collect_state()

    def _invoke_main(self, func):
        """
        Ensure calls touching Qt objects run on the main Qt thread.
        """
        app = QtCore.QCoreApplication.instance()
        if app is None or QtCore.QThread.currentThread() == app.thread():
            return func()
        result = {}

        def wrapper():
            result["value"] = func()
            self._main_loop.quit()

        QtCore.QTimer.singleShot(0, wrapper)
        self._main_loop.exec()
        return result.get("value")

    def choose_skin_folder(self) -> Optional[str]:
        if not self.window:
            return None
        result = self.window.create_file_dialog(dialog_type=webview.FOLDER_DIALOG)
        if result:
            folder = result[0]
            self._duck.skin_folder = folder
            if hasattr(self._duck, "save_settings"):
                self._duck.save_settings()
            return folder
        return None

    # --- Helpers ---
    def _ensure_duck_settings(self):
        if hasattr(self._duck, "load_settings"):
            try:
                self._duck.load_settings()
            except Exception:
                pass

    def _get_idle_frames(self) -> List[str]:
        frames: List[str] = []
        if hasattr(self._duck, "resources"):
            try:
                self._duck.resources.load_sprites_now()
                pixmaps = self._duck.resources.get_animation_frames_by_name("idle") or []
                for pix in pixmaps[:10]:
                    data_url = _pixmap_to_data_url(pix)
                    if data_url:
                        frames.append(data_url)
            except Exception:
                pass
        return frames


_active_window: Optional[webview.Window] = None


def open_settings_window(duck):
    """
    Launch the settings webview using the HTML template and live app state.
    pywebview requires running on the main thread, so this call is blocking until the window closes.
    """
    global _active_window
    if _active_window is not None:
        try:
            _active_window.show()
            _active_window.focus()
            return
        except Exception:
            _active_window = None

    html_path = Path(resource_path("settings-ui-html-template/index.html")).resolve()
    if not html_path.exists():
        raise FileNotFoundError(f"Settings template not found: {html_path}")

    api = SettingsAPI(duck)
    window = webview.create_window(
        "Quack Duck Settings",
        html_path.as_uri(),
        width=1180,
        height=780,
        js_api=api,
    )
    api.window = window
    _active_window = window
    # Use Edge Chromium backend on Windows if available to avoid Qt conflicts.
    gui_backend = "edgechromium" if os.name == "nt" else None
    webview.start(debug=False, gui=gui_backend)
    _active_window = None
