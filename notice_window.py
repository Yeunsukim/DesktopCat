"""소식 창: Gemini가 가져온 소식(Markdown)을 보여 주는 새 창.

 · 일반 창이지만 뜰 때 포커스를 가져가지 않는다(WA_ShowWithoutActivating): 작업 중에 타자를 치고 있어도 입력이 이 창으로 새지 않는다.
 · AI 답변 안의 링크는 http/https 만 열린다. (file:// 같은 주소를 눌러서 프로그램이 실행되는 일을 막는다)
 · 창은 하나만 쓰고, 새 소식이 오면 내용을 바꿔서 다시 보여 준다.
"""
import os
import time

import win32con
import win32gui
from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QColor, QFont, QTextBlockFormat, QTextCharFormat, QTextCursor
import cute
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QTextBrowser, QVBoxLayout, QWidget

FOOTER = "AI가 정리한 내용이라 틀릴 수 있다냥. 주식·환율은 숫자만 전할 뿐 투자 조언이 아니다옹."
FOOTER_ACTIVITY = "AI가 프로그램 이름과 창 제목만 보고 짐작한 요약이라 틀릴 수 있다냥."
FOOTER_RAW = "이 컴퓨터에 저장된 기록 그대로다냥. (AI에게 보내지 않았다옹)"

# 본문(Markdown)의 모양: 제목은 주황 포인트, 줄 간격은 넉넉하게
DOC_CSS = ("h1 { font-size: 24px; color: #D94A76; } h2 { font-size: 18px; color: #D94A76; } h3 { font-size: 14px; color: #D94A76; }"
           "li { margin-bottom: 4px; } a { color: #E5557E; } hr { color: #F6C5D5; }")


class NoticeWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("소식왔다~옹~ 🐾")
        self.setObjectName("page")
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.resize(560, 720)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 18, 18, 14)
        lay.setSpacing(12)
        head = QHBoxLayout()                              # 제목과 날짜를 한 줄에: '오늘의 소식  (2026-10-16 15:40 기준)'
        head.setContentsMargins(6, 0, 6, 0)
        self.title = QLabel("")
        self.title.setStyleSheet("font-size: 22px; font-weight: bold; color: #D94A76;")
        self.when = QLabel("")
        self.when.setObjectName("help")
        self.avatar = cute.CatAvatar(54, "talk")                    # 고양이가 알려 주는 느낌: 동그란 원 안의 고양이 얼굴
        head.addWidget(self.avatar)
        head.addSpacing(8)
        head.addWidget(self.title, 0, Qt.AlignmentFlag.AlignVCenter)
        head.addSpacing(10)
        head.addWidget(self.when, 0, Qt.AlignmentFlag.AlignVCenter)
        head.addStretch(1)
        lay.addLayout(head)
        self.view = QTextBrowser()
        self.view.setOpenLinks(False)
        self.view.setFont(QFont("Malgun Gothic", 11))
        self.view.document().setDefaultStyleSheet(DOC_CSS)
        self.view.document().setDocumentMargin(28)
        self.view.setStyleSheet("QTextBrowser { background: #FFFFFF; border: 1px solid #F6C5D5; border-radius: 14px; }")
        self.view.anchorClicked.connect(self._link)
        lay.addWidget(self.view)
        self.foot = QLabel(FOOTER)
        self.foot.setWordWrap(True)
        self.foot.setObjectName("help")
        lay.addWidget(self.foot)

    @staticmethod
    def _link(url: QUrl):
        if url.scheme().lower() in ("http", "https"):
            try:
                os.startfile(url.toString())
            except Exception:
                pass

    @staticmethod
    def compose(text: str, sources: list) -> str:
        """본문과 출처를 하나의 Markdown 으로 합친다 (제목·날짜는 위쪽 한 줄에 따로 보여 준다)."""
        md = "%s\n" % text.strip()
        if sources:
            md += "\n---\n**출처**\n\n"
            for s in sources[:12]:
                t = (s.get("title") or s["url"]).replace("[", "(").replace("]", ")")
                md += "- [%s](%s)\n" % (t, s["url"])
        return md

    def show_result(self, title: str, text: str, sources: list, when: str | None = None, activate: bool = False,
                    footer: str | None = None):
        """activate=True: 사용자가 직접 시험했을 때처럼 '지금 보고 싶다'는 경우, 창을 맨 앞으로 가져오고 포커스도 준다.
        False(정해 둔 시각에 저절로 뜰 때): 포커스는 안 가져가되 다른 창들 위에는 보이게 한다."""
        self.title.setText(title)
        self.foot.setText(footer or FOOTER)
        self.when.setText("(%s 기준)" % (when or time.strftime("%Y-%m-%d %H:%M")))
        self.view.setMarkdown(self.compose(text, sources))
        self._style_doc()
        self.view.verticalScrollBar().setValue(0)
        if self.isMinimized():
            self.showNormal()
        self.show()
        self.raise_()
        if activate:
            self.activateWindow()
        else:
            self._lift_without_focus()

    def _lift_without_focus(self):
        """포커스 없이 창 순서만 맨 위로: 잠깐 '항상 위'로 올렸다가 바로 풀면 다른 창들 위에 남는다."""
        try:
            hwnd = int(self.winId())
            flags = win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_NOACTIVATE
            win32gui.SetWindowPos(hwnd, win32con.HWND_TOPMOST, 0, 0, 0, 0, flags)
            win32gui.SetWindowPos(hwnd, win32con.HWND_NOTOPMOST, 0, 0, 0, 0, flags)
        except Exception:
            pass

    def _style_doc(self):
        """Markdown 읽기는 스타일시트를 안 쓰므로 직접 꾸민다: 제목은 주황 포인트 색,
        줄 간격은 122%로 단정하게, 소제목 위만 조금 띄우고 목록 항목 사이는 촘촘하게."""
        fmt = QTextCharFormat()
        fmt.setForeground(QColor("#D94A76"))
        block = self.view.document().begin()
        while block.isValid():
            bf = QTextBlockFormat()
            bf.setLineHeight(122, QTextBlockFormat.LineHeightTypes.ProportionalHeight.value)
            level = block.blockFormat().headingLevel()
            if level:
                bf.setTopMargin(4 if level == 1 else 14)
                bf.setBottomMargin(4)
            elif block.textList() is not None:
                bf.setBottomMargin(2)
            else:
                bf.setTopMargin(0)
                bf.setBottomMargin(6)
            cur = QTextCursor(block)
            cur.mergeBlockFormat(bf)
            if level:
                cur.select(QTextCursor.SelectionType.BlockUnderCursor)
                cur.mergeCharFormat(fmt)
            block = block.next()

    def bring_front(self):
        """풍선을 눌렀을 때: 창을 앞으로 가져온다(이때는 사용자가 원한 것이니 포커스도 준다)."""
        if self.isVisible():
            self.raise_()
            self.activateWindow()
