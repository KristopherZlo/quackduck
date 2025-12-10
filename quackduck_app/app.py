import logging
import os
import platform
import sys
import traceback

from PyQt6 import QtGui, QtWidgets

from .core import cleanup_bak_files, configure_logging, resource_path
from .duck import Duck
from .i18n import translations


def exception_handler(exctype, value, tb):
    error_message = "".join(traceback.format_exception(exctype, value, tb))
    crash_log_path = os.path.join(os.path.expanduser("~"), "quackduck_crash.log")

    system_info = (
        f"System Information:\n"
        f"OS: {platform.system()} {platform.release()} ({platform.version()})\n"
        f"Machine: {platform.machine()}\n"
        f"Processor: {platform.processor()}\n"
        f"Python Version: {platform.python_version()}\n\n"
    )

    with open(crash_log_path, "w", encoding="utf-8") as crash_log:
        crash_log.write(system_info)
        crash_log.write(error_message)

    logging.error(system_info + error_message)

    if QtWidgets.QApplication.instance() is not None:
        msg = QtWidgets.QMessageBox()
        msg.setIcon(QtWidgets.QMessageBox.Icon.Critical)
        msg.setWindowTitle(translations.get("error_title", "Error!"))
        msg.setText(translations.get("application_error", "The application encountered an error:") + f" \n{value}")
        msg.setDetailedText(system_info + error_message)
        msg.exec()
    else:
        logging.error("An error occurred before QApplication was initialized:")
        logging.error(system_info + error_message)

    sys.exit(1)


def main():
    configure_logging()

    app = QtWidgets.QApplication(sys.argv)

    icon_path = resource_path("assets/images/white-quackduck-visible.ico")
    if os.path.exists(icon_path):
        app.setWindowIcon(QtGui.QIcon(icon_path))
    else:
        logging.error("File icons not found: %s", icon_path)

    if "--cleanup-bak" in sys.argv:
        app_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
        cleanup_bak_files(app_dir)

    app.setQuitOnLastWindowClosed(False)
    sys.excepthook = exception_handler

    duck = Duck()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
