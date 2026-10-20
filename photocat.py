"""실사 사진 고양이: 동작마다 미리 만들어 둔 사진 컷(assets/sprites)을 골라서 그린다.

뼈대 방식(catrig.py)과 같은 자리에 끼워 쓴다. 고양이가 무엇을 하는지(동작 이름·경과 시간·걸음 위상)는 CatBrain/Animator 가 그대로 정하고,
여기서는 그 동작에 맞는 사진 컷 번호를 계산해서 컷 사이를 부드럽게 섞어 그린다.

 - 컷은 시작할 때가 아니라 처음 쓸 때 만든다(실제 화면 크기로 줄이고, 털색을 바꿨으면 그 색으로 칠한다).
 - 동작이 바뀔 때는 직전 그림에서 새 그림으로 서서히 바뀐다.
 - 털실공·밥그릇·방석 같은 소품과 바닥 그림자는 사진에 없어서 여기서 그린다.
"""
import json
import random
import math
import time
from pathlib import Path

import numpy as np
from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import (QBrush, QColor, QImage, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap,
                         QRadialGradient)

import coats

OUTLINE = QColor(70, 60, 55)


def _smooth(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


def _pingpong(x, lo, hi):
    """lo..hi 사이를 왔다갔다 하는 컷 번호 (끝에서 튀지 않게)."""
    span = hi - lo
    if span <= 0:
        return float(lo)
    m = x % (2 * span)
    return lo + (m if m <= span else 2 * span - m)


def _interp(x, xs, ys):
    return float(np.interp(x, xs, ys))


# 걸음: 사진 컷이 한 바퀴(컷 전체) 도는 동안 고양이가 이동하는 거리(뼈대 단위).
# 발이 땅을 밀 때 땅에 대고 미끄러지지 않으려면 한 바퀴 거리가 '발이 뒤로 가는 폭(≈30) ÷ 땅에 닿는 시간 비율(≈0.6)' 정도여야 한다.
# Animator 의 걸음 위상(u)은 뼈대 걸음 주기(walk 54.8, trot 92, run 194, sneak 30.6)에 맞춰져 있어서, 그 비율로 바꿔 쓴다.
_RIG_CYCLE = {"walk": 54.8, "trot": 92.0, "run": 194.0, "sneak": 30.6}
_SPRITE_CYCLE = {"walk": 70.0, "trot": 70.0, "run": 150.0, "sneak": 36.0}
_GAIT_RATIO = {k: _RIG_CYCLE[k] / _SPRITE_CYCLE[k] for k in _RIG_CYCLE}
_GAIT_KEY = {"walk": "walk", "trot": "trot", "run": "run", "sneak": "sneak"}

# 공중 자세(발이 바닥에 닿지 않는 컷)는 바닥에 맞춰 내리지 않는다
_AIRBORNE = {"jump_up", "jump_down", "hold", "hop"}
MAX_DROP = 4.0                                    # 안전장치: 한 컷을 이보다 많이 내려 그리지 않는다 (논리 픽셀)
# 바닥(작업 표시줄 윗변·창 윗변)에 발을 딱 맞추면 오히려 떠 보인다: 발을 바닥 쪽으로 조금 걸쳐 그린다 (논리 픽셀).
SINK = 2.5
# 누운 자세는 사진 각도 때문에 뻗은 앞발 끝이 맨 아래이고 배는 그보다 위에 있다: 몸 아랫선이 바닥에 닿도록 더 내린다
# (sprites.json 의 동작별 'rest' = 맨 아래보다 몸 아랫선이 몇 줄 위인지, tools/frame_gaps.py 가 잰다). 그만큼 앞발은 작업 표시줄 쪽으로 내려간다.
REST_SHARE, REST_MAX = 0.9, 8.0


def _foot_gap_rows(img) -> int:
    """컷 그림 맨 아래 줄과 '단단한 몸이 있는 맨 아래 줄' 사이의 빈 줄 수 (옅은 번짐 가장자리는 무시한다)."""
    ptr = img.constBits()
    ptr.setsize(img.sizeInBytes())
    al = np.frombuffer(ptr, np.uint8).reshape(img.height(), img.width(), 4)[:, :, 3]
    rows = np.where((al >= 170).sum(axis=1) >= 5)[0]
    return int(img.height() - 1 - rows.max()) if len(rows) else 0


# 가만히 쉬는 자세: 짧은 영상을 앞뒤로 되감듯 쉬지 않고 왔다갔다 하면 머리가 기계처럼 끄덕인다.
# 실제 고양이처럼 대부분 가만히 있다가(HOLD 초) 가끔 이웃 컷으로 천천히 옮겨 간다 (컷 사이는 부드럽게 섞인다).
_DRIFT = {"stand", "sit", "sit_tilt", "loaf"}
DRIFT_HOLD = (1.2, 4.0)                   # 초: 한 자세로 가만히 있는 시간
DRIFT_FPS = 1.6                           # 옮겨 갈 때의 속도 (초당 컷)
# 서서 쉬는 자세 등: 컷 사이를 왔다갔다 (초당 컷 수)
_PINGPONG = {"stand": ("stand", 1.2), "sit": ("sit", 1.0), "sit_tilt": ("sit_tilt", 1.0), "loaf": ("loaf", 0.9),
             "sleep_curl": ("sleep_curl", 0.7), "sleep_side": ("sleep_side", 0.7), "sleep_nap": ("sleep_nap", 0.7),
             "hold": ("hold", 2.5), "wiggle": ("wiggle", 5.0)}
# 한 바퀴 계속 도는 동작 (초당 컷 수)
# (몸단장은 천천히, 긁기·꾹꾹이·뒷발킥처럼 원래 빠른 동작은 상대적으로 빠르게)
_LOOP = {"sleep_doze": ("sleep_doze", 0.8), "groom": ("groom", 1.9), "groom_leg": ("groom_leg", 1.6),
         "scratch_neck": ("scratch_neck", 2.2), "groom_face": ("groom_face", 1.7), "scratch": ("scratch", 3.4),
         "knead": ("knead", 6.0), "tail_play": ("tail_play", 2.6), "bunny": ("bunny", 6.5)}


# 컷 사이 자세 차이가 작아서 계속 부드럽게 섞어도 잔상이 안 보이는 동작 (그 밖의 동작은 선명하게 보여 주다가 바뀔 때만 섞는다)
_SOFT_BLEND = {"stand", "sit", "sit_tilt", "loaf", "sleep_curl", "sleep_side", "sleep_nap", "yawn", "stretch", "eat", "stroke"}


# 컷 사이 섞기: 두 컷의 실루엣 차이(tools/frame_gaps.py 가 재서 sprites.json 에 'gaps' 로 저장)가 GAP_FULL 이하면 컷 사이를 처음부터 끝까지 섞고,
# GAP_ZERO 이상이면 섞지 않고 선명하게 바꾼다(섞으면 두 자세가 겹쳐 안개 같은 잔상이 된다). 그 사이는 컷 사이 시간의 뒷부분에서만 섞는다.
GAP_FULL, GAP_ZERO = 0.04, 0.09          # (이전 0.07/0.16: 차이가 큰 컷까지 섞어서 잔상이 길게 보였다)
BLEND_SPAN = 0.45                          # 컷 사이 시간 중 섞는 구간의 최대 비율 (뒤쪽에서만 섞고 앞쪽은 선명하게 보여 준다)
# 동작이 바뀔 때(걷기→쉬기 등) 직전 그림이 사라지고 새 그림이 나타나는 시간(초). 점프·착지처럼 빠른 동작으로 바뀔 때는 짧게 한다.
TRANS_SEC, TRANS_FAST = 0.10, 0.05          # (이전 0.22/0.09: 걷던 고양이 위에 새 자세가 오래 겹쳐 보였다)
_FAST_KEYS = {"jump_up", "jump_down", "land", "crouch", "hold", "swat", "bat", "hop", "bunny", "wiggle"}


class _Frame:
    __slots__ = ("pm", "w", "h", "cx", "hx", "hy", "drop")

    def __init__(self, pm, w, h, cx, hx, hy, drop=0.0):
        self.pm, self.w, self.h, self.cx, self.hx, self.hy, self.drop = pm, w, h, cx, hx, hy, drop
        # drop: 이 컷을 아래로 더 내려 그릴 거리(논리 픽셀). 컷 그림의 맨 아래와 단단한 발바닥 사이의 빈 줄만큼 내려서 발이 바닥에 딱 닿게 한다


class PhotoRig:
    """CatRig 와 같은 자리에 끼우는 사진 고양이 그리개."""

    def __init__(self, folder: Path, coat: str = "brown", dpr: float = 1.0, scale: float = 0.8):
        meta = json.loads((Path(folder) / "sprites.json").read_text(encoding="utf-8"))
        self.dir = Path(folder)
        self.store = float(meta["store"])
        self.meta = meta["actions"]
        self.coat = coat if coat in coats.COAT_KEYS else "brown"
        self.dpr = dpr
        self.sc = scale
        self._cache: dict[tuple[str, int], _Frame] = {}
        self._union = {}
        for k, a in self.meta.items():                     # 삼색 무늬가 컷마다 몸의 같은 자리에 오도록 동작별로 전체 범위를 잰다
            fr = a["frames"]
            self._union[k] = (max(f["cx"] for f in fr), max(f["w"] - f["cx"] for f in fr), max(f["h"] for f in fr))
        for k in self.meta:
            if not (self.dir / k / "f0.png").exists():
                raise FileNotFoundError(k)
        self.gaps = {k: a.get("gaps") for k, a in self.meta.items()}
        u = self.sc / self.store
        self.sinks = {k: 0.0 if k in _AIRBORNE else SINK + min(REST_MAX, float(a.get("rest", 0.0)) * u * REST_SHARE) for k, a in self.meta.items()}
        self.sink_now = SINK                              # 방금 그린 컷을 바닥 쪽으로 내린 양 (쥐 그림 등 바닥에 놓는 것을 같은 높이에 맞추는 데 쓴다)
        self._cur_key = None
        self._cur_face = None
        self._drift = None                                # 가만히 쉬는 자세의 컷 위치 (_drift_pos)
        self._trans = None                                # (시작 시각, 길이, 직전 그림 {layers, face})
        self._last = None                                 # 방금 그린 그림: 동작이 바뀔 때 서서히 사라지게 하려고 기억해 둔다
        self._phase = 0.0
        self._last_u = 0.0
        self._last_bt = 1.0
        self._prev_name = None
        self._head = (30.0, 90.0)
        self._pose_idx = (0, 0, 0.0)
        self.detail = 1.0                                 # (CatRig 와 같은 자리: 여기서는 쓰지 않음)

    # ------------------------------------------------------------ 털색
    def set_coat(self, coat: str):
        if coat in coats.COAT_KEYS and coat != self.coat:
            self.coat = coat
            self._cache.clear()
            self._last, self._trans = None, None

    # ------------------------------------------------------------ 컷 만들기
    def _frame(self, key: str, i: int) -> _Frame:
        n = len(self.meta[key]["frames"])
        i = max(0, min(n - 1, i))
        f = self._cache.get((key, i))
        if f is not None:
            return f
        m = self.meta[key]["frames"][i]
        img = QImage(str(self.dir / key / f"f{i}.png"))
        if img.isNull():                                   # 파일이 없거나 읽는 중이면(예: 컷을 다시 만드는 중) 죽지 않고 이미 불러온 가까운 컷을 대신 쓴다
            near = [v for (k2, i2), v in self._cache.items() if k2 == key]
            if near:
                return near[0]
            raise FileNotFoundError(f"{key}/f{i}.png")
        img = img.convertToFormat(QImage.Format.Format_RGBA8888)
        gap_rows = 0 if key in _AIRBORNE else _foot_gap_rows(img)       # (털색을 바꾸기 전 원본의 투명도로 잰다)
        eyes = m.get("eyes")                               # 눈 자리 (tools/eye_marks.py 가 sprites.json 에 넣어 둔다)
        if self.coat != "brown" or eyes:
            ptr = img.constBits()
            ptr.setsize(img.sizeInBytes())
            orig = np.frombuffer(ptr, np.uint8).reshape(img.height(), img.width(), 4).copy()
            arr = orig
        if self.coat != "brown":
            ml, mr, uh = self._union[key]
            uv = coats.uv_grid(img.height(), img.width(), m["cx"], ml, mr, uh) if self.coat == "calico" else None
            head = None
            if uv is not None:
                # 얼굴 중심: 머리 꼭대기(m["hx"], m["hy"]; 몸 중심에서 앞쪽·바닥에서 위쪽, 저장 픽셀)에서 귀 끝~얼굴 중심 거리만큼 아래로
                st = self.store
                ml, mr, uh = self._union[key]
                fx = m["cx"] + m["hx"] - 6.0 * st                          # 컷 안 가로: 머리 꼭대기보다 조금 뒤(귀는 얼굴 뒤쪽에 있다)
                fy = img.height() - m["hy"] + 26.0 * st                    # 컷 안 세로(위→아래): 귀 끝에서 약 26 아래가 얼굴 중심
                hu = (fx - m["cx"] + ml) / max(ml + mr, 1.0)
                hv = 1.0 - (img.height() - fy) / max(uh, 1.0)
                hr = 26.0 * st / max(ml + mr, 1.0)
                head = (hu, hv, hr)
            arr = coats.recolor(arr, self.coat, uv, head)
        if eyes:
            arr = coats.paint_eyes(arr, orig, eyes)                       # 털색과 상관없이 같은 또렷한 눈 (털색을 바꿀 때 눈까지 털로 칠해졌다)
        if self.coat != "brown" or eyes:
            arr = np.ascontiguousarray(arr)
            img = QImage(arr.data, arr.shape[1], arr.shape[0], arr.shape[1] * 4, QImage.Format.Format_RGBA8888).copy()
        img = img.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
        ks = self.sc * self.dpr / self.store
        tw, th = max(1, round(img.width() * ks)), max(1, round(img.height() * ks))
        img = img.scaled(tw, th, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
        pm = QPixmap.fromImage(img)
        pm.setDevicePixelRatio(self.dpr)
        u = self.sc / self.store                           # 저장 픽셀 → 화면(논리) 픽셀
        f = _Frame(pm, m["w"] * u, m["h"] * u, m["cx"] * u, m["hx"] / self.store, m["hy"] / self.store,
                   min(MAX_DROP, gap_rows * u + (0.0 if gap_rows == 0 else 0.3)))
        self._cache[(key, i)] = f
        return f

    # ------------------------------------------------------------ 어떤 컷을 보여줄지
    def _n(self, key):
        """원래(사진) 컷 수. 중간 컷을 만든 동작은 저장된 컷이 이보다 mult 배 많다."""
        return self.meta[key].get("orig", len(self.meta[key]["frames"]))

    def _select(self, name, an):
        """(사진 이름, 컷 번호(소수), 끝에서 처음으로 이어지는가). 소수 부분은 다음 컷과 섞는 비율이다."""
        t = an.t
        if name in _GAIT_RATIO:
            key = _GAIT_KEY[name]
            du = (an.u - self._last_u) % 1.0
            self._phase = (self._phase + du * _GAIT_RATIO[name]) % 1.0
            self._last_u = an.u
            return key, self._phase * self._n(key), True
        if name in _DRIFT and name in self.meta:
            return name, self._drift_pos(name, t), False
        if name in _PINGPONG:
            key, fps = _PINGPONG[name]
            return key, _pingpong(t * fps, 0, self._n(key) - 1), False
        if name in _LOOP:
            key, fps = _LOOP[name]
            return key, (t * fps) % self._n(key), True
        if name == "crouch":
            return "crouch", 2.0 + 3.0 * _smooth(t / 0.28), False
        if name == "jump":
            p = max(0.0, min(1.0, an.param.get("p", 0.0)))
            key = "jump_down" if an.param.get("down") else "jump_up"
            return key, p * (self._n(key) - 1), False
        if name == "hop":
            p = max(0.0, min(1.0, an.param.get("p", 0.0)))
            return "hop", p * (self._n("hop") - 1), False
        if name == "fall":                                           # 떨어지기 시작: 도약 컷 → 이후에는 머리 숙인 떨어지는 컷들을 왔다갔다
            idx = 2.0 + min(t * 2.5, 1.0) if t < 0.4 else _pingpong((t - 0.4) * 5.0, 3, 5)
            return "jump_down", idx, False
        if name == "land":
            return "land", min(5.0, t * 18.0), False
        if name == "yawn":
            return "yawn", _smooth(t / 2.4) * (self._n("yawn") - 1), False
        if name == "stretch":
            return "stretch", _smooth(t / 3.6) * (self._n("stretch") - 1), False
        if name == "eat":
            return "eat", _pingpong(t * 2.4, 1, self._n("eat") - 1), False
        if name == "swat":
            return "swat", _interp(t, (0.0, 0.26, 0.36, 0.9), (0.0, 2.0, 3.4, 5.0)), False
        if name == "bat":
            return "bat", _interp(t, (0.0, 0.24, 0.34, 0.7), (0.0, 2.0, 3.3, 5.0)), False
        if name == "stroke":
            n = self._n("stroke")
            return "stroke", (min(float(n - 1), t * 2.5) if t < 1.6 else _pingpong((t - 1.6) * 3.0, n - 2, n - 1)), False
        return "stand", _pingpong(t * 1.2, 0, self._n("stand") - 1), False

    def _drift_pos(self, key, t):
        """가만히 쉬는 자세의 컷 위치(소수): 한동안 가만히 있다가 이웃 컷으로 천천히 옮겨 간다."""
        n = self._n(key)
        st = self._drift
        if st is None or st["key"] != key or t < st["t"]:                  # 새로 이 자세가 됐다
            st = self._drift = {"key": key, "pos": 0.0, "goal": 0.0, "t": t, "until": t + random.uniform(*DRIFT_HOLD)}
        dt, st["t"] = t - st["t"], t
        if t >= st["until"] and n > 1:
            if abs(st["goal"] - st["pos"]) < 1e-6:                         # 다음에 갈 컷: 이웃 1~2 컷 (맨 처음 컷 쪽으로 조금 더 자주)
                g = round(st["pos"]) + random.choice((-2, -1, -1, 1, 2))
                st["goal"] = float(min(max(g, 0), n - 1))
                if st["goal"] == st["pos"]:
                    st["goal"] = float(min(max(round(st["pos"]) + (1 if st["pos"] < n - 1 else -1), 0), n - 1))
            d = st["goal"] - st["pos"]
            step = DRIFT_FPS * dt
            if abs(d) <= step:
                st["pos"] = st["goal"]
                st["until"] = t + random.uniform(*DRIFT_HOLD)
            else:
                st["pos"] += step if d > 0 else -step
        return st["pos"]

    def _pick(self, key, idx, wrap):
        """원래 컷 단위의 위치(idx)를 저장된 컷 번호 두 개와 섞는 비율로 바꾼다. 비율은 두 컷 사이 차이가 클수록 0 에 가깝게(선명하게) 줄인다."""
        total = len(self.meta[key]["frames"])
        pos = idx * self.meta[key].get("mult", 1)
        i0 = int(math.floor(pos))
        fr = pos - i0
        i0 = i0 % total if wrap else max(0, min(total - 1, i0))
        i1 = (i0 + 1) % total if wrap else min(total - 1, i0 + 1)
        if i1 == i0:
            return i0, i0, 0.0
        g = self.gaps.get(key)
        gp = g[i0] if g and i0 < len(g) else 1.0
        w = BLEND_SPAN * max(0.0, min(1.0, (GAP_ZERO - gp) / (GAP_ZERO - GAP_FULL)))      # 차이가 작을수록 섞는 구간이 길고(최대 BLEND_SPAN), 크면 0 (섞지 않음)
        if w <= 0.0:
            return i0, i0, 0.0
        k = max(0.0, min(1.0, (fr - (1.0 - w)) / w))                          # 컷 사이 시간의 뒤쪽 w 만큼에서만 섞는다 (다음 컷이 시작될 때 끊김이 없게 끝에서 1 이 된다)
        return i0, i1, k * k * (3 - 2 * k)

    @property
    def busy(self):
        """동작이 바뀌는 중이면 True: 그동안은 매 프레임 그려야 부드럽다."""
        return self._trans is not None

    # ------------------------------------------------------------ 그리기
    def draw(self, p: QPainter, brain, origin, room=None):
        """origin: 발바닥 중심의 화면 좌표(논리 픽셀). brain: CatBrain.
        room: 바닥 아래로 그릴 수 있는 공간(논리 픽셀). 작업 표시줄이 없는 화면 맨 아래에서는 0 이라 발을 내려 그리지 않는다."""
        an = brain.an
        face = brain.facing
        d = self.dpr
        try:
            key, idx, wrap = self._select(an.name, an)
        except KeyError:                                   # (컷 수를 세다가) 컷 정보에 없는 동작을 만났다
            key = None
        if key not in self.meta:                           # 컷 정보에 없는 동작이면 죽지 않고 서 있는 사진으로 대신한다
            key, idx, wrap = "stand", 0.0, False
        i0, i1, fr = self._pick(key, idx, wrap)
        a, b = self._frame(key, i0), self._frame(key, i1)
        self._pose_idx = (min(i0, 5), min(i1, 5), fr)               # (공 위치 계산용: 털실공4 는 6컷)
        self._head = (a.hx + (b.hx - a.hx) * fr, a.hy + (b.hy - a.hy) * fr)

        # 동작이 바뀌면: 직전 그림을 기억해 두었다가 서서히 사라지게 하고 새 그림을 서서히 나타나게 한다
        now = time.perf_counter()
        if self._cur_key is not None and self._last is not None and (key != self._cur_key or face != self._cur_face):
            # 자세가 바뀌거나, 같은 자세에서 방향만 바뀌어도 서서히 바꾼다 (예전에는 방향이 바뀌면 거울처럼 한순간에 뒤집혔다)
            self._trans = (now, TRANS_FAST if key in _FAST_KEYS else TRANS_SEC, self._last)
        self._cur_key = key
        self._cur_face = face
        fade, old = 1.0, None
        if self._trans:
            t0, dur, snap = self._trans
            k = (now - t0) / dur
            if k >= 1.0:
                self._trans = None
            else:
                fade, old = k * k * (3 - 2 * k), snap

        ox, oy = round(origin[0] * d) / d, round(origin[1] * d) / d
        p.save()
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.translate(ox, oy)
        if face < 0:
            p.scale(-1.0, 1.0)
        grounded = brain.state.name not in ("JUMP", "KICK_LEAP", "FALL", "HELD")
        sink = self.sinks.get(key, SINK) if grounded else 0.0
        if room is not None:
            sink = max(0.0, min(sink, room - 1.0))
        self.sink_now = sink
        self._head = (self._head[0], self._head[1] - sink)
        p.translate(0.0, round(sink * d) / d)                        # 그림자·소품·고양이를 모두 같이 내린다 (발이 바닥에 살짝 걸친다)
        if grounded:
            self._shadow(p, a.w)
        self._props_under(p, brain, an.name, a, b, fr)
        layers = [(a.pm, -a.cx, -a.h + a.drop, 1.0)]                          # (그림, 왼쪽 위 x, y, 진하기): 아래 컷은 그대로, 위 컷만 섞는 비율만큼 올린다
        if fr > 0.001 and i1 != i0:
            layers.append((b.pm, -b.cx, -b.h + b.drop, fr))
        if old is not None:                                           # 사라지는 직전 그림 (방향이 달라졌으면 좌우를 뒤집어 그린다)
            p.save()
            p.translate(0.0, round((old.get("sink", sink) - sink) * d) / d)   # 직전 그림은 그때 내린 높이 그대로
            if old["face"] != face:
                p.scale(-1.0, 1.0)
            for pm, x, y, al in old["layers"]:
                p.setOpacity(al * (1.0 - fade) ** 2)               # 사라지는 그림은 처음에 빨리 옅어져서 잔상이 오래 남지 않는다
                p.drawPixmap(QPointF(round(x * d) / d, round(y * d) / d), pm)
            p.restore()
        fade_in = min(1.0, fade * 1.5)                               # 새 그림은 조금 더 빨리 나타나서 중간에 몸이 너무 투명해지지 않게
        for pm, x, y, al in layers:
            p.setOpacity(al * fade_in)
            p.drawPixmap(QPointF(round(x * d) / d, round(y * d) / d), pm)
        p.setOpacity(1.0)
        self._last = {"layers": layers, "face": face, "sink": sink}
        self._props_over(p, brain, an.name, a)
        p.restore()

    def head_top(self, _ps=None):
        """머리 꼭대기 위치(뼈대 단위: 바라보는 방향 쪽이 +, 위쪽이 +). 말풍선을 머리에 붙이는 데 쓴다."""
        return self._head[0] * 1.0, self._head[1] * 1.0 + 2.0

    # ------------------------------------------------------------ 그림자·소품
    def _shadow(self, p, width):
        s = self.sc
        w = max(width * 0.72, 40 * s)
        g = QRadialGradient(QPointF(0, 0), w / 2)
        g.setColorAt(0.0, QColor(30, 25, 20, 100))
        g.setColorAt(0.6, QColor(30, 25, 20, 48))
        g.setColorAt(1.0, QColor(30, 25, 20, 0))
        p.save()
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(g))
        p.translate(0, 0)
        p.scale(1.0, 0.10)
        p.drawEllipse(QPointF(0, 0), w / 2, w / 2)
        p.restore()

    def _props_under(self, p, brain, name, a, b, fr):
        s = self.sc
        if name == "knead":                                          # 분홍 방석 (앞발 아래): 앞발 끝(몸 중심에서 앞쪽 53~75)보다 앞으로 충분히 나오게, 뒤쪽은 몸 아래에 깔리게
            x = 50 * s
            body = QPainterPath()
            body.moveTo(x - 62 * s, -2 * s)
            body.cubicTo(x - 70 * s, -11 * s, x - 54 * s, -22 * s, x - 36 * s, -19 * s)
            body.cubicTo(x - 14 * s, -24 * s, x + 18 * s, -24 * s, x + 38 * s, -19 * s)
            body.cubicTo(x + 58 * s, -22 * s, x + 72 * s, -10 * s, x + 62 * s, -2 * s)
            body.cubicTo(x + 38 * s, 4 * s, x - 38 * s, 4 * s, x - 62 * s, -2 * s)
            body.closeSubpath()
            g = QLinearGradient(0, -24 * s, 0, 4 * s)
            g.setColorAt(0.0, QColor("#f4b8cb"))
            g.setColorAt(1.0, QColor("#d98aa6"))
            p.save()
            p.setPen(QPen(OUTLINE, 1.2))
            p.setBrush(QBrush(g))
            p.drawPath(body)
            p.setPen(QPen(QColor("#c46f8d"), 1.1))
            for dx in (-22, 0, 22):
                p.drawLine(QPointF(x + dx * s, -17 * s), QPointF(x + dx * 0.8 * s, -3 * s))
            p.restore()
        elif name == "eat":                                          # 밥그릇 (코 앞)
            x = (a.w - a.cx) - 22 * s
            p.save()
            p.setPen(QPen(OUTLINE, 1.2))
            p.setBrush(QColor("#7ea6d8"))
            bowl = QPainterPath()
            bowl.moveTo(x - 22 * s, -13 * s)
            bowl.lineTo(x + 22 * s, -13 * s)
            bowl.lineTo(x + 16 * s, 0)
            bowl.lineTo(x - 16 * s, 0)
            bowl.closeSubpath()
            p.drawPath(bowl)
            p.setBrush(QColor("#a56a3c"))
            p.drawEllipse(QPointF(x, -13 * s), 21 * s, 4.5 * s)
            p.setBrush(QColor("#c98a52"))
            for dx, dy in ((-9, -15), (-2, -17), (7, -15), (13, -14), (2, -14)):
                p.drawEllipse(QPointF(x + dx * s, dy * s), 3.2 * s, 2.4 * s)
            p.restore()
        if name == "bunny" and brain.ball:                           # 끌어안은 공: 고양이 뒤에 그려서 앞발이 공 위에 걸치게
            # 끌어안은 공: 사진 속 앞발과 몸 사이 빈자리(몸 중심에서 앞쪽 x, 바닥 위 y; 뼈대 단위)에 놓는다. 컷마다 눈금을 얹어 읽은 값이라,
            # 컷의 크기·정렬(tools/build_sprites.py)을 바꾸면 다시 읽어야 한다. 앞 3컷은 누워서 두 앞발 사이, 뒤 3컷은 팔 아래 가슴 앞.
            i0, i1, fr = self._pose_idx
            # 컷마다 눈금을 얹어 읽은 값: (몸 중심에서 앞쪽 x, 바닥 위 y, 반지름). 사진 속 공 자리(앞발·가슴·배 사이 빈 구멍)에 맞춘다.
            # 앞 3컷은 두 앞발 사이에 안기고, 뒤 3컷은 앞발 아래 몸 앞쪽 바닥 근처에 더 크게 놓여 뒷발로 찬다. 컷 크기·정렬을 바꾸면 다시 읽어야 한다.
            bx = [62.0, 64.0, 66.0, 66.0, 66.0, 68.0]
            by = [34.0, 36.0, 38.0, 46.0, 48.0, 47.0]
            br = [22.0, 22.0, 23.0, 25.0, 26.0, 26.0]
            x = bx[i0] + (bx[i1] - bx[i0]) * fr
            y = by[i0] + (by[i1] - by[i0]) * fr
            r = br[i0] + (br[i1] - br[i0]) * fr
            self._ball(p, x * s, -y * s, r * s, 40.0 * math.sin(brain.an.clock * 8.5))

    def _props_over(self, p, brain, name, a):
        if brain.ball and name != "bunny":
            s = self.sc
            bx = (brain.ball["x"] - brain.x) * brain.facing           # 고양이 기준, 바라보는 쪽이 +
            self._ball(p, bx, -9 * s, 9 * s, (brain.ball["x"] * 3.0) % 360)

    def _ball(self, p, x, y, r, rot):
        p.save()
        p.translate(x, y)
        p.rotate(rot)
        p.setPen(QPen(OUTLINE, 1.2))
        p.setBrush(QColor("#e4605f"))
        p.drawEllipse(QPointF(0, 0), r, r)
        p.setPen(QPen(QColor("#f7a6a0"), max(1.0, r / 6.5)))
        p.drawArc(QRectF(-r * 0.78, -r * 0.78, r * 1.56, r * 1.56), 30 * 16, 120 * 16)
        p.drawArc(QRectF(-r * 0.55, -r * 0.88, r * 1.33, r * 1.77), 200 * 16, 110 * 16)
        p.drawArc(QRectF(-r * 0.88, -r * 0.33, r * 1.77, r), 250 * 16, 140 * 16)
        p.restore()

    @staticmethod
    def _head_crop(img):
        """앉은 고양이 그림에서 머리와 어깨 부분(위쪽)만 정사각형으로 잘라낸다."""
        small = img.scaled(80, 80, Qt.AspectRatioMode.IgnoreAspectRatio)

        def bbox(im, y_lo=0, y_hi=None):
            y_hi = im.height() if y_hi is None else y_hi
            xs, ys = [], []
            for y in range(y_lo, y_hi):
                for x in range(im.width()):
                    if im.pixelColor(x, y).alpha() > 40:
                        xs.append(x)
                        ys.append(y)
            return (min(xs), min(ys), max(xs), max(ys)) if xs else (0, 0, im.width() - 1, im.height() - 1)

        x0, y0, x1, y1 = bbox(small)
        band_bottom = y0 + int((y1 - y0) * 0.50)                 # 위쪽 절반: 머리와 어깨
        bx0, by0, bx1, by1 = bbox(small, y0, band_bottom + 1)
        kx, ky = img.width() / 80.0, img.height() / 80.0
        cx, cy = (bx0 + bx1) / 2 * kx, (by0 + by1) / 2 * ky
        side = max((bx1 - bx0) * kx, (by1 - by0) * ky) * 1.15
        left, top = int(max(0, cx - side / 2)), int(max(0, cy - side / 2))
        side = int(min(side, img.width() - left, img.height() - top))
        return img.copy(left, top, side, side)

    # ------------------------------------------------------------ 트레이 아이콘용
    def icon_pixmap(self, size=64, head=False):
        """앉아 있는 고양이를 정사각형에 맞춰 그린다 (트레이·창 아이콘).
        head=True: 꼬리와 몸 아래를 빼고 얼굴 위주로 잘라서, 16~32px 로 작게 보여도 고양이로 알아보게 한다."""
        img = self._frame("sit", 0).pm.toImage()
        if head:
            img = self._head_crop(img)
        out = QImage(size, size, QImage.Format.Format_ARGB32)
        out.fill(Qt.GlobalColor.transparent)
        q = QPainter(out)
        q.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        k = min((size - 4) / img.width(), (size - 4) / img.height())
        tw, th = img.width() * k, img.height() * k
        q.drawImage(QRectF((size - tw) / 2, size - th - 2, tw, th), img)
        q.end()
        return QPixmap.fromImage(out)
