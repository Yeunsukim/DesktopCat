"""AI 가 만든 걷기 GIF(체크무늬 배경, 30프레임, 고양이는 제자리에서 걸음)에서 고양이만 오려 투명 PNG 프레임으로 만든다. (개발용)

GIF 는 256색으로 줄여져 있고 배경 체크무늬의 점무늬(디더링)가 프레임마다 조금씩 달라서, 한 프레임만 보고는 밝은 다리·흰 발이 배경과 구분되지 않는다.
그래서 30프레임 전체로 '배경 판'을 만든다:
  · 체크무늬는 모든 프레임에서 같은 자리에 있다. 한 픽셀이 대부분의 프레임에서 '옅은 무채색(체크무늬 색)'이면 그 픽셀의 배경색 = 그 색들의 중앙값.
  · 고양이 몸통처럼 거의 항상 가려진 픽셀은 배경 판이 없다 → 항상 고양이.
  · 프레임마다: 배경 판과 색이 충분히 다르면 고양이. 흰 발처럼 배경색과 비슷해도 고양이 덩어리 안쪽이면 구멍 메우기로 되살린다.
그림자(바닥에 비친 옅은 회색)는 배경 판과 비교하면 어둡기만 하고 색이 없어서 따로 걸러낸다.
사용: python tools/gif_extract.py <gif> <출력 폴더> [시작 프레임] [프레임 수]
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageSequence
from scipy import ndimage as ndi


def frames_of(path):
    return [np.array(f.convert("RGB")) for f in ImageSequence.Iterator(Image.open(path))]


def background_plate(frames):
    """(판 RGB float, 판이 있는 픽셀 마스크). 판이 없는 픽셀(항상 고양이)은 False."""
    F = np.stack(frames).astype(np.float32)                     # (N, H, W, 3)
    mx, mn = F.max(3), F.min(3)
    lum = F.mean(3)
    bgish = ((mx - mn) <= 40) & (lum > 170)                     # 체크무늬는 옅은 무채색~옅은 푸른기
    cnt = bgish.sum(0)
    has = cnt >= 6
    plate = np.zeros(F.shape[1:], np.float32)
    # bgish 인 프레임들의 중앙값 (bgish 아닌 값은 NaN 처리)
    G = np.where(bgish[..., None], F, np.nan)
    with np.errstate(all="ignore"):
        med = np.nanmedian(G, axis=0)
    plate = np.where(has[..., None], med, 0.0)
    return plate, has


def cutout(f, plate, has):
    c = f.astype(np.float32)
    diff = np.abs(c - plate).max(2)
    mx, mn = c.max(2), c.min(2)
    lum = c.mean(2)
    colored = (mx - mn) > 34                                    # 털색 (체크무늬는 거의 무채색)
    dark = lum < 150
    # 배경 판과 색이 충분히 다르면 고양이. (옅은 분홍 귀 안쪽·연한 털은 채도가 낮아도 판과는 확실히 다르다)
    # 그림자는 판과 '밝기만' 다르고 색상이 같다 → 채도 없는 어두운 부분만 따로 거른다.
    fg = np.where(has, (diff > 40) & (colored | dark | (diff > 60)), True)
    # 바닥 그림자: 배경 판보다 어둡지만 색이 없는 것 → 고양이 아님
    shadow = has & ~colored & ~dark & (lum > 120) & (diff < 75)
    fg &= ~shadow
    fg = ndi.binary_opening(fg, iterations=1)
    lab, n = ndi.label(fg)
    if n:
        sz = ndi.sum(fg, lab, range(1, n + 1))
        keep = np.zeros(n + 1, bool)
        keep[1:] = sz >= 0.03 * sz.max()                         # 고양이 덩어리 (꼬리 조각 포함)
        fg = keep[lab]
    # 흰 발·흰 털이 배경 판과 같은 색이라 구멍이 난 곳: 작은 구멍은 메운다 (바깥으로 열린 틈은 두고)
    holes = ndi.binary_fill_holes(fg) & ~fg
    lh, nh = ndi.label(holes)
    if nh:
        hs = ndi.sum(holes, lh, range(1, nh + 1))
        hk = np.zeros(nh + 1, bool)
        hk[1:] = hs < 1500
        fg |= hk[lh]
    fg = ndi.binary_closing(fg, iterations=2) | fg
    # 가장자리 부드럽게 (1칸 안쪽으로 줄이고 블러)
    a = ndi.gaussian_filter(ndi.minimum_filter(fg.astype(np.float32), size=3), 0.9) * ndi.binary_dilation(fg, iterations=1)
    # 투명한 곳의 색이 배경색(흰색)이 되지 않게 가까운 고양이 색으로 채운다
    idx = ndi.distance_transform_edt(~fg, return_distances=False, return_indices=True)
    rgb = np.where(fg[..., None], c, c[idx[0], idx[1]])
    return np.dstack([np.clip(rgb, 0, 255), np.clip(a, 0, 1) * 255]).astype(np.uint8)


def extract(path, out, start=0, count=None):
    fr = frames_of(path)
    plate, has = background_plate(fr)
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    sel = fr[start:start + count] if count else fr[start:]
    for i, f in enumerate(sel):
        Image.fromarray(cutout(f, plate, has), "RGBA").save(out / f"f{i}.png")
    return len(sel)


if __name__ == "__main__":
    src, out = sys.argv[1], sys.argv[2]
    start = int(sys.argv[3]) if len(sys.argv) > 3 else 0
    count = int(sys.argv[4]) if len(sys.argv) > 4 else None
    print("프레임", extract(src, out, start, count))


# ---------------------------------------------------------------- 회색 스튜디오 배경(체크무늬가 아닌 부드러운 배경)용: GrabCut
def cutout_grabcut(f, iters=4):
    """색이 있는 털(채도) 또는 어두운 줄무늬를 씨앗으로 GrabCut 을 돌려 고양이를 오린다. 바닥 그림자는 색이 없어서 배경으로 남는다."""
    import cv2
    h, w = f.shape[:2]
    c = f.astype(np.int16)
    sat = c.max(2) - c.min(2)
    lum = c.mean(2)
    seed = ((sat > 62) | (lum < 105))
    seed = ndi.binary_opening(seed, iterations=2)
    lab, n = ndi.label(seed)
    if n:
        sz = ndi.sum(seed, lab, range(1, n + 1))
        seed = np.isin(lab, [i + 1 for i, v in enumerate(sz) if v >= 0.05 * sz.max()])
    ys, xs = np.where(seed)
    x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
    mask = np.full((h, w), cv2.GC_BGD, np.uint8)
    box = np.zeros((h, w), bool)
    box[max(0, y0 - 12):y1 + 12, max(0, x0 - 12):x1 + 12] = True
    mask[box] = cv2.GC_PR_BGD
    mask[box & ndi.binary_dilation(seed, iterations=6)] = cv2.GC_PR_FGD
    mask[ndi.binary_erosion(seed, iterations=3)] = cv2.GC_FGD
    bgd = np.zeros((1, 65), np.float64)
    fgd = np.zeros((1, 65), np.float64)
    cv2.grabCut(cv2.cvtColor(f, cv2.COLOR_RGB2BGR), mask, None, bgd, fgd, iters, cv2.GC_INIT_WITH_MASK)
    fg = (mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD)
    fg = ndi.binary_opening(fg, iterations=1)
    lab, n = ndi.label(fg)
    if n:
        sz = ndi.sum(fg, lab, range(1, n + 1))
        fg = np.isin(lab, [i + 1 for i, v in enumerate(sz) if v >= 0.03 * sz.max()])
    fg = refine_with_background_model(f, fg)
    holes = ndi.binary_fill_holes(fg) & ~fg
    lh, nh = ndi.label(holes)
    if nh:
        hs = ndi.sum(holes, lh, range(1, nh + 1))
        fg |= np.isin(lh, [i + 1 for i, v in enumerate(hs) if v < 1500])
    a = ndi.gaussian_filter(ndi.minimum_filter(fg.astype(np.float32), size=3), 1.0) * ndi.binary_dilation(fg, iterations=1)
    idx = ndi.distance_transform_edt(~fg, return_distances=False, return_indices=True)
    cf = f.astype(np.float32)
    rgb = np.where(fg[..., None], cf, cf[idx[0], idx[1]])
    return np.dstack([np.clip(rgb, 0, 255), np.clip(a, 0, 1) * 255]).astype(np.uint8)


def refine_with_background_model(f, fg):
    """GrabCut 결과(fg)는 연한 털(주둥이·이마 앞쪽)을 안쪽으로 깎는다. 배경 색을 따로 추정해서, GrabCut 결과 근처에서 '배경과 색이 다른' 픽셀을 되살린다.
    배경 추정: 고양이에서 멀리 떨어진 픽셀들로 부드러운 면(가중 가우시안)을 만든다. 바닥 그림자는 밝기만 낮고 색이 같아서 되살리지 않는다."""
    import cv2
    g = cv2.GaussianBlur(f, (0, 0), 1.3)                         # GIF 의 점무늬(디더링) 잡음 제거
    lab = cv2.cvtColor(g, cv2.COLOR_RGB2LAB).astype(np.float32)
    far = ~ndi.binary_dilation(fg, iterations=26)
    w = far.astype(np.float32)
    bg = np.zeros_like(lab)
    den = cv2.GaussianBlur(w, (0, 0), 38) + 1e-4
    for k in range(3):
        bg[..., k] = cv2.GaussianBlur(lab[..., k] * w, (0, 0), 38) / den
    d = lab - bg
    dchroma = np.hypot(d[..., 1], d[..., 2])
    dL = d[..., 0]
    diff = (dchroma > 6.0) | (dL > 9.0) | (dL < -38.0)
    grow = diff & ndi.binary_dilation(fg, iterations=20)
    out = fg | grow
    out = ndi.binary_opening(out, iterations=2)                 # 낱개 점(잡음)은 지운다
    out = ndi.binary_closing(out, iterations=3) | out            # 털 사이 작은 틈은 메운다
    lab_, n = ndi.label(out)
    if n:
        sz = ndi.sum(out, lab_, range(1, n + 1))
        out = np.isin(lab_, [i + 1 for i, v in enumerate(sz) if v >= 0.03 * sz.max()])
    return out


def extract_grabcut(path, out, start=0, count=None):
    fr = frames_of(path)
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    sel = fr[start:start + count] if count else fr[start:]
    for i, f in enumerate(sel):
        Image.fromarray(cutout_grabcut(f), "RGBA").save(out / f"f{i}.png")
    return len(sel)


def export_set(src, name, start, count, mode="checker"):
    """GIF 의 start 번부터 count 프레임을 오려서 assets/ai/<name>/f0.png... 와 meta.json 으로 저장한다 (build_sprites.py 가 읽는 형식, 고양이에 꼭 맞게 잘라 둠).
    mode: 'checker'(체크무늬 배경) / 'grabcut'(회색 스튜디오 같은 부드러운 배경)"""
    import json
    out = Path(__file__).resolve().parent.parent / "assets" / "ai" / name
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("f*.png"):
        old.unlink()
    tmp = out / "_tmp"
    if mode == "checker_refined":
        fr = frames_of(src)
        plate, has = background_plate(fr)
        tmp.mkdir(parents=True, exist_ok=True)
        for i, f in enumerate(fr[start:start + count]):
            Image.fromarray(cutout_checker_refined(f, plate, has), "RGBA").save(tmp / f"f{i}.png")
    else:
        (extract_grabcut if mode == "grabcut" else extract)(src, tmp, start, count)
    frames = []
    for i in range(count):
        im = Image.open(tmp / f"f{i}.png")
        a = np.array(im)[..., 3]
        ys, xs = np.where(a > 5)
        im = im.crop((int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1))
        im.save(out / f"f{i}.png")
        frames.append({"file": f"f{i}.png", "box": [0, 0, im.width, im.height], "size": list(im.size)})
        (tmp / f"f{i}.png").unlink()
    tmp.rmdir()
    (out / "meta.json").write_text(json.dumps({"name": name, "source_size": [640, 360], "frames": frames}, ensure_ascii=False), encoding="utf-8")
    return count


# ---------------------------------------------------------------- 체크무늬 배경: 배경 판으로 1차 오린 뒤 GrabCut 으로 가장자리 다듬기
def cutout_checker_refined(f, plate, has, iters=3):
    """1차: 배경 판 방식(cutout)의 결과를 '확실한 고양이'(안쪽)와 '확실한 배경'(바깥)으로 나누고, 그 사이 띠(가장자리)만 GrabCut 이 결정한다.
    GrabCut 단독은 체크무늬를 고양이 조각으로 집어서 못 쓰지만, 씨앗이 정확하면 연한 귀 가장자리·털 끝을 잘 살린다."""
    import cv2
    first = cutout(f, plate, has)
    fg0 = first[..., 3] > 128
    sure_fg = ndi.binary_erosion(fg0, iterations=5)
    # 배경 판과 거의 똑같은 색인 곳은 확실한 배경 (연한 털도 판과는 색이 다르다)
    diff = np.abs(f.astype(np.float32) - plate).max(2)
    sure_bg = ~ndi.binary_dilation(fg0, iterations=9) | (has & (diff < 14) & ~ndi.binary_erosion(fg0, iterations=0))
    mask = np.full(fg0.shape, cv2.GC_PR_BGD, np.uint8)
    mask[ndi.binary_dilation(fg0, iterations=9) & ~sure_fg] = cv2.GC_PR_FGD
    mask[fg0 & ~sure_fg] = cv2.GC_PR_FGD
    mask[sure_fg] = cv2.GC_FGD
    mask[sure_bg & ~fg0] = cv2.GC_BGD
    bgd = np.zeros((1, 65), np.float64)
    fgd = np.zeros((1, 65), np.float64)
    cv2.grabCut(cv2.cvtColor(f, cv2.COLOR_RGB2BGR), mask, None, bgd, fgd, iters, cv2.GC_INIT_WITH_MASK)
    fg = (mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD)
    fg = ndi.binary_opening(fg, iterations=1)
    lab, n = ndi.label(fg)
    if n:
        sz = ndi.sum(fg, lab, range(1, n + 1))
        fg = np.isin(lab, [i + 1 for i, v in enumerate(sz) if v >= 0.03 * sz.max()])
    holes = ndi.binary_fill_holes(fg) & ~fg
    lh, nh = ndi.label(holes)
    if nh:
        hs = ndi.sum(holes, lh, range(1, nh + 1))
        fg |= np.isin(lh, [i + 1 for i, v in enumerate(hs) if v < 1500])
    a = ndi.gaussian_filter(ndi.minimum_filter(fg.astype(np.float32), size=3), 0.9) * ndi.binary_dilation(fg, iterations=1)
    idx = ndi.distance_transform_edt(~fg, return_distances=False, return_indices=True)
    cf = f.astype(np.float32)
    rgb = np.where(fg[..., None], cf, cf[idx[0], idx[1]])
    return np.dstack([np.clip(rgb, 0, 255), np.clip(a, 0, 1) * 255]).astype(np.uint8)
