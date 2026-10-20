"""컷마다 눈 위치를 찾아 assets/sprites/sprites.json 의 각 컷에 'eyes': [[x, y], ...] (저장 픽셀) 로 저장한다. (개발용)

털색을 바꿀 때 눈(홍채·동공)이 털처럼 칠해져서 검은·흰·삼색 고양이의 눈이 안 보였다. 앱(photocat → coats.paint_eyes)은
이 위치에 털색과 상관없이 같은 또렷한 눈을 다시 그린다.
눈은 색이 털과 거의 같아서(색상 30~45°) 색으로는 찾을 수 없다. 그래서 동작마다 첫 컷에서 사람이 찍어 둔 눈 위치(SEEDS)를 시작점으로,
다음 컷들은 눈 둘레의 밝기 무늬가 가장 닮은 곳을 찾아 따라간다(1단계). 그렇게 잘 찾은 눈 조각들을 '견본 모음'으로 삼아,
모든 동작·모든 컷의 얼굴 쪽 영역에서 견본과 가장 닮은 곳을 다시 찾는다(2단계: 고개를 돌리거나 크게 움직인 컷, 첫 컷에서 눈을 감았던 동작도 찾는다).
닮은 정도가 낮으면(눈을 감았거나 가려짐) 그 컷에는 눈을 두지 않는다.
사용: python tools/eye_marks.py [확인용 그림 폴더]      (build_sprites.py 가 frame_gaps 다음에 부른다)
"""
import json
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
SP = ROOT / "assets" / "sprites"

# 동작별 첫 컷(f0)의 눈 위치 (저장 픽셀, 사람이 확대 그림을 보고 찍음). 첫 컷에서 눈을 감았거나 얼굴이 안 보이는 동작은 뺐다.
SEEDS = {
    "walk": [(296, 35)], "run": [(323, 35)], "trot": [(250, 69)], "sneak": [(313.5, 50.5)],
    "jump_down": [(237, 34)], "jump_up": [(209, 34.5)], "crouch": [(198, 26)], "land": [(290, 37)], "hold": [(191, 39.5)],
    "stand": [(223.5, 37)], "sit": [(166, 43), (188, 42)], "sit_tilt": [(167, 44), (188.5, 42)], "loaf": [(195.5, 44)],
    "sleep_nap": [(202.5, 51)], "scratch": [(144.5, 43)], "groom": [(195, 38)], "groom_leg": [(183, 45)], "groom_face": [(146, 45)],
    "stretch": [(240.5, 78)], "yawn": [(130, 39)], "tail_play": [(144.5, 41.5)], "swat": [(158, 42)], "wiggle": [(181, 41)],
    "bat": [(144, 44)],
}
HW, HH = 7, 6               # 비교하는 눈 둘레 조각의 반 크기 (저장 픽셀)
SEARCH = 8                  # 앞 컷 위치에서 이만큼 둘레를 찾는다
ACCEPT = 0.62               # 이보다 덜 닮으면 그 컷에는 눈이 없다(감았거나 가려짐)
LIB_KEEP = 0.80             # 1단계에서 이만큼 닮게 찾은 눈 조각만 견본으로 쓴다
LIB_ACCEPT = 0.74           # 2단계: 견본과 이만큼 닮아야 눈으로 본다
ROI_X, ROI_Y = 0.62, 0.68   # 2단계에서 찾는 곳: 컷의 앞쪽(오른쪽) 38%, 위쪽 68% (그림은 모두 오른쪽을 본다)
LIB_PAIR = 0.42             # 둘째 눈은 첫 눈과 나란한 좁은 자리에서 너그럽게 (반대쪽 눈은 모양이 덜 닮는다)
FRONTAL = set()             # (자동 둘째 눈 찾기를 쓸 동작: 정면 동작은 아래 FAR_EYES 로 사람이 찍은 값을 쓴다. 자동으로는 이마 무늬·코를 잡았다)
# 정면을 향한 동작의 '반대쪽 눈' (사람이 확대 그림을 보고 찍음, 저장 픽셀). 둘레 3 픽셀 안에서 가장 어두운 동공 쪽으로 맞춰 쓴다.
FAR_EYES = {
    "sit": {0: (188, 42), 1: (185, 34), 3: (186.5, 43.5), 4: (188, 46), 5: (191, 43)},
    "sit_tilt": {0: (186, 42), 1: (179, 43), 2: (165.5, 43.5), 3: (164, 45.5), 4: (187, 46.5), 5: (162.5, 46)},
    "hold": {1: (99.5, 34), 2: (205, 36), 3: (101, 34), 4: (194, 36), 5: (101, 34)},
    "jump_down": {1: (218, 54.5)},
}
TRUST = 0.75                # 1단계에서 이만큼 닮게 따라간 눈은 2단계 검사 없이 믿는다
CENTER_MIN, CENTER_MEAN = 0.16, 0.38    # 눈 가운데(5x5)의 가장 어두운 값·평균 밝기 상한: 동공·테두리가 있어야 눈


