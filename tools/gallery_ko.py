"""모든 동작을 설명과 함께 한 장으로:  python tools/gallery_ko.py  →  preview/all_actions.png"""
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PIL import Image, ImageDraw, ImageFont
from PyQt6.QtGui import QColor, QGuiApplication, QImage, QPainter

import animations as A
from animations_runtime import Animator
from catrig import CatRig, load_skin

app = QGuiApplication.instance() or QGuiApplication(["gallery"])
RIG = CatRig(load_skin(ROOT / "assets" / "skin"))
FONT = ImageFont.truetype("C:/Windows/Fonts/malgun.ttf", 17)
FONT_B = ImageFont.truetype("C:/Windows/Fonts/malgunbd.ttf", 20)
FONT_H = ImageFont.truetype("C:/Windows/Fonts/malgunbd.ttf", 26)

# (분류, 이름, 설명, 동작, 시간, 보행위상, 추가 파라미터)
ITEMS = [
    ("이동", "걷기", "평소에 느긋하게 돌아다닙니다. 발이 바닥에서 미끄러지지 않게 걸음 폭에 맞춰 움직여요.", "walk", 0, 0.12, {}),
    ("이동", "종종걸음", "신나거나 기분 좋을 때 빠르게 걷습니다.", "trot", 0, 0.1, {}),
    ("이동", "달리기 (우다다)", "몸을 쭉 뻗고 귀를 뒤로 눕히고 달립니다. 가끔 \"우다다다냐옹!\" 하고 말합니다.", "run", 0, 0.05, {}),
    ("이동", "살금살금", "몸을 낮추고 귀를 눕힌 채 먹잇감에 다가가듯 걷습니다.", "sneak", 0, 0.1, {}),
    ("점프", "웅크리기", "뛰기 직전에 몸을 낮추고 엉덩이를 씰룩입니다.", "crouch", 0.3, 0, {}),
    ("점프", "뛰어오르기", "몸을 위로 쭉 펴고 앞발을 머리 위로 뻗어 창 위로 올라갑니다.", "jump", 1, 0, {"p": 0.4}),
    ("점프", "창 모서리 걸치기", "올라가는 끝에 앞발을 앞으로 뻗어 창 윗변을 짚습니다.", "jump", 1, 0, {"p": 0.95}),
    ("점프", "뛰어내리기 / 낙하", "머리를 아래로 하고 앞발을 뻗어 내려갑니다. 창 가장자리에서 떨어질 때와 던졌을 때도 같아요.", "fall", 1, 0, {}),
    ("점프", "착지", "내려와서 몸을 낮춰 충격을 받고 다시 일어섭니다.", "land", 0.05, 0, {}),
    ("점프", "집어 올리기", "마우스로 드래그하면 목덜미를 잡힌 것처럼 대롱대롱 매달립니다.", "hold", 0.3, 0, {}),
    ("쉬기", "서 있기", "숨 쉬며 두리번거리고, 귀와 꼬리가 가끔 움직입니다.", "stand", 1, 0, {}),
    ("쉬기", "앉기", "엉덩이를 붙이고 앉아 주위를 둘러봅니다.", "sit", 1, 0, {}),
    ("쉬기", "몸 세우고 앉아 갸웃", "가장 자주 하는 자세. 몸을 곧게 세우고 고개를 갸웃하며 이쪽을 봅니다.", "sit_tilt", 2.5, 0, {}),
    ("쉬기", "식빵 자세", "앞발을 몸 아래로 접고 웅크려 앉습니다.", "loaf", 1, 0, {}),
    ("잠자기", "잠자기 1 (동그랗게)", "몸을 동그랗게 말고 꼬리로 몸을 감싸 잡니다.", "sleep_curl", 1, 0, {}),
    ("잠자기", "잠자기 2 (옆으로)", "옆으로 누워 다리를 쭉 뻗고 잡니다.", "sleep_side", 1, 0, {}),
    ("잠자기", "잠자기 3 (턱 괴고)", "식빵 자세로 앞발에 턱을 괴고 존다.", "sleep_nap", 1, 0, {}),
    ("잠자기", "꾸벅꾸벅 졸기", "앉은 채로 고개를 꾸벅이며 존다.", "sleep_doze", 3, 0, {}),
    ("몸단장", "그루밍 1: 앞발 핥기", "앉아서 앞발을 혀로 핥습니다.", "groom", 0.1, 0, {}),
    ("몸단장", "그루밍 2: 뒷다리 들고 핥기", "앉아서 몸을 뒤로 젖히고 뒷다리 하나를 높이 들어 허벅지를 핥습니다.", "groom_leg", 0.1, 0, {}),
    ("몸단장", "그루밍 4: 세수", "가까운 쪽 앞발을 핥은 뒤, 그 발로 얼굴을 쓸어 닦습니다. 반대쪽 앞발은 바닥에 서 있습니다.", "groom_face", 0.5, 0, {}),
    ("몸단장", "그루밍 3: 목 긁기", "고개를 뒤로 젖히고 눈을 감은 채, 뒷발로 목 밑을 시원하게 긁습니다.", "scratch_neck", 0.05, 0, {}),
    ("몸단장", "하품", "입을 크게 벌려 하품합니다. 턱이 내려가고 송곳니가 보여요.", "yawn", 1, 0, {}),
    ("몸단장", "기지개", "앞다리를 쭉 뻗고 엉덩이를 치켜들며 쭈욱 늘어납니다.", "stretch", 1.6, 0, {}),
    ("몸단장", "귀 뒤 긁기", "앉아서 뒷발로 귀 뒤를 긁습니다.", "scratch", 0.05, 0, {}),
    ("먹기 · 놀기", "밥 먹기", "메뉴의 '밥 주기'를 누르면 밥그릇에 얼굴을 넣고 냠냠 씹습니다.", "eat", 0.3, 0, {}),
    ("먹기 · 놀기", "꾹꾹이", "방석 위에서 눈을 감고 앞발을 번갈아 꾹꾹 누르며 골골거립니다.", "knead", 0.2, 0, {}),
    ("먹기 · 놀기", "꼬리 가지고 놀기", "자기 꼬리를 쳐다보며 앞발로 톡톡 건드립니다.", "tail_play", 0.1, 0, {}),
    ("먹기 · 놀기", "아이콘 발로 차기", "바탕화면 아이콘 옆으로 가서 앞발로 후려쳐 아이콘을 날려 보냅니다.", "swat", 0.32, 0, {}),
    ("먹기 · 놀기", "털실공: 엉덩이 씰룩", "'놀아주기'를 누르면 시작. 공을 노려보며 엉덩이를 씰룩입니다.", "wiggle", 1, 0, {}),
    ("먹기 · 놀기", "털실공: 덮치기", "공을 향해 폴짝 뛰어 덮칩니다.", "hop", 0, 0.45, {"p": 0.45}),
    ("먹기 · 놀기", "털실공: 툭 치기", "앞발로 공을 툭 쳐서 굴립니다.", "bat", 0.34, 0, {}),
    ("먹기 · 놀기", "털실공: 끌어안고 뒷발킥", "공을 끌어안고 뒷발로 팡팡 찹니다.", "bunny", 0.1, 0, {}),
    ("반응", "쓰다듬기", "마우스를 몸 위에서 쓱쓱 문지르면 눈을 감고 골골송을 부르며 엉덩이를 치켜듭니다.", "stroke", 1, 0, {}),
]

