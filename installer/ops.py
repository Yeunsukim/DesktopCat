"""설치/삭제 프로그램이 같이 쓰는 동작들 (바로가기, 시작 프로그램 등록, 앱 목록 등록, 실행 중인 고양이 끄기 ...)."""
import base64
import ctypes
import os
import subprocess
import sys
import time
import winreg
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from guard_common import request_quit                      # noqa: E402

APP_ID = os.environ.get("DESKTOPCAT_APP_ID", "DesktopCat")         # 시험할 때만 다른 이름으로 설치해 볼 수 있게 (실제 설치는 기본값)
IS_TEST = APP_ID != "DesktopCat"
DISPLAY_NAME = "데스크탑 고양이" + (" (시험)" if IS_TEST else "")
VERSION = "1.0.0"
PUBLISHER = "Desktop Cat"
EXE = "DesktopCat.exe"
UNINSTALLER = "uninstall.exe"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
UNINSTALL_KEY = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\\" + APP_ID
CREATE_NO_WINDOW = 0x08000000
MUTEXES = ("Local\\DesktopCatGuardMutex", "Local\\DesktopCatPetMutex")


def default_dir() -> Path:
    """이전에 설치한 곳이 있으면 거기, 없으면 내 계정 프로그램 폴더 (관리자 권한이 필요 없다)."""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, UNINSTALL_KEY) as k:
            loc = winreg.QueryValueEx(k, "InstallLocation")[0]
            if loc:
                return Path(loc)
    except OSError:
        pass
    return Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "Programs" / APP_ID


def user_data_dir() -> Path:
    return Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "DesktopCat"


def remove_canaries() -> int:
    """경비 고양이가 문서·사진·다운로드 폴더에 둔 숨김 미끼 파일을 지운다 (기록해 둔 것 중 이름이 미끼 이름인 파일만). 지운 개수를 돌려준다."""
    import json
    base = Path(os.environ.get("DESKTOPCAT_DATA") or user_data_dir())
    state = base / "security" / "canary.json"
    n = 0
    try:
        listed = json.loads(state.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return 0
    for p in listed:
        f = Path(p)
        if "고양이미끼" not in f.name:
            continue
        try:
            ctypes.windll.kernel32.SetFileAttributesW(str(f), 0x80)          # 숨김·읽기 전용을 풀고 지운다
            f.unlink()
            n += 1
        except OSError:
            pass
    try:
        state.unlink()
    except OSError:
        pass
    return n


def _known_folder(csidl: int) -> Path:
    buf = ctypes.create_unicode_buffer(260)
    ctypes.windll.shell32.SHGetFolderPathW(0, csidl, 0, 0, buf)
    return Path(buf.value)


def start_menu_lnk() -> Path:
    return _known_folder(0x02) / f"{DISPLAY_NAME}.lnk"          # CSIDL_PROGRAMS (내 계정 시작 메뉴 > 프로그램)


def desktop_lnk() -> Path:
    return _known_folder(0x10) / f"{DISPLAY_NAME}.lnk"          # CSIDL_DESKTOPDIRECTORY


def _powershell(script: str):
    enc = base64.b64encode(script.encode("utf-16-le")).decode()
    return subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-EncodedCommand", enc],
                          capture_output=True, creationflags=CREATE_NO_WINDOW, timeout=90)


def create_shortcut(lnk: Path, target: Path, desc: str):
    lnk.parent.mkdir(parents=True, exist_ok=True)
    q = lambda s: str(s).replace("'", "''")
    _powershell("$s=(New-Object -ComObject WScript.Shell).CreateShortcut('%s'); $s.TargetPath='%s'; $s.WorkingDirectory='%s'; "
                "$s.IconLocation='%s,0'; $s.Description='%s'; $s.Save()" % (q(lnk), q(target), q(target.parent), q(target), q(desc)))


def remove_file(p: Path):
    try:
        p.unlink(missing_ok=True)
    except OSError:
        pass


# --- 시작 프로그램 / 앱 목록 ------------------------------------------------
def set_autostart(exe: Path, on: bool):
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
        if on:
            winreg.SetValueEx(k, APP_ID, 0, winreg.REG_SZ, f'"{exe}"')
        else:
            try:
                winreg.DeleteValue(k, APP_ID)
            except OSError:
                pass


def register_uninstall(install_dir: Path, size_kb: int):
    exe = install_dir / EXE
    unin = install_dir / UNINSTALLER
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, UNINSTALL_KEY) as k:
        for name, val in (("DisplayName", DISPLAY_NAME), ("DisplayVersion", VERSION), ("Publisher", PUBLISHER),
                          ("InstallLocation", str(install_dir)), ("DisplayIcon", f"{exe},0"),
                          ("UninstallString", f'"{unin}"'), ("QuietUninstallString", f'"{unin}" --silent')):
            winreg.SetValueEx(k, name, 0, winreg.REG_SZ, val)
        for name, val in (("NoModify", 1), ("NoRepair", 1), ("EstimatedSize", int(size_kb))):
            winreg.SetValueEx(k, name, 0, winreg.REG_DWORD, val)


def unregister_uninstall():
    try:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, UNINSTALL_KEY)
    except OSError:
        pass


# --- 실행 중인 고양이 끄기 ---------------------------------------------------
def is_running() -> bool:
    k32 = ctypes.windll.kernel32
    k32.OpenMutexW.restype = ctypes.c_void_p
    for name in MUTEXES:
        h = k32.OpenMutexW(0x00100000, False, name)            # SYNCHRONIZE
        if h:
            k32.CloseHandle(ctypes.c_void_p(h))
            return True
    return False


def stop_app(wait: float = 20.0) -> bool:
    """실행 중인 고양이를 정중하게 끈다(바탕화면 아이콘도 제자리로 돌아간다). 안 꺼지면 강제로 끈다."""
    if not is_running():
        return True
    request_quit()
    end = time.time() + wait
    while time.time() < end:
        if not is_running():
            return True
        time.sleep(0.5)
    subprocess.run(["taskkill", "/F", "/T", "/IM", EXE], capture_output=True, creationflags=CREATE_NO_WINDOW)
    time.sleep(1.5)
    return not is_running()


def delete_tree_after_exit(target: Path):
    """실행 중인 삭제 프로그램 자신이 들어 있는 폴더는 지금 지울 수 없으니, 끝난 뒤에 지우는 배치 파일을 띄운다."""
    bat = Path(os.environ.get("TEMP", str(Path.home()))) / f"{APP_ID}_cleanup.bat"
    bat.write_text('@echo off\r\nfor /l %%i in (1,1,30) do (\r\n  rmdir /s /q "{d}" 2>nul\r\n  if not exist "{d}" goto done\r\n'
                   '  ping -n 2 127.0.0.1 >nul\r\n)\r\n:done\r\ndel "%~f0"\r\n'.format(d=target), encoding="ascii", errors="replace")
    subprocess.Popen(["cmd", "/c", str(bat)], creationflags=CREATE_NO_WINDOW | 0x00000008, close_fds=True)
