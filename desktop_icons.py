"""바탕화면 아이콘(SysListView32)의 위치를 읽고 옮기고, 원래대로 복원한다.

explorer.exe 프로세스 메모리에 임시 버퍼를 만들어 ListView 메시지를 주고받는다.
좌표는 모두 물리 픽셀이며, 논리 픽셀 변환은 호출하는 쪽에서 한다.
"""
import atexit
import ctypes
import time
import json
from ctypes import wintypes
from pathlib import Path

import win32gui
import win32process

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

user32.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.SendMessageW.restype = wintypes.LPARAM
kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.VirtualAllocEx.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_size_t, wintypes.DWORD, wintypes.DWORD]
kernel32.VirtualAllocEx.restype = ctypes.c_void_p
kernel32.VirtualFreeEx.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_size_t, wintypes.DWORD]
kernel32.ReadProcessMemory.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t,
                                       ctypes.POINTER(ctypes.c_size_t)]
kernel32.WriteProcessMemory.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t,
                                        ctypes.POINTER(ctypes.c_size_t)]

PROCESS_ACCESS = 0x0008 | 0x0010 | 0x0020 | 0x0400   # VM_OPERATION | VM_READ | VM_WRITE | QUERY_INFORMATION
MEM_COMMIT_RESERVE = 0x3000
MEM_RELEASE = 0x8000
PAGE_READWRITE = 0x04

LVM_GETITEMCOUNT = 0x1004
LVM_GETITEMPOSITION = 0x1010
LVM_SETITEMPOSITION = 0x100F
LVM_GETITEMSPACING = 0x1033
LVM_GETITEMTEXTW = 0x1073
LVM_SETEXTENDEDLISTVIEWSTYLE = 0x1036
LVM_GETEXTENDEDLISTVIEWSTYLE = 0x1037
LVS_EX_SNAPTOGRID = 0x00080000
LVIF_TEXT = 0x0001
LVS_AUTOARRANGE = 0x0100
GWL_STYLE = -16

TEXT_OFFSET = 256
TEXT_CHARS = 260


class LVITEMW(ctypes.Structure):
    _fields_ = [
        ("mask", ctypes.c_uint), ("iItem", ctypes.c_int), ("iSubItem", ctypes.c_int),
        ("state", ctypes.c_uint), ("stateMask", ctypes.c_uint),
        ("pszText", ctypes.c_void_p), ("cchTextMax", ctypes.c_int), ("iImage", ctypes.c_int),
        ("lParam", ctypes.c_ssize_t), ("iIndent", ctypes.c_int), ("iGroupId", ctypes.c_int),
        ("cColumns", ctypes.c_uint), ("puColumns", ctypes.c_void_p), ("piColFmt", ctypes.c_void_p),
        ("iGroup", ctypes.c_int),
    ]


def _find_listview() -> int:
    progman = win32gui.FindWindow("Progman", None)
    defview = win32gui.FindWindowEx(progman, 0, "SHELLDLL_DefView", None) if progman else 0
    if not defview:
        found = []

        def cb(hwnd, _):
            if win32gui.GetClassName(hwnd) == "WorkerW":
                dv = win32gui.FindWindowEx(hwnd, 0, "SHELLDLL_DefView", None)
                if dv:
                    found.append(dv)
            return True

        win32gui.EnumWindows(cb, None)
        defview = found[0] if found else 0
    return win32gui.FindWindowEx(defview, 0, "SysListView32", None) if defview else 0