CELL_W, CELL_H, IMG_H, COLS = 440, 500, 350, 4
CAT_COLORS = {"이동": "#4f86c6", "점프": "#d9822b", "쉬기": "#5aa469", "잠자기": "#7a6bc4", "몸단장": "#c75d8a",
              "먹기 · 놀기": "#c4a02e", "반응": "#d4504f"}


def render(name, t, k, param):
    an = Animator(name)
    an.clock, an.t = t, t
    if name in A.GAITS:
        an.u = k
    an.param = dict(param)
    ps = an.pose()
    img = QImage(CELL_W, IMG_H, QImage.Format.Format_ARGB32)
    img.fill(QColor("#dff0ec"))
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    gy = IMG_H - 46
    p.setPen(QColor(0, 0, 0, 60))
    p.drawLine(0, gy, CELL_W, gy)
    RIG.tail.a = None                                   # 꼬리 시뮬레이션을 매번 새로 시작
    RIG.draw(p, ps, 1.0, 1, 1.4, origin=(CELL_W / 2 - 10, gy))
    p.end()
    ptr = img.constBits()
    ptr.setsize(img.sizeInBytes())
    return Image.frombuffer("RGBA", (CELL_W, IMG_H), bytes(ptr), "raw", "BGRA", 0, 1).convert("RGB")


def wrap(draw, text, font, width):
    lines, cur = [], ""
    for ch in text:
        if draw.textlength(cur + ch, font=font) > width:
            lines.append(cur)
            cur = ch.lstrip()
        else:
            cur += ch
    if cur:
        lines.append(cur)
    return lines


def main():
    rows = (len(ITEMS) + COLS - 1) // COLS
    head = 90
    sheet = Image.new("RGB", (CELL_W * COLS, head + CELL_H * rows), "#f7f5f0")
    d = ImageDraw.Draw(sheet)
    d.text((24, 22), f"고양이가 할 수 있는 동작 {len(ITEMS)}가지", font=FONT_H, fill="#2b2b2b")
    d.text((24, 58), "아래 모든 동작은 사진을 입힌 뼈대 고양이가 실시간으로 만들어 냅니다.", font=FONT, fill="#666")
    for i, (cat, name, desc, anim, t, k, prm) in enumerate(ITEMS):
        x, y = (i % COLS) * CELL_W, head + (i // COLS) * CELL_H
        sheet.paste(render(anim, t, k, prm), (x, y))
        d.rectangle((x, y, x + CELL_W - 1, y + CELL_H - 1), outline="#d8d4c8")
        col = CAT_COLORS[cat]
        d.rounded_rectangle((x + 10, y + 10, x + 10 + d.textlength(cat, font=FONT) + 18, y + 38), 8, fill=col)
        d.text((x + 19, y + 12), cat, font=FONT, fill="white")
        d.text((x + 14, y + IMG_H + 8), f"{i + 1}. {name}", font=FONT_B, fill="#222")
        for j, line in enumerate(wrap(d, desc, FONT, CELL_W - 28)[:3]):
            d.text((x + 14, y + IMG_H + 40 + j * 24), line, font=FONT, fill="#555")
    out = ROOT / "preview" / "all_actions.png"
    out.parent.mkdir(exist_ok=True)
    sheet.save(out)
    print("saved", out, sheet.size)


if __name__ == "__main__":
    main()

