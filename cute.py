"""러블리 분홍 디자인의 공용 부품: 팔레트, 동그란 원 안의 만화풍 고양이 얼굴(살아 움직임), 귀여운 아이콘.

모든 창(메뉴·풍선·소식 창·설정·런처)이 같은 분홍 팔레트와 '굵은 윤곽선 스티커' 느낌을 쓰고,
말하는 쪽에는 항상 이 고양이 얼굴(CatAvatar)이 붙어서 '고양이가 알려 준다'는 느낌이 나게 한다.
고양이 얼굴과 아이콘은 모두 QPainter 로 직접 그린 벡터라서 어떤 크기·화면 배율에서도 또렷하고 따로 그림 파일이 필요 없다.
"""
import math
import time

from PyQt6.QtCore import QPointF, QRectF, Qt, QTimer
from PyQt6.QtGui import QBrush, QColor, QFont, QPainter, QPainterPath, QPen, QPixmap, QPolygonF
from PyQt6.QtWidgets import QWidget

# ---------------------------------------------------------------- 팔레트 (참고 사이트의 분홍 #f67499, #ef99b1 을 바탕으로)
BG = "#FFE6EE"          # 창 바탕: 아주 연한 분홍
BG2 = "#FFD3E0"         # 조금 진한 연분홍 (선택·강조 바탕)
CARD = "#FFFFFF"
PINK = "#F67499"        # 대표 분홍
PINK_D = "#E5557E"      # 눌렀을 때·글씨용 진한 분홍
PINK_L = "#EF99B1"      # 옅은 분홍 (원 바탕, 테두리)
LINE = "#F6C5D5"        # 테두리
INK = "#5A3A47"         # 윤곽선·글씨(검정 대신 자두색: 부드럽지만 또렷)
SUB = "#A8728A"         # 보조 글씨
OK = "#3FA373"
WARN = "#D8456F"
Q = QColor


def qc(hexstr, alpha=255):
    c = QColor(hexstr)
    c.setAlpha(alpha)
    return c


