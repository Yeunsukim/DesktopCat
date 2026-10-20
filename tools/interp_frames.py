"""컷 사이에 '가짜 중간 컷'을 만든다. (개발용: OpenCV 필요, 앱에는 들어가지 않음)

두 컷의 같은 부분(다리, 머리, 몸)이 어디로 움직였는지를 '광학 흐름(optical flow)'으로 계산한 뒤,
각 컷을 그 방향으로 중간까지 끌어와서 겹쳐 중간 자세를 만든다. 컷 사이를 단순히 겹치는 것(크로스페이드)과 달리
다리가 움직이는 모습이 이어져서 두 자세가 겹쳐 보이는 잔상이 생기지 않는다.

잘 안 되는 경우(꼬리가 위로 확 올라가는 컷, 다리가 교차하는 컷)는 중간 컷이 흐려지거나 일그러지므로,
컷 사이 차이가 너무 크면(MAX_GAP) 중간 컷을 만들지 않고 건너뛴다.
"""
import cv2
import numpy as np

MAX_GAP = 0.45       # 두 컷의 실루엣 불일치(0~1)가 이보다 크면 흐름 계산이 믿을 수 없으니 중간 컷을 만들지 않는다


def _to_canvas(img, cx, W, H, maxL):
    """RGBA 컷을 몸 중심(cx)과 바닥 기준으로 공통 캔버스에 올린다. 곱해진 알파(premultiplied) float32 로 돌려준다."""
    a = np.asarray(img, np.float32) / 255.0
    a[..., :3] *= a[..., 3:4]
    h, w = a.shape[:2]
    x0 = int(round(maxL - cx))
    y0 = H - h
    can = np.zeros((H, W, 4), np.float32)
    can[y0:y0 + h, x0:x0 + w] = a
    return can


def _gray(can):
    rgb = can[..., :3] + (1.0 - can[..., 3:4]) * 0.5            # 회색 바탕에 얹은 모습
    g = (rgb[..., 0] * 0.299 + rgb[..., 1] * 0.587 + rgb[..., 2] * 0.114)
    return np.clip(g * 255, 0, 255).astype(np.uint8)


def _flow(g0, g1):
    dis = cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_MEDIUM)
    dis.setFinestScale(0)
    return dis.calc(g0, g1, None)


def _warp(can, flow, t):
    H, W = flow.shape[:2]
    gx, gy = np.meshgrid(np.arange(W, dtype=np.float32), np.arange(H, dtype=np.float32))
    return cv2.remap(can, gx + flow[..., 0] * t, gy + flow[..., 1] * t, cv2.INTER_LINEAR,
                     borderMode=cv2.BORDER_CONSTANT, borderValue=0)


def gap(c0, c1):
    """두 컷이 얼마나 다른지 (겹치는 영역 밖의 비율, 0~1)."""
    m0, m1 = c0[..., 3] > 0.5, c1[..., 3] > 0.5
    u = np.logical_or(m0, m1).sum()
    return float(np.logical_xor(m0, m1).sum() / max(u, 1))


def between(c0, c1, ts):
    """c0 → c1 사이의 여러 시점 t(0~1)의 중간 컷들 (premultiplied 캔버스)."""
    g0, g1 = _gray(c0), _gray(c1)
    f01, f10 = _flow(g0, g1), _flow(g1, g0)
    out = []
    for t in ts:
        a = _warp(c0, f10, t)                  # c0 를 c1 쪽으로 t 만큼 (반대 방향 흐름으로 되가져 옴)
        b = _warp(c1, f01, 1.0 - t)            # c1 을 c0 쪽으로 (1-t) 만큼
        out.append(a if t < 0.5 else b)        # 두 컷을 섞으면 어긋난 곳이 희미하게 이중으로 보이는 잔상이 되므로, 가까운 쪽 컷 한 장만 쓴다
    return out


def _unpremul(can):
    al = np.clip(can[..., 3:4], 0, 1)
    rgb = can[..., :3] / np.maximum(al, 1e-4)
    # 알파를 살짝 또렷하게 (두 컷을 섞은 가장자리가 흐려지지 않게)
    al2 = np.clip((al - 0.12) / 0.76, 0, 1)
    out = np.concatenate([np.clip(rgb, 0, 1), al2], -1)
    return (out * 255 + 0.5).astype(np.uint8)


def expand(frames, infos, mult, cyclic):
    """frames: RGBA PIL 컷 목록, infos: [{'cx','hx','hy'}], mult: 컷 하나를 몇 개로 늘릴지(2면 중간 1장, 3이면 2장).
    cyclic 이면 마지막 → 처음 사이에도 만든다.
    돌려주는 것: (컷 목록, 정보 목록, 건너뛴 구간 번호 목록). 정보는 w,h,cx,hx,hy (cx 는 저장한 컷 기준)."""
    maxL = max(i["cx"] for i in infos)
    maxR = max(f.width - i["cx"] for f, i in zip(frames, infos))
    H = max(f.height for f in frames)
    W = int(np.ceil(maxL + maxR)) + 2
    cans = [_to_canvas(f, i["cx"], W, H, maxL) for f, i in zip(frames, infos)]
    n = len(frames)
    pairs = [(i, (i + 1) % n) for i in range(n)] if cyclic else [(i, i + 1) for i in range(n - 1)]
    ts = [k / mult for k in range(1, mult)]
    out_cans, out_inf, skipped = [], [], []
    for i in range(n):
        out_cans.append(cans[i])
        out_inf.append(dict(infos[i], _canvas=True))
        pair = next((p for p in pairs if p[0] == i), None)
        if pair is None:
            continue
        j = pair[1]
        if gap(cans[i], cans[j]) > MAX_GAP:
            skipped.append(i)
            for _ in ts:                                   # 건너뛴 구간은 앞 컷을 그대로 반복해서 길이(시간)를 맞춘다
                out_cans.append(cans[i])
                out_inf.append(dict(infos[i], _canvas=True))
            continue
        for t, mid in zip(ts, between(cans[i], cans[j], ts)):
            out_cans.append(mid)
            out_inf.append({"cx": infos[i]["cx"] + (infos[j]["cx"] - infos[i]["cx"]) * t,
                            "hx": infos[i]["hx"] + (infos[j]["hx"] - infos[i]["hx"]) * t,
                            "hy": infos[i]["hy"] + (infos[j]["hy"] - infos[i]["hy"]) * t, "_canvas": True})
    res_f, res_i = [], []
    from PIL import Image
    for can, inf in zip(out_cans, out_inf):
        rgba = _unpremul(can)
        ys, xs = np.where(rgba[..., 3] > 6)
        if not len(ys):
            continue
        x0, x1, y0, y1 = xs.min(), xs.max() + 1, ys.min(), H            # 아래쪽은 바닥(발바닥) 기준선이라 자르지 않는다
        res_f.append(Image.fromarray(rgba[y0:y1, x0:x1], "RGBA"))
        # 캔버스 안에서 몸 중심은 maxL (그리고 컷을 자르면서 x0 만큼 줄어듦)
        res_i.append({"cx": float(maxL - x0), "hx": inf["hx"], "hy": inf["hy"]})
    return res_f, res_i, skipped
