"""실사 고양이 사진(assets/cat_lying.png)에서 뼈대 고양이에 입힐 '스킨' 조각을 오려낸다.

    python tools/make_skin.py   →  assets/skin/*.png, skin.json

만드는 것:
  head.png            귀를 뺀 머리 (볼에 붙은 어깨 털은 잘라냄)
  ear_near/far.png    움직일 수 있는 귀 두 개 (피벗 = 귀 밑동)
  lid_a/b.png         감은 눈꺼풀 (실제 털 질감 + 음영)
  paw.png             앞발
  fur_body.png        몸통 털 (여러 조각을 불규칙하게 이어 붙이고 줄무늬를 손으로 그려 넣음: 반복 없음)
  fur_leg.png         다리·꼬리 털 (옅은 가로 줄무늬)  / fur_dark.png (먼 쪽 다리)  / fur_cream.png (배·가슴)
사진을 좌우로 뒤집어(고양이가 오른쪽을 보게) 쓴다. 개발용 도구라 Pillow/numpy/scipy 가 필요하다.
"""
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from scipy import ndimage

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "assets" / "cat_lying.png"
OUT = ROOT / "assets" / "skin"

HEAD_SCALE = 0.244            # 사진 1px = 로컬 단위 0.244
SAVE_SCALE = HEAD_SCALE * 2   # 2배 해상도로 저장 (저장된 이미지 1px = 0.5 단위)
HEAD_CENTER = (146, 170)      # 뒤집은 사진의 얼굴 중심 (머리 회전의 기준점)
EYES_ORIG = [(343, 151), (413, 151)]
MOUTH_ORIG = (385, 224)

# 뒤집은 사진 기준 좌표 (확대 격자로 확인한 값)
EAR_NEAR = {"poly": [(46, 108), (46, 62), (58, 28), (78, 13), (103, 21), (127, 44), (137, 64), (134, 96), (110, 110)],
            "pivot": (100, 98)}     # 왼쪽(뒤쪽) 귀
EAR_FAR = {"poly": [(197, 100), (197, 66), (210, 46), (240, 27), (270, 14), (279, 14), (279, 62), (262, 92),
                    (238, 108), (210, 112)],
           "pivot": (224, 98)}      # 오른쪽(앞쪽) 귀
# 턱 영역 (뒤집은 사진 기준): 입술 선(y≈222) 아래 턱 털. 확대 사진으로 확인한 좌표
JAW_POLY = [(147, 222), (177, 221), (207, 222), (211, 231), (203, 244), (177, 251), (151, 244), (143, 232)]
LIP_M = (177, 221.5)
RES = 2                       # 털 질감 해상도 배수 (1 단위 = 2*RES 텍셀). 확대해도 도트가 보이지 않게
RNG = np.random.default_rng(7)


def foreground_alpha(rgb):
    """흰 배경 제거: 가장자리와 이어진 거의 흰색 영역만 배경으로 본다."""
    dist = 255 - rgb.min(axis=2).astype(np.int16)
    cand = dist <= 22
    lab, _ = ndimage.label(cand)
    border = np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))
    bg = np.isin(lab, border[border != 0])
    cand2 = dist <= 62
    lab2, _ = ndimage.label(cand2)
    b2 = np.unique(np.concatenate([lab2[0], lab2[-1], lab2[:, 0], lab2[:, -1]]))
    shadow = np.isin(lab2, b2[b2 != 0]) & ~bg
    bg = bg | (shadow & ndimage.binary_dilation(bg, iterations=6) & (dist <= 62 * 0.6 + 22 * 0.4))
    fg = ndimage.binary_fill_holes(ndimage.binary_opening(~bg, iterations=1))
    lab_fg, n = ndimage.label(fg)
    if n > 1:
        sizes = ndimage.sum(fg, lab_fg, range(1, n + 1))
        fg = lab_fg == (int(np.argmax(sizes)) + 1)
    return ndimage.gaussian_filter(fg.astype(np.float32), 1.0)


def smoothstep(x):
    x = np.clip(x, 0, 1)
    return x * x * (3 - 2 * x)


def poly_mask(shape, poly, blur=0.0):
    img = Image.new("L", (shape[1], shape[0]), 0)
    ImageDraw.Draw(img).polygon([tuple(p) for p in poly], fill=255)
    m = np.asarray(img, np.float32) / 255.0
    return ndimage.gaussian_filter(m, blur) if blur else m


