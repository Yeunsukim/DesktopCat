"""고양이 행동의 '흐름'과 '시간 배분'.

두 가지를 정한다.
 1) 흐름(FLOW): 지금 하던 행동 다음에 올 수 있는 행동과 그 개연성. 뛰다가 갑자기 동그랗게 누워 자는 일이 없도록,
    '달리기 → 걷기 → 서 있기 → 그루밍 → 식빵 → 잠' 처럼 흥분도가 한 단계씩 오르내리게 이어 붙인다.
 2) 시간 배분(TARGET_*): 행동 묶음별로 하루 시간을 얼마씩 쓸지의 목표 비율. 연구에서 집고양이는 하루의 약 60%를 자고 약 25%를 쉬며
    (합쳐 85% 안팎), 이동·놀이·그루밍·먹기는 각각 한 자릿수에서 10%대 정도만 차지한다.
    행동마다 길이가 달라서 '고를 확률'만으로는 시간 비율이 안 맞으므로, 흐름과 행동 길이로 만든 마르코프 연쇄의 정상 분포를
    계산해서 목표 시간 비율이 나오도록 가중치(solve)를 자동으로 맞춘다.

화면·윈도우 의존성이 없어서 시험하기 쉽다 (tools/sim_behavior.py, tools/test_flow.py).
"""
import random

# 행동 종류(kind). trot 은 걷기 틀에서 종종걸음 걸음걸이를 쓰는 것
KINDS = ("walk", "trot", "run", "sneak", "jump", "kick", "travel",
         "idle", "sit", "sittilt", "loaf", "sleep",
         "groom", "groomleg", "groomface", "scratchneck", "scratch",
         "yawn", "stretch", "knead", "tailplay")

GROUP_OF = {
    "sleep": "잠",
    "idle": "쉬기", "sit": "쉬기", "sittilt": "쉬기", "loaf": "쉬기",
    "groom": "그루밍", "groomleg": "그루밍", "groomface": "그루밍", "scratchneck": "그루밍", "scratch": "그루밍",
    "walk": "이동", "trot": "이동", "run": "이동", "sneak": "이동", "jump": "이동", "travel": "이동",
    "kick": "놀이", "knead": "놀이", "tailplay": "놀이",
    "yawn": "하품·기지개", "stretch": "하품·기지개",
}

# 행동이 이어지는 시간(초, 최소~최대). 평균은 시간 비율 계산에 쓰고, 실제로는 이 범위에서 무작위로 뽑는다.
DUR = {
    "walk": (3, 7), "trot": (3, 6), "run": (2, 3.5), "sneak": (3, 6), "jump": (1.2, 2.0), "kick": (6, 10), "travel": (8, 20),
    "idle": (3, 8), "sit": (8, 22), "sittilt": (10, 25), "loaf": (15, 40), "sleep": (40, 150),
    "groom": (6, 12), "groomleg": (5, 8), "groomface": (6, 10), "scratchneck": (3, 5), "scratch": (2.5, 4),
    "yawn": (2.4, 2.4), "stretch": (3.6, 3.6), "knead": (6, 10), "tailplay": (4, 7),
}

# 깨어 있는 낮 동안의 목표 시간 비율(%). 하루 전체로 보면 밤의 잠(22~07시)을 합쳐 잠 약 60%, 쉬기 약 20%, 그루밍 약 8%,
# 이동 약 5%, 놀이 약 4%, 하품·기지개 약 2%가 된다.
TARGET_DAY = {"잠": 36, "쉬기": 32, "그루밍": 13, "이동": 8, "놀이": 6, "하품·기지개": 3}
# '한쪽에서 쉬기' 모드: 돌아다니지 않고 구석에서 쉰다
TARGET_CORNER = {"잠": 54, "쉬기": 28, "그루밍": 12, "놀이": 2, "하품·기지개": 4}      # 놀이 = 눕기 전 꾹꾹이
CORNER_KINDS = ("sit", "sittilt", "loaf", "sleep", "groom", "groomleg", "groomface", "scratchneck", "yawn", "stretch", "knead", "idle")

_GROOM = {"groomface": 2.0, "groomleg": 1.5, "groom": 0.6, "scratchneck": 1.0, "sit": 2.0, "loaf": 2.0, "sleep": 1.5, "yawn": 1.0,
          "idle": 1.0, "walk": 0.8}
