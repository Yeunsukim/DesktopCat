"""공통 디자인(테마): 우클릭 메뉴, 앱 등록, 설정, 대화상자가 같은 분위기로 보이게 하는 스타일시트(QSS).

따뜻한 크림색 바탕 + 고양이 털색 주황 포인트 + 둥근 모서리. 앱을 시작할 때 apply(app, 폴더)를 한 번 부른다.
 · 체크 표시 그림은 시작할 때 한 번 만들어 데이터 폴더에 둔다 (스타일시트가 파일 그림만 받을 수 있어서).
 · 직접 그리는 창(풍선, 런처 반원)은 이 스타일의 영향을 받지 않는다.
"""
from pathlib import Path

from PyQt6.QtCore import QEvent, QObject, QPointF, Qt
from PyQt6.QtGui import QColor, QFont, QPainter, QPalette, QPen, QPixmap

BG = "#FFE6EE"          # 창 바탕 (아주 연한 분홍)
CARD = "#FFFFFF"        # 입력 칸·카드
LINE = "#F6C5D5"        # 테두리
TEXT = "#5A3A47"        # 글씨 (검정 대신 자두색)
SUB = "#A8728A"         # 보조 글자
ACCENT = "#F67499"      # 대표 분홍 (참고 사이트의 #f67499)
ACCENT_D = "#E5557E"
SOFT = "#FFD3E0"        # 선택·강조 바탕
WARN = "#D8456F"


def _check_png(folder: Path) -> str:
    """흰 체크 표시 그림을 만들어 경로를 돌려준다 (실패하면 빈 문자열: 체크 칸이 주황색 네모로만 보인다)."""
    try:
        path = Path(folder) / "theme_check.png"
        if not path.exists():
            pm = QPixmap(36, 36)
            pm.fill(Qt.GlobalColor.transparent)
            p = QPainter(pm)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            pen = QPen(QColor("white"), 4.6)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            p.setPen(pen)
            p.drawPolyline([QPointF(9, 19), QPointF(15.5, 25.5), QPointF(27, 11)])
            p.end()
            pm.save(str(path), "PNG")
        return str(path).replace("\\", "/")
    except Exception:
        return ""


def _arrow_png(folder: Path, up: bool) -> str:
    """작은 삼각형 화살표 그림 (시간·콤보 상자의 위/아래 버튼용). 실패하면 빈 문자열."""
    try:
        path = Path(folder) / ("theme_arrow2_%s.png" % ("up" if up else "down"))
        if not path.exists():
            pm = QPixmap(40, 40)
            pm.fill(Qt.GlobalColor.transparent)
            p = QPainter(pm)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor("#D94A76"))
            tri = [QPointF(8, 26), QPointF(32, 26), QPointF(20, 11)] if up else [QPointF(8, 14), QPointF(32, 14), QPointF(20, 29)]
            p.drawPolygon(tri)
            p.end()
            pm.save(str(path), "PNG")
        return str(path).replace("\\", "/")
    except Exception:
        return ""


