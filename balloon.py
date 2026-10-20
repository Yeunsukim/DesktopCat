"""여러 줄 풍선: 고양이 머리 위에서 일정 같은 긴 글을 보여 준다.

고양이의 한 줄 말풍선(Overlay._bubble)은 미리 그려 둔 짧은 문구용이라, 길고 줄이 바뀌는 글은 이 별도 창으로 보여 준다.
 · 포커스를 가져가지 않는 투명 최상위 창(WS_EX_NOACTIVATE). 고양이가 움직이면 머리 위로 따라간다.
 · 글은 보여 주기 전에 한 번만 그림으로 만들어 둔다 (이모지 글자를 매 프레임 그리면 느리다).
 · 글 길이에 따라 8~20초 뒤 사라지고, 마우스를 올려 두면 사라지지 않는다. 풍선을 클릭하면 on_click 을 부르고 닫는다.
"""
import time

import win32con
import win32gui
import cute
from PyQt6.QtCore import QPointF, QRect, QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPainterPath, QPen, QPixmap, QPolygonF
from PyQt6.QtWidgets import QWidget

OUTLINE = QColor(cute.INK)
TEXT = QColor(cute.INK)
MAX_W = 260                       # 글 폭(논리 픽셀). 넘으면 줄을 바꾼다
PAD_X, PAD_Y = 14, 10
TAIL = 11                         # 말풍선 꼬리 길이
AV = 38                           # 말하는 고양이 얼굴(동그란 원)의 지름
AV_SPACE = AV + 8                 # 글 왼쪽에 비워 두는 너비


