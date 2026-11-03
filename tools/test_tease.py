"""놀아주기(깃털) 점검: 화면 없이 가짜 마우스 커서를 움직여서 고양이가 나비(커서)를 제대로 쫓는지 확인한다.

    python tools/test_tease.py

확인하는 것
 1) 가로로 빠르게 움직이는 커서를 따라가는가 (거리 오차, 최고 속도 제한, 한 프레임에 순간이동 없음)
 2) 높이 있는 커서 아래에서 뛰어오르는가 (앞발이 커서 높이에 닿는 만큼만 뛴다), 너무 높으면 최대 높이까지만
 3) 낮은 커서(바닥 근처)는 엉덩이 씰룩 → 덮치기 → 바닥 치기, 앉은 키 높이는 앞발로 툭툭
 4) 10초가 되면 끝나고(뛰는 중이면 내려앉은 뒤) 앉아서 쉬며, 그 뒤 놀아주기 끝 알림(on_played)을 부르는가
 5) 창 윗변에 서 있을 때와 너무 높은 커서(창 위로 올라가기), 집어 올리면 놀이가 멈추는가
시계와 커서는 가짜다 (실제 시간 24fps 로 돌리지 않고 가상 시간으로 빠르게 돌린다).
"""
import math
import random
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import behavior as B  # noqa: E402
from pet import Pet  # noqa: E402

DT = 1 / 24
FLOOR = 1040
FAILS = []


def check(name, ok, info=""):
    print(("  통과  " if ok else "  실패  ") + name + ("  — " + info if info else ""))
    if not ok:
        FAILS.append(name)


class Clock:
    now = 1000.0


time.monotonic = lambda: Clock.now        # 두뇌가 쓰는 시계를 가상 시계로


class FakeTracker:
    def __init__(self, wins=()):
        self.wins = list(wins)

    def refresh(self, _t):
        return self.wins


class FakeField:
    enabled = False
    moving = {}

    def update(self, dt):
        pass

    def candidates(self):
        return []

    def scan(self):
        pass


def make(seed=1, wins=()):
    random.seed(seed)
    Clock.now = 1000.0
    world = B.World([(0, 0, 1920, FLOOR)], FakeTracker(wins), 1.0, 84)
    pet = Pet(Path(tempfile.mkdtemp()) / "pet.json")
    pet.save = lambda: None
    brain = B.CatBrain(world, pet, FakeField(), 0.8)
    brain.x, brain.feet = 960.0, float(FLOOR)
    brain.hour_fn = lambda: 5.0
    brain.mode = None
    world.rect_of = lambda hwnd: next(((w.left, w.top, w.right, w.bottom) for w in wins if w.hwnd == hwnd), None)
    brain.cursor_fn = lambda: (960.0, FLOOR - 90.0)
    brain.played = 0
    brain.on_played = lambda: setattr(brain, "played", brain.played + 1)
    return brain


def run(brain, cursor, seconds, on_step=None):
    """cursor(t) -> (x, y). 가상 시간으로 seconds 초 돌리고 프레임별 기록을 돌려준다."""
    brain.cursor_fn = lambda: cursor(Clock.now - 1000.0)
    log = []
    for i in range(int(seconds / DT)):
        Clock.now += DT
        px, pf = brain.x, brain.feet
        brain.update(DT)
        tz = brain.tease
        log.append({"t": i * DT, "x": brain.x, "feet": brain.feet, "dx": brain.x - px, "df": brain.feet - pf, "state": brain.state,
                    "ph": tz["ph"] if tz else None, "cur": cursor(Clock.now - 1000.0), "vx": tz["vx"] if tz else 0.0})
        if on_step:
            on_step(brain, log[-1])
    return log


def finite(log):
    return all(math.isfinite(r["x"]) and math.isfinite(r["feet"]) for r in log)


