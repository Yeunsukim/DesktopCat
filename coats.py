"""고양이 털색 바꾸기: 사진 컷의 '털 부분'만 골라서 밝기(줄무늬·털결)는 그대로 두고 색만 바꾼다.

눈동자·코·귀 안쪽 분홍·혀는 털이 아니라서 그대로 둔다 (색상이 털색 범위 밖이므로 걸러진다).
numpy 만 사용 (설치 파일에 들어가는 프로그램에서도 쓴다).
"""
import numpy as np

# (이름, 메뉴에 보이는 이름)
COATS = (
    ("brown", "갈색 줄무늬"),
    ("gray", "회색"),
    ("black", "검은색"),
    ("white", "흰색"),
    ("orange", "치즈(주황)"),
    ("calico", "삼색(흰·주황·검정)"),
)
COAT_KEYS = tuple(k for k, _ in COATS)

# 밝기(0=가장 어두움 ~ 1=가장 밝음) → 색 (0~1). 가운데 값들이 털의 중간 톤.
_RAMPS = {
    "gray":   ([0.0, 0.35, 0.70, 1.0], [(0.07, 0.07, 0.09), (0.34, 0.35, 0.39), (0.66, 0.67, 0.70), (0.93, 0.94, 0.96)]),
    "black":  ([0.0, 0.50, 1.0],       [(0.00, 0.00, 0.01), (0.075, 0.075, 0.085), (0.27, 0.27, 0.30)]),
    "white":  ([0.0, 0.40, 0.75, 1.0], [(0.60, 0.60, 0.64), (0.84, 0.84, 0.86), (0.96, 0.95, 0.94), (1.0, 0.99, 0.97)]),
    "calico_white": ([0.0, 0.40, 0.75, 1.0], [(0.84, 0.83, 0.84), (0.93, 0.925, 0.925), (0.985, 0.978, 0.968), (1.0, 0.996, 0.988)]),
    "calico_black": ([0.0, 0.50, 1.0], [(0.015, 0.013, 0.013), (0.085, 0.078, 0.075), (0.27, 0.25, 0.235)]),   # 삼색의 검정은 약간 갈색 기운
    "orange": ([0.0, 0.30, 0.60, 0.85, 1.0],
               [(0.30, 0.13, 0.04), (0.64, 0.31, 0.10), (0.89, 0.53, 0.22), (0.97, 0.75, 0.46), (1.0, 0.91, 0.73)]),
}


def _smooth(x, a, b):
    t = np.clip((x - a) / (b - a), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def _ramp(name, ln):
    xs, cols = _RAMPS[name]
    c = np.array(cols, np.float32)
    return np.stack([np.interp(ln, xs, c[:, i]) for i in range(3)], -1)


def _fur_weight(rgb):
    """털일 확률(0~1): 색상이 갈색~황토 범위이고 어느 정도 채도가 있는 곳."""
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
    h *= 60.0
    s = d / np.maximum(mx, 1e-6)
    hue_w = _smooth(h, 8, 16) * (1.0 - _smooth(h, 60, 72))        # 분홍(귀 안쪽·코)과 초록 눈은 제외
    # 어두운 줄무늬는 붉은 기운(색상이 분홍 쪽으로 기울어도)이 있어도 털이다: 귀 안쪽·코는 밝은 분홍이라 밝기로 구분한다
    dark_fur = _smooth(0.55 - mx, 0.0, 0.18) * _smooth(s, 0.12, 0.22)
    hue_w = np.maximum(hue_w, dark_fur * (1.0 - _smooth(h, 55, 70)) * (1.0 - 0.0 * h))
    sat_w = _smooth(s, 0.09, 0.19)                                 # 거의 무채색인 흰 수염·하이라이트는 제외
    return hue_w * sat_w


def _vnoise(u, v, freq, seed):
    """값 잡음(value noise): 격자 점마다 무작위 값을 두고 사이를 부드럽게 이은 0~1 무늬. u, v 는 (H, W) 배열."""
    n = int(freq) + 4
    g = np.random.default_rng(seed).random((n, n)).astype(np.float32)
    x, y = (u + 0.25) * freq, (v + 0.25) * freq
    x0 = np.clip(np.floor(x).astype(np.int32), 0, n - 2)
    y0 = np.clip(np.floor(y).astype(np.int32), 0, n - 2)
    fx, fy = np.clip(x - x0, 0, 1), np.clip(y - y0, 0, 1)
    fx, fy = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)
    top = g[y0, x0] * (1 - fx) + g[y0, x0 + 1] * fx
    bot = g[y0 + 1, x0] * (1 - fx) + g[y0 + 1, x0 + 1] * fx
    return top * (1 - fy) + bot * fy


