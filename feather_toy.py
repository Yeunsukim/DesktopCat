"""놀아주기(깃털)용 나비 낚싯대: 마우스 커서 자리에 나비를 단 가는 철심을 벡터로 그려 따라다니게 한다.

 · 윈도우의 커서는 점 그림(비트맵)만 받고, '마우스 포인터 크기' 설정이 클수록 한 번 더 확대돼서 크고 거칠게 보인다.
   그래서 나비는 커서 그림이 아니라 **마우스를 따라다니는 투명 창**에 벡터(QPainter)로 직접 그린다: 어떤 화면 배율에서도 또렷하고, 크기도 마음대로다.
   창은 클릭이 그대로 아래 창으로 통과하고(WS_EX_TRANSPARENT), 포커스도 가져가지 않는다. 마우스 위치는 약 100번/초로 따라간다.
 · 진짜 커서(화살표·글자 입력 I 빔·손가락)는 SetSystemCursor 로 **투명한 커서**로 바꿔 숨긴다. 클릭이 되는 점은 그대로 마우스 자리이고, 나비의 가운데가 그 점이다.
 · 되돌리기는 SPI_SETCURSORS 로 사용자가 정해 둔 커서 모양(레지스트리)을 다시 불러온다: 사용자의 커서 설정은 건드리지 않는다.
 · 고양이가 갑자기 죽어도 커서가 투명한 채로 남지 않게, 숨겨 둔 동안 데이터 폴더에 표식 파일(cursor_swapped.flag)을 두고 다음에 켤 때(recover) 되돌린다.
   종료·놀이 끝·전체 화면 앱 등 어떤 경우에도 stop() 으로 되돌린다.
"""
import ctypes
import math
import time
from ctypes import wintypes
from pathlib import Path

import win32con
import win32gui
from PyQt6.QtCore import QPointF, QRectF, Qt, QTimer
from PyQt6.QtGui import QColor, QCursor, QPainter, QPainterPath, QPen, QPixmap
from PyQt6.QtWidgets import QWidget

W, H = 112, 112                             # 논리 픽셀: 나비 낚싯대 창 크기
HOT = (27.0, 25.0)                          # 마우스가 가리키는 점 = 나비 가운데 (창 안 좌표)
OCR_IDS = (32512, 32513, 32649)             # OCR_NORMAL(화살표), OCR_IBEAM(글자 입력), OCR_HAND(손가락)
SPI_SETCURSORS = 0x0057
FLAP = (1.0, 0.72, 0.42, 0.24, 0.42, 0.72)  # 날개를 펼친 정도 (1 = 활짝, 작을수록 접힘): 한 번 퍼덕이는 순서
FLAP_EVERY = 0.07                           # 초: 그림을 바꾸는 간격 (한 번 퍼덕이는 데 약 0.42초)
FOLLOW_MS = 10                              # 밀리초: 마우스를 따라가는 간격

_user32 = ctypes.windll.user32
_gdi32 = ctypes.windll.gdi32
_user32.CreateIconIndirect.restype = ctypes.c_void_p
_user32.CopyIcon.restype = ctypes.c_void_p
_user32.CopyIcon.argtypes = [ctypes.c_void_p]
_user32.SetSystemCursor.argtypes = [ctypes.c_void_p, wintypes.DWORD]
_user32.DestroyIcon.argtypes = [ctypes.c_void_p]
_user32.GetDC.restype = ctypes.c_void_p
_user32.ReleaseDC.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
_gdi32.CreateDIBSection.restype = ctypes.c_void_p
_gdi32.CreateDIBSection.argtypes = [ctypes.c_void_p, ctypes.c_void_p, wintypes.UINT, ctypes.POINTER(ctypes.c_void_p), ctypes.c_void_p, wintypes.DWORD]
_gdi32.CreateBitmap.restype = ctypes.c_void_p
_gdi32.CreateBitmap.argtypes = [ctypes.c_int, ctypes.c_int, wintypes.UINT, wintypes.UINT, ctypes.c_void_p]
_gdi32.DeleteObject.argtypes = [ctypes.c_void_p]


class _BitmapInfoHeader(ctypes.Structure):
    _fields_ = [("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG), ("biHeight", wintypes.LONG), ("biPlanes", wintypes.WORD),
                ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD), ("biSizeImage", wintypes.DWORD),
                ("biXPelsPerMeter", wintypes.LONG), ("biYPelsPerMeter", wintypes.LONG), ("biClrUsed", wintypes.DWORD),
                ("biClrImportant", wintypes.DWORD)]


class _IconInfo(ctypes.Structure):
    _fields_ = [("fIcon", wintypes.BOOL), ("xHotspot", wintypes.DWORD), ("yHotspot", wintypes.DWORD), ("hbmMask", ctypes.c_void_p),
                ("hbmColor", ctypes.c_void_p)]


