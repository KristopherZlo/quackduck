from PyQt6 import QtCore

from quackduck_app.settings_store import SettingsManager


def test_settings_manager_roundtrip(tmp_path):
    manager = SettingsManager("test_org", "test_app")
    manager._settings = QtCore.QSettings(str(tmp_path / "settings.ini"), QtCore.QSettings.Format.IniFormat)

    manager.set_value("volume", 42)
    assert manager.get_value("volume", default=0, value_type=int) == 42

    manager.clear()
    assert manager.get_value("volume", default="missing", value_type=str) == "missing"


def test_settings_manager_sync_writes_file(tmp_path):
    settings_path = tmp_path / "persist.ini"
    manager = SettingsManager("test_org_sync", "test_app_sync")
    manager._settings = QtCore.QSettings(str(settings_path), QtCore.QSettings.Format.IniFormat)

    manager.set_value("theme", "dark")
    manager.sync()

    assert settings_path.exists()
