"""AI(나노 바나나)가 만든 동작 그림(한 장에 고양이 6컷 안팎, 흰 배경)을 컷별 투명 배경 그림으로 만든다. (개발용 도구 - 앱에는 들어가지 않음)

입력:  preview/ai_motions/*.png
출력:  assets/ai/<동작이름>/f0.png ~ fN.png  (투명 배경, 고양이만 꼭 맞게 자름)
       assets/ai/<동작이름>/meta.json
       preview/ai_cut/<동작이름>.png          (잘린 결과 확인용: 자홍색 배경 위에 올려서 남은 흰 테두리가 잘 보이게 함)

배경 지우는 방법 (흰색에 가까우면 지우는 단순 방식은 연한 털까지 지워서 쓰지 않음):
 ① 확실한 배경 = '완전히 흰색'이면서 넓게 이어진 영역 + 칸을 나누는 아주 길고 가는 선 + 바닥의 옅은 회색 그림자
 ② 확실한 배경 바로 옆 몇 칸(경계띠)에서만, 고양이 털색을 이웃 안쪽에서 찾아 '흰색이 섞인 만큼'을 투명도로 계산 (알파 매팅)
 ③ 경계는 1칸 안쪽으로 줄이고 살짝 블러해서 실선 느낌과 흰 테두리를 없앰
"""
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage as ndi

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "preview" / "ai_motions"
OUT = ROOT / "assets" / "ai"
SHOW = ROOT / "preview" / "ai_cut"

BAND = 4.0          # 경계띠 폭(칸): 배경에서 이만큼 안쪽까지만 투명도를 계산한다
FEATHER = 0.9       # 경계 블러 세기


def _edge_labels(lab):
    e = np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))
    return e[e > 0]


def _long_lines(mask: np.ndarray, length: int = 140, thick: int = 7) -> np.ndarray:
    """아주 길고 가는 가로/세로 선(칸 구분선)만 골라낸다. 고양이 털/수염은 이렇게 길고 곧지 않다."""
    h = ndi.binary_opening(mask, structure=np.ones((1, length))) & ~ndi.binary_opening(mask, structure=np.ones((thick, length)))
    v = ndi.binary_opening(mask, structure=np.ones((length, 1))) & ~ndi.binary_opening(mask, structure=np.ones((length, thick)))
    return ndi.binary_dilation(h | v, iterations=2)


