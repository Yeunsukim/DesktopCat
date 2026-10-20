"""지킴이(launcher.py)와 고양이 프로그램(cat.py)이 같이 쓰는 도구.

지킴이는 고양이가 죽었을 때 다시 살려야 하므로 가볍고 튼튼해야 한다. 그래서 이 파일은 표준 라이브러리만 쓴다
(PyQt 등을 가져오지 않는다).
"""
import ctypes
import mmap
import os
import struct
import sys
import time
from pathlib import Path

QUIT_EVENT = "Local\\DesktopCatQuitEvent"           # 이 이벤트를 켜면 고양이가 깔끔하게 종료한다 (아이콘 복원 포함)
HEARTBEAT_TAG = "Local\\DesktopCatHeartbeat"        # 고양이가 살아 있다는 신호를 적어 두는 공유 메모리 이름
GUARD_MUTEX = "Local\\DesktopCatGuardMutex"         # 지킴이가 두 개 뜨지 않게 하는 표식

EXIT_QUIT = 0          # 사용자가 종료함 → 지킴이도 같이 끝난다
EXIT_RESTART = 3       # 고양이가 스스로 "다시 켜 줘" 하고 끝남 (자원이 새거나 오류가 계속될 때) → 바로 다시 시작


def data_dir() -> Path:
    """기록·로그를 두는 폴더. 설치된 exe 는 %LOCALAPPDATA%\\DesktopCat, 소스로 돌릴 때는 소스 폴더."""
    if os.environ.get("DESKTOPCAT_DATA"):                # 시험할 때만: 실제 설정·기록을 건드리지 않게 다른 폴더를 쓴다
        d = Path(os.environ["DESKTOPCAT_DATA"])
    elif getattr(sys, "frozen", False):
        d = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "DesktopCat"
    else:
        d = Path(__file__).resolve().parent
    try:
        d.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    return d


def log_text(path: Path, text: str, cap: int = 200_000):
    """로그에 한 줄 덧붙인다. 파일이 cap 바이트를 넘으면 비우고 새로 시작해서, 며칠을 켜 둬도 커지지 않는다."""
    try:
        path = Path(path)
        if path.exists() and path.stat().st_size > cap:
            path.write_text("", encoding="utf-8")
        with path.open("a", encoding="utf-8") as f:
            f.write(time.strftime("[%Y-%m-%d %H:%M:%S] ") + text.rstrip() + "\n")
    except OSError:
        pass


class Heartbeat:
    """고양이가 5초마다 현재 시각을 적고, 지킴이가 읽어서 멈췄는지 판단한다."""

    def __init__(self):
        self.mm = mmap.mmap(-1, 16, tagname=HEARTBEAT_TAG)

    def beat(self):
        self.mm[0:8] = struct.pack("d", time.time())

    def last(self) -> float:
        return struct.unpack("d", self.mm[0:8])[0]


def request_quit() -> bool:
    """실행 중인 고양이에게 종료 신호를 보낸다."""
    k32 = ctypes.windll.kernel32
    k32.OpenEventW.restype = ctypes.c_void_p
    h = k32.OpenEventW(0x0002, False, QUIT_EVENT)          # EVENT_MODIFY_STATE
    if not h:
        return False
    k32.SetEvent(ctypes.c_void_p(h))
    k32.CloseHandle(ctypes.c_void_p(h))
    return True


class _MemCounters(ctypes.Structure):
    _fields_ = [("cb", ctypes.c_ulong), ("PageFaultCount", ctypes.c_ulong), ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t), ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t), ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t), ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t)]


def process_usage():
    """이 프로세스의 자원 사용량: 메모리(MB), 핸들 수, GDI 개체 수, USER 개체 수. 실패하면 None.
    GDI/USER 개체는 프로세스당 약 10,000개가 한계라서, 조금씩 새면 며칠 뒤 갑자기 죽는 흔한 원인이다."""
    try:
        k32, u32, ps = ctypes.windll.kernel32, ctypes.windll.user32, ctypes.windll.psapi
        k32.GetCurrentProcess.restype = ctypes.c_void_p
        proc = ctypes.c_void_p(k32.GetCurrentProcess())
        mc = _MemCounters()
        mc.cb = ctypes.sizeof(mc)
        ps.GetProcessMemoryInfo.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong]
        ps.GetProcessMemoryInfo(proc, ctypes.byref(mc), mc.cb)
        handles = ctypes.c_ulong()
        k32.GetProcessHandleCount.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        k32.GetProcessHandleCount(proc, ctypes.byref(handles))
        u32.GetGuiResources.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
        return {"ws_mb": mc.WorkingSetSize / 1e6, "handles": handles.value,
                "gdi": u32.GetGuiResources(proc, 0), "user": u32.GetGuiResources(proc, 1)}
    except Exception:
        return None
