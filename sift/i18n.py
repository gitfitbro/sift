"""Internationalization support for sift using gettext.

Usage:
    from sift.i18n import _

    console.print(_("Session created successfully"))
    console.print(_("No template found: {name}").format(name=template))

Currently ships with English only. The infrastructure allows community
translations to be added by creating .po files in sift/locales/.

Translation workflow:
    pybabel extract -o sift/locales/sift.pot sift/
    pybabel init -l es -i sift/locales/sift.pot -d sift/locales
    pybabel update -i sift/locales/sift.pot -d sift/locales
    pybabel compile -d sift/locales
"""

import gettext
import os
from pathlib import Path

LOCALE_DIR = Path(__file__).parent / "locales"


def setup_i18n(lang: str | None = None) -> gettext.NullTranslations:
    """Initialize translations. Falls back to English passthrough.

    Args:
        lang: Language code (e.g. 'es', 'fr', 'de'). Auto-detects from
              SIFT_LANG env var or system locale if not specified.

    Returns:
        A gettext translations object.
    """
    lang = lang or os.environ.get("SIFT_LANG")

    if lang:
        languages = [lang]
    else:
        languages = None  # gettext will use system locale

    try:
        translations = gettext.translation(
            "sift",
            localedir=str(LOCALE_DIR),
            languages=languages,
            fallback=True,
        )
    except Exception:
        translations = gettext.NullTranslations()

    return translations


# Module-level translation function
_translations = setup_i18n()
_ = _translations.gettext
ngettext = _translations.ngettext