# FLOW[앞 행동][다음 행동] = 이어질 개연성(상대값, 없으면 0 = 이어지지 않음)
FLOW = {
    "start": {"sit": 3, "idle": 3, "sittilt": 2, "walk": 2, "groom": 1, "loaf": 1, "yawn": 0.5},
    "walk": {"idle": 3, "sit": 2, "walk": 2, "trot": 0.5, "sneak": 1, "jump": 1.5, "kick": 1, "scratch": 1, "groom": 1, "sittilt": 1,
             "run": 0.5, "travel": 1},
    "trot": {"walk": 2, "idle": 3, "sit": 2, "run": 1, "jump": 1, "kick": 1, "groom": 1},
    "run": {"walk": 3, "trot": 1, "idle": 4, "sit": 2, "groomface": 2, "groom": 2, "tailplay": 0.5},        # 달리고 나서 곧장 눕지 않는다
    "sneak": {"kick": 3, "run": 2, "walk": 2, "idle": 1.5, "jump": 1, "sit": 0.5},                        # 살금살금 뒤엔 덮치기
    "jump": {"idle": 3, "sit": 3, "walk": 2, "groom": 1, "sittilt": 1, "scratch": 0.5},
    "kick": {"idle": 3, "walk": 3, "trot": 1, "sit": 2, "groom": 1, "run": 1},
    "travel": {"idle": 3, "sit": 2, "walk": 2, "groom": 1, "sittilt": 1},
    "idle": {"walk": 3, "sit": 3, "sittilt": 2, "sneak": 1, "groom": 1.5, "yawn": 1, "stretch": 1, "scratch": 1, "jump": 1, "trot": 1,
             "kick": 0.5, "travel": 0.5, "tailplay": 0.5, "loaf": 0.5},
    "sit": {"sittilt": 3, "groom": 2, "groomface": 1.5, "groomleg": 1, "scratchneck": 1, "loaf": 2.5, "idle": 2, "yawn": 1.2, "walk": 1.2,
            "sleep": 1, "stretch": 0.5, "tailplay": 1},
    "sittilt": {"sit": 3, "idle": 2, "walk": 2, "jump": 1, "groom": 1, "groomface": 1, "loaf": 1, "yawn": 0.5, "sleep": 0.5},
    "loaf": {"sleep": 4, "groom": 2, "groomface": 1, "yawn": 1.5, "sit": 1, "knead": 1, "stretch": 1, "idle": 0.5},
    "knead": {"loaf": 4, "sleep": 3, "sit": 1, "groom": 1, "yawn": 0.5},                                   # 꾹꾹이는 눕기 전 준비
    "sleep": {"yawn": 4, "stretch": 4, "sit": 2, "groomface": 2, "loaf": 1, "idle": 1},                    # 잠에서 깨면 하품·기지개부터
    "yawn": {"stretch": 3, "sit": 3, "idle": 2, "groomface": 2, "loaf": 1.5, "sleep": 1.5, "walk": 1, "scratchneck": 1},
    "stretch": {"walk": 4, "trot": 1, "idle": 3, "sit": 2, "scratch": 1, "sneak": 0.5, "groom": 0.5, "jump": 0.5},
    "groom": _GROOM, "groomface": _GROOM, "groomleg": _GROOM,
    "scratchneck": {"groom": 1, "sit": 2, "idle": 2, "walk": 1.5, "loaf": 1},
    "scratch": {"walk": 2, "sit": 2, "idle": 2, "groom": 1, "stretch": 1},
    "tailplay": {"groom": 2, "sit": 2, "idle": 2, "run": 1, "walk": 1, "loaf": 0.5},
    "eat": {"groomface": 4, "sit": 2, "loaf": 2, "sleep": 2, "walk": 1, "idle": 1},                        # 먹고 나면 세수 → 식빵/낮잠
    "play": {"sit": 3, "idle": 3, "groomface": 2, "loaf": 1, "yawn": 1, "trot": 0.5},                      # 놀고 나면 숨 고르기
}


def mean_dur(kind):
    a, b = DUR[kind]
    return (a + b) / 2


def row(last, kinds=None):
    r = FLOW.get(last) or FLOW["start"]
    return {k: v for k, v in r.items() if kinds is None or k in kinds}


