"""뼈대(스켈레톤) 고양이 렌더러.

고양이는 옆모습(오른쪽을 봄)으로, 로컬 좌표계에서 계산한다:
    원점 = 몸 아래 바닥 위의 한 점, x = 앞쪽, y = 위쪽 (그릴 때만 화면 y로 뒤집음)

Pose 는 숫자 딕셔너리라서 두 포즈를 그냥 섞기(lerp)만 해도 부드러운 전환이 된다.
다리는 발 위치만 주면 IK로 관절이 접히고, 꼬리는 스프링 사슬로 시뮬레이션한다(늦게 따라오며 부드럽게 휨).
skin 이 있으면 실사 사진 조각(assets/skin)으로, 없으면 일러스트로 그린다.
"""
import json
import math
import random
from pathlib import Path

import numpy as np

import coats
from PyQt6.QtCore import QLineF, QPointF, QRectF, Qt
from PyQt6.QtGui import (QBrush, QColor, QImage, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap, QPolygonF,
                         QTransform)

# ---------------------------------------------------------------- 색 (일러스트)
C_BODY = QColor("#c58f5c")
C_BODY_FAR = QColor("#a87646")
C_STRIPE = QColor("#6e4b2f")
C_CREAM = QColor("#f4e8d6")
C_OUT = QColor("#4b3225")
C_EAR_IN = QColor("#eaa9a1")
C_NOSE = QColor("#e58a8f")
C_EYE = QColor("#a9b63f")
C_MOUTH = QColor("#8c3b46")
C_TONGUE = QColor("#ec7c86")
OUTLINE_W = 1.5

# ---------------------------------------------------------------- 포즈
DEFAULT = {
    # 척추: 엉덩이/어깨 관절 위치, 등 휨(위로 볼록 +), 몸 두께
    "hx": -34, "hy": 52, "sx": 34, "sy": 55, "arch": 0, "hip_r": 21, "chest_r": 22,
    "sag": 3.5,                                 # 배가 아래로 처진 정도 (단위). 고양이 배는 가운데가 늘어진다
    "hump": 1.5,                                # 등이 위로 둥글게 솟은 정도
    # 발 목표 (x, y, 발 기울기). N=가까운 쪽, F=먼 쪽
    "FNx": 38, "FNy": 0, "FNa": 0, "FFx": 28, "FFy": 0, "FFa": 0,
    "HNx": -30, "HNy": 0, "HNa": 0, "HFx": -22, "HFy": 0, "HFa": 0,
    "fa_N": 24, "fa_F": 24,                     # 뒷발 중족골(발목→발) 각도: 0=수직, 90=수평
    # 머리: 어깨 기준 위치, 기울기
    "hdx": 22, "hdy": 24, "hrot": 0,
    "earN": 0, "earF": 0,                       # +면 뒤로 눕힘 (도), -면 앞으로 세움
    "eyeO": 1, "eyeH": 0, "mouth": 0, "tongue": 0, "lookx": 0, "looky": 0, "whisk": 0,
    # 꼬리: 밑동 들림각, 말림(마디당), 흔들림 크기/빠르기, 파동 지연
    "tb": 20, "tc": 3, "tw": 8, "tf": 0.45, "tp": 0.55,
    "tg": 1,                                    # 1이면 꼬리가 바닥 아래로 내려가지 않고 바닥에 눕는다
    "tfront": 0,                                # 1이면 꼬리를 몸통 앞에 그림 (몸을 감싸는 자세)
    "shadow": 1,
    "flover": 0,                                # 1이면 앞다리를 머리 위에 그린다 (머리를 아래로 한 다이브 자세에서 앞발이 보이게)
    # 소품 (알파 0이면 안 그림): 밥그릇, 방석, 털실공
    "bowl": 0, "bowlx": 66, "cush": 0, "cushx": 40, "ball": 0, "ballx": 70, "bally": 0, "ballrot": 0, "ballmid": 0,
}


def pose(*parts, **kw):
    """기본 포즈 위에 부분 딕셔너리들(앞→뒤 순)과 키워드를 덮어쓴다. 뒤에 온 값이 이긴다."""
    p = dict(DEFAULT)
    for part in parts:
        p.update(part)
    p.update(kw)
    return p


def lerp_pose(a, b, k):
    return {key: a[key] + (b[key] - a[key]) * k for key in a}


# ---------------------------------------------------------------- 기하
def ik2(ax, ay, tx, ty, l1, l2, bend):
    """2마디 IK. bend=+1/-1 로 무릎(팔꿈치) 방향 선택. 관절 위치를 돌려준다."""
    dx, dy = tx - ax, ty - ay
    d = math.hypot(dx, dy)
    d = max(abs(l1 - l2) + 0.5, min(l1 + l2 - 0.5, d))
    base = math.atan2(dy, dx)
    cos_a = (l1 * l1 + d * d - l2 * l2) / (2 * l1 * d)
    a = math.acos(max(-1.0, min(1.0, cos_a)))
    ang = base + bend * a
    return ax + l1 * math.cos(ang), ay + l1 * math.sin(ang)


def _pt(x, y):
    return QPointF(x, -y)


def capsule(ax, ay, bx, by, ra, rb, simplify=True):
    """두께가 다른 두 원을 잇는 캡슐 경로 (로컬 좌표, y 위쪽)."""
    path = QPainterPath()
    dx, dy = bx - ax, by - ay
    d = math.hypot(dx, dy) or 1e-6
    nx, ny = -dy / d, dx / d
    poly = QPolygonF([_pt(ax + nx * ra, ay + ny * ra), _pt(bx + nx * rb, by + ny * rb),
                      _pt(bx - nx * rb, by - ny * rb), _pt(ax - nx * ra, ay - ny * ra)])
    path.setFillRule(Qt.FillRule.WindingFill)       # 기본값(홀짝)이면 겹친 부분이 구멍이 된다
    path.addPolygon(poly)
    path.addEllipse(_pt(ax, ay), ra, ra)
    path.addEllipse(_pt(bx, by), rb, rb)
    return path.simplified() if simplify else path


def union_capsules(pts, radii, simplify=True):
    """여러 마디의 캡슐을 한 덩어리 경로로 합친다 (simplified 는 마지막에 한 번만: 느린 연산이라)."""
    path = QPainterPath()
    path.setFillRule(Qt.FillRule.WindingFill)
    for i in range(len(pts) - 1):
        ax, ay = pts[i]
        bx, by = pts[i + 1]
        ra, rb = radii[i], radii[i + 1]
        dx, dy = bx - ax, by - ay
        d = math.hypot(dx, dy) or 1e-6
        nx, ny = -dy / d, dx / d
        path.addPolygon(QPolygonF([_pt(ax + nx * ra, ay + ny * ra), _pt(bx + nx * rb, by + ny * rb),
                                   _pt(bx - nx * rb, by - ny * rb), _pt(ax - nx * ra, ay - ny * ra)]))
        path.addEllipse(_pt(ax, ay), ra, ra)
    path.addEllipse(_pt(*pts[-1]), radii[-1], radii[-1])
    return path.simplified() if simplify else path


def _bez(p0, p1, p2, t):
    u = 1 - t
    return (u * u * p0[0] + 2 * u * t * p1[0] + t * t * p2[0],
            u * u * p0[1] + 2 * u * t * p1[1] + t * t * p2[1])


