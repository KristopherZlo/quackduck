from PyQt6 import QtCore


class SettingsManager:
    """
    Thin wrapper over QSettings with explicit typing helpers.
    """

    def __init__(self, organization: str = "zl0yxp", application: str = "QuackDuck") -> None:
        self._settings = QtCore.QSettings(organization, application)

    def get_value(self, key: str, default=None, value_type=None):
        return self._settings.value(key, defaultValue=default, type=value_type)

    def set_value(self, key: str, value) -> None:
        self._settings.setValue(key, value)

    def clear(self) -> None:
        self._settings.clear()

    def sync(self) -> None:
        self._settings.sync()