# ---------------------------------------------------------------- 투명 커서 (진짜 커서 숨기기)
def _blank_cursor(n=32):
    """완전히 투명한 n×n 커서: 색 그림은 모두 0, AND 마스크는 모두 1(= 화면 그대로). 핫스팟은 왼쪽 위."""
    bi = _BitmapInfoHeader(ctypes.sizeof(_BitmapInfoHeader), n, -n, 1, 32, 0, 0, 0, 0, 0, 0)
    bits = ctypes.c_void_p()
    dc = _user32.GetDC(None)
    try:
        color = _gdi32.CreateDIBSection(dc, ctypes.byref(bi), 0, ctypes.byref(bits), None, 0)
    finally:
        _user32.ReleaseDC(None, dc)
    if not color or not bits:
        return None
    ctypes.memset(bits, 0, n * n * 4)
    row = (n + 15) // 16 * 2                                    # 1비트 그림의 한 줄 크기(바이트): 16픽셀(2바이트) 단위로 맞춘다
    ones = (ctypes.c_ubyte * (row * n))(*([0xFF] * (row * n)))
    mask = _gdi32.CreateBitmap(n, n, 1, 1, ctypes.byref(ones))
    info = _IconInfo(False, 0, 0, mask, color)
    h = _user32.CreateIconIndirect(ctypes.byref(info))
    _gdi32.DeleteObject(color)
    _gdi32.DeleteObject(mask)
    return h or None


def restore_cursors():
    """사용자가 정해 둔 커서 모양으로 되돌린다 (시스템 커서를 레지스트리에서 다시 불러온다)."""
    try:
        _user32.SystemParametersInfoW(SPI_SETCURSORS, 0, None, 0)
    except Exception:
        pass


