import os
import zipfile

import pytest
import requests

from autoupdater import AutoUpdater


def test_find_onedir_root_with_single_folder(tmp_path):
    extracted_root = tmp_path / "extracted"
    extracted_root.mkdir()
    inner = extracted_root / "build"
    inner.mkdir()
    (inner / "file.txt").write_text("content", encoding="utf-8")

    updater = AutoUpdater("1.0.0", "owner", "repo")
    assert updater._find_onedir_root(str(extracted_root)) == str(inner)


def test_cleanup_old_app_removes_everything_but_temp(tmp_path):
    app_dir = tmp_path / "app"
    app_dir.mkdir()
    keep_dir = app_dir / "temp_updater"
    keep_dir.mkdir()
    old_file = app_dir / "old.txt"
    old_file.write_text("old", encoding="utf-8")
    old_folder = app_dir / "old_folder"
    old_folder.mkdir()

    updater = AutoUpdater("1.0.0", "owner", "repo")
    updater._cleanup_old_app(str(app_dir))

    assert keep_dir.exists()
    assert not old_file.exists()
    assert not old_folder.exists()


def test_copy_all_copies_tree(tmp_path):
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    (src / "nested").mkdir(parents=True)
    (src / "nested" / "file.txt").write_text("data", encoding="utf-8")

    updater = AutoUpdater("1.0.0", "owner", "repo")
    updater._copy_all(str(src), str(dst))

    copied = dst / "nested" / "file.txt"
    assert copied.exists()
    assert copied.read_text(encoding="utf-8") == "data"


def test_download_file_success(monkeypatch, tmp_path):
    content = b"abc" * 100

    class DummyResponse:
        def __init__(self, body: bytes):
            self._body = body
            self.headers = {"content-length": str(len(body))}

        def raise_for_status(self):
            return None

        def iter_content(self, chunk_size=8192):
            for index in range(0, len(self._body), chunk_size):
                yield self._body[index:index + chunk_size]

    def fake_get(url, stream=True, timeout=60):
        return DummyResponse(content)

    updater = AutoUpdater("1.0.0", "owner", "repo")
    monkeypatch.setattr(requests, "get", fake_get)

    progress_updates = []
    dest_file = tmp_path / "download.bin"

    assert updater._download_file("http://example.com/file", str(dest_file), progress_updates.append) is True
    assert dest_file.read_bytes() == content
    assert 100 in progress_updates


def test_download_file_failure(monkeypatch, tmp_path):
    def fake_get(*args, **kwargs):
        raise requests.RequestException("boom")

    updater = AutoUpdater("1.0.0", "owner", "repo")
    monkeypatch.setattr(requests, "get", fake_get)

    dest_file = tmp_path / "download.bin"
    assert updater._download_file("http://example.com/file", str(dest_file)) is False
    assert not dest_file.exists()


def test_download_and_install_success(monkeypatch, tmp_path):
    updater = AutoUpdater("1.0.0", "owner", "repo")
    app_dir = tmp_path / "app"
    app_dir.mkdir()
    release_info = {"assets": [{"browser_download_url": "http://example.com/build.zip", "name": "build.zip"}]}

    def fake_download(url, dest_file, progress_callback=None):
        with zipfile.ZipFile(dest_file, "w") as archive:
            archive.writestr("build_root/new.txt", "fresh")
        if progress_callback:
            progress_callback(100)
        return True

    monkeypatch.setattr(updater, "_download_file", fake_download)

    progress_updates = []
    success = updater.download_and_install(release_info, str(app_dir), progress_callback=progress_updates.append)

    assert success is True
    assert (app_dir / "new.txt").exists()
    assert progress_updates[-1] == 100
    assert not (app_dir / "temp_updater").exists()


def test_restart_app_invokes_new_process(monkeypatch, tmp_path):
    updater = AutoUpdater("1.0.0", "owner", "repo")

    called = {}

    def fake_popen(args):
        called["args"] = args

    def fake_exit(code):
        called["exit"] = code
        raise SystemExit

    monkeypatch.setattr("autoupdater.subprocess.Popen", fake_popen)
    monkeypatch.setattr("autoupdater.os._exit", fake_exit)

    exe_name = "quackduck.exe"
    with pytest.raises(SystemExit):
        updater.restart_app(exe_name, str(tmp_path))

    assert called["args"][0] == str(tmp_path / exe_name)
    assert called["exit"] == 0


def test_check_for_updates_handles_errors(monkeypatch):
    def fake_get(*args, **kwargs):
        raise requests.RequestException("failure")

    updater = AutoUpdater("1.0.0", "owner", "repo")
    monkeypatch.setattr(requests, "get", fake_get)

    assert updater.check_for_updates() is None