def fill_holes_rgb(rgb, known, sigma=7.0):
    """known(0/1) 밖의 픽셀을 주변 색으로 번지게 채운다 (정규화 컨볼루션)."""
    k = known.astype(np.float32)
    num = np.stack([ndimage.gaussian_filter(rgb[..., c] * k, sigma) for c in range(3)], axis=-1)
    den = ndimage.gaussian_filter(k, sigma)[..., None] + 1e-6
    filled = num / den
    return np.where(known[..., None] > 0.5, rgb, filled)


def save_rgba(arr_rgb, alpha, path, crop=None, resize=None):
    img = Image.fromarray(np.dstack([np.clip(arr_rgb, 0, 255).astype(np.uint8), (np.clip(alpha, 0, 1) * 255).astype(np.uint8)]),
                          "RGBA")
    if crop:
        img = img.crop(crop)
    if resize:
        img = img.resize(resize, Image.LANCZOS)
    img.save(path)
    return img


# ----------------------------------------------------------------------- 털 질감
def quilt(sources, size, n_patch, patch_px, scale, rng):
    """사진 털 조각들을 무작위로 겹쳐 붙여(가장자리 부드럽게) 반복 없는 질감을 만든다."""
    W, H = size
    canvas = np.zeros((H, W, 3), np.float32)
    weight = np.zeros((H, W), np.float32)
    for _ in range(n_patch):
        src = sources[rng.integers(len(sources))]
        s = int(patch_px * rng.uniform(0.8, 1.25))
        sx = rng.integers(0, src.shape[1] - s)
        sy = rng.integers(0, src.shape[0] - s)
        patch = src[sy:sy + s, sx:sx + s]
        if rng.random() < 0.5:
            patch = patch[:, ::-1]
        if rng.random() < 0.5:
            patch = patch[::-1]
        if rng.random() < 0.5:
            patch = np.rot90(patch)
        pw = max(8, int(round(s * scale)))
        patch = np.asarray(Image.fromarray(np.ascontiguousarray(patch).astype(np.uint8)).resize((pw, pw), Image.LANCZOS),
                           np.float32)
        yy, xx = np.mgrid[0:pw, 0:pw]
        # 가장자리에서 0 으로 떨어지는 Hann 창 → 조각 경계가 보이지 않고 부드럽게 섞인다
        win = (np.sin(np.pi * (xx + 0.5) / pw) * np.sin(np.pi * (yy + 0.5) / pw)) ** 2
        x0 = int(rng.integers(-pw // 2, W - pw // 2))
        y0 = int(rng.integers(-pw // 2, H - pw // 2))
        xa, ya = max(0, x0), max(0, y0)
        xb, yb = min(W, x0 + pw), min(H, y0 + pw)
        if xb <= xa or yb <= ya:
            continue
        pwin = win[ya - y0:yb - y0, xa - x0:xb - x0]
        canvas[ya:yb, xa:xb] += patch[ya - y0:yb - y0, xa - x0:xb - x0] * pwin[..., None]
        weight[ya:yb, xa:xb] += pwin
    out = canvas / np.maximum(weight, 1e-3)[..., None]
    hole = weight < 0.02                                    # 아주 드물게 남는 빈 픽셀은 평균색으로 메움
    if hole.any():
        out[hole] = np.median(out[~hole].reshape(-1, 3), axis=0)
    return out


def add_hair(img, rng, density=0.17 / (RES * RES), length=(7 * RES, 16 * RES), spread=36, alpha=(0.20, 0.42), width=2 * RES - 1):
    """털 가닥을 촘촘하게 얹는다. 질감 1px 가 화면에서 0.5 단위라, 가닥 굵기를 2px(=1 단위)로 해야 실제 크기에서도 보인다.
    각 가닥은 그 자리의 털 색을 밝게/어둡게 바꾼 색이라 자연스럽게 섞인다."""
    H, W = img.shape[:2]
    layer = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)).convert("RGBA")
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    dr = ImageDraw.Draw(ov)
    for _ in range(int(W * H * density)):
        x, y = rng.uniform(0, W), rng.uniform(0, H)
        ang = np.radians(90 + rng.uniform(-spread, spread))           # 대체로 위아래 방향 (털이 자란 방향)
        ln = rng.uniform(*length)
        base = img[int(y) % H, int(x) % W]
        k = rng.choice((1.30, 1.15, 0.84, 0.70), p=(0.3, 0.25, 0.25, 0.2))
        col = tuple(int(min(255, c * k)) for c in base)
        a = int(255 * rng.uniform(*alpha))
        x2, y2 = x + ln * np.cos(ang), y + ln * np.sin(ang)
        # 털끝은 가늘어지게: 굵은 선 + 끝쪽 가는 선
        mx, my = (x + x2) / 2, (y + y2) / 2
        dr.line((x, y, mx, my), fill=col + (a,), width=width)
        dr.line((mx, my, x2, y2), fill=col + (int(a * 0.8),), width=1)
    return np.asarray(Image.alpha_composite(layer, ov).convert("RGB"), np.float32)


def boost(img, k):
    """평균을 기준으로 밝고 어두운 차이를 k 배로 키운다 (머리 사진처럼 털 결과 무늬가 또렷하게)."""
    mean = img.reshape(-1, 3).mean(axis=0)
    return np.clip(mean + (img - mean) * k, 0, 255)


def paint_tabby(img, dark, rng):
    """자연스러운 얼룩(태비) 무늬: 등 쪽이 가장 짙고 배로 갈수록 옅어지며, 줄은 끊어지고 굵기·간격이 제각각이고,
    줄 사이사이에 번진 점 얼룩이 섞인다. 호랑이처럼 균일하고 긴 줄을 만들지 않는다."""
    H, W = img.shape[:2]
    stripes = Image.new("L", (W, H), 0)
    dr = ImageDraw.Draw(stripes)
    x = rng.uniform(0, 30 * RES)
    while x < W + 30:
        xc = x + rng.uniform(-6, 6) * RES
        nseg = int(rng.choice((1, 2, 2, 3)))
        y0 = -4 * RES
        for _ in range(nseg):                                           # 한 줄을 여러 토막으로 끊는다
            ln = H * rng.uniform(0.12, 0.30)
            w0 = rng.uniform(6, 13) * RES
            wob = rng.uniform(2, 6) * RES
            ph = rng.uniform(0, 6.28)
            lean = rng.uniform(-0.3, 0.3)
            L, R = [], []
            for k in range(0, 13):
                u = k / 12
                y = y0 + u * ln
                cx = xc + wob * np.sin(ph + u * 4.0) + lean * (y - y0)
                w = w0 * (np.sin(np.pi * u) ** 0.7) * (0.8 + 0.2 * np.sin(u * 7 + ph)) + 0.8 * RES   # 양 끝이 가늘다
                L.append((cx - w / 2, y))
                R.append((cx + w / 2, y))
            dr.polygon(L + R[::-1], fill=255)
            y0 += ln + H * rng.uniform(0.04, 0.12)
            xc += lean * ln * 0.4
            if y0 > H * 0.7:
                break
        x += rng.uniform(26, 58) * RES
    stripes = stripes.filter(ImageFilter.GaussianBlur(3.4 * RES))
    a = np.asarray(stripes, np.float32) / 255.0
    # 등 쪽이 가장 짙고, 배 쪽으로 갈수록 옅어진다
    fall = np.clip(1.15 - np.linspace(0, 1, H)[:, None] * 1.0, 0.25, 1.0)
    a = a * fall

    spots = Image.new("L", (W, H), 0)
    sd = ImageDraw.Draw(spots)
    for _ in range(int(W * H / (RES * RES) / 900)):                    # 번진 점 얼룩
        cx, cy = rng.uniform(0, W), rng.uniform(0, H * 0.8)
        r = rng.uniform(2.5, 7) * RES
        sd.ellipse((cx - r * rng.uniform(0.7, 1.4), cy - r, cx + r * rng.uniform(0.7, 1.4), cy + r),
                   fill=int(rng.uniform(80, 200)))
    spots = spots.filter(ImageFilter.GaussianBlur(2.4 * RES))
    b = np.asarray(spots, np.float32) / 255.0 * 0.5 * fall

    mask = np.clip(a * 0.62 + b, 0, 0.85)[..., None]
    detail = ndimage.gaussian_filter(0.85 + 0.3 * rng.random((H, W, 1)).astype(np.float32), (0.8, 0.8, 0))
    return img * (1 - mask) + (np.array(dark, np.float32) * detail) * mask


def paint_stripes(img, dark, rng, spacing=(24 * RES, 40 * RES), width=(11 * RES, 20 * RES), length=(0.5, 0.85), alpha=0.82):
    """등에서 배 쪽으로 내려오는 불규칙한 호랑이 줄무늬(굵기·간격·기울기·길이가 제각각)를 그려 넣는다."""
    H, W = img.shape[:2]
    layer = Image.new("L", (W, H), 0)
    dr = ImageDraw.Draw(layer)
    x = rng.uniform(0, spacing[1])
    while x < W + 30:
        for _ in range(1 if rng.random() > 0.25 else 2):             # 가끔 두 갈래
            xc = x + rng.uniform(-4, 4) * RES
            ln = H * rng.uniform(*length)
            w0 = rng.uniform(*width)
            wob = rng.uniform(1.5, 5.0) * RES
            ph = rng.uniform(0, 6.28)
            lean = rng.uniform(-0.18, 0.18)
            left, right = [], []
            for k in range(0, 21):
                u = k / 20
                y = -4 * RES + u * (ln + 4 * RES)
                cx = xc + wob * np.sin(ph + u * 5.0) + lean * y
                w = w0 * (1 - u ** 1.4) * (0.75 + 0.25 * np.sin(u * 9 + ph)) + 0.6 * RES
                left.append((cx - w / 2, y))
                right.append((cx + w / 2, y))
            dr.polygon(left + right[::-1], fill=255)
        x += rng.uniform(*spacing)
    layer = layer.filter(ImageFilter.GaussianBlur(2.6 * RES))                 # 번지듯 부드러운 경계
    a = (np.asarray(layer, np.float32) / 255.0)[..., None] * alpha
    # 줄무늬 안쪽이 완전한 평면이 되지 않도록 털결 질감을 곱한다
    detail = 0.85 + 0.3 * rng.random((H, W, 1)).astype(np.float32)
    detail = ndimage.gaussian_filter(detail, (0.8, 0.8, 0))
    return img * (1 - a) + (np.array(dark, np.float32) * detail) * a


def paint_rings(img, dark, rng, period=17 * RES, alpha=0.55):
    H, W = img.shape[:2]
    layer = Image.new("L", (W, H), 0)
    dr = ImageDraw.Draw(layer)
    y = rng.uniform(0, period)
    while y < H:
        t = rng.uniform(3, 6) * RES
        pts = [(x, y + 2.5 * RES * np.sin(x / (11 * RES) + y)) for x in range(0, W + 8 * RES, 8 * RES)]
        dr.line(pts, fill=255, width=int(t))
        y += period * rng.uniform(0.8, 1.25)
    layer = layer.filter(ImageFilter.GaussianBlur(1.8 * RES))
    a = (np.asarray(layer, np.float32) / 255.0)[..., None] * alpha
    return img * (1 - a) + np.array(dark, np.float32) * a


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    src = Image.open(SRC).convert("RGB")
    W, H = src.size
    rgb = np.asarray(src)
    alpha = foreground_alpha(rgb)
    mir = np.ascontiguousarray(rgb[:, ::-1]).astype(np.float32)
    malpha = np.ascontiguousarray(alpha[:, ::-1])
    mx = lambda x: W - x
    yy, xx = np.mgrid[0:H, 0:W]
    cx, cy = HEAD_CENTER
    info = {}

    # ===================================================== 머리 (귀 제외) + 귀 2개
    box = (36, 8, 280, 256)
    # 볼: 오른쪽(주둥이 쪽)은 사진에서 어깨 털이 붙어 있던 곳이라 더 안쪽에서 자른다
    rx = np.where(xx > cx, 90.0, 104.0)
    ell = (((xx - cx) / rx) ** 2 + ((yy - (cy - 2)) / 92.0) ** 2) <= 1.0
    # 턱선: 볼이 가장 넓은 높이(y≈170) 아래로는 윤곽이 안쪽으로 모여 턱으로 이어진다.
    # 타원만 쓰면 볼 아래에 사진 속 목·어깨 털이 불룩하게 딸려 들어오므로, 턱선 밖은 잘라낸다.
    x_left = 46 + 70 * smoothstep((yy - 175) / 75.0)
    x_right = 240 - 55 * smoothstep((yy - 190) / 60.0)
    jaw_line = (xx >= x_left) & (xx <= x_right)
    top_zone = (yy < 118) & (xx > box[0]) & (xx < box[2])
    zone = ndimage.gaussian_filter(((ell & jaw_line) | top_zone).astype(np.float32), 3.5)
    fade = 1.0 - smoothstep((yy - 224) / 30.0)
    head_alpha = malpha * zone * fade

    ear_info = {}
    hole_total = np.zeros_like(head_alpha)
    ear_masks = {}
    for name, e in (("near", EAR_NEAR), ("far", EAR_FAR)):
        m = poly_mask(head_alpha.shape, e["poly"], blur=1.2)
        ear_masks[name] = m
        px, py = e["pivot"]
        above = (yy < py + 3).astype(np.float32)
        hole_total = np.maximum(hole_total, (poly_mask(head_alpha.shape, e["poly"]) > 0.5) * above)
    # 귀가 빠진 자리: 귀 밑동 14px 띠만 주변 털색으로 채워 두고(귀가 눕거나 돌아가도 틈이 안 보이게), 나머지는 투명
    known = (head_alpha > 0.5) & (hole_total < 0.5)
    filled_rgb = fill_holes_rgb(mir, known.astype(np.float32), 7.0)
    band = np.zeros_like(head_alpha)
    for e in (EAR_NEAR, EAR_FAR):
        px, py = e["pivot"]
        poly = poly_mask(head_alpha.shape, e["poly"]) > 0.5
        band = np.maximum(band, poly * (yy >= py - 14) * (yy < py + 3))
    band = band * (malpha > 0.5)                              # 귀 실루엣 안쪽만 (배경으로 번지지 않게)
    head_rgb = np.where(hole_total[..., None] > 0.5, filled_rgb, mir)
    head_a = np.where(hole_total > 0.5, ndimage.gaussian_filter(band, 0.8), head_alpha)
    head_a = np.where((hole_total > 0.5) & (band < 0.5), 0.0, head_a)

    # ---- 턱: 입술 선(y≈222) 아래 턱 부분을 따로 오려 둔다. 입을 벌리면 이 조각이 내려가고 그 틈으로 입속이 보인다.
    #      (쉴 때는 머리+턱 두 장의 알파를 합치면 원래와 같으므로 이음새가 없다)
    jm = poly_mask(head_a.shape, JAW_POLY, blur=0.9)
    jaw_a = head_a * jm
    head_a = head_a * (1.0 - jm)
    jys, jxs = np.where(jm > 0.02)
    jb = (max(0, jxs.min() - 2), max(0, jys.min() - 2), min(W, jxs.max() + 3), min(H, jys.max() + 3))
    jsz = (round((jb[2] - jb[0]) * SAVE_SCALE), round((jb[3] - jb[1]) * SAVE_SCALE))
    save_rgba(head_rgb, jaw_a, OUT / "jaw.png", crop=jb, resize=jsz)

    ax, ay = cx - box[0], cy - box[1]
    size_px = (round((box[2] - box[0]) * SAVE_SCALE), round((box[3] - box[1]) * SAVE_SCALE))
    save_rgba(head_rgb, head_a, OUT / "head.png", crop=box, resize=size_px)
    info["head"] = {"size": list(size_px), "anchor": [ax * SAVE_SCALE, ay * SAVE_SCALE], "scale": HEAD_SCALE / SAVE_SCALE}

    to_units = lambda x, y: ((x - cx) * HEAD_SCALE, (y - cy) * HEAD_SCALE)
    jx0, jy0 = to_units(jb[0], jb[1])
    info["jaw"] = {"file": "jaw", "rect": [jx0, jy0, (jb[2] - jb[0]) * HEAD_SCALE, (jb[3] - jb[1]) * HEAD_SCALE]}
    info["lip"] = to_units(*LIP_M)                    # 윗입술 선 위의 입 중심 (코 바로 아래)
    for name, e in (("near", EAR_NEAR), ("far", EAR_FAR)):
        m = ear_masks[name]
        a = malpha * m
        ys, xs = np.where(a > 0.02)
        b = (max(0, xs.min() - 2), max(0, ys.min() - 2), min(W, xs.max() + 3), min(H, ys.max() + 3))
        sz = (round((b[2] - b[0]) * SAVE_SCALE), round((b[3] - b[1]) * SAVE_SCALE))
        save_rgba(mir, a, OUT / f"ear_{name}.png", crop=b, resize=sz)
        ux0, uy0 = to_units(b[0], b[1])
        px, py = to_units(*e["pivot"])
        ear_info[name] = {"file": f"ear_{name}", "pivot": [px, py], "rect": [ux0, uy0, (b[2] - b[0]) * HEAD_SCALE,
                                                                       (b[3] - b[1]) * HEAD_SCALE]}
    info["ears"] = ear_info

    # ===================================================== 털 재료 (몸통 안쪽 저대비 조각) + 색 맞춤
    gray = mir.mean(axis=2)
    hm = (((xx - cx) / 90.0) ** 2 + ((yy - (cy - 20)) / 60.0) ** 2 <= 1.0) & (malpha > 0.98)
    hm &= (gray > 85) & (gray < 175)
    head_med = np.median(mir[hm], axis=0)
    flank = np.ascontiguousarray(rgb[196:292, 196:335]).astype(np.float32)          # 등/옆구리 (원본 좌표)
    shift = head_med - np.median(flank.reshape(-1, 3), axis=0)
    flank_adj = np.clip(flank + shift * 0.95, 0, 255)
    sources = [flank_adj]
    print("head fur tone", head_med.astype(int), "flank shift", shift.astype(int))

    dark = np.array([62, 42, 28], np.float32)                                         # 줄무늬 색 (머리 줄무늬와 비슷)
    # 몸통: 480x240px (= 240x120 단위, 몸 전체를 한 장으로 덮어 타일 반복이 없다)
    body = quilt(sources, (480 * RES, 240 * RES), n_patch=1500 * RES * RES, patch_px=48, scale=0.5 * RES, rng=RNG)
    body = paint_tabby(boost(body, 2.1), dark, RNG)
    body = add_hair(body, RNG)
    head_mean = head_rgb[head_a > 0.9].mean(axis=0)                    # 머리 사진의 평균 털색
    body = body + (head_mean - body.reshape(-1, 3).mean(axis=0)) * 0.9  # 몸통 밝기·색을 머리에 맞춤 (무늬의 명암 차이는 그대로)
    Image.fromarray(np.clip(body, 0, 255).astype(np.uint8)).save(OUT / "fur_body.png")
    # 다리·꼬리: 가로 고리무늬
    leg = quilt(sources, (192 * RES, 192 * RES), n_patch=520 * RES * RES, patch_px=40, scale=0.5 * RES, rng=RNG)
    leg = paint_rings(boost(leg, 2.3), dark, RNG)
    leg = add_hair(leg, RNG)
    leg = leg + (head_mean - leg.reshape(-1, 3).mean(axis=0)) * 0.9
    Image.fromarray(np.clip(leg, 0, 255).astype(np.uint8)).save(OUT / "fur_leg.png")
    Image.fromarray(np.clip(leg * 0.74, 0, 255).astype(np.uint8)).save(OUT / "fur_dark.png")
    # 꼬리: 머리 털색과 평균이 같고, 고리무늬는 옅은 갈색 (몸통보다 짙지 않게)
    tailtex = boost(quilt(sources, (192 * RES, 192 * RES), n_patch=520 * RES * RES, patch_px=40, scale=0.5 * RES, rng=RNG), 1.5)
    tailtex = tailtex + (head_med - tailtex.reshape(-1, 3).mean(axis=0))
    tailtex = paint_rings(tailtex, np.array([112, 82, 58], np.float32), RNG, alpha=0.30)
    tailtex = add_hair(tailtex, RNG)
    Image.fromarray(np.clip(tailtex, 0, 255).astype(np.uint8)).save(OUT / "fur_tail.png")
    # 배·가슴: 얼굴의 흰 털(머리 사진에서 가장 밝은 상위 8%)과 같은 색으로 맞춘다. 털결 명암은 약하게 남겨 평평해 보이지 않게 한다
    hl = head_rgb.mean(axis=2)
    hmask = (head_a > 0.9) & (hl >= np.percentile(hl[head_a > 0.9], 92))
    cream = head_rgb[hmask].mean(axis=0).astype(np.float32)
    print("face white fur", cream.astype(int))
    cr = add_hair(quilt(sources, (320 * RES, 200 * RES), n_patch=700 * RES * RES, patch_px=40, scale=0.5 * RES, rng=RNG), RNG, density=0.012 / (RES * RES))
    cr = boost(cr, 1.0)
    cr = cream + (cr - cr.reshape(-1, 3).mean(axis=0)) * 0.35
    Image.fromarray(np.clip(cr, 0, 255).astype(np.uint8)).save(OUT / "fur_cream.png")

    # ===================================================== 감은 눈꺼풀: 털 질감 + 음영, 가장자리는 부드럽게
    lid_rx, lid_ry = 4.9, 3.3                                                      # 단위 (사진 속 눈 크기에 맞춤)
    lw, lh = round(lid_rx * 2 / 0.5), round(lid_ry * 2 / 0.5)
    eyes_m = [(mx(x), y) for x, y in EYES_ORIG]
    lids = []
    # 눈꺼풀 질감은 눈 바로 위(눈썹뼈) 털에서 가져온다: 눈 주변 피부와 결·색이 같다
    brow = [mir[96:128, 112:172], mir[98:130, 172:236]]
    for i, name in enumerate(("a", "b")):
        patch = quilt(brow, (lw, lh), n_patch=40, patch_px=18, scale=0.5 * 1.35, rng=RNG)
        gy = np.linspace(0, 1, lh)[:, None, None]
        shade = 0.88 + 0.16 * np.sin(np.pi * np.clip(gy * 1.05, 0, 1)) - 0.06 * gy        # 윗눈꺼풀 주름: 위·아래는 살짝 어둡고 가운데가 밝게
        patch = patch * shade
        yy2, xx2 = np.mgrid[0:lh, 0:lw]
        e = (((xx2 - lw / 2 + 0.5) / (lw / 2 - 1)) ** 2 + ((yy2 - lh / 2 + 0.5) / (lh / 2 - 1)) ** 2)
        a = 1.0 - smoothstep((e - 0.30) / 0.70)                                           # 가장자리 페더 (주변 털로 서서히 이어짐)
        save_rgba(patch, a, OUT / f"lid_{name}.png")
        lids.append(f"lid_{name}")
    info["lids"] = lids
    info["lid_size"] = [lid_rx * 2, lid_ry * 2]
    info["eyes"] = [to_units(*e) for e in eyes_m]
    info["mouth"] = to_units(mx(MOUTH_ORIG[0]), MOUTH_ORIG[1])

    # ===================================================== 앞발
    px0, py0, px1, py1 = 386, 346, 468, 398
    pal = np.zeros((H, W), np.float32)
    pal[py0:py1, px0:px1] = alpha[py0:py1, px0:px1]
    pe = (((xx - (px0 + px1) / 2) / 40.0) ** 2 + ((yy - (py0 + py1) / 2 - 1) / 25.0) ** 2) <= 1.0
    pmask = ndimage.gaussian_filter(pe.astype(np.float32), 2.5) * pal
    paw = save_rgba(rgb.astype(np.float32), pmask, OUT / "paw_tmp.png", crop=(px0, py0, px1, py1))
    paw.transpose(Image.FLIP_LEFT_RIGHT).resize((44, 28), Image.LANCZOS).save(OUT / "paw.png")
    (OUT / "paw_tmp.png").unlink()

    tail = rgb[175:292, 18:130].reshape(-1, 3)
    lum = tail.sum(axis=1)
    info["tail_dark"] = [int(v) for v in np.median(tail[lum <= np.percentile(lum, 12)], axis=0)]
    info["head_mean"] = [int(v) for v in head_mean]
    info["paw_size"] = [18.0, 11.5]
    info["fur_scale"] = 0.5 / RES
    info["eye_rx"], info["eye_ry"] = 4.6, 3.5
    (OUT / "skin.json").write_text(json.dumps(info, indent=1), encoding="utf-8")
    # 이전 버전 잔재 정리
    for old in ("fur.png",):
        (OUT / old).unlink(missing_ok=True)
    print("saved to", OUT)


if __name__ == "__main__":
    main()
