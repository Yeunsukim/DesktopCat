"""경비 기능들이 같이 쓰는 작은 도구: 프로세스 목록·실행 파일 경로·해시·시스템 경로 판단.

모두 일반 사용자 권한으로 되는 일만 한다 (읽지 못하는 프로세스는 그냥 건너뛴다). pywin32 와 ctypes 만 쓴다.
"""
import ctypes
import hashlib
import os
import time
from pathlib import Path

PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
PROCESS_TERMINATE = 0x0001

WINDIR = os.environ.get("SystemRoot", r"C:\Windows").lower()
PROGRAM_DIRS = tuple(p.lower() for p in (os.environ.get("ProgramFiles", r"C:\Program Files"), os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) if p)
# 끝내면 시스템이 망가지는 프로세스 이름: '종료' 버튼을 아예 보여 주지 않는다
CRITICAL_NAMES = {"system", "registry", "smss.exe", "csrss.exe", "wininit.exe", "winlogon.exe", "services.exe", "lsass.exe", "svchost.exe",
                  "dwm.exe", "fontdrvhost.exe", "explorer.exe", "sihost.exe", "ctfmon.exe", "taskhostw.exe", "runtimebroker.exe",
                  "searchhost.exe", "startmenuexperiencehost.exe", "shellexperiencehost.exe", "audiodg.exe", "spoolsv.exe", "memcompression"}
SUSPICIOUS_DIR_PARTS = ("\\appdata\\local\\temp\\", "\\appdata\\roaming\\", "\\appdata\\local\\", "\\downloads\\", "\\users\\public\\", "\\programdata\\",
                        "\\windows\\temp\\", "\\$recycle.bin\\", "\\perflogs\\")


def exe_path(pid: int) -> str:
    """프로세스의 실행 파일 전체 경로 (못 읽으면 빈 문자열)."""
    try:
        k32 = ctypes.windll.kernel32
        k32.OpenProcess.restype = ctypes.c_void_p
        h = k32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not h:
            return ""
        try:
            buf = ctypes.create_unicode_buffer(1040)
            size = ctypes.c_ulong(1040)
            if k32.QueryFullProcessImageNameW(ctypes.c_void_p(h), 0, buf, ctypes.byref(size)):
                return buf.value
        finally:
            k32.CloseHandle(ctypes.c_void_p(h))
    except Exception:
        pass
    return ""


def list_pids():
    import win32process
    try:
        return [p for p in win32process.EnumProcesses() if p > 4]
    except Exception:
        return []


def file_sha256(path, limit_mb=200):
    """파일의 SHA-256 (너무 크면 None). VirusTotal 조회처럼 '해시만' 쓸 때 쓴다."""
    try:
        p = Path(path)
        if not p.is_file() or p.stat().st_size > limit_mb * 1024 * 1024:
            return None
        h = hashlib.sha256()
        with open(p, "rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def is_windows_path(path: str) -> bool:
    return str(path).lower().startswith(WINDIR + "\\")


def in_program_files(path: str) -> bool:
    return str(path).lower().startswith(PROGRAM_DIRS) if PROGRAM_DIRS else False


def suspicious_location(path: str) -> bool:
    low = str(path).lower() + ("" if str(path).endswith("\\") else "")
    return any(part in low for part in SUSPICIOUS_DIR_PARTS)


def can_terminate(name: str, path: str) -> bool:
    """'종료' 버튼을 보여 줘도 되는 프로세스인가 (윈도우 폴더·시스템 필수 프로세스·고양이 자신은 안 된다)."""
    if not path or is_windows_path(path):
        return False
    return Path(path).name.lower() not in CRITICAL_NAMES and name.lower() not in CRITICAL_NAMES


def terminate(pid: int) -> bool:
    """프로세스를 끝낸다 (사용자가 확인 창에서 허락한 뒤에만 부른다)."""
    try:
        import win32api
        h = win32api.OpenProcess(PROCESS_TERMINATE, False, pid)
        try:
            win32api.TerminateProcess(h, 1)
        finally:
            win32api.CloseHandle(h)
        return True
    except Exception:
        return False


def top_writers(seconds=1.5, top=3, skip_pids=()):
    """잠깐(seconds) 사이에 디스크에 가장 많이 쓴 프로세스 상위 몇 개: [{pid, name, path, mb_s}] — 랜섬웨어 '의심 후보'를 보여 주려는 용도(확정 아님)."""
    import win32api
    import win32process

    def counters():
        out = {}
        for pid in list_pids():
            if pid in skip_pids:
                continue
            try:
                h = win32api.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
            except Exception:
                continue
            try:
                out[pid] = win32process.GetProcessIoCounters(h)["WriteTransferCount"]
            except Exception:
                pass
            finally:
                try:
                    win32api.CloseHandle(h)
                except Exception:
                    pass
        return out

    a = counters()
    time.sleep(seconds)
    b = counters()
    rows = []
    for pid, w1 in b.items():
        d = w1 - a.get(pid, w1)
        if d > 256 * 1024:
            path = exe_path(pid)
            rows.append({"pid": pid, "name": Path(path).name if path else str(pid), "path": path, "mb_s": round(d / seconds / 1048576, 1)})
    rows.sort(key=lambda r: -r["mb_s"])
    return rows[:top]


def _known_folder(csidl: int):
    buf = ctypes.create_unicode_buffer(260)
    ctypes.windll.shell32.SHGetFolderPathW(0, csidl, 0, 0, buf)
    return Path(buf.value) if buf.value else None


def default_folders():
    """랜섬웨어를 지켜볼 기본 폴더: 문서·사진·다운로드·바탕화면 (OneDrive 로 옮겨진 것도 윈도우가 알려 주는 대로)."""
    cands = [_known_folder(0x05), _known_folder(0x27), Path.home() / "Downloads", _known_folder(0x10)]   # 문서, 사진, 다운로드, 바탕화면
    out, seen = [], set()
    for c in cands:
        if c and c.is_dir() and str(c).lower() not in seen:
            seen.add(str(c).lower())
            out.append(str(c))
    return out
