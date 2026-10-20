"""설정 창 (우클릭 메뉴 → ⚙ 설정…).

탭 하나가 기능 하나다.
 · '캘린더' 탭: 구글 캘린더 비공개 주소(iCal), 알림 켜기, 알림 시각, 지금 시험.
 · '소식' 탭: Gemini 키, 모델, 지역, 시세 항목, 프롬프트(물어볼 내용), 알림 켜기·시각, 연결 시험, 지금 시험.
캘린더 주소와 Gemini 키는 남이 알면 안 되는 비밀 값이라 화면에 가리고(보이기 체크 시에만 보임), 윈도우 계정으로 암호화해서 저장한다.
다른 기능(어제 한 일) 탭은 같은 방식으로 이 창에 더한다. 모양은 theme.py 의 공통 스타일을 따른다.
"""
import re

import calendar_ics
import cute
import gemini_client
import news_sources
from PyQt6.QtCore import QTimer, QUrl, Qt, QTime
from PyQt6.QtCore import QPointF, QSize
from PyQt6.QtGui import QColor, QDesktopServices, QIcon, QPainter, QPen
from PyQt6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFrame, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QListWidget,
                             QListWidgetItem, QMessageBox, QPlainTextEdit, QPushButton, QScrollArea, QSpinBox, QTabWidget, QTimeEdit, QVBoxLayout, QWidget)

CAL_WARN = "이 주소는 비밀이다냥. 남에게 알리지 말아 달라옹."
NEWS_WARN = "프롬프트와 자료가 Gemini로 전송된다냥 (무료 한도 있음)."
ACT_EXCL_HELP = "이 단어가 든 창은 ‘제외됨’으로만 기록한다냥."
ACT_CONSENT = ("기록을 켜기 전에 꼭 확인해 달라냥.\n\n"
               "• 프로그램 이름과 창 제목(문서 이름, 웹페이지 제목 등)을 5초마다 이 컴퓨터에 저장한다옹. 키보드로 친 내용은 저장하지 않는다냥.\n"
               "• ‘AI 요약’을 만들 때 이 기록이 구글 Gemini로 전송된다냥. 무료 등급에서는 구글이 서비스 개선에 쓸 수 있다고 안내돼 있다옹.\n"
               "• 시크릿 창·암호 관리자·은행 관련 창은 제외하고, 설정에서 제외할 단어를 더할 수 있다냥.\n\n"
               "기록을 켤까냥?")
MAIL_WARN = "앱 비밀번호는 비밀이다냥 (암호화해 저장한다옹)."
MAIL_OK = "저장된 앱 비밀번호가 있다냥"
GUARD_HELP = "백신을 대신하지 않고, 수상한 행동을 알려 주기만 한다냥."
URLS = {
    "calendar": "https://calendar.google.com/calendar/u/0/r/settings",
    "twosv": "https://myaccount.google.com/signinoptions/twosv",
    "apppw": "https://myaccount.google.com/apppasswords",
    "aistudio": "https://aistudio.google.com/apikey",
    "vt": "https://www.virustotal.com",
    "vt_key": "https://www.virustotal.com/gui/my-apikey",
}
KEY_OK = "저장된 키가 있다냥"
URL_OK = "저장된 주소가 있다냥"


def _label(text, name="", wrap=True):
    lab = QLabel(text)
    lab.setWordWrap(wrap)
    if name:
        lab.setObjectName(name)
    return lab


def _url_button(text, url):
    """눌러서 인터넷 주소를 여는 링크: 파란 밑줄 글씨 (버튼 모양이 아님). 마우스를 올리면 전체 주소."""
    b = QPushButton(text + " ↗")
    b.setObjectName("url")
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    b.setToolTip(url)
    b.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(url)))
    return b


class StatusLabel(QLabel):
    """상태 한 줄: 앞에 작은 아이콘(확인됨=초록 동그라미 체크, 아직=빈 동그라미). 이모지 대신 직접 그린다."""

    def __init__(self, text="", ok=False):
        super().__init__(text)
        self.setWordWrap(True)
        self.setContentsMargins(22, 0, 0, 0)
        self.setObjectName("ok" if ok else "help")

    def setObjectName(self, name):
        super().setObjectName(name)
        self.update()

    def paintEvent(self, e):
        super().paintEvent(e)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        cy = self.fontMetrics().height() / 2.0 + 1
        if self.objectName() == "ok":
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor("#3FA373"))
            p.drawEllipse(QPointF(8, cy), 8, 8)
            pen = QPen(QColor("white"), 2.0)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            p.setPen(pen)
            p.drawPolyline([QPointF(4.2, cy + 0.2), QPointF(7.0, cy + 3.0), QPointF(11.8, cy - 3.0)])
        else:
            p.setPen(QPen(QColor(cute.LINE), 1.8))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QPointF(8, cy), 7.2, 7.2)
        p.end()


def _status(text, ok):
    return StatusLabel(text, ok)


class FoldCard(QFrame):
    """접고 펼치는 안내 카드: 머리글(▸/▾ 제목)을 누르면 안쪽(번호 붙은 할 일 · 주소 링크 · '항목: 내용' 줄)이 열리고 닫힌다."""

    def __init__(self, title, steps=(), links=(), facts=(), open=False):
        super().__init__()
        self.setObjectName("card")
        self.title = title
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 6, 12, 8)
        lay.setSpacing(4)
        self.head = QPushButton()
        self.head.setObjectName("fold")
        self.head.setCursor(Qt.CursorShape.PointingHandCursor)
        self.head.setToolTip("눌러서 펼치기 / 접기")
        self.head.clicked.connect(lambda: self.set_open(not self.body.isVisible()))
        lay.addWidget(self.head)
        self.body = QWidget()
        b = QVBoxLayout(self.body)
        b.setContentsMargins(0, 2, 0, 0)
        b.setSpacing(6)
        for n, text in enumerate(steps, 1):
            row = QHBoxLayout()
            row.setSpacing(8)
            num = QLabel(str(n))
            num.setObjectName("stepnum")
            num.setFixedSize(18, 18)
            num.setAlignment(Qt.AlignmentFlag.AlignCenter)
            row.addWidget(num, 0, Qt.AlignmentFlag.AlignTop)
            row.addWidget(_label(text), 1)
            b.addLayout(row)
        for text, url in links:
            b.addWidget(_url_button(text, url), 0, Qt.AlignmentFlag.AlignLeft)
        for key, text in facts:
            row = QHBoxLayout()
            row.setSpacing(8)
            k = _label(key, "factkey", wrap=False)
            k.setFixedWidth(74)
            row.addWidget(k, 0, Qt.AlignmentFlag.AlignTop)
            row.addWidget(_label(text, "facts"), 1)
            b.addLayout(row)
        lay.addWidget(self.body)
        self.set_open(open)

    def set_open(self, on):
        self.body.setVisible(bool(on))
        self.head.setText(("▾  " if on else "▸  ") + self.title)


