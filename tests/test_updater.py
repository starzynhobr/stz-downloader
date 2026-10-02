import asyncio
import hashlib

import httpx
import pytest

from stz_downloader import updater as updater_module
from stz_downloader.updater import (
    UpdateError,
    Updater,
    installer_command,
    is_newer,
    parse_checksums,
)

INSTALLER = b"pretend installer bytes" * 1000
GOOD = hashlib.sha256(INSTALLER).hexdigest()
BAD = "0" * 64
NAME = "stz-downloader-9.9.9.0-desktop-setup.exe"
ASSET_URL = f"https://github.com/x/releases/download/v9.9.9/{NAME}"
SUMS_URL = "https://github.com/x/releases/download/v9.9.9/SHA256SUMS.txt"


def _release(tag="v9.9.9", digest=GOOD, sums=True):
    assets = [
        {"name": "stz-downloader-9.9.9.0-setup.exe", "browser_download_url": "https://x/qt.exe"},
        {
            "name": NAME,
            "browser_download_url": ASSET_URL,
            "size": len(INSTALLER),
            **({"digest": f"sha256:{digest}"} if digest else {}),
        },
    ]
    if sums:
        assets.append({"name": "SHA256SUMS.txt", "browser_download_url": SUMS_URL})
    return {"tag_name": tag, "body": "Notes", "html_url": "https://github.com/x/releases/v9.9.9", "assets": assets}


def _updater(tmp_path, release, sums_hash=GOOD, payload=INSTALLER):
    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url == updater_module.LATEST_URL:
            return httpx.Response(200, json=release)
        if url == SUMS_URL:
            return httpx.Response(200, text=f"{sums_hash}  {NAME}\nabc  other.zip\n")
        if url == ASSET_URL:
            return httpx.Response(200, content=payload)
        return httpx.Response(404)

    return Updater(download_dir=tmp_path, transport=httpx.MockTransport(handler))


def run(coro):
    return asyncio.run(coro)


def test_version_comparison():
    assert is_newer("0.1.11", "0.1.10")
    assert is_newer("v0.2", "0.1.10")
    assert not is_newer("0.1.10", "0.1.10")
    assert not is_newer("0.1.9", "0.1.10")
    assert not is_newer("garbage", "0.1.10")


def test_checksum_file_parsing():
    sums = parse_checksums(f"{GOOD}  {NAME}\n{BAD} *other.zip\nnot a line\n")
    assert sums == {NAME: GOOD, "other.zip": BAD}


def test_newer_release_is_offered_with_both_hashes(tmp_path):
    up = _updater(tmp_path, _release())
    state = run(up.check())
    assert state["available"] and state["version"] == "9.9.9"
    assert up._release.expected == [GOOD, GOOD]


def test_same_version_is_not_offered(tmp_path):
    up = _updater(tmp_path, _release(tag=f"v{updater_module.__version__}"))
    assert run(up.check())["available"] is False


def test_verified_installer_is_saved(tmp_path):
    up = _updater(tmp_path, _release())
    run(up.check())
    path = run(up.download_and_verify())
    assert path.read_bytes() == INSTALLER
    assert not list(tmp_path.glob("*.part"))


def test_tampered_download_is_rejected_and_deleted(tmp_path):
    up = _updater(tmp_path, _release(), payload=b"evil")
    run(up.check())
    with pytest.raises(UpdateError, match="mismatch"):
        run(up.download_and_verify())
    assert not list(tmp_path.iterdir())


def test_disagreeing_hashes_are_refused(tmp_path):
    up = _updater(tmp_path, _release(), sums_hash=BAD)
    run(up.check())
    with pytest.raises(UpdateError, match="disagree"):
        run(up.download_and_verify())


def test_unverifiable_installer_is_refused(tmp_path):
    up = _updater(tmp_path, _release(digest=None, sums=False))
    run(up.check())
    with pytest.raises(UpdateError, match="no SHA-256"):
        run(up.download_and_verify())


def test_github_digest_alone_is_enough(tmp_path):
    up = _updater(tmp_path, _release(sums=False))
    run(up.check())
    assert run(up.download_and_verify()).exists()


def test_offline_check_reports_an_error_instead_of_raising(tmp_path):
    def offline(request):
        raise httpx.ConnectError("no network")

    up = Updater(download_dir=tmp_path, transport=httpx.MockTransport(offline))
    state = run(up.check())
    assert state["status"] == "error" and not state["available"]


def test_installer_runs_detached_silent_and_relaunches(tmp_path):
    command = installer_command(tmp_path / "my folder" / NAME)
    assert command.startswith('cmd.exe /c start "" "')
    assert f'my folder\\{NAME}"' in command or f'my folder/{NAME}"' in command
    for flag in ("/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/AUTOUPDATE=1"):
        assert flag in command


def test_leftover_installers_are_removed(tmp_path):
    (tmp_path / NAME).write_bytes(b"old")
    (tmp_path / f"{NAME}.part").write_bytes(b"half")
    Updater(download_dir=tmp_path).clean_downloads()
    assert not list(tmp_path.iterdir())
