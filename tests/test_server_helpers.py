from stz_downloader.server.app import _normalize


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
        "path": r"C:\Downloads\example.zip",
    }