def _fbm(u, v, seed, base=2.0):
    """큰 얼룩에 작은 울퉁불퉁함을 겹친 무늬 (0~1)."""
    return (0.58 * _vnoise(u, v, base, seed) + 0.28 * _vnoise(u, v, base * 2.1, seed + 11)
            + 0.14 * _vnoise(u, v, base * 4.3, seed + 23))


def _boxblur(a, r):
    """r 칸 반지름의 평균 흐리기 (numpy 만 사용)."""
    if r < 1:
        return a
    k = 2 * r + 1
    out = a
    for ax in (0, 1):
        c = np.cumsum(np.pad(out, [(r + 1, r) if i == ax else (0, 0) for i in range(2)], mode="edge"), axis=ax)
        hi = np.take(c, range(k, c.shape[ax]), axis=ax)
        lo = np.take(c, range(0, c.shape[ax] - k), axis=ax)
        out = (hi - lo) / k
    return out


# 삼색의 목표 비율(몸통 면적): 주황 50%, 검정 20%, 흰색 30%.  얼룩 문턱은 이 비율이 나오도록 _calibrate() 가 구한 값이다.
TARGET_ORANGE, TARGET_BLACK = 0.50, 0.20
BLACK_K, ORANGE_K = 0.857, 1.050          # 순위 구간 보정 계수(머리 영역을 따로 칠해서 생기는 어긋남을 맞춘다): 실제 면적을 재서 정한 값


def _patch_fields(u, v, ln, head):
    """얼룩의 '자리' 점수들. 값이 클수록 그 색이 앉기 쉽다. (문턱은 _patches 에서 비율에 맞춰 정한다)"""
    fuzz = 0.04 * (ln - 0.5) + 0.03 * (_vnoise(u, v, 38.0, 7) - 0.5)            # 털 올 단위로 살짝만 들쭉날쭉
    fo = _fbm(u, v, 101, 2.6)                                      # 주황: 큼직한 덩어리 (등·옆구리·엉덩이를 넓게 덮음)
    fb = _fbm(u, v, 202, 4.2)                                      # 검정: 중간 크기 덩어리 몇 개
    top = 0.55 * (1.0 - _smooth(v, 0.30, 0.95))                    # 위쪽(등)일수록 색이 앉기 쉽다 (너무 세게 하면 몸이 말린 자세에서 한가운데가 흰 원이 된다)
    return fo + 0.28 * top + fuzz, fb + 0.20 * top + fuzz


def _face_fields(u, v, head):
    """얼굴 둘레 점수. (face, eyes_nose, far, dh)  face: 주황이 앉을 이마·귀·뺨, eyes_nose: 눈·코·입(검정 금지), far: 머리에서 먼 곳(검정 허용)."""
    if head is None:
        z = np.zeros_like(u)
        return z, z, np.ones_like(u), z + 9.0
    hu, hv, hr = head
    ex, ey = (u - hu) / max(hr, 1e-3), (v - hv) / max(hr, 1e-3)
    wob = 0.30 * (_vnoise(u, v, 9.0, 51) - 0.5) + 0.12 * (_vnoise(u, v, 23.0, 53) - 0.5)
    dh = np.sqrt(ex * ex + ey * ey) + wob
    head_zone = 1.0 - _smooth(dh, 1.0, 1.6)
    nose_mouth = _smooth(ex, 0.25, 0.9) * (1.0 - _smooth(ey, -0.6, 0.1))
    cap = _smooth(-ey - 0.1 * ex + 0.55 * (_vnoise(u, v, 11.0, 61) - 0.5) + 0.25 * (_vnoise(u, v, 27.0, 63) - 0.5), 0.05, 0.60)
    cheek = np.exp(-(((ex + 0.15) / 0.55) ** 2 + ((ey - 0.35) / 0.40) ** 2))
    face = head_zone * np.clip(0.9 * cap + 0.45 * cheek, 0.0, 1.0) * (1.0 - 0.9 * nose_mouth)
    throat = _smooth(v - hv + 0.25 * hr * (_vnoise(u, v, 13.0, 67) - 0.5), 0.55 * hr, 1.05 * hr)
    face = face * (1.0 - throat)
    eyes_nose = 1.0 - _smooth(dh, 0.0, 0.7)
    far = _smooth(dh, 2.0, 3.2)
    return face, eyes_nose, far, dh


