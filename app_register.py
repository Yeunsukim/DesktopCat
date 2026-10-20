"""'앱 등록…' 창: 런처(고양이를 누르면 열리는 반원)에 아이콘을 추가한다.

등록할 수 있는 것 네 가지:
 · 프로그램·파일      exe, 바로가기, 문서 …                              (kind = file)
 · 웹 주소            https://… (런처에는 사이트의 파비콘이 뜬다)          (kind = url)
 · 명령 실행          cmd 또는 PowerShell 창을 열고 명령을 쳐 준다           (kind = cmd, shell = cmd | powershell, keep = 창 유지)
 · 윈도우 도구        제어판·장치 관리자·윈도우 설정 같은 시스템 도구         (kind = sys)
고양이 창(포커스를 가져가지 않는 최상위 도구창)을 부모로 주면 창이 그 위에 떠서, 다른 창 뒤에 숨지 않는다. 모양은 theme.py·cute.py 를 따른다.
"""
import os
from pathlib import Path

import cute
from PyQt6.QtWidgets import (QCheckBox, QComboBox, QDialog, QFileDialog, QHBoxLayout, QLabel, QLineEdit, QPushButton, QRadioButton,
                             QVBoxLayout, QWidget)

FILE_FILTER = "프로그램·바로가기 (*.exe *.lnk *.bat *.cmd *.url);;모든 파일 (*.*)"

# (표시 이름, 실행 대상). control 은 제어판 항목(.cpl), ms-settings: 는 윈도우 설정 화면, .msc 는 관리 콘솔
SYSTEM_TOOLS = [
    ("제어판", "control"),
    ("윈도우 설정", "ms-settings:"),
    ("프로그램 및 기능 (설치된 프로그램 지우기)", "control appwiz.cpl"),
    ("장치 관리자", "devmgmt.msc"),
    ("작업 관리자", "taskmgr"),
    ("네트워크 연결", "control ncpa.cpl"),
    ("Wi-Fi 설정", "ms-settings:network-wifi"),
    ("소리 설정", "control mmsys.cpl"),
    ("디스플레이 설정", "ms-settings:display"),
    ("블루투스 및 장치", "ms-settings:bluetooth"),
    ("앱 설정", "ms-settings:appsfeatures"),
    ("전원 옵션", "control powercfg.cpl"),
    ("시스템 속성", "control sysdm.cpl"),
    ("디스크 관리", "diskmgmt.msc"),
    ("서비스", "services.msc"),
    ("이벤트 뷰어", "eventvwr.msc"),
    ("파일 탐색기", "explorer"),
    ("계산기", "calc"),
    ("메모장", "notepad"),
]
KINDS = ("file", "url", "cmd", "sys")
KIND_LABEL = {"file": "프로그램·파일", "url": "웹 주소", "cmd": "명령 실행 (cmd·PowerShell)", "sys": "윈도우 도구 (제어판 등)"}


class AppRegisterDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle("앱 등록 🐾")
        self.setMinimumWidth(460)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 16, 18, 16)
        lay.setSpacing(10)
        head = QHBoxLayout()
        head.addWidget(cute.CatAvatar(46, "happy"))
        head.addSpacing(8)
        t = QLabel("고양이 아이콘에 앱 추가하기")
        t.setObjectName("title")
        head.addWidget(t)
        head.addStretch(1)
        lay.addLayout(head)
        h = QLabel("고양이를 누르면 나오는 반원에 아이콘이 생긴다냥. 눌러서 바로 열 수 있다옹.")
        h.setObjectName("help")
        h.setWordWrap(True)
        lay.addWidget(h)

        self.radios = {}
        for row_kinds in (("file", "url"), ("cmd", "sys")):
            row = QHBoxLayout()
            for k in row_kinds:
                r = QRadioButton(KIND_LABEL[k])
                self.radios[k] = r
                row.addWidget(r)
            row.addStretch(1)
            lay.addLayout(row)
        self.radios["file"].setChecked(True)

        # 입력 칸들 (종류에 따라 보이는 것만 보인다)
        self.target = QLineEdit()
        trow = QHBoxLayout()
        trow.setContentsMargins(0, 0, 0, 0)
        trow.addWidget(self.target, 1)
        self.browse = QPushButton("찾아보기…")
        self.browse.clicked.connect(self._browse)
        trow.addWidget(self.browse)
        self.target_box = QWidget()
        self.target_box.setLayout(trow)
        lay.addWidget(self.target_box)

        self.cmd_box = QWidget()
        cl = QHBoxLayout(self.cmd_box)
        cl.setContentsMargins(0, 0, 0, 0)
        self.shell = QComboBox()
        self.shell.addItem("cmd (명령 프롬프트)", "cmd")
        self.shell.addItem("PowerShell", "powershell")
        cl.addWidget(self.shell)
        self.keep = QCheckBox("실행 후에도 창 열어 두기")
        self.keep.setChecked(True)
        cl.addWidget(self.keep)
        cl.addStretch(1)
        lay.addWidget(self.cmd_box)

        self.tool_box = QWidget()
        tl = QVBoxLayout(self.tool_box)
        tl.setContentsMargins(0, 0, 0, 0)
        self.tool = QComboBox()
        for name, tgt in SYSTEM_TOOLS:
            self.tool.addItem(name, tgt)
        self.tool.setMaxVisibleItems(14)
        self.tool.currentIndexChanged.connect(self._tool_changed)
        tl.addWidget(self.tool)
        lay.addWidget(self.tool_box)

        lay.addWidget(QLabel("런처에 보일 이름"))
        self.name = QLineEdit()
        lay.addWidget(self.name)

        self.msg = QLabel("")
        self.msg.setObjectName("warn")
        self.msg.setWordWrap(True)
        lay.addWidget(self.msg)

        btns = QHBoxLayout()
        btns.addStretch(1)
        cancel = QPushButton("취소")
        cancel.clicked.connect(self.reject)
        ok = QPushButton("등록")
        ok.setDefault(True)
        ok.clicked.connect(self._ok)
        btns.addWidget(cancel)
        btns.addWidget(ok)
        lay.addLayout(btns)

        for r in self.radios.values():
            r.toggled.connect(self._kind_changed)
        self._kind_changed()

    def kind(self) -> str:
        return next(k for k, r in self.radios.items() if r.isChecked())

    def is_url(self) -> bool:
        return self.kind() == "url"

    def _kind_changed(self):
        k = self.kind()
        self.target_box.setVisible(k in ("file", "url", "cmd"))
        self.browse.setVisible(k == "file")
        self.cmd_box.setVisible(k == "cmd")
        self.tool_box.setVisible(k == "sys")
        self.target.setPlaceholderText({"file": "프로그램이나 파일 경로", "url": "웹 주소 (예: https://www.naver.com)",
                                        "cmd": "실행할 명령 (예: ping 8.8.8.8 / ipconfig /all / dir C:" + chr(92) + ")"}.get(k, ""))
        if k == "sys":
            self._tool_changed()
        self.msg.setText("")

    def _tool_changed(self, *_):
        if self.kind() == "sys":
            self.name.setText(self.tool.currentText().split(" (")[0])

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(self, "등록할 프로그램을 골라 달라냥", "", FILE_FILTER)
        if path:
            path = os.path.normpath(path)
            self.target.setText(path)
            if not self.name.text().strip():
                self.name.setText(Path(path).stem)

    def result_values(self):
        """(이름, 대상, 종류, 부가 정보 dict) 또는 입력이 모자라면 None."""
        k = self.kind()
        if k == "sys":
            return self.name.text().strip() or self.tool.currentText().split(" (")[0], self.tool.currentData(), "sys", {}
        target = self.target.text().strip()
        if not target:
            return None
        if k == "url":
            if "://" not in target:
                target = "https://" + target
            name = self.name.text().strip() or target.split("://", 1)[1].split("/", 1)[0]
            return name, target, "url", {}
        if k == "cmd":
            name = self.name.text().strip() or (target if len(target) <= 14 else target[:13] + "…")
            return name, target, "cmd", {"shell": self.shell.currentData(), "keep": self.keep.isChecked()}
        target = os.path.normpath(target)
        return self.name.text().strip() or Path(target).stem, target, "file", {}

    def _ok(self):
        v = self.result_values()
        if v is None:
            self.msg.setText("등록할 대상을 먼저 적어 달라냥")
            return
        if v[2] == "file" and not os.path.exists(v[1]):
            self.msg.setText("그런 파일을 못 찾겠다냥 (경로를 확인해 달라옹)")
            return
        self.accept()


def register_app(parent, settings) -> str:
    """창을 띄우고 결과를 한 줄로 돌려준다: 'added' / 'duplicate' / 'cancel'."""
    dlg = AppRegisterDialog(parent)
    if not dlg.exec():
        return "cancel"
    name, target, kind, extra = dlg.result_values()
    return "added" if settings.add_app(name, target, kind, **extra) else "duplicate"