class DesktopIcons:
    def __init__(self, backup_path: Path):
        self.backup_path = Path(backup_path)
        self.lv = 0
        self._proc = None
        self._buf = None
        self.attached = False
        self.orig_snap = True
        self._backed_up = False
        self._atexit = False
        self._next_try = 0.0
        self.kicked: dict = {}

    # --- 연결 ---------------------------------------------------------
    def attach(self) -> bool:
        try:
            self.lv = _find_listview()
            if not self.lv:
                return False
            _, pid = win32process.GetWindowThreadProcessId(self.lv)
            self._proc = kernel32.OpenProcess(PROCESS_ACCESS, False, pid)
            if not self._proc:
                return False
            self._buf = kernel32.VirtualAllocEx(self._proc, None, 4096, MEM_COMMIT_RESERVE, PAGE_READWRITE)
            self.attached = bool(self._buf)
        except Exception:
            self.attached = False
        if self.attached and not self._atexit:
            atexit.register(self.shutdown)
            self._atexit = True
        return self.attached

    def revalidate(self) -> bool:
        """바탕화면 목록 창이 아직 살아 있는지 확인한다. 윈도우 탐색기가 죽었다 다시 뜨면 창이 바뀌므로,
        30초에 한 번씩 다시 연결을 시도한다(격자 정렬은 다시 꺼 둔다). 연결이 안 되면 False."""
        try:
            if (self.attached and self.lv and win32gui.IsWindow(self.lv)
                    and win32gui.GetClassName(self.lv) == "SysListView32"):
                return True
            now = time.monotonic()
            if now < self._next_try:
                return False
            self._next_try = now + 30
            self.close()
            if self.attach():
                self.set_snap(False)
                return True
        except Exception:
            self.attached = False
        return False

    def close(self):
        if self._proc and self._buf:
            kernel32.VirtualFreeEx(self._proc, self._buf, 0, MEM_RELEASE)
            self._buf = None
        if self._proc:
            kernel32.CloseHandle(self._proc)
            self._proc = None
        self.attached = False

    # --- 상태 질의 ----------------------------------------------------
    def is_autoarrange(self) -> bool:
        return bool(win32gui.GetWindowLong(self.lv, GWL_STYLE) & LVS_AUTOARRANGE)

    def is_visible(self) -> bool:
        return bool(win32gui.IsWindowVisible(self.lv))

    def spacing(self) -> tuple[int, int]:
        r = user32.SendMessageW(self.lv, LVM_GETITEMSPACING, 0, 0)
        return r & 0xFFFF, (r >> 16) & 0xFFFF

    def count(self) -> int:
        return int(user32.SendMessageW(self.lv, LVM_GETITEMCOUNT, 0, 0))

    # --- 격자 정렬 (실행 중에만 끈다) ----------------------------------
    def snap_enabled(self) -> bool:
        return bool(user32.SendMessageW(self.lv, LVM_GETEXTENDEDLISTVIEWSTYLE, 0, 0) & LVS_EX_SNAPTOGRID)

    def set_snap(self, on: bool):
        user32.SendMessageW(self.lv, LVM_SETEXTENDEDLISTVIEWSTYLE, LVS_EX_SNAPTOGRID,
                            LVS_EX_SNAPTOGRID if on else 0)

    # --- 읽기/쓰기 ----------------------------------------------------
    def _read(self, offset, size) -> bytes:
        out = ctypes.create_string_buffer(size)
        n = ctypes.c_size_t(0)
        kernel32.ReadProcessMemory(self._proc, self._buf + offset, out, size, ctypes.byref(n))
        return out.raw

    def _write(self, offset, data: bytes):
        n = ctypes.c_size_t(0)
        kernel32.WriteProcessMemory(self._proc, self._buf + offset, data, len(data), ctypes.byref(n))

    def position(self, index: int) -> tuple[int, int]:
        user32.SendMessageW(self.lv, LVM_GETITEMPOSITION, index, self._buf)
        x, y = ctypes.c_int.from_buffer_copy(self._read(0, 4)).value, ctypes.c_int.from_buffer_copy(self._read(4, 4)).value
        return x, y

    def name(self, index: int) -> str:
        item = LVITEMW()
        item.mask = LVIF_TEXT
        item.iItem = index
        item.pszText = self._buf + TEXT_OFFSET
        item.cchTextMax = TEXT_CHARS
        self._write(0, bytes(item))
        self._write(TEXT_OFFSET, b"\x00\x00")
        user32.SendMessageW(self.lv, LVM_GETITEMTEXTW, index, self._buf)
        raw = self._read(TEXT_OFFSET, TEXT_CHARS * 2)
        return raw.decode("utf-16-le", errors="ignore").split("\x00", 1)[0]

    def set_position(self, index: int, x: int, y: int):
        x = max(-32000, min(32000, int(x)))
        y = max(-32000, min(32000, int(y)))
        user32.SendMessageW(self.lv, LVM_SETITEMPOSITION, index, ((y & 0xFFFF) << 16) | (x & 0xFFFF))

    def snapshot(self) -> list[dict]:
        """현재 아이콘 목록: [{index, key, x, y}]. key = 이름(중복은 #n 접미사)."""
        seen: dict[str, int] = {}
        result = []
        for i in range(self.count()):
            nm = self.name(i)
            n = seen.get(nm, 0)
            seen[nm] = n + 1
            x, y = self.position(i)
            result.append({"index": i, "key": f"{nm}#{n}", "x": x, "y": y})
        return result

    # --- 백업/복원 ----------------------------------------------------
    # 고양이가 찬 아이콘만 기록해 둔다: 이름#번호 → {"origin": 차기 전 위치, "final": 멈춘 위치}
    # (켠 뒤에 새로 만든 아이콘도, 이름을 안 바꿨다면 제자리로 돌아간다. 고양이가 안 찬 아이콘은 건드리지 않는다)

    def _save(self):
        try:
            self.backup_path.write_text(json.dumps({"snap": self.orig_snap, "kicked": self.kicked}, ensure_ascii=False),
                                        encoding="utf-8")
        except OSError:
            pass

    def _key_of(self, index: int):
        """index 번째 아이콘의 키(이름#번호)."""
        try:
            seen: dict[str, int] = {}
            for i in range(index + 1):
                nm = self.name(i)
                n = seen.get(nm, 0)
                seen[nm] = n + 1
                if i == index:
                    return f"{nm}#{n}"
        except Exception:
            pass
        return None

    def note_kick(self, index: int):
        """고양이가 아이콘을 차기 직전: 그 아이콘의 원래 위치를 (처음 찰 때만) 기록한다."""
        if not self.attached or not self._backed_up:
            return
        key = self._key_of(index)
        if key is None:
            return
        entry = self.kicked.get(key)
        if entry is None:
            x, y = self.position(index)
            self.kicked[key] = {"origin": [x, y], "final": None}
        else:
            entry["final"] = None                     # 또 차는 중
        self._save()

    def note_rest(self, index: int):
        """찬 아이콘이 멈춤: 멈춘 자리를 기록한다 (그 뒤에 사용자가 직접 옮겼는지 알아내려고)."""
        if not self.attached or not self._backed_up:
            return
        key = self._key_of(index)
        entry = self.kicked.get(key) if key else None
        if entry is not None:
            entry["final"] = list(self.position(index))
            self._save()

    def backup(self):
        """'격자 정렬' 원래 설정을 저장하고, 찬 아이콘 기록을 시작한다.

        이전 실행이 갑자기 꺼져서 기록이 남아 있으면, 그때 찬 아이콘을 먼저 제자리로 돌려놓는다.
        (예전 버전이 남긴 '전체 아이콘 위치' 형식의 백업도 알아본다.)
        """
        snap = self.snap_enabled()
        if self.backup_path.exists():
            try:
                data = json.loads(self.backup_path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                data = {}
            snap = bool(data.get("snap", snap))
            self.orig_snap = snap
            self.kicked = dict(data.get("kicked") or {})
            if data.get("icons"):                     # 예전 형식
                for it in self.snapshot():
                    pos = data["icons"].get(it["key"])
                    if pos and (pos[0], pos[1]) != (it["x"], it["y"]):
                        self.set_position(it["index"], pos[0], pos[1])
            self._backed_up = True
            self.restore()
        self.orig_snap = snap
        self.kicked = {}
        self._backed_up = True
        self._save()

    def restore(self) -> int:
        """고양이가 찬 아이콘을 원래 위치로 되돌린다. 움직인 아이콘 수를 돌려준다.
        아이콘이 없어졌거나 이름이 바뀌었으면 건너뛰고, 찬 뒤에 사용자가 직접 옮긴 아이콘도 건드리지 않는다."""
        if not self.attached or not self.kicked:
            return 0
        by_key = {it["key"]: it for it in self.snapshot()}
        moved = 0
        for key, e in list(self.kicked.items()):
            it = by_key.get(key)
            del self.kicked[key]
            if it is None:
                continue
            fin = e.get("final")
            if fin is not None and (abs(it["x"] - fin[0]) > 6 or abs(it["y"] - fin[1]) > 6):
                continue                              # 사용자가 직접 옮겼다
            ox, oy = e["origin"]
            if (it["x"], it["y"]) != (ox, oy):
                self.set_position(it["index"], ox, oy)
                moved += 1
        self._save()
        return moved

    def shutdown(self):
        """종료 처리: 위치 복원 → 격자 정렬 설정 복원 → 백업 파일 삭제 (여러 번 불러도 안전)."""
        if not self.attached:
            return
        try:
            if self._backed_up:
                self.restore()
                self.set_snap(self.orig_snap)
                self.backup_path.unlink(missing_ok=True)
        finally:
            self.close()
