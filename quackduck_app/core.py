import hashlib
import inspect
import logging
import os
import shutil
import sys
from pathlib import Path
from typing import Any

from PyQt6.QtGui import QColor

# Core application constants
PROJECT_VERSION = "1.5.2"
GLOBAL_DEBUG_MODE = True
APP_NAME = "QuackDuck"
APP_EXECUTABLE = "quackduck.exe"

# User data folders
CURRENT_DIR = os.path.join(os.path.expanduser("~"), "quackduck", "current")
BACKUP_DIR = os.path.join(os.path.expanduser("~"), "quackduck", "backup")
LOG_FILE = os.path.join(os.path.expanduser("~"), "quackduck.log")

os.makedirs(CURRENT_DIR, exist_ok=True)
os.makedirs(BACKUP_DIR, exist_ok=True)


def configure_logging() -> None:
    """
    Configure application logging once. Subsequent calls are no-ops.
    """
    if getattr(configure_logging, "_configured", False):
        return

    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s %(levelname)s:%(message)s",
        handlers=[
            logging.FileHandler(LOG_FILE, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )
    configure_logging._configured = True


def log_call_stack() -> None:
    """
    Dump the current call stack to the logger to help trace animation/resource issues.
    """
    for frame in inspect.stack()[1:]:
        logging.info("Called by %s in %s at line %s", frame.function, frame.filename, frame.lineno)


def resource_path(relative_path: str) -> str:
    """
    Return an absolute path to a bundled resource, working both in dev mode and after packaging.
    """
    try:
        if getattr(sys, "frozen", False):
            base_path = Path(sys.executable).parent
        else:
            base_path = Path(__file__).resolve().parent.parent
        return str(base_path.joinpath(relative_path))
    except Exception as exc:  # pragma: no cover - defensive fallback
        logging.error("Error calculating path for %s: %s", relative_path, exc)
        return relative_path


def cleanup_bak_files(app_dir: str) -> None:
    """
    Remove any lingering .bak files or folders inside the application directory.
    """
    for item in os.listdir(app_dir):
        if item.endswith(".bak"):
            bak_path = os.path.join(app_dir, item)
            try:
                if os.path.isfile(bak_path) or os.path.islink(bak_path):
                    os.unlink(bak_path)
                elif os.path.isdir(bak_path):
                    shutil.rmtree(bak_path)
                logging.info("Removed leftover .bak: %s", bak_path)
            except Exception as exc:
                logging.error("Could not remove leftover .bak: %s, error=%s", bak_path, exc)


def get_system_accent_color() -> QColor:
    """
    Best effort fetch of the Windows accent color; falls back to QuackDuck cyan elsewhere.
    """
    if sys.platform == "win32":
        try:
            import winreg

            registry = winreg.ConnectRegistry(None, winreg.HKEY_CURRENT_USER)
            key = winreg.OpenKey(registry, r"SOFTWARE\\Microsoft\\Windows\\DWM", 0, winreg.KEY_READ)
            accent_color, _ = winreg.QueryValueEx(key, "AccentColor")
            winreg.CloseKey(key)
            alpha = (accent_color >> 24) & 0xFF
            red = (accent_color >> 16) & 0xFF
            green = (accent_color >> 8) & 0xFF
            blue = accent_color & 0xFF
            return QColor(red, green, blue, alpha)
        except Exception as exc:
            logging.error("Failed to get system accent color: %s", exc)
    return QColor(5, 184, 204)


def get_seed_from_name(name: str) -> int:
    """
    Stable seed derived from a pet name, used to generate repeatable traits.
    """
    digest = hashlib.sha256(name.encode()).hexdigest()
    return int(digest, 16) % (2**32)


def safe_int(value: Any, default: int = 0) -> int:
    """
    Utility conversion helper for stray settings values.
    """
    try:
        return int(value)
    except Exception:
        return default