def solve(kinds, target, iters=400):
    """목표 시간 비율(묶음별 %)이 나오도록 행동마다 '기본 가중치'를 맞춘다. {kind: 가중치}"""
    kinds = [k for k in kinds if GROUP_OF[k] in target]
    w = {k: 1.0 for k in kinds}
    tsum = float(sum(target.values()))
    for _ in range(60):
        # 정상 분포 π (다음 행동 확률 = 가중치 × 개연성, 행마다 정규화)
        pi = {k: 1.0 / len(kinds) for k in kinds}
        P = {}
        for i in kinds:
            r = row(i, kinds)
            tot = sum(w[j] * r.get(j, 0) for j in kinds)
            P[i] = {j: (w[j] * r.get(j, 0) / tot) for j in kinds} if tot > 0 else {j: 1.0 / len(kinds) for j in kinds}
        for _ in range(iters // 4):
            nxt = dict.fromkeys(kinds, 0.0)
            for i in kinds:
                for j, p in P[i].items():
                    nxt[j] += pi[i] * p
            pi = nxt
        share = {k: pi[k] * mean_dur(k) for k in kinds}
        s = sum(share.values())
        group = {}
        for k in kinds:
            group[GROUP_OF[k]] = group.get(GROUP_OF[k], 0.0) + share[k] / s * 100
        for k in kinds:
            g = GROUP_OF[k]
            ratio = (target[g] / tsum * 100) / max(group[g], 1e-6)
            w[k] *= ratio ** 0.6
    return w


def expected_share(kinds, w):
    """가중치 w 로 얻어지는 묶음별 시간 비율(%) (확인용)."""
    kinds = list(kinds)
    pi = {k: 1.0 / len(kinds) for k in kinds}
    P = {}
    for i in kinds:
        r = row(i, kinds)
        tot = sum(w[j] * r.get(j, 0) for j in kinds)
        P[i] = {j: (w[j] * r.get(j, 0) / tot) for j in kinds} if tot > 0 else {j: 1.0 / len(kinds) for j in kinds}
    for _ in range(300):
        nxt = dict.fromkeys(kinds, 0.0)
        for i in kinds:
            for j, p in P[i].items():
                nxt[j] += pi[i] * p
        pi = nxt
    share = {k: pi[k] * mean_dur(k) for k in kinds}
    s = sum(share.values())
    out = {}
    for k in kinds:
        out[GROUP_OF[k]] = out.get(GROUP_OF[k], 0.0) + share[k] / s * 100
    return out


# solve() 로 미리 계산해 둔 값 (시작할 때마다 계산하면 2초쯤 걸려서 상수로 둔다). FLOW·DUR·TARGET 을 고치면
# tools/test_flow.py 가 이 값이 낡았다고 알려 주니, 그때 `python tools/test_flow.py --print` 로 새 값을 뽑아 붙여 넣는다.
WEIGHTS_DAY = {'walk': 1.014, 'trot': 1.014, 'run': 1.014, 'sneak': 1.014, 'jump': 1.014, 'kick': 4.348, 'travel': 1.014, 'idle': 0.757,
               'sit': 0.757, 'sittilt': 0.757, 'loaf': 0.757, 'sleep': 1.002, 'groom': 1.163, 'groomleg': 1.163, 'groomface': 1.163,
               'scratchneck': 1.163, 'scratch': 1.163, 'yawn': 1.672, 'stretch': 1.672, 'knead': 4.348, 'tailplay': 4.348}
WEIGHTS_CORNER = {'sit': 0.547, 'sittilt': 0.547, 'loaf': 0.547, 'sleep': 1.27, 'groom': 1.071, 'groomleg': 1.071, 'groomface': 1.071,
                  'scratchneck': 1.071, 'yawn': 1.609, 'stretch': 1.609, 'knead': 23.205, 'idle': 0.547}


def activity_mult(hour: float):
    """하루 중 시간대별 보정 (고양이는 해 뜰 때·질 때 활발하고 한낮엔 낮잠): (이동·놀이 배수, 잠 배수)."""
    if 7 <= hour < 10 or 17 <= hour < 21:
        return 1.35, 0.75
    if 11 <= hour < 16:
        return 0.65, 1.35
    return 1.0, 1.0


def choose(last, base, allowed, mult=None, rng=random):
    """앞 행동 last 다음에 할 행동을 고른다. base: 기본 가중치, allowed: 지금 할 수 있는 종류 집합, mult: {kind: 배수}."""
    r = FLOW.get(last) or FLOW["start"]
    mult = mult or {}
    cand, wts = [], []
    for k, aff in r.items():
        if k in allowed and k in base and aff > 0:
            wt = base[k] * aff * mult.get(k, 1.0)
            if wt > 0:
                cand.append(k)
                wts.append(wt)
    if not cand:                                    # 이어질 행동이 모두 막혔으면 얌전한 것 중에서
        cand = [k for k in ("sit", "idle", "sittilt") if k in allowed] or list(allowed)
        wts = [1.0] * len(cand)
    return rng.choices(cand, wts)[0]


def duration(kind, rng=random):
    a, b = DUR[kind]
    return rng.uniform(a, b)
