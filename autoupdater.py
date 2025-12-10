# autoupdater.py

import os
import sys
import shutil
import zipfile
import logging
import requests
import subprocess

from PyQt6 import QtCore, QtWidgets


class AutoUpdater:
    """
    AutoUpdater downloads a new onedir PyInstaller build, unpacks it,
    then overwrites the current app folder with the new files. Old files,
    if locked, are renamed to .bak. Finally, it launches the new .exe with '--cleanup-bak'
    so the new process can delete .bak once they're unlocked.
    """

    def __init__(self, current_version, repo_owner, repo_name):
        """
        Args:
            current_version (str): e.g., '1.5.0'
            repo_owner (str): e.g., 'KristopherZlo'
            repo_name (str): e.g., 'quackduck'
        """
        self.current_version = current_version
        self.repo_owner = repo_owner
        self.repo_name = repo_name

    def check_for_updates(self):
        """
        Checks GitHub's latest release via API. Returns release dict if a newer version is found, else None.
        """
        api_url = f"https://api.github.com/repos/{self.repo_owner}/{self.repo_name}/releases/latest"
        try:
            resp = requests.get(api_url, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            latest_version = data["tag_name"].lstrip("v")
            if latest_version > self.current_version:
                return data
            logging.info("No new version found.")
        except Exception as e:
            logging.error(f"Error in check_for_updates: {e}")
            return None
        return None

    def download_and_install(self, release_info, app_dir, progress_callback=None):
        """
        Downloads the new onedir build, extracts it to temp_updater/extracted,
        removes (or renames) old files from app_dir, copies new files there, 
        and removes temp_updater.

        Args:
            release_info (dict): data from GitHub's releases API
            app_dir (str): path to the folder where old quackduck.exe etc. are
            progress_callback (callable): optional function(percent:int)->None
        Returns:
            bool: True if success, False otherwise
        """
        assets = release_info.get("assets", [])
        if not assets:
            logging.error("No assets in this release.")
            return False

        asset = assets[0]  # assume the first asset is our .zip
        download_url = asset["browser_download_url"]
        file_name = asset["name"]  # e.g. "QuackDuck.v1.5.0.zip"

        temp_dir = os.path.join(app_dir, "temp_updater")
        os.makedirs(temp_dir, exist_ok=True)
        zip_path = os.path.join(temp_dir, file_name)

        try:
            # 1) Download
            if not self._download_file(download_url, zip_path, progress_callback):
                return False

            # 2) Extract
            extracted_dir = os.path.join(temp_dir, "extracted")
            os.makedirs(extracted_dir, exist_ok=True)
            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(extracted_dir)

            # 3) Remove/rename old files in app_dir
            self._cleanup_old_app(app_dir)

            # 4) Copy new files from extracted -> app_dir
            build_root = self._find_onedir_root(extracted_dir)
            if not build_root or not os.path.isdir(build_root):
                logging.error("Could not find onedir root in extracted zip.")
                return False
            self._copy_all(build_root, app_dir)

            # 5) Remove temp_updater folder
            self._remove_dir_safely(temp_dir)

            logging.info("Updated in place. New version is installed.")
            return True

        except Exception as e:
            logging.error(f"Error installing update: {e}")
            return False

    def restart_app(self, exe_name, app_dir):
        """
        Launch 'app_dir/exe_name' with '--cleanup-bak', then kill current process.
        The new instance will remove .bak files once it starts up.
        """
        new_exe = os.path.join(app_dir, exe_name)
        logging.info(f"Launching new exe with cleanup flag: {new_exe}")
        try:
            subprocess.Popen([new_exe, '--cleanup-bak'])
        except Exception as e:
            logging.error(f"Failed to launch new exe: {e}")

        os._exit(0)

    # ------------------------------------------
    # Internal helpers
    # ------------------------------------------

    def _download_file(self, url, dest_file, progress_callback=None):
        """
        Download from `url` to `dest_file` in chunks, with optional progress callback.
        """
        try:
            r = requests.get(url, stream=True, timeout=60)
            r.raise_for_status()
            total_size = int(r.headers.get("content-length", 0))
            downloaded = 0
            chunk_size = 8192
            with open(dest_file, "wb") as f:
                for chunk in r.iter_content(chunk_size=chunk_size):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if progress_callback and total_size>0:
                            pct = int(downloaded*100/ total_size)
                            progress_callback(pct)
            return True
        except Exception as e:
            logging.error(f"Error downloading file: {e}")
            return False

    def _cleanup_old_app(self, app_dir):
        """
        Remove old files from app_dir. If locked, rename to .bak so that
        the new version can delete them on next startup (with --cleanup-bak).
        """
        temp_updater_lower = "temp_updater"
        for item in os.listdir(app_dir):
            item_lower = item.lower()
            # skip temp_updater itself
            if item_lower == temp_updater_lower:
                continue

            item_path = os.path.join(app_dir, item)
            try:
                if os.path.isfile(item_path) or os.path.islink(item_path):
                    # e.g. quackduck.exe
                    os.unlink(item_path)
                elif os.path.isdir(item_path):
                    shutil.rmtree(item_path)
            except OSError as e:
                logging.error(f"Could not remove {item_path}: {e}")
                # fallback: rename => .bak
                new_name = item + ".bak"
                new_path = os.path.join(app_dir, new_name)
                try:
                    os.rename(item_path, new_path)
                except Exception as ee:
                    logging.error(f"Could not rename {item_path} => .bak: {ee}")

    def _find_onedir_root(self, extracted_root):
        """
        If there's exactly one subfolder inside extracted_root, return it, else extracted_root.
        """
        items = os.listdir(extracted_root)
        if len(items)==1:
            candidate = os.path.join(extracted_root, items[0])
            if os.path.isdir(candidate):
                return candidate
        return extracted_root

    def _copy_all(self, src, dst):
        """
        Recursively copy all files/folders from src to dst.
        """
        for root, dirs, files in os.walk(src):
            rel = os.path.relpath(root, src)
            target_dir = os.path.join(dst, rel)
            os.makedirs(target_dir, exist_ok=True)
            for file in files:
                shutil.copy2(os.path.join(root, file), os.path.join(target_dir, file))

    def _remove_dir_safely(self, folder):
        """
        Attempt to remove folder fully; ignore errors if locked.
        """
        try:
            shutil.rmtree(folder)
        except Exception as e:
            logging.error(f"Could not remove {folder}: {e}")

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
        layout.addWidget(self.label_info, alignment=QtCore.Qt.AlignmentFlag.AlignCenter)

        self.label_warning = QtWidgets.QLabel("Please do not touch anything!")
        layout.addWidget(self.label_warning, alignment=QtCore.Qt.AlignmentFlag.AlignCenter)

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
