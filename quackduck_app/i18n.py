import json
import logging
import os
from typing import Dict

from .core import resource_path

DEFAULT_LANGUAGE = "en"
current_language = DEFAULT_LANGUAGE


def load_translation(lang_code: str) -> Dict[str, str]:
    """
    Load the translation JSON for the requested language code.
    """
    lang_path = resource_path(os.path.join("languages", f"lang_{lang_code}.json"))
    try:
        with open(lang_path, "r", encoding="utf-8") as file:
            return json.load(file)
    except FileNotFoundError:
        logging.error("Translation file not found: %s", lang_path)
    except json.JSONDecodeError as exc:
        logging.error("Translation file is invalid: %s (%s)", lang_path, exc)
    return {}


translations: Dict[str, str] = load_translation(DEFAULT_LANGUAGE)


def set_language(lang_code: str) -> None:
    """
    Switch active translations in-place.
    """
    global translations, current_language
    current_language = lang_code
    new_translations = load_translation(lang_code)
    translations.clear()
    translations.update(new_translations)
