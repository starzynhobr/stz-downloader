from pathlib import Path

from stz_downloader.startup import _windowsapps_family_from_exe


def test_windowsapps_family_from_exe() -> None:
    path = Path(
        r"C:\Program Files\WindowsApps"
        r"\stz-downloader_0.1.9.0_x64__ewhqyqms530qa"
        r"\stz-downloader.exe"
    )

    assert _windowsapps_family_from_exe(path) == "stz-downloader_ewhqyqms530qa"