def _card(title, steps=(), links=(), facts=(), open=False):
    return FoldCard(title, steps, links, facts, open)


def _restyle(lab, name):
    """글자 상태 줄의 종류(ok/help)를 바꾸고 스타일을 다시 입힌다."""
    lab.setObjectName(name)
    lab.style().unpolish(lab)
    lab.style().polish(lab)


def _group(title):
    g = QGroupBox(title)
    lay = QVBoxLayout(g)
    lay.setSpacing(8)
    return g, lay


def _link_button(text, slot):
    """작은 보조 버튼 (지우기·되돌리기 같은 것): 테두리가 있는 작은 알약 모양. 인터넷 주소 링크(_url_button)와 모양이 다르다."""
    b = QPushButton(text)
    b.setObjectName("ghost")
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    b.clicked.connect(slot)
    return b


def _page():
    """스크롤되는 탭 한 장: (탭에 넣을 위젯, 내용을 넣을 세로 배치)."""
    inner = QWidget()
    inner.setObjectName("page")
    lay = QVBoxLayout(inner)
    lay.setContentsMargins(4, 4, 10, 4)
    lay.setSpacing(6)
    sc = QScrollArea()
    sc.setWidgetResizable(True)
    sc.setFrameShape(QScrollArea.Shape.NoFrame)
    sc.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)       # 가로 스크롤은 쓰지 않는다 (세로로만 내려 본다)
    sc.setWidget(inner)
    return sc, lay


def _secret_row(placeholder):
    """가려 쓰는 입력 칸 + '보이기' 체크."""
    row = QHBoxLayout()
    edit = QLineEdit()
    edit.setEchoMode(QLineEdit.EchoMode.Password)
    edit.setPlaceholderText(placeholder)
    row.addWidget(edit, 1)
    show = QCheckBox("보이기")
    show.toggled.connect(lambda on: edit.setEchoMode(QLineEdit.EchoMode.Normal if on else QLineEdit.EchoMode.Password))
    row.addWidget(show)
    return edit, row


class TimesEditor(QGroupBox):
    """알림 시각 목록 + 추가/삭제 (캘린더·소식·어제 한 일 탭이 같이 쓴다)."""

    def __init__(self, times, default=QTime(9, 0), title="알림 시각 (하루에 여러 번 가능)"):
        super().__init__(title)
        lay = QVBoxLayout(self)
        lay.setSpacing(8)
        self.list = QListWidget()
        self.list.setMaximumHeight(84)
        for t in times:
            self.list.addItem(t)
        lay.addWidget(self.list)
        row = QHBoxLayout()
        self.edit = QTimeEdit(default)
        self.edit.setDisplayFormat("HH:mm")
        row.addWidget(self.edit)
        add = QPushButton("＋ 추가")
        add.clicked.connect(self.add)
        rem = QPushButton("선택 삭제")
        rem.clicked.connect(self.remove)
        row.addWidget(add)
        row.addWidget(rem)
        row.addStretch(1)
        lay.addLayout(row)

    def add(self):
        t = self.edit.time().toString("HH:mm")
        items = self.get()
        if t not in items:
            items.append(t)
            self.list.clear()
            for x in sorted(items):
                self.list.addItem(x)

    def remove(self):
        for it in self.list.selectedItems():
            self.list.takeItem(self.list.row(it))

    def get(self):
        return [self.list.item(i).text() for i in range(self.list.count())]


