"""Animator: 동작 재생, 보행 위상 진행, 동작 전환 블렌딩."""
import random

import animations as A
from catrig import lerp_pose


class Animator:
    def __init__(self, name="stand"):
        self.name = name
        self.t = 0.0          # 현재 동작 시작 후 경과 시간
        self.clock = random.random() * 50          # 전역 시계 (꼬리/숨쉬기용)
        self.u = 0.0          # 보행 위상 0..1
        self.blend_dur = 0.25
        self.blend_t = 1.0
        self.from_pose = None
        self.last = None
        self.param = {}

    def play(self, name, blend=0.25, restart=False, **param):
        if name == self.name and not restart:
            self.param.update(param)
            return
        self.from_pose = self.last
        self.blend_dur, self.blend_t = max(1e-3, blend), 0.0
        if name not in A.GAITS or self.name not in A.GAITS:
            pass                                    # 보행 간 전환이 아니면 위상은 그대로 두어도 무방
        self.name, self.t, self.param = name, 0.0, dict(param)

    def update(self, dt, dist=0.0):
        self.t += dt
        self.clock += dt
        self.blend_t += dt / self.blend_dur
        g = A.GAITS.get(self.name)
        if g and dist:
            S, d = g
            self.u = (self.u + dist * d / S) % 1.0

    def pose(self):
        p = A.ANIMS[self.name](self)
        p.update(A.BODY_FEEL.get(self.name, {}))        # 자세별 배/등 느낌
        if self.from_pose is not None and self.blend_t < 1.0:
            p = lerp_pose(self.from_pose, p, A.smooth(self.blend_t))
        elif self.blend_t >= 1.0:
            self.from_pose = None
        self.last = p
        return p
