"""사진 부품 뼈대 인형: 사진에서 오려 낸 몸통·다리·꼬리·머리(assets/parts)를 관절 값에 맞춰 늘이고 구부려 붙여서 그린다.

CatRig 와 같은 포즈 값(animations.py 의 33개 동작)을 그대로 받는다. 관절 계산(IK)·꼬리 시뮬레이션·머리 위치는 CatRig 것을 쓰고,
도형+질감 대신 사진 조각을 붙이는 부분만 바꿨다.
 · 다리·꼬리·목: 곧게 펴서 오린 '띠'를 관절 점들을 따라 구부려 붙인다 (짧은 조각 여러 개를 이어 그린다).
 · 몸통: 사진을 가로 조각으로 나눠 척추 곡선을 따라 배치하고, 조각 두께를 포즈의 몸통 두께(등 휨·배 처짐·가슴 두께)에 맞춘다.
 · 머리: 사진 머리를 머리 중심에 붙이고 기울기(hrot)만큼 돌린다. 눈 감김은 눈꺼풀색 조각으로 덮는다.
"""
import json
import math
from pathlib import Path

import numpy as np
from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QImage, QPainter, QPixmap, QTransform

import coats
from catrig import CatRig, _bez, _pt

S0 = 0.40                          # 사진 한 픽셀 = 뼈대 단위 0.40 (사진 고양이를 뼈대 크기에 맞춘 배율)
HEAD_K = 1.0                       # 머리 크기 배율 (사진 그대로 = 1.0)
FAR_DARK = 0.70                    # 먼 쪽 다리는 어둡게
XH, XS = 187.0, 360.0              # 사진에서 엉덩이/어깨 관절의 가로 위치 (몸통 조각 배치 기준)


def _to_arr(img: QImage):
    img = img.convertToFormat(QImage.Format.Format_RGBA8888)
    ptr = img.constBits()
    ptr.setsize(img.sizeInBytes())
    return np.frombuffer(ptr, np.uint8).reshape(img.height(), img.width(), 4).copy()


def _to_qimage(arr):
    arr = np.ascontiguousarray(arr)
    return QImage(arr.data, arr.shape[1], arr.shape[0], arr.shape[1] * 4, QImage.Format.Format_RGBA8888).copy()


ITER = 3                           # 꺾인 관절을 둥글게 다듬는 정도 (많을수록 둥글다)


def _smooth_chain(pts, n):
    """점들을 지나는 부드러운 선(Chaikin 2회)을 호 길이 기준으로 n 개 점으로 다시 뽑는다."""
    p = [tuple(map(float, q)) for q in pts]
    for _ in range(ITER):
        q = [p[0]]
        for a, b in zip(p, p[1:]):
            q.append((0.75 * a[0] + 0.25 * b[0], 0.75 * a[1] + 0.25 * b[1]))
            q.append((0.25 * a[0] + 0.75 * b[0], 0.25 * a[1] + 0.75 * b[1]))
        q.append(p[-1])
        p = q
    seg = [math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(p, p[1:])]
    total = sum(seg) or 1e-6
    out, k, acc = [], 0, 0.0
    for i in range(n):
        target = total * i / (n - 1)
        while k < len(seg) - 1 and acc + seg[k] < target:
            acc += seg[k]
            k += 1
        f = 0.0 if seg[k] == 0 else min(1.0, max(0.0, (target - acc) / seg[k]))
        out.append((p[k][0] + (p[k + 1][0] - p[k][0]) * f, p[k][1] + (p[k + 1][1] - p[k][1]) * f))
    return out, total