def sure_background(rgb: np.ndarray, with_edges: bool = False):
    """확실한 배경(True). with_edges=True 이면 (배경, 칸 선/테두리 자리)를 돌려준다."""
    c = rgb.astype(np.int16)
    mx, mn = c.max(2), c.min(2)
    pure = (mn >= 244) & ((mx - mn) <= 10)                      # 완전히 흰색 (연한 털은 이보다 색이 있어서 남는다)
    neutral = (mx - mn) <= 12
    lines = _long_lines(neutral & (mn < 240))                   # 칸 구분선 (검정/회색)
    dark = (mx < 110) & ((mx - mn) < 22)
    lab_d, _ = ndi.label(dark & ~lines)
    frame = np.isin(lab_d, _edge_labels(lab_d))                 # 가장자리에 붙은 둥근 검은 테두리
    # 길쭉하고 속이 빈 검은/회색 덩어리(굵은 칸 선, 둥근 테두리 조각)도 선으로 본다
    lab_g, ng = ndi.label((mx < 90) & ((mx - mn) < 12))     # 진짜 검은 선만 (털 줄무늬는 갈색 기운이 있음)
    long_line = np.zeros(ng + 1, bool)
    for k, sl in enumerate(ndi.find_objects(lab_g), 1):
        h, w = sl[0].stop - sl[0].start, sl[1].stop - sl[1].start
        area = (lab_g[sl] == k).sum()
        if max(h, w) >= 100 and area / float(h * w) < 0.2 and (area / float(max(h, w)) <= 18 or area / float(h * w) < 0.06):     # 길고 가늘고 속이 빈 것만
            long_line[k] = True
    long_line = ndi.binary_dilation(long_line[lab_g], iterations=2)
    cand = pure | lines | frame | long_line
    lab, n = ndi.label(cand)
    sizes = ndi.sum(cand, lab, range(1, n + 1))
    keep = np.zeros(n + 1, bool)
    keep[1:] = sizes >= 150                                     # 작은 흰 점(흰 털)은 배경으로 안 봄
    keep[_edge_labels(lab)] = True
    bg = keep[lab]
    # 다리 사이/배 밑에 갇힌 작은 흰 조각, 떨어져 남은 옅은 회색 그림자 조각: 색이 없는(무채색) 밝은 덩어리는 작아도 배경으로
    lum = c.mean(2).astype(np.float32)
    m1 = ndi.uniform_filter(lum, 5)
    smooth = np.sqrt(np.maximum(ndi.uniform_filter(lum * lum, 5) - m1 * m1, 0)) < 2.2     # 배경은 균일, 털은 결이 있음
    flat_white = (mn >= 249) & ((mx - mn) <= 5)                # 거의 순백: 흰 털은 이 정도로 완전히 균일하지 않다
    leftover = (((pure) | ((mn > 165) & ((mx - mn) <= 12))) & smooth | flat_white) & ~bg
    lab_l, nl = ndi.label(leftover)
    if nl:
        ls = ndi.sum(leftover, lab_l, range(1, nl + 1))
        lk = np.zeros(nl + 1, bool)
        lk[1:] = ls >= 12
        bg = bg | lk[lab_l]
    # 바닥 그림자: 배경과 이어진 옅은 회색(색이 없음)만 번져서 배경으로
    shadow = (mn > 130) & ((mx - mn) <= 14)
    grow = bg.copy()
    for _ in range(70):
        nxt = ndi.binary_dilation(grow) & (shadow | bg)
        if (nxt == grow).all():
            break
        grow = nxt
    if with_edges:
        return grow, (lines | frame | long_line)
    return grow


def is_checker(rgb: np.ndarray) -> bool:
    """배경에 '투명 표시용 체크무늬'(흰색과 회색 사각형)가 그려져 있는지: 완전한 흰색과 중간 회색(185~235)의 무채색 픽셀이 둘 다 많으면 체크무늬."""
    c = rgb.astype(np.int16)
    neutral = (c.max(2) - c.min(2)) <= 5
    white = neutral & (c.min(2) >= 250)
    gray = neutral & (c.min(2) >= 185) & (c.min(2) <= 235)
    return gray.mean() > 0.04 and white.mean() > 0.10


def checker_background(rgb: np.ndarray) -> np.ndarray:
    """체크무늬(흰·회색 사각형)와 바닥 그림자를 배경(True)으로. 고양이 털은 색이 있어서(채도) 남는다."""
    c = rgb.astype(np.int16)
    lum = c.mean(2)
    neutral = (c.max(2) - c.min(2)) <= 7
    seed = neutral & (lum > 110)
    lab, n = ndi.label(seed, structure=np.ones((3, 3)))
    sizes = ndi.sum(seed, lab, range(1, n + 1))
    keep = np.zeros(n + 1, bool)
    border = np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))
    keep[border[border > 0]] = True                              # 가장자리와 이어진 체크무늬
    for k, sl in enumerate(ndi.find_objects(lab), 1):            # 다리 사이에 갇힌 사각형(가장자리와 안 이어짐): 반듯한 사각형이면 체크무늬
        if keep[k] or sizes[k - 1] < 120:
            continue
        h, w = sl[0].stop - sl[0].start, sl[1].stop - sl[1].start
        if sizes[k - 1] / float(h * w) > 0.88:
            keep[k] = True
    bg = keep[lab]
    # 칸을 나누는 검은 선(길고 가는 가로/세로 선)도 배경으로
    dark = neutral & (lum <= 110)
    bg = bg | _long_lines(dark, length=140, thick=9)
    # 그림자: 배경과 이어진 옅은 무채색 번짐(밝기 110 이상)을 배경으로
    soft = (c.max(2) - c.min(2) <= 12) & (lum > 110)
    grow = bg.copy()
    for _ in range(80):
        nxt = ndi.binary_dilation(grow) & (soft | grow)
        if (nxt == grow).all():
            break
        grow = nxt
    return grow


