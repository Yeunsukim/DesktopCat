"""프로그램 아이콘(assets/cat.ico, assets/cat_icon.png)을 만든다: 분홍 동그라미 속 고양이 비서 얼굴(cute.app_icon_pixmap)을 크기마다 새로 그려서 .ico 로 저장.
설치 파일·실행 파일·바로가기·시작 메뉴 아이콘이 이것을 쓴다.
    python tools/make_icon.py
"""
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PyQt6.QtCore import QBuffer, QByteArray, QIODevice
from PyQt6.QtWidgets import QApplication

app = QApplication.instance() or QApplication(["icon"])
import cute

SIZES = (16, 24, 32, 48, 64, 128, 256)


def png_bytes(pm):
    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    pm.toImage().save(buf, "PNG")
    return bytes(ba)


def write_ico(path, sizes):
    """크기마다 따로 그린 PNG 를 담은 .ico (큰 아이콘은 PNG 그대로 담는 현재 윈도우 형식). Pillow 의 축소 저장은 작은 크기가 흐려서 직접 쓴다."""
    import struct
    imgs = [(s, png_bytes(cute.app_icon_pixmap(s))) for s in sizes]
    head = struct.pack("<HHH", 0, 1, len(imgs))
    off = 6 + 16 * len(imgs)
    entries, data = b"", b""
    for s, png in imgs:
        entries += struct.pack("<BBBBHHII", 0 if s >= 256 else s, 0 if s >= 256 else s, 0, 0, 1, 32, len(png), off + len(data))
        data += png
    Path(path).write_bytes(head + entries + data)


out = ROOT / "assets" / "cat.ico"
write_ico(out, SIZES)
cute.app_icon_pixmap(256).save(str(ROOT / "assets" / "cat_icon.png"))
print("saved", out, out.stat().st_size, "bytes")
