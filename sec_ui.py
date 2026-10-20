"""경비 경보 화면: 경보 상세 창.

 · 위쪽에 놀란(말하는) 고양이 얼굴 + 경보 제목 + 시각
 · 본문: 무슨 일이 있었는지 → 그 아래 ‘지금 해야 할 일’을 번호·그림·화살표로 순서대로 그린 카드
 · 의심 프로그램 후보 목록: 줄마다 [위치 열기] [종료…] 버튼 (종료는 시스템 중요 프로세스·윈도우 폴더 프로그램에는 안 보이고, 누르면 확인 창을 거친다)
 · 아래쪽: [확인했어요] [무시] — 경고 단계의 건에는 [허용 목록에 추가]
고양이는 자동으로 지우거나 끝내지 않는다. 여기서 사용자가 누르는 것만 실행된다.
"""
import datetime as dt
import subprocess

import cute
import sec_common
from PyQt6.QtCore import QPointF, QRectF, QTimer, Qt
from PyQt6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QMessageBox, QPlainTextEdit, QPushButton, QSizePolicy, QVBoxLayout, QWidget)

LEVEL_TEXT = {"danger": "위험", "warn": "의심", "info": "참고"}


# 경보 종류별 '지금 해야 할 일' (순서대로 그림으로 보여 준다): (제목, 설명, 그림)
RANSOM_STEPS = [
    ("인터넷을 바로 끊어요", "와이파이를 끄거나 랜선을 뽑아요", "wifi"),
    ("의심 프로그램을 끝내요", "안 되면 컴퓨터를 종료해요 (켜 둘수록 더 많이 암호화돼요)", "power"),
    ("몸값은 내지 마요", "백신(알약)과 전문가에게 알려요", "shield"),
    ("백업 장치는 연결하지 마요", "외장 디스크·클라우드도 암호화될 수 있어요", "disk"),
]
PROGRAM_STEPS = [
    ("어떤 프로그램인지 확인해요", "‘위치 열기’로 파일이 있는 곳을 봐요", "folder"),
    ("내가 아는 프로그램이면 허용해요", "‘허용 목록에 추가’를 누르면 다음부터 알리지 않아요", "check"),
    ("모르는 프로그램이면 검사해요", "백신(알약)으로 검사하고, 계속 수상하면 끝내요", "shield"),
]
PRIVACY_STEPS = [
    ("지금 내가 쓰는 앱인지 봐요", "화상회의·녹음 같은 앱을 켜 두었나요?", "eye"),
    ("내가 쓰는 앱이면 허용해요", "‘허용 목록에 추가’를 누르면 다음부터 알리지 않아요", "check"),
    ("모르는 앱이면 끝내고 검사해요", "백신(알약)으로 검사해요", "shield"),
]
DOWNLOAD_STEPS = [
    ("실행하지 말고 출처를 떠올려요", "어디에서 받은 파일인지 확인해요", "folder"),
    ("백신으로 검사해요", "알약 등으로 한 번 더 확인해요", "shield"),
    ("필요 없으면 직접 지워요", "고양이는 파일을 지우지 않아요", "trash"),
]


def steps_for(ev):
    """사건 한 건에 맞는 '지금 해야 할 일' 목록 (참고 단계·시스템 알림은 없음)."""
    if ev.get("level") == "info" or ev.get("kind") == "system":
        return []
    return {"ransom": RANSOM_STEPS, "privacy": PRIVACY_STEPS, "download": DOWNLOAD_STEPS}.get(ev.get("kind"), PROGRAM_STEPS)


def _pen(color, width):
    pen = QPen(QColor(color), width)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    return pen