def matte(rgb: np.ndarray, floor_frac: float = 0.14, floor_sat: float = 0.13, floor_mn: int = 175, checker: bool = False):
    """배경을 지우고 (알파 0~1, 색, 고양이 영역)을 돌려준다."""
    c = rgb.astype(np.float32)
    bg = checker_background(rgb) if checker else sure_background(rgb)
    # 작은 구멍은 메꾼다 (고양이 안쪽 흰 털)
    # 바닥 정리: 고양이 키의 맨 아래 14% 구간에서, 이미 배경인 곳과 이어진 밝고 색 없는 부분(바닥에 비친 그림자/흰 번짐)을 배경으로
    mxs, mns = c.max(2), c.min(2)
    sat = (mxs - mns) / np.maximum(mxs, 1)
    grp, ng = ndi.label(ndi.binary_dilation(~bg, iterations=12))
    zone = np.zeros(bg.shape, bool)
    for gi, sl in enumerate(ndi.find_objects(grp), 1):
        top, bot = sl[0].start, sl[0].stop
        zone[max(top, int(bot - floor_frac * (bot - top))):bot, sl[1]] = True
    floor_ok = zone & (mns > floor_mn) & (sat < floor_sat) & (not checker)       # (체크무늬 그림은 위에서 그림자까지 지웠다)
    grow = bg.copy()
    for _ in range(60):
        nxt = ndi.binary_dilation(grow) & (floor_ok | grow)
        if (nxt == grow).all():
            break
        grow = nxt
    bg = grow
    fg0 = ~bg
    holes = ndi.binary_fill_holes(fg0) & ~fg0                   # 고양이에 둘러싸인 빈 곳
    lab_h, nh = ndi.label(holes)
    if nh:
        hs = ndi.sum(holes, lab_h, range(1, nh + 1))
        hk = np.zeros(nh + 1, bool)
        hk[1:] = hs < 60                                        # 아주 작은 것(흰 털 점)만 메우고, 다리 사이 틈 같은 큰 빈 곳은 비워 둠
        fg0 = fg0 | hk[lab_h]
    # 아주 작은 조각(먼지)은 지운다
    lab, n = ndi.label(fg0)
    if n:
        sz = ndi.sum(fg0, lab, range(1, n + 1))
        k = np.zeros(n + 1, bool)
        k[1:] = sz >= 500
        fg0 = k[lab]
    bg = ~fg0

    # 확실한 고양이 색: 흰색에서 충분히 멀거나 색이 있는 픽셀
    dist_bg, bidx = ndi.distance_transform_edt(~bg, return_indices=True)       # 배경까지의 거리, 가장 가까운 배경 픽셀
    B = c[bidx[0], bidx[1]] if checker else np.full_like(c, 255.0)              # 가장 가까운 배경 색(체크무늬는 흰색/회색이 섞여 있음)
    d = B - c                                                   # 배경색까지의 거리(채널별)
    dist_w = np.sqrt((d ** 2).sum(2))
    sure_fg = fg0 & (dist_w > 95)
    # 원본이 흐릿할수록(경계 밝기 변화가 완만할수록) 경계띠를 넓히고 블러를 키운다 (해상도 낮은 그림이 딱딱하게 잘리는 것 방지)
    lum = c.mean(2)
    gy, gx = np.gradient(ndi.gaussian_filter(lum, 0.5))
    gmag = np.hypot(gx, gy)
    eband = fg0 & (dist_bg <= 3)
    sharp = float(np.percentile(gmag[eband], 75)) if eband.any() else 45.0
    k = float(np.clip(45.0 / max(sharp, 1.0), 1.0, 1.8))
    band_w, feather = BAND * k, FEATHER * k
    band = fg0 & (dist_bg <= band_w)
    # 경계띠의 각 픽셀: 가장 가까운 '확실한 고양이 색'을 F로 삼아, C = a*F + (1-a)*흰색 에서 a를 구한다
    idx = ndi.distance_transform_edt(~sure_fg, return_distances=False, return_indices=True)
    F = c[idx[0], idx[1]]
    dF = B - F
    denom = (dF ** 2).sum(2)
    num = (d * dF).sum(2)
    alpha_b = np.where(denom > 600, num / np.maximum(denom, 1), 1.0)
    alpha_b = np.clip(alpha_b, 0, 1) ** 1.3                    # 약한(흰색이 많이 섞인) 곳은 더 투명하게 → 흰 테두리 감소
    alpha = np.where(fg0, 1.0, 0.0).astype(np.float32)
    alpha[band] = alpha_b[band]
    edge1 = fg0 & (dist_bg <= 1.5)                              # 배경 바로 옆 1칸은 더 투명하게
    alpha[edge1] *= 0.55
    # 경계 부드럽게: 1칸 안쪽으로 줄이고 블러
    a = ndi.minimum_filter(alpha, size=3)
    a = ndi.gaussian_filter(a, feather)
    a = np.where(ndi.binary_dilation(fg0, iterations=2), a, 0.0)
    # 색 정리: 투명한 곳의 색은 가까운 고양이 색으로 채워서, 줄이거나 부드럽게 그릴 때 흰/검은 테두리가 안 생기게 함
    a3 = np.clip(alpha, 0.02, 1)[..., None]
    unmixed = np.clip((c - B * (1 - a3)) / a3, 0, 255)
    mixed = 0.7 * F + 0.3 * unmixed                             # 경계의 흰 기운은 안쪽 털색 쪽으로 당겨서 흰 테두리 제거
    col = np.where(band[..., None], np.where(alpha[..., None] > 0.15, np.where((alpha < 0.97)[..., None], mixed, unmixed), F), c)
    col = np.where((a <= 0.01)[..., None] | (~fg0)[..., None], F, col)
    return np.clip(a, 0, 1), col, fg0