def stylesheet(check_png: str = "", up_png: str = "", down_png: str = "") -> str:
    check = "image: url(%s);" % check_png if check_png else ""
    up = "image: url(%s);" % up_png if up_png else ""
    down = "image: url(%s);" % down_png if down_png else ""
    return """
* { font-family: "Malgun Gothic", "Segoe UI Emoji"; font-size: 13px; }
QDialog, QMessageBox, QInputDialog, QFileDialog, QWidget#page { background: %(BG)s; }
QLabel { color: %(TEXT)s; background: transparent; }
QLabel#help { color: %(SUB)s; }
QLabel#warn { color: %(WARN)s; }
QLabel#ok { color: #2F8F5F; font-weight: bold; }
QLabel#title { font-size: 16px; font-weight: bold; }
QFrame#card { background: %(BG)s; border: 1px solid %(LINE)s; border-radius: 10px; }
QLabel#cardtitle { color: %(ACCENT_D)s; font-weight: bold; }
QLabel#stepnum { background: %(ACCENT)s; color: white; border-radius: 9px; font-weight: bold; font-size: 11px; }
QLabel#factkey { color: %(TEXT)s; font-weight: bold; }
QLabel#facts { color: %(SUB)s; }
QToolTip { background: %(CARD)s; color: %(TEXT)s; border: 1px solid %(LINE)s; padding: 4px 8px; }

QTabWidget::pane { border: none; background: transparent; }
QTabBar { background: transparent; }
QTabBar::tab { background: transparent; color: %(SUB)s; padding: 7px 10px; margin: 0 2px 8px 0; border-radius: 16px; }
QTabBar::tab:selected { background: %(SOFT)s; color: #D94A76; font-weight: bold; }
QTabBar::tab:hover:!selected { background: #FFEFF4; }

QGroupBox { background: %(CARD)s; border: 2px solid %(LINE)s; border-radius: 18px; margin-top: 16px; padding: 16px 12px 12px 12px; }
QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; left: 12px; top: 1px; padding: 0 6px; color: #D94A76; font-weight: bold; }

QPushButton { background: %(CARD)s; border: 1px solid #F2B8CB; border-radius: 15px; padding: 7px 18px; color: %(TEXT)s; }
QPushButton:hover { background: #FFEDF3; border-color: #EF99B1; }
QPushButton:pressed { background: #FFD0DF; }
QPushButton:disabled { color: #D9AEBF; background: #F8E4EC; }
QPushButton:default, QPushButton#primary { background: %(ACCENT)s; border: 1px solid %(ACCENT_D)s; color: white; font-weight: bold; }
QPushButton:default:hover, QPushButton#primary:hover { background: #EF5F88; }
QPushButton#ghost { background: %(CARD)s; border: 1px solid #F2B8CB; border-radius: 15px; padding: 7px 18px; color: %(SUB)s; }
QPushButton#ghost:hover { color: %(WARN)s; border-color: %(WARN)s; background: #FFF3F7; }
QPushButton#url { background: transparent; border: none; color: #2F6FD0; text-decoration: underline; padding: 2px 2px; text-align: left; }
QPushButton#url:hover { color: #1C4FA0; background: transparent; }
QPushButton#fold { background: transparent; border: none; color: %(ACCENT_D)s; font-weight: bold; text-align: left; padding: 2px 0; }
QPushButton#fold:hover { background: transparent; color: %(WARN)s; }
QPushButton#link { background: transparent; border: none; color: %(WARN)s; padding: 2px 6px; }
QPushButton#link:hover { text-decoration: underline; background: transparent; }

QLineEdit, QPlainTextEdit, QTextEdit, QTimeEdit, QComboBox, QListWidget, QSpinBox {
    background: %(CARD)s; border: 1px solid #F2B8CB; border-radius: 9px; padding: 6px 9px; color: %(TEXT)s;
    selection-background-color: #FFB3C8; selection-color: %(TEXT)s; }
QLineEdit:focus, QPlainTextEdit:focus, QTimeEdit:focus, QComboBox:focus, QListWidget:focus { border: 1px solid %(ACCENT)s; }
QComboBox::drop-down { border: none; width: 26px; }
QComboBox::down-arrow { %(down)s width: 14px; height: 14px; }
QTimeEdit, QSpinBox { padding-right: 30px; min-height: 22px; }
QTimeEdit::up-button, QSpinBox::up-button { subcontrol-origin: border; subcontrol-position: top right; width: 26px; height: 16px; margin: 1px 1px 0 0;
    background: #FFEDF3; border-left: 1px solid #F2B8CB; border-top-right-radius: 8px; }
QTimeEdit::down-button, QSpinBox::down-button { subcontrol-origin: border; subcontrol-position: bottom right; width: 26px; height: 16px; margin: 0 1px 1px 0;
    background: #FFEDF3; border-left: 1px solid #F2B8CB; border-top: 1px solid #FADCE6; border-bottom-right-radius: 8px; }
QTimeEdit::up-button:hover, QTimeEdit::down-button:hover, QSpinBox::up-button:hover, QSpinBox::down-button:hover { background: #FFC9D9; }
QTimeEdit::up-button:pressed, QTimeEdit::down-button:pressed, QSpinBox::up-button:pressed, QSpinBox::down-button:pressed { background: #FFB3C8; }
QTimeEdit::up-arrow, QSpinBox::up-arrow { %(up)s width: 12px; height: 12px; }
QTimeEdit::down-arrow, QSpinBox::down-arrow { %(down)s width: 12px; height: 12px; }
QComboBox QAbstractItemView { background: %(CARD)s; color: %(TEXT)s; border: 1px solid %(LINE)s; selection-background-color: %(SOFT)s; selection-color: #D94A76; outline: 0; }
QComboBox QAbstractItemView::item { color: %(TEXT)s; min-height: 24px; padding: 2px 8px; }
QComboBox QAbstractItemView::item:selected { background: %(SOFT)s; color: #D94A76; }
QTextBrowser { color: %(TEXT)s; }
QListWidget { padding: 4px; }
QListWidget::item { padding: 4px 8px; border-radius: 6px; }
QListWidget::item:selected { background: %(SOFT)s; color: #D94A76; }

QRadioButton { spacing: 9px; color: %(TEXT)s; }
QRadioButton::indicator { width: 18px; height: 18px; border-radius: 10px; border: 1px solid #EBA9BF; background: %(CARD)s; }
QRadioButton::indicator:checked { background: qradialgradient(cx:0.5, cy:0.5, radius:0.5, fx:0.5, fy:0.5, stop:0 #FFFFFF, stop:0.38 #FFFFFF, stop:0.42 %(ACCENT)s, stop:1 %(ACCENT)s); border-color: %(ACCENT_D)s; }
QCheckBox { spacing: 9px; color: %(TEXT)s; }
QCheckBox::indicator { width: 20px; height: 20px; border-radius: 6px; border: 1px solid #EBA9BF; background: %(CARD)s; }
QCheckBox::indicator:hover { border-color: %(ACCENT)s; }
QCheckBox::indicator:checked { background: %(ACCENT)s; border-color: %(ACCENT_D)s; %(check)s }

QScrollArea { background: transparent; border: none; }
QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar::handle:vertical { background: #F4B6CA; border-radius: 4px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: #EF99B1; }
QScrollBar::add-line, QScrollBar::sub-line { height: 0; width: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }

QMenu { background: #FFF7FA; border: 1px solid %(LINE)s; border-radius: 12px; padding: 6px; }
QMenu::item { padding: 8px 26px 8px 14px; border-radius: 8px; color: %(TEXT)s; margin: 1px 0; }
QMenu::item:selected { background: %(SOFT)s; color: #D94A76; }
QMenu::item:disabled { color: %(SUB)s; }
QMenu::separator { height: 1px; background: #FADCE6; margin: 6px 10px; }
QMenu { icon-size: 22px; }
QMenu::indicator { width: 16px; height: 16px; left: 6px; border-radius: 4px; }
QMenu::indicator:checked { background: %(ACCENT)s; %(check)s }
""" % dict(BG=BG, CARD=CARD, LINE=LINE, TEXT=TEXT, SUB=SUB, ACCENT=ACCENT, ACCENT_D=ACCENT_D, SOFT=SOFT, WARN=WARN, check=check, up=up, down=down)