def _draw_icon(p, kind, cx, cy):
    """단계 옆의 작은 그림 (선으로 그린 단순한 아이콘)."""
    p.setPen(_pen(cute.INK, 2.0))
    p.setBrush(Qt.BrushStyle.NoBrush)
    if kind == "wifi":
        for r in (6, 11, 16):
            p.drawArc(QRectF(cx - r, cy + 7 - r, 2 * r, 2 * r), 45 * 16, 90 * 16)
        p.setBrush(QColor(cute.INK))
        p.drawEllipse(QPointF(cx, cy + 7), 1.6, 1.6)
        p.setPen(_pen(cute.WARN, 2.8))
        p.drawLine(QPointF(cx - 12, cy - 11), QPointF(cx + 12, cy + 12))
    elif kind == "power":
        p.drawArc(QRectF(cx - 9, cy - 8, 18, 18), 120 * 16, 300 * 16)
        p.drawLine(QPointF(cx, cy - 12), QPointF(cx, cy - 1))
    elif kind == "shield":
        path = QPainterPath()
        path.moveTo(cx, cy - 12)
        path.lineTo(cx + 10, cy - 8)
        path.lineTo(cx + 10, cy + 1)
        path.quadTo(cx + 10, cy + 9, cx, cy + 13)
        path.quadTo(cx - 10, cy + 9, cx - 10, cy + 1)
        path.lineTo(cx - 10, cy - 8)
        path.closeSubpath()
        p.drawPath(path)
        p.drawPolyline([QPointF(cx - 4, cy + 1), QPointF(cx - 1, cy + 4), QPointF(cx + 5, cy - 3)])
    elif kind == "disk":
        p.drawRoundedRect(QRectF(cx - 11, cy - 6, 22, 12), 3, 3)
        p.setBrush(QColor(cute.INK))
        p.drawEllipse(QPointF(cx + 6, cy), 1.4, 1.4)
        p.setPen(_pen(cute.WARN, 2.8))
        p.drawLine(QPointF(cx - 12, cy - 11), QPointF(cx + 12, cy + 12))
    elif kind == "folder":
        p.drawPolyline([QPointF(cx - 11, cy - 5), QPointF(cx - 7, cy - 9), QPointF(cx - 2, cy - 9), QPointF(cx, cy - 5)])
        p.drawRoundedRect(QRectF(cx - 11, cy - 5, 22, 15), 3, 3)
    elif kind == "check":
        p.setPen(_pen(cute.OK, 3.2))
        p.drawPolyline([QPointF(cx - 9, cy), QPointF(cx - 2, cy + 7), QPointF(cx + 9, cy - 7)])
    elif kind == "eye":
        p.drawEllipse(QRectF(cx - 12, cy - 7, 24, 14))
        p.setBrush(QColor(cute.INK))
        p.drawEllipse(QPointF(cx, cy), 3.2, 3.2)
    elif kind == "trash":
        p.drawRoundedRect(QRectF(cx - 7, cy - 4, 14, 14), 2, 2)
        p.drawLine(QPointF(cx - 10, cy - 6), QPointF(cx + 10, cy - 6))
        p.drawPolyline([QPointF(cx - 3, cy - 6), QPointF(cx - 3, cy - 9), QPointF(cx + 3, cy - 9), QPointF(cx + 3, cy - 6)])


