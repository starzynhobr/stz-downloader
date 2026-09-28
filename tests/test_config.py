from stz_downloader import config


def test_runtime_aria2_defaults_survive_without_pyproject(tmp_path, monkeypatch):
    """PyInstaller has no repository pyproject; performance defaults must remain."""
    empty_bundle = tmp_path / "bundle"
    empty_bundle.mkdir()
    monkeypatch.setattr(config, "_project_root", lambda: empty_bundle)
    monkeypatch.setenv("APPDATA", str(tmp_path / "roaming"))

    loaded = config.load_config()

    assert "--file-allocation=falloc" in loaded.aria2.extra_args
    assert "--continue=true" in loaded.aria2.extra_args
    assert "--split=16" in loaded.aria2.extra_args


def test_aria2_extra_args_are_not_shared_between_configs():
    first = config.Aria2Config()
    second = config.Aria2Config()
    first.extra_args.append("--test-only=true")
    assert "--test-only=true" not in second.extra_args
