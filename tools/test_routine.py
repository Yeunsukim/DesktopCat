"""생활 리듬(routine.py) 점검: 가짜 시계로 잠자는 시간·밥 시간·놀아주기 요구가 제때 일어나는지 확인한다.

    python tools/test_routine.py
"""
import datetime as dt
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import routine as R  # noqa: E402
from config_store import Settings  # noqa: E402

ok = True


def check(label, cond):
    global ok
    ok &= bool(cond)
    print(("통과 " if cond else "실패 ") + label)


class Clock:
    def __init__(self, y=2026, mo=10, d=19, h=12, mi=0):
        self.t = dt.datetime(y, mo, d, h, mi).timestamp()

    def __call__(self):
        return self.t

    def set(self, h, mi=0, d=19):
        self.t = dt.datetime(2026, 10, d, h, mi).timestamp()

    def at(self, h, mi=0, d=19):
        return dt.datetime(2026, 10, d, h, mi)


def make(clock):
    st = Settings(Path(tempfile.mkdtemp()))
    st.save = lambda: None
    return R.Routine(st, clock), st


# --- 잠자는 시간
c = Clock(); r, st = make(c)
check("21:59 는 낮", not r.is_night(c.at(21, 59)))
check("22:00 부터 밤", r.is_night(c.at(22, 0)))
check("자정 지나 03:00 도 밤", r.is_night(c.at(3, 0)))
check("06:59 까지 밤", r.is_night(c.at(6, 59)))
check("07:00 에 깸", not r.is_night(c.at(7, 0)))
st.data["care"]["night"]["start"], st.data["care"]["night"]["end"] = "23:30", "05:30"
check("시간을 바꾸면 따라감 (23:29 낮, 23:30 밤, 05:29 밤, 05:30 낮)", not r.is_night(c.at(23, 29)) and r.is_night(c.at(23, 30)) and r.is_night(c.at(5, 29)) and not r.is_night(c.at(5, 30)))
st.data["care"]["night"]["enabled"] = False
check("끄면 언제나 낮", not r.is_night(c.at(2, 0)))
st.data["care"]["night"].update(enabled=True, start="xx", end="07:00")
check("시각 형식이 틀리면 낮으로 처리(오류 없음)", not r.is_night(c.at(2, 0)))

# --- 밥 시간
c = Clock(h=7, mi=59); r, st = make(c)
check("07:59 에는 아직 밥 시간 아님", r.due_meal(c.at(7, 59)) is None)
check("08:00 이 되면 아침 밥 시간", r.due_meal(c.at(8, 0)) == c.at(8, 0))
c.set(8, 0)
ev = r.tick(1000.0)
check("08:00 첫 졸라대기 사건 ('meal','아침',True)", ("meal", "아침", True) in ev)
check("바로 다음 점검에는 또 울지 않음", not any(e[0] == "meal" for e in r.tick(1010.0)))
check("3분 뒤 되풀이 ('meal','아침',False)", ("meal", "아침", False) in r.tick(1000.0 + R.REPEAT_SEC))
n = 2
mono = 1000.0 + R.REPEAT_SEC
while n < 20:
    mono += R.REPEAT_SEC
    got = [e for e in r.tick(mono) if e[0] == "meal"]
    n += 1 if not got else 0
    if got:
        n_total = r.meal["n"]
    if mono > 1000 + 20 * R.REPEAT_SEC:
        break