class StepFlow(QWidget):
    """‘지금 해야 할 일’을 순서대로 그린 카드: 번호 동그라미 → 그림 → 제목·설명, 번호 사이는 아래로 향한 화살표."""
    HEAD, ROW = 38, 66

    def __init__(self):
        super().__init__()
        self.steps = []
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_steps(self, steps):
        self.steps = list(steps)
        self.setVisible(bool(self.steps))
        self.setFixedHeight(self.HEAD + self.ROW * len(self.steps) + 8 if self.steps else 0)
        self.update()

    def _font(self, px, bold=False):
        f = QFont(self.font())
        f.setPixelSize(px)
        f.setBold(bold)
        return f

    def paintEvent(self, e):
        if not self.steps:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QPen(QColor(cute.LINE), 2))
        p.setBrush(QColor(cute.CARD))
        p.drawRoundedRect(QRectF(1, 1, self.width() - 2, self.height() - 2), 14, 14)
        p.setFont(self._font(15, True))
        p.setPen(QColor(cute.WARN))
        p.drawText(QRectF(18, 8, self.width() - 36, 24), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, "지금 해야 할 일 (순서대로)")
        n = len(self.steps)
        for i, (title, desc, icon) in enumerate(self.steps):
            cy = self.HEAD + self.ROW * i + self.ROW / 2
            bx = 34
            if i < n - 1:                                       # 다음 번호로 이어지는 화살표
                p.setPen(_pen(cute.PINK_L, 3))
                y0, y1 = cy + 17, cy + self.ROW - 20
                p.drawLine(QPointF(bx, y0), QPointF(bx, y1))
                p.drawPolyline([QPointF(bx - 5, y1 - 5), QPointF(bx, y1 + 1), QPointF(bx + 5, y1 - 5)])
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(cute.PINK_D))
            p.drawEllipse(QPointF(bx, cy), 15, 15)
            p.setFont(self._font(16, True))
            p.setPen(QColor("white"))
            p.drawText(QRectF(bx - 15, cy - 15, 30, 30), Qt.AlignmentFlag.AlignCenter, str(i + 1))
            p.setPen(QPen(QColor(cute.LINE), 2))
            p.setBrush(QColor(cute.BG))
            p.drawEllipse(QPointF(82, cy), 21, 21)
            _draw_icon(p, icon, 82, cy)
            p.setFont(self._font(15, True))
            p.setPen(QColor(cute.INK))
            p.drawText(QRectF(116, cy - 24, self.width() - 130, 24), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, title)
            p.setFont(self._font(12))
            p.setPen(QColor(cute.SUB))
            p.drawText(QRectF(116, cy, self.width() - 130, 34), Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft | Qt.TextFlag.TextWordWrap, desc)
        p.end()