def face_down(u, v, head):
    """머리 안에서 '아래쪽(코·입·턱)' 정도 0~1. 머리 중심보다 아래·앞쪽일수록 1."""
    if head is None:
        return np.zeros_like(u)
    hu, hv, hr = head
    ex, ey = (u - hu) / max(hr, 1e-3), (v - hv) / max(hr, 1e-3)
    wob = 0.45 * (_vnoise(u, v, 8.0, 71) - 0.5) + 0.20 * (_vnoise(u, v, 21.0, 73) - 0.5)         # 경계가 일직선(가로 띠)이 되지 않게
    return np.clip(0.9 * _smooth(ey + wob, -0.10, 0.65) + 0.5 * _smooth(ex + wob, 0.30, 0.95) * _smooth(ey, -0.4, 0.2), 0.0, 1.0)


def _rank_pct(score, mask):
    """mask 안의 점수를 0(가장 낮음)~1(가장 높음)의 순위 백분율로 바꾼다. mask 밖은 0."""
    out = np.zeros(score.shape, np.float32)
    vals = score[mask]
    if vals.size == 0:
        return out
    order = np.argsort(np.argsort(vals, kind="stable"), kind="stable")
    out[mask] = (order + 0.5) / vals.size
    return out


def _patches(u, v, ln, head=None, mask=None):
    """삼색 무늬: (검정 정도, 주황 정도). u: 왼→오(0~1), v: 위→아래(0~1), ln: 털 밝기(털결), head: 머리 중심 (u, v, 반지름),
    mask: 털이 있는 곳(몸통 면적의 기준; 없으면 전체).

    **비율을 순위로 정한다**: 몸통에서 얼룩 '자리 점수'가 가장 높은 50%가 주황, 그다음 20%가 검정, 나머지 30%가 흰색이다.
    그래서 자세가 달라도(앉기·눕기·걷기) 몸통의 주황 50%·검정 20%·흰색 30% 가 거의 그대로 나온다.
    흰색은 아랫배·다리 끝·가슴이 되도록 점수에 위쪽(등) 가산점을 둔다. 얼굴은 흰색 바탕에 이마·귀·뺨에만 주황이 앉고, 검정은 얼굴에서 먼 곳에만 앉는다."""
    if mask is None:
        mask = np.ones(u.shape, bool)
    face, eyes_nose, far, dh = _face_fields(u, v, head)
    body = mask & (dh > 1.45)                                        # 몸통: 머리에서 머리 반지름의 1.45배 이상 떨어진 털 (머리 영역은 아래에서 따로)
    so, sb = _patch_fields(u, v, ln, head)
    # --- 주황: 자리 점수의 상위 TARGET_ORANGE ---
    ro = _rank_pct(so, body)
    wo_body = _smooth(ro, 1.0 - (ORANGE_K * TARGET_ORANGE + TARGET_BLACK * 0.55) - 0.015, 1.0 - (ORANGE_K * TARGET_ORANGE + TARGET_BLACK * 0.55) + 0.015) * body   # 검정이 주황 위에 앉아 가져가는 몫(검정의 약 45%)만큼 더 넓게 잡는다
    # --- 검정: 주황이 아닌 곳 중에서도 검정 점수가 높은 곳, 몸통의 TARGET_BLACK (주황과 겹치면 검정이 이긴다) ---
    sb2 = sb - 0.6 * (1.0 - far)
    rb = _rank_pct(sb2, body)
    wb_body = _smooth(rb, 1.0 - TARGET_BLACK * BLACK_K - 0.015, 1.0 - TARGET_BLACK * BLACK_K + 0.015) * body * far
    wo_body = wo_body * (1.0 - wb_body)
    # --- 머리 영역: 위쪽 절반(이마·귀·뺨 위)은 몸과 같은 점수로 주황이 이어지게, 아래쪽(코·입·턱)은 흰색으로 남긴다.
    #     (이전: 머리 둘레를 둥글게 흰색으로 두어 부채꼴 모양의 뿌연 흰 영역이 생겼다) ---
    head_zone = mask & (dh <= 1.45)
    upper = 1.0 - _smooth(face_down(u, v, head), 0.0, 1.0)             # 1: 머리 위쪽(이마·귀), 0: 아래쪽(코·입·턱)
    head_score = so + 0.25 * face
    wo_head = _smooth(head_score, 0.50, 0.56) * upper * (1.0 - 0.6 * eyes_nose) * head_zone
    return wb_body, np.maximum(wo_body, wo_head)