# ---------------------------------------------------------------- 고양이 얼굴 (원 안의 만화 삽화)
def draw_cat_face(p: QPainter, cx: float, cy: float, r: float, t: float = 0.0, mood: str = "happy", ring: bool = True,
                  bg: str = PINK):
    """중심 (cx, cy), 반지름 r 인 분홍 원 안에 만화풍 고양이 얼굴을 그린다.
    t: 시간(초) — 눈 깜빡임·귀 쫑긋·가벼운 까딱임에 쓴다.  mood: happy(^ ^) / normal(동그란 눈) / sleep(— —) / talk(말하는 입) / heart(하트 눈)."""
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    bob = math.sin(t * 2.2) * 0.025                                   # 머리가 살짝 까딱
    p.translate(cx, cy)
    p.scale(r, r)
    ink = QPen(qc(INK), 0.075, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    # 바탕 원
    circle = QPainterPath()
    circle.addEllipse(QPointF(0, 0), 1.0, 1.0)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(qc(bg))
    p.drawPath(circle)
    # 원 안으로만 그리는 부분(몸·팔): 아래쪽을 잘라낸다
    p.save()
    p.setClipPath(circle)
    p.translate(0, bob * 0.5)
    body = QPainterPath()
    body.addRoundedRect(QRectF(-0.62, 0.50, 1.24, 0.9), 0.35, 0.35)
    p.setPen(ink)
    p.setBrush(qc(INK))
    p.drawPath(body)
    for sx in (-1, 1):                                                # 하얀 앞발
        p.setBrush(QColor("white"))
        p.drawEllipse(QPointF(sx * 0.60, 0.56), 0.15, 0.15)
    p.restore()
    p.translate(0, bob)
    # 귀 (원 밖으로 살짝 튀어나온다). 가끔 한쪽 귀를 쫑긋
    twitch = 0.0
    ph = (t % 5.0)
    if ph < 0.35:
        twitch = math.sin(ph / 0.35 * math.pi) * 0.09
    for sx in (-1, 1):
        ear = QPainterPath()
        tip_y = -1.0 - (twitch if sx > 0 else 0.0)
        ear.moveTo(sx * 0.60, -0.22)
        ear.lineTo(sx * 0.52, tip_y)
        ear.lineTo(sx * 0.12, -0.52)
        ear.closeSubpath()
        p.setPen(ink)
        p.setBrush(QColor("white"))
        p.drawPath(ear)
        inner = QPainterPath()
        inner.moveTo(sx * 0.50, -0.36)
        inner.lineTo(sx * 0.46, tip_y + 0.22)
        inner.lineTo(sx * 0.24, -0.50)
        inner.closeSubpath()
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(qc(PINK_L))
        p.drawPath(inner)
    # 얼굴
    face = QPainterPath()
    face.addEllipse(QPointF(0, -0.04), 0.66, 0.52)
    p.setPen(ink)
    p.setBrush(QColor("white"))
    p.drawPath(face)
    # 볼터치
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(qc(PINK_L, 190))
    for sx in (-1, 1):
        p.drawEllipse(QPointF(sx * 0.40, 0.09), 0.11, 0.065)
    # 눈
    blink = (t % 3.6) > 3.48
    eye_y = -0.07
    if mood == "heart":
        for sx in (-1, 1):
            h = QPainterPath()
            x0, y0 = sx * 0.26, eye_y
            h.moveTo(x0, y0 + 0.10)
            h.cubicTo(x0 - 0.20, y0 - 0.04, x0 - 0.08, y0 - 0.17, x0, y0 - 0.06)
            h.cubicTo(x0 + 0.08, y0 - 0.17, x0 + 0.20, y0 - 0.04, x0, y0 + 0.10)
            p.setBrush(qc(PINK_D))
            p.drawPath(h)
    elif mood in ("happy", "talk") or blink or mood == "sleep":
        p.setPen(QPen(qc(INK), 0.07, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.setBrush(Qt.BrushStyle.NoBrush)
        for sx in (-1, 1):
            a = QPainterPath()
            if mood == "sleep" or (blink and mood == "normal"):
                a.moveTo(sx * 0.26 - 0.10, eye_y + 0.02)
                a.lineTo(sx * 0.26 + 0.10, eye_y + 0.02)
            else:                                                      # ^ 모양 웃는 눈
                a.moveTo(sx * 0.26 - 0.10, eye_y + 0.05)
                a.quadTo(sx * 0.26, eye_y - 0.12, sx * 0.26 + 0.10, eye_y + 0.05)
            p.drawPath(a)
    else:
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(qc(INK))
        for sx in (-1, 1):
            p.drawEllipse(QPointF(sx * 0.26, eye_y), 0.065, 0.085)
            p.setBrush(QColor("white"))
            p.drawEllipse(QPointF(sx * 0.26 + 0.02, eye_y - 0.03), 0.02, 0.02)
            p.setBrush(qc(INK))
    # 코·입
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(qc(PINK_D))
    nose = QPolygonF([QPointF(-0.045, 0.045), QPointF(0.045, 0.045), QPointF(0, 0.095)])
    p.drawPolygon(nose)
    p.setPen(QPen(qc(INK), 0.055, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    p.setBrush(Qt.BrushStyle.NoBrush)
    if mood == "talk":
        open_k = 0.5 + 0.5 * math.sin(t * 9.0)
        m = QPainterPath()
        m.addEllipse(QPointF(0, 0.20), 0.06 + 0.02 * open_k, 0.035 + 0.05 * open_k)
        p.setBrush(qc(PINK_D))
        p.drawPath(m)
    else:
        m = QPainterPath()
        m.moveTo(0, 0.095)
        m.lineTo(0, 0.14)
        m.moveTo(-0.11, 0.14)
        m.quadTo(-0.055, 0.215, 0, 0.14)
        m.quadTo(0.055, 0.215, 0.11, 0.14)                               # ω 모양 입
        p.drawPath(m)
    # 수염
    p.setPen(QPen(qc(INK), 0.035, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    for sx in (-1, 1):
        for dy, ang in ((0.07, -0.10), (0.15, 0.10)):
            p.drawLine(QPointF(sx * 0.56, dy), QPointF(sx * 0.80, dy + ang))
    p.restore()
    if ring:                                                          # 원 테두리(아바타 가장자리)
        p.save()
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setPen(QPen(QColor("white"), max(1.5, r * 0.07)))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QPointF(cx, cy), r - 0.5, r - 0.5)
        p.restore()


class CatAvatar(QWidget):
    """창 머리말에 붙이는 살아 있는 고양이 얼굴. mood 를 바꿀 수 있고, 보이는 동안만 12프레임으로 움직인다."""

    def __init__(self, size=44, mood="happy", parent=None):
        super().__init__(parent)
        self.mood = mood
        self.setFixedSize(size, size)
        self._t0 = time.monotonic()
        self._timer = QTimer(self)
        self._timer.setInterval(85)
        self._timer.timeout.connect(self.update)

    def showEvent(self, e):
        self._timer.start()
        super().showEvent(e)

    def hideEvent(self, e):
        self._timer.stop()
        super().hideEvent(e)

    def paintEvent(self, _):
        p = QPainter(self)
        try:
            s = min(self.width(), self.height())
            draw_cat_face(p, self.width() / 2, self.height() / 2, s / 2 - 1, time.monotonic() - self._t0, self.mood)
        finally:
            p.end()


# ---------------------------------------------------------------- 귀여운 아이콘 (64x64 칸에 그린다)
S = 64


def _pm(dpr, size=S):
    pm = QPixmap(round(size * dpr), round(size * dpr))
    pm.setDevicePixelRatio(dpr)
    pm.fill(Qt.GlobalColor.transparent)
    return pm


def _begin(pm):
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    p.scale(pm.width() / pm.devicePixelRatio() / S, pm.height() / pm.devicePixelRatio() / S)
    return p


def _pen(w=2.6):
    return QPen(qc(INK), w, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)


def _face(p, x, y, k=1.0):
    """아이콘 위에 얹는 작은 얼굴 (점 눈 + 볼터치 + 웃는 입)."""
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(qc(PINK_L, 200))
    for sx in (-1, 1):
        p.drawEllipse(QPointF(x + sx * 9 * k, y + 3 * k), 3.2 * k, 2.2 * k)
    p.setBrush(qc(INK))
    for sx in (-1, 1):
        p.drawEllipse(QPointF(x + sx * 6 * k, y - 1.5 * k), 1.8 * k, 2.2 * k)
    p.setPen(QPen(qc(INK), 1.6 * k, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    p.setBrush(Qt.BrushStyle.NoBrush)
    m = QPainterPath()
    m.moveTo(x - 2.6 * k, y + 2.4 * k)
    m.quadTo(x, y + 6 * k, x + 2.6 * k, y + 2.4 * k)
    p.drawPath(m)


def _sticker(p, fill="#FFFFFF"):
    """둥근 스티커 바탕 (굵은 자두색 윤곽 + 하이라이트)."""
    p.setPen(_pen(2.8))
    p.setBrush(qc(fill))
    p.drawEllipse(QRectF(4, 4, S - 8, S - 8))


def icon_calendar(dpr=1.0):
    pm = _pm(dpr)
    p = _begin(pm)
    p.setPen(_pen())
    p.setBrush(QColor("white"))
    p.drawRoundedRect(QRectF(8, 12, 48, 44), 9, 9)
    top = QPainterPath()
    top.addRoundedRect(QRectF(8, 12, 48, 17), 9, 9)
    top.addRect(QRectF(8, 20, 48, 9))
    p.setBrush(qc(PINK))
    p.drawPath(top.simplified())
    p.setBrush(QColor("white"))
    for x in (20, 44):                                                # 달력 고리
        p.drawRoundedRect(QRectF(x - 3.2, 6, 6.4, 13), 3.2, 3.2)
    _face(p, 32, 40, 1.15)
    p.end()
    return pm


def icon_mail(dpr=1.0):
    pm = _pm(dpr)
    p = _begin(pm)
    p.setPen(_pen())
    p.setBrush(QColor("white"))
    p.drawRoundedRect(QRectF(7, 15, 50, 36), 8, 8)
    v = QPainterPath()
    v.moveTo(9, 20)
    v.lineTo(32, 38)
    v.lineTo(55, 20)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawPath(v)
    h = QPainterPath()                                                # 하트 도장
    x0, y0 = 32, 41
    h.moveTo(x0, y0 + 8)
    h.cubicTo(x0 - 14, y0 - 2, x0 - 5, y0 - 12, x0, y0 - 4)
    h.cubicTo(x0 + 5, y0 - 12, x0 + 14, y0 - 2, x0, y0 + 8)
    p.setBrush(qc(PINK))
    p.setPen(_pen(2.2))
    p.drawPath(h)
    p.end()
    return pm


def icon_google(dpr=1.0):
    pm = _pm(dpr)
    p = _begin(pm)
    _sticker(p)
    c = QPointF(32, 32)
    rect = QRectF(c.x() - 15, c.y() - 15, 30, 30)
    for col, a0, span in (("#EA4335", 45, 100), ("#FBBC05", 145, 85), ("#34A853", 230, 100), ("#4285F4", 330, 70)):
        pen = QPen(qc(col), 7.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.FlatCap)
        p.setPen(pen)
        p.drawArc(rect, int(a0 * 16), int(span * 16))
    p.setPen(QPen(qc("#4285F4"), 7.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.FlatCap))
    p.drawLine(QPointF(33, 32), QPointF(47, 32))                      # G 의 가로획
    p.end()
    return pm


def icon_youtube(dpr=1.0):
    pm = _pm(dpr)
    p = _begin(pm)
    p.setPen(_pen())
    p.setBrush(qc("#FF4E5E"))
    p.drawRoundedRect(QRectF(5, 14, 54, 38), 12, 12)
    p.setPen(_pen(2.2))
    p.setBrush(QColor("white"))
    tri = QPolygonF([QPointF(26, 24), QPointF(26, 42), QPointF(43, 33)])
    p.drawPolygon(tri)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(qc("#FFB3BD", 220))
    for x in (12, 52):
        p.drawEllipse(QPointF(x, 38), 3.4, 2.3)
    p.end()
    return pm


def icon_globe(dpr=1.0):
    pm = _pm(dpr)
    p = _begin(pm)
    p.setPen(_pen())
    p.setBrush(qc("#9ADBF5"))
    p.drawEllipse(QRectF(6, 6, 52, 52))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(qc("#8EDB9B"))
    for pts in (((14, 22), (24, 14), (30, 22), (24, 30), (16, 30)), ((38, 38), (50, 34), (52, 46), (44, 52), (36, 48))):
        p.drawPolygon(QPolygonF([QPointF(*q) for q in pts]))
    p.setPen(_pen())
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawEllipse(QRectF(6, 6, 52, 52))
    _face(p, 32, 30, 1.1)
    p.end()
    return pm


def icon_terminal(dpr=1.0):
    """명령 창(cmd·PowerShell): 고양이 귀가 달린 자두색 화면에 분홍 '>_'."""
    pm = _pm(dpr)
    p = _begin(pm)
    p.setPen(_pen())
    p.setBrush(qc(INK))
    for sx in (-1, 1):                                                # 귀
        ear = QPolygonF([QPointF(32 + sx * 22, 20), QPointF(32 + sx * 19, 6), QPointF(32 + sx * 9, 16)])
        p.drawPolygon(ear)
    p.drawRoundedRect(QRectF(6, 15, 52, 40), 12, 12)
    p.setPen(QPen(qc(PINK_L), 3.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    p.drawPolyline(QPolygonF([QPointF(17, 28), QPointF(26, 35), QPointF(17, 42)]))
    p.drawLine(QPointF(31, 44), QPointF(44, 44))
    p.end()
    return pm


def icon_tools(dpr=1.0):
    """제어판·설정: 톱니바퀴."""
    pm = _pm(dpr)
    p = _begin(pm)
    path = QPainterPath()
    cx = cy = 32
    teeth = 8
    for i in range(teeth * 2):
        ang = math.pi * 2 * i / (teeth * 2)
        r = 26 if i % 2 == 0 else 20
        a2 = ang + math.pi * 2 / (teeth * 4)
        for a_, r_ in ((ang, r), (a2, r)):
            pt = QPointF(cx + r_ * math.cos(a_), cy + r_ * math.sin(a_))
            if path.elementCount() == 0:
                path.moveTo(pt)
            else:
                path.lineTo(pt)
    path.closeSubpath()
    p.setPen(_pen())
    p.setBrush(qc("#FFD36B"))
    p.drawPath(path)
    p.setBrush(qc("#FFF2C9"))
    p.drawEllipse(QRectF(17, 17, 30, 30))
    _face(p, 32, 32, 0.95)
    p.end()
    return pm


def icon_chevron(dpr=1.0, right=True):
    pm = _pm(dpr)
    p = _begin(pm)
    p.setPen(_pen(2.6))
    p.setBrush(qc(PINK_L))
    p.drawEllipse(QRectF(8, 8, 48, 48))
    d = 1 if right else -1
    p.setPen(QPen(QColor("white"), 6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    p.drawPolyline(QPolygonF([QPointF(32 - 5 * d, 20), QPointF(32 + 5 * d, 32), QPointF(32 - 5 * d, 44)]))
    p.end()
    return pm


def sticker_for(pix: QPixmap, dpr=1.0, fill="#FFFFFF"):
    """웹사이트 파비콘·프로그램 아이콘을 귀여운 동그란 스티커 안에 넣는다."""
    pm = _pm(dpr)
    p = _begin(pm)
    _sticker(p, fill)
    if pix is not None and not pix.isNull():
        side = 42
        src = pix.scaled(int(side * dpr * 2), int(side * dpr * 2), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        w, h = src.width() / dpr / 2, src.height() / dpr / 2
        p.drawPixmap(QRectF(32 - w / 2, 32 - h / 2, w, h), src, QRectF(src.rect()))
    p.end()
    return pm


ICONS = {"calendar": icon_calendar, "mail": icon_mail, "google": icon_google, "youtube": icon_youtube, "globe": icon_globe,
         "terminal": icon_terminal, "tools": icon_tools}


class MenuHeader(QWidget):
    """우클릭 메뉴 맨 위: 고양이 얼굴 + 고양이가 하는 한마디 + 상태(배고픔·기분)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        from PyQt6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout
        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 8, 14, 6)
        lay.setSpacing(10)
        self.avatar = CatAvatar(46, "happy")
        lay.addWidget(self.avatar)
        col = QVBoxLayout()
        col.setSpacing(1)
        self.line1 = QLabel("")
        self.line1.setStyleSheet("font-weight: bold; color: %s; background: transparent;" % INK)
        self.line2 = QLabel("")
        self.line2.setStyleSheet("color: %s; font-size: 12px; background: transparent;" % SUB)
        col.addWidget(self.line1)
        col.addWidget(self.line2)
        lay.addLayout(col)
        self.setMinimumWidth(230)

    def set_text(self, line1, line2, mood="happy"):
        self.line1.setText(line1)
        self.line2.setText(line2)
        self.avatar.mood = mood


# ---------------------------------------------------------------- 이모티콘 지우기 (풍선 글에서)
import re as _re

_EMOJI = _re.compile("[\U0001F000-\U0001FAFF☀-➿⬀-⯿️‍]")


def app_icon_pixmap(size: int) -> QPixmap:
    """프로그램 대표 아이콘: 분홍 동그라미 안의 고양이 비서 얼굴 (설정 창 머리의 그 얼굴). 투명 바탕, 크기마다 새로 그려 작아도 또렷하다.
    작은 크기(<=32)는 얼굴이 뭉개지지 않게 원을 크게 그리고 흰 테두리를 뺀다 (귀 끝은 칸 위쪽 끝에 닿는다)."""
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    small = size <= 32
    r = size * (0.475 if small else 0.44)
    draw_cat_face(p, size / 2, size * (0.525 if small else 0.52), r, 0.0, "happy", ring=not small)
    p.end()
    return pm


def app_icon():
    """QIcon (16~256 여러 크기). 트레이·모든 창의 제목 표시줄·작업 표시줄에 쓴다."""
    from PyQt6.QtGui import QIcon
    ic = QIcon()
    for size in (16, 20, 24, 32, 48, 64, 128, 256):
        ic.addPixmap(app_icon_pixmap(size))
    return ic


def tab_icon(name: str, dpr: float = 2.0, size: int = 22) -> QPixmap:
    """설정 창 탭용 작은 아이콘 (얼굴 없이 단순하게: calendar / news / mail / clock / paw / shield). 분홍 + 자두색 윤곽, 투명 바탕."""
    pm = _pm(dpr, size)
    p = _begin(pm)
    p.setPen(_pen(3.4))
    p.setBrush(QColor("white"))
    if name == "calendar":
        p.drawRoundedRect(QRectF(7, 12, 50, 45), 10, 10)
        top = QPainterPath()
        top.addRoundedRect(QRectF(7, 12, 50, 19), 10, 10)
        top.addRect(QRectF(7, 22, 50, 9))
        p.setBrush(qc(PINK))
        p.drawPath(top.simplified())
        p.setBrush(QColor("white"))
        for x in (20, 44):
            p.drawRoundedRect(QRectF(x - 3.4, 4, 6.8, 14), 3.4, 3.4)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(qc(INK))
        for x in (20, 32, 44):
            p.drawEllipse(QPointF(x, 43), 3.2, 3.2)
    elif name == "news":
        p.drawRoundedRect(QRectF(7, 8, 50, 48), 9, 9)
        p.setBrush(qc(PINK))
        p.drawRoundedRect(QRectF(15, 16, 34, 12), 4, 4)
        p.setPen(_pen(3.6))
        for y in (38, 47):
            p.drawLine(QPointF(15, y), QPointF(49, y))
    elif name == "mail":
        p.drawRoundedRect(QRectF(5, 12, 54, 40), 9, 9)
        v = QPainterPath()
        v.moveTo(8, 18)
        v.lineTo(32, 36)
        v.lineTo(56, 18)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(v)
    elif name == "clock":
        p.drawEllipse(QRectF(5, 5, 54, 54))
        p.setBrush(qc(PINK, 235))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawPie(QRectF(10, 10, 44, 44), 90 * 16, -90 * 16)          # 지난 시간 (분홍 부채꼴)
        p.setPen(_pen(4.0))
        p.drawLine(QPointF(32, 32), QPointF(32, 15))
        p.drawLine(QPointF(32, 32), QPointF(44, 32))
    elif name == "paw":
        p.setBrush(qc(PINK))
        pad = QPainterPath()
        pad.moveTo(32, 30)
        pad.cubicTo(18, 30, 10, 44, 14, 52)
        pad.cubicTo(18, 60, 27, 54, 32, 54)
        pad.cubicTo(37, 54, 46, 60, 50, 52)
        pad.cubicTo(54, 44, 46, 30, 32, 30)
        p.drawPath(pad)
        for x, y, rx, ry in ((12, 27, 6.5, 8.5), (24, 14, 6.5, 9), (40, 14, 6.5, 9), (52, 27, 6.5, 8.5)):
            p.drawEllipse(QPointF(x, y), rx, ry)
    elif name == "shield":
        sh = QPainterPath()
        sh.moveTo(32, 5)
        sh.lineTo(55, 13)
        sh.lineTo(55, 30)
        sh.cubicTo(55, 45, 44, 55, 32, 60)
        sh.cubicTo(20, 55, 9, 45, 9, 30)
        sh.lineTo(9, 13)
        sh.closeSubpath()
        p.setBrush(qc(PINK))
        p.drawPath(sh)
        p.setPen(QPen(QColor("white"), 5.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPolyline([QPointF(21, 32), QPointF(29, 40), QPointF(44, 22)])
    p.end()
    return pm


def strip_emoji(text: str) -> str:
    """글에서 이모티콘(그림 문자)만 지운다. '→' 같은 글 기호와 한글은 그대로 둔다. 남은 공백은 정리한다."""
    out = _EMOJI.sub("", text)
    out = _re.sub(r"[ \t]{2,}", " ", out)
    out = _re.sub(r"\(\s+", "(", out)
    out = _re.sub(r"\s+\)", ")", out)
    return out.strip()


# ---------------------------------------------------------------- 쥐 (경비 고양이가 잡는 '악성코드')
def draw_mouse(p: QPainter, x: float, y: float, direction: int = 1, t: float = 0.0, caught: bool = False, alpha: float = 1.0, size: float = 1.0):
    """발바닥 y 에 서 있는 귀여운 쥐(길이 약 30px). direction=1 이면 오른쪽을 본다. caught=True 면 납작해지며 별이 튄다."""
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    p.setOpacity(max(0.0, min(1.0, alpha)))
    p.translate(x, y)
    p.scale(direction * size, size)
    ink = QPen(qc(INK), 1.7, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    if caught:
        p.scale(1.1, 0.55)                                                   # 납작
    else:
        p.translate(0, -abs(math.sin(t * 15)) * 1.8)                         # 달리며 통통
    # 꼬리 (살랑)
    tail = QPainterPath()
    w = math.sin(t * 12) * 3.0
    tail.moveTo(-11, -7)
    tail.cubicTo(-20, -4 + w, -22, -16 - w, -31, -13 + w)
    p.setPen(QPen(qc(INK), 1.7, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawPath(tail)
    p.setPen(ink)
    # 다리
    leg = math.sin(t * 15) * 3.0
    p.setBrush(qc("#CFC6D1"))
    for dx, ph in ((-5, 0.0), (5, math.pi)):
        p.drawEllipse(QPointF(dx + math.sin(t * 15 + ph) * leg * 0.4, -1.5), 2.6, 1.8)
    # 몸통
    p.setBrush(qc("#E4DCE6"))
    p.drawEllipse(QPointF(0, -8.5), 13, 8)
    # 귀
    for ex, ey in ((3.5, -15.5), (9.5, -14.5)):
        p.setBrush(qc("#E4DCE6"))
        p.drawEllipse(QPointF(ex, ey), 4.6, 4.6)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(qc(PINK_L))
        p.drawEllipse(QPointF(ex, ey), 2.6, 2.6)
        p.setPen(ink)
    # 머리·주둥이
    p.setBrush(qc("#EFE8F0"))
    p.drawEllipse(QPointF(11, -8), 7.2, 6.4)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(qc(PINK_D))
    p.drawEllipse(QPointF(17.6, -7.2), 1.9, 1.5)                             # 코
    p.setBrush(qc(INK))
    p.drawEllipse(QPointF(12.8, -9.8), 1.5, 1.7)                             # 눈
    p.setBrush(qc(PINK_L, 200))
    p.drawEllipse(QPointF(9.5, -6.2), 2.2, 1.4)                              # 볼터치
    p.restore()
    if caught:                                                               # 잡혔을 때 튀는 별
        p.save()
        p.setOpacity(max(0.0, min(1.0, alpha)))
        p.translate(x, y - 10)
        for i in range(4):
            a = i * math.pi / 2 + t * 4
            r = 10 + min(t, 1.0) * 10
            sx, sy = math.cos(a) * r, math.sin(a) * r * 0.7
            star = QPainterPath()
            for k in range(8):
                rr = 4.2 if k % 2 == 0 else 1.4
                aa = k * math.pi / 4
                pt = QPointF(sx + math.cos(aa) * rr, sy + math.sin(aa) * rr)
                star.moveTo(pt) if k == 0 else star.lineTo(pt)
            star.closeSubpath()
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(qc("#FFD36B" if i % 2 else PINK_L))
            p.drawPath(star)
        p.restore()
