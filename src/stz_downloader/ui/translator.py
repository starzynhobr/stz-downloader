"""Runtime i18n for the QML UI.

Exposes ``i18n`` to QML with a ``strings`` map for the current language and a
``language`` property. Changing the language fires ``languageChanged``, which
re-evaluates every QML binding that reads ``i18n.strings.*`` — so the whole UI
re-translates live, no restart needed.

Translations live in ``i18n/translations.json``; add a language by adding a
top-level block there (and a display name in ``_LANGUAGE_NAMES``).
"""
from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import Property, QLocale, QObject, QSettings, Signal, Slot

_FILE = Path(__file__).resolve().parent / "i18n" / "translations.json"
_LANGUAGE_NAMES = {
    "en": "English",
    "pt": "Português",
    "es": "Español",
    "de": "Deutsch",
    "fr": "Français",
}


class Translator(QObject):
    languageChanged = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._data: dict[str, dict] = json.loads(_FILE.read_text("utf-8"))
        self._store = QSettings("stz", "stz-downloader")
        saved = self._store.value("language")
        self._lang = saved if saved in self._data else self._detect()

    def _detect(self) -> str:
        code = QLocale.system().name().split("_")[0]
        return code if code in self._data else "en"

    @Property(str, notify=languageChanged)
    def language(self) -> str:
        return self._lang

    @language.setter
    def language(self, value: str) -> None:
        if value != self._lang and value in self._data:
            self._lang = value
            self._store.setValue("language", value)
            self.languageChanged.emit()

    @Property("QVariantMap", notify=languageChanged)
    def strings(self) -> dict:
        # English as the fallback layer so a missing key never shows blank.
        merged = dict(self._data.get("en", {}))
        merged.update(self._data.get(self._lang, {}))
        return merged

    @Property("QVariantList", constant=True)
    def availableLanguages(self) -> list:  # noqa: N802
        return [
            {"code": code, "name": _LANGUAGE_NAMES.get(code, code)}
            for code in self._data
        ]

    @Slot(str)
    def setLanguage(self, code: str) -> None:  # noqa: N802
        self.language = code