def recolor(arr: np.ndarray, coat: str, uv=None, head=None) -> np.ndarray:
    """arr: (H, W, 4) uint8 (투명도 포함) 사진 컷 → 털색을 coat 로 바꾼 같은 크기 배열.
    uv: 삼색일 때 무늬 위치를 정하는 (u, v) 배열 두 개 (컷마다 몸의 같은 자리에 무늬가 오도록 동작 전체 기준으로 계산해서 넘긴다).
    head: 이 컷의 머리 중심 (u, v, 반지름) (uv 와 같은 좌표계). 삼색에서 얼굴에 주황을 모으고 눈·코·입 주변의 검정을 피하는 데 쓴다."""
    if coat == "brown" or coat not in COAT_KEYS:
        return arr
    rgb = arr[..., :3].astype(np.float32) / 255.0
    w = _fur_weight(rgb)
    if head is not None and uv is not None:
        # 몸통 한가운데에 흩어진 밝은 점(가장자리 정리에서 남은 흰 얼룩)은 털이다. 귀 안쪽·코는 머리 근처에만 있으니, 머리에서 먼 곳은 모두 털로 본다.
        hu, hv, hr = head
        dh = np.sqrt((uv[0] - hu) ** 2 + (uv[1] - hv) ** 2) / max(hr, 1e-3)
        w = np.maximum(w, _smooth(dh, 1.9, 2.6) * (arr[..., 3] > 20))
    luma = 0.299 * rgb[..., 0] + 0.587 * rgb[..., 1] + 0.114 * rgb[..., 2]
    ln = np.clip((luma - 0.08) / 0.80, 0.0, 1.0)
    if coat == "calico":
        wb, wo = _patches(*uv, ln, head, arr[..., 3] > 128) if uv is not None else (np.zeros_like(ln), np.zeros_like(ln))
        lw = 0.15 * ln + 0.85 * _boxblur(ln, 6)                    # 흰 털에는 갈색 줄무늬가 없다: 줄무늬(좁은 어두운 선)를 넓게 흐려서 지운다
        lw = np.clip(0.50 + 0.50 * lw, 0.0, 1.0)                  # 밝은 쪽으로 모으되 몸의 입체감(그림자)은 남긴다
        white = _ramp("calico_white", lw)
        mapped = white * (1 - wb - wo)[..., None] + _ramp("orange", ln) * wo[..., None] + _ramp("calico_black", ln) * wb[..., None]
    else:
        mapped = _ramp(coat, ln)
    out = rgb * (1 - w[..., None]) + mapped * w[..., None]
    res = arr.copy()
    res[..., :3] = np.clip(out * 255.0 + 0.5, 0, 255).astype(np.uint8)
    return res


EYE_RX, EYE_RY = 4.4, 3.5                    # 저장 픽셀: 눈(홍채+동공) 반지름
_IRIS = ([0.0, 0.35, 0.70, 1.0], [(0.20, 0.21, 0.07), (0.50, 0.53, 0.16), (0.72, 0.75, 0.27), (0.88, 0.90, 0.50)])   # 어두운 올리브 → 연두빛 노랑 (사진에 어울리게 너무 쨍하지 않게)


