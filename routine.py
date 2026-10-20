"""고양이의 하루 생활 리듬: 잠자는 시간 · 밥 시간(하루 세 번) · 놀아주기 요구.

화면·소리는 다루지 않고 '지금 무슨 일이 일어나야 하는지'만 계산해서 사건 목록으로 돌려준다 (cat.py 가 소리·풍선·행동으로 옮긴다).
시계를 바꿔 끼울 수 있어서 시험하기 쉽다 (tools/test_routine.py).

 · 잠자는 시간(기본 22:00~07:00): 고양이는 구석에서 웅크리고 자고, 이 시간에는 일정·소식 알림도, 밥·놀이 졸라대기도 하지 않는다.
 · 밥 시간(기본 08:00, 13:00, 19:00): 그 시각이 지났는데 밥을 안 줬으면(밥 시간 30분 전부터 준 밥은 인정)
   '냐옹~ 냐옹~' 소리와 풍선으로 3분마다 졸라댄다(최대 10번). 다음 밥 시간이나 잠자는 시간이 되면 그만둔다.
 · 놀아주기: 마지막으로 놀아 준 뒤 일정 시간(기본 60분)이 지나면 놀아 달라고 한다. 컴퓨터 일을 하는 사람도 쉬라는 뜻이다.
   안 놀아 주면 같은 식으로 3분마다 '냐옹~ 냐옹~' (최대 10번).
"""
import datetime as dt
import os
import time

REPEAT_SEC = 180.0         # 졸라대기를 되풀이하는 간격
MAX_REPEATS = 10           # 한 번의 졸라대기에서 최대 횟수 (끝없이 시끄럽지 않게)
MEAL_EARLY = dt.timedelta(minutes=30)        # 밥 시간보다 이만큼 일찍 준 밥도 그 끼니로 친다
MEAL_MAX_WINDOW = dt.timedelta(hours=8)
_TEST_PLAY_SEC = float(os.environ.get("DESKTOPCAT_PLAY_SEC", 0) or 0)      # 시험용: 놀아 달라는 간격(초)을 짧게


def hm(text):
    """'HH:MM' → 하루 중 분(0~1439). 형식이 틀리면 None."""
    try:
        h, m = str(text).split(":")
        h, m = int(h), int(m)
        if 0 <= h <= 23 and 0 <= m <= 59:
            return h * 60 + m
    except (ValueError, AttributeError):
        pass
    return None


def meal_label(slot: dt.datetime) -> str:
    return "아침" if slot.hour < 11 else "점심" if slot.hour < 16 else "저녁"


class Routine:
    def __init__(self, settings, now_fn=time.time):
        """now_fn(): 지금 시각(초, time.time 과 같은 형식). 시험에서 가짜 시계를 넣는다."""
        self.settings = settings
        self.now_fn = now_fn
        st = settings.data.setdefault("care_state", {})
        self.last_fed = float(st.get("last_fed", 0.0) or 0.0)
        self.last_play = now_fn()                    # 프로그램을 켠 때부터 센다
        self.meal = None                             # 졸라대는 중인 끼니 {"slot", "n", "next"}
        self.play = None                             # 놀아 달라는 중 {"n", "next"}
        self._night = None

    # --- 설정 ----------------------------------------------------------
    @property
    def cfg(self):
        return self.settings.data["care"]

    def _dt(self, ts=None):
        return dt.datetime.fromtimestamp(self.now_fn() if ts is None else ts)

    # --- 잠자는 시간 -----------------------------------------------------
    def is_night(self, now: dt.datetime | None = None) -> bool:
        c = self.cfg["night"]
        a, b = hm(c.get("start")), hm(c.get("end"))
        if not c.get("enabled") or a is None or b is None or a == b:
            return False
        now = now or self._dt()
        m = now.hour * 60 + now.minute
        return (a <= m < b) if a < b else (m >= a or m < b)          # 22:00~07:00 처럼 자정을 넘기는 경우

    def _night_start_today(self, now):
        a = hm(self.cfg["night"].get("start"))
        return now.replace(hour=a // 60, minute=a % 60, second=0, microsecond=0) if a is not None and self.cfg["night"].get("enabled") else None

    # --- 밥 시간 ---------------------------------------------------------
    def meal_slots(self, now: dt.datetime):
        out = []
        for t in self.cfg["meals"].get("times", []):
            m = hm(t)
            if m is not None:
                out.append(now.replace(hour=m // 60, minute=m % 60, second=0, microsecond=0))
        return sorted(set(out))

    def due_meal(self, now: dt.datetime):
        """지금 '밥을 줘야 하는데 안 준' 끼니의 시각. 없으면 None."""
        c = self.cfg["meals"]
        if not c.get("enabled") or self.is_night(now):
            return None
        slots = self.meal_slots(now)
        night_start = self._night_start_today(now)
        due = None
        for i, sl in enumerate(slots):
            end = sl + MEAL_MAX_WINDOW
            if i + 1 < len(slots):
                end = min(end, slots[i + 1])
            if night_start is not None and night_start > sl:
                end = min(end, night_start)
            if sl <= now < end and self.last_fed < (sl - MEAL_EARLY).timestamp():
                due = sl
        return due

    @property
    def meal_active(self) -> bool:
        return self.meal is not None

    def fed(self):
        """밥을 먹었다 (간식 포함)."""
        self.last_fed = self.now_fn()
        self.meal = None
        st = self.settings.data.setdefault("care_state", {})
        st["last_fed"] = self.last_fed
        self.settings.save()

    # --- 놀아주기 --------------------------------------------------------
    @property
    def play_active(self) -> bool:
        return self.play is not None

    def played(self):
        self.last_play = self.now_fn()
        self.play = None

    snooze_play = played                          # 직접 '한쪽에서 쉬기'를 켠 순간에는 놀아 달라는 요구를 한 주기 미룬다

    # --- 시간이 흐를 때 (몇 초에 한 번 부른다) ---------------------------------
    def tick(self, mono: float):
        """지금 해야 할 일의 목록: ('night',) ('wake',) ('meal', 이름, 처음인가) ('play_start',) ('play', 처음인가)."""
        now = self._dt()
        events = []
        night = self.is_night(now)
        if night != self._night:
            if self._night is not None or night:         # 켠 직후 낮이면 'wake' 를 알릴 필요가 없다
                events.append(("night",) if night else ("wake",))
            self._night = night
        if night:
            self.meal = self.play = None
            return events
        # 밥
        due = self.due_meal(now)
        if due is None:
            self.meal = None
        else:
            if self.meal is None or self.meal["slot"] != due:
                self.meal = {"slot": due, "n": 0, "next": mono}
            if mono >= self.meal["next"] and self.meal["n"] < MAX_REPEATS:
                events.append(("meal", meal_label(due), self.meal["n"] == 0))
                self.meal["n"] += 1
                self.meal["next"] = mono + REPEAT_SEC
        # 놀아주기
        p = self.cfg["play"]
        every = max(10, int(p.get("every_min", 60) or 60)) * 60
        if _TEST_PLAY_SEC:
            every = _TEST_PLAY_SEC                   # 시험할 때만 환경 변수로 줄임
        if p.get("enabled") and self.now_fn() - self.last_play >= every:
            if self.play is None:
                self.play = {"n": 0, "next": mono}
                events.append(("play_start",))
            if mono >= self.play["next"] and self.play["n"] < MAX_REPEATS:
                events.append(("play", self.play["n"] == 0))
                self.play["n"] += 1
                self.play["next"] = mono + REPEAT_SEC
        else:
            self.play = None
        return events
