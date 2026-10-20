"""열려 있는 최상위 창들의 위치(고양이가 올라설 윗변)를 수집한다."""
import ctypes
import time
from ctypes import wintypes
from typing import NamedTuple

import win32con
import win32gui

_dwm = ctypes.WinDLL("dwmapi")
_dwm.DwmGetWindowAttribute.argtypes = [wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]
DWMWA_EXTENDED_FRAME_BOUNDS = 9
DWMWA_CLOAKED = 14

_SKIP_CLASSES = {
    "Progman", "WorkerW", "Shell_TrayWnd", "Shell_SecondaryTrayWnd",
    "Windows.UI.Core.CoreWindow", "XamlExplorerHostIslandWindow", "TopLevelWindowForOverflowXamlIsland",
}


class Win(NamedTuple):
    hwnd: int
    left: float
    top: float
    right: float
    bottom: float


def _cloaked(hwnd) -> bool:
    v = ctypes.c_int(0)
    _dwm.DwmGetWindowAttribute(hwnd, DWMWA_CLOAKED, ctypes.byref(v), 4)
    return v.value != 0


def frame_rect(hwnd):
    """그림자 여백을 뺀 실제 창 사각형 (물리 픽셀)."""
    r = wintypes.RECT()
    if _dwm.DwmGetWindowAttribute(hwnd, DWMWA_EXTENDED_FRAME_BOUNDS, ctypes.byref(r), ctypes.sizeof(r)) == 0:
        return r.left, r.top, r.right, r.bottom
    return win32gui.GetWindowRect(hwnd)


_frame = frame_rect


class WindowTracker:
    """Z-order 위에서 아래 순서로 보이는 창 목록을 돌려준다 (논리 픽셀)."""

    def __init__(self, dpr: float, ignore_hwnds=()):
        self.dpr = dpr
        self.ignore = set(ignore_hwnds)
        self.windows: list[Win] = []
        self._last = 0.0

    def add_ignore(self, hwnd: int):
        self.ignore.add(int(hwnd))

    def refresh(self, interval: float = 0.25) -> list[Win]:
        now = time.monotonic()
        if now - self._last < interval:
            return self.windows
        self._last = now
        found: list[Win] = []

        def cb(hwnd, _):
            if hwnd in self.ignore or not win32gui.IsWindowVisible(hwnd) or win32gui.IsIconic(hwnd):
                return True
            ex = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
            if ex & win32con.WS_EX_TRANSPARENT or ex & win32con.WS_EX_NOACTIVATE:
                return True
            if ex & win32con.WS_EX_TOOLWINDOW and not ex & win32con.WS_EX_APPWINDOW:
                return True
            if not win32gui.GetWindowText(hwnd) or win32gui.GetClassName(hwnd) in _SKIP_CLASSES:
                return True
            if _cloaked(hwnd):
                return True
            l, t, r, b = _frame(hwnd)
            if r - l < 120 or b - t < 60:
                return True
            d = self.dpr
            found.append(Win(hwnd, l / d, t / d, r / d, b / d))
            return True

        try:
            win32gui.EnumWindows(cb, None)
        except Exception:
            return self.windows
        self.windows = found
        return found
