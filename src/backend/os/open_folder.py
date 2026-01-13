from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path


class OpenFolderError(RuntimeError):
    pass


def _is_wsl() -> bool:
    if os.environ.get("WSL_DISTRO_NAME"):
        return True
    rel = platform.release().lower()
    ver = platform.version().lower()
    return ("microsoft" in rel) or ("microsoft" in ver)


def _to_windows_path(path: Path) -> str:
    try:
        out = subprocess.check_output(["wslpath", "-w", str(path)], text=True).strip()
        return out or str(path)
    except Exception:
        return str(path)


def open_folder(path: Path) -> None:
    p = Path(path).expanduser().resolve()

    if sys.platform.startswith("win"):
        try:
            os.startfile(str(p))  # type: ignore[attr-defined]
        except Exception as exc:
            raise OpenFolderError(f"Windows 打开目录失败：{exc}") from exc
        return

    if sys.platform == "darwin":
        try:
            subprocess.Popen(["open", str(p)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as exc:
            raise OpenFolderError(f"macOS 打开目录失败：{exc}") from exc
        return

    # Linux / WSL
    if _is_wsl() and (shutil.which("explorer.exe") is not None):
        try:
            win_path = _to_windows_path(p)
            subprocess.Popen(["explorer.exe", win_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as exc:
            raise OpenFolderError(f"WSL 打开目录失败：{exc}") from exc
        return

    opener = shutil.which("xdg-open")
    if opener is not None:
        try:
            subprocess.Popen([opener, str(p)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as exc:
            raise OpenFolderError(f"Linux 打开目录失败：{exc}") from exc
        return

    gio = shutil.which("gio")
    if gio is not None:
        try:
            subprocess.Popen([gio, "open", str(p)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as exc:
            raise OpenFolderError(f"Linux(gio) 打开目录失败：{exc}") from exc
        return

    raise OpenFolderError("未找到可用的打开目录命令（explorer.exe / xdg-open / gio）")