def light_palette(app):
    """윈도우가 '다크 모드'여도 이 프로그램의 창은 늘 연한 분홍 바탕·자두색 글씨로 보이게 한다.
    (다크 모드에서는 기본 글씨색이 흰색이라 스타일시트가 색을 정하지 않은 곳이 '흰 바탕에 흰 글씨'가 되어 목록·본문이 텅 빈 것처럼 보였다.)"""
    try:
        app.styleHints().setColorScheme(Qt.ColorScheme.Light)          # Qt 6.8 이상: 앱을 밝은 모드로 고정
    except Exception:
        pass
    pal = QPalette()
    for role, color in ((QPalette.ColorRole.Window, BG), (QPalette.ColorRole.WindowText, TEXT), (QPalette.ColorRole.Base, CARD),
                        (QPalette.ColorRole.AlternateBase, BG), (QPalette.ColorRole.Text, TEXT), (QPalette.ColorRole.Button, CARD),
                        (QPalette.ColorRole.ButtonText, TEXT), (QPalette.ColorRole.ToolTipBase, CARD), (QPalette.ColorRole.ToolTipText, TEXT),
                        (QPalette.ColorRole.Highlight, SOFT), (QPalette.ColorRole.HighlightedText, "#D94A76"),
                        (QPalette.ColorRole.PlaceholderText, SUB), (QPalette.ColorRole.Link, "#2F6FD0")):
        pal.setColor(role, QColor(color))
    app.setPalette(pal)


class _TitleBar(QObject):
    """창이 보일 때마다 윈도우 제목 표시줄을 밝은 분홍으로 맞춘다.
    윈도우가 다크 모드면 제목 표시줄이 검은색이라 안쪽의 분홍 화면과 어울리지 않는다.
    · 다크 모드 표시(DWMWA_USE_IMMERSIVE_DARK_MODE)를 끈다 (윈도우 10 이상)
    · 윈도우 11 에서는 제목 표시줄 색과 글씨색도 테마색으로 칠한다 (윈도우 10 에서는 무시되고 흰색 제목 표시줄로 남는다)"""

    def eventFilter(self, obj, ev):
        if ev.type() == QEvent.Type.Show and obj.isWidgetType() and obj.isWindow() and not (obj.windowFlags() & Qt.WindowType.FramelessWindowHint):
            self.paint(obj)
        return False

    @staticmethod
    def paint(w):
        try:
            import ctypes
            hwnd = int(w.winId())
            dwm = ctypes.windll.dwmapi

            def put(attr, value):
                v = ctypes.c_int(value)
                dwm.DwmSetWindowAttribute(ctypes.c_void_p(hwnd), attr, ctypes.byref(v), 4)

            put(20, 0)                                   # DWMWA_USE_IMMERSIVE_DARK_MODE = 끔
            put(35, 0x00EEE6FF)                          # DWMWA_CAPTION_COLOR  (BG #FFE6EE, 0x00BBGGRR)
            put(36, 0x00473A5A)                          # DWMWA_TEXT_COLOR     (TEXT #5A3A47)
            put(34, 0x00D5C5F6)                          # DWMWA_BORDER_COLOR   (LINE #F6C5D5)
        except Exception:
            pass


_title_bar = None


def apply(app, folder: Path):
    """앱 전체에 테마를 입힌다."""
    app.setFont(QFont("Malgun Gothic", 10))
    light_palette(app)
    global _title_bar
    _title_bar = _TitleBar(app)
    app.installEventFilter(_title_bar)
    app.setStyleSheet(stylesheet(_check_png(folder), _arrow_png(folder, True), _arrow_png(folder, False)))


def round_menu(menu):
    """QMenu 의 둥근 모서리가 보이게 창 바탕을 투명하게 한다(윈도우에서는 이렇게 해야 모서리 뒤 네모가 안 보인다)."""
    menu.setWindowFlags(menu.windowFlags() | Qt.WindowType.FramelessWindowHint | Qt.WindowType.NoDropShadowWindowHint)
    menu.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