def paint_eyes(arr: np.ndarray, orig: np.ndarray, eyes) -> np.ndarray:
    """털색을 바꾼 그림(arr)의 눈 자리에 털색과 상관없이 같은 또렷한 눈을 다시 그린다 (갈색도 더 또렷하게).
    털색을 바꿀 때 노란 홍채가 털로 칠해져 검은·흰·삼색 고양이의 눈이 안 보였다.
    orig: 털색을 바꾸기 전 원본. 동공·테두리·홍채의 밝기 무늬는 원본에서 가져온다. eyes: [(x, y)] 저장 픽셀 (tools/eye_marks.py 가 찾음).
    arr, orig: (H, W, 4) uint8. 같은 크기의 새 배열을 돌려준다."""
    out = arr.copy()
    h, w = arr.shape[:2]
    for ex, ey in eyes:
        x0, x1 = max(0, int(ex - EYE_RX - 5)), min(w, int(ex + EYE_RX + 6))
        y0, y1 = max(0, int(ey - EYE_RY - 5)), min(h, int(ey + EYE_RY + 6))
        if x1 <= x0 or y1 <= y0:
            continue
        ys, xs = np.mgrid[y0:y1, x0:x1].astype(np.float32)
        e = ((xs - ex) / EYE_RX) ** 2 + ((ys - ey) / EYE_RY) ** 2
        src = orig[y0:y1, x0:x1].astype(np.float32) / 255.0
        lum = 0.299 * src[..., 0] + 0.587 * src[..., 1] + 0.114 * src[..., 2]
        solid = _smooth(src[..., 3], 0.4, 0.8)
        inside = e < 1.0
        if inside.sum() < 6:
            continue
        lo, hi = np.percentile(lum[inside], 8), np.percentile(lum[inside], 92)
        t = np.clip((lum - lo) / max(hi - lo, 0.05), 0.0, 1.0)            # 눈 안에서의 밝기 순서 (0 = 가장 어두움, 1 = 홍채의 가장 밝은 곳)
        # 동공: 눈 가운데 쪽에서 원본이 가장 어두운 곳의 무게중심(보는 방향을 따른다)에 둥근 동공을 그린다.
        # (어두운 곳을 그대로 동공으로 칠하면 눈 가장자리의 진한 테두리까지 이어져 초승달 모양이 됐다)
        core = (e < 0.55) * np.clip(0.45 - lum, 0.0, None) ** 2
        if core.sum() > 1e-5:
            px, py = float((xs * core).sum() / core.sum()), float((ys * core).sum() / core.sum())
        else:
            px, py = ex, ey
        px = min(max(px, ex - 0.45 * EYE_RX), ex + 0.45 * EYE_RX)
        py = min(max(py, ey - 0.40 * EYE_RY), ey + 0.40 * EYE_RY)
        pe = ((xs - px) / (0.42 * EYE_RX)) ** 2 + ((ys - py) / (0.72 * EYE_RY)) ** 2
        pupil = 1.0 - _smooth(pe, 0.55, 1.0)
        iris = _ramp_custom(_IRIS, 0.45 + 0.55 * t)                         # 홍채 결은 원본 밝기 무늬를 살리되 밝은 쪽으로 모은다
        col = iris * (1.0 - pupil[..., None]) + np.array([0.035, 0.03, 0.025], np.float32) * pupil[..., None]
        he = ((xs - (px - 0.32 * EYE_RX)) / 0.95) ** 2 + ((ys - (py - 0.38 * EYE_RY)) / 0.95) ** 2   # 반짝임 (눈에 생기)
        hl = (1.0 - _smooth(he, 0.25, 1.0)) * 0.70
        col = col * (1.0 - hl[..., None]) + np.array([0.97, 0.97, 0.94], np.float32) * hl[..., None]
        wi = (1.0 - _smooth(e, 0.60, 0.95)) * solid                        # 눈 안 (가장자리는 부드럽게)
        cur = out[y0:y1, x0:x1, :3].astype(np.float32) / 255.0
        cur = cur * (1.0 - wi[..., None]) + col * wi[..., None]
        # 눈 둘레의 진한 테두리: 원본에서 어두웠던 곳은 털색과 상관없이 진하게 (흰·삼색 털 위에서도 눈 모양이 또렷하게)
        wr = _smooth(e, 0.7, 1.0) * (1.0 - _smooth(e, 1.6, 2.4)) * _smooth(0.42 - lum, 0.0, 0.16) * solid
        cur = cur * (1.0 - wr[..., None]) + np.array([0.06, 0.05, 0.04], np.float32) * wr[..., None]
        out[y0:y1, x0:x1, :3] = np.clip(cur * 255.0 + 0.5, 0, 255).astype(np.uint8)
    return out


def _ramp_custom(ramp, x):
    xs, cs = ramp
    cs = np.array(cs, np.float32)
    return np.stack([np.interp(x, xs, cs[:, k]) for k in range(3)], axis=-1).astype(np.float32)


def uv_grid(h: int, w: int, cx: float, max_l: float, max_r: float, union_h: float):
    """한 컷의 각 픽셀이 동작 전체(모든 컷의 합친 범위) 안에서 어디쯤인지: (u, v). 컷이 달라도 몸의 같은 자리는 같은 값."""
    xs = (np.arange(w, dtype=np.float32) - cx + max_l) / max(max_l + max_r, 1.0)
    ys = 1.0 - (h - np.arange(h, dtype=np.float32)) / max(union_h, 1.0)
    return np.meshgrid(xs, ys)