def alpha_of(path):
    return np.asarray(Image.open(path).convert("RGBA"))[..., 3].astype(np.float32) / 255.0


def luminance(path):
    im = np.asarray(Image.open(path).convert("RGBA")).astype(np.float32) / 255.0
    lum = 0.299 * im[..., 0] + 0.587 * im[..., 1] + 0.114 * im[..., 2]
    return np.where(im[..., 3] > 0.5, lum, 0.5)                   # 바탕(투명)은 중간 밝기로


def patch(lum, x, y):
    x, y = int(round(x)), int(round(y))
    if x - HW < 0 or y - HH < 0 or x + HW + 1 > lum.shape[1] or y + HH + 1 > lum.shape[0]:
        return None
    p = lum[y - HH:y + HH + 1, x - HW:x + HW + 1]
    s = p.std()
    return (p - p.mean()) / s if s > 1e-4 else None


def track(key, n, frames=None):
    """동작 하나의 모든 컷에서 눈 위치를 찾는다. [[(x, y), ...] (컷마다)], [닮은 정도 목록].
    frames(컷 정보)가 있으면 머리 꼭대기가 움직인 만큼 눈도 옮겨 놓고 그 둘레를 찾는다 (컷 사이 움직임이 큰 달리기·점프)."""
    seeds = SEEDS.get(key)
    out = [[] for _ in range(n)]
    scores = [[] for _ in range(n)]
    if not seeds:
        return out, scores
    lums = [luminance(SP / key / f"f{i}.png") for i in range(n)]
    tops = [(f["cx"] + f["hx"], lums[i].shape[0] - f["hy"]) for i, f in enumerate(frames)] if frames else None
    for sx, sy in seeds:
        tmpl = patch(lums[0], sx, sy)
        if tmpl is None:
            continue
        out[0].append((float(sx), float(sy), 1.0))
        scores[0].append(1.0)
        px, py = sx, sy
        for i in range(1, n):
            centers = [(px, py)]                                      # 앞 컷 자리 그대로, 그리고 머리 꼭대기가 움직인 만큼 옮긴 자리: 둘 다 찾아보고 더 닮은 곳
            if tops:
                mx, my = tops[i][0] - tops[i - 1][0], tops[i][1] - tops[i - 1][1]
                if abs(mx) < 40 and abs(my) < 40 and (abs(mx) > 2 or abs(my) > 2):
                    centers.append((px + mx, py + my))
            best, bx, by = -1.0, px, py
            for qx, qy in centers:
                for dy in range(-SEARCH, SEARCH + 1):
                    for dx in range(-SEARCH, SEARCH + 1):
                        p = patch(lums[i], qx + dx, qy + dy)
                        if p is None:
                            continue
                        c = float((tmpl * p).mean())
                        if c > best:
                            best, bx, by = c, qx + dx, qy + dy
            if best >= ACCEPT:
                out[i].append((float(bx), float(by), best))
                scores[i].append(round(best, 2))
                tmpl = 0.85 * tmpl + 0.15 * patch(lums[i], bx, by)       # 모양이 조금씩 바뀌는 것을 따라가되 첫 컷 모양을 오래 기억한다
                tmpl = (tmpl - tmpl.mean()) / max(tmpl.std(), 1e-4)
                px, py = bx, by
            else:
                scores[i].append(round(best, 2))                      # 못 찾음: 다음 컷은 마지막으로 찾은 자리 둘레에서 찾는다
    return out, scores


