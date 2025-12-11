import json
import logging
import os
from pathlib import Path
from typing import Dict

from .core import resource_path

DEFAULT_LANGUAGE = "en"
LANGUAGE_DIR = Path(resource_path("languages")).resolve()
ALLOWED_LANGUAGES = {DEFAULT_LANGUAGE, "ru"}
current_language = DEFAULT_LANGUAGE
_translation_cache: Dict[str, Dict[str, str]] = {}


def _normalize_lang_code(lang_code: str) -> str:
    """
    Lowercase and vet the requested language code against the allow list.
    """
    safe_code = (lang_code or DEFAULT_LANGUAGE).split(".")[0].strip().lower()
    if safe_code in ALLOWED_LANGUAGES:
        return safe_code
    logging.warning("Unsupported language '%s'. Falling back to '%s'.", lang_code, DEFAULT_LANGUAGE)
    return DEFAULT_LANGUAGE


def _is_safe_path(path: Path) -> bool:
    """
    Ensure the resolved path stays within the languages directory.
    """
    try:
        path.relative_to(LANGUAGE_DIR)
        return True
    except ValueError:
        return False


def _read_translation_file(lang_code: str) -> Dict[str, str]:
    """
    Read a translation file from disk with safety checks.
    """
    lang_path = (LANGUAGE_DIR / f"lang_{lang_code}.json").resolve(strict=False)
    if not _is_safe_path(lang_path):
        logging.error("Blocked unsafe translation path: %s", lang_path)
        return {}
    try:
        with open(lang_path, "r", encoding="utf-8") as file:
            data = json.load(file)
            if not isinstance(data, dict):
                logging.error("Translation file root must be an object: %s", lang_path)
                return {}
            return data
    except FileNotFoundError:
        logging.error("Translation file not found: %s", lang_path)
    except json.JSONDecodeError as exc:
        logging.error("Translation file is invalid: %s (%s)", lang_path, exc)
    except Exception as exc:  # pragma: no cover - defensive
        logging.error("Unexpected error reading translation file %s: %s", lang_path, exc)
    return {}


def load_translation(lang_code: str) -> Dict[str, str]:
    """
    Load the translation JSON for the requested language code with caching and safe fallback.
    """
    safe_lang = _normalize_lang_code(lang_code)
    original_lang = safe_lang
    if safe_lang in _translation_cache:
        return _translation_cache[safe_lang]

    translations_for_lang = _read_translation_file(safe_lang)
    if not translations_for_lang and safe_lang != DEFAULT_LANGUAGE:
        logging.warning(
            "Falling back to default language '%s' after load failure for '%s'.",
            DEFAULT_LANGUAGE,
            safe_lang,
        )
        translations_for_lang = _read_translation_file(DEFAULT_LANGUAGE)
        safe_lang = DEFAULT_LANGUAGE

    _translation_cache[safe_lang] = translations_for_lang
    if original_lang not in _translation_cache:
        _translation_cache[original_lang] = translations_for_lang
    return _translation_cache[safe_lang]


translations: Dict[str, str] = dict(load_translation(DEFAULT_LANGUAGE))


def set_language(lang_code: str) -> None:
    """
    Switch active translations in-place.
    """
    global translations, current_language
    safe_lang = _normalize_lang_code(lang_code)
    new_translations = load_translation(safe_lang)
    if not new_translations and safe_lang != DEFAULT_LANGUAGE:
        safe_lang = DEFAULT_LANGUAGE
        new_translations = load_translation(DEFAULT_LANGUAGE)

    if not new_translations:
        logging.error("No translations available; keeping current language '%s'.", current_language)
        return

    translations.clear()
    translations.update(new_translations)
    current_language = safe_lang