class AlertWindow(QWidget):
    def __init__(self, events, on_allow=None):
        """events: SecEvents.  on_allow(사건): '허용 목록에 추가'를 눌렀을 때 부른다 (종류별 허용 처리는 호출한 쪽이 한다)."""
        super().__init__()
        self.events, self.on_allow = events, on_allow
        self.ev = None
        self.setObjectName("page")
        self.setWindowTitle("경비 고양이 경보")
        self.resize(560, 780)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 16, 18, 14)
        lay.setSpacing(10)
        head = QHBoxLayout()
        self.avatar = cute.CatAvatar(58, "talk")
        head.addWidget(self.avatar)
        head.addSpacing(10)
        col = QVBoxLayout()
        self.title = QLabel("")
        self.title.setWordWrap(True)
        self.title.setStyleSheet("font-size: 19px; font-weight: bold; color: %s;" % cute.WARN)
        self.when = QLabel("")
        self.when.setObjectName("help")
        col.addWidget(self.title)
        col.addWidget(self.when)
        head.addLayout(col, 1)
        lay.addLayout(head)
        self.body = QPlainTextEdit()
        self.body.setReadOnly(True)
        lay.addWidget(self.body, 1)
        self.steps = StepFlow()
        lay.addWidget(self.steps)
        self.sus_box = QFrame()
        self.sus_lay = QVBoxLayout(self.sus_box)
        self.sus_lay.setContentsMargins(0, 0, 0, 0)
        self.sus_lay.setSpacing(6)
        lay.addWidget(self.sus_box)
        self.msg = QLabel("")
        self.msg.setObjectName("help")
        self.msg.setWordWrap(True)
        lay.addWidget(self.msg)
        row = QHBoxLayout()
        row.addStretch(1)
        self.btn_allow = QPushButton("허용 목록에 추가")
        self.btn_allow.clicked.connect(self._allow)
        self.btn_ignore = QPushButton("무시")
        self.btn_ignore.clicked.connect(lambda: self._mark("ignored"))
        self.btn_seen = QPushButton("확인했어요")
        self.btn_seen.setDefault(True)
        self.btn_seen.clicked.connect(lambda: self._mark("seen"))
        for b in (self.btn_allow, self.btn_ignore, self.btn_seen):
            row.addWidget(b)
        lay.addLayout(row)
        self._timer = QTimer(self)                        # 의심 프로그램 후보는 경보보다 조금 늦게 알게 되므로 열려 있는 동안 다시 읽는다
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self.refresh)

    # --- 보이기 ----------------------------------------------------------
    def show_event(self, ev, activate=True):
        self.ev = ev
        self.msg.setText("")
        self.refresh(force=True)
        self.show()
        self.raise_()
        if activate:
            self.activateWindow()
        self._timer.start()

    def hideEvent(self, e):
        self._timer.stop()
        super().hideEvent(e)

    def refresh(self, force=False):
        if self.ev is None:
            return
        cur = self.events.get(self.ev["id"]) or self.ev
        sig = (cur["text"], len(cur["data"].get("suspects", [])), cur["status"])
        if not force and sig == getattr(self, "_sig", None):
            return
        self._sig = sig
        self.ev = cur
        color = {"danger": cute.WARN, "warn": cute.PINK_D}.get(cur["level"], cute.INK)
        self.title.setStyleSheet("font-size: 19px; font-weight: bold; color: %s;" % color)
        self.title.setText("[%s] %s" % (LEVEL_TEXT.get(cur["level"], ""), cur["title"]))
        self.when.setText(dt.datetime.fromtimestamp(cur["ts"]).strftime("%Y-%m-%d %H:%M:%S") + ("  ·  시험 경보" if cur["data"].get("test") else ""))
        self.avatar.mood = "talk" if cur["level"] == "danger" else "normal"
        self.body.setPlainText(cur["text"].split("\n\n지금 해야 할 일:")[0])         # 해야 할 일은 아래 그림 카드로 따로 보여 준다
        self.steps.set_steps(steps_for(cur))
        while self.sus_lay.count():
            w = self.sus_lay.takeAt(0).widget()
            if w:
                w.deleteLater()
        for s in cur["data"].get("suspects", []):
            self.sus_lay.addWidget(self._suspect_row(s))
        self.btn_allow.setVisible(cur["kind"] != "ransom" and not cur["data"].get("test"))

    def _suspect_row(self, s):
        row = QFrame()
        row.setStyleSheet("QFrame { background: white; border: 2px solid %s; border-radius: 12px; }" % cute.LINE)
        lay = QHBoxLayout(row)
        lay.setContentsMargins(10, 6, 10, 6)
        speed = ("  (%s MB/초)" % s["mb_s"]) if s.get("mb_s") not in (None, "") else ""
        lab = QLabel("%s%s\n%s" % (s.get("name", "?"), speed, s.get("path", "")))
        lab.setWordWrap(True)
        lab.setStyleSheet("border: none; background: transparent;")
        lay.addWidget(lab, 1)
        if s.get("path"):
            b = QPushButton("위치 열기")
            b.clicked.connect(lambda _=False, p=s["path"]: self._open_location(p))
            lay.addWidget(b)
        if s.get("pid") and sec_common.can_terminate(s.get("name", ""), s.get("path", "")):
            k = QPushButton("종료…")
            k.clicked.connect(lambda _=False, x=s: self._terminate(x))
            lay.addWidget(k)
        return row

    # --- 사용자가 누른 것만 실행 ------------------------------------------
    @staticmethod
    def _open_location(path):
        try:
            subprocess.Popen(["explorer", "/select,", str(path)])
        except OSError:
            pass

    def _terminate(self, s):
        ans = QMessageBox.question(self, "프로그램 종료", "‘%s’ 프로그램을 끝낼까요?\n저장하지 않은 작업이 사라질 수 있어요.\n\n%s" % (s.get("name"), s.get("path", "")))
        if ans == QMessageBox.StandardButton.Yes:
            ok = sec_common.terminate(int(s["pid"]))
            self.msg.setText("끝냈어요." if ok else "끝내지 못했어요 (권한이 없거나 이미 끝났어요).")

    def _mark(self, status):
        if self.ev:
            self.events.set_status(self.ev["id"], status)
        self.close()

    def _allow(self):
        if self.ev:
            if self.on_allow:
                self.on_allow(self.ev)
            self.events.set_status(self.ev["id"], "allowed")
        self.close()