def main():
    k = 1.0
    print("== 1) 가로로 움직이는 커서 따라가기 (발바닥 높이 90px 위에서 좌우로 왕복) ==")
    b = make()
    b.command_tease()
    check("명령을 받으면 TEASE 상태", b.state is B.S.TEASE and b.tease_active())
    cur = lambda t: (960 + 420 * math.sin(t * 1.0), FLOOR - 90)               # 최대 약 420px/s 로 흔드는 커서 (사람이 깃털 장난감을 흔드는 정도)
    log = run(b, cur, 9.5)
    err = [abs(r["x"] - r["cur"][0]) for r in log if r["t"] > 1.0]
    vmax = max(abs(r["dx"]) for r in log) / DT
    check("값이 깨지지 않음", finite(log))
    check("속도가 최고 속도 이하 (%d px/s 이하)" % B.TEASE_VMAX, vmax <= B.TEASE_VMAX * k + 5, "최고 %.0f px/s" % vmax)
    check("커서 아래에 붙어 다님 (평균 오차 < 90px)", sum(err) / len(err) < 90, "평균 오차 %.0fpx" % (sum(err) / len(err)))
    spots = [r["x"] for r in log]
    check("실제로 좌우로 크게 움직임", max(spots) - min(spots) > 700, "움직인 범위 %.0fpx" % (max(spots) - min(spots)))
    check("방향을 바꿀 때 순간이동 없음 (한 프레임 이동 < 20px)", max(abs(r["dx"]) for r in log) < 20)

    print("== 2) 높이 있는 커서 아래에서 뛰어오르기 ==")
    for h_above in (140, 220, 330, 440, 520):
        b = make(2)
        b.command_tease()
        target = (900, FLOOR - h_above)
        peaks = []

        def step(br, r, peaks=peaks):
            if r["ph"] == "air":
                peaks.append(FLOOR - r["feet"])
        log = run(b, lambda t, target=target: target, 11.5, step)
        phs = Counter(r["ph"] for r in log)
        rise = max(peaks) if peaks else 0
        reach = rise + B.TEASE_REACH_AIR * k
        need = h_above
        want = min(need, B.TEASE_LEAP_MAX + B.TEASE_REACH_AIR)
        check("커서 %dpx 위: 뛴다 (공중 %.1f초)" % (h_above, phs["air"] * DT), phs["air"] > 10)
        check("  앞발이 닿는 높이 %.0fpx ≥ 목표 %.0fpx - 25" % (reach, want), reach >= want - 25, "뛴 높이 %.0fpx" % rise)
        check("  너무 높이 뛰지 않음 (≤ 최대 %dpx)" % B.TEASE_LEAP_MAX, rise <= B.TEASE_LEAP_MAX * k + 3)
        near = [abs(r["x"] - target[0]) for r in log if r["ph"] == "air"]
        check("  뛸 때 커서 바로 아래에서 (오차 < 45px)", max(near) < 45 if near else False, "최대 %.0fpx" % max(near) if near else "")
        check("  내려앉으면 바닥 높이로 돌아옴", abs(log[-1]["feet"] - FLOOR) < 1.0)
        check("  뛰는 속도 자연스러움 (한 프레임 < 100px)", max(abs(r["df"]) for r in log) < 100, "최대 %.0fpx" % max(abs(r["df"]) for r in log))
        air_runs, cur_n = [], 0
        for r in log:
            cur_n = cur_n + 1 if r["ph"] == "air" else 0
            if cur_n:
                air_runs.append(cur_n)
        check("  공중에 떠 있는 시간이 1.1초 이하 (날쌔게)", max(air_runs) * DT <= 1.1, "최대 %.2f초" % (max(air_runs) * DT))

    print("== 3) 커서 높이별 동작 ==")
    for name, h_above, want in (("바닥 근처", 5, {"wiggle", "pounce", "bat"}), ("앉은 키 높이", 60, {"swat"})):
        b = make(3)
        b.command_tease()
        log = run(b, lambda t, h=h_above: (900, FLOOR - h), 9.0)
        phs = Counter(r["ph"] for r in log)
        check("%s(%dpx): %s 동작을 한다" % (name, h_above, "·".join(sorted(want))), all(phs[w] > 0 for w in want), str(dict(phs)))
        check("  뛰어오르지 않음", phs["air"] == 0)

    print("== 4) 끝나는 때 ==")
    b = make(4)
    b.command_tease()
    log = run(b, lambda t: (700 + 200 * math.sin(t * 2), FLOOR - 160), 12.5)
    end_t = next((r["t"] for r in log if r["state"] is not B.S.TEASE), None)
    check("10~11.3초 사이에 끝남", end_t is not None and 9.9 <= end_t <= 11.4, "끝난 때 %.1f초" % (end_t or -1))
    check("끝나면 앉아서 쉼 (SIT)", b.state is B.S.SIT)
    check("놀아주기 끝 알림을 한 번 부름", b.played == 1)
    check("끝난 뒤 tease 정보가 비워짐", b.tease is None)
    check("끝난 뒤 발은 바닥에", abs(b.feet - FLOOR) < 1.0)
    print("     배고픔/기분: %.0f / %.0f" % (b.pet.hunger, b.pet.mood))

    print("== 5) 창·끼어들기 ==")
    win = B.Win(7, 600.0, 700.0, 1300.0, 900.0) if hasattr(B, "Win") else None
    from windows_info import Win
    win = Win(7, 600.0, 700.0, 1300.0, 900.0)                        # 윗변 700, 바닥(1040)보다 340 위
    b = make(5, wins=[win])
    b.world.refresh()
    b.command_tease()
    log = run(b, lambda t: (950, 300), 9.0)                          # 커서가 바닥에서 740 위 (뛰어서도 못 닿는다): 창 윗변(바닥에서 340 위)으로 올라가서 거기서 뛴다
    on_win = [r for r in log if abs(r["feet"] - 700) < 2 and r["ph"] in ("run", "crouch", "air", "land", "swat")]
    check("너무 높은 커서: 창 윗변으로 올라감", len(on_win) > 40, "창 위에 있던 프레임 %d" % len(on_win))
    check("  올라간 뒤 창 안쪽에서 커서를 쫓음", all(600 <= r["x"] <= 1300 for r in on_win))
    b = make(6, wins=[win])
    b.world.refresh()
    b.x, b.feet, b.on = 900.0, 700.0, 7                              # 창 위에 서서 시작
    b.command_tease()
    log = run(b, lambda t: (1600, FLOOR - 40), 6.0)                  # 커서가 창 밖 오른쪽 아래
    check("창 위에서 커서가 창 밖 아래: 뛰어내려서 바닥으로", abs(log[-1]["feet"] - FLOOR) < 1.5 or log[-1]["state"] is B.S.SIT, "마지막 발 높이 %.0f" % log[-1]["feet"])
    check("  뛰어내린 뒤에도 놀이가 이어짐", any(r["state"] is B.S.TEASE and abs(r["feet"] - FLOOR) < 1.5 and r["t"] > 1 for r in log))
    b = make(7)
    b.command_tease()
    run(b, lambda t: (900, FLOOR - 200), 2.0)
    b.grab()
    check("집어 올리면 놀이가 멈춤", b.tease is None and not b.tease_active() and b.state is B.S.HELD)
    b = make(8)
    b.command_tease()
    run(b, lambda t: (900, FLOOR - 200), 1.0)
    b.stroke()
    check("놀이 중 쓰다듬기·클릭 런처는 무시", b.state is B.S.TEASE and b.is_busy())
    b = make(9)
    b.state = B.S.FALL
    b.command_tease()
    check("낙하 중에 시키면 기다렸다가(pending) 시작", b.pending == "tease")

    print("== 6) 바탕화면 아이콘 밟고 뛰기 ==")
    class IconField(FakeField):
        enabled = True
        cell = (76.0, 93.0)

        def __init__(self, items):
            self.items = items
            self.moving = {}
    icons = [{"index": i, "x": 862.0, "y": top - 9.3} for i, top in enumerate((900.0, 810.0, 720.0, 630.0))]          # 같은 줄 위에 90px 간격 (가운데 x = 900, 윗면 y = 900·810·720·630)
    b = make(10)
    b.field = IconField(icons)
    b.command_tease()
    stood = []
    log = run(b, lambda t: (905, 330), 12.5, lambda br, r: stood.append((r["feet"], r["ph"], r["x"])))
    tops = (900.0, 810.0, 720.0, 630.0)
    seen = {t for t in tops if sum(1 for f, ph, x in stood if abs(f - t) < 1.5 and ph in ("land", "run", "crouch")) > 2}
    check("나비가 높고 아이콘이 가까이: 아이콘을 계단처럼 밟고 올라감 (%d/4칸)" % len(seen), len(seen) >= 3, "밟은 높이 %s" % sorted(seen))
    air_from_icon = [f for f, ph, x in stood if ph == "air" and f < 899]
    check("  아이콘에서 다시 뛰어오름 (공중 프레임 %d)" % len(air_from_icon), len(air_from_icon) > 6)
    top = min(r["feet"] for r in log)
    check("  바닥에서만 뛸 때보다 더 높이 올라감 (발이 %.0fpx 까지)" % (FLOOR - top), FLOOR - top > 440, "")
    check("  끝나면 바닥에 내려와서 마무리 (SIT, on_played 한 번)", b.state is B.S.SIT and b.played == 1 and abs(b.feet - FLOOR) < 1.5, "state=%s played=%d feet=%.0f" % (b.state.name, b.played, b.feet))
    check("  값이 깨지지 않음", finite(log))
    b = make(11)
    b.field = IconField(icons)
    b.command_tease()
    log = run(b, lambda t: (905, FLOOR - 60), 6.0)
    check("나비가 낮으면 아이콘을 밟지 않음", all(abs(r["feet"] - t) > 2 for r in log for t in (900.0, 810.0, 720.0, 630.0)))
    b = make(12)
    b.field = IconField([{"index": 0, "x": 1500.0, "y": 890.0}])
    b.command_tease()
    log = run(b, lambda t: (905, 330), 9.0)
    check("아이콘이 나비에서 멀면(120px 넘게) 밟지 않고 바닥에서 뜀", all(abs(r["feet"] - 900) > 2 for r in log))

    print()
    print("모두 통과" if not FAILS else "실패 %d건: %s" % (len(FAILS), ", ".join(FAILS)))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