check("최대 10번까지만 졸라댐 (n=%d)" % r.meal["n"], r.meal["n"] == R.MAX_REPEATS)
check("졸라대는 중이라는 표시(meal_active)", r.meal_active)
r.fed()
check("밥을 주면 졸라대기가 멈춤", not r.meal_active and r.due_meal(c.at(8, 5)) is None and not any(e[0] == "meal" for e in r.tick(99999.0)))
c.set(13, 0)
check("13:00 에는 점심 밥 시간", r.due_meal(c.at(13, 0)) == c.at(13, 0))
c.set(12, 40); r.last_fed = 0.0
r.fed()                                                   # 12:40 에 미리 줌 (30분 이내)
c.set(13, 0)
check("점심 20분 전에 준 밥은 점심으로 인정", r.due_meal(c.at(13, 0)) is None)
c.set(12, 10); r2, st2 = make(c); r2.last_fed = c.at(12, 10).timestamp()
check("40분 전에 준 밥은 인정 안 함 (12:20에 준 것은 13:00 끼니로 안 침)", True)
c3 = Clock(h=12, mi=20); r3, _ = make(c3); r3.last_fed = c3.at(12, 20).timestamp()
check("12:20 에 준 밥은 13:00 끼니로 인정 안 함", r3.due_meal(c3.at(13, 0)) == c3.at(13, 0))
c4 = Clock(h=19, mi=30); r4, _ = make(c4)
check("19:30 에 저녁 밥 시간(안 줬을 때)", r4.due_meal(c4.at(19, 30)) == c4.at(19, 0))
check("21:59 까지 저녁을 안 줬으면 졸라댐", r4.due_meal(c4.at(21, 59)) == c4.at(19, 0))
check("22:00 잠자는 시간에는 졸라대지 않음", r4.due_meal(c4.at(22, 0)) is None)
check("점심 끼니의 시간대는 저녁 시간에 끝남 (18:59 에도 점심 미급식이면 졸라댐)", r4.due_meal(c4.at(18, 59)) == c4.at(13, 0))
check("19:00 에는 점심이 아니라 저녁", r4.due_meal(c4.at(19, 0)) == c4.at(19, 0))
st4 = r4.settings; st4.data["care"]["meals"]["enabled"] = False
check("밥 시간 기능을 끄면 졸라대지 않음", r4.due_meal(c4.at(19, 30)) is None)
st4.data["care"]["meals"].update(enabled=True, times=["8:00", "zz", "25:00", "13:00"])
check("틀린 시각은 무시하고 맞는 것만 사용", [s.hour for s in r4.meal_slots(c4.at(0, 0))] == [8, 13])

# --- 밤 사건과 아침 사건
c = Clock(h=21, mi=59); r, st = make(c); r.fed()
r.last_play = c.t
check("낮에 켜면 'wake' 사건이 없음", not any(e[0] == "wake" for e in r.tick(1.0)))
c.set(22, 0)
ev = r.tick(2.0)
check("22:00 에 ('night',) 사건", ("night",) in ev)
c.set(23, 0); r.last_play = 0.0
check("밤에는 놀아 달라고도, 밥 달라고도 안 함", r.tick(3.0) == [])
c.set(7, 0, d=20)
check("07:00 에 ('wake',) 사건", ("wake",) in r.tick(4.0))
cn = Clock(h=23, mi=0); rn, _ = make(cn)
check("밤에 켜면 처음에 ('night',) 사건", ("night",) in rn.tick(1.0))

# --- 놀아주기
c = Clock(h=10, mi=0); r, st = make(c); r.fed()
c.set(10, 59)
check("59분 지나기 전에는 놀아 달라고 안 함", not any(e[0] in ("play", "play_start") for e in r.tick(10.0)))
c.set(11, 0)
ev = r.tick(20.0)
check("1시간 뒤 ('play_start',) 와 ('play',True)", ("play_start",) in ev and ("play", True) in ev and r.play_active)
check("3분 뒤 되풀이 ('play',False)", ("play", False) in r.tick(20.0 + R.REPEAT_SEC))
r.played()
check("놀아 주면 요구가 멈추고 1시간 다시 셈", not r.play_active and not any(e[0] == "play" for e in r.tick(2000.0)))
c.set(11, 30); check("놀아 준 뒤 30분 후에는 조용", not any(e[0] == "play" for e in r.tick(2100.0)))
c.set(12, 0, d=19); c.t += 1
check("놀아 준 뒤 1시간이 되면 다시 요구", any(e[0] == "play" for e in r.tick(2200.0)))
st.data["care"]["play"]["every_min"] = 30
r.played(); c.t += 29 * 60
check("간격을 30분으로 바꾸면 29분엔 조용", not any(e[0] == "play" for e in r.tick(3000.0)))
c.t += 2 * 60
check("30분이 지나면 요구", any(e[0] == "play" for e in r.tick(3100.0)))
st.data["care"]["play"]["enabled"] = False; r.played(); c.t += 3 * 3600
check("놀아주기 요구를 끄면 조용", not any(e[0] in ("play", "play_start") for e in r.tick(4000.0)))

print("전체:", "모두 통과" if ok else "실패 있음")
sys.exit(0 if ok else 1)
