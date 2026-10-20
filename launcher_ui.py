"""고양이를 클릭하면 머리 위에 열리는 반원(아치) 모양 앱 런처.

고양이 창(Overlay)과 별개의 프레임 없는 투명 최상위 창이다. 포커스를 가져가지 않아서(WS_EX_NOACTIVATE) 쓰던 작업을 방해하지 않는다.
 · 아이콘은 호(arc)를 따라 놓이고, 마우스를 올리면 가운데 빈 곳에 이름이 나온다.
 · 기본 아이콘 2개(캘린더, Gmail) + 사용자가 등록한 앱(설정 파일의 apps). 7개를 넘으면 양 끝의 화살표로 쪽을 넘긴다.
 · 닫히는 때: 다시 클릭 / 바깥 클릭 / Esc / 8초 동안 마우스가 아치 위에 없을 때 / 고양이가 다른 일을 시작했을 때.
 · 아치 모양으로만 마우스를 받는다(setMask). 나머지 투명한 곳은 클릭이 그대로 아래 창으로 간다.
"""
import math
import os
import subprocess
import time

import win32api
import win32con
import win32gui
from PyQt6.QtCore import QFileInfo, QPoint, QPointF, QRect, QRectF, Qt
from PyQt6.QtGui import (QBrush, QColor, QFont, QFontMetrics, QPainter, QPainterPath, QPen, QPixmap, QPolygonF, QRegion)
import cute
import favicon
from PyQt6.QtWidgets import QFileIconProvider, QWidget

OUTLINE = QColor(90, 58, 71)       # 자두색 윤곽선 (cute.INK)
TEXT = QColor(90, 58, 71)
R_MID = 98.0                    # 아이콘이 놓이는 호의 반지름 (아이콘 사이가 넉넉하도록 74 → 98)
BAND = 25.0                     # 띠의 반폭 (아이콘 지름 32 + 위아래 여유)
SRC = 64                        # 아이콘 그림을 만드는 크기 (화면에는 ICON 으로 줄여서 그린다)
ICON = 32                       # 화면에 그리는 아이콘 크기(논리 픽셀)
PER_PAGE = 5                    # 한 쪽에 놓는 아이콘 수 (호가 짧아져서 5개 + 양 끝 화살표)
ANG0, ANG1 = 12.0, 168.0        # 아이콘 호의 시작/끝 각도 (도, 오른쪽 수평 = 0, 위 = 90)
IDLE_SECONDS = 8.0
OPEN_SECONDS = 0.16             # 열릴 때 커지는 시간
ROLL_SECONDS = 0.34             # 쪽을 넘길 때 아이콘이 굴러가는 시간
ROLL_SHIFT = 95.0               # 굴러가는 각도(도)

CALENDAR_URL = "https://calendar.google.com/calendar/u/0/r"
GMAIL_URL = "https://mail.google.com/"
GOOGLE_URL = "https://www.google.com/"
YOUTUBE_URL = "https://www.youtube.com/"


# ---------------------------------------------------------------- 아이콘 그리기 (상표 그림을 쓰지 않고 직접 그린다)
def _blank(dpr):
    pm = QPixmap(round(SRC * dpr), round(SRC * dpr))
    pm.setDevicePixelRatio(dpr)
    pm.fill(Qt.GlobalColor.transparent)
    return pm


