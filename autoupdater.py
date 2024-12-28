import os
import logging
import shutil
import tempfile
import zipfile
import requests

class AutoUpdater:
    """
    An autoupdater class for checking, downloading and installing updates from GitHub,
    then automatically restarting the application (killing old process).
    """

    def __init__(self, current_version, repo_owner, repo_name):
        """
        Arguments:
            current_version (str): current version of the application, e.g. '1.5.0'
            repo_owner (str): repository owner (e.g. 'KristopherZlo')
            repo_name (str): repository name (e.g. 'quackduck')
        """
        self.current_version = current_version
        self.repo_owner = repo_owner
        self.repo_name = repo_name

    def check_for_updates(self):
        """
        Returns info about the latest version on GitHub if it's newer than current_version.
        Otherwise returns None.
        """
        api_url = f"https://api.github.com/repos/{self.repo_owner}/{self.repo_name}/releases/latest"
        try:
            response = requests.get(api_url, timeout=10)
            if response.status_code == 200:
                latest_release = response.json()
                latest_version = latest_release["tag_name"].lstrip("v")
                if latest_version > self.current_version:
                    return latest_release
                logging.info("No new version found.")
            else:
                logging.warning(f"Failed to fetch release info. Status: {response.status_code}")
        except Exception as e:
            logging.error(f"Error in check_for_updates: {e}")
        return None

    def download_and_install(self, release_info, current_dir, backup_dir):
        """
        Downloads a ZIP from GitHub, makes a backup of current files, installs the new version,
        and if successful, restarts the application (killing the old process).

        Arguments:
            release_info (dict): JSON release data from GitHub
            current_dir (str): path to the current folder with application files
            backup_dir (str): path to the backup folder
        """
        assets = release_info.get("assets", [])
        if not assets:
            logging.error("No assets in this release.")
            return False

        asset = assets[0]
        download_url = asset["browser_download_url"]
        file_name = asset["name"]

        temp_dir = tempfile.mkdtemp()
        zip_path = os.path.join(temp_dir, file_name)

        try:
            logging.info(f"Downloading update from: {download_url}")
            with requests.get(download_url, stream=True, timeout=30) as r:
                r.raise_for_status()
                with open(zip_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)

            logging.info("Backing up current version...")
            self.backup_current_version(current_dir, backup_dir)

            extract_dir = os.path.join(temp_dir, "extracted")
            os.makedirs(extract_dir, exist_ok=True)
            logging.info("Unpacking update ZIP...")
            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(extract_dir)

            logging.info("Installing new version...")
            if not self.install_new_version(extract_dir, current_dir):
                logging.error("Failed to install new files, restoring backup.")
                self.restore_backup_version(current_dir, backup_dir)
                return False

            logging.info("Successfully installed new version. Attempting to restart...")
            exe_path = os.path.join(current_dir, "quackduck.exe")
            self.restart_app(exe_path)
            return True

        except Exception as e:
            logging.error(f"Error while downloading/installing: {e}")
            self.restore_backup_version(current_dir, backup_dir)
            return False
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def backup_current_version(self, current_dir, backup_dir):
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir, exist_ok=True)

        # Clear backup_dir
        for f in os.listdir(backup_dir):
            p = os.path.join(backup_dir, f)
            if os.path.isfile(p) or os.path.islink(p):
                os.unlink(p)
            elif os.path.isdir(p):
                shutil.rmtree(p)

        # Copy everything from current to backup
        for item in os.listdir(current_dir):
            s = os.path.join(current_dir, item)
            d = os.path.join(backup_dir, item)
            if os.path.isdir(s):
                shutil.copytree(s, d, dirs_exist_ok=True)
            else:
                shutil.copy2(s, d)

    def restore_backup_version(self, current_dir, backup_dir):
        # Clear current_dir
        for f in os.listdir(current_dir):
            p = os.path.join(current_dir, f)
            if os.path.isfile(p) or os.path.islink(p):
                os.unlink(p)
            elif os.path.isdir(p):
                shutil.rmtree(p)
        # Copy from backup_dir back to current_dir
        for item in os.listdir(backup_dir):
            s = os.path.join(backup_dir, item)
            d = os.path.join(current_dir, item)
            if os.path.isdir(s):
                shutil.copytree(s, d, dirs_exist_ok=True)
            else:
                shutil.copy2(s, d)

    def install_new_version(self, extract_dir, current_dir):
        try:
            # Remove all files/folders in current_dir
            for f in os.listdir(current_dir):
                p = os.path.join(current_dir, f)
                if os.path.isfile(p) or os.path.islink(p):
                    os.unlink(p)
                elif os.path.isdir(p):
                    shutil.rmtree(p)
            # Copy everything from extract_dir to current_dir
            for item in os.listdir(extract_dir):
                s = os.path.join(extract_dir, item)
                d = os.path.join(current_dir, item)
                if os.path.isdir(s):
                    shutil.copytree(s, d, dirs_exist_ok=True)
                else:
                    shutil.copy2(s, d)
            return True
        except Exception as e:
            logging.error(f"Error installing new version: {e}")
            return False

    def restart_app(self, exe_path):
        """
        Launch the new exe file and forcibly kill the current process.
        """
        try:
            logging.info(f"Launching new version: {exe_path}")
            os.startfile(exe_path)  # Windows-only
            logging.info("Terminating old process now.")
            # This kills the current process abruptly:
            os._exit(0)
        except Exception as e:
            logging.error(f"Error while trying to restart: {e}")