class SettingsDialog(QDialog):
    def __init__(self, parent, settings, run_test, on_saved, activity=None, show_raw=None, guard=None, show_alert=None):
        """run_test(이름, 인자=None): 지금 시험 실행 ('어제 한 일'은 인자로 날짜 'YYYY-MM-DD').
        on_saved(): 저장 뒤에 부른다(스케줄러가 지난 시각을 '한 것'으로 표시).
        activity: 활동 기록기(ActivityLog, 없으면 '어제 한 일' 탭을 안 보임).  show_raw(날짜): 기록을 AI 없이 그대로 보여 주는 함수."""
        super().__init__(parent)
        self.settings, self.run_test, self.on_saved = settings, run_test, on_saved
        self.activity, self.show_raw = activity, show_raw
        self.guard, self.show_alert = guard, show_alert           # 경비 고양이 본부(SecurityGuard)와 경보 상세 창을 여는 함수
        self.setWindowTitle("고양이 설정 🐾")
        self.resize(620, 660)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(10)
        head = QHBoxLayout()
        head.addWidget(cute.CatAvatar(48, "happy"))
        head.addSpacing(8)
        head.addWidget(_label("고양이 비서 설정", "title"))
        head.addStretch(1)
        lay.addLayout(head)
        self.tabs = QTabWidget()
        lay.addWidget(self.tabs, 1)
        self.tabs.addTab(self._calendar_tab(), "📅 캘린더")
        self.tabs.addTab(self._news_tab(), "📰 소식")
        self.tabs.addTab(self._mail_tab(), "📧 메일")
        if activity is not None:
            self.tabs.addTab(self._activity_tab(), "🕘 어제 한 일")
            self.tabs.currentChanged.connect(lambda _i: self._refresh_days())
        self.tabs.addTab(self._care_tab(), "🐾 생활")
        if guard is not None:
            self.tabs.addTab(self._guard_tab(), "🛡 경비")
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Close)
        btns.button(QDialogButtonBox.StandardButton.Save).setText("저장")
        btns.button(QDialogButtonBox.StandardButton.Close).setText("닫기")
        btns.accepted.connect(self._save)
        btns.rejected.connect(self.reject)
        foot = QHBoxLayout()
        self.save_msg = QLabel("")                                   # 저장해도 창은 닫지 않는다 (다른 탭을 계속 볼 수 있게). 닫기는 닫기 버튼으로
        self.save_msg.setObjectName("help")
        self._save_timer = QTimer(self)                              # 안내 문구는 잠깐만 보인다 (창이 닫히면 타이머도 같이 사라진다)
        self._save_timer.setSingleShot(True)
        self._save_timer.timeout.connect(lambda: self.save_msg.setText(""))
        foot.addWidget(self.save_msg, 1)
        foot.addWidget(btns)
        lay.addLayout(foot)
        self._strip_emojis()

    def _strip_emojis(self):
        """버튼·그룹 제목·탭 이름·창 제목에서 이모지를 뺀다 (이모지가 섞이면 화면이 어수선해 보인다)."""
        for w in self.findChildren(QPushButton):
            w.setText(cute.strip_emoji(w.text()).strip())
        for g in self.findChildren(QGroupBox):
            g.setTitle(cute.strip_emoji(g.title()).strip())
        names = {"캘린더": "calendar", "소식": "news", "메일": "mail", "어제 한 일": "clock", "생활": "paw", "경비": "shield"}
        self.tabs.setIconSize(QSize(20, 20))
        for i in range(self.tabs.count()):
            t = cute.strip_emoji(self.tabs.tabText(i)).strip()
            self.tabs.setTabText(i, t)
            if t in names:                                       # 이모지 대신 탭마다 알맞은 그림 (달력·신문·편지·시계·발바닥·방패)
                self.tabs.setTabIcon(i, QIcon(cute.tab_icon(names[t])))
        self.setWindowTitle(cute.strip_emoji(self.windowTitle()).strip())

    # ------------------------------------------------------------ 캘린더 탭
    def _calendar_tab(self):
        page, lay = _page()
        sch = self.settings.data["schedules"]["calendar"]
        self.cal_on = QCheckBox("정해 둔 시각에 오늘 일정을 알려 주기")
        self.cal_on.setChecked(bool(sch.get("enabled")))
        lay.addWidget(self.cal_on)

        g, gl = _group("구글 캘린더 연결")
        gl.addWidget(_card("연결 방법", steps=["구글 캘린더 → 설정 → ‘내 캘린더의 설정’", "‘캘린더 통합’에서 <b>iCal 형식의 비공개 주소</b> 복사", "아래 칸에 붙여 넣기"],
                           links=[("calendar.google.com 설정 열기", URLS["calendar"])], open=not self.settings.get_secret("calendar_url")))
        self.has_url = bool(self.settings.get_secret("calendar_url"))
        self.url_state = _status(URL_OK if self.has_url else "아직 주소가 없다냥", self.has_url)
        gl.addWidget(self.url_state)
        self.url, row = _secret_row("https://calendar.google.com/calendar/ical/…/basic.ics")
        gl.addLayout(row)
        gl.addWidget(_label(CAL_WARN, "warn"))
        gl.addWidget(_link_button("저장된 주소 지우기", self._clear_url), 0, Qt.AlignmentFlag.AlignLeft)
        lay.addWidget(g)

        self.times_ed = TimesEditor(sch.get("times", []))
        self.times, self.time_edit = self.times_ed.list, self.times_ed.edit        # (시험 코드가 쓰는 이름 유지)
        lay.addWidget(self.times_ed)

        test = QPushButton("🐾 지금 시험해 보기")
        test.clicked.connect(self._test)
        lay.addWidget(test)

        ho = self.settings.data["hourly_opts"]
        g2, g2l = _group("⏰ 매시 정각 알림")
        self.hourly_cal = QCheckBox("매시 정각마다 앞으로 몇 시간 안의 일정을 알려 주기")
        self.hourly_cal.setChecked(bool(ho.get("calendar")))
        g2l.addWidget(self.hourly_cal)
        hrow = QHBoxLayout()
        self.hourly_hours = QSpinBox()
        self.hourly_hours.setRange(1, 8)
        self.hourly_hours.setValue(int(ho.get("hours", 2) or 2))
        self.hourly_hours.setPrefix("앞으로 ")
        self.hourly_hours.setSuffix(" 시간")
        hrow.addWidget(self.hourly_hours)
        hrow.addStretch(1)
        g2l.addLayout(hrow)
        g2l.addWidget(_label("예: 8시 정각 → 8~10시 일정을 알려 준다냥.", "help"))
        t2 = QPushButton("🐾 지금 앞으로 일정 확인해 보기")
        t2.clicked.connect(self._test_hourly_cal)
        g2l.addWidget(t2)
        lay.addWidget(g2)
        lay.addStretch(1)
        return page

    # ------------------------------------------------------------ 메일 탭 (Gmail)
    def _mail_tab(self):
        page, lay = _page()
        ho = self.settings.data["hourly_opts"]
        self.hourly_mail = QCheckBox("매시 정각마다 새 메일 알려 주기")
        self.hourly_mail.setChecked(bool(ho.get("mail")))
        lay.addWidget(self.hourly_mail)
        lay.addWidget(_label("새 메일이 오면 보낸 사람을 알려 준다냥.", "help"))

        g, gl = _group("Gmail 연결")
        gl.addWidget(_card("연결 방법 (앱 비밀번호)", steps=["구글 계정에서 <b>2단계 인증</b> 켜기", "<b>앱 비밀번호</b> 만들기 (이름은 아무거나)", "나온 16자리를 아래에 붙여 넣기"],
                           links=[("myaccount.google.com 2단계 인증", URLS["twosv"]), ("myaccount.google.com 앱 비밀번호", URLS["apppw"])],
                           facts=[("읽는 것", "보낸 사람 이름만"), ("안 하는 것", "읽음 표시·삭제·보내기"),
                                  ("안 열리면", "2단계 인증이 꺼짐·패스키만 사용·회사/학교 계정(관리자가 막음)·다른 구글 계정으로 로그인한 경우예요.")],
                           open=not self.settings.get_secret("gmail_pass")))
        self.mail_addr = QLineEdit(self.settings.data["mail"].get("address", ""))
        self.mail_addr.setPlaceholderText("Gmail 주소 (예: name@gmail.com)")
        gl.addWidget(self.mail_addr)
        self.has_mail_pw = bool(self.settings.get_secret("gmail_pass"))
        self.mail_state = _status(MAIL_OK if self.has_mail_pw else "아직 앱 비밀번호가 없다냥", self.has_mail_pw)
        gl.addWidget(self.mail_state)
        self.mail_pw, row = _secret_row("앱 비밀번호 (16자리, 공백은 있어도 된다냥)")
        gl.addLayout(row)
        gl.addWidget(_label(MAIL_WARN, "warn"))
        brow = QHBoxLayout()
        t = QPushButton("📧 지금 새 메일 확인해 보기")
        t.clicked.connect(self._test_mail)
        brow.addWidget(t)
        brow.addWidget(_link_button("저장된 앱 비밀번호 지우기", self._clear_mail))
        brow.addStretch(1)
        gl.addLayout(brow)
        lay.addWidget(g)
        lay.addStretch(1)
        return page

    def _clear_mail(self):
        self.settings.set_secret("gmail_pass", "")
        self.settings.data["mail_state"] = {}
        self.settings.save()
        self.has_mail_pw = False
        self.mail_pw.clear()
        self.mail_state.setText("아직 앱 비밀번호가 없다냥")
        _restyle(self.mail_state, "help")

    def _apply_mail(self) -> bool:
        d = self.settings.data
        addr = self.mail_addr.text().strip()
        if addr and (not addr.isascii() or "@" not in addr or re.search(r"\s", addr)):
            QMessageBox.warning(self, "메일 주소 확인", "Gmail 주소가 이상하다냥 (예: name@gmail.com)")
            return False
        pw = re.sub(r"\s+", "", self.mail_pw.text())
        if pw:
            if len(pw) < 8 or not pw.isascii():
                QMessageBox.warning(self, "앱 비밀번호 확인", "앱 비밀번호가 이상하다냥. 구글이 보여 준 16자리를 그대로 붙여 넣어 달라옹 (영문·숫자만).")
                return False
            self.settings.set_secret("gmail_pass", pw)
            self.has_mail_pw = True
            self.mail_pw.clear()
            self.mail_state.setText(MAIL_OK)
            _restyle(self.mail_state, "ok")
            d["mail_state"] = {}                       # 새 계정/비밀번호면 기준점부터 다시
        if addr != d["mail"].get("address", ""):
            d["mail_state"] = {}
        d["mail"] = {"address": addr}
        return True

    # ------------------------------------------------------------ 소식 탭
    def _news_tab(self):
        page, lay = _page()
        sch = self.settings.data["schedules"]["news"]
        opts = self.settings.data["news_opts"]
        self.news_on = QCheckBox("정해 둔 시각에 소식(날씨·뉴스·시세)을 알려 주기")
        self.news_on.setChecked(bool(sch.get("enabled")))
        lay.addWidget(self.news_on)

        g, gl = _group("Gemini 연결")
        gl.addWidget(_card("연결 방법", steps=["Google AI Studio에서 <b>API 키</b> 만들기", "키를 아래에 붙여 넣고 ‘연결 시험’"],
                           links=[("aistudio.google.com/apikey 열기", URLS["aistudio"])],
                           facts=[("고양이가", "날씨·뉴스·시세를 직접 모아 와요"), ("Gemini가", "모은 자료를 정리만 해 줘요")],
                           open=not self.settings.get_secret("gemini_key")))
        self.has_key = bool(self.settings.get_secret("gemini_key"))
        self.key_state = _status(KEY_OK if self.has_key else "아직 키가 없다냥", self.has_key)
        gl.addWidget(self.key_state)
        self.key, row = _secret_row("Gemini API 키")
        gl.addLayout(row)
        mrow = QHBoxLayout()
        mrow.addWidget(QLabel("모델"))
        self.model = QLineEdit(self.settings.data.get("gemini_model", ""))
        self.model.setPlaceholderText(gemini_client.DEFAULT_MODEL + " (비우면 이 모델)")
        mrow.addWidget(self.model, 1)
        gl.addLayout(mrow)
        brow = QHBoxLayout()
        ping = QPushButton("🔌 연결 시험")
        ping.clicked.connect(self._ping)
        brow.addWidget(ping)
        brow.addWidget(_link_button("저장된 키 지우기", self._clear_key))
        brow.addStretch(1)
        gl.addLayout(brow)
        gl.addWidget(_label(NEWS_WARN, "warn"))
        lay.addWidget(g)

        g2, g2l = _group("소식 내용")
        crow = QHBoxLayout()
        crow.addWidget(QLabel("날씨 지역"))
        self.city = QComboBox()
        self.city.setMaxVisibleItems(14)
        self.city.addItem("자동 (이 컴퓨터의 IP 주소로 찾기)", news_sources.AUTO)
        for name in news_sources.CITIES:
            self.city.addItem(name, name)
        self.city.setCurrentIndex(max(0, self.city.findData(opts.get("city") or news_sources.AUTO)))
        crow.addWidget(self.city, 1)
        g2l.addLayout(crow)
        g2l.addWidget(_label("‘자동’은 틀릴 수 있다냥. 틀리면 직접 골라 달라옹.", "help"))
        g2l.addWidget(_label("시세 항목 (한 줄에 ‘이름=심볼’, 예: 코스피=^KS11)"))
        self.quotes = QPlainTextEdit(opts.get("quotes") or news_sources.DEFAULT_QUOTES)
        self.quotes.setFixedHeight(84)
        g2l.addWidget(self.quotes)
        g2l.addWidget(_label("고양이에게 시킬 정리 방법 (프롬프트)"))
        self.prompt = QPlainTextEdit(self.settings.data["prompts"].get("news") or gemini_client.DEFAULT_NEWS_PROMPT)
        self.prompt.setMinimumHeight(110)
        g2l.addWidget(self.prompt)
        g2l.addWidget(_link_button("기본값으로 되돌리기", self._reset_news_text), 0, Qt.AlignmentFlag.AlignLeft)
        self.use_search = QCheckBox("Gemini의 구글 검색 사용 (유료 등급 키만 가능)")
        self.use_search.setChecked(bool(opts.get("use_search")))
        g2l.addWidget(self.use_search)
        lay.addWidget(g2)

        self.news_times_ed = TimesEditor(sch.get("times", []), QTime(8, 0))
        lay.addWidget(self.news_times_ed)

        test = QPushButton("🐾 지금 시험해 보기")
        test.clicked.connect(self._test_news)
        lay.addWidget(test)
        lay.addStretch(1)
        return page

    # ------------------------------------------------------------ 어제 한 일 탭
    def _activity_tab(self):
        page, lay = _page()
        act = self.settings.data["activity"]
        sch = self.settings.data["schedules"]["yesterday"]
        self.act_on = QCheckBox("컴퓨터에서 쓴 프로그램과 창 제목을 기록하기")
        self.act_on.setChecked(bool(act.get("enabled") and act.get("consented")))
        self.act_on.clicked.connect(self._act_toggled)          # 사용자가 직접 눌렀을 때만 (동의 확인)
        lay.addWidget(self.act_on)
        self.act_status = _status("", False)
        lay.addWidget(self.act_status)

        g, gl = _group("기록 방법")
        gl.addWidget(_card("기록하는 내용", facts=[("저장하는 것", "프로그램 이름·창 제목 (5초마다, 이 컴퓨터에만)"), ("저장 안 함", "키보드로 친 내용"),
                                      ("세지 않는 때", "5분 넘게 입력이 없거나 화면이 잠긴 시간"), ("보관", "30일 뒤 자동 삭제")], open=False))
        gl.addWidget(QLabel("제외할 단어 (한 줄에 하나)"))
        self.act_exclude = QPlainTextEdit("\n".join(act.get("exclude", [])))
        self.act_exclude.setFixedHeight(72)
        gl.addWidget(self.act_exclude)
        gl.addWidget(_label(ACT_EXCL_HELP, "help"))
        brow = QHBoxLayout()
        opn = QPushButton("📂 기록 폴더 열기")
        opn.clicked.connect(self._open_folder)
        brow.addWidget(opn)
        brow.addWidget(_link_button("기록 모두 지우기", self._clear_activity))
        brow.addStretch(1)
        gl.addLayout(brow)
        lay.addWidget(g)

        g2, g2l = _group("지난 기록 보기 (최근 30일)")
        self.day_state = _label("", "help")
        g2l.addWidget(self.day_state)
        self.day_combo = QComboBox()
        g2l.addWidget(self.day_combo)
        drow = QHBoxLayout()
        self.btn_sum = QPushButton("🤖 AI 요약 보기")
        self.btn_sum.clicked.connect(self._summarize)
        self.btn_raw = QPushButton("📋 기록 그대로 보기")
        self.btn_raw.clicked.connect(self._raw)
        drow.addWidget(self.btn_sum)
        drow.addWidget(self.btn_raw)
        g2l.addLayout(drow)
        lay.addWidget(g2)
        self._refresh_days()
        self._refresh_act_status()

        g3, g3l = _group("정해 둔 시각에 어제 한 일 알려 주기")
        self.sum_on = QCheckBox("매일 정해 둔 시각에 어제 한 일을 요약해서 알려 주기")
        self.sum_on.setChecked(bool(sch.get("enabled")))
        g3l.addWidget(self.sum_on)
        g3l.addWidget(_label("고양이에게 시킬 정리 방법 (프롬프트)"))
        self.sum_prompt = QPlainTextEdit(self.settings.data["prompts"].get("yesterday") or gemini_client.DEFAULT_YESTERDAY_PROMPT)
        self.sum_prompt.setMinimumHeight(100)
        g3l.addWidget(self.sum_prompt)
        g3l.addWidget(_link_button("기본값으로 되돌리기", lambda: self.sum_prompt.setPlainText(gemini_client.DEFAULT_YESTERDAY_PROMPT)),
                      0, Qt.AlignmentFlag.AlignLeft)
        g3l.addWidget(_label("요약은 소식 탭의 Gemini 키로 만든다냥.", "help"))
        lay.addWidget(g3)

        self.sum_times_ed = TimesEditor(sch.get("times", []), QTime(9, 30))
        lay.addWidget(self.sum_times_ed)
        lay.addStretch(1)
        return page

    def _act_toggled(self, checked):
        """기록을 처음 켤 때 무엇이 저장되고 어디로 가는지 알리고 동의를 받는다."""
        act = self.settings.data["activity"]
        if checked and not act.get("consented"):
            ans = QMessageBox.question(self, "기록을 켤까냥?", ACT_CONSENT)
            if ans != QMessageBox.StandardButton.Yes:
                self.act_on.setChecked(False)
                return
            act["consented"] = True
        act["enabled"] = bool(checked and act.get("consented"))      # '저장'을 안 눌러도 바로 적용된다 (켜 놓고 닫았는데 기록이 안 되던 문제)
        self.settings.save()
        self._refresh_act_status()

    def _refresh_act_status(self):
        """기록이 지금 되고 있는지 한 줄로 보여 준다."""
        if self.activity is None or not hasattr(self, "act_status"):
            return
        import datetime
        import activity_log
        act = self.settings.data["activity"]
        if not (act.get("enabled") and act.get("consented")):
            self.act_status.setText("지금은 기록하지 않는다냥")
            _restyle(self.act_status, "help")
            return
        total = sum(sum(t.values()) for t in self.activity.load(datetime.date.today()).values())
        self.act_status.setText("기록 중이다냥 · 오늘 %s" % (activity_log.fmt_duration(total) if total >= 5 else "0초"))
        _restyle(self.act_status, "ok")

    def _refresh_days(self):
        """기록이 있는 날짜를 최근 순으로 콤보박스에 채운다."""
        if self.activity is None or not hasattr(self, "day_combo"):
            return
        import activity_log
        keep = self.day_combo.currentData()
        self.day_combo.clear()
        for d in reversed(self.activity.dates()):
            total = sum(sum(t.values()) for t in self.activity.load(d).values())
            self.day_combo.addItem("%s · %s" % (activity_log.day_label(d), activity_log.fmt_duration(total)), d.isoformat())
        has = self.day_combo.count() > 0
        i = self.day_combo.findData(keep) if keep else -1
        if i >= 0:
            self.day_combo.setCurrentIndex(i)
        self.day_combo.setEnabled(has)
        self.btn_sum.setEnabled(has)
        self.btn_raw.setEnabled(has)
        enabled = bool(self.settings.data["activity"].get("enabled"))
        self.day_state.setText("보고 싶은 날을 고르면 된다냥." if has else
                               ("기록을 시작했다냥. 하루가 지나면 날짜가 나온다옹." if enabled else "아직 기록이 없다냥. 위에서 기록을 켜 달라옹."))

    def _summarize(self):
        day = self.day_combo.currentData()
        if day and self._apply():
            self.run_test("yesterday", day)

    def _raw(self):
        day = self.day_combo.currentData()
        if day and self.show_raw:
            self.show_raw(day)

    def _open_folder(self):
        import os
        try:
            self.activity.dir.mkdir(parents=True, exist_ok=True)
            os.startfile(str(self.activity.dir))
        except OSError:
            pass

    def _clear_activity(self):
        n = len(self.activity.dates())
        if not n:
            QMessageBox.information(self, "기록 지우기", "지울 기록이 없다냥.")
            return
        if QMessageBox.question(self, "기록 모두 지우기", "저장된 기록 %d일치를 모두 지울까냥? (되돌릴 수 없다옹)" % n) == QMessageBox.StandardButton.Yes:
            self.activity.clear_all()
            self._refresh_days()

    # ------------------------------------------------------------ 생활 탭 (잠자는 시간·밥·놀아주기·구석 쉬기)
    def _care_tab(self):
        page, lay = _page()
        c = self.settings.data["care"]

        g, gl = _group("😴 잠자는 시간")
        self.night_on = QCheckBox("이 시간에는 구석에서 웅크리고 자기")
        self.night_on.setChecked(bool(c["night"].get("enabled")))
        gl.addWidget(self.night_on)
        row = QHBoxLayout()
        self.night_start = self._time_edit(c["night"].get("start"), QTime(22, 0))
        self.night_end = self._time_edit(c["night"].get("end"), QTime(7, 0))
        row.addWidget(QLabel("시작"))
        row.addWidget(self.night_start)
        row.addWidget(QLabel("끝"))
        row.addWidget(self.night_end)
        row.addStretch(1)
        gl.addLayout(row)
        gl.addWidget(_label("자는 동안 알림과 졸라대기를 쉰다냥.", "help"))
        lay.addWidget(g)

        g2, g2l = _group("🍚 밥 시간 (하루 세 번)")
        self.meals_on = QCheckBox("밥 시간에 밥을 안 주면 졸라대기")
        self.meals_on.setChecked(bool(c["meals"].get("enabled")))
        g2l.addWidget(self.meals_on)
        times = list(c["meals"].get("times", [])) + ["08:00", "13:00", "19:00"]
        self.meal_edits = []
        for i, default in enumerate((QTime(8, 0), QTime(13, 0), QTime(19, 0))):
            mrow = QHBoxLayout()                              # 한 줄에 하나씩 (옆으로 늘어놓으면 창보다 넓어진다)
            e = self._time_edit(times[i], default)
            self.meal_edits.append(e)
            lab = QLabel(("아침", "점심", "저녁")[i])
            lab.setMinimumWidth(36)
            mrow.addWidget(lab)
            mrow.addWidget(e)
            mrow.addStretch(1)
            g2l.addLayout(mrow)
        g2l.addWidget(_label("안 주면 3분마다 졸라댄다냥 (최대 10번).", "help"))
        lay.addWidget(g2)

        g3, g3l = _group("🧶 놀아주기")
        self.play_on = QCheckBox("일하는 사람도 쉬라고, 일정 시간마다 놀아 달라고 하기")
        self.play_on.setChecked(bool(c["play"].get("enabled")))
        g3l.addWidget(self.play_on)
        prow = QHBoxLayout()
        self.play_every = QSpinBox()
        self.play_every.setRange(10, 240)
        self.play_every.setSingleStep(5)
        self.play_every.setValue(int(c["play"].get("every_min", 60) or 60))
        self.play_every.setSuffix(" 분마다")
        prow.addWidget(self.play_every)
        prow.addStretch(1)
        g3l.addLayout(prow)
        g3l.addWidget(_label("마지막으로 논 뒤 이 시간이 지나면 졸라댄다냥.", "help"))
        lay.addWidget(g3)

        g4, g4l = _group("🛌 한쪽에서 쉬기")
        srow = QHBoxLayout()
        srow.addWidget(QLabel("쉬는 구석"))
        self.corner_side = QComboBox()
        self.corner_side.addItem("화면 오른쪽 아래", "right")
        self.corner_side.addItem("화면 왼쪽 아래", "left")
        self.corner_side.setCurrentIndex(max(0, self.corner_side.findData(c["corner"].get("side", "right"))))
        srow.addWidget(self.corner_side, 1)
        g4l.addLayout(srow)
        g4l.addWidget(_label("‘한쪽에서 쉬기’를 켜면 이 구석으로 간다냥.", "help"))
        lay.addWidget(g4)
        lay.addStretch(1)
        return page

    @staticmethod
    def _time_edit(text, default):
        e = QTimeEdit(default)
        e.setDisplayFormat("HH:mm")
        t = QTime.fromString(str(text or ""), "HH:mm")
        if t.isValid():
            e.setTime(t)
        return e

    def _apply_care(self):
        c = self.settings.data["care"]
        fmt = "HH:mm"
        c["night"] = {"enabled": self.night_on.isChecked(), "start": self.night_start.time().toString(fmt), "end": self.night_end.time().toString(fmt)}
        times = sorted({e.time().toString(fmt) for e in self.meal_edits})
        c["meals"] = {"enabled": self.meals_on.isChecked(), "times": times}
        c["play"] = {"enabled": self.play_on.isChecked(), "every_min": int(self.play_every.value())}
        c["corner"] = {"side": self.corner_side.currentData() or "right"}
        self.settings.save()

    # ------------------------------------------------------------ 경비 탭 (랜섬웨어 경보 · 잡은 쥐 기록)
    def _guard_tab(self):
        page, lay = _page()
        sec = self.settings.data["security"]
        r = sec["ransom"]
        self.sec_on = QCheckBox("경비 고양이 켜기 (쥐를 지켜보다가 수상하면 알려 줘요)")
        self.sec_on.setChecked(bool(sec.get("enabled")))
        lay.addWidget(self.sec_on)
        lay.addWidget(_label(GUARD_HELP, "help"))

        g, gl = _group("랜섬웨어 경보")
        self.ransom_on = QCheckBox("문서가 한꺼번에 암호화되기 시작하면 알리기")
        self.ransom_on.setChecked(bool(r.get("enabled")))
        gl.addWidget(self.ransom_on)
        self.canary_on = QCheckBox("숨김 미끼 파일 사용 (가장 빠른 경보)")
        self.canary_on.setChecked(bool(r.get("canary")))
        gl.addWidget(self.canary_on)
        srow = QHBoxLayout()
        srow.addWidget(QLabel("민감도"))
        self.sens = QComboBox()
        for key, label in (("loose", "느슨 (오탐 적음)"), ("normal", "보통"), ("strict", "엄격 (더 빨리, 오탐 가능)")):
            self.sens.addItem(label, key)
        self.sens.setCurrentIndex(max(0, self.sens.findData(r.get("sensitivity", "normal"))))
        srow.addWidget(self.sens, 1)
        gl.addLayout(srow)
        folders = chr(10).join("· " + f.replace(chr(92), chr(92) + chr(0x200b)) for f in self.guard.folders())     # 긴 경로가 줄을 바꿀 수 있게 \ 뒤에 보이지 않는 공백
        gl.addWidget(_label("지켜보는 폴더:" + chr(10) + (folders or "없음"), "help"))
        gl.addWidget(_label("숨김 가짜 문서가 바뀌면 바로 경보를 울린다냥.", "help"))
        b1 = QPushButton("미끼 파일 모두 지우기")
        b1.clicked.connect(self._remove_canaries)
        gl.addWidget(b1, 0, Qt.AlignmentFlag.AlignLeft)
        brow = QHBoxLayout()
        b2 = QPushButton("시험 경보 (위험)")
        b2.clicked.connect(lambda: self.guard.test_alert("danger"))
        b3 = QPushButton("시험 경보 (의심)")
        b3.clicked.connect(lambda: self.guard.test_alert("warn"))
        brow.addWidget(b2)
        brow.addWidget(b3)
        brow.addStretch(1)
        gl.addLayout(brow)
        lay.addWidget(g)

        g3, g3l = _group("자동 시작·실행 중 프로그램 점검")
        sc = sec.get("scan", {})
        self.scan_on = QCheckBox("몇 분마다 새 자동 시작 항목과 수상한 프로그램 찾아보기")
        self.scan_on.setChecked(bool(sc.get("enabled", True)))
        g3l.addWidget(self.scan_on)
        irow = QHBoxLayout()
        irow.addWidget(QLabel("점검 간격"))
        self.scan_every = QComboBox()
        for m in (5, 10, 30, 60):
            self.scan_every.addItem("%d분" % m, m)
        self.scan_every.setCurrentIndex(max(0, self.scan_every.findData(int(sc.get("interval_min", 10)))))
        irow.addWidget(self.scan_every)
        scan_btn = QPushButton("지금 점검")
        scan_btn.clicked.connect(self._scan_now)
        irow.addWidget(scan_btn)
        irow.addStretch(1)
        g3l.addLayout(irow)
        self.dl_on = QCheckBox("다운로드 폴더에 새로 받은 실행 파일 살펴보기")
        self.dl_on.setChecked(bool(sec.get("download", {}).get("enabled", True)))
        g3l.addWidget(self.dl_on)
        g3l.addWidget(_label("서명·출처·이중 확장자를 확인한다냥 (지우진 않음).", "help"))
        self.priv_on = QCheckBox("카메라·마이크를 처음 쓰는 프로그램이 있으면 알리기")
        self.priv_on.setChecked(bool(sec.get("privacy", {}).get("enabled", True)))
        g3l.addWidget(self.priv_on)
        g3l.addWidget(_label("처음 하루는 배우는 기간이다냥 (알림 없음).", "help"))
        al = sec.get("allow", {})
        self.allow_label = _label("허용한 항목: 프로그램 %d개, 자동 시작 %d개, 카메라·마이크 %d개" % (len(al.get("process", [])), len(al.get("autorun", [])), len(al.get("privacy", []))), "help")
        g3l.addWidget(self.allow_label)
        g3l.addWidget(_link_button("허용 목록 지우기", self._clear_allow), 0, Qt.AlignmentFlag.AlignLeft)
        g3l.addWidget(_label("처음 상태를 저장하고, 새로 생긴 것만 알려 준다냥.", "help"))
        lay.addWidget(g3)

        gv, gvl = _group("VirusTotal 조회 (선택)")
        self.vt_on = QCheckBox("수상한 파일의 해시값을 VirusTotal에 물어보기")
        self.vt_on.setChecked(bool(sec.get("vt", {}).get("enabled")))
        gvl.addWidget(self.vt_on)
        gvl.addWidget(_card("연결 방법 (무료)", steps=["virustotal.com에서 무료 계정 만들기", "프로필의 <b>API key</b> 복사", "아래에 붙여 넣고 ‘연결 시험’"],
                            links=[("virustotal.com 열기", URLS["vt"]), ("virustotal.com/gui/my-apikey (로그인 후)", URLS["vt_key"])],
                            facts=[("보내는 것", "파일의 해시값(지문)만. 내용·이름은 안 보내요"), ("조회 대상", "서명이 없는 수상한 파일만 (결과 30일 보관)"),
                                   ("무료 한도", "분당 4건·하루 500건 (고양이가 지켜요)"), ("주의", "‘정보 없음’은 안전하다는 뜻이 아니에요")],
                            open=not self.settings.get_secret("vt_key")))
        self.has_vt = bool(self.settings.get_secret("vt_key"))
        self.vt_state = _status(KEY_OK if self.has_vt else "아직 키가 없다냥", self.has_vt)
        gvl.addWidget(self.vt_state)
        self.vt_key, vrow = _secret_row("VirusTotal API 키 (무료 계정에서 받는다냥)")
        gvl.addLayout(vrow)
        vb = QHBoxLayout()
        vtest = QPushButton("연결 시험")
        vtest.clicked.connect(self._vt_test)
        vb.addWidget(vtest)
        vb.addWidget(_link_button("저장된 키 지우기", self._clear_vt))
        vb.addStretch(1)
        gvl.addLayout(vb)
        lay.addWidget(gv)

        g2, g2l = _group("잡은 쥐 기록 (최근 30일)")
        self.sec_list = QListWidget()
        self.sec_list.setMinimumHeight(150)
        self.sec_list.itemDoubleClicked.connect(self._open_event)
        g2l.addWidget(self.sec_list)
        rrow = QHBoxLayout()
        o = QPushButton("자세히 보기")
        o.clicked.connect(lambda: self._open_event(self.sec_list.currentItem()))
        rf = QPushButton("새로고침")
        rf.clicked.connect(self._refresh_events)
        rrow.addWidget(o)
        rrow.addWidget(rf)
        rrow.addWidget(_link_button("기록 모두 지우기", self._clear_events))
        rrow.addStretch(1)
        g2l.addLayout(rrow)
        lay.addWidget(g2)
        self._refresh_events()
        lay.addStretch(1)
        return page

    def _vt_test(self):
        key = self.vt_key.text().strip() or self.settings.get_secret("vt_key")
        if not key:
            QMessageBox.information(self, "VirusTotal", "먼저 API 키를 넣어 달라냥.")
            return
        self.guard.vt_test_async(key)

    def _clear_vt(self):
        self.settings.set_secret("vt_key", "")
        self.has_vt = False
        self.vt_key.clear()
        self.vt_state.setText("아직 키가 없다냥")
        _restyle(self.vt_state, "help")

    def _scan_now(self):
        self._apply()
        self.guard.scan_async()

    def _clear_allow(self):
        a = self.settings.data["security"]["allow"]
        a["process"], a["autorun"], a["privacy"] = [], [], []
        self.settings.save()
        self.allow_label.setText("허용한 항목: 프로그램 0개, 자동 시작 0개, 카메라·마이크 0개")

    def _refresh_events(self):
        import datetime
        self.sec_list.clear()
        marks = {"danger": "위험", "warn": "의심", "info": "참고"}
        st = {"new": "새 것", "seen": "확인함", "ignored": "무시", "allowed": "허용"}
        for e in self.guard.events.recent(100):
            it = QListWidgetItem("%s  [%s] %s  (%s)" % (datetime.datetime.fromtimestamp(e["ts"]).strftime("%m-%d %H:%M"), marks.get(e["level"], ""), e["title"],
                                                         st.get(e["status"], "")))
            it.setData(Qt.ItemDataRole.UserRole, e["id"])
            self.sec_list.addItem(it)
        if not self.sec_list.count():
            self.sec_list.addItem("아직 잡은 쥐가 없다냥 (좋은 일이다옹)")

    def _open_event(self, item):
        if item is None:
            return
        ev = self.guard.events.get(item.data(Qt.ItemDataRole.UserRole) or "")
        if ev and self.show_alert:
            self.show_alert(ev, True)

    def _clear_events(self):
        if self.guard.events.recent(1) and QMessageBox.question(self, "기록 지우기", "잡은 쥐 기록을 모두 지울까냥?") == QMessageBox.StandardButton.Yes:
            self.guard.events.clear()
            self._refresh_events()

    def _remove_canaries(self):
        if QMessageBox.question(self, "미끼 파일 지우기", "고양이가 만든 숨김 미끼 파일을 모두 지울까냥? (다른 파일은 건드리지 않는다옹)\n"
                                "지우면 '숨김 미끼 파일 사용'도 꺼진다냥.") == QMessageBox.StandardButton.Yes:
            n = self.guard.remove_canaries()
            self.canary_on.setChecked(False)
            QMessageBox.information(self, "미끼 파일 지우기", "미끼 파일 %d개를 지웠다냥." % n)

    def _apply_guard(self):
        d = self.settings.data["security"]
        d["enabled"] = self.sec_on.isChecked()
        d["ransom"].update({"enabled": self.ransom_on.isChecked(), "canary": self.canary_on.isChecked(), "sensitivity": self.sens.currentData() or "normal"})
        d["scan"] = {"enabled": self.scan_on.isChecked(), "interval_min": int(self.scan_every.currentData() or 10)}
        d["privacy"] = {"enabled": self.priv_on.isChecked()}
        d["download"] = {"enabled": self.dl_on.isChecked()}
        key = self.vt_key.text().strip()
        if key:
            if len(key) < 20 or not key.isascii() or " " in key:
                QMessageBox.warning(self, "VirusTotal 키 확인", "VirusTotal 키가 이상하다냥. 공백이나 한글 없이 키만 붙여 넣어 달라옹.")
            else:
                self.settings.set_secret("vt_key", key)
                self.has_vt = True
                self.vt_key.clear()
                self.vt_state.setText(KEY_OK)
                _restyle(self.vt_state, "ok")
        d["vt"] = {"enabled": self.vt_on.isChecked() and bool(self.settings.get_secret("vt_key"))}
        self.settings.save()

    def _reset_news_text(self):
        self.prompt.setPlainText(gemini_client.DEFAULT_NEWS_PROMPT)
        self.quotes.setPlainText(news_sources.DEFAULT_QUOTES)

    def _clear_key(self):
        self.settings.set_secret("gemini_key", "")
        self.has_key = False
        self.key.clear()
        self.key_state.setText("아직 키가 없다냥")
        _restyle(self.key_state, "help")

    def _clear_url(self):
        self.settings.set_secret("calendar_url", "")
        self.has_url = False
        self.url.clear()
        self.url_state.setText("아직 주소가 없다냥")
        _restyle(self.url_state, "help")

    # ------------------------------------------------------------ 저장/시험
    def _apply_news(self) -> bool:
        new_key = self.key.text().strip()
        if new_key:
            if len(new_key) < 10 or not new_key.isascii() or re.search(r"\s", new_key):
                QMessageBox.warning(self, "키 확인", "Gemini 키가 이상해 보인다냥. 공백이나 한글 없이 키만 붙여 넣어 달라옹.")
                return False
            self.settings.set_secret("gemini_key", new_key)
            self.has_key = True
            self.key.clear()
            self.key_state.setText(KEY_OK)
            _restyle(self.key_state, "ok")
        model = self.model.text().strip()
        if model and not re.fullmatch(r"[A-Za-z0-9._-]{1,80}", model):
            QMessageBox.warning(self, "모델 확인", "모델 이름은 영문·숫자·점·하이픈만 쓸 수 있다냥 (예: %s)." % gemini_client.DEFAULT_MODEL)
            return False
        d = self.settings.data
        d["gemini_model"] = model
        prompt = self.prompt.toPlainText().strip()
        d["prompts"]["news"] = "" if prompt in ("", gemini_client.DEFAULT_NEWS_PROMPT) else prompt[:4000]
        quotes = self.quotes.toPlainText().strip()
        parsed = news_sources.parse_quotes(quotes)
        d["news_opts"] = {"city": self.city.currentData() or news_sources.AUTO,
                          "quotes": "" if not parsed or quotes == news_sources.DEFAULT_QUOTES else "\n".join("%s=%s" % x for x in parsed),
                          "use_search": self.use_search.isChecked()}
        sch = d["schedules"]["news"]
        sch["enabled"] = self.news_on.isChecked()
        sch["times"] = self.news_times_ed.get()
        self.settings.save()
        return True

    def _apply_activity(self):
        d = self.settings.data
        act = d["activity"]
        act["enabled"] = bool(self.act_on.isChecked() and act.get("consented"))      # 동의 없이는 켜지지 않는다
        words = []
        for line in self.act_exclude.toPlainText().splitlines():
            w = line.strip()[:40]
            if w and w not in words:
                words.append(w)
        act["exclude"] = words[:50]
        prompt = self.sum_prompt.toPlainText().strip()
        d["prompts"]["yesterday"] = "" if prompt in ("", gemini_client.DEFAULT_YESTERDAY_PROMPT) else prompt[:4000]
        sch = d["schedules"]["yesterday"]
        sch["enabled"] = self.sum_on.isChecked()
        sch["times"] = self.sum_times_ed.get()
        self.settings.save()

    def _apply(self) -> bool:
        """화면의 값을 설정에 반영하고 저장한다. 주소·키가 틀리면 안내하고 False."""
        if not self._apply_news():
            return False
        if not self._apply_mail():
            return False
        d = self.settings.data
        d["hourly_opts"] = {"calendar": self.hourly_cal.isChecked(), "hours": int(self.hourly_hours.value()), "mail": self.hourly_mail.isChecked()}
        if self.activity is not None:
            self._apply_activity()
        if self.guard is not None:
            self._apply_guard()
        self._apply_care()
        new_url = self.url.text().strip()
        if new_url:
            try:
                calendar_ics.normalize_url(new_url)
            except calendar_ics.CalendarError as e:
                QMessageBox.warning(self, "주소 확인", str(e))
                return False
            self.settings.set_secret("calendar_url", calendar_ics.normalize_url(new_url))
            self.has_url = True
            self.url.clear()
            self.url_state.setText(URL_OK)
            _restyle(self.url_state, "ok")
        sch = self.settings.data["schedules"]["calendar"]
        sch["enabled"] = self.cal_on.isChecked()
        sch["times"] = self.times_ed.get()
        self.settings.save()
        return True

    def _save(self):
        if self._apply():
            self.on_saved()
            self.save_msg.setText("저장했다냥. 창은 닫기를 눌러야 닫힌다옹.")
            self._save_timer.start(3500)

    def _test(self):
        if self._apply():
            self.run_test("calendar")

    def _test_hourly_cal(self):
        if self._apply():
            self.run_test("hourly", "calendar")

    def _test_mail(self):
        if self._apply():
            self.run_test("hourly", "mail")

    def _test_news(self):
        if self._apply():
            self.run_test("news")

    def _ping(self):
        if self._apply():
            self.run_test("gemini_ping")