def sheet(meta, folder):
    """확인용: 동작마다 컷들의 얼굴 둘레를 늘어놓고 찾은 눈에 동그라미를 그린다."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    K, CW, CH, PER = 3, 56, 40, 12
    for key in meta["actions"]:
        fr = meta["actions"][key]["frames"]
        rows = (len(fr) + PER - 1) // PER
        img = Image.new("RGB", (PER * CW * K, rows * (CH * K + 12)), (255, 255, 255))
        d = ImageDraw.Draw(img)
        for i, f in enumerate(fr):
            im = Image.open(SP / key / f"f{i}.png").convert("RGBA")
            bg = Image.new("RGBA", im.size, (190, 200, 210, 255))
            bg.alpha_composite(im)
            eyes = f.get("eyes") or []
            cx, cy = (np.mean([e[0] for e in eyes]), np.mean([e[1] for e in eyes])) if eyes else (im.width * 0.84, im.height * 0.34)
            x0, y0 = int(cx - CW / 2), int(cy - CH / 2)
            c = Image.new("RGBA", (CW, CH), (255, 255, 255, 255))
            c.paste(bg.crop((x0, y0, x0 + CW, y0 + CH)), (0, 0))
            c = c.resize((CW * K, CH * K), Image.NEAREST).convert("RGB")
            dc = ImageDraw.Draw(c)
            for ex, ey in eyes:
                X, Y = (ex - x0) * K, (ey - y0) * K
                dc.ellipse([X - 4.2 * K, Y - 3.3 * K, X + 4.2 * K, Y + 3.3 * K], outline=(255, 0, 0))
            col, row = i % PER, i // PER
            img.paste(c, (col * CW * K, row * (CH * K + 12) + 12))
            d.text((col * CW * K + 2, row * (CH * K + 12)), "f%d %s" % (i, "" if eyes else "(없음)"), fill=(0, 0, 0))
        img.save(folder / f"eyes_{key}.png")


def library(meta, tracked):
    """1단계에서 잘 찾은 눈 조각들 (견본 모음, 날것의 밝기)."""
    lib = []
    for key, (eyes, scores) in tracked.items():
        for i, (es, ss) in enumerate(zip(eyes, scores)):
            if not es:
                continue
            lum = luminance(SP / key / f"f{i}.png")
            for x, y, c in es:
                if c >= LIB_KEEP:
                    x, y = int(round(x)), int(round(y))
                    p = lum[y - HH:y + HH + 1, x - HW:x + HW + 1]
                    if p.shape == (2 * HH + 1, 2 * HW + 1) and p.std() > 0.02:
                        lib.append(p.astype(np.float32))
    return lib[::max(1, len(lib) // 90)]                                     # 너무 많으면 고르게 줄인다


def response(lum, lib, alpha=None):
    """견본 모음과 닮은 정도 지도: (지도, x0). 지도[yy, xx] 는 눈 중심 (x0 + xx + HW, yy + HH) 의 값, 눈일 수 없는 자리는 -1.
    눈일 수 있는 자리: 조각 대부분이 고양이(불투명)이고, 밝기 변화가 있고, 가운데에 아주 어두운 동공·테두리가 있어야 한다
    (밝기가 평평한 바탕은 닮은 정도가 엉뚱하게 높게 나와 귀 옆 바탕을 눈으로 잡았고, 귀 밑의 짙은 털은 가운데가 덜 어둡다)."""
    h, w = lum.shape
    x0, y1 = int(w * ROI_X), int(h * ROI_Y)
    # 그림 위·오른쪽 끝에 붙은 눈(정면 얼굴의 반대쪽 눈)도 찾도록 바탕을 덧댄다
    roi = np.pad(lum[:y1, x0:].astype(np.float32), ((HH, 0), (0, HW + 2)), constant_values=0.5)
    al = np.pad((alpha[:y1, x0:] if alpha is not None else np.ones((y1, w - x0), np.float32)), ((HH, 0), (0, HW + 2)), constant_values=0.0)
    off = (x0 + HW, 0)                                                 # 지도[yy, xx] 의 눈 중심 = (off[0] + xx, off[1] + yy)
    if roi.shape[0] < 2 * HH + 2 or roi.shape[1] < 2 * HW + 2:
        return None, off
    best = None
    for t in lib:
        r = cv2.matchTemplate(roi, t, cv2.TM_CCOEFF_NORMED)
        best = r if best is None else np.maximum(best, r)
    ksz = (2 * HW + 1, 2 * HH + 1)
    sl = (slice(HH, HH + best.shape[0]), slice(HW, HW + best.shape[1]))
    op = cv2.boxFilter((al > 0.5).astype(np.float32), -1, ksz, normalize=True, borderType=cv2.BORDER_CONSTANT)[sl]
    m1 = cv2.boxFilter(roi, -1, ksz, normalize=True, borderType=cv2.BORDER_REFLECT)
    m2 = cv2.boxFilter(roi * roi, -1, ksz, normalize=True, borderType=cv2.BORDER_REFLECT)
    textured = np.sqrt(np.maximum(m2 - m1 * m1, 0.0))[sl] >= 0.05
    dark = cv2.erode(roi, np.ones((5, 5), np.uint8))[sl]                                    # 가운데 5x5 의 가장 어두운 값
    mean = cv2.boxFilter(roi, -1, (5, 5), normalize=True, borderType=cv2.BORDER_REFLECT)[sl]
    first = (op >= 0.92) & textured & (dark <= CENTER_MIN) & (mean <= CENTER_MEAN)
    # 둘째 눈(반대쪽 눈)은 얼굴 가장자리에 붙어 있어 조각에 바탕이 섞인다: 불투명은 덜 따지고 대신 더 어두워야 한다
    second = (op >= 0.70) & textured & (dark <= CENTER_MIN - 0.03) & (mean <= CENTER_MEAN)
    return (np.where(first, best, -1.0), np.where(second, best, -1.0)), off


def pick(resp, off, have, frontal=False):
    """닮은 정도 지도에서 눈을 고른다. have: 1단계에서 이미 찾은 눈 [(x, y)]. 많아야 두 눈.
    얼굴이 정면을 향하는 동작(frontal)에서 한 눈만 있으면, 그 눈 오른쪽 14~34 픽셀·같은 높이(위아래 6 픽셀 안)에서 반대쪽 눈을 찾는다.
    (반대쪽 눈은 견본과 덜 닮아서 기준을 낮추는 대신 자리를 좁혔다. 옆모습에서도 찾게 했더니 눈 뒤 줄무늬·코를 잡았다.)"""
    eyes = [(float(x), float(y)) for x, y in have]
    if resp is None:
        return eyes
    r, r2 = resp[0].copy(), resp[1].copy()
    hh, ww = r.shape
    ys, xs = np.mgrid[0:hh, 0:ww]
    cx, cy = off[0] + xs, off[1] + ys                                    # 각 칸의 눈 중심 좌표

    def suppress(ex, ey):
        m = (np.abs(cx - ex) <= 9) & (np.abs(cy - ey) <= 7)            # 같은 눈을 두 번 잡지 않게
        r[m] = -1.0
        r2[m] = -1.0

    for ex, ey in eyes:
        suppress(ex, ey)
    if not eyes:
        k = int(np.argmax(r))
        if r.flat[k] >= LIB_ACCEPT:
            eyes.append((float(cx.flat[k]), float(cy.flat[k])))
            suppress(*eyes[0])
    if len(eyes) == 1 and frontal:
        ex, ey = eyes[0]
        band = (np.abs(cy - ey) <= 6) & (cx - ex >= 14) & (cx - ex <= 34)
        rb = np.where(band, r2, -1.0)
        k = int(np.argmax(rb))
        if rb.flat[k] >= LIB_PAIR:
            eyes.append((float(cx.flat[k]), float(cy.flat[k])))
    return eyes[:2]


def snap_dark(lum, x, y, r=3):
    """(x, y) 둘레 r 픽셀 안에서 가장 어두운 곳(동공)으로 맞춘다. 충분히 어둡지 않으면 그대로."""
    xi, yi = int(round(x)), int(round(y))
    win = cv2.blur(lum.astype(np.float32), (5, 5))[max(0, yi - r):yi + r + 1, max(0, xi - r):xi + r + 1]
    if win.size == 0:
        return float(x), float(y)
    k = np.unravel_index(int(np.argmin(win)), win.shape)
    if win[k] > 0.30:
        return float(x), float(y)
    return float(max(0, xi - r) + k[1]), float(max(0, yi - r) + k[0])


def eye_ok(resp, off, x, y):
    """1단계에서 따라간 눈이 '눈일 수 있는 자리'인지 (따라가다 털 무늬로 미끄러진 것을 버린다)."""
    if resp is None:
        return True
    m = resp[1]
    xx, yy = int(round(x)) - off[0], int(round(y)) - off[1]
    if not (0 <= yy < m.shape[0] and 0 <= xx < m.shape[1]):
        return True                                                   # 찾는 영역 밖이면 판단하지 않는다 (1단계 결과를 믿는다)
    return bool(m[max(0, yy - 1):yy + 2, max(0, xx - 1):xx + 2].max() > -1.0)


def main(sheet_dir=None):
    meta = json.loads((SP / "sprites.json").read_text(encoding="utf-8"))
    report = []
    tracked = {key: track(key, len(act["frames"]), act["frames"]) for key, act in meta["actions"].items() if key in SEEDS}
    lib = library(meta, tracked)
    for key, act in meta["actions"].items():
        fr = act["frames"]
        t_eyes = tracked.get(key, ([[] for _ in fr], None))[0]
        found_n = 0
        for i, f in enumerate(fr):
            fp = SP / key / f"f{i}.png"
            resp, off = response(luminance(fp), lib, alpha_of(fp))
            have = [(x, y) for x, y, c in t_eyes[i] if i == 0 or c >= TRUST or eye_ok(resp, off, x, y)]   # 아주 닮게 따라간 눈은 그대로 믿는다
            e = pick(resp, off, have, key in FRONTAL)
            far = FAR_EYES.get(key, {}).get(i)
            if far and len(e) == 1:
                fx, fy = snap_dark(luminance(fp), *far)
                if abs(fx - e[0][0]) > 8:
                    e.append((fx, fy))
            if e:
                f["eyes"] = [[round(float(x), 1), round(float(y), 1)] for x, y in e]
                found_n += 1
            else:
                f.pop("eyes", None)
        report.append((key, found_n, len(fr), len(lib)))
    (SP / "sprites.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    if sheet_dir:
        sheet(meta, sheet_dir)
    return report


if __name__ == "__main__":
    for key, found, n, nlib in main(sys.argv[1] if len(sys.argv) > 1 else None):
        print(f"{key:12s} 눈을 찾은 컷 {found:2d}/{n:2d}  (견본 {nlib}개)")
