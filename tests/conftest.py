import os

import pytest
from PyQt6.QtCore import QCoreApplication


@pytest.fixture(scope="session", autouse=True)
def qt_core_app():
    """
    Ensure a Qt core application exists for classes like QSettings/QColor.
    """
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QCoreApplication.instance()
    if app is None:
        app = QCoreApplication([])
    yield app
