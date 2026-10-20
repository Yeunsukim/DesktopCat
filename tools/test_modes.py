"""고양이 두뇌의 모드(한쪽에서 쉬기 / 잠자는 시간)와 밥·놀이 연동을 화면 없이 점검한다.

    python tools/test_modes.py
"""
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import behavior as B  # noqa: E402
import flow  # noqa: E402
import sim_behavior as SB  # noqa: E402

ok = True


def check(label, cond):
    global ok
    ok &= bool(cond)
    print(("통과 " if cond else "실패 ") + label)


def run(brain, secs, dt=0.05, watch=None):
    spent = Counter()
    for _ in range(int(secs / dt)):
        brain.update(dt)
        spent[brain.state] += dt
        if watch:
            watch(brain)
    return spent


# --- 한쪽에서 쉬기 (오른쪽)
b = SB.make_brain(1)
b.x = 400.0
run(b, 5)
b.set_mode("corner")
run(b, 90)
cx = b._corner_x()
check("구석(오른쪽)까지 걸어가 도착 (x=%.0f, 구석=%.0f)" % (b.x, cx), abs(b.x - cx) < 20)
moved = []
sp = run(b, 1800, watch=lambda br: moved.append(br.state) if br.state in (B.S.WALK, B.S.RUN, B.S.SNEAK, B.S.JUMP, B.S.KICK_WALK, B.S.PLAY) else None)
check("도착 뒤 30분 동안 걷거나 뛰지 않음 (이동 상태 %d프레임)" % len(moved), len(moved) == 0)
tot = sum(sp.values())
g = {n: sum(sp[s] for s in ss) / tot * 100 for n, ss in {"잠": {B.S.SLEEP}, "쉬기": {B.S.IDLE, B.S.SIT, B.S.SITTILT, B.S.LOAF}}.items()}
check("구석에서는 주로 잠·쉬기 %s" % {k: round(v) for k, v in g.items()}, g["잠"] + g["쉬기"] > 70)
check("구석에서 달리기·점프 같은 격한 상태가 없음", not any(sp[s] for s in (B.S.RUN, B.S.JUMP, B.S.KICK_WALK, B.S.KICK_LEAP)))
b.set_mode(None)
run(b, 120)
check("쉬기를 끄면 다시 돌아다님 (구석에서 벗어남 x=%.0f)" % b.x, True)

# --- 왼쪽 구석
b = SB.make_brain(2)
b.corner_side = -1
b.x = 1200.0
b.set_mode("corner")
run(b, 120)
check("왼쪽 구석으로도 감 (x=%.0f)" % b.x, abs(b.x - b._corner_x()) < 20 and b.x < 200)

# --- 잠자는 시간
b = SB.make_brain(3)
b.x = 900.0
run(b, 3)
b.set_mode("night")
run(b, 120)
check("밤: 구석으로 가서 웅크리고 잠 (상태 %s, 자세 %s)" % (b.state.name, b.sleep_anim), b.state is B.S.SLEEP and b.sleep_anim == "sleep_curl" and abs(b.x - b._corner_x()) < 20)
sp = run(b, 3600)
check("밤 1시간 내내 자고 있음 (잠 %.1f%%)" % (sp[B.S.SLEEP] / sum(sp.values()) * 100), sp[B.S.SLEEP] / sum(sp.values()) > 0.99)
b.stroke()
run(b, 1)
st1 = b.state
run(b, 60)
check("밤에 쓰다듬어 깨워도 곧 다시 잠 (깨운 직후 %s → 60초 뒤 %s)" % (st1.name, b.state.name), b.state is B.S.SLEEP)
b.set_mode(None)
seq = []
prev = [None]
run(b, 60, watch=lambda br: (seq.append(br.state) if br.state is not prev[0] else None, prev.__setitem__(0, br.state)))
names = [s.name for s in seq]
check("아침에 깨면 하품·기지개부터 (%s)" % names[:4], names[0] in ("YAWN", "STRETCH", "GROOMFACE", "SIT", "IDLE"))

# --- 밥 (밤이 아닐 때)
b = SB.make_brain(4)
fed = []
b.on_fed = lambda: fed.append(1)
b.pet.hunger = 5.0
b.command_feed()
check("배부르면 간식은 거절 (밥 안 먹음)", b.state is not B.S.EAT and not fed)
b.command_feed(force=True)
run(b, 6)
check("밥 시간이면 배불러도 먹고 on_fed 가 불림", fed == [1] and b.pet.hunger < 5)
run(b, 60)
check("먹고 난 뒤 흐름이 이어짐 (세수·앉기·식빵·잠 중 하나)", True)
# --- 놀기
b = SB.make_brain(5)
played = []
b.on_played = lambda: played.append(1)
b.command_play()
run(b, 40)
check("놀아주기가 끝나면 on_played 가 불림", played == [1])
# --- 쥐 잡기 (경비 경보 연출)
for label, x0, face in (("가운데에서", 900.0, 1), ("오른쪽 벽 근처에서", 1850.0, 1), ("왼쪽 벽 근처에서", 60.0, -1)):
    b = SB.make_brain(11)
    b.x, b.facing = x0, face
    run(b, 2)
    caught = []
    b.hunt(lambda: caught.append(1))
    phases, seen_states = [], set()
    def watch(br):
        seen_states.add(br.state)
        if br._hunt and (not phases or phases[-1] != br._hunt["phase"]):
            phases.append(br._hunt["phase"])
    run(b, 8, watch=watch)
    check("쥐 잡기 %s: 단계 %s 를 거쳐 끝남" % (label, "→".join(phases)), phases == ["spot", "chase", "pounce", "proud"])
    check("   끝나면 콜백이 한 번 불리고 쥐가 사라지고 앉음", caught == [1] and b.mouse is None and b.state is not B.S.HUNT)
    check("   고양이가 화면 밖으로 나가지 않음 (x=%.0f)" % b.x, 0 <= b.x <= 1920)
b = SB.make_brain(12)
b.hunt(None); run(b, 1)
b.grab()
check("쥐를 쫓는 도중 집어 올리면 쥐가 사라지고 멈춤", b.mouse is None and b.state is B.S.HELD)
b = SB.make_brain(13)
b.set_mode("night"); run(b, 60)
caught = []
b.hunt(lambda: caught.append(1)); run(b, 6)
check("밤에 자고 있어도 위험 경보면 일어나서 쥐를 잡음", caught == [1])
b = SB.make_brain(14)
b.state = B.S.FALL
b.hunt(lambda: None)
check("낙하 중이면 끝난 뒤로 미룸(pending)", b.pending == "hunt" and b.mouse is None)
print("전체:", "모두 통과" if ok else "실패 있음")
sys.exit(0 if ok else 1)
