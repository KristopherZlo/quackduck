import os

from PyQt6.QtGui import QColor

from quackduck_app import core


def test_resource_path_points_to_project_file():
    path = core.resource_path(os.path.join("languages", "lang_en.json"))
    assert os.path.isabs(path)
    assert path.endswith(os.path.join("languages", "lang_en.json"))
    assert os.path.exists(path)


def test_resource_path_handles_frozen(monkeypatch, tmp_path):
    fake_executable = tmp_path / "build" / "quackduck.exe"
    fake_executable.parent.mkdir(parents=True, exist_ok=True)
    fake_executable.write_text("", encoding="utf-8")

    monkeypatch.setattr(core.sys, "frozen", True, raising=False)
    monkeypatch.setattr(core.sys, "executable", str(fake_executable))

    result = core.resource_path(os.path.join("assets", "icon.ico"))
    assert result == str(fake_executable.parent / "assets" / "icon.ico")


def test_cleanup_bak_files_removes_only_bak(tmp_path):
    app_dir = tmp_path / "app"
    app_dir.mkdir()
    bak_file = app_dir / "data.bak"
    bak_file.write_text("remove me", encoding="utf-8")
    bak_dir = app_dir / "old.bak"
    bak_dir.mkdir()
    (bak_dir / "file.txt").write_text("nested", encoding="utf-8")
    normal_file = app_dir / "keep.txt"
    normal_file.write_text("stay", encoding="utf-8")

    core.cleanup_bak_files(str(app_dir))

    assert not bak_file.exists()
    assert not bak_dir.exists()
    assert normal_file.exists()


def test_get_system_accent_color_defaults(monkeypatch):
    monkeypatch.setattr(core.sys, "platform", "linux")
    color = core.get_system_accent_color()
    assert isinstance(color, QColor)
    assert (color.red(), color.green(), color.blue()) == (5, 184, 204)


def test_get_seed_from_name_is_stable():
    seed_one = core.get_seed_from_name("Quacky")
    seed_two = core.get_seed_from_name("Quacky")
    assert seed_one == seed_two
    assert isinstance(seed_one, int)


def test_safe_int_handles_invalid_values():
    assert core.safe_int("10") == 10
    assert core.safe_int("not-a-number", default=7) == 7
    assert core.safe_int(None, default=-1) == -1