def find_cats(fg: np.ndarray, want: int = 6):
    """덩어리(고양이)를 찾는다. 꼬리처럼 떨어진 조각은 가까운 몸에 붙인다."""
    for grow in (7, 11, 15, 21, 27, 35, 45):
        d = ndi.binary_dilation(fg, structure=np.ones((3, 3)), iterations=grow)
        lab, n = ndi.label(d)
        if n == want:
            return lab * fg, n, grow
        if n < want:
            break
    d = ndi.binary_dilation(fg, structure=np.ones((3, 3)), iterations=21)
    lab, n = ndi.label(d)
    sizes = ndi.sum(fg, lab, range(1, n + 1))
    order = np.argsort(-sizes)[:want] + 1
    out = np.zeros_like(lab)
    for k, o in enumerate(order, 1):
        out[(lab == o) & fg] = k
    return out, int(min(n, want)), -1


def order_cells(lab, n):
    """읽는 순서(위→아래, 왼쪽→오른쪽)로 번호를 매긴다."""
    info = []
    for i in range(1, n + 1):
        ys, xs = np.where(lab == i)
        info.append((i, (ys.min() + ys.max()) / 2, (xs.min() + xs.max()) / 2, ys.min(), ys.max(), xs.min(), xs.max()))
    h = np.mean([r[4] - r[3] for r in info])
    info.sort(key=lambda r: r[1])
    rows, cur = [], [info[0]]
    for r in info[1:]:
        if abs(r[1] - np.mean([q[1] for q in cur])) < h * 0.5:
            cur.append(r)
        else:
            rows.append(cur)
            cur = [r]
    rows.append(cur)
    res = []
    for row in rows:
        res += sorted(row, key=lambda r: r[2])
    return res