def icon_calendar(dpr):
    pm = _blank(dpr)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    r = QRectF(4, 4, SRC - 8, SRC - 8)
    p.setPen(QPen(QColor(60, 100, 200), 1.6))
    p.setBrush(QColor(255, 255, 255))
    p.drawRoundedRect(r, 5, 5)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(66, 133, 244))
    top = QPainterPath()
    top.addRoundedRect(QRectF(r.left(), r.top(), r.width(), 11), 5, 5)
    top.addRect(QRectF(r.left(), r.top() + 6, r.width(), 5))
    p.drawPath(top.simplified())
    p.setPen(QColor(255, 255, 255))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.setPen(QPen(QColor(255, 255, 255), 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    p.drawLine(QPointF(r.left() + 9, r.top() + 1.5), QPointF(r.left() + 9, r.top() + 5))
    p.drawLine(QPointF(r.right() - 9, r.top() + 1.5), QPointF(r.right() - 9, r.top() + 5))
    f = QFont("Malgun Gothic", 10)
    f.setBold(True)
    p.setFont(f)
    p.setPen(QColor(50, 90, 190))
    p.drawText(QRectF(r.left(), r.top() + 11, r.width(), r.height() - 11), Qt.AlignmentFlag.AlignCenter,
               str(time.localtime().tm_mday))
    p.end()
    return pm


def icon_mail(dpr):
    pm = _blank(dpr)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    r = QRectF(3.5, 8, SRC - 7, SRC - 16)
    p.setPen(QPen(QColor(200, 70, 60), 1.8))
    p.setBrush(QColor(255, 255, 255))
    p.drawRoundedRect(r, 3.5, 3.5)
    p.setPen(QPen(QColor(215, 70, 60), 2.4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawPolyline(QPolygonF([QPointF(r.left() + 2, r.top() + 3), QPointF(r.center().x(), r.center().y() + 3),
                              QPointF(r.right() - 2, r.top() + 3)]))
    p.end()
    return pm


def icon_globe(dpr):
    pm = _blank(dpr)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    r = QRectF(5, 5, SRC - 10, SRC - 10)
    p.setPen(QPen(QColor(40, 100, 170), 1.6))
    p.setBrush(QColor(110, 180, 235))
    p.drawEllipse(r)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.setPen(QPen(QColor(255, 255, 255, 220), 1.3))
    p.drawEllipse(QRectF(r.center().x() - 5, r.top(), 10, r.height()))
    p.drawLine(QPointF(r.left(), r.center().y()), QPointF(r.right(), r.center().y()))
    p.end()
    return pm


def icon_arrow(dpr, right):
    pm = _blank(dpr)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(QPen(QColor(90, 80, 75), 3.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    c = SRC / 2
    d = 7 if right else -7
    p.drawPolyline(QPolygonF([QPointF(c - d / 2, c - 9), QPointF(c + d / 2, c), QPointF(c - d / 2, c + 9)]))
    p.end()
    return pm


_provider = None


def icon_for_app(a, dpr, icons_dir):
    """등록한 앱의 귀여운 아이콘: 웹 주소는 사이트 파비콘(없으면 귀여운 지구본), 명령 창은 고양이 귀 터미널, 윈도우 도구는 톱니바퀴,
    프로그램·파일은 윈도우가 주는 아이콘을 동그란 스티커 안에."""
    kind = a.get("kind", "file")
    if kind == "url":
        pm = favicon.load(icons_dir, a["target"]) if icons_dir else None
        return cute.sticker_for(pm, dpr) if pm is not None else cute.icon_globe(dpr)
    if kind == "cmd":
        return cute.icon_terminal(dpr)
    if kind == "sys":
        return cute.icon_tools(dpr)
    return cute.sticker_for(file_pixmap(a["target"]), dpr)


def _crop_to_content(pm):
    """투명한 여백을 잘라내고 그림이 있는 부분만 남긴다 (아이콘이 점처럼 작게 보이는 것을 막는다)."""
    import numpy as np
    img = pm.toImage().convertToFormat(pm.toImage().Format.Format_ARGB32)
    ptr = img.constBits()
    ptr.setsize(img.sizeInBytes())
    al = np.frombuffer(ptr, np.uint8).reshape(img.height(), img.width(), 4)[:, :, 3]
    ys, xs = np.where(al > 20)
    if not len(xs):
        return pm
    x0, y0, x1, y1 = int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())
    return pm.copy(x0, y0, x1 - x0 + 1, y1 - y0 + 1)


def file_pixmap(path):
    """프로그램·파일의 윈도우 아이콘 (못 가져오면 None)."""
    global _provider
    try:
        if _provider is None:
            _provider = QFileIconProvider()
        pm = _provider.icon(QFileInfo(path)).pixmap(48, 48)          # 48 을 요청하면 정확히 48px 그림이 온다 (64 를 요청하면 256 캔버스 구석에 작게 담겨 온다)
        if pm.isNull():
            return None
        return _crop_to_content(pm)
    except Exception:
        return None


def launch(e):
    """항목 실행. file/url: 윈도우가 알아서 연다. cmd: 명령 창(cmd 또는 PowerShell)을 열고 명령을 친다. sys: 제어판·설정 같은 윈도우 도구."""
    kind, target = e.get("kind", "file"), e["target"]
    if kind == "cmd":
        keep = e.get("keep", True)
        if e.get("shell") == "powershell":
            cmd = ["powershell"] + (["-NoExit"] if keep else []) + ["-Command", target]
        else:
            cmd = ("cmd /k " if keep else "cmd /c ") + target
        subprocess.Popen(cmd, creationflags=0x00000010)            # CREATE_NEW_CONSOLE: 새 명령 창
    elif kind == "sys":
        parts = target.split(None, 1)
        if len(parts) == 2 and not target.lower().startswith("ms-settings:"):
            subprocess.Popen(parts)                                  # 예: control appwiz.cpl
        else:
            os.startfile(target)
    else:
        os.startfile(target)


def icon_for_file(path, dpr):
    """등록한 프로그램의 윈도우 아이콘 (exe·바로가기·문서). 못 가져오면 지구본."""
    global _provider
    try:
        if _provider is None:
            _provider = QFileIconProvider()
        ic = _provider.icon(QFileInfo(path))
        pm = ic.pixmap(round(SRC * dpr), round(SRC * dpr))
        if pm.isNull():
            return icon_globe(dpr)
        pm.setDevicePixelRatio(dpr)
        return pm
    except Exception:
        return icon_globe(dpr)


class LauncherBubble(QWidget):
    def __init__(self, brain, settings, head_fn, screens_fn, icons_dir=None):
        """head_fn() -> (화면 x, 머리 꼭대기 화면 y) 논리 픽셀.  screens_fn() -> [(left, top, right, bottom), ...] 작업 영역들.
        icons_dir: 웹사이트 파비콘을 보관한 폴더."""
        super().__init__()
        self.brain, self.settings, self.head_fn, self.screens_fn = brain, settings, head_fn, screens_fn
        self.icons_dir = icons_dir
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
                            | Qt.WindowType.Tool | Qt.WindowType.NoDropShadowWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setMouseTracking(True)
        self.R_O = R_MID + BAND + 6
        self.W, self.H = int(2 * self.R_O + 12), int(self.R_O + 34 + 10)       # 위쪽 10 은 이름 알약이 아치 위에 얹히는 자리
        self.resize(self.W, self.H)
        self.center = QPointF(self.W / 2, self.H - 20)           # 호의 중심(창 안 좌표)
        self.is_open = False
        self.page = 0
        self.hover = -1
        self.items = []                                           # 이번 쪽에 보이는 것: dict(name, pix, act, pos)
        self._all = []
        self._roll = None                                         # 쪽 넘기는 중이면 (시작 시각, 방향, 나가는 항목들)
        self._t_open = 0.0
        self._last_act = 0.0
        self._mouse_was_down = False
        self._esc_was_down = False
        self._pos = None
        self._font = QFont("Malgun Gothic", 9)
        self._font.setBold(True)
        self.on_register = None                                   # 호출되면 '앱 등록' 창을 연다(cat.py 가 연결)
        self.show()
        self.hwnd = int(self.winId())
        ex = win32gui.GetWindowLong(self.hwnd, win32con.GWL_EXSTYLE)
        win32gui.SetWindowLong(self.hwnd, win32con.GWL_EXSTYLE, ex | win32con.WS_EX_NOACTIVATE | win32con.WS_EX_TOOLWINDOW)
        self.hide()
        self._build_mask()

    # ------------------------------------------------------------ 모양
    def _band_path(self, grow=0.0):
        """아이콘 호를 감싸는 아치 모양 띠 (창 안 좌표). 양 끝은 둥글다."""
        ro, ri = R_MID + BAND + grow, R_MID - BAND - grow
        cx, cy = self.center.x(), self.center.y()
        a0, a1 = ANG0, ANG1
        path = QPainterPath()
        path.arcMoveTo(QRectF(cx - ro, cy - ro, 2 * ro, 2 * ro), a0)
        path.arcTo(QRectF(cx - ro, cy - ro, 2 * ro, 2 * ro), a0, a1 - a0)
        path.lineTo(cx + ri * math.cos(math.radians(a1)), cy - ri * math.sin(math.radians(a1)))
        path.arcTo(QRectF(cx - ri, cy - ri, 2 * ri, 2 * ri), a1, -(a1 - a0))
        path.closeSubpath()
        # 양 끝 둥근 마개를 원으로 덧붙인다
        for ang in (a0, a1):
            px = cx + R_MID * math.cos(math.radians(ang))
            py = cy - R_MID * math.sin(math.radians(ang))
            cap = QPainterPath()
            cap.addEllipse(QPointF(px, py), BAND + grow, BAND + grow)
            path = path.united(cap)
        return path

    def _build_mask(self):
        """마우스를 받는(=그려지는) 영역: 아치 모양(조금 넉넉하게) + 이름 표시 자리 — 나머지는 아래 창으로 클릭이 간다."""
        poly = self._band_path(3.0).toFillPolygon().toPolygon()
        reg = QRegion(poly)
        r = self._label_rect()
        if r is not None:
            reg = reg.united(QRegion(r))
        self._band_region = QRegion(poly)
        self.setMask(reg)

    def _label_rect(self):
        """마우스를 올린 항목의 이름이 놓이는 사각형(아치 안쪽 빈 곳 가운데). 올린 항목이 없으면 None."""
        if not (0 <= self.hover < len(self.items)):
            return None
        fm = QFontMetrics(self._font)
        name = fm.elidedText(self.items[self.hover]["name"], Qt.TextElideMode.ElideRight, 150)
        w = fm.horizontalAdvance(name) + 24
        top = self.center.y() - (R_MID + BAND)                     # 아치 맨 위
        return QRect(int(self.center.x() - w / 2), int(top - 24 - 3), w, 24)       # 알약이 아치 바로 위에 얹힌다(간격 3)

    # ------------------------------------------------------------ 항목
    def _make_items(self):
        dpr = self.devicePixelRatioF()
        items = [
            {"name": "구글 캘린더", "pix": cute.icon_calendar(dpr), "kind": "url", "target": CALENDAR_URL},
            {"name": "Gmail", "pix": cute.icon_mail(dpr), "kind": "url", "target": GMAIL_URL},
            {"name": "구글", "pix": cute.icon_google(dpr), "kind": "url", "target": GOOGLE_URL},
            {"name": "유튜브", "pix": cute.icon_youtube(dpr), "kind": "url", "target": YOUTUBE_URL},
        ]
        for a in self.settings.apps:
            e = dict(a)
            e["pix"] = icon_for_app(a, dpr, self.icons_dir)
            e["kind"] = a.get("kind", "file")
            items.append(e)
        self._all = items

    def _layout_page(self):
        n = len(self._all)
        pages = max(1, math.ceil(n / PER_PAGE))
        self.page = max(0, min(self.page, pages - 1))
        chunk = self._all[self.page * PER_PAGE:(self.page + 1) * PER_PAGE]
        dpr = self.devicePixelRatioF()
        entries = list(chunk)
        if pages > 1:                                             # 양 끝에 쪽 넘기기 화살표
            entries = [{"name": "이전", "pix": cute.icon_chevron(dpr, False), "kind": "prev"}] + entries + \
                      [{"name": "다음", "pix": cute.icon_chevron(dpr, True), "kind": "next"}]
        m = len(entries)
        for i, e in enumerate(entries):
            ang = ANG1 - 8.0 - (ANG1 - ANG0 - 16.0) * (i / (m - 1)) if m > 1 else 90.0       # 왼쪽 끝(큰 각도)에서 오른쪽 끝으로 고르게
            e["ang"] = ang
            e["pos"] = self._pos_at(ang)
        self.items = entries

    def _pos_at(self, ang):
        return QPointF(self.center.x() + R_MID * math.cos(math.radians(ang)),
                       self.center.y() - R_MID * math.sin(math.radians(ang)))

    def _flip(self, d):
        """쪽 넘기기: d=+1 다음, -1 이전. 나가는 아이콘은 반대쪽으로 굴러가며 사라지고 새 아이콘이 굴러 들어온다."""
        old = [e for e in self.items if e["kind"] not in ("prev", "next")]
        n = max(1, math.ceil(len(self._all) / PER_PAGE))
        self.page = (self.page + d) % n
        self._layout_page()
        self._roll = (time.monotonic(), d, old)
        self.hover = -1
        self._build_mask()
        self.update()

    # ------------------------------------------------------------ 열기/닫기
    def toggle(self):
        if self.is_open:
            self.close_now()
        else:
            self.open_now()

    def open_now(self):
        b = self.brain
        if b.is_busy():
            return                                                 # 점프·낙하·집어 올리기 중에는 열지 않는다
        b.think(True)
        self.page = 0
        self.hover = -1
        self._make_items()
        self._layout_page()
        self._build_mask()
        self._follow(force=True)
        self.is_open = True
        self._t_open = self._last_act = time.monotonic()
        self._mouse_was_down = bool(win32api.GetAsyncKeyState(win32con.VK_LBUTTON) & 0x8000)
        self._esc_was_down = bool(win32api.GetAsyncKeyState(win32con.VK_ESCAPE) & 0x8000)
        self.show()
        self.raise_()

    def close_now(self):
        if not self.is_open:
            return
        self.is_open = False
        self.hide()
        self.brain.think(False)

    def _follow(self, force=False):
        """고양이 머리 위로 위치를 맞춘다. 화면 밖으로 나가면 화면 안으로 당긴다."""
        hx, hy = self.head_fn()
        x = round(hx - self.center.x())
        y = round(hy + 46 - self.center.y())                       # 호의 중심이 머리 꼭대기보다 조금 아래: 아치 양 끝이 머리 옆을 감싼다
        areas = self.screens_fn()
        if areas:
            a = min(areas, key=lambda r: 0.0 if r[0] <= hx <= r[2] else min(abs(hx - r[0]), abs(hx - r[2])))
            x = max(int(a[0]), min(x, int(a[2]) - self.W))
            y = max(int(a[1]), min(y, int(a[3]) - self.H))
        if force or (x, y) != self._pos:
            self._pos = (x, y)
            self.move(x, y)

    # ------------------------------------------------------------ 매 프레임 (cat.py 의 frame_body 가 부른다)
    def tick(self):
        if not self.is_open:
            return
        now = time.monotonic()
        b = self.brain
        if not b.thinking or b.state.name != "SITTILT":
            self.close_now()                                       # 고양이가 집어 올려지거나 다른 일을 시작했다
            return
        self._follow()
        gp = win32api.GetCursorPos()
        gp = (gp[0] / self.devicePixelRatioF(), gp[1] / self.devicePixelRatioF())
        inside = self._inside_band(gp)
        if inside:
            self._last_act = now
        elif now - self._last_act > IDLE_SECONDS:
            self.close_now()
            return
        down = bool(win32api.GetAsyncKeyState(win32con.VK_LBUTTON) & 0x8000)
        if down and not self._mouse_was_down and not inside and not self._on_cat(gp):
            self.close_now()                                       # 바깥을 눌렀다 (고양이를 누르면 고양이 쪽에서 닫는다)
            return
        self._mouse_was_down = down
        esc = bool(win32api.GetAsyncKeyState(win32con.VK_ESCAPE) & 0x8000)
        if esc and not self._esc_was_down:
            self.close_now()
            return
        self._esc_was_down = esc
        if self._roll is not None:
            if now - self._roll[0] >= ROLL_SECONDS:
                self._roll = None
            self.update()
        elif now - self._t_open < OPEN_SECONDS + 0.05:
            self.update()                                          # 커지는 동안만 다시 그린다

    def _inside_band(self, gpos):
        lx, ly = gpos[0] - self.x(), gpos[1] - self.y()
        return 0 <= lx < self.W and 0 <= ly < self.H and self._band_region.contains(QPoint(int(lx), int(ly)))

    def _on_cat(self, gpos):
        x, y, w, h = self.brain.hit_rect
        return x <= gpos[0] <= x + w and y <= gpos[1] <= y + h

    # ------------------------------------------------------------ 마우스
    def _item_at(self, pt):
        if self._roll is not None:
            return -1                                              # 굴러가는 동안에는 누를 수 없다
        for i, e in enumerate(self.items):
            if math.hypot(pt.x() - e["pos"].x(), pt.y() - e["pos"].y()) <= ICON / 2 + 2:
                return i
        return -1

    def mouseMoveEvent(self, ev):
        i = self._item_at(ev.position())
        if i != self.hover:
            self.hover = i
            self._build_mask()
            self.update()
        self._last_act = time.monotonic()

    def leaveEvent(self, _):
        if self.hover != -1:
            self.hover = -1
            self._build_mask()
            self.update()

    def mouseReleaseEvent(self, ev):
        if ev.button() != Qt.MouseButton.LeftButton:
            return
        i = self._item_at(ev.position())
        if i < 0:
            return
        e = self.items[i]
        kind = e["kind"]
        if kind in ("prev", "next"):
            self._flip(-1 if kind == "prev" else 1)
            return
        self.run(e)

    def run(self, e):
        """항목을 실행하고 런처를 닫는다."""
        try:
            launch(e)
            self.brain.say("냐옹~", 1.2)
        except Exception:
            self.brain.say("못 열겠다냐옹.. 😿", 2.5)
        self.close_now()

    # ------------------------------------------------------------ 그리기
    def paintEvent(self, _):
        p = QPainter(self)
        try:
            self._paint(p)
        finally:
            p.end()

    @staticmethod
    def _edge_fade(ang):
        """호의 양 끝(화살표 자리)에 가까워지면 0 으로: 굴러가는 아이콘이 화살표 아래로 사라지는 것처럼 보이게."""
        lo, hi = ANG0 + 6.0, ANG1 - 6.0
        x = min(ang - lo, hi - ang) / 14.0
        x = max(0.0, min(1.0, x))
        return x * x * (3 - 2 * x)

    def _draw_item(self, p, e, pos, alpha, hovered):
        if alpha <= 0.01:
            return
        p.save()
        p.setOpacity(p.opacity() * alpha)
        if hovered:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(246, 116, 153, 70))                      # 마우스를 올리면 분홍빛이 번진다
            p.drawEllipse(pos, ICON / 2 + 5, ICON / 2 + 5)
        sz = ICON * (1.12 if hovered else 1.0)
        p.drawPixmap(QRectF(pos.x() - sz / 2, pos.y() - sz / 2, sz, sz), e["pix"], QRectF(e["pix"].rect()))
        p.restore()

    def _paint(self, p):
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        k = min(1.0, (time.monotonic() - self._t_open) / OPEN_SECONDS)
        k = 1 - (1 - k) ** 3                                       # 열릴 때 부드럽게 커진다
        p.translate(self.center)
        p.scale(0.6 + 0.4 * k, 0.6 + 0.4 * k)
        p.translate(-self.center)
        p.setOpacity(k)
        path = self._band_path()
        p.setPen(QPen(OUTLINE, 2.4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        p.setBrush(QColor(255, 246, 249, 246))
        p.drawPath(path)
        roll = self._roll
        if roll is None:
            for i, e in enumerate(self.items):
                self._draw_item(p, e, e["pos"], 1.0, i == self.hover)
        else:
            t0, d, old = roll
            k = min(1.0, (time.monotonic() - t0) / ROLL_SECONDS)
            k = 1 - (1 - k) ** 3                                   # 처음엔 빠르게, 끝에서 부드럽게 멈춘다
            for e in self.items:
                if e["kind"] in ("prev", "next"):
                    self._draw_item(p, e, e["pos"], 1.0, False)
            for e in old:                                          # 나가는 아이콘: 진행 방향으로 굴러가며 옅어진다
                ang = e["ang"] + d * ROLL_SHIFT * k
                self._draw_item(p, e, self._pos_at(ang), (1.0 - k) * self._edge_fade(ang), False)
            for e in self.items:                                   # 들어오는 아이콘: 반대쪽에서 굴러 들어오며 진해진다
                if e["kind"] not in ("prev", "next"):
                    ang = e["ang"] - d * ROLL_SHIFT * (1.0 - k)
                    self._draw_item(p, e, self._pos_at(ang), k * self._edge_fade(ang), False)
        r = self._label_rect()
        if r is not None:                                          # 이름은 아치 안쪽 빈 곳 가운데에 알약 모양으로
            p.setPen(QPen(OUTLINE, 2.0))
            p.setBrush(QColor(255, 255, 255, 250))
            p.drawRoundedRect(QRectF(r), 12, 12)
            p.setFont(self._font)
            p.setPen(TEXT)
            fm = QFontMetrics(self._font)
            p.drawText(QRectF(r), Qt.AlignmentFlag.AlignCenter,
                       fm.elidedText(self.items[self.hover]["name"], Qt.TextElideMode.ElideRight, 150))
