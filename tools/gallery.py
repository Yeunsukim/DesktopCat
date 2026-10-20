"""모든 동작을 한 장의 이미지로 뽑는다:  python tools/gallery.py  →  preview/gallery.png"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from preview import sheet

import animations as A
from animations_runtime import Animator

# (표시 이름, 동작, 시간, 보행 위상 or 점프 진행도)
SPECS = [
    ("stand", "stand", 1.0, 0), ("walk", "walk", 0, 0.12), ("trot", "trot", 0, 0.1), ("run", "run", 0, 0.05),
    ("sneak", "sneak", 0, 0.1), ("sit", "sit", 1.0, 0), ("sit tilt", "sit_tilt", 2.5, 0), ("loaf", "loaf", 1.0, 0), ("groom", "groom", 0.1, 0),
    ("yawn", "yawn", 1.0, 0), ("scratch", "scratch", 0.05, 0), ("stretch", "stretch", 1.6, 0),
    ("tail play", "tail_play", 0.1, 0),
    ("sleep 1 curl", "sleep_curl", 1, 0), ("sleep 2 side", "sleep_side", 1, 0), ("sleep 3 nap", "sleep_nap", 1, 0),
    ("sleep doze", "sleep_doze", 3, 0),
    ("eat", "eat", 0.3, 0), ("knead", "knead", 0.2, 0), ("stroke", "stroke", 1.0, 0), ("crouch", "crouch", 0.3, 0),
    ("jump up", "jump", 0, 0.08), ("jump stretch", "jump", 0, 0.4), ("jump reach", "jump", 0, 0.92),
    ("land", "land", 0.05, 0),
    ("fall", "fall", 0.6, 0), ("held", "hold", 0.3, 0), ("swat (kick)", "swat", 0.32, 0), ("bat ball", "bat", 0.34, 0),
    ("wiggle", "wiggle", 1.0, 0), ("bunny kick", "bunny", 0.1, 0),
]


def main():
    frames = []
    for label, name, t, k in SPECS:
        an = Animator(name)
        an.clock, an.t = t, t
        if name in A.GAITS:
            an.u = k
        an.param = {"p": k}
        frames.append((label, A.ANIMS[name](an), t))
    out = Path(__file__).resolve().parent.parent / "preview"
    out.mkdir(exist_ok=True)
    sheet(frames, out / "gallery.png", cols=5, cell=(330, 250), scale=1.55, ground=38)
    print("saved", out / "gallery.png")


if __name__ == "__main__":
    main()