# ---------------------------------------------------------------- 그림 (벡터)
def draw_wand(p: QPainter, flap: float):
    """나비를 단 가는 철심. 철심은 오른쪽 아래에서 위로 휘어 올라와 나비 몸통 아래에 닿는다 (flap: 날개를 펼친 정도 0.22~1)."""
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    hx, hy = HOT
    wire = QPainterPath()
    wire.moveTo(W - 7, H - 4)
    wire.cubicTo(W - 11, 72, 72, 38, hx - 2, hy + 7)
    for color, w in ((QColor(255, 255, 255, 120), 2.8), (QColor(88, 90, 104, 235), 1.05)):      # 어두운 바탕에서도 보이게 옅은 흰 테두리를 먼저
        pen = QPen(color, w)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(wire)
    p.save()                                                    # 나비: 몸 축을 왼쪽 위로 살짝 기울이고 작게
    p.translate(hx, hy)
    p.rotate(26)
    p.scale(0.7, 0.7)
    outline = QColor(76, 36, 30)

    def wing(sx, upper):
        path = QPainterPath()
        if upper:
            path.moveTo(1.5, -3)
            path.cubicTo(6, -22, 24, -26, 25, -10)
            path.cubicTo(25, -2, 13, 3, 1.5, 3)
        else:
            path.moveTo(1.5, 2)
            path.cubicTo(14, 2, 21, 9, 18, 17)
            path.cubicTo(14, 24, 4, 20, 1.5, 6)
        path.closeSubpath()
        p.save()
        p.scale(sx * max(0.22, flap), 1.0)                      # 좌우 날개를 펼친 정도만큼 가로로 줄인다 (퍼덕임)
        p.setPen(QPen(outline, 1.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        p.setBrush(QColor(232, 72, 38) if upper else QColor(247, 160, 36))
        p.drawPath(path)
        p.setPen(Qt.PenStyle.NoPen)                             # 날개 무늬: 노란 점
        p.setBrush(QColor(255, 214, 72))
        if upper:
            p.drawEllipse(QPointF(15, -13), 4.2, 3.2)
            p.drawEllipse(QPointF(9, -6), 2.4, 2.0)
        else:
            p.drawEllipse(QPointF(11, 12), 3.4, 2.8)
        p.restore()

    for sx in (-1, 1):
        wing(sx, False)
        wing(sx, True)
    p.setPen(Qt.PenStyle.NoPen)                                 # 몸통·머리·더듬이
    p.setBrush(QColor(52, 34, 40))
    p.drawEllipse(QPointF(0, 1), 2.6, 11)
    p.drawEllipse(QPointF(0, -11.5), 3.0, 3.0)
    ant = QPen(QColor(52, 34, 40), 1.5)
    ant.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(ant)
    p.setBrush(Qt.BrushStyle.NoBrush)
    for sx in (-1, 1):
        a = QPainterPath()
        a.moveTo(sx * 1.2, -14)
        a.quadTo(sx * 4.5, -23, sx * 9, -24)
        p.drawPath(a)
    p.restore()


class _Wand(QWidget):
    """마우스를 따라다니는 나비 낚싯대 창 (클릭 통과·포커스 안 가져감·항상 위)."""

    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool | Qt.WindowType.NoDropShadowWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.resize(W, H)
        dpr = self.devicePixelRatioF()
        self.frames = []                                        # 날개 모양별로 한 번만 그려 둔다 (화면 배율에 맞춰 또렷하게)
        for f in FLAP:
            pm = QPixmap(round(W * dpr), round(H * dpr))
            pm.setDevicePixelRatio(dpr)
            pm.fill(Qt.GlobalColor.transparent)
            q = QPainter(pm)
            draw_wand(q, f)
            q.end()
            self.frames.append(pm)
        self.i = 0
        self.show()
        self.hwnd = int(self.winId())
        ex = win32gui.GetWindowLong(self.hwnd, win32con.GWL_EXSTYLE)
        win32gui.SetWindowLong(self.hwnd, win32con.GWL_EXSTYLE, ex | win32con.WS_EX_NOACTIVATE | win32con.WS_EX_TOOLWINDOW | win32con.WS_EX_LAYERED
                               | win32con.WS_EX_TRANSPARENT)
        self.hide()

    def paintEvent(self, _):
        p = QPainter(self)
        try:
            p.drawPixmap(0, 0, self.frames[self.i])
        finally:
            p.end()

    def keep_on_top(self):
        try:
            win32gui.SetWindowPos(self.hwnd, win32con.HWND_TOPMOST, 0, 0, 0, 0,
                                  win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_NOACTIVATE | win32con.SWP_NOOWNERZORDER)
        except Exception:
            pass


# ---------------------------------------------------------------- 켜고 끄기
class FeatherCursor:
    def __init__(self, dpr: float, flag_path):
        self.flag = Path(flag_path)
        self.active = False
        self.wand = None
        self.timer = None
        self._pos = None
        self._top_at = 0.0

    def _hide_cursors(self):
        h = _blank_cursor()
        if not h:
            return False
        try:
            for oid in OCR_IDS:
                c = _user32.CopyIcon(h)                         # SetSystemCursor 는 넘겨 준 핸들을 가져가 버리므로 복사본을 준다
                if c:
                    _user32.SetSystemCursor(c, oid)
        finally:
            _user32.DestroyIcon(h)
        return True

    def start(self):
        if self.active:
            return True
        try:
            if self.wand is None:
                self.wand = _Wand()
                self.timer = QTimer()
                self.timer.setTimerType(Qt.TimerType.PreciseTimer)
                self.timer.setInterval(FOLLOW_MS)
                self.timer.timeout.connect(self._follow)
            self.flag.write_text("1", encoding="ascii")         # 숨겨 둔 동안만 있는 표식 (갑자기 꺼졌을 때 다음 시작에서 되돌리려고)
            if not self._hide_cursors():
                self.flag.unlink(missing_ok=True)
                return False
            self.active = True
            self._pos = None
            self._follow()
            self.wand.show()
            self.wand.keep_on_top()
            self.timer.start()
            return True
        except Exception:
            self.stop()
            return False

    def _follow(self):
        """마우스 자리로 나비를 옮기고, 날개를 퍼덕이는 그림으로 바꾼다."""
        w = self.wand
        if w is None or not self.active:
            return
        p = QCursor.pos()
        pos = (p.x(), p.y())
        if pos != self._pos:
            self._pos = pos
            w.move(p.x() - round(HOT[0]), p.y() - round(HOT[1]))
        now = time.monotonic()
        i = int(now / FLAP_EVERY) % len(w.frames)
        if i != w.i:
            w.i = i
            w.update()
        if now - self._top_at > 0.5:                            # 작업 표시줄 같은 다른 '항상 위' 창보다 뒤로 밀리지 않게
            self._top_at = now
            w.keep_on_top()

    def tick(self, now: float):
        """(프레임 루프에서 부른다. 따라가기는 자체 타이머가 하므로 할 일이 없다.)"""

    def stop(self):
        if self.timer is not None:
            self.timer.stop()
        if self.wand is not None:
            self.wand.hide()
        if self.active or self.flag.exists():
            restore_cursors()
            try:
                self.flag.unlink()
            except OSError:
                pass
        self.active = False

    def recover(self):
        """이전 실행이 커서를 숨긴 채 갑자기 꺼졌으면 되돌린다 (시작할 때 한 번)."""
        if self.flag.exists():
            restore_cursors()
            try:
                self.flag.unlink()
            except OSError:
                pass

    def close(self):
        self.stop()
        if self.wand is not None:
            self.wand.close()
            self.wand = None