class Balloon(QWidget):
    def __init__(self, head_fn, screens_fn):
        """head_fn() -> (화면 x, 머리 꼭대기 화면 y).  screens_fn() -> 작업 영역 목록."""
        super().__init__()
        self.head_fn, self.screens_fn = head_fn, screens_fn
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
                            | Qt.WindowType.Tool | Qt.WindowType.NoDropShadowWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setMouseTracking(True)
        self.on_click = None
        self._click = None
        self._pix = None
        self._until = 0.0
        self._pos = None
        self._avatar = (30.0, 30.0, 19.0)
        self._t_show = 0.0
        self._last_anim = 0.0
        self._queue = []                  # 대기 중인 풍선 [(줄들, 초, 클릭 동작)]
        self._font = QFont("Malgun Gothic", 10)
        self.show()
        hw = int(self.winId())
        ex = win32gui.GetWindowLong(hw, win32con.GWL_EXSTYLE)
        win32gui.SetWindowLong(hw, win32con.GWL_EXSTYLE, ex | win32con.WS_EX_NOACTIVATE | win32con.WS_EX_TOOLWINDOW)
        self.hwnd = hw
        self.hide()

    # ------------------------------------------------------------ 글 그림 만들기
    def _render(self, lines):
        """줄들을 하나의 풍선 그림(투명 배경)으로 그린다: 흰 풍선 + 굵은 윤곽선 + 아래 꼬리. 왼쪽에는 고양이 얼굴 자리를 비워 둔다.
        (그림, 풍선 크기) 를 돌려주고, 얼굴 위치는 self._avatar = (중심 x, 중심 y, 반지름) 에 적어 둔다."""
        dpr = self.devicePixelRatioF()
        fm = QFontMetrics(self._font)
        text = chr(10).join(lines)
        box = fm.boundingRect(QRect(0, 0, MAX_W, 4000), int(Qt.TextFlag.TextWordWrap), text)
        tw, th = max(box.width(), 60), box.height()
        w = tw + 2 * PAD_X + AV_SPACE
        h = max(th + 2 * PAD_Y, AV + 14)
        pm = QPixmap(round((w + 4) * dpr), round((h + TAIL + 4) * dpr))
        pm.setDevicePixelRatio(dpr)
        pm.fill(Qt.GlobalColor.transparent)
        q = QPainter(pm)
        q.setRenderHint(QPainter.RenderHint.Antialiasing)
        q.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        path = QPainterPath()
        path.addRoundedRect(QRectF(2, 2, w, h), 18, 18)
        cx = 2 + w * 0.5 + (AV_SPACE * 0.0)
        tail = QPainterPath()                                                  # 꼬리: 풍선과 한 덩어리로 합쳐서 윤곽선이 끊기지 않게
        tail.moveTo(cx - 9, 2 + h - 2)
        tail.lineTo(cx, 2 + h + TAIL)
        tail.lineTo(cx + 9, 2 + h - 2)
        tail.closeSubpath()
        path = path.united(tail)
        q.setPen(QPen(OUTLINE, 2.4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        q.setBrush(QColor(255, 255, 255, 250))
        q.drawPath(path)
        q.setFont(self._font)
        q.setPen(TEXT)
        q.drawText(QRectF(2 + PAD_X + AV_SPACE, 2 + (h - th) / 2, tw + 2, th + 2), int(Qt.TextFlag.TextWordWrap) | int(Qt.AlignmentFlag.AlignLeft), text)
        q.end()
        self._avatar = (2 + PAD_X * 0.6 + AV / 2 + 2, 2 + h / 2, AV / 2)
        return pm, (w + 4, h + TAIL + 4)

    # ------------------------------------------------------------ 보이기/숨기기
    def show_lines(self, lines, seconds=None, on_click=None):
        """on_click: 이번 풍선만의 클릭 동작(없으면 기본 on_click)."""
        self._click = on_click
        lines = [x for x in (cute.strip_emoji(l) for l in lines) if x]        # 풍선 글에는 이모티콘을 쓰지 않는다
        pm, (w, h) = self._render(lines)
        self._pix = pm
        self.resize(int(w), int(h))
        n = sum(len(x) for x in lines)
        self._until = time.monotonic() + (seconds if seconds is not None else min(20.0, 8.0 + 0.12 * n + 1.0 * len(lines)))
        self._pos = None
        self._t_show = time.monotonic()
        self._follow(force=True)
        self.show()
        self.raise_()
        self.update()

    def enqueue(self, lines, seconds=None, on_click=None):
        """정해 둔 알림용: 지금 풍선이 떠 있으면 그것이 닫힌 뒤에 보여 준다 (여러 알림이 동시에 와도 서로 덮어쓰지 않는다)."""
        if self.isVisible():
            self._queue.append((lines, seconds, on_click))
            del self._queue[:-6]                          # 너무 많이 쌓이면 오래된 것부터 버린다 (최근 6개만)
        else:
            self.show_lines(lines, seconds, on_click)

    def close_now(self):
        self._until = 0.0
        self.hide()

    @property
    def is_open(self):
        return self.isVisible()

    def _follow(self, force=False):
        hx, hy = self.head_fn()
        x = round(hx - self.width() / 2)
        y = round(hy - self.height() - 2)
        areas = self.screens_fn()
        if areas:
            a = min(areas, key=lambda r: 0.0 if r[0] <= hx <= r[2] else min(abs(hx - r[0]), abs(hx - r[2])))
            x = max(int(a[0]), min(x, int(a[2]) - self.width()))
            y = max(int(a[1]), min(y, int(a[3]) - self.height()))
        if force or (x, y) != self._pos:
            self._pos = (x, y)
            self.move(x, y)

    def tick(self):
        """매 프레임: 고양이를 따라가고, 시간이 다 되면 닫는다 (마우스가 위에 있으면 연장)."""
        if not self.isVisible():
            if self._queue:                                   # 앞 풍선이 닫혔으면 대기 중인 다음 풍선
                lines, secs, fn = self._queue.pop(0)
                self.show_lines(lines, secs, fn)
            return
        now = time.monotonic()
        if self.underMouse():
            self._until = max(self._until, now + 3.0)
        if now >= self._until:
            self.hide()
            return
        self._follow()
        if now - self._last_anim > 0.08:                      # 고양이 얼굴이 살아 움직이게 12프레임쯤으로 다시 그린다
            self._last_anim = now
            self.update()

    # ------------------------------------------------------------ 마우스/그리기
    def mouseReleaseEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton:
            self.hide()
            fn = self._click or self.on_click
            if fn:
                fn()

    def paintEvent(self, _):
        p = QPainter(self)
        try:
            if self._pix is not None:
                p.drawPixmap(0, 0, self._pix)
                t = time.monotonic() - self._t_show
                cx, cy, r = self._avatar
                cute.draw_cat_face(p, cx, cy, r, t, "talk" if t < 2.2 else "happy")      # 처음 2초는 입을 오물오물
        finally:
            p.end()
