import json

from stz_downloader.settings import DEFAULT_EXTENSIONS, SettingsStore


def test_fresh_settings_use_the_bundled_extension_defaults(tmp_path):
    store = SettingsStore(tmp_path / "missing" / "settings.json")

    assert store.settings.extensions == DEFAULT_EXTENSIONS
    assert len(store.settings.extensions) == 33
    assert ".pdf" in store.settings.extensions


def test_saved_extension_customization_is_not_overwritten(tmp_path):
    path = tmp_path / "settings.json"
    custom = [extension for extension in DEFAULT_EXTENSIONS if extension != ".pdf"]
    path.write_text(json.dumps({"extensions": custom}), encoding="utf-8")

    store = SettingsStore(path)

    assert len(store.settings.extensions) == 32
    assert store.settings.extensions == custom


def test_fresh_default_lists_are_independent(tmp_path):
    first = SettingsStore(tmp_path / "first.json")
    second = SettingsStore(tmp_path / "second.json")

    first.settings.extensions.pop()

    assert second.settings.extensions == DEFAULT_EXTENSIONS