# ---------------------------------------------------------------- 꼬리 시뮬레이션
class TailSim:
    """꼬리를 스프링-댐퍼 사슬로 시뮬레이션한다.

    각 마디는 '앞 마디의 방향 + 말림' 을 향해 스프링으로 끌려가므로, 밑동이 움직이면 끝으로 갈수록
    늦게 따라오며 부드럽게 휜다(팔로스루).

    움직임은 고양이처럼 '가끔 두세 번 천천히 흔들고 쉬는' 식이다:
      · 평소: 아주 느린 살랑거림 (몇 초에 한 번)
      · 몇 초마다 한 번: 1~2초에 한 번 왔다 갔다 하는 흔들기를 2~3번만 하고 가라앉는다
    스프링은 충분히 감쇠되어 있어서 '부르르' 떨리거나 엔진처럼 진동하지 않는다.
    """
    N = 12
    SEG = 81.0 * 0.8 / 12          # 꼬리 전체 길이 (이전 81에서 20% 줄임)
    K0 = 420.0            # 밑동 쪽은 뻣뻣하고 (고유진동 3Hz 안팎)
    KDECAY = 0.90         # 끝으로 갈수록 부드럽다
    ZETA = 0.60           # 충분히 감쇠
    VMAX = 5.0            # 마디 각속도 상한 (rad/s) — 아무리 해도 이보다 빠르게는 안 움직인다

    def __init__(self):
        self.a = None
        self.v = None
        self.t = None
        self.hy = 0.0
        self.lag = 0.0
        self.next_flick = 0.0
        self.next_burst = 0.0
        self.burst_t0 = -99.0
        self.burst_len = 3.0
        self.burst_f = 0.7
        self.burst_dir = 1.0
        self.rnd = random.Random(5)

    def _schedule_burst(self, t, ps):
        f = min(1.0, max(0.5, 0.45 + 0.22 * ps["tf"]))        # 한 번 왔다 갔다 하는 빠르기 (Hz): 0.5~1Hz = 1~2초에 한 번
        swings = self.rnd.choice((2, 2, 3))                    # 두세 번만 흔든다
        self.burst_t0, self.burst_f = t, f
        self.burst_len = swings / f
        self.burst_dir = self.rnd.choice((-1.0, 1.0))
        self.next_burst = t + self.burst_len + self.rnd.uniform(2.5, 6.0)

    def step(self, ps, t):
        n = self.N
        base = math.radians(180 - ps["tb"])
        rest = -math.radians(ps["tc"]) * 9.0 / n
        if self.a is None or self.t is None or t < self.t or t - self.t > 0.3:      # 처음/시간이 튀면 정지 자세로 초기화
            ang, self.a = base, []
            for _ in range(n):
                ang += rest
                self.a.append(ang)
            self.v, self.t, self.hy = [0.0] * n, t, ps["hy"]
            self.next_flick = t + self.rnd.uniform(5.0, 9.0)
            self.next_burst = t + self.rnd.uniform(0.6, 2.5)
            self.burst_t0 = -99.0
            return self.a
        dt = t - self.t
        self.t = t
        if dt <= 0:
            return self.a
        if t >= self.next_burst:
            self._schedule_burst(t, ps)
        if t >= self.next_flick:                              # 가끔 꼬리 끝이 살짝 튕기는 동작
            sign = self.rnd.choice((-1.0, 1.0))
            power = max(0.25, min(1.2, ps["tw"] / 14.0))
            for i in range(n // 3, n):
                self.v[i] += sign * self.rnd.uniform(1.0, 2.4) * power * (i / n)
            self.next_flick = t + self.rnd.uniform(6.0, 12.0)
        vhy = (ps["hy"] - self.hy) / max(dt, 1e-3)               # 몸이 크게 오르내리면(점프 등) 꼬리가 반대로 처지는 관성
        self.hy = ps["hy"]
        target_lag = max(-0.35, min(0.35, -0.0015 * vhy))
        self.lag += (target_lag - self.lag) * min(1.0, dt * 2.5)  # 저역통과: 걸음 때문에 생기는 잔떨림은 걸러냄
        lag = self.lag
        steps = max(1, int(math.ceil(dt / 0.01)))
        h = dt / steps
        amp = math.radians(ps["tw"])
        two_pi = 2 * math.pi
        for s in range(steps):
            tt = t - dt + (s + 1) * h
            k = (tt - self.burst_t0) / self.burst_len
            env = math.sin(math.pi * k) ** 2 if 0.0 <= k <= 1.0 else 0.0      # 흔들기 구간에서만 0→1→0 으로 부드럽게
            swing = amp * (self.burst_dir * env * math.sin(two_pi * self.burst_f * (tt - self.burst_t0))
                           + 0.20 * math.sin(two_pi * 0.15 * tt + 0.7) + 0.10 * math.sin(two_pi * 0.23 * tt + 2.1))
            parent = base + swing + lag
            for i in range(n):
                # 끝으로 갈수록 커지는 느린 S자 물결 (꼬리 끝이 살랑거림)
                wob = amp * 0.30 * math.sin(two_pi * 0.5 * tt - ps["tp"] * 1.4 * i) * (i / n) * (0.35 + 0.65 * env)
                target = parent + rest + wob
                kk = self.K0 * (self.KDECAY ** i)
                acc = -kk * (self.a[i] - target) - 2 * self.ZETA * math.sqrt(kk) * self.v[i]
                v = self.v[i] + acc * h
                v = max(-self.VMAX, min(self.VMAX, v))
                self.v[i] = v
                self.a[i] += v * h
                parent = self.a[i]
        return self.a


# ---------------------------------------------------------------- 실사 스킨
class Skin:
    """실사 사진에서 오려낸 조각(assets/skin)으로 뼈대 고양이를 덮는다. tools/make_skin.py 가 만든다."""

    def __init__(self, folder, coat="brown"):
        self._folder = Path(folder)
        info = self._info = json.loads((self._folder / "skin.json").read_text(encoding="utf-8"))
        self.coat = "brown"
        self.head_scale = 0.85          # 머리 크기 (사진 그대로가 1.0)
        self.neck_k = 0.95              # 목 길이 (어깨~머리 거리)
        self._load_all(coat)
        h = info["head"]
        self.head_rect = QRectF(-h["anchor"][0] * h["scale"], -h["anchor"][1] * h["scale"],
                                h["size"][0] * h["scale"], h["size"][1] * h["scale"])
        self.eyes = [tuple(e) for e in info["eyes"]]
        self.lid_size = tuple(info["lid_size"])
        self.mouth = tuple(info["mouth"])
        self.lip = tuple(info["lip"])
        self.paw_w, self.paw_h = info["paw_size"][0] * 0.9, info["paw_size"][1] * 0.9      # 발 크기 10% 축소
        self.fur_scale = info["fur_scale"]
        rnd = random.Random(11)
        # (위치 지터, cos, sin, 길이, 펜 키): 대부분 짧은 잔털, 일부는 길게 삐져나온 털
        self.rand = []
        for _ in range(512):
            ang = math.radians(rnd.uniform(-34, 34))
            ln = rnd.uniform(0.8, 1.7) if rnd.random() < 0.85 else rnd.uniform(1.7, 2.5)
            self.rand.append((rnd.random(), math.cos(ang), math.sin(ang), ln, rnd.randrange(4)))
        self.rand_np = np.array(self.rand, dtype=np.float64)       # 열: 지터, cos, sin, 길이, 펜 키

    # --- 털색 -------------------------------------------------------------
    def _pixmap(self, name, kind, coat):
        img = QImage(str(self._folder / f"{name}.png"))
        if coat != "brown" and not img.isNull():
            img = img.convertToFormat(QImage.Format.Format_RGBA8888)
            ptr = img.constBits()
            ptr.setsize(img.sizeInBytes())
            arr = np.frombuffer(ptr, np.uint8).reshape(img.height(), img.width(), 4).copy()
            arr = np.ascontiguousarray(coats.recolor(arr, coat))           # (예전 recolor_part 는 없어졌다: 뼈대 방식은 무늬 위치 없이 색만 바꾼다)
            img = QImage(arr.data, arr.shape[1], arr.shape[0], arr.shape[1] * 4, QImage.Format.Format_RGBA8888).copy()
        return QPixmap.fromImage(img)

    def _load_all(self, coat):
        """질감 조각을 불러오고(털색이 갈색이 아니면 색을 바꿔서) 그에 따른 색 값도 다시 계산한다."""
        info = self._info
        load = lambda name, kind: self._pixmap(name, kind, coat)
        self.pix = {"body": load("fur_body", "body"), "leg": load("fur_leg", "leg"), "dark": load("fur_dark", "dark"),
                    "cream": load("fur_cream", "cream"), "tail": load("fur_tail", "tail"), "head": load("head", "head"),
                    "paw": load("paw", "paw"), "jaw": load(info["jaw"]["file"], "jaw")}
        self.jaw = (self.pix["jaw"], QRectF(*info["jaw"]["rect"]))
        self.ears = {key: (load(e["file"], "ear"), tuple(e["pivot"]), QRectF(*e["rect"])) for key, e in info["ears"].items()}
        self.lids = [load(n, "lid") for n in info["lids"]]
        if any(pm.isNull() for pm in list(self.pix.values()) + self.lids + [e[0] for e in self.ears.values()]):
            raise FileNotFoundError(f"스킨 이미지가 없습니다: {self._folder}  (python tools/make_skin.py 로 만드세요)")
        one = lambda pm: QColor(pm.scaled(1, 1, Qt.AspectRatioMode.IgnoreAspectRatio,
                                          Qt.TransformationMode.SmoothTransformation).toImage().pixelColor(0, 0))
        if coat == "brown":
            self.dark = QColor(*info["tail_dark"])
            self.head_col = QColor(*info["head_mean"])        # 머리 사진의 평균 털색 (목에서 머리로 이어 붙일 때 쓴다)
        else:
            self.dark = one(self.pix["dark"])
            hi = self.pix["head"].toImage().convertToFormat(QImage.Format.Format_RGBA8888)
            hp = hi.constBits()
            hp.setsize(hi.sizeInBytes())
            ha = np.frombuffer(hp, np.uint8).reshape(hi.height(), hi.width(), 4)
            m = ha[..., 3] > 200
            self.head_col = QColor(*[int(x) for x in ha[..., :3][m].mean(0)]) if m.any() else self.dark
        # 가장자리 잔털 색: 몸 털 질감의 평균색을 밝게/어둡게
        avg = one(self.pix["body"])
        self.avg = {k: one(self.pix[k]) for k in ("body", "leg", "dark", "tail")}
        if coat == "brown":
            self.ring_col = QColor(104, 76, 54, 105)               # 꼬리의 줄무늬 고리 (털색보다 조금 짙게)
        else:
            self.ring_col = QColor(self.avg["tail"]).darker(190)
            self.ring_col.setAlpha(105)
        self.strand_cols = [QColor(avg).lighter(145), QColor(avg).lighter(125), QColor(avg).lighter(108), QColor(avg)]
        self.fuzz_pens = []
        for ci in range(4):
            c = QColor(self.strand_cols[ci])
            c.setAlpha(105)
            self.fuzz_pens.append(QPen(c, 0.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        self.coat = coat

    def set_coat(self, coat):
        if coat in coats.COAT_KEYS and coat != self.coat:
            self._load_all(coat)

    def brush(self, kind, ox=0.0, oy=0.0, rot=0.0):
        """털 질감 브러시. 질감 중심이 (ox, oy)에 오고 rot(도, 화면 시계방향)만큼 돌아가서,
        부위(몸통/다리)의 방향을 따라 무늬가 같이 돈다."""
        pm = self.pix[kind]
        fs = self.fur_scale
        b = QBrush(pm)
        tr = QTransform()
        tr.translate(ox, -oy)
        tr.rotate(rot)
        tr.translate(-pm.width() * fs / 2, -pm.height() * fs / 2)
        tr.scale(fs, fs)
        b.setTransform(tr)
        return b


def load_skin(folder, coat="brown"):
    """스킨이 없거나 깨졌으면 None (그러면 일러스트 모양으로 그린다)."""
    try:
        return Skin(folder, coat)
    except Exception:
        return None


class CatRig:
    """Pose 하나를 QPainter 에 그린다. skin 이 있으면 실사 질감, 없으면 일러스트."""

    FRONT = (25, 25)        # 앞다리 윗마디, 아랫마디
    HIND = (26, 25, 16)     # 허벅지, 정강이, 발(중족골)

    def __init__(self, skin=None):
        self.skin = skin
        self.tail = TailSim()
        self._limb_paths = {}               # 관절 위치가 같으면(쉬는 자세의 다리) 같은 경로를 다시 쓴다
        self.detail = 1.0                   # 0 이면 움직이는 동안 눈에 잘 안 띄는 잔털·부드러운 그림자를 생략해서 그리는 비용을 줄인다 (멈추면 1.0)

    # ------------------------------------------------------------ 외부 API
    def draw(self, p: QPainter, ps: dict, t: float, facing: int = 1, scale: float = 1.0,
             origin=(0.0, 0.0), blink: float = 0.0):
        p.save()
        p.translate(origin[0], origin[1])
        p.scale(scale * facing, scale)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        if ps["shadow"] > 0.01:
            self._shadow(p, ps)
        joints = self._solve(ps)
        tail_pts = self._tail_points(ps, t)
        self._props_under(p, ps)
        self._far_legs(p, ps, joints)
        if not ps["tfront"] >= 0.5:
            self._tail(p, tail_pts)
        body_path = self._body(p, ps)
        if self.skin:
            self._throat(p, ps, body_path)
        if ps["tfront"] >= 0.5:
            self._tail(p, tail_pts)
        self._near_legs(p, ps, joints)
        if ps["ballmid"] >= 0.5:
            self._ball(p, ps)                       # 공을 끌어안는 자세: 머리 뒤(몸·다리 앞)에 그려서 얼굴이 가려지지 않게
        self._head(p, ps, blink)
        if ps["flover"] >= 0.5:
            self._front_legs_over(p, ps, joints)
        self._props_over(p, ps)
        p.restore()

    # ------------------------------------------------------------ 소품
    def _props_under(self, p, ps):
        if ps["cush"] > 0.02:
            x = ps["cushx"]
            p.save()
            p.setOpacity(min(1.0, ps["cush"]))
            body = QPainterPath()
            body.moveTo(x - 64, -3)
            body.cubicTo(x - 72, -12, x - 56, -24, x - 38, -21)
            body.cubicTo(x - 16, -26, x + 18, -26, x + 40, -21)
            body.cubicTo(x + 60, -24, x + 74, -11, x + 64, -3)
            body.cubicTo(x + 40, 3, x - 40, 3, x - 64, -3)
            body.closeSubpath()
            p.setPen(QPen(C_OUT, OUTLINE_W))
            grad = QLinearGradient(0, -26, 0, 3)
            grad.setColorAt(0.0, QColor("#f4b8cb"))
            grad.setColorAt(1.0, QColor("#d98aa6"))
            p.setBrush(QBrush(grad))
            p.drawPath(body)
            p.setPen(QPen(QColor("#c46f8d"), 1.2))                       # 가운데 단추 주름
            for dx_ in (-24, 0, 24):
                p.drawLine(QPointF(x + dx_, -19), QPointF(x + dx_ * 0.8, -4))
            p.setPen(QPen(QColor(255, 255, 255, 120), 1.6))
            p.drawArc(QRectF(x - 46, -23, 92, 10), 20 * 16, 140 * 16)
            p.restore()
        if ps["bowl"] > 0.02:
            x = ps["bowlx"]
            p.save()
            p.setOpacity(min(1.0, ps["bowl"]))
            p.setPen(QPen(C_OUT, OUTLINE_W))
            p.setBrush(QColor("#7ea6d8"))
            bowl = QPainterPath()
            bowl.moveTo(x - 22, -13)
            bowl.lineTo(x + 22, -13)
            bowl.lineTo(x + 16, 0)
            bowl.lineTo(x - 16, 0)
            bowl.closeSubpath()
            p.drawPath(bowl)
            p.setBrush(QColor("#a56a3c"))
            p.drawEllipse(QPointF(x, -13), 21, 4.5)
            p.setBrush(QColor("#c98a52"))
            for dx_, dy_ in ((-9, -15), (-2, -17), (7, -15), (13, -14), (2, -14)):
                p.drawEllipse(QPointF(x + dx_, dy_), 3.2, 2.4)
            p.restore()

    def _props_over(self, p, ps):
        if ps["ballmid"] < 0.5:
            self._ball(p, ps)

    def _ball(self, p, ps):
        if ps["ball"] > 0.02:
            x, y = ps["ballx"], 9 + ps["bally"]
            p.save()
            p.setOpacity(min(1.0, ps["ball"]))
            p.translate(_pt(x, y))
            p.rotate(ps["ballrot"])
            p.setPen(QPen(C_OUT, OUTLINE_W))
            p.setBrush(QColor("#e4605f"))
            p.drawEllipse(QPointF(0, 0), 9, 9)
            p.setPen(QPen(QColor("#f7a6a0"), 1.4))
            p.drawArc(QRectF(-7, -7, 14, 14), 30 * 16, 120 * 16)
            p.drawArc(QRectF(-5, -8, 12, 16), 200 * 16, 110 * 16)
            p.drawArc(QRectF(-8, -3, 16, 9), 250 * 16, 140 * 16)
            p.restore()

    # ------------------------------------------------------------ 풀이
    def _solve(self, ps):
        fa, fb = self.FRONT
        ha, hb, hc = self.HIND
        j = {}
        # 앞다리 (팔꿈치는 뒤쪽으로)
        for side, off in (("N", (3, -10)), ("F", (-3, -9))):
            ax, ay = ps["sx"] + off[0], ps["sy"] + off[1]
            tx, ty = ps["F" + side + "x"], ps["F" + side + "y"]
            ex, ey = ik2(ax, ay, tx, ty, fa, fb, -1)
            j["F" + side] = ((ax, ay), (ex, ey), (tx, ty))
        # 뒷다리 (무릎은 앞쪽으로): 발목 위치를 발 목표에서 역산 후 IK
        for side, off in (("N", (0, -9)), ("F", (6, -8))):
            ax, ay = ps["hx"] + off[0], ps["hy"] + off[1]
            tx, ty = ps["H" + side + "x"], ps["H" + side + "y"]
            ang = math.radians(ps["fa_" + side])
            hockx, hocky = tx - math.sin(ang) * hc, ty + math.cos(ang) * hc
            kx, ky = ik2(ax, ay, hockx, hocky, ha, hb, +1)
            j["H" + side] = ((ax, ay), (kx, ky), (hockx, hocky), (tx, ty))
        if ps["tg"] > 0.5:                          # 바닥이 있는 자세에서는 관절이 바닥 밑으로 내려가지 않게
            for key, pts in j.items():
                j[key] = tuple((x, max(y, 2.0)) if 0 < i < len(pts) - 1 else (x, y) for i, (x, y) in enumerate(pts))
        return j

    # ------------------------------------------------------------ 그림자
    def _shadow(self, p, ps):
        p.save()
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(0, 0, 0, 38))
        width = abs(ps["sx"] - ps["hx"]) * 0.5 + 44
        p.drawEllipse(QPointF(0, 1), width, 5.5)
        p.restore()

    # ------------------------------------------------------------ 실사용 잔털 / 접촉 그림자
    def _halo(self, p, path, strength=1.0, region=None):
        """윤곽선 대신, 부위 가장자리에 아주 옅은 그림자를 번지게 깔아 몸에서 떨어져 보이게 한다."""
        if self.detail < 0.5:
            return
        p.save()
        if region:
            p.setClipPath(self._half_plane(region))
        p.setBrush(Qt.BrushStyle.NoBrush)
        for w, a in ((5.0, 7), (2.4, 11)):
            p.setPen(QPen(QColor(25, 15, 8, int(a * strength)), w, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap,
                          Qt.PenJoinStyle.RoundJoin))
            p.drawPath(path)
        p.restore()

    def _fluff(self, p, path, color, region=None, wide=False):
        """부위 윤곽을 털색으로 한 겹 부풀려 그려서, 가장자리가 수북하고 푹신하게 보이게 한다.
        region=(Ax, Ay, ux, uy, dmin) 이면 다리 축 방향으로 dmin 이상 떨어진 쪽에만 그린다(몸통과 이어지는 윗부분 제외)."""
        p.save()
        if region:
            p.setClipPath(self._half_plane(region))
        c = QColor(color)
        p.setBrush(Qt.BrushStyle.NoBrush)
        for w, al in (((7.0, 34), (3.4, 80)) if wide else ((4.0, 64),)):
            c.setAlpha(al)
            p.setPen(QPen(c, w, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            p.drawPath(path)
        p.restore()

    @staticmethod
    def _half_plane(region):
        ax, ay, ux, uy, dmin = region
        nx, ny = -uy, ux
        poly = QPolygonF([QPointF(ax + ux * dmin + nx * 80, ay + uy * dmin + ny * 80),
                          QPointF(ax + ux * 200 + nx * 80, ay + uy * 200 + ny * 80),
                          QPointF(ax + ux * 200 - nx * 80, ay + uy * 200 - ny * 80),
                          QPointF(ax + ux * dmin - nx * 80, ay + uy * dmin - ny * 80)])
        path = QPainterPath()
        path.addPolygon(poly)
        path.closeSubpath()
        return path

    def _fill_limb_faded(self, p, path, pts, brush, fade):
        """다리를 채우되 위쪽(몸통과 만나는 곳) 길이 fade 비율만큼은 점점 투명해져서 몸통 털과 자연스럽게 섞이게 한다.
        끝쪽을 불투명으로 깔고, 위쪽은 시작점을 조금씩 달리한 반투명 띠를 겹쳐 그러데이션을 만든다."""
        ax, ay = pts[0]
        bx, by = pts[-1]
        vx, vy = bx - ax, by - ay
        L = math.hypot(vx, vy) or 1.0
        ux, uy = vx / L, -vy / L
        nx, ny = -uy, ux
        A = _pt(ax, ay)

        def band(d0):
            return QPolygonF([QPointF(A.x() + ux * d0 + nx * 30, A.y() + uy * d0 + ny * 30),
                              QPointF(A.x() + ux * (L + 24) + nx * 30, A.y() + uy * (L + 24) + ny * 30),
                              QPointF(A.x() + ux * (L + 24) - nx * 30, A.y() + uy * (L + 24) - ny * 30),
                              QPointF(A.x() + ux * d0 - nx * 30, A.y() + uy * d0 - ny * 30)])

        p.save()
        p.setClipPath(path)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(brush)
        p.setOpacity(1.0)
        p.drawPolygon(band(fade * L))
        n = 5
        for k in range(n):
            p.setOpacity(0.32)
            p.drawPolygon(band(fade * L * k / n - 6))
        p.restore()

    def _cream_top(self, p, path, pts, brush, frac, strength=1.0):
        """다리 윗부분(몸통과 만나는 곳)을 배·가슴과 같은 연한 털로 덮고, 아래로 갈수록 서서히 갈색으로 이어지게 한다.
        띠를 길이를 달리해 여러 겹 겹쳐서 부드러운 그러데이션을 만든다."""
        ax, ay = pts[0]
        bx, by = pts[-1]
        vx, vy = bx - ax, by - ay
        L = math.hypot(vx, vy) or 1.0
        ux, uy = vx / L, -vy / L                        # 화면 좌표 (y 가 뒤집힘)
        nx, ny = -uy, ux
        A = _pt(ax, ay)
        p.save()
        p.setClipPath(path)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(brush)
        n = 6
        for k in range(n):
            reach = frac * L * (k + 1) / n
            poly = QPolygonF([QPointF(A.x() - ux * 14 + nx * 30, A.y() - uy * 14 + ny * 30),
                              QPointF(A.x() + ux * reach + nx * 30, A.y() + uy * reach + ny * 30),
                              QPointF(A.x() + ux * reach - nx * 30, A.y() + uy * reach - ny * 30),
                              QPointF(A.x() - ux * 14 - nx * 30, A.y() - uy * 14 - ny * 30)])
            p.setOpacity(0.23 * strength)
            p.drawPolygon(poly)
        p.restore()

    def _fuzz(self, p, path, n, offset=0, length=1.0, skip=None, sel=None, gravity=0.0):
        """부위 가장자리에 짧은 털 가닥을 그려 보송보송한 실루엣을 만든다 (위치는 고정 난수라 깜빡이지 않음).
        가닥들의 위치·방향을 numpy 로 한꺼번에 계산하고, 같은 색은 drawLines 한 번에 그린다.
        skip=(Ax, Ay, ux, uy, dmin): 다리 축 방향으로 dmin 안쪽(몸통과 이어지는 윗부분)은 그리지 않는다.
        sel=('ny'|'nx', 문턱): 바깥쪽 법선의 해당 성분이 문턱보다 큰 곳만 (배 아래 / 가슴 앞)."""
        if self.detail < 0.5:
            return
        sk = self.skin
        poly = path.toFillPolygon()
        m = poly.size()
        if m < 4:
            return
        ptr = poly.data()
        ptr.setsize(m * 16)
        P = np.frombuffer(ptr, dtype=np.float64).reshape(m, 2)
        R = sk.rand_np
        ks = (np.arange(n) * 5 + offset) % len(R)
        jt, ca, sa, ln, key = R[ks, 0], R[ks, 1], R[ks, 2], R[ks, 3], R[ks, 4].astype(int)
        idx = ((np.arange(n) + jt) / n * m).astype(int) % m
        A = P[idx]
        T = P[(idx + 1) % m] - A
        d = np.hypot(T[:, 0], T[:, 1])
        ok = d > 1e-6
        if not ok.any():
            return
        i0 = int(np.argmax(ok))                         # 경로 방향에 따라 바깥쪽 법선의 부호가 정해진다 (한 번만 판별)
        a0 = A[i0]
        sgn = -1.0 if path.contains(QPointF(a0[0] + T[i0, 1] / d[i0] * 1.5, a0[1] - T[i0, 0] / d[i0] * 1.5)) else 1.0
        d = np.where(ok, d, 1.0)
        nx, ny = T[:, 1] / d * sgn, -T[:, 0] / d * sgn
        if skip is not None:
            ok &= ((A[:, 0] - skip[0]) * skip[2] + (A[:, 1] - skip[1]) * skip[3]) >= skip[4]
        if sel is not None:
            comp = ny if sel[0] == "ny" else nx
            ok &= comp > sel[1]
        dx = nx * ca - ny * sa - 0.30
        dy = nx * sa + ny * ca + 0.12 + gravity
        dn = np.hypot(dx, dy)
        dn = np.where(dn < 1e-9, 1.0, dn)
        L = ln * length / dn
        x1, y1 = A[:, 0] - nx * 0.9, A[:, 1] - ny * 0.9
        x2, y2 = A[:, 0] + dx * L, A[:, 1] + dy * L
        pens = sk.fuzz_pens
        p.save()
        for k in np.unique(key[ok]):
            sel_k = ok & (key == k)
            p.setPen(pens[int(k)])
            p.drawLines(list(map(QLineF, x1[sel_k].tolist(), y1[sel_k].tolist(), x2[sel_k].tolist(), y2[sel_k].tolist())))
        p.restore()

    # ------------------------------------------------------------ 다리
    def _limb(self, p, pts, radii, color, paw=None, paw_color=C_CREAM, far=False, cream_top=0.0):
        sk = self.skin
        if sk:
            vx, vy = pts[-1][0] - pts[0][0], pts[-1][1] - pts[0][1]
            rot = -math.degrees(math.atan2(vx, -vy))                  # 고리 무늬가 다리 축에 수직이 되도록
            cx, cy = (pts[0][0] + pts[-1][0]) / 2, (pts[0][1] + pts[-1][1]) / 2
            key = (tuple((round(x, 2), round(y, 2)) for x, y in pts), tuple(radii))
            path = self._limb_paths.get(key)
            if path is None:
                if len(self._limb_paths) > 48:
                    self._limb_paths.clear()
                path = self._limb_paths[key] = union_capsules(pts, radii)
            brush = sk.brush("dark" if far else "leg", cx, cy, rot)
            Lk = math.hypot(vx, vy) or 1.0
            A0 = _pt(*pts[0])
            region = None if far else (A0.x(), A0.y(), vx / Lk, -vy / Lk, 0.32 * Lk * 0.9)
            if not far:
                self._fluff(p, path, sk.avg["leg"], region)
            if far:
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(brush)
                p.drawPath(path)                            # 먼 쪽 다리는 몸통 뒤에 가려지므로 그대로 채움
            else:
                self._fill_limb_faded(p, path, pts, brush, 0.32)       # 위쪽은 몸통 털 속으로 스며든다
            if cream_top > 0:                               # 앞다리: 흰 가슴에서 갈색 다리로 서서히 이어짐
                self._cream_top(p, path, pts, sk.brush("cream", cx, cy, rot), cream_top, 0.7 if far else 0.8)
            self._fuzz(p, path, 10 if far else 32, offset=int(pts[0][0] * 3) & 31, length=1.0, skip=region)
        else:
            p.setPen(QPen(C_OUT, OUTLINE_W, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            p.setBrush(color)
            for i in range(len(pts) - 1):
                p.drawPath(capsule(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1], radii[i], radii[i + 1]))
            # 마디 사이 이음새가 보이지 않게 관절 원을 한 번 더 채움
            p.setPen(Qt.PenStyle.NoPen)
            for i in range(1, len(pts) - 1):
                p.drawEllipse(_pt(*pts[i]), radii[i] - 0.6, radii[i] - 0.6)
        if paw:
            px, py, ang = paw
            p.save()
            p.translate(_pt(px, py))
            p.rotate(-ang)
            if sk:
                rect = QRectF(3 - sk.paw_w / 2, -2.2 - sk.paw_h / 2, sk.paw_w, sk.paw_h)
                p.drawPixmap(rect, sk.pix["paw"], QRectF(sk.pix["paw"].rect()))
                if far:
                    p.setPen(Qt.PenStyle.NoPen)
                    p.setBrush(QColor(0, 0, 0, 55))
                    p.drawEllipse(rect.adjusted(1, 1, -1, -1))
            else:
                p.setPen(QPen(C_OUT, OUTLINE_W))
                p.setBrush(paw_color)
                p.drawEllipse(QPointF(3, -2.2), 8.2, 5.0)
            p.restore()

    @staticmethod
    def _thigh(a, k, h, t, r_hip, r_mid, r_knee, r_hock, r_foot):
        """뒷다리: 엉덩이~무릎 사이(넙적다리)에 마디를 하나 더 두어 위쪽을 통통하게, 무릎·발목은 가늘게."""
        m = (a[0] + (k[0] - a[0]) * 0.5, a[1] + (k[1] - a[1]) * 0.5)
        return [a, m, k, h, t], [r_hip, r_mid, r_knee, r_hock, r_foot]

    def _far_legs(self, p, ps, j):
        for side in ("F",):
            a, e, t = j["F" + side]
            if ps["flover"] < 0.5:
                self._limb(p, [a, e, t], [8.4, 5.8, 4.6], C_BODY_FAR, (t[0], t[1], ps["F" + side + "a"]),
                           C_CREAM.darker(112), far=True, cream_top=0.55)
            a, k, h, t = j["H" + side]
            pts, rad = self._thigh(a, k, h, t, 10.6, 11.6, 6.2, 3.8, 3.8)
            self._limb(p, pts, rad, C_BODY_FAR, (t[0], t[1], ps["H" + side + "a"]),
                       C_CREAM.darker(112), far=True)

    def _near_legs(self, p, ps, j):
        a, k, h, t = j["HN"]
        pts, rad = self._thigh(a, k, h, t, 12.6, 13.6, 6.9, 4.0, 4.0)
        self._limb(p, pts, rad, C_BODY, (t[0], t[1], ps["HNa"]))
        if ps["flover"] < 0.5:
            a, e, t = j["FN"]
            self._limb(p, [a, e, t], [9.6, 6.4, 4.8], C_BODY, (t[0], t[1], ps["FNa"]), cream_top=0.55)

    def _front_legs_over(self, p, ps, j):
        """다이브 자세: 머리가 아래로 향해 앞다리가 머리에 가려지므로, 앞다리를 머리 위에 그린다."""
        a, e, t = j["FF"]
        self._limb(p, [a, e, t], [8.4, 5.8, 4.6], C_BODY_FAR, (t[0], t[1], ps["FFa"]), C_CREAM.darker(112), far=True)
        a, e, t = j["FN"]
        self._limb(p, [a, e, t], [9.6, 6.4, 4.8], C_BODY, (t[0], t[1], ps["FNa"]))

    # ------------------------------------------------------------ 꼬리 (끝으로 갈수록 가늘고, 시뮬레이션으로 부드럽게 휨)
    R_BASE, R_TIP = 6.4, 1.7          # 꼬리 굵기 (뿌리 → 끝 반지름). 끝으로 갈수록 가늘어진다

    def _tail_points(self, ps, t):
        ang = self.tail.step(ps, t)
        seg = TailSim.SEG
        # 꼬리 뿌리: 엉덩이 끝에서 척추 방향 뒤쪽으로, 등선이 아니라 엉덩이 중간(조금 아래)에 붙인다
        tdx, tdy = ps["sx"] - ps["hx"], ps["sy"] - ps["hy"]
        tl = math.hypot(tdx, tdy) or 1.0
        tx_, ty_ = tdx / tl, tdy / tl
        x = ps["hx"] - tx_ * ps["hip_r"] * 0.88 + ty_ * 7.5
        y = ps["hy"] - ty_ * ps["hip_r"] * 0.88 - tx_ * 7.5
        pts = [(x, y)]
        for a in ang:
            x += seg * math.cos(a)
            y += seg * math.sin(a)
            if ps["tg"] > 0.5:
                y = max(y, 3.0)
            pts.append((x, y))
        return pts

    def _tail(self, p, pts):
        n = len(pts) - 1
        radii = [self.R_BASE + (self.R_TIP - self.R_BASE) * (i / n) ** 1.15 for i in range(n + 1)]
        path = union_capsules(pts, radii)
        sk = self.skin
        p.save()

        def band(i0, i1, grow=0.5):                         # i0~i1 마디만 감싸는 띠 경로
            return union_capsules(pts[i0:i1 + 1], [r + grow for r in radii[i0:i1 + 1]], simplify=False)

        rings = ((3, 4), (6, 7), (9, 10), (11, n))
        if sk:
            tb = sk.brush("tail", pts[0][0], pts[0][1])
            self._fluff(p, path, sk.avg["tail"])
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(tb)
            p.drawPath(path)
            p.setClipPath(path)
            ring_col = sk.ring_col                               # 털색보다 조금 짙은 옅은 고리
            p.setBrush(ring_col)
            for i0, i1 in rings:
                p.drawPath(band(i0, i1, 1.2))
            p.setClipping(False)
            self._fuzz(p, path, 40, offset=7, length=1.0)
        else:
            p.setPen(QPen(C_OUT, OUTLINE_W, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            p.setBrush(C_BODY_FAR)
            p.drawPath(path)
            p.setClipPath(path)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(C_STRIPE)
            for i0, i1 in rings:
                p.drawPath(band(i0, i1, 1.2))
            p.setClipping(False)
            p.setPen(QPen(C_OUT, OUTLINE_W, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPath(path)
        p.restore()

    # ------------------------------------------------------------ 몸통
    def _body_path(self, ps):
        """등선과 배선이 따로 휘는 몸통 윤곽.

        · 등: 다리를 뻗고 모으는 정도(척추가 펴지고 굽는 정도)에 따라 휘고, 기본으로 살짝 솟아 있다.
        · 배: 가운데가 아래로 늘어진다(sag).
        부드러운 폐곡선(Catmull-Rom)으로 이어서 캡슐을 이어 붙인 것처럼 각지지 않는다."""
        hx, hy, sx, sy = ps["hx"], ps["hy"], ps["sx"], ps["sy"]
        dx, dy = sx - hx, sy - hy
        d = math.hypot(dx, dy) or 1e-6
        tx, ty = dx / d, dy / d
        nx, ny = -ty, tx
        ext = (ps["FNx"] + ps["FFx"]) / 2 - (ps["HNx"] + ps["HFx"]) / 2 - 60.0    # 앞뒤 다리가 벌어진 정도
        flex = max(-7.0, min(7.0, -0.11 * ext))                  # 다리를 뻗으면 등이 펴지고, 모으면 둥글게 굽는다
        arch = ps["arch"] * 1.4 + ps["hump"] + flex
        H, S = (hx, hy), (sx, sy)
        M = ((hx + sx) / 2 + nx * arch, (hy + sy) / 2 + ny * arch)
        n = 17
        top, bot = [], []
        for i in range(n):
            u = i / (n - 1)
            B = _bez(H, M, S, u)
            B1, B0 = _bez(H, M, S, min(1.0, u + 0.02)), _bez(H, M, S, max(0.0, u - 0.02))
            ux, uy = B1[0] - B0[0], B1[1] - B0[1]
            dn = math.hypot(ux, uy) or 1.0
            qx, qy = -uy / dn, ux / dn
            r = ps["hip_r"] * (1 - u) + ps["chest_r"] * u + 1.2 * math.sin(math.pi * u)
            bump = math.sin(math.pi * min(1.0, max(0.0, (u - 0.1) / 0.8))) ** 1.5
            rt = r + 0.6 * ps["hump"] * math.sin(math.pi * u)
            rb = r + ps["sag"] * bump
            top.append((B[0] + qx * rt, B[1] + qy * rt))
            bot.append((B[0] - qx * rb, B[1] - qy * rb))
        def cap(cx, cy, r, sx_, sy_, mx_, my_, steps=6):
            """(cx,cy) 를 중심으로 반지름 r 인 반원: sx_ 방향에서 시작해 mx_ 방향(끝점)을 지나 반대쪽으로."""
            pts = []
            for k in range(1, steps + 1):
                f = math.pi * k / (steps + 1)
                pts.append((cx + r * (sx_ * math.cos(f) + mx_ * math.sin(f)),
                            cy + r * (sy_ * math.cos(f) + my_ * math.sin(f))))
            return pts

        front = cap(sx, sy, ps["chest_r"], nx_ := -ty, ny_ := tx, tx, ty)      # 윗선 끝 → 앞쪽 → 아랫선 끝
        rear = cap(hx, hy, ps["hip_r"], ty, -tx, -tx, -ty)                     # 아랫선 끝 → 뒤쪽 → 윗선 시작
        loop = top + front + bot[::-1] + rear
        m = len(loop)
        path = QPainterPath()
        pt = lambda q: _pt(q[0], q[1])
        path.moveTo(pt(loop[0]))
        for i in range(m):
            P0, P1, P2, P3 = loop[i - 1], loop[i], loop[(i + 1) % m], loop[(i + 2) % m]
            c1 = (P1[0] + (P2[0] - P0[0]) / 6, P1[1] + (P2[1] - P0[1]) / 6)
            c2 = (P2[0] - (P3[0] - P1[0]) / 6, P2[1] - (P3[1] - P1[1]) / 6)
            path.cubicTo(pt(c1), pt(c2), pt(P2))
        path.closeSubpath()
        mid_r = (ps["hip_r"] + ps["chest_r"]) / 2 - 1.5
        return path, {"M": M, "mid_r": mid_r, "bot_mid": bot[n // 2], "n": (nx, ny)}

    def _body(self, p, ps):
        H = (ps["hx"], ps["hy"])
        S = (ps["sx"], ps["sy"])
        dx, dy = S[0] - H[0], S[1] - H[1]
        d = math.hypot(dx, dy) or 1e-6
        nx, ny = -dy / d, dx / d                    # 몸의 '위쪽' 법선
        path, info = self._body_path(ps)
        M, mid_r, bm = info["M"], info["mid_r"], info["bot_mid"]
        sag = ps["sag"]
        sk = self.skin
        rot = -math.degrees(math.atan2(dy, dx))     # 줄무늬가 척추 방향을 따라 돌아가게
        body_brush = sk.brush("body", M[0], M[1], rot) if sk else None
        self._neck(p, ps, outline=True, brush=body_brush)      # 목도 같은 털 브러시라 몸통과 무늬가 이어진다
        if sk:
            self._halo(p, path)
            self._fluff(p, path, sk.avg["body"], wide=True)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(body_brush)
        else:
            p.setPen(QPen(C_OUT, OUTLINE_W, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            p.setBrush(C_BODY)
        p.drawPath(path)
        # 안쪽 무늬는 몸 경로로 잘라서 그린다
        p.save()
        p.setClipPath(path)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(sk.brush("cream", M[0], M[1], rot) if sk else C_CREAM)
        lift = 0.42 * (mid_r + sag)
        bc = _pt(bm[0] + nx * lift, bm[1] + ny * lift)                 # 처진 배선 바로 위
        cc = _pt(S[0] + 7, S[1] - ps["chest_r"] * 0.55)
        # 배·가슴의 연한 털: 크기가 다른 타원을 겹쳐 가장자리가 번지게 한다 (실사는 경계가 딱 떨어지지 않음)
        steps = tuple((1.28 - 0.1 * i, op) for i, op in enumerate(
            (0.2, 0.26, 0.42, 0.7, 0.92))) if sk else ((1.0, 1.0),)
        for grow, op in steps:
            p.setOpacity(op)
            p.drawEllipse(bc, d * 0.42 * grow, (mid_r * 0.62 + sag * 0.5) * grow)
            p.drawEllipse(cc, ps["chest_r"] * 0.62 * grow, ps["chest_r"] * 0.7 * grow)
        p.setOpacity(1.0)
        if sk:                                           # 입체감: 위는 밝게, 아래는 어둡게
            r = path.boundingRect()
            grad = QLinearGradient(0, r.top(), 0, r.bottom())
            grad.setColorAt(0.0, QColor(255, 255, 255, 30))
            grad.setColorAt(0.5, QColor(0, 0, 0, 0))
            grad.setColorAt(1.0, QColor(20, 10, 0, 85))
            p.setBrush(QBrush(grad))
            p.drawRect(r)
        else:
            p.setPen(QPen(C_STRIPE, 3.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            for i in range(1, 6):
                u = i / 6
                bx, by = _bez(H, M, S, u)
                r = ps["hip_r"] + (ps["chest_r"] - ps["hip_r"]) * u
                p.drawLine(_pt(bx + nx * (r + 2), by + ny * (r + 2)),
                           _pt(bx + nx * (r * 0.35), by + ny * (r * 0.35) - 2))
            p.drawLine(_pt(H[0] - 14, H[1] + 4), _pt(H[0] - 2, H[1] + 8))
            p.drawLine(_pt(H[0] - 15, H[1] - 6), _pt(H[0] - 3, H[1] - 3))
        p.restore()
        if sk:                                              # 실사는 윤곽선이 없어서 목을 한 번 더 덮을 필요가 없다
            self._fuzz(p, path, 190, offset=3, length=1.0)
            # 배 아래와 가슴 앞은 아주 약간만 더 부드럽게 (길게 늘어뜨리지 않는다)
            self._fuzz(p, path, 60, offset=19, length=1.1, sel=("ny", 0.35), gravity=0.12)
            self._fuzz(p, path, 32, offset=23, length=1.0, sel=("nx", 0.5))
        else:
            self._neck(p, ps, outline=False)                # 목 아랫부분이 몸통 윤곽선을 덮어 자연스럽게 이어 붙임
        return path

    def _throat(self, p, ps, body_path):
        """목 앞쪽(턱 밑~가슴)을 얼굴·배와 같은 흰 털로 덮어 가슴의 흰 부분과 이어 준다.
        몸통을 그린 뒤, 머리를 그리기 전에 그려서 턱 밑으로 흰 털이 보이게 한다."""
        sk = self.skin
        cx, cy = self._head_center(ps)
        sx, sy = ps["sx"], ps["sy"]
        L = math.hypot(cx - sx, cy - sy) or 1.0
        ux, uy = (cx - sx) / L, (cy - sy) / L                       # 어깨 → 머리 방향
        fx, fy = uy, -ux                                            # 앞쪽(몸이 향하는 쪽) 법선
        tx, ty = cx - ux * 9 + fx * 5, cy - uy * 9 + fy * 5         # 턱 바로 밑
        bx, by = sx + fx * 8 - ux * 4, sy + fy * 8 - uy * 4         # 가슴의 흰 부분 위쪽
        mx, my = (tx + bx) / 2, (ty + by) / 2
        ln = math.hypot(tx - bx, ty - by)
        ang = math.degrees(math.atan2(-(ty - by), tx - bx))
        neck = capsule(sx + 2, sy + 2, cx - 3.5, cy - 3.5, 13.2, 12.4, simplify=False)
        clip = QPainterPath(neck)
        clip.setFillRule(Qt.FillRule.WindingFill)
        clip.addPath(body_path)
        p.save()
        p.setClipPath(clip)
        p.translate(_pt(mx, my))
        p.rotate(ang)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(sk.brush("cream", sx, sy))
        for grow, op in ((1.4, 0.12), (1.25, 0.18), (1.1, 0.26), (0.96, 0.42), (0.82, 0.75)):
            p.setOpacity(op)
            p.drawEllipse(QPointF(0, 0), (ln / 2 + 5) * grow, 8.5 * grow)
        p.restore()

    def head_top(self, ps):
        """머리 꼭대기(귀 끝 높이) 위치 (로컬 좌표, y 위쪽). 말풍선을 머리에 붙이는 데 쓴다."""
        cx, cy = self._head_center(ps)
        k = self.skin.head_scale if self.skin else 1.0
        off = 34.0 * k + 2.0                          # 머리 중심에서 귀 끝까지
        a = math.radians(ps["hrot"])
        return cx - math.sin(a) * off, cy + math.cos(a) * off

    def _head_center(self, ps):
        """머리 중심. 실사 스킨은 목을 5% 짧게(어깨에서 머리까지 거리 ×neck_k) 한다."""
        k = self.skin.neck_k if self.skin else 1.0
        return ps["sx"] + ps["hdx"] * k, ps["sy"] + ps["hdy"] * k

    def _neck(self, p, ps, outline, brush=None):
        cx, cy = self._head_center(ps)
        sk = self.skin
        p.save()
        if sk:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(brush)
            neck = capsule(ps["sx"] + 2, ps["sy"] + 2, cx - 3.5, cy - 3.5, 13.2, 12.4)
            p.drawPath(neck)
            # 어깨에서 머리 쪽으로 갈수록 머리 털색이 섞여서 목과 얼굴의 밝기·색이 자연스럽게 이어진다
            g = QLinearGradient(QPointF(ps["sx"] + 2, -(ps["sy"] + 2)), QPointF(cx, -cy))
            c0, c1 = QColor(sk.head_col), QColor(sk.head_col)
            c0.setAlpha(0)
            c1.setAlpha(190)
            g.setColorAt(0.0, c0)
            g.setColorAt(0.35, QColor(sk.head_col.red(), sk.head_col.green(), sk.head_col.blue(), 70))
            g.setColorAt(1.0, c1)
            p.setBrush(QBrush(g))
            p.drawPath(neck)
        elif outline:
            p.setPen(QPen(C_OUT, OUTLINE_W, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            p.setBrush(C_BODY)
            p.drawPath(capsule(ps["sx"] + 2, ps["sy"] + 2, cx - 4, cy - 4, 15, 14))
        else:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(C_BODY)
            p.drawPath(capsule(ps["sx"] + 4, ps["sy"] + 4, cx - 4, cy - 4, 12.5, 12.5))
        p.restore()

    # ------------------------------------------------------------ 머리
    def _head_photo(self, p, ps, blink):
        """실사 머리 사진 + 움직이는 귀 + 털 질감 눈꺼풀/입 (머리 중심 기준 좌표)."""
        sk = self.skin
        p.drawPixmap(sk.head_rect, sk.pix["head"], QRectF(sk.pix["head"].rect()))
        # 귀: 밑동(피벗)을 기준으로 뒤로 눕거나(+) 앞으로 선다(-)
        for key, flat in (("near", ps["earN"]), ("far", ps["earF"])):
            pm, (px, py), rect = sk.ears[key]
            p.save()
            p.translate(px, py)
            p.rotate(-flat * 0.9)
            p.drawPixmap(rect.translated(-px, -py), pm, QRectF(pm.rect()))
            p.restore()
        self._mouth_photo(p, ps)
        o = ps["eyeO"] * (1 - blink)
        happy = ps["eyeH"] > 0.5
        w, h = sk.lid_size
        for i, (ex, ey) in enumerate(sk.eyes):
            if not (happy or o < 0.45):
                continue
            full = happy or o < 0.18
            frac = 1.0 if full else 1.0 - o / 0.45
            p.save()
            p.translate(ex, ey)
            p.setClipRect(QRectF(-w / 2, -h / 2, w, h * frac))
            p.drawPixmap(QRectF(-w / 2, -h / 2, w, h), sk.lids[i % 2], QRectF(sk.lids[i % 2].rect()))
            p.setClipping(False)
            if full:
                rx, ry = w / 2 * 0.78, h / 2
                path = QPainterPath()
                if happy:                                                       # ^ ^
                    path.moveTo(-rx, ry * 0.30)
                    path.quadTo(0, -ry * 0.95, rx, ry * 0.30)
                else:                                                           # 감은 눈 (아래로 살짝 처진 속눈썹 선)
                    path.moveTo(-rx, -ry * 0.05)
                    path.quadTo(0, ry * 0.85, rx, -ry * 0.05)
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.setPen(QPen(QColor(20, 12, 8, 45), 2.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
                p.drawPath(path.translated(0, 0.5))                             # 눈꺼풀 아래 옅은 그림자
                p.setPen(QPen(QColor(40, 26, 16, 215), 0.9, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
                p.drawPath(path)
                lash = QPainterPath()                                           # 바깥쪽 끝에 잔 속눈썹
                sx = rx if i == 0 else -rx
                for k, a in enumerate((-0.5, 0.0, 0.5)):
                    lash.moveTo(sx * 0.9, -0.2 + (ry * 0.15 if not happy else 0))
                    lash.lineTo(sx * 1.12, a * 1.2 + (0.9 if not happy else -0.6))
                p.setPen(QPen(QColor(35, 22, 14, 150), 0.7, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
                p.drawPath(lash)
            p.restore()

    def _mouth_photo(self, p, ps):
        """입: 턱 조각이 실제로 내려가고, 그 틈으로 입속(윗니·혀)이 보인다. 혀를 내밀면 턱 위로 늘어진다."""
        sk = self.skin
        m = max(0.0, min(1.0, ps["mouth"]))
        drop = m * 5.0                                       # 턱이 내려가는 양 (단위)
        tongue = ps["tongue"]
        lx, ly = sk.lip                                      # 윗입술 선 위 입 중심 (머리 중심 기준, y 아래가 +)
        jaw_pm, jaw_rect = sk.jaw
        if drop > 0.3:
            w = 3.5 + 0.35 * drop                            # 입 반폭
            bot = ly + drop + 1.6                            # 턱 조각에 가려질 아래쪽
            mouth = QPainterPath()
            mouth.moveTo(lx - w, ly + 0.2)
            mouth.quadTo(lx - w * 0.5, ly - 1.3, lx, ly - 0.7)             # 윗입술은 M 자 곡선
            mouth.quadTo(lx + w * 0.5, ly - 1.3, lx + w, ly + 0.2)
            mouth.quadTo(lx + w * 1.06, ly + drop * 0.6, lx + w * 0.82, bot)
            mouth.lineTo(lx - w * 0.82, bot)
            mouth.quadTo(lx - w * 1.06, ly + drop * 0.6, lx - w, ly + 0.2)
            grad = QLinearGradient(0, ly, 0, bot)
            grad.setColorAt(0.0, QColor("#3f1019"))
            grad.setColorAt(1.0, QColor("#8c3846"))
            p.save()
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(grad))
            p.drawPath(mouth)
            if m > 0.45:                                     # 윗송곳니
                p.setBrush(QColor(246, 240, 228))
                for sx in (-1, 1):
                    fx = lx + sx * w * 0.62
                    p.drawPolygon(QPolygonF([QPointF(fx - 0.7, ly - 0.2), QPointF(fx + 0.7, ly - 0.2),
                                             QPointF(fx, ly + 1.3 + (m - 0.45) * 1.8)]))
            if m > 0.3:                                      # 입 안의 혀 (턱 조각 뒤에 놓여 입 안쪽처럼 보임)
                p.setBrush(QColor("#d96b7b"))
                p.drawEllipse(QPointF(lx, ly + drop * 0.9 + 0.2), w * 0.72, 0.9 + drop * 0.16)
            p.restore()
        p.save()
        p.translate(0, drop)
        p.drawPixmap(jaw_rect, jaw_pm, QRectF(jaw_pm.rect()))
        p.restore()
        if tongue > 0.04:
            t = min(1.0, tongue)
            L = 1.6 + 5.6 * t                                # 혀 길이
            wd = 3.5                                         # 혀 폭
            curl = 0.9 * t                                   # 끝이 살짝 앞(오른쪽)으로 말림
            x0, y0 = lx + 0.1, ly + drop * 0.55 + 0.4
            tp = QPainterPath()
            tp.moveTo(x0 - wd / 2, y0)
            tp.lineTo(x0 - wd / 2 + 0.1, y0 + L - wd * 0.55)
            tp.cubicTo(x0 - wd / 2, y0 + L + 0.5, x0 + curl - 0.3, y0 + L + 0.9, x0 + curl + 0.4, y0 + L + 0.2)
            tp.cubicTo(x0 + wd / 2 + curl, y0 + L - 0.2, x0 + wd / 2 + curl * 0.6, y0 + L - wd * 0.5, x0 + wd / 2, y0 + L - wd * 0.9)
            tp.lineTo(x0 + wd / 2, y0)
            tp.closeSubpath()
            p.save()
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(30, 10, 14, 55))               # 혀가 턱 털 위에 드리우는 옅은 그림자
            p.drawPath(tp.translated(0.5, 0.8))
            grad = QLinearGradient(0, y0, 0, y0 + L)
            grad.setColorAt(0.0, QColor("#c9566a"))
            grad.setColorAt(0.55, QColor("#ec8b98"))
            grad.setColorAt(1.0, QColor("#f4a6b0"))
            p.setBrush(QBrush(grad))
            p.setPen(QPen(QColor(150, 60, 76, 190), 0.55))
            p.drawPath(tp)
            p.setPen(QPen(QColor(170, 70, 88, 150), 0.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.drawLine(QPointF(x0, y0 + 0.9), QPointF(x0 + curl * 0.5, y0 + L - 1.3))      # 혀 가운데 홈
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(255, 255, 255, 80))
            p.drawEllipse(QPointF(x0 - wd * 0.18 + curl * 0.3, y0 + L * 0.55), 0.55, 1.4)  # 침 기운 같은 반짝임
            p.restore()

    def _head(self, p, ps, blink):
        cx, cy = self._head_center(ps)
        p.save()
        p.translate(_pt(cx, cy))
        p.rotate(-ps["hrot"])
        if self.skin:
            p.scale(self.skin.head_scale, self.skin.head_scale)      # 사진 머리가 커 보여서 줄임
            self._head_photo(p, ps, blink)
            p.restore()
            return
        outline = QPen(C_OUT, OUTLINE_W, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)

        def ear(x, y, base_w, h, flat, col, inner):
            p.save()
            p.translate(x, y)
            p.rotate(-flat * 0.9)
            tri = QPolygonF([QPointF(-base_w, 0), QPointF(base_w, 0), QPointF(base_w * 0.15, -h)])
            p.setPen(outline)
            p.setBrush(col)
            p.drawPolygon(tri)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(inner)
            p.drawPolygon(QPolygonF([QPointF(-base_w * 0.55, -1), QPointF(base_w * 0.55, -1),
                                     QPointF(base_w * 0.12, -h * 0.68)]))
            p.restore()

        # 먼 쪽 귀 (머리 뒤)
        ear(8, -14, 8.5, 17, ps["earF"], C_BODY_FAR, C_EAR_IN.darker(108))
        # 얼굴
        p.setPen(outline)
        p.setBrush(C_BODY)
        p.drawEllipse(QPointF(0, 0), 22, 19)
        # 가까운 귀
        ear(-8, -14, 9, 18, ps["earN"], C_BODY, C_EAR_IN)
        # 이마 줄무늬
        p.setPen(QPen(C_STRIPE, 2.4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawLine(QPointF(-2, -17), QPointF(-2, -10))
        p.drawLine(QPointF(5, -18), QPointF(5, -11))
        p.drawLine(QPointF(-9, -15), QPointF(-8, -9))
        # 볼 털 (뒤쪽)
        p.setPen(QPen(C_STRIPE, 2.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawLine(QPointF(-18, 4), QPointF(-10, 6))
        p.drawLine(QPointF(-17, 9), QPointF(-9, 9))
        # 주둥이
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(C_CREAM)
        p.drawEllipse(QPointF(11, 6), 11.5, 8.6)
        # 코
        p.setBrush(C_NOSE)
        p.setPen(QPen(C_OUT, 1.0))
        p.drawPolygon(QPolygonF([QPointF(17.5, 0.6), QPointF(23, 0.6), QPointF(20.5, 4.2)]))
        # 입
        m = ps["mouth"]
        p.setPen(QPen(C_OUT, 1.3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        if m < 0.12:
            path = QPainterPath(QPointF(20.5, 4.2))
            path.lineTo(20.5, 6.5)
            p.drawPath(path)
            p.drawArc(QRectF(15.2, 5.2, 5.4, 4.2), 180 * 16, 180 * 16)
            p.drawArc(QRectF(20.4, 5.2, 5.4, 4.2), 180 * 16, 180 * 16)
        else:
            h = 3 + m * 10
            p.setBrush(C_MOUTH)
            mouth = QPainterPath()
            mouth.moveTo(15, 7)
            mouth.quadTo(20, 7 + h * 1.5, 25.5, 7)
            mouth.quadTo(20, 6, 15, 7)
            p.drawPath(mouth)
            if ps["tongue"] > 0.05:
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(C_TONGUE)
                p.drawEllipse(QPointF(20.5, 7 + h * 0.95), 3.6, 2.2 + ps["tongue"] * 4.2)
        # 수염
        p.setPen(QPen(QColor(255, 255, 255, 215), 1.0))
        w = ps["whisk"]
        for dy_, ang in ((3, -8 + w * 6), (6, 2 + w * 4), (9, 12 + w * 2)):
            a = math.radians(ang)
            p.drawLine(QPointF(19, dy_), QPointF(19 + 17 * math.cos(a), dy_ + 17 * math.sin(a)))
        # 눈
        self._eye(p, ps, 2.8, -2.0, 5.2, 6.2, blink)
        self._eye(p, ps, 14.8, -2.0, 4.2, 5.4, blink)
        p.restore()

    def _eye(self, p, ps, x, y, rx, ry, blink):
        o = ps["eyeO"] * (1 - blink)
        happy = ps["eyeH"]
        p.save()
        p.translate(x, y)
        if happy > 0.5:                                     # ^ ^ 기분 좋은 눈
            p.setPen(QPen(C_OUT, 2.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.drawArc(QRectF(-rx, -ry * 0.5, rx * 2, ry * 1.5), 20 * 16, 140 * 16)
        elif o < 0.18:                                      # 감은 눈
            p.setPen(QPen(C_OUT, 1.9, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.drawArc(QRectF(-rx, -ry * 0.9, rx * 2, ry * 1.4), 200 * 16, 140 * 16)
        else:
            h = ry * (0.35 + 0.65 * o)
            p.setPen(QPen(C_OUT, 1.2))
            p.setBrush(C_EYE)
            p.drawEllipse(QPointF(0, 0), rx, h)
            lx, ly = ps["lookx"] * rx * 0.35, ps["looky"] * h * 0.3
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor("#2a1f1a"))
            p.drawEllipse(QPointF(lx, ly), rx * 0.42, h * 0.88)
            p.setBrush(QColor(255, 255, 255, 235))
            p.drawEllipse(QPointF(lx - rx * 0.18, ly - h * 0.3), rx * 0.2, rx * 0.2)
        p.restore()



