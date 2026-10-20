"""컷 사이 모양 차이(실루엣이 얼마나 다른지, 0~1)를 재서 assets/sprites/sprites.json 의 각 동작에 'gaps' 로 저장한다. (개발용)

gaps[i] = i 번째 컷과 다음 컷((i+1) % n) 사이의 차이. 앱(photocat.py)은 차이가 작은 쌍만 서로 섞어서 보여 주고,
큰 쌍(걷기 다리처럼 많이 움직인 곳)은 섞으면 두 자세가 겹쳐 안개 같은 잔상이 되므로 선명하게 바꾼다.
누운 자세(LYING)에는 'rest' 도 저장한다: 단단한 맨 아래(뻗은 앞발 끝 등)보다 몸 아랫선이 몇 줄 위인지(저장 픽셀, 컷들의 중앙값).
앱은 그만큼 더 내려 그려서 몸이 바닥에 닿게 한다(발은 작업 표시줄 쪽으로 내려간다).
사용: python tools/frame_gaps.py            (build_sprites.py 가 끝에서 자동으로 부른다)
"""
import json
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SP = ROOT / "assets" / "sprites"


def silhouette_gap(a, b):
    """두 컷을 발바닥 높이와 몸 중심에 맞춰 겹쳤을 때, 서로 다른 곳의 비율(합집합 대비)."""
    ma, mb = a[0] > 128, b[0] > 128
    ca, cb = a[1], b[1]
    L = int(max(ca, cb)) + 2
    R = int(max(ma.shape[1] - ca, mb.shape[1] - cb)) + 2
    H = max(ma.shape[0], mb.shape[0])
    W = L + R

    def put(m, c):
        can = np.zeros((H, W), bool)
        x0 = int(round(L - c))
        can[H - m.shape[0]:, x0:x0 + m.shape[1]] = m
        return can

    pa, pb = put(ma, ca), put(mb, cb)
    u = np.logical_or(pa, pb).sum()
    return float(np.logical_xor(pa, pb).sum() / max(u, 1))


LYING = ("loaf", "sleep_curl", "sleep_side", "sleep_nap", "bunny")


def rest_gap(alpha):
    """단단한 맨 아래 줄보다 '몸 아랫선'(바닥 가까이 닿은 열들의 아래 끝 중앙값)이 몇 줄 위인지 (저장 픽셀)."""
    solid = alpha >= 170
    rows = np.where(solid.sum(axis=1) >= 5)[0]
    cols = np.where(solid.sum(axis=0) >= 6)[0]                 # 몸이 있는 열 (가는 꼬리 끝·수염은 뺀다)
    if not len(rows) or not len(cols):
        return 0.0
    low = rows.max()
    bottoms = np.array([np.where(solid[:, c])[0].max() for c in cols])
    near = bottoms[bottoms >= low - 40]                        # 바닥 근처에 닿아 있는 열만 (들어 올린 다리·꼬리는 빼고)
    return float(low - np.median(near)) if len(near) else 0.0


def main():
    meta = json.loads((SP / "sprites.json").read_text(encoding="utf-8"))
    for key, act in meta["actions"].items():
        fr = act["frames"]
        loaded, rests = [], []
        for i, f in enumerate(fr):
            a = np.array(Image.open(SP / key / f"f{i}.png"))[..., 3]
            sm = a[::2, ::2]                                       # 절반 해상도로 충분하다
            loaded.append((sm, f["cx"] / 2.0))
            if key in LYING:
                rests.append(rest_gap(a))
        n = len(fr)
        act["gaps"] = [round(silhouette_gap(loaded[i], loaded[(i + 1) % n]), 3) for i in range(n)]
        if rests:
            act["rest"] = round(float(np.median(rests)), 1)       # 컷마다 다르게 하면 위아래로 출렁거리므로 동작마다 한 값
        else:
            act.pop("rest", None)
    (SP / "sprites.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    return meta


if __name__ == "__main__":
    m = main()
    for k, a in sorted(m["actions"].items()):
        g = a["gaps"]
        print(f"{k:13s} 컷 {len(g):2d}  차이 평균 {np.mean(g):.3f}  최대 {max(g):.3f}  (0.09 이하인 쌍 {sum(1 for x in g if x <= 0.09)}/{len(g)})")
