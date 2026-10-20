"""포즈/애니메이션을 이미지 시트로 뽑아 눈으로 확인하는 개발용 도구 (화면 불필요)."""
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont, QGuiApplication, QImage, QPainter

from catrig import CatRig, load_skin

_app = QGuiApplication.instance() or QGuiApplication(["preview"])
# 환경변수 SKIN=0 이면 일러스트, 기본은 실사 스킨 (있을 때)
_ROOT = Path(__file__).resolve().parent.parent
RIG = CatRig(load_skin(_ROOT / "assets" / "skin") if os.environ.get("SKIN", "1") != "0" else None)


def sheet(frames, path, cols=4, cell=(300, 230), scale=1.5, bg="#9fd0c8", ground=34):
    """frames: [(label, pose_dict, t, facing)]  → PNG 한 장."""
    rows = (len(frames) + cols - 1) // cols
    img = QImage(cell[0] * cols, cell[1] * rows, QImage.Format.Format_ARGB32)
    img.fill(QColor(bg))
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    font = QFont("Arial", 9)
    p.setFont(font)
    for i, f in enumerate(frames):
        label, ps = f[0], f[1]
        t = f[2] if len(f) > 2 else 0.0
        facing = f[3] if len(f) > 3 else 1
        cx, cy = (i % cols) * cell[0], (i // cols) * cell[1]
        p.setPen(QColor(0, 0, 0, 90))
        p.drawLine(cx, cy + cell[1] - ground, cx + cell[0], cy + cell[1] - ground)
        p.setPen(QColor(20, 20, 20))
        p.drawText(cx + 6, cy + 16, label)
        RIG.draw(p, ps, t, facing, scale, origin=(cx + cell[0] / 2, cy + cell[1] - ground))
        p.setPen(QColor(255, 255, 255, 120))
        p.drawRect(cx, cy, cell[0], cell[1])
    p.end()
    img.save(str(path))
    return path
