from pathlib import Path
from unittest.mock import patch

import pytest

from stz_downloader.server.app import (
    URL_RE,
    _committed_bytes,
    _normalize,
    _reveal_path,
    _url_extension,
)

GB = 1024 ** 3


@pytest.mark.parametrize("name", ["file.zip", "my file.zip", "ação, versão final.zip"])
def test_reveal_windows_quotes_only_the_selected_path(tmp_path, name):
    path = tmp_path / "Download folder" / name
    with (
        patch("stz_downloader.server.app.sys.platform", "win32"),
        patch("stz_downloader.server.app.subprocess.Popen") as popen,
    ):
        _reveal_path(Path(path))
    popen.assert_called_once_with(f'explorer.exe /select,"{path.resolve()}"')


def test_normalize_download_includes_progress_speed_and_path():
    item = {
        "gid": "abc",
        "status": "active",
        "totalLength": "100",
        "completedLength": "25",
        "downloadSpeed": "5",
        "files": [{"path": r"C:\Downloads\example.zip"}],
    }

    assert _normalize(item) == {
        "gid": "abc",
        "status": "active",
        "name": "example.zip",
        "total": 100,
        "completed": 25,
        "speed": 5,
        "progress": 0.25,
        "error": "",
        "errorCode": "",
        "path": r"C:\Downloads\example.zip",
    }


# -- disk ledger ---------------------------------------------------------

def test_committed_bytes_sums_across_the_queue():
    """Two 150 GB downloads each fit in 200 GB free, but not together.

    Per-download checks pass both; only the sum catches the overcommit.
    """
    items = [
        {"status": "active", "total": 150 * GB, "completed": 0},
        {"status": "waiting", "total": 150 * GB, "completed": 0},
    ]
    assert _committed_bytes(items) == 300 * GB


def test_committed_bytes_counts_only_what_is_still_owed():
    items = [{"status": "active", "total": 100 * GB, "completed": 40 * GB}]
    assert _committed_bytes(items) == 60 * GB


def test_committed_bytes_respects_space_already_taken_on_disk():
    """A segmented download writes near the end of the file immediately, so
    NTFS has already allocated the whole thing. Measured: 91.8 MB fetched of a
    4 GB file, 3980 MB actually consumed. Counting `total - completed` here
    would double-count nearly the entire file."""
    items = [{
        "status": "active",
        "total": 4 * GB,
        "completed": 92 * 1024 ** 2,   # what aria2 reports as fetched
        "onDisk": 3980 * 1024 ** 2,    # what the volume actually lost
    }]
    # Only the sliver the file hasn't grown into yet is still owed.
    assert _committed_bytes(items) == 4 * GB - 3980 * 1024 ** 2


def test_committed_bytes_falls_back_to_completed_without_on_disk():
    """When the file can't be stat'ed we still want a usable estimate."""
    items = [{"status": "active", "total": 100 * GB, "completed": 40 * GB}]
    assert _committed_bytes(items) == 60 * GB


def test_committed_bytes_queued_download_claims_its_full_size():
    """Nothing written yet, so the whole file is still to come."""
    items = [{"status": "waiting", "total": 150 * GB, "completed": 0, "onDisk": 0}]
    assert _committed_bytes(items) == 150 * GB


def test_committed_bytes_ignores_finished_and_failed():
    items = [
        {"status": "complete", "total": 50 * GB, "completed": 50 * GB},
        {"status": "error", "total": 50 * GB, "completed": 1 * GB},
        {"status": "removed", "total": 50 * GB, "completed": 0},
        {"status": "paused", "total": 10 * GB, "completed": 0},
    ]
    # Only the paused one still has a claim on the disk.
    assert _committed_bytes(items) == 10 * GB


def test_committed_bytes_handles_unknown_size_and_overshoot():
    items = [
        {"status": "active", "total": 0, "completed": 0},          # size unknown
        {"status": "active", "total": 10 * GB, "completed": 12 * GB},  # over-reported
    ]
    assert _committed_bytes(items) == 0


def test_committed_bytes_empty_queue():
    assert _committed_bytes([]) == 0


# -- clipboard filtering -------------------------------------------------

@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://example.com/file.zip", ".zip"),
        ("https://example.com/file.ZIP", ".zip"),
        ("https://example.com/a/b/movie.mkv?token=abc&x=1", ".mkv"),
        ("https://example.com/archive.tar.gz#frag", ".gz"),
        ("https://example.com/no-extension", ""),
        ("https://example.com/", ""),
    ],
)
def test_url_extension(url, expected):
    assert _url_extension(url) == expected


@pytest.mark.parametrize(
    "text",
    [
        "https://example.com/file.zip",
        "http://example.com/file.zip",
        "HTTPS://EXAMPLE.COM/FILE.ZIP",
    ],
)
def test_url_re_accepts_plain_urls(text):
    assert URL_RE.match(text)


@pytest.mark.parametrize(
    "text",
    [
        "look at https://example.com/file.zip please",  # prose around a link
        "ftp://example.com/file.zip",                   # unsupported scheme
        "example.com/file.zip",                         # no scheme
        "",
        "just some copied text",
    ],
)
def test_url_re_rejects_non_urls(text):
    assert not URL_RE.match(text)


def test_failed_download_without_a_path_is_named_from_its_url():
    item = {
        "gid": "x",
        "status": "error",
        "files": [{"path": "", "uris": [{"uri": "https://example.com/dir/old-build.zip?token=1"}]}],
    }
    assert _normalize(item)["name"] == "old-build.zip"
