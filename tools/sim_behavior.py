"""고양이 두뇌(CatBrain)를 화면 없이 빠르게 돌려서 '시간을 어디에 쓰는지' 비율을 잽니다 (행동 비율 조정·검증용).

    python tools/sim_behavior.py [시간(기본 8)] [시드 수(기본 3)]

 · 창·아이콘이 없는 빈 바탕화면(1920x1040) 하나에서, 사람이 밥을 챙겨 주는 것처럼 배고파지면 밥을 줍니다.
 · 상태를 묶음별로 합산해서 전체 시간 중 몇 %인지 출력합니다.
"""
import random
import sys
import tempfile
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import behavior as B  # noqa: E402
from pet import Pet  # noqa: E402

GROUPS = {
    "잠": {B.S.SLEEP},
    "쉬기(앉기·서 있기·식빵)": {B.S.IDLE, B.S.SIT, B.S.SITTILT, B.S.LOAF, B.S.STROKE},
    "털 고르기·긁기": {B.S.GROOM, B.S.GROOMLEG, B.S.SCRATCHNECK, B.S.GROOMFACE, B.S.SCRATCH},
    "이동(걷기·달리기·살금·점프)": {B.S.WALK, B.S.RUN, B.S.SNEAK, B.S.JUMP, B.S.FALL},
    "놀이(공·꾹꾹이·꼬리·아이콘 차기)": {B.S.PLAY, B.S.KICK_WALK, B.S.KICK_LEAP, B.S.KICK_HIT, B.S.KNEAD, B.S.TAILPLAY},
    "먹기": {B.S.EAT},
    "하품·기지개": {B.S.YAWN, B.S.STRETCH},
}


class FakeTracker:
    def refresh(self, _t):
        return []


class FakeField:
    enabled = False
    moving = {}

    def update(self, dt):
        pass

    def candidates(self):
        return []

    def scan(self):
        pass


def make_brain(seed):
    random.seed(seed)
    world = B.World([(0, 0, 1920, 1040)], FakeTracker(), 1.0, 105)
    pet = Pet(Path(tempfile.mkdtemp()) / "pet.json")
    pet.save = lambda: None
    brain = B.CatBrain(world, pet, FakeField(), 1.0)
    brain.hour_fn = lambda: 5.0          # 시간대 보정이 없는(배수 1.0) 시각으로 고정해서 기본 비율을 잼
    return brain


def run(hours=8.0, seed=1, dt=0.05, setup=None, on_step=None):
    """(묶음별 비율 dict, 상태별 비율 Counter, 전이 Counter)."""
    brain = make_brain(seed)
    if setup:
        setup(brain)
    spent, trans = Counter(), Counter()
    prev = brain.state
    steps = int(hours * 3600 / dt)
    for i in range(steps):
        brain.update(dt)
        spent[brain.state] += dt
        if brain.state is not prev:
            trans[(prev, brain.state)] += 1
            prev = brain.state
        if brain.pet.hunger > 70 and i % 400 == 0:       # 사람이 밥을 챙겨 준다
            brain.pet.feed()
            brain.pet.feed()
        if on_step:
            on_step(brain, i * dt)
    total = sum(spent.values())
    groups = {g: sum(spent[s] for s in ss) / total * 100 for g, ss in GROUPS.items()}
    other = 100 - sum(groups.values())
    if other > 0.05:
        groups["기타(집어 올림 등)"] = other
    return groups, Counter({s.name: v / total * 100 for s, v in spent.items()}), trans


def main():
    hours = float(sys.argv[1]) if len(sys.argv) > 1 else 8.0
    seeds = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    acc, states = Counter(), Counter()
    for sd in range(seeds):
        g, s, _ = run(hours, sd + 1)
        acc.update(g)
        states.update(s)
    print("== %.0f시간 × %d회 평균 (깨어 있는 낮 시간 기준) ==" % (hours, seeds))
    for k, v in sorted(acc.items(), key=lambda x: -x[1]):
        print("  %-24s %5.1f%%" % (k, v / seeds))
    print("-- 상태별")
    for k, v in sorted(states.items(), key=lambda x: -x[1]):
        print("  %-12s %5.1f%%" % (k, v / seeds))


if __name__ == "__main__":
    main()
