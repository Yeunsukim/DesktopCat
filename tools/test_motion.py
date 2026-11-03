"""동작 속도·잠자는 방향 점검 (화면 없이).

    python tools/test_motion.py

확인하는 것
 1) 평소 동작은 10% 빠르게(MOTION_SPEED) 흐르고, 나비잡기(깃털 놀이)와 종종걸음은 그대로(1.0배)인가
 2) 배고픔·기분(pet)은 실제 시간대로 가는가 (동작만 빠르게)
 3) 웅크리고 자는 사진(sleep_curl)은 같은 방향을 보는 컷(2~5번)만 오가는가 (0·1번 컷은 머리가 반대쪽이라 자는 내내 몸이 뒤집혀 보였다)
 4) 밤 모드로 오래 자도 바라보는 방향(facing)이 바뀌지 않는가
"""
import random
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
import behavior as B  # noqa: E402
from behavior import S  # noqa: E402
from sim_behavior import make_brain  # noqa: E402

DT = 1 / 24
FAILS = []


def check(name, ok, info=""):
    print(("  통과  " if ok else "  실패  ") + name + ("  — " + info if info else ""))
    if not ok:
        FAILS.append(name)


def advance(brain, sec):
    t0, n = brain.t, int(sec / DT)
    for _ in range(n):
        brain.update(DT)
    return brain.t - t0


print("== 1) 동작 속도 배율 ==")
b = make_brain(1)
b.pending = None
b.gait = S.WALK
b.go(S.WALK, 1000.0)
b.facing = 1
b._travel = None
r = b._motion_speed()
check("걷기: %.2f배" % B.MOTION_SPEED, abs(r - B.MOTION_SPEED) < 1e-9 and abs(B.MOTION_SPEED - 1.1) < 1e-9, "배율 %.2f" % r)
b.gait = S.RUN
check("종종걸음(걷기 + 빠른 걸음): 1.0배", b._motion_speed() == 1.0)
b.go(S.RUN, 1000.0)
check("달리기(우다다): 10% 빠름", abs(b._motion_speed() - B.MOTION_SPEED) < 1e-9)
b.go(S.SLEEP, 1000.0)
check("자기: 10% 빠름", abs(b._motion_speed() - B.MOTION_SPEED) < 1e-9)
b.go(S.TEASE, 1000.0)
check("나비잡기(S.TEASE): 1.0배", b._motion_speed() == 1.0)
b.go(S.FALL, 1000.0)
b.tease = {"end": 1e18}
check("나비잡기 도중의 점프·낙하도 1.0배", b._motion_speed() == 1.0)
b.tease = None
check("나비잡기가 끝나면 다시 10% 빠름", abs(b._motion_speed() - B.MOTION_SPEED) < 1e-9)

print("== 2) 실제로 시간이 그렇게 흐르는가 / pet 은 실제 시간 ==")
b = make_brain(2)
b.mode = None
ticks = []
b.pet.tick = lambda dt: ticks.append(dt)
b.go(S.SIT, 1000.0)
adv = advance(b, 10.0)
check("앉아 있는 10초 동안 동작 시간은 11초 흐름", abs(adv - 11.0) < 0.2, "%.2f초" % adv)
check("pet.tick 은 실제 시간(10초)", abs(sum(ticks) - 10.0) < 0.2, "%.2f초" % sum(ticks))
b = make_brain(3)
b.gait = S.RUN
b.go(S.WALK, 1000.0)
b._travel = None
adv = advance(b, 5.0)
check("종종걸음 5초는 그대로 5초", abs(adv - 5.0) < 0.2 and b.state is S.WALK, "%.2f초" % adv)

print("== 3) 웅크리고 자는 컷: 같은 방향만 오감 ==")
from photocat import PhotoRig, _PP_RANGE  # noqa: E402


class An:
    name = "sleep_curl"
    param = {}
    t = 0.0


rig = PhotoRig(ROOT / "assets" / "sprites")
lo, hi = _PP_RANGE["sleep_curl"]
an, seen = An(), []
for k in range(0, 4000):
    an.t = k * 0.05                       # 200초 동안
    key, idx, _ = rig._select("sleep_curl", an)
    seen.append(idx)
check("컷 번호가 2~5 사이를 벗어나지 않음", key == "sleep_curl" and min(seen) >= 2.0 and max(seen) <= 5.0, "%.2f ~ %.2f" % (min(seen), max(seen)))
check("그래도 컷이 오가며 숨 쉬는 움직임은 있음", max(seen) - min(seen) >= 2.9)
for other in ("sleep_side", "sleep_nap", "sleep_doze", "loaf"):
    an.name = other
    try:
        rig._select(other, an)
        ok = True
    except Exception:
        ok = False
    check("다른 자세(%s)는 그대로 처음~끝 컷을 씀" % other, ok and other not in _PP_RANGE)

print("== 4) 밤에 자는 동안 방향이 안 바뀜 ==")
for seed in (1, 2, 3):
    b = make_brain(seed)
    b.set_mode("night")
    faces, anims = set(), set()
    n = 0
    while n < int(1800 / DT) and not (b.state is S.SLEEP and b.t > 5):
        b.update(DT)                      # 구석까지 가서 잠들 때까지
        n += 1
    for _ in range(int(1500 / DT)):       # 25분 동안 자는 모습 지켜보기
        b.update(DT)
        if b.state is S.SLEEP:
            faces.add(b.facing)
            anims.add(b.sleep_anim)
    check("씨앗 %d: 25분 동안 방향이 한 가지 (%s)" % (seed, sorted(faces)), len(faces) == 1 and anims == {"sleep_curl"})

print()
print("모두 통과" if not FAILS else "실패: %d 건 — %s" % (len(FAILS), ", ".join(FAILS)))
sys.exit(1 if FAILS else 0)
