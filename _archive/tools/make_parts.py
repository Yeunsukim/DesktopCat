"""한 장의 걷는 고양이 사진에서 '뼈대 인형'용 부품(몸통·다리 4개·꼬리·머리·목)을 오린다. (개발용: OpenCV·scipy·Pillow 필요)

원본: assets/ai/1-이동-걷기-2/f1.png  (옆모습, 오른쪽을 봄, 네 다리가 모두 보이는 컷)
결과: assets/parts/*.png 와 assets/parts/parts.json, assets/parts/uv.npz

방법
 · 다리·꼬리·목: 중심선(관절 점들)을 따라 곧게 펴서 오린 '띠'(rectified strip). 앱에서 이 띠를 관절 위치를 따라 구부려 붙인다.
 · 몸통: 등선~배선 사이를 오려낸 사진 (다리·꼬리·머리 쪽은 잘라 냄). 앱에서 세로 조각으로 나눠 척추 곡선을 따라 붙인다.
 · 머리: 목 쪽은 서서히 투명하게 오려낸 사진.
 · 모든 부품은 '원본 사진의 어느 자리였는지'(uv)를 같이 저장한다 → 삼색처럼 털색 무늬를 바꿀 때 부품이 달라도 무늬가 이어진다.
"""
import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image
from scipy.interpolate import splev, splprep
from scipy.spatial import cKDTree

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "assets" / "ai" / "1-이동-걷기-2" / "f1.png"
OUT = ROOT / "assets" / "parts"

# ---------------------------------------------------------------- 사진 위의 관절/중심선 (원본 픽셀 좌표, 눈금을 얹은 확대 그림에서 읽은 값)
LEGS = {
    # 이름: (중심선 점들 위→아래, 띠 반폭)   위쪽 끝은 몸통 안쪽(어깨/엉덩이 쪽)
    "front_a": ([(358, 118), (357, 160), (355, 195), (366, 240)], 30),     # 곧게 선 앞다리
    "front_b": ([(404, 122), (422, 160), (440, 198), (476, 234)], 32),     # 앞으로 뻗은 앞다리
    "hind_a": ([(168, 124), (140, 160), (106, 198), (104, 240)], 38),      # 뒤로 밀어낸 뒷다리
    "hind_b": ([(196, 138), (198, 172), (212, 205), (240, 236)], 34),      # 앞으로 나가는 뒷다리
}
TAIL = ([(132, 92), (120, 112), (100, 134), (72, 151), (44, 165), (22, 163), (6, 158)], 26)
NECK = ([(385, 105), (415, 85), (445, 62)], 46)
HEAD_BOX = (398, 0, 510, 104)           # 머리(귀 포함) 잘라내는 사각형 (x0, y0, x1, y1)
HEAD_ANCHOR = (462, 50)                 # 머리 중심 (회전 중심, 앱에서 리그의 머리 중심에 맞춘다)
TORSO_X = (112, 440)                    # 몸통 가로 범위 (왼쪽은 엉덩이, 오른쪽은 가슴·목 아래)
BELLY = ([112, 128, 150, 185, 240, 300, 335, 380, 405, 440], [136, 134, 148, 160, 160, 157, 154, 148, 140, 118])   # 배선(다리가 붙기 전 몸통 아래 경계)
FADE_TOP = 18                           # 다리·꼬리의 몸통 쪽 끝을 서서히 투명하게 하는 길이(띠 픽셀)


def load():
    a = np.array(Image.open(SRC).convert("RGBA")).astype(np.float32)
    return a


def smooth_polyline(pts, n):
    pts = np.array(pts, np.float32)
    k = min(3, len(pts) - 1)
    tck, _ = splprep([pts[:, 0], pts[:, 1]], k=k, s=0)
    u = np.linspace(0, 1, n)
    x, y = splev(u, tck)
    dx, dy = splev(u, tck, der=1)
    return np.stack([x, y], 1), np.stack([dx, dy], 1)


