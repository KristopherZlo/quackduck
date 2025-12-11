import json
import logging
from pathlib import Path

import pytest

from quackduck_app import i18n


@pytest.fixture
def temp_languages(monkeypatch, tmp_path):
    original_translations = dict(i18n.translations)
    lang_dir = tmp_path / "languages"
    lang_dir.mkdir()

    (lang_dir / "lang_en.json").write_text(json.dumps({"greet": "hi"}), encoding="utf-8")
    (lang_dir / "lang_ru.json").write_text(json.dumps({"greet": "privet"}), encoding="utf-8")

    monkeypatch.setattr(i18n, "LANGUAGE_DIR", lang_dir)
    monkeypatch.setattr(i18n, "_translation_cache", {})
    i18n.current_language = i18n.DEFAULT_LANGUAGE
    i18n.translations.clear()
    i18n.translations.update(i18n.load_translation(i18n.DEFAULT_LANGUAGE))

    yield lang_dir

    i18n.translations.clear()
    i18n.translations.update(original_translations)
    i18n.current_language = i18n.DEFAULT_LANGUAGE


def test_normalize_lang_code_supported(temp_languages):
    assert i18n._normalize_lang_code("RU.UTF-8") == "ru"


def test_normalize_lang_code_unsupported_fallback(temp_languages, caplog):
    with caplog.at_level(logging.WARNING):
        normalized = i18n._normalize_lang_code("de")
    assert normalized == i18n.DEFAULT_LANGUAGE
    assert "Unsupported language" in caplog.text


def test_is_safe_path_rejects_outside(temp_languages):
    outside_path = Path(temp_languages).parent / "other" / "lang_en.json"
    assert i18n._is_safe_path(outside_path) is False


def test_read_translation_file_invalid_json(temp_languages, caplog):
    bad_file = temp_languages / "lang_ru.json"
    bad_file.write_text("{invalid", encoding="utf-8")

    with caplog.at_level(logging.ERROR):
        data = i18n._read_translation_file("ru")

    assert data == {}
    assert "Translation file is invalid" in caplog.text


def test_load_translation_falls_back_to_default(temp_languages, caplog):
    (temp_languages / "lang_ru.json").unlink()

    with caplog.at_level(logging.WARNING):
        translations = i18n.load_translation("ru")

    assert translations == i18n.load_translation("en")
    assert "Falling back to default language" in caplog.text


def test_load_translation_caches_results(temp_languages):
    first = i18n.load_translation("en")
    second = i18n.load_translation("en")
    assert first is second


def test_set_language_updates_globals(temp_languages):
    i18n.set_language("ru")
    assert i18n.current_language == "ru"
    assert i18n.translations.get("greet") == "privet"