class PuppetRig(CatRig):
    """CatRig 와 같은 draw() 를 가진 사진 부품 인형."""

    def __init__(self, folder: Path, coat: str = "brown", dpr: float = 1.0, scale: float = 0.8):
        super().__init__(None)
        self.dir = Path(folder)
        self.meta = json.loads((self.dir / "parts.json").read_text(encoding="utf-8"))
        self.uv = np.load(self.dir / "uv.npz")
        self.coat = "brown"
        self.dpr, self.sc = dpr, scale
        self.pm = {}
        self._set_coat(coat)

    # ------------------------------------------------------------ 부품 불러오기 (털색·화면 크기에 맞춰 미리 줄여 둔다)
    def set_coat(self, coat):
        if coat != self.coat:
            self._set_coat(coat)

    def _set_coat(self, coat):
        self.coat = coat if coat in coats.COAT_KEYS else "brown"
        f = S0 * self.sc * self.dpr                 # 사진 픽셀 → 화면(물리) 픽셀
        self.pm = {}
        for name in ("front_a", "front_b", "hind_a", "hind_b", "tail", "neck", "head", "torso"):
            arr = _to_arr(QImage(str(self.dir / f"{name}.png")))
            if self.coat != "brown":
                u = self.uv[name].astype(np.float32)
                arr = coats.recolor(arr, self.coat, (u[..., 0], u[..., 1]))
            far = arr.copy()
            far[..., :3] = (far[..., :3].astype(np.float32) * FAR_DARK).astype(np.uint8)
            for key, a in ((name, arr), (name + "_far", far)):
                if key.endswith("_far") and name not in ("front_a", "front_b", "hind_a", "hind_b"):
                    continue
                img = _to_qimage(a).convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
                w, h = max(1, round(img.width() * f)), max(1, round(img.height() * f))
                img = img.scaled(w, h, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
                self.pm[key] = QPixmap.fromImage(img)
        self._f = f
        # 몸통 열별 등선·배선 (사진 픽셀, 몸통 크롭 기준)
        t = self.meta["torso"]
        self._top = np.array(t["top"], np.float32)
        self._bel = np.array(t["belly"], np.float32)
        self._torso_x0 = float(t["x0"])

    # ------------------------------------------------------------ 띠 그리기 (곧은 띠를 점들을 따라 구부려 붙임)
    def _ribbon(self, p, key, pts, width_k=1.0, end_ext=0.0, n=None):
        pm = self.pm[key]
        base = key.replace("_far", "")
        info = self.meta["tail"] if base == "tail" else self.meta["neck"] if base == "neck" else self.meta["legs"][base]
        pts = [tuple(q) for q in pts]
        if end_ext:
            ax, ay = pts[-2]
            bx, by = pts[-1]
            d = math.hypot(bx - ax, by - ay) or 1.0
            pts[-1] = (bx + (bx - ax) / d * end_ext, by + (by - ay) / d * end_ext)
        n = n or 26
        ch, total = _smooth_chain(pts, n + 1)
        hpix, wpix = pm.height(), pm.width()
        w = info["size"][0] * S0 * width_k                         # 띠 폭 (뼈대 단위)
        for i in range(n):
            ax, ay = ch[i]
            bx, by = ch[i + 1]
            dx, dy = bx - ax, -(by - ay)                           # 화면 좌표(y 아래)
            ln = math.hypot(dx, dy)
            if ln < 1e-6:
                continue
            ang = math.degrees(math.atan2(-dx, dy))                # 로컬 +y(아래) 가 진행 방향을 향하도록
            v0, v1 = hpix * i / n, hpix * (i + 1) / n
            p.save()
            p.translate(_pt(ax, ay))
            p.rotate(ang)
            ov = 0.5 / self._f * self._f                            # 이웃 조각과 겹치게 (꺾이는 곳에서 틈이 안 생기게)
            p.drawPixmap(QRectF(-w / 2, -0.5, w, ln + 1.0), pm, QRectF(0, max(0.0, v0 - 0.5 * self._f), wpix, min(hpix, v1 + 0.5 * self._f) - max(0.0, v0 - 0.5 * self._f)))
            p.restore()

    # ------------------------------------------------------------ 다리
    def _chain(self, joints, ps, side):
        return [tuple(q) for q in joints]

    def _far_legs(self, p, ps, j):
        if ps["flover"] < 0.5:
            self._ribbon(p, "front_b_far", j["FF"], 1.0, end_ext=3.0)
        self._ribbon(p, "hind_b_far", j["HF"], 1.0, end_ext=3.0)

    def _near_legs(self, p, ps, j):
        self._ribbon(p, "hind_a", j["HN"], 1.0, end_ext=3.0)
        if ps["flover"] < 0.5:
            self._ribbon(p, "front_a", j["FN"], 1.0, end_ext=3.0)

    def _front_legs_over(self, p, ps, j):
        self._ribbon(p, "front_b_far", j["FF"], 1.0, end_ext=3.0)
        self._ribbon(p, "front_a", j["FN"], 1.0, end_ext=3.0)

    # ------------------------------------------------------------ 꼬리
    def _tail(self, p, pts):
        self._ribbon(p, "tail", pts, 1.0, n=14)

    # ------------------------------------------------------------ 몸통
    def _spine(self, ps):
        """CatRig._body_path 와 같은 등/배 곡선: u(0=엉덩이,1=어깨) → (중심, 위쪽 법선, 접선, 위 두께, 아래 두께)."""
        hx, hy, sx, sy = ps["hx"], ps["hy"], ps["sx"], ps["sy"]
        dx, dy = sx - hx, sy - hy
        d = math.hypot(dx, dy) or 1e-6
        nx, ny = -dy / d, dx / d
        ext = (ps["FNx"] + ps["FFx"]) / 2 - (ps["HNx"] + ps["HFx"]) / 2 - 60.0
        flex = max(-7.0, min(7.0, -0.11 * ext))
        arch = ps["arch"] * 1.4 + ps["hump"] + flex
        Hh, Ss = (hx, hy), (sx, sy)
        M = ((hx + sx) / 2 + nx * arch, (hy + sy) / 2 + ny * arch)

        def at(u):
            uc = min(1.0, max(0.0, u))
            B = _bez(Hh, M, Ss, uc)
            B1, B0 = _bez(Hh, M, Ss, min(1.0, uc + 0.02)), _bez(Hh, M, Ss, max(0.0, uc - 0.02))
            ux, uy = B1[0] - B0[0], B1[1] - B0[1]
            dn = math.hypot(ux, uy) or 1.0
            tx, ty = ux / dn, uy / dn
            if u < 0 or u > 1:                                     # 양 끝 밖은 접선 방향으로 곧게 연장
                B = (B[0] + tx * (u - uc) * d, B[1] + ty * (u - uc) * d)
            r = ps["hip_r"] * (1 - uc) + ps["chest_r"] * uc + 1.2 * math.sin(math.pi * uc)
            bump = math.sin(math.pi * min(1.0, max(0.0, (uc - 0.1) / 0.8))) ** 1.5
            rt = r + 0.6 * ps["hump"] * math.sin(math.pi * uc)
            rb = r + ps["sag"] * bump
            return B, (-ty, tx), (tx, ty), rt, rb

        return at, d

    def _body(self, p, ps):
        pm = self.pm["torso"]
        at, d = self._spine(ps)
        x0 = self._torso_x0
        wcols = pm.width() / self._f                                # 사진 픽셀 단위 폭
        step = 8
        i = 0
        ncols = int(round(wcols))
        # 가장 안쪽(기준) 열의 두께: 두께 보정의 기준
        def col(cx):
            return max(0, min(ncols - 1, int(cx)))
        slices = []
        for c0 in range(0, ncols, step):
            c1 = min(ncols, c0 + step)
            slices.append((c0, c1))
        for c0, c1 in slices:
            cm = (c0 + c1) / 2.0
            xph = x0 + cm                                          # 사진의 가로 위치
            u = (xph - XH) / (XS - XH)
            B, nrm, tan, rt, rb = at(u)
            # 이 열의 사진 두께와 (안쪽으로 맞춘) 기준 열의 두께
            top, bel = self._top[col(cm)], self._bel[col(cm)]
            ht = (bel - top) / 2.0 * S0                            # 사진 반두께 (뼈대 단위)
            uc = min(1.0, max(0.0, u))
            xr = XH + uc * (XS - XH) - x0
            htr = (self._bel[col(xr)] - self._top[col(xr)]) / 2.0 * S0
            k = ((rt + rb) / 2.0) / max(htr, 1.0)                  # 사진 몸통 두께를 포즈 몸통 두께에 맞추는 배율
            half = ht * k
            # 사진에서 이 열의 중심 행이 기준 열 중심 행보다 얼마나 위/아래인지 (몸통이 휘는 선)
            yc = (top + bel) / 2.0
            ycr = (self._top[col(xr)] + self._bel[col(xr)]) / 2.0
            off = (ycr - yc) * S0 * k                              # 위(+)로 이동할 양
            cx_, cy_ = B[0] + nrm[0] * ((rt - rb) / 2.0 + off), B[1] + nrm[1] * ((rt - rb) / 2.0 + off)
            # 이 조각이 차지하는 척추 길이
            Bn, _, _, _, _ = at(u + (c1 - c0) * S0 / d * (1.0 if True else 1.0))
            ln = math.hypot(Bn[0] - B[0], Bn[1] - B[1]) or (c1 - c0) * S0
            ln = max(ln, (c1 - c0) * S0 * 0.7)
            ang = math.degrees(math.atan2(-tan[1], tan[0]))
            p.save()
            p.translate(_pt(cx_, cy_))
            p.rotate(ang)
            src = QRectF(c0 * self._f - 0.5, max(0.0, (top - 1) * self._f), (c1 - c0) * self._f + 1.0,
                         min(pm.height(), (bel + 2) * self._f) - max(0.0, (top - 1) * self._f))
            hs = half + 0.6
            p.drawPixmap(QRectF(-ln / 2 - 0.35, -hs, ln + 0.7, 2 * hs), pm, src)
            p.restore()
        return None

    def _throat(self, p, ps, body_path):
        pass

    # ------------------------------------------------------------ 머리·목
    def head_top(self, ps):
        cx, cy = self._head_center(ps)
        a = math.radians(ps["hrot"])
        off = self.meta["head"]["anchor"][1] * S0 * HEAD_K + 2.0
        return cx - math.sin(a) * off, cy + math.cos(a) * off

    def _head(self, p, ps, blink):
        cx, cy = self._head_center(ps)
        sx, sy = ps["sx"], ps["sy"]
        # 목: 어깨 위쪽에서 머리 중심까지
        self._ribbon(p, "neck", [(sx + 6, sy + 10), ((sx + cx) / 2 + 2, (sy + cy) / 2 + 4), (cx - 2, cy - 2)], 1.0, n=6)
        pm = self.pm["head"]
        ax, ay = self.meta["head"]["anchor"]
        p.save()
        p.translate(_pt(cx, cy))
        p.rotate(-ps["hrot"])
        k = HEAD_K
        p.drawPixmap(QRectF(-ax * S0 * k, -ay * S0 * k, pm.width() / self._f * S0 * k, pm.height() / self._f * S0 * k),
                     pm, QRectF(pm.rect()))
        p.restore()