def process(path: Path):
    name = path.stem
    rgb = np.array(Image.open(path).convert("RGB"))
    # 흰 공의 그림자가 바닥 높은 곳까지 남는 그림은 바닥 정리 범위를 넓힌다 (다른 그림에 쓰면 흰 털이 상할 수 있음)
    wide_floor = "털실공4" in name
    chk = is_checker(rgb)
    if chk:
        print("  (체크무늬 배경으로 판단)")
    alpha, color, fg = matte(rgb, 0.42, 0.10, 130, chk) if wide_floor else matte(rgb, checker=chk)
    ci = rgb.astype(np.int16)
    edge_zone = _long_lines(((ci.max(2) - ci.min(2)) <= 14) & (ci.max(2) < 150), length=140, thick=9)   # 진짜 검은/짙은 칸 선만
    edge_zone[:2] = edge_zone[-2:] = True
    edge_zone[:, :2] = edge_zone[:, -2:] = True
    want = {"꾹꾹이": 9, "살금살금": 7}.get(name.split("-")[-1], 6)     # 그림에 따라 컷 수가 다른 것
    lab, n, grow = find_cats(fg, want)
    cells = order_cells(lab, n)
    out_dir = OUT / name
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("f*.png"):
        old.unlink()
    cut_frames = []
    meta = {"name": name, "source_size": [rgb.shape[1], rgb.shape[0]], "frames": []}
    frames = []
    for k, (i, cy, cx, y0, y1, x0, x1) in enumerate(cells):
        m = lab == i
        sub, ns = ndi.label(m)
        if ns > 1:                                  # 칸 선 조각 같은 작은 부스러기는 버림
            sz = ndi.sum(m, sub, range(1, ns + 1))
            keep = np.zeros(ns + 1, bool)
            keep[1:] = sz >= sz.max() * 0.06
            m = keep[sub]
        a = np.where(ndi.binary_dilation(m, iterations=4), alpha, 0)     # 옆 컷의 조각이 섞이지 않게 이 컷 영역만
        rgba = np.dstack([color.astype(np.uint8), (a * 255 + 0.5).astype(np.uint8)])
        ys, xs = np.where(a > 0.02)
        box = (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1)
        tile = Image.fromarray(rgba[box[1]:box[3], box[0]:box[2]], "RGBA")
        tile.save(out_dir / f"f{k}.png")
        frames.append(tile)
        touch = int((ndi.binary_dilation(m, iterations=3) & edge_zone).sum())
        meta["frames"].append({"file": f"f{k}.png", "box": list(box), "size": list(tile.size), "cut_by_edge": touch > 12})
        if touch > 12:
            cut_frames.append(k)
    (out_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    if frames:
        H = max(f.height for f in frames) + 20
        W = sum(f.width for f in frames) + 20 * (len(frames) + 1)
        sheet = Image.new("RGBA", (W, H), (170, 40, 170, 255))      # 자홍색: 남은 흰 테두리/배경이 눈에 확 띄게
        x = 20
        for f in frames:
            sheet.alpha_composite(f, (x, H - 10 - f.height))
            x += f.width + 20
        SHOW.mkdir(parents=True, exist_ok=True)
        sheet.convert("RGB").save(SHOW / f"{name}.png")
    return n, grow, cut_frames


def main():
    only = sys.argv[1:]
    bad = []
    for p in sorted(SRC.glob("*.png")):
        if only and not any(o in p.stem for o in only):
            continue
        n, grow, cut = process(p)
        flag = "" if n >= 6 and grow > 0 else "  <-- 확인 필요"
        print(f"{p.stem}: 컷 {n}개{flag}" + (f"  ※ 칸 가장자리에서 잘린 컷(0부터): {cut}" if cut else ""))
        if flag:
            bad.append(p.stem)
    print("\n확인 필요:", bad or "없음")


if __name__ == "__main__":
    main()
