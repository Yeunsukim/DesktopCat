"""고양이 동작 라이브러리. 각 동작은 f(a) -> pose 이고 a 는 Animator(시간/보행 위상)다.

보행(walk/trot/run)은 '이동 거리'로 발 위상을 진행시켜 발이 바닥에서 미끄러지지 않는다.
"""
import math
from dataclasses import dataclass

from catrig import DEFAULT, lerp_pose, pose

PI = math.pi
ANIMS = {}
GAITS = {}          # 이름 → (보폭 S, 접지 비율 d)


def anim(name):
    def deco(fn):
        ANIMS[name] = fn
        return fn
    return deco


def smooth(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


def sn(t, hz, ph=0.0):
    return math.sin(2 * PI * hz * t + ph)


def ramp(t, t0, t1):
    return smooth((t - t0) / (t1 - t0))


# ============================================================ 공통 부품
def breathing(a, amp=0.7, hz=0.45):
    return amp * sn(a.clock, hz)


def tail_idle(a, tb=34, tw=22, tf=0.38):
    return {"tb": tb, "tw": tw, "tf": tf, "tc": 3}


def look_around(a, amp=1.0):
    """느리게 두리번거리는 머리/눈 움직임."""
    return {"lookx": amp * sn(a.clock, 0.11) * 0.9, "hrot": amp * 3 * sn(a.clock, 0.13, 1.0),
            "earN": 4 * max(0, sn(a.clock, 0.21, 0.4)) ** 6 * 6}


def ear_twitch(a):
    k = max(0.0, sn(a.clock, 0.17, 0.3)) ** 14
    return {"earF": 14 * k}


# ============================================================ 서기/앉기/식빵
@anim("stand")
def stand(a):
    b = breathing(a)
    return pose(look_around(a), tail_idle(a), ear_twitch(a),
                sy=58 + b, hy=55 + b * 0.6, hx=-31, sx=31, hip_r=22, chest_r=23,
                FNx=36, FFx=27, HNx=-34, HFx=-26, hdx=22, hdy=24 + b * 0.5)


@anim("sit")
def sit(a):
    b = breathing(a, 0.6)
    return pose(look_around(a), ear_twitch(a),
                hx=-22, hy=24, sx=20, sy=64 + b, hip_r=25, chest_r=21, arch=-2,
                FNx=30, FNy=0, FFx=24, FFy=0,
                HNx=6, HNy=0, HNa=0, fa_N=86, HFx=-4, HFy=0, fa_F=86,
                hdx=12, hdy=27 + b * 0.4,
                tb=-62, tc=-5, tw=12, tf=0.3, tp=0.5, shadow=1)


@anim("loaf")
def loaf(a):
    b = breathing(a, 0.5, 0.4)
    return pose(look_around(a, 0.4),
                hx=-26, hy=22, sx=24, sy=24 + b, hip_r=22, chest_r=21, arch=1,
                FNx=40, FNy=4, FFx=33, FFy=3, HNx=-8, HNy=2, fa_N=88, HFx=-14, HFy=1, fa_F=88,
                hdx=22, hdy=14, eyeO=0.75,
                tb=-35, tc=-3, tw=8, tf=0.25, tp=0.5)


# ============================================================ 보행
def leg(u, S, d, lift, x0):
    """발 궤적: 접지(몸 뒤로 밀림) → 공중(앞으로 휘둘러 나감). (x, y, 위상 w, 접지 여부) 반환."""
    u %= 1.0
    if u < d:
        w = u / d
        return x0 + S / 2 - S * w, 0.0, w, True
    w = (u - d) / (1 - d)
    e = w * w * (3 - 2 * w)
    return x0 - S / 2 + S * e, lift * math.sin(PI * min(1.0, w * 1.05)) ** 0.85, w, False


def _gait_pose(a, S, d, lift, offs, body, extra=None):
    u = a.u
    HN, FN, HF, FF = offs
    fnx, fny, fnw, fnst = leg(u + FN, S, d, lift, 36)
    ffx, ffy, ffw, ffst = leg(u + FF, S, d, lift, 27)
    hnx, hny, hnw, hnst = leg(u + HN, S, d, lift, -34)
    hfx, hfy, hfw, hfst = leg(u + HF, S, d, lift, -26)
    p = dict(
        FNx=fnx, FNy=fny, FNa=(-6 if fnst else -28 * math.sin(PI * fnw) + 8), FFx=ffx, FFy=ffy,
        FFa=(-6 if ffst else -28 * math.sin(PI * ffw) + 8),
        HNx=hnx, HNy=hny, HNa=0, HFx=hfx, HFy=hfy, HFa=0,
        fa_N=(34 + 14 * hnw ** 2) if hnst else 46 + 22 * math.sin(PI * hnw),
        fa_F=(34 + 14 * hfw ** 2) if hfst else 46 + 22 * math.sin(PI * hfw),
    )
    p.update(body)
    if extra:
        p.update(extra)
    return pose(**p)


GAITS["walk"] = (34.0, 0.62)


@anim("walk")
def walk(a):
    u = a.u
    bob = sn(u, 2)
    body = dict(sx=31, hx=-31, sy=58 + 1.1 * bob, hy=61 - 1.1 * bob, arch=1.2 * sn(u, 2, 1.0),
                hdx=23, hdy=23 + 1.2 * sn(u, 2, 0.5), hrot=2.5 * sn(u, 1) - 1, lookx=0.2,
                tb=42 + 1.2 * sn(u, 1), tw=16, tf=0.5, tc=3, earN=0, earF=0)
    return _gait_pose(a, 34.0, 0.62, 9.0, (0.0, 0.25, 0.5, 0.75), body)


GAITS["sneak"] = (22.0, 0.72)


@anim("sneak")
def sneak(a):
    u = a.u
    body = dict(sx=33, hx=-32, sy=40 + 0.8 * sn(u, 2), hy=44 - 0.8 * sn(u, 2), hip_r=22, chest_r=22,
                hdx=26, hdy=10, hrot=-8, tb=22, tc=1.5, tw=10, tf=0.4, earN=-6, earF=-6, eyeO=1, lookx=0.9)
    return _gait_pose(a, 22.0, 0.72, 6.0, (0.0, 0.25, 0.5, 0.75), body)


GAITS["trot"] = (46.0, 0.5)


@anim("trot")
def trot(a):
    u = a.u
    bob = sn(u, 2, 0.6)
    body = dict(sx=33, hx=-32, sy=58 + 2.5 * bob, hy=61 + 2.5 * bob, arch=1.5,
                hdx=24, hdy=24, hrot=-2, tb=52, tw=14, tf=0.9, tc=3, earN=8, earF=8)
    return _gait_pose(a, 46.0, 0.5, 12.0, (0.0, 0.5, 0.5, 0.0), body)


GAITS["run"] = (66.0, 0.34)


@anim("run")
def run(a):
    u = a.u
    ext = sn(u, 1, 0.9)
    body = dict(sx=36 + 5 * ext, hx=-35 - 4 * ext, sy=52 + 6 * ext, hy=50 - 6 * ext,
                arch=-6 * ext + 3, hip_r=21, chest_r=22,
                hdx=26, hdy=20, hrot=-6, mouth=0.15, tb=30, tc=1.5, tw=6, tf=1.4, tp=0.4,
                earN=26, earF=26, eyeO=1)
    return _gait_pose(a, 66.0, 0.34, 18.0, (0.0, 0.5, 0.12, 0.62), body)


# ============================================================ 키프레임 도구
def kf(t, keys, loop=False):
    """keys=[(시간, 포즈)] 사이를 부드럽게 보간. loop면 마지막 시간으로 순환."""
    if loop:
        t = t % keys[-1][0]
    if t <= keys[0][0]:
        return keys[0][1]
    for (t0, p0), (t1, p1) in zip(keys, keys[1:]):
        if t < t1:
            return lerp_pose(p0, p1, smooth((t - t0) / (t1 - t0)))
    return keys[-1][1]


def purr(a, amp=0.55, hz=26):
    return amp * sn(a.clock, hz)


# ============================================================ 잠자기 3종
@anim("sleep_curl")
def sleep_curl(a):
    """잠자기 1: 동그랗게 몸을 말고 잔다."""
    b = breathing(a, 1.0, 0.3)
    return pose(hx=-12, hy=21, sx=16, sy=24 + b * 0.7, hip_r=26, chest_r=24, arch=7 + b * 0.5,
                FNx=24, FNy=2, FFx=18, FFy=2, HNx=-2, HNy=2, fa_N=88, HFx=-6, HFy=2, fa_F=88,
                hdx=22, hdy=-5, hrot=-12, eyeO=0, mouth=0, earN=-6, earF=-4,
                tb=-24, tc=-15, tw=2.5, tf=0.2, tp=0.4, tfront=1)


@anim("sleep_side")
def sleep_side(a):
    """잠자기 2: 옆으로 누워 다리를 쭉 뻗고 잔다."""
    b = breathing(a, 1.2, 0.28)
    return pose(hx=-34, hy=18 + b * 0.5, sx=32, sy=19 + b, hip_r=19, chest_r=19, arch=1,
                FNx=66, FNy=11, FNa=18, FFx=60, FFy=21, FFa=24,
                HNx=-4, HNy=9, HNa=-6, fa_N=70, HFx=6, HFy=19, HFa=-6, fa_F=70,
                hdx=33, hdy=-3, hrot=-6, eyeO=0, earN=-10, earF=-8,
                tb=-6, tc=-2, tw=3, tf=0.2)


@anim("sleep_nap")
def sleep_nap(a):
    """잠자기 3: 식빵 자세로 턱을 앞발에 괴고 존다."""
    b = breathing(a, 0.8, 0.35)
    return pose(ear_twitch(a),
                hx=-24, hy=21, sx=24, sy=24 + b, hip_r=22, chest_r=21, arch=1,
                FNx=54, FNy=3, FFx=47, FFy=3, HNx=-6, HNy=2, fa_N=88, HFx=-12, HFy=1, fa_F=88,
                hdx=30, hdy=-6 + b * 0.4, hrot=-6, eyeO=0, earN=-4,
                tb=-20, tc=-4, tw=3, tf=0.25)


@anim("sleep_doze")
def sleep_doze(a):
    """앉아서 꾸벅꾸벅 조는 모습."""
    cyc = (a.clock * 0.22) % 1.0
    nod = smooth(cyc / 0.6) * (1 - smooth((cyc - 0.8) / 0.2))
    p = sit(a)
    p.update(eyeO=0.0 if nod > 0.3 else 0.15, hrot=-4 - 22 * nod, hdy=27 - 7 * nod, hdx=12 + 4 * nod, earN=-4)
    return p


# ============================================================ 밥 먹기
@anim("eat")
def eat(a):
    chew = max(0.0, sn(a.clock, 3.6)) * 0.5
    dip = 1.5 * sn(a.clock, 1.8)
    return pose(hx=-30, hy=42, sx=32, sy=38, hip_r=22, chest_r=22, arch=0,
                FNx=40, FNy=0, FFx=30, FFy=0, HNx=-36, HFx=-28, fa_N=30, fa_F=30,
                hdx=30, hdy=-9 + dip, hrot=-30, mouth=0.06 + chew, eyeO=0.55, earN=-4,
                tb=48, tc=-2, tw=14, tf=0.5, bowl=1, bowlx=32 + 30 + 20, tg=1)


# ============================================================ 꾹꾹이
@anim("knead")
def knead(a):
    ph = 2 * PI * 1.25 * a.clock
    def paw(offset):
        s = math.sin(ph + offset)
        lift = max(0.0, s)
        return 46 + 5 * math.cos(ph + offset), 1.5 + 9 * lift, -30 * lift
    nx, ny, na = paw(0.0)
    fx, fy, fa_ = paw(PI)
    v = purr(a)
    return pose(hx=-32, hy=36 + v * 0.5, sx=30, sy=44 + v, hip_r=22, chest_r=22, arch=2,
                FNx=nx, FNy=ny, FNa=na, FFx=fx - 6, FFy=fy, FFa=fa_,
                HNx=-14, HNy=1, fa_N=75, HFx=-22, HFy=1, fa_F=75,
                hdx=26, hdy=12, hrot=-10, eyeO=0, eyeH=1, mouth=0.14, earN=6, earF=6, whisk=1,
                tb=38, tc=2, tw=18, tf=0.5, cush=1, cushx=30)


# ============================================================ 쓰다듬기 / 그루밍 / 하품
@anim("stroke")
def stroke(a):
    """쓰다듬을 때: 손에 머리를 들이밀고 엉덩이를 치켜든다. 골골송 떨림."""
    v = purr(a, 0.6, 24)
    k = ramp(a.t, 0, 0.35)
    base = stand(a)
    tgt = pose(hx=-32, hy=60 + v, sx=31, sy=53 + v * 0.6, hip_r=22, chest_r=23, arch=3,
               FNx=37, FFx=28, HNx=-34, HFx=-26, hdx=26, hdy=24, hrot=20 + 2 * sn(a.clock, 0.8),
               eyeO=0, eyeH=1, mouth=0.1, earN=12, earF=12, whisk=1,
               tb=82, tc=0, tw=7, tf=1.1)
    return lerp_pose(base, tgt, k)


@anim("groom")
def groom(a):
    """앉아서 앞발을 핥는다."""
    lick = max(0.0, sn(a.clock, 2.3)) ** 0.7
    p = sit(a)
    p.update(FFx=39 + 1.5 * sn(a.clock, 2.3), FFy=64 + 1.5 * sn(a.clock, 2.3), FFa=40,
             FNx=44, FNy=0, FNa=0, flover=1,
             hdx=8, hdy=21, hrot=-24, eyeO=0.08, mouth=0.28 * lick, tongue=lick, lookx=0)
    return p


@anim("yawn")
def yawn(a):
    k = smooth(a.t / 0.5) * (1 - smooth((a.t - 1.7) / 0.5))
    p = sit(a)
    p.update(mouth=k, eyeO=1 - k, hrot=14 * k, hdy=27 + 3 * k, earN=-6 * k)
    return p


@anim("scratch")
def scratch(a):
    """앉아서 뒷발로 귀 뒤를 긁는다."""
    s = sn(a.clock, 6.5)
    p = sit(a)
    p.update(HNx=-4 + 3 * s, HNy=80 + 4 * s, HNa=-20, fa_N=-70, hrot=14, eyeO=0.1, hdy=24, earN=14,
             sy=64, hx=-20, hy=34)
    return p


@anim("groom_leg")
def groom_leg(a):
    """그루밍 2 (사진 1): 앉아서 몸을 뒤로 젖히고 뒷다리 하나를 높이 들어 올려 허벅지를 핥는다."""
    lick = max(0.0, sn(a.clock, 1.8)) ** 0.8
    p = sit(a)
    p.update(hx=-32, hy=14, sx=-12, sy=57, hip_r=23, chest_r=19, arch=2.0,
             HNx=14 + 1.2 * sn(a.clock, 1.8), HNy=60 + 1.5 * sn(a.clock, 1.8), HNa=-10, fa_N=180,
             HFx=26, HFy=0, fa_F=86,                    # 반대쪽 뒷다리는 앞으로 뻗어 바닥에 둔다
             FNx=-4, FNy=0, FFx=-10, FFy=0,
             hdx=14, hdy=14, hrot=-40, eyeO=0.06, mouth=0.3 * lick, tongue=lick, lookx=0,
             earN=-4, earF=-4, tb=-30, tw=10)
    return p


@anim("groom_face")
def groom_face(a):
    """그루밍 4: 가까운 쪽 앞발을 핥은 뒤 그 발로 얼굴을 쓸어 닦는다 (세수). 서 있는 발은 먼 쪽 발이다."""
    k = (a.clock / 3.6) % 1.0
    lick = smooth(k / 0.12) * (1 - smooth((k - 0.38) / 0.1))                  # 앞 40%: 발을 핥는다
    wipe = smooth((k - 0.4) / 0.1) * (1 - smooth((k - 0.94) / 0.06))           # 뒤 55%: 얼굴을 쓸어 닦는다
    w = math.sin(2 * PI * 2.2 * a.clock)
    p = sit(a)
    p.update(FNx=34 + 4 * wipe * w + 2 * lick, FNy=66 + 9 * wipe * (0.5 + 0.5 * w) - 2 * lick, FNa=40 - 20 * wipe,
             FFx=40, FFy=0, FFa=0, flover=1,                                     # 먼 쪽 앞발은 서 있다
             hdx=10, hdy=22, hrot=-18 + 6 * wipe * w, eyeO=0.06, mouth=0.28 * lick, tongue=lick, lookx=0,
             earN=-4 + 8 * wipe, earF=-4 + 8 * wipe, whisk=0.5 * wipe)
    return p


@anim("scratch_neck")
def scratch_neck(a):
    """그루밍 3 (사진 2): 고개를 뒤로 젖히고 눈을 감은 채, 뒷발로 목 밑·턱 아래를 시원하게 긁는다."""
    sc = sn(a.clock, 7.0)
    p = sit(a)
    p.update(HNx=22 + 3.5 * sc, HNy=70 + 4 * sc, HNa=-20, fa_N=180,
             hdx=10, hdy=27, hrot=34, eyeO=0.0, eyeH=0, mouth=0.1, earN=18, earF=18, whisk=0.8,
             sy=62, hx=-22, hy=26)
    return p


@anim("stretch")
def stretch(a):
    """기지개(앞다리를 쭉 뻗고 엉덩이를 치켜들며 하품)."""
    k = smooth(a.t / 0.9) * (1 - smooth((a.t - 2.6) / 0.9))
    bow = pose(hx=-30, hy=62, sx=40, sy=27, hip_r=22, chest_r=21, arch=-2,
               FNx=70, FNy=0, FFx=62, FFy=0, HNx=-36, HFx=-28, fa_N=18, fa_F=18,
               hdx=22, hdy=8, hrot=-14, mouth=0.9, eyeO=0, earN=8, earF=8,
               tb=58, tc=0, tw=4, tf=0.6)
    return lerp_pose(stand(a), bow, k)


# ============================================================ 점프 / 착지 / 낙하
_CROUCH = pose(hx=-32, hy=34, sx=26, sy=36, hip_r=23, chest_r=22, arch=0,
               FNx=36, FFx=28, HNx=-26, HFx=-18, fa_N=60, fa_F=60,
               hdx=24, hdy=14, hrot=-12, eyeO=1, earN=-6, earF=-6, tb=15, tw=4)
_LAUNCH = pose(hx=-34, hy=42, sx=34, sy=64, hip_r=21, chest_r=21, arch=-3,
               FNx=62, FNy=40, FNa=-10, FFx=54, FFy=46, FFa=-10, HNx=-54, HNy=8, HNa=-20, fa_N=62,
               HFx=-46, HFy=14, fa_F=70, hdx=24, hdy=22, hrot=12, eyeO=1, earN=20, earF=20,
               tb=-10, tc=2, tw=4, tg=0)
_APEX = pose(hx=-18, hy=50, sx=26, sy=58, hip_r=22, chest_r=22, arch=3,
             FNx=36, FNy=26, FFx=30, FFy=30, HNx=-10, HNy=20, HNa=0, fa_N=50, HFx=-4, HFy=24, fa_F=55,
             hdx=24, hdy=18, hrot=0, eyeO=1, earN=16, earF=16, tb=8, tw=5, tg=0)
_REACH = pose(hx=-30, hy=60, sx=36, sy=50, hip_r=21, chest_r=22, arch=0,
              FNx=62, FNy=12, FNa=18, FFx=55, FFy=18, FFa=18, HNx=-38, HNy=24, fa_N=40,
              HFx=-30, HFy=30, fa_F=45, hdx=26, hdy=14, hrot=-14, eyeO=1, earN=24, earF=24,
              tb=30, tw=5, tg=0)


@anim("crouch")
def crouch(a):
    """점프 직전 웅크리기 (엉덩이 씰룩)."""
    k = smooth(a.t / 0.3)
    wig = 1.8 * sn(a.clock, 9) * k
    c = dict(_CROUCH)
    c.update(hy=_CROUCH["hy"] + wig * 0.8, hx=_CROUCH["hx"] + wig, lookx=0.8)
    return lerp_pose(stand(a), c, k)


@anim("hop")
def hop(a):
    """바닥에서 짧게 앞으로 폴짝 (털실공 덮치기 등)."""
    p = max(0.0, min(1.0, a.param.get("p", 0.0)))
    return kf(p, [(0.0, _LAUNCH), (0.45, _APEX), (0.8, _REACH), (1.0, _REACH)])


# 뛰어오를 때: 몸을 위로 쭉 펴고 앞발을 머리 위로 뻗는다 (뒷발은 아래로 곧게)
_STRETCH = pose(hx=-10, hy=64, sx=8, sy=100, hip_r=19, chest_r=19, arch=-2, sag=1.0, hump=0.0,
                FNx=42, FNy=122, FNa=62, FFx=33, FFy=130, FFa=62,
                HNx=-6, HNy=0, HNa=-70, fa_N=-25, HFx=-14, HFy=6, HFa=-70, fa_F=-20,
                hdx=6, hdy=27, hrot=28, eyeO=1, earN=24, earF=24, whisk=0.4,
                tb=-62, tc=-3, tw=10, tf=0.8, tg=0, shadow=0)
# 뛰어내릴 때 / 낙하: 몸을 수평으로 쭉 펴고 날아가는 자세 (앞다리는 앞으로, 뒷다리는 뒤로 뻗고, 꼬리는 위로 휜다)
_DIVE = pose(hx=-30, hy=78, sx=30, sy=44, hip_r=17, chest_r=18, arch=1.0, sag=0.5, hump=1.0,
             FNx=76, FNy=2, FNa=-55, FFx=66, FFy=10, FFa=-55,
             HNx=-84, HNy=70, HNa=-30, fa_N=-80, HFx=-72, HFy=80, HFa=-30, fa_F=-75,
             hdx=22, hdy=-4, hrot=-38, eyeO=1, earN=26, earF=26, whisk=0.8,
             tb=62, tc=7, tw=12, tf=0.7, tg=0, shadow=0)


@anim("jump")
def jump(a):
    """오르기: 웅크렸다 → 몸을 위로 쭉 펴고(사진 속 자세) → 창 모서리에 앞발을 걸친다.
    내리기(param down=1): 도약 → 머리를 아래로 하고 앞발부터 내려간다."""
    p = max(0.0, min(1.0, a.param.get("p", 0.0)))
    if a.param.get("down"):
        return kf(p, [(0.0, _LAUNCH), (0.30, _DIVE), (1.0, _DIVE)])
    mid = lerp_pose(_STRETCH, _REACH, 0.55)
    return kf(p, [(0.0, _LAUNCH), (0.2, _STRETCH), (0.62, _STRETCH), (0.82, mid), (1.0, _REACH)])


@anim("land")
def land(a):
    return kf(a.t, [(0.0, _CROUCH), (0.28, stand(a))])


@anim("fall")
def fall(a):
    """떨어질 때: 몸이 뒤집히며 머리가 아래로 향하는 다이브 자세 (사진 참고)."""
    start = pose(hx=-26, hy=46, sx=28, sy=54, hip_r=22, chest_r=22, arch=3,
                 FNx=46, FNy=24, FNa=-10, FFx=40, FFy=32, HNx=-46, HNy=14, fa_N=55,
                 HFx=-40, HFy=24, fa_F=60, hdx=22, hdy=22, hrot=8, eyeO=1, mouth=0.5,
                 earN=30, earF=30, tb=78, tc=-3, tw=18, tf=2.2, tg=0, shadow=0)
    d = dict(_DIVE)
    w = 2.0 * sn(a.clock, 1.6)
    d.update(hrot=_DIVE["hrot"] + w, HNy=_DIVE["HNy"] + w, HFy=_DIVE["HFy"] - w, mouth=0.35)
    return lerp_pose(start, d, ramp(a.t, 0.0, 0.3))


@anim("hold")
def hold(a):
    """목덜미를 잡혀 대롱대롱."""
    sw = sn(a.clock, 0.9)
    return pose(hx=-6 + 4 * sw, hy=22, sx=14 + 2 * sw, sy=64, hip_r=21, chest_r=20, arch=-2,
                FNx=24 + 5 * sw, FNy=34, FNa=-50, FFx=18 + 5 * sw, FFy=36, FFa=-50,
                HNx=-6 + 8 * sw, HNy=-4, fa_N=15, HFx=2 + 8 * sw, HFy=-2, fa_F=15,
                hdx=8, hdy=24, hrot=0, eyeO=0.8, mouth=0.1, earN=10, earF=10,
                tb=-80, tc=0, tw=6, tf=0.9, tg=0, shadow=0)


# ============================================================ 장난: 걷어차기 / 꼬리 놀이 / 털실공
@anim("swat")
def swat(a):
    """앞발로 후려치기 (아이콘 차기). a.t: 0~0.28 와인드업, 0.28~0.4 타격, 이후 회복."""
    t = a.t
    wind = pose(hx=-30, hy=40, sx=24, sy=70, hip_r=22, chest_r=21, arch=-2,
                FNx=14, FNy=58, FNa=30, FFx=30, FFy=24, HNx=-44, HNy=6, fa_N=60, HFx=-36, HFy=12, fa_F=66,
                hdx=14, hdy=24, hrot=14, eyeO=1, earN=-8, earF=-8, lookx=1, tb=40, tw=3, tg=0)
    hit = pose(hx=-34, hy=42, sx=34, sy=60, hip_r=22, chest_r=21, arch=-3,
               FNx=70, FNy=34, FNa=-40, FFx=34, FFy=30, HNx=-50, HNy=2, fa_N=70, HFx=-42, HFy=10, fa_F=70,
               hdx=30, hdy=20, hrot=-14, eyeO=0.7, mouth=0.3, earN=-14, earF=-14, lookx=1, tb=20, tw=4, tg=0)
    rec = pose(hx=-32, hy=44, sx=30, sy=60, hip_r=22, chest_r=22,
               FNx=48, FNy=30, FNa=-10, FFx=34, FFy=26, HNx=-44, HNy=6, fa_N=55, HFx=-36, HFy=12, fa_F=60,
               hdx=24, hdy=24, hrot=0, eyeO=1, tb=30, tw=5, tg=0)
    return kf(t, [(0.0, wind), (0.26, wind), (0.36, hit), (0.9, rec)])


@anim("bat")
def bat(a):
    """바닥에 선 채로 앞발로 공을 툭 친다 (뒷발은 땅에 붙어 있음). a.t: 0~0.3 와인드업, 0.3 타격."""
    base = dict(hx=-32, hip_r=22, chest_r=22, HNx=-34, HFx=-26, fa_N=24, fa_F=24, FFx=27)
    wind = pose(base, hy=52, sx=26, sy=64, FNx=16, FNy=36, FNa=34, hdx=20, hdy=24, hrot=10,
                lookx=1, earN=-8, earF=-8, tb=40, tw=14, tf=2)
    hit = pose(base, hy=50, sx=36, sy=54, FNx=68, FNy=10, FNa=-40, hdx=29, hdy=18, hrot=-12,
               lookx=1, mouth=0.2, earN=-12, earF=-12, tb=24, tw=10, tf=2)
    rec = pose(base, hy=55, sx=31, sy=58, FNx=40, FNy=2, hdx=23, hdy=24, lookx=0.6, tb=26, tw=8)
    return kf(a.t, [(0.0, wind), (0.24, wind), (0.34, hit), (0.6, rec)])


@anim("tail_play")
def tail_play(a):
    """꼬리를 흔들며 쳐다보고 앞발로 톡톡 건드린다."""
    ph = 2 * PI * 1.6 * a.clock
    p = sit(a)
    p.update(tb=70 + 12 * math.sin(ph * 0.5), tc=13, tw=28, tf=1.6, tp=0.35, tfront=1, tg=0,
             hdx=6, hdy=22, hrot=-18, lookx=-1, looky=0.4, eyeO=1, earN=-6, earF=-6,
             FNx=30 + 8 * max(0.0, math.sin(ph)), FNy=14 * max(0.0, math.sin(ph)), FNa=-20 * max(0.0, math.sin(ph)),
             mouth=0.0)
    return p


@anim("bunny")
def bunny(a):
    """장난감을 끌어안고 뒷발로 팡팡 차는 장난."""
    ph = 2 * PI * 3.2 * a.clock
    s1, s2 = math.sin(ph), math.sin(ph + PI)
    return pose(hx=-34, hy=20, sx=30, sy=22, hip_r=19, chest_r=19, arch=1,
                FNx=52, FNy=22, FNa=-10, FFx=47, FFy=14, FFa=-10,
                HNx=8 + 20 * s1, HNy=15 + 5 * max(0.0, s1), HNa=-10, fa_N=50, HFx=8 + 20 * s2, HFy=22 + 4 * max(0.0, s2),
                HFa=-10, fa_F=50,
                hdx=30, hdy=7 + 1.5 * sn(a.clock, 6), hrot=-10, eyeH=1, mouth=0.22 + 0.15 * sn(a.clock, 6),
                earN=10, earF=10, tb=14, tc=2, tw=20, tf=2.2, ball=1, ballmid=1, ballx=56, bally=-1 + 1.5 * s1,
                ballrot=40 * s1)


@anim("wiggle")
def wiggle(a):
    """사냥 직전 엉덩이 씰룩씰룩."""
    k = ramp(a.t, 0, 0.3)
    w = sn(a.clock, 7.5)
    c = pose(hx=-34 + 2.5 * w, hy=36, sx=32, sy=26, hip_r=23, chest_r=21, arch=0,
             FNx=46, FFx=38, HNx=-30 + 2 * w, HFx=-22 - 2 * w, fa_N=50, fa_F=50,
             hdx=26, hdy=4, hrot=-14, eyeO=1, lookx=1, looky=-0.3, earN=-10, earF=-10,
             tb=22, tc=1, tw=32, tf=2.6, ball=1, ballx=106, bally=0)
    return lerp_pose(stand(a), c, k)


# ============================================================ 몸의 느낌 (자세별 배 처짐/등 굽음)
BODY_FEEL = {
    "sit": dict(sag=5.0, hump=2.5, arch=2.0),
    "sit_tilt": dict(sag=5.0, hump=2.0),
    "loaf": dict(sag=5.5, hump=2.5),
    "sleep_curl": dict(sag=6.0, hump=4.0),
    "sleep_side": dict(sag=6.5, hump=1.0),
    "sleep_nap": dict(sag=5.5, hump=2.5),
    "sleep_doze": dict(sag=5.0, hump=2.5),
    "groom": dict(sag=5.0, hump=2.5),
    "yawn": dict(sag=5.0, hump=2.5),
    "scratch": dict(sag=5.0, hump=2.5),
    "groom_leg": dict(sag=6.0, hump=3.5),
    "groom_face": dict(sag=5.0, hump=2.5),
    "scratch_neck": dict(sag=5.0, hump=2.5),
    "tail_play": dict(sag=5.0, hump=2.5),
    "knead": dict(sag=4.5, hump=2.0),
    "eat": dict(sag=4.0),
    "crouch": dict(sag=4.5, hump=2.5),
    "land": dict(sag=5.0, hump=2.0),
    "run": dict(sag=0.8, hump=1.0),
    "trot": dict(sag=2.2),
    "jump": dict(sag=1.0),
    "hop": dict(sag=1.2),
    "fall": dict(sag=0.5),
    "stretch": dict(sag=1.5),
    "bunny": dict(sag=5.0),
}


# ============================================================ 몸을 세우고 앉아 고개를 갸웃 (자주 하는 자세)
@anim("sit_tilt")
def sit_tilt(a):
    """몸을 곧게 세우고 앉아서 고개를 갸웃하며 이쪽을 바라본다. 8초 주기로 갸웃 → 유지 → 제자리 → 반대쪽 갸웃."""
    b = breathing(a, 0.5)
    period = 8.0
    k = (a.clock / period) % 1.0
    side = 1.0 if int(a.clock / period) % 2 == 0 else -0.65
    tilt = smooth(k / 0.10) * (1 - smooth((k - 0.58) / 0.12))
    nod = -4.0 * smooth((k - 0.58) / 0.12) * (1 - smooth((k - 0.72) / 0.12))      # 풀릴 때 살짝 끄덕
    p = sit(a)
    p.update(hx=-22, hy=25, sx=8, sy=68 + b, hip_r=24, chest_r=21,
             FNx=16, FNy=0, FFx=9, FFy=0, HNx=8, HFx=-2,
             hdx=6, hdy=29 + b * 0.3, hrot=side * 18 * tilt + nod, eyeO=1, lookx=0, looky=0,
             earN=-6 * tilt - 2, earF=-6 * tilt - 2, whisk=0.6 * tilt,
             tb=-8, tc=-4, tw=14, tf=0.3)
    return p