def strip(img, pts, hw, step=1.0, fade_top=FADE_TOP, others=None):
    """중심선을 따라 곧게 펴서 오린 띠. 위쪽(v=0)이 pts[0]. 가로가 +x(진행 방향의 오른쪽)."""
    rough, _ = smooth_polyline(pts, 400)
    seg = np.hypot(*np.diff(rough, axis=0).T)
    length = float(seg.sum())
    n = max(8, int(length / step))
    c, d = smooth_polyline(pts, n)
    d = d / np.maximum(np.hypot(d[:, 0], d[:, 1])[:, None], 1e-6)
    nrm = np.stack([d[:, 1], -d[:, 0]], 1)                         # 진행 방향이 아래(0,1)일 때 (1,0)
    v = np.arange(-hw, hw, 1.0, dtype=np.float32) + 0.5
    mx = (c[:, 0:1] + nrm[:, 0:1] * v[None, :]).astype(np.float32)
    my = (c[:, 1:2] + nrm[:, 1:2] * v[None, :]).astype(np.float32)
    pre = img.copy()
    if others:                                                       # 이웃 다리·몸통 아래쪽 픽셀 제거: 내 중심선이 다른 중심선보다 가까운 곳만 남긴다
        own, _ = smooth_polyline(pts, 300)
        tree_o = cKDTree(own)
        tree_x = cKDTree(np.concatenate([smooth_polyline(q, 300)[0] for q in others]))
        gy, gx = np.mgrid[0:img.shape[0], 0:img.shape[1]]
        q = np.stack([gx.ravel(), gy.ravel()], 1).astype(np.float32)
        do, _ = tree_o.query(q)
        dx, _ = tree_x.query(q)
        mine = (do <= dx * 0.92 + 1.0).reshape(img.shape[:2])
        pre[..., 3] = pre[..., 3] * mine
    pre[..., :3] *= pre[..., 3:4] / 255.0
    out = cv2.remap(pre, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
    al = np.maximum(out[..., 3:4], 1e-3)
    rgb = np.clip(out[..., :3] / (al / 255.0), 0, 255)
    a = out[..., 3]
    if fade_top > 0:
        ramp = np.clip(np.arange(n) / float(fade_top), 0, 1)[:, None]
        a = a * ramp
    res = np.dstack([rgb, a]).astype(np.uint8)
    uv = np.stack([mx / img.shape[1], my / img.shape[0]], -1).astype(np.float16)
    return res, uv, length


def main():
    img = load()
    H, W = img.shape[:2]
    OUT.mkdir(parents=True, exist_ok=True)
    meta = {"photo": [W, H], "legs": {}, "scale_hint": 0.40}
    uvs = {}

    for name, (pts, hw) in LEGS.items():
        others = [q for n2, (q, _) in LEGS.items() if n2 != name] + [TAIL[0]]
        s, uv, length = strip(img, pts, hw, others=others)
        Image.fromarray(s, "RGBA").save(OUT / f"{name}.png")
        uvs[name] = uv
        meta["legs"][name] = {"length": length, "half_width": hw, "size": [s.shape[1], s.shape[0]]}

    s, uv, length = strip(img, TAIL[0], TAIL[1], fade_top=14)
    Image.fromarray(s, "RGBA").save(OUT / "tail.png")
    uvs["tail"] = uv
    meta["tail"] = {"length": length, "half_width": TAIL[1], "size": [s.shape[1], s.shape[0]]}

    s, uv, length = strip(img, NECK[0], NECK[1], fade_top=0)
    # 목: 양 끝을 부드럽게 (몸통 쪽·머리 쪽)
    n = s.shape[0]
    ramp = np.minimum(np.clip(np.arange(n) / 14.0, 0, 1), np.clip((n - 1 - np.arange(n)) / 14.0, 0, 1))[:, None]
    s[..., 3] = (s[..., 3] * ramp).astype(np.uint8)
    Image.fromarray(s, "RGBA").save(OUT / "neck.png")
    uvs["neck"] = uv
    meta["neck"] = {"length": length, "half_width": NECK[1], "size": [s.shape[1], s.shape[0]]}

    # 몸통: 가로 TORSO_X, 세로는 등선 위쪽 여유부터 배선까지. 배선 아래는 잘라 낸다 (다리 자리).
    x0, x1 = TORSO_X
    xs = np.arange(x0, x1)
    belly = np.interp(xs, BELLY[0], BELLY[1])
    y0 = 20
    y1 = int(belly.max()) + 6
    crop = img[y0:y1, x0:x1].copy()
    yy = (np.arange(y0, y1)[:, None]).astype(np.float32)
    cut = np.clip((belly[None, :] + 1.5 - yy) / 3.0, 0, 1)                    # 배선 아래는 투명 (3픽셀 부드럽게)
    crop[..., 3] *= cut
    # 엉덩이 왼쪽 경계: 꼬리 밑동 쪽(왼쪽 위)은 꼬리 띠가 맡으므로, 꼬리가 몸통에 붙는 선(세로에 가까운 선)에서 몸통을 자른다
    TAIL_CUT = [(128, 60), (126, 100), (118, 140)]                              # (x, y) 위→아래, 이 선보다 왼쪽은 몸통에서 제외
    cx_line = np.interp(np.arange(y0, y1), [q[1] for q in TAIL_CUT], [q[0] for q in TAIL_CUT])
    side = np.clip((np.arange(x0, x1)[None, :] - cx_line[:, None]) / 5.0, 0, 1)
    crop[..., 3] *= side
    Image.fromarray(crop.astype(np.uint8), "RGBA").save(OUT / "torso.png")
    gx, gy = np.meshgrid(xs, np.arange(y0, y1))
    uvs["torso"] = np.stack([gx / W, gy / H], -1).astype(np.float16)
    # 열마다 등선(알파가 시작되는 행)과 배선 높이 → 앱에서 조각의 두께를 리그 몸통 두께에 맞추는 데 쓴다
    top = []
    for i in range(crop.shape[1]):
        col = crop[:, i, 3]
        nz = np.where(col > 128)[0]
        top.append(int(nz[0]) if len(nz) else 0)
    meta["torso"] = {"x0": x0, "y0": y0, "size": [crop.shape[1], crop.shape[0]], "top": top,
                     "belly": [float(b - y0) for b in belly]}

    # 머리
    bx0, by0, bx1, by1 = HEAD_BOX
    head = img[by0:by1, bx0:bx1].copy()
    hh, hw_ = head.shape[:2]
    fx = np.clip((np.arange(hw_) / 22.0), 0, 1)[None, :]                       # 왼쪽(목 쪽) 서서히 투명
    fy = np.clip(((hh - 1 - np.arange(hh)) / 22.0), 0, 1)[:, None]             # 아래쪽(가슴 쪽) 서서히 투명
    head[..., 3] *= np.minimum(fx, 1.0) * np.minimum(fy, 1.0)
    Image.fromarray(head.astype(np.uint8), "RGBA").save(OUT / "head.png")
    gx, gy = np.meshgrid(np.arange(bx0, bx1), np.arange(by0, by1))
    uvs["head"] = np.stack([gx / W, gy / H], -1).astype(np.float16)
    meta["head"] = {"anchor": [HEAD_ANCHOR[0] - bx0, HEAD_ANCHOR[1] - by0], "size": [hw_, hh]}

    np.savez_compressed(OUT / "uv.npz", **uvs)
    (OUT / "parts.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    print("부품 저장:", OUT, [p.name for p in sorted(OUT.glob("*.png"))])


if __name__ == "__main__":
    main()
