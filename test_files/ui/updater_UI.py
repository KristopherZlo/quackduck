import sys
from PyQt5 import QtWidgets, QtCore

class AutoUpdater:
    def check_for_updates(self):
        return {"version": "1.1", "url": "https://example.com/update"}

    def download_and_install(self, release_info, app_dir, progress_callback):
        for i in range(101):
            progress_callback(i)
            QtCore.QThread.msleep(50)  # Simulate 5 seconds total
        return True

    def restart_app(self, exe_name, app_dir):
        print(f"Restarting app: {exe_name} in {app_dir}")

class UpdateWorker(QtCore.QThread):
    progress = QtCore.pyqtSignal(int)
    finished = QtCore.pyqtSignal(bool)

    def __init__(self, autoupdater, app_dir, parent=None):
        super().__init__(parent)
        self.autoupdater = autoupdater
        self.app_dir = app_dir

    def run(self):
        release_info = self.autoupdater.check_for_updates()
        success = self.autoupdater.download_and_install(
            release_info=release_info,
            app_dir=self.app_dir,
            progress_callback=self.progress.emit
        )
        self.finished.emit(success)

class UpdateWindow(QtWidgets.QDialog):
    def __init__(self, autoupdater, current_version, app_dir, exe_name="quackduck.exe", parent=None):
        super().__init__(parent)
        self.autoupdater = autoupdater
        self.current_version = current_version
        self.app_dir = app_dir
        self.exe_name = exe_name

        self.setWindowTitle("Quack update")
        self.setFixedSize(400, 120)
        self.setStyleSheet("""
            QDialog {
                background-color: #121212;
            }
            QLabel {
                color: #ffffff;
                font-size: 14px;
            }
            QProgressBar {
                background-color: #1e1e1e;
                border: none;
                text-align: center;
                color: #ffffff;
                height: 16px;
            }
            QProgressBar::chunk {
                background-color: #4caf50;
            }
        """)

        layout = QtWidgets.QVBoxLayout(self)

        self.label_info = QtWidgets.QLabel("Installing the update...")
        layout.addWidget(self.label_info, alignment=QtCore.Qt.AlignCenter)

        self.label_warning = QtWidgets.QLabel("Please do not touch anything!")
        layout.addWidget(self.label_warning, alignment=QtCore.Qt.AlignCenter)

        self.progress_bar = QtWidgets.QProgressBar()
        self.progress_bar.setRange(0, 100)
        layout.addWidget(self.progress_bar)

        self.setLayout(layout)

        self.worker = UpdateWorker(autoupdater, app_dir)
        self.worker.progress.connect(self.progress_bar.setValue)
        self.worker.finished.connect(self.on_update_finished)

        self.worker.start()

    def on_update_finished(self, success):
        if not success:
            QtWidgets.QMessageBox.critical(self, "Error", "Failed to install update.")
            self.close()
            return

        self.progress_bar.setValue(100)
        self.label_info.setText("Successfully installed!")
        QtWidgets.QMessageBox.information(
            self,
            "Success",
            "Update installed. Restarting the application..."
        )
        self.autoupdater.restart_app(self.exe_name, self.app_dir)

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)

    autoupdater = AutoUpdater()
    current_version = "1.0"
    app_dir = "/path/to/app"

    window = UpdateWindow(autoupdater, current_version, app_dir)
    window.show()

    sys.exit(app.exec_())
