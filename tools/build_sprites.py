"""잘라 낸 사진 컷(assets/ai)을 앱에서 쓰는 '고양이 그림 모음'(assets/sprites)으로 만든다. (개발용 도구)

하는 일
 1) 크기 맞추기: 동작마다 원본 그림의 확대 정도가 달라서, 같은 고양이로 보이게 '귀 안쪽 분홍색 크기'를 기준으로 배율을 정한다.
    기준은 서 있는 고양이가 뼈대 고양이(서 있을 때 세로 114)와 같은 높이가 되게 한 것. 귀가 안 보이는 동작은 EAR_FIX 로 손으로 보정.
 2) 털색 맞추기: 동작마다 털색이 조금씩 달라서(어떤 건 연하고 어떤 건 진함) 전체 평균 색과 밝기 분포에 맞춘다.
 3) 컷마다 발바닥 높이(맨 아래)와 몸 중심, 머리 꼭대기 위치를 기록 → 걷거나 앉을 때 컷이 바뀌어도 몸이 제자리에 있고 말풍선이 머리 위에 붙는다.
 4) 저장 해상도: 뼈대 단위 1 = STORE 픽셀. (화면에 그릴 때는 앱이 시작할 때 실제 크기로 줄여서 쓴다)

결과: assets/sprites/<이름>/f0.png ...  과  assets/sprites/sprites.json
사용: python tools/build_sprites.py [--chart]     (--chart: 크기 맞춘 결과를 한눈에 보는 그림 preview/sprite_chart.png)
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np
from PIL import Image
from scipy import ndimage as ndi

ROOT = Path(__file__).resolve().parent.parent
AI = ROOT / "assets" / "ai"
OUT = ROOT / "assets" / "sprites"
STORE = 1.6              # 저장 해상도 (뼈대 단위 1 = 1.6 픽셀)
STAND_H = 114.0          # 뼈대 고양이가 서 있을 때 세로 (배율 1)

# 사진 동작 이름(폴더 끝부분) → 앱의 동작 이름
NAMES = {
    "서있기": "stand", "앉기": "sit", "몸 세우고 앉아 갸웃": "sit_tilt", "식빵자세": "loaf",
    # 걷기는 GIF 영상(걷기-3, tools/gif_extract.py 로 만든 17프레임), 종종걸음·살금살금은 다시 받은 그림 "-2" 를 쓴다
    "걷기-3": "walk", "종종걸음-3": "trot", "달리기": "run", "살금살금-2": "sneak", "웅크리기": "crouch",
    "뛰어오르기": "jump_up", "뛰어내리기": "jump_down", "착지": "land", "집어올리기": "hold",
    "잠자기1": "sleep_curl", "잠자기2": "sleep_side", "잠자기3": "sleep_nap", "꾸벅꾸벅 졸기": "sleep_doze",
    "그루밍1": "groom", "그루밍2": "groom_leg", "그루밍3": "scratch_neck", "그루밍4": "groom_face",
    "귀뒤긁기": "scratch", "하품": "yawn", "기지개": "stretch",
    "밥먹기": "eat", "꾹꾹이": "knead", "꼬리가지고놀기": "tail_play", "아이콘발로차기": "swat",
    "털실공1-엉덩이씰룩": "wiggle", "털실공2-덥치기": "hop", "털실공3-툭치기": "bat", "털실공4-끌어안고뒷발킥": "bunny",
    "쓰다듬기": "stroke",
}
# 귀 크기를 직접 정해 주는 동작 (자동으로 재면 귀가 눕거나 가려져서 틀리는 것들)
EAR_FIX = {
    "walk": 21.0, "trot": 21.0, "run": 21.5, "sneak": 21.0, "land": 21.0, "jump_up": 21.0, "jump_down": 21.0,
    "hold": 21.0, "hop": 21.0, "sit_tilt": 27.0, "scratch_neck": 28.0, "sleep_side": 22.0,
    "tail_play": 28.5, "swat": 27.5, "bat": 27.5, "stroke": 24.0, "groom_leg": 26.0, "groom": 26.5, "wiggle": 22.5,
    "bunny": 27.0, "knead": 25.0,
}
STAND_KEY = "stand"
# 머리 크기 보정: 동작마다 머리 높이(귀 끝~턱)를 눈금자로 재서 서 있는 고양이(약 112)에 맞춘 값. 1.0 이면 그대로.
# (귀 크기로 정한 배율은 귀가 눕거나 가려지면 틀려서, 눈으로 잰 머리 높이로 다시 맞춘다)
HEAD_ADJ = {
    "stand": 0.98, "walk": 1.06, "trot": 0.98, "sneak": 1.10, "run": 1.05, "crouch": 1.02, "land": 1.02,
    "jump_up": 1.12, "hold": 1.15, "sit": 0.92, "sit_tilt": 0.90, "loaf": 1.10,
    "scratch": 0.90, "scratch_neck": 0.90, "groom_leg": 0.85, "tail_play": 0.96,
    "eat": 0.92, "knead": 0.97, "hop": 1.08, "bat": 1.08, "bunny": 1.05, "stroke": 1.08,
}
# 컷 사이에 중간 컷을 만드는 동작: 이름 → (컷 하나를 몇 개로 늘릴지, 마지막 컷에서 처음으로 이어지는 반복 동작인가)
INTERP = {
    "walk": (2, True), "trot": (2, True),                  # GIF 에서 만든 걷기·종종걸음도 컷 사이에 중간 컷을 넣어 촘촘하게 한다
    "run": (2, True), "sneak": (3, True),
    "groom": (2, True), "groom_leg": (2, True), "groom_face": (2, True), "scratch": (2, True), "scratch_neck": (2, True),
    "knead": (2, True), "tail_play": (2, True),
    "yawn": (2, False), "stretch": (2, False), "crouch": (2, False), "swat": (2, False), "bat": (2, False),
}


# ---------------------------------------------------------------- 색 변환 (sRGB <-> Lab)
def _srgb_to_lab(rgb):
    c = rgb / 255.0
    c = np.where(c > 0.04045, ((c + 0.055) / 1.055) ** 2.4, c / 12.92)
    m = np.array([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]])
    xyz = c @ m.T / np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16 / 116)
    return np.stack([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])], -1)


def _lab_to_srgb(lab):
    fy = (lab[..., 0] + 16) / 116
    fx, fz = fy + lab[..., 1] / 500, fy - lab[..., 2] / 200
    f = np.stack([fx, fy, fz], -1)
    xyz = np.where(f ** 3 > 0.008856, f ** 3, (f - 16 / 116) / 7.787) * np.array([0.95047, 1.0, 1.08883])
    m = np.linalg.inv(np.array([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]]))
    c = xyz @ m.T
    c = np.where(c > 0.0031308, 1.055 * np.clip(c, 0, None) ** (1 / 2.4) - 0.055, 12.92 * c)
    return np.clip(c * 255.0, 0, 255)


# ---------------------------------------------------------------- 귀 크기
def _hsv(rgb):
    mx, mn = rgb.max(2), rgb.min(2)
    d = mx - mn + 1e-6
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    h = np.zeros_like(mx)
    m = mx == r
    h[m] = ((g - b) / d)[m] % 6
    m = (mx == g) & ~(mx == r)
    h[m] = ((b - r) / d + 2)[m]
    m = (mx == b) & ~(mx == g) & ~(mx == r)
    h[m] = ((r - g) / d + 4)[m]
    return h * 60, d / np.maximum(mx, 1e-6), mx


def ear_size(arr):
    """귀 안쪽 분홍색 덩어리(가장 큰 것)의 크기(√면적). 같은 고양이면 크기에 비례한다. 못 찾으면 None."""
    rgb = arr[..., :3].astype(np.float32) / 255
    al = arr[..., 3] > 200
    h, s, v = _hsv(rgb)
    pink = ndi.binary_opening(al & ((h > 335) | (h < 14)) & (s > 0.18) & (v > 0.5), iterations=1)
    lab, n = ndi.label(pink)
    if not n:
        return None
    return float(np.sqrt(ndi.sum(pink, lab, range(1, n + 1)).max()))


# ---------------------------------------------------------------- 메인
def load_sheets():
    sheets = {}
    for d in sorted(AI.iterdir()):
        meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
        key = NAMES.get(d.name.split("-", 2)[2])            # "5-먹기놀기-털실공1-엉덩이씰룩" → "털실공1-엉덩이씰룩"
        if key is None:
            print("이름을 못 찾음:", d.name)
            continue
        frames = [np.array(Image.open(d / f["file"]).convert("RGBA")) for f in meta["frames"]]
        sheets[key] = frames
    return sheets


def scales(sheets):
    ears = {}
    for k, fr in sheets.items():
        vals = [e for e in (ear_size(a) for a in fr) if e]
        ears[k] = float(np.percentile(vals, 75)) if vals else None
    ears.update(EAR_FIX)
    stand_h = float(np.median([a.shape[0] for a in sheets[STAND_KEY]]))
    f_ref = STAND_H / stand_h                    # 서 있는 컷이 뼈대와 같은 높이가 되는 배율 (원본 픽셀 → 뼈대 단위)
    r_ref = ears[STAND_KEY]
    return {k: f_ref * r_ref / ears[k] for k in sheets}, ears, f_ref


def fur_stats(frames):
    px = []
    for a in frames:
        m = a[..., 3] > 240
        if m.sum():
            px.append(a[..., :3][m].astype(np.float32))
    lab = _srgb_to_lab(np.concatenate(px))
    return lab.mean(0), lab.std(0)


def match_colors(sheets, strength=0.85):
    stats = {k: fur_stats(v) for k, v in sheets.items()}
    ref_mean = np.median([s[0] for s in stats.values()], axis=0)
    ref_std = np.median([s[1] for s in stats.values()], axis=0)
    out = {}
    for k, frames in sheets.items():
        m, s = stats[k]
        ratio = np.clip(ref_std / np.maximum(s, 1e-3), 0.85, 1.2)
        new = []
        for a in frames:
            lab = _srgb_to_lab(a[..., :3].astype(np.float32))
            adj = (lab - m) * ratio + ref_mean
            lab = lab * (1 - strength) + adj * strength
            rgb = _lab_to_srgb(lab)
            b = a.copy()
            b[..., :3] = rgb.astype(np.uint8)
            new.append(b)
        out[k] = new
    return out, ref_mean


def drop_specks(arr, min_frac=0.12):
    """주 덩어리에서 떨어져 있고 작은 조각(발로차기 컷에 들어간 깃털 같은 것)을 지운다."""
    m = arr[..., 3] > 40
    lab, n = ndi.label(ndi.binary_dilation(m, iterations=4))
    if n <= 1:
        return arr
    sizes = ndi.sum(m, lab, range(1, n + 1))
    keep = np.zeros(n + 1, bool)
    keep[1:] = sizes >= sizes.max() * min_frac
    out = arr.copy()
    out[..., 3] = np.where(keep[lab], arr[..., 3], 0)
    return out


def _disk(r):
    y, x = np.ogrid[-r:r + 1, -r:r + 1]
    return (x * x + y * y) <= r * r


def core_size(arr):
    """다리·꼬리 같은 가는 부분을 뺀 몸통의 크기(√면적). AI 그림은 컷마다 고양이 크기가 조금씩 달라서, 컷별 크기 보정에 쓴다."""
    m = arr[..., 3] > 128
    r = max(6, int(0.075 * np.sqrt(m.sum())))
    return float(np.sqrt(ndi.binary_opening(m, structure=_disk(r)).sum()))


# 자세가 크게 바뀌어서(몸이 세로로 서거나 크게 휘어서) 몸통 면적이 컷마다 달라지는 것이 정상인 동작은 컷별 보정을 하지 않는다
NO_FRAME_FIX = {"jump_up", "jump_down", "hold", "stretch", "stroke", "yawn", "bunny", "hop", "eat"}


def frame_factors(key, frames):
    """컷마다 곱해 줄 크기 보정(동작 안에서 몸통 크기를 같게). 한계 -20%~+35%."""
    if key in NO_FRAME_FIX:
        return [1.0] * len(frames)
    cs = np.array([core_size(a) for a in frames])
    med = float(np.median(cs))
    return [float(np.clip(med / c, 0.8, 1.35)) for c in cs]


def torso_x(img):
    """몸통(머리·목·다리·꼬리를 뺀 가슴·배)의 가로 중심. 걸을 때 컷을 겹치는 기준으로 쓴다: 몸통은 걷는 동안 한 줄로 부드럽게 가야 하므로,
    머리나 다리 모양이 바뀌어도 거의 움직이지 않는 이 값에 맞추면 몸이 덜덜 떨리지 않는다."""
    m = np.asarray(img)[..., 3] > 128
    r = max(6, int(0.22 * np.sqrt(m.sum())))
    core = ndi.binary_opening(m, structure=_disk(r))
    xs = np.where(core)[1]
    return float(xs.mean()) if len(xs) > 50 else None


# 걷는 동작: 컷을 몸통 중심에 맞춰 겹친다 (엉덩이 기준보다 몸이 덜 떨린다)
TORSO_ANCHOR = {"walk", "trot", "run", "sneak", "crouch"}


def make_frame(arr, f):
    """배율 f(원본 픽셀→뼈대 단위)를 적용해 저장 크기로 줄이고, 몸 중심·머리 위치를 잰다."""
    im = Image.fromarray(arr, "RGBA")
    k = f * STORE
    w, h = max(1, round(im.width * k)), max(1, round(im.height * k))
    # 알파가 번지지 않게 색을 알파로 미리 곱한 뒤 줄이고 되돌린다
    a = np.array(im).astype(np.float32)
    pm = a.copy()
    pm[..., :3] *= (a[..., 3:4] / 255.0)
    pim = Image.fromarray(np.clip(pm, 0, 255).astype(np.uint8), "RGBA").resize((w, h), Image.LANCZOS)
    p = np.array(pim).astype(np.float32)
    al = np.maximum(p[..., 3:4], 1e-3) / 255.0
    p[..., :3] = np.clip(p[..., :3] / al, 0, 255)
    res = Image.fromarray(p.astype(np.uint8), "RGBA")
    arr2 = np.array(res)
    ys, xs = np.where(arr2[..., 3] > 25)
    if not len(ys):
        return res, w / 2, (w / 2, h)
    # 몸 중심(컷을 겹쳐 놓을 기준점): 다리·꼬리·뻗은 발을 뺀 몸통(굵은 부분)의 아래쪽 35%(엉덩이·배)의 가로 중심.
    # 꼬리가 없는 컷이나 앞발을 뻗은 컷, 몸을 숙인 컷에서도 엉덩이는 그대로 있으므로 컷이 바뀔 때 몸이 앞뒤로 밀리지 않는다.
    m = arr2[..., 3] > 128
    r0 = max(4, int(0.075 * np.sqrt(m.sum())))
    core = ndi.binary_opening(m, structure=_disk(r0))
    cy_, cx_ = np.where(core)
    if len(cy_) > 50:
        top, bot = cy_.min(), cy_.max()
        sel = cy_ >= bot - 0.35 * (bot - top)
        cx = float(cx_[sel].mean())
    else:
        lo = np.percentile(ys, 20)
        cx = float(xs[ys >= lo].mean())
    # 머리 꼭대기: 몸 오른쪽 45% 안에서 가장 높은 점 (고양이는 항상 오른쪽을 본다)
    x0 = xs.min() + 0.55 * (xs.max() - xs.min())
    r = xs >= x0
    i = int(np.argmin(ys[r]))
    head = (float(xs[r][i]), float(ys[r][i]))
    return res, cx, head


# 몸통 크기를 맞추지 않는 동작: 자세 때문에 몸통이 길게 늘어나거나 서 있게 되어 몸통 면적이 달라지는 게 정상인 것
NO_BODY_NORM = {"jump_up", "jump_down", "hold", "stretch"}
BODY_CLAMP = (0.80, 1.25)


def body_factors(sheets, sc, ff_all):
    """동작마다, 다리·꼬리를 뺀 몸통의 크기(√면적)가 서 있는 고양이와 같아지는 배율. (머리 크기만 맞추면 몸이 긴 사진은 몸통이 커 보인다)"""
    cs = {}
    for key, frames in sheets.items():
        v = [core_size(a) * ff_all[key][i] for i, a in enumerate(frames)]
        cs[key] = float(np.median(v)) * sc[key]
    ref = cs[STAND_KEY]
    out = {}
    for key, c in cs.items():
        out[key] = 1.0 if key in NO_BODY_NORM else float(np.clip(ref / c, *BODY_CLAMP))
    return out, cs


def main():
    sheets = load_sheets()
    sc, ears, f_ref = scales(sheets)
    sheets, ref_mean = match_colors(sheets)
    ff_all = {k: frame_factors(k, v) for k, v in sheets.items()}
    body_k, body_cs = body_factors(sheets, sc, ff_all)
    for k, v in sorted(body_k.items(), key=lambda kv: kv[1]):
        if abs(v - 1.0) > 0.03:
            print(f"  몸통 크기 통일: {k} 배율 {v:.2f} (몸통 {body_cs[k]:.0f} → {body_cs[k] * v:.0f})")
    OUT.mkdir(parents=True, exist_ok=True)
    meta = {"store": STORE, "actions": {}}
    chart = []
    total = 0
    for key, frames in sheets.items():
        d = OUT / key
        d.mkdir(exist_ok=True)
        for old in d.glob("f*.png"):
            old.unlink()
        info = []
        tiles = []
        ff = ff_all[key]
        if max(ff) > 1.04 or min(ff) < 0.96:
            print(f"  {key}: 컷별 크기 보정 {[round(x, 2) for x in ff]}")
        imgs, raw = [], []
        for i, a in enumerate(frames):
            img, cx, head = make_frame(drop_specks(a) if key == "swat" else a, sc[key] * body_k[key] * ff[i])
            imgs.append(img)
            raw.append({"cx": cx, "hx": head[0] - cx, "hy": img.height - head[1]})
        if key in TORSO_ANCHOR:
            tx = [torso_x(im) for im in imgs]
            if all(t is not None for t in tx):
                off = float(np.mean([t - r["cx"] for t, r in zip(tx, raw)]))      # 평균 위치는 그대로 두고 컷마다의 흔들림만 없앤다
                spread = max(t - r["cx"] for t, r in zip(tx, raw)) - min(t - r["cx"] for t, r in zip(tx, raw))
                for t, r in zip(tx, raw):
                    new_cx = t - off
                    r["hx"] += r["cx"] - new_cx                                   # 머리 위치는 새 기준점 대비로 다시 잰다
                    r["cx"] = new_cx
                print(f"  {key}: 몸통 중심 기준으로 정렬 (컷마다 흔들림 {spread / STORE:.1f} → 0)")
        orig = len(imgs)
        mult, cyclic = INTERP.get(key, (1, False))
        if mult > 1 and "--no-interp" not in sys.argv:
            import interp_frames
            imgs, raw, skipped = interp_frames.expand(imgs, raw, mult, cyclic)
            print(f"  {key}: 컷 {orig} → {len(imgs)} (중간 컷 만들기, 건너뛴 구간 {skipped})")
        else:
            mult = 1
        for i, (img, r) in enumerate(zip(imgs, raw)):
            img.save(d / f"f{i}.png", optimize=True)
            total += (d / f"f{i}.png").stat().st_size
            info.append({"w": img.width, "h": img.height, "cx": round(r["cx"], 1), "hx": round(r["hx"], 1), "hy": round(r["hy"], 1)})
            tiles.append((img, r["cx"]))
        meta["actions"][key] = {"frames": info, "orig": orig, "mult": mult}
        chart.append((key, tiles))
        w = [f["w"] / STORE for f in info]
        h = [f["h"] / STORE for f in info]
        print(f"{key:13s} 귀 {ears[key]:5.1f}  배율 {sc[key]:.3f}  크기(뼈대 단위) {np.median(w):4.0f} x {np.median(h):4.0f}  컷 {len(frames)}")
    missing = [k for k in NAMES.values() if k not in meta["actions"]]
    if missing:
        raise SystemExit(f"동작이 빠졌습니다(NAMES 와 assets/ai 폴더 이름을 확인): {missing}")
    (OUT / "sprites.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    import frame_gaps                                    # 컷 사이 모양 차이를 재서 sprites.json 에 넣는다 (앱이 차이가 작은 컷끼리만 섞는 데 쓴다)
    frame_gaps.main()
    import eye_marks                                     # 컷마다 눈 위치를 찾아 sprites.json 에 넣는다 (앱이 털색과 상관없이 또렷한 눈을 그리는 데 쓴다)
    eye_marks.main()
    print(f"\n그림 모음 완성: {OUT}  (PNG 합계 {total / 1e6:.1f} MB)")
    if "--chart" in sys.argv:
        draw_chart(chart)


def draw_chart(chart):
    """동작별 첫 컷을 같은 눈금(바닥선 위)에 늘어놓아 크기가 맞는지 한눈에 본다."""
    cols = 6
    cw, chh = 330, 260
    rows = (len(chart) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * cw, rows * chh), (60, 95, 80))
    from PIL import ImageDraw
    dr = ImageDraw.Draw(sheet)
    for n, (key, tiles) in enumerate(chart):
        x0, y0 = (n % cols) * cw, (n // cols) * chh
        base = y0 + chh - 24
        dr.line([(x0, base), (x0 + cw, base)], fill=(200, 200, 200))
        for yy in range(0, 240, 20):                      # 뼈대 단위 20 눈금
            dr.line([(x0, base - yy * STORE * 1.0), (x0 + 6, base - yy * STORE * 1.0)], fill=(200, 200, 200))
        img, cx = tiles[0]
        sheet.paste(img, (int(x0 + cw / 2 - cx * 0.9), int(base - img.height * 0.9)) if False else (int(x0 + cw / 2 - cx), int(base - img.height)), img)
        dr.text((x0 + 4, y0 + 3), key, fill=(255, 255, 255))
    (ROOT / "preview").mkdir(exist_ok=True)
    sheet.save(ROOT / "preview" / "sprite_chart.png")
    print("확인 그림:", ROOT / "preview" / "sprite_chart.png")


if __name__ == "__main__":
    main()
