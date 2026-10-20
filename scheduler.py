"""정해 둔 시각에 알림 작업(캘린더·소식·어제 한 일)을 실행하는 스케줄러.

 · 시각이 되면 작업을 별도 스레드에서 돌리고(네트워크 호출이 고양이 화면을 멈추지 않게), 끝나면 시그널로 화면 스레드에 결과를 넘긴다.
 · 같은 시각의 알림은 한 번만: 마지막으로 실행한 시각 칸(last_run)을 설정 파일에 적어 둔다.
 · 컴퓨터가 꺼져 있어서 시각을 놓쳤으면, 켜진 뒤 처음 점검 때 그날 놓친 알림 중 가장 최근 것 하나만 따라잡는다.
 · 설정에서 시각을 바꿔 저장하면 이미 지난 시각들은 '한 것'으로 표시해서, 저장하자마자 알림이 울리지 않는다.
"""
import datetime as dt
import threading

from PyQt6.QtCore import QObject, pyqtSignal

CHECK_EVERY = 20.0                 # 초: 이보다 자주 점검하지 않는다


def slot_str(day: dt.date, hhmm: str) -> str:
    return "%s %s" % (day.isoformat(), hhmm)


def valid_time(s: str) -> bool:
    try:
        h, m = s.split(":")
        return 0 <= int(h) <= 23 and 0 <= int(m) <= 59 and len(m) == 2
    except Exception:
        return False


class Scheduler(QObject):
    finished = pyqtSignal(str, object, object)          # (작업 이름, 결과, 오류 예외 또는 None)

    def __init__(self, settings, jobs: dict, parent=None):
        """jobs: {작업 이름: 인자 없는 함수(스레드에서 실행됨, 결과를 돌려주거나 예외를 던진다)}"""
        super().__init__(parent)
        self.settings = settings
        self.jobs = jobs
        self._running = set()
        self._next = 0.0
        self.quiet = None                 # 함수: True 를 돌려주면(잠자는 시간) 정해 둔 알림 작업을 하지 않는다 ("지금 시험"은 예외)
        self._snap = self._take()         # 알림마다 (켜짐, 시각들): 설정을 저장했을 때 바뀐 알림만 '지난 시각은 한 것'으로 표시하려고 기억해 둔다

    # --- 점검 ---------------------------------------------------------
    def due_slot(self, name: str, now: dt.datetime):
        """지금 실행해야 할 시각 칸 문자열 또는 None. 오늘 지난 칸 중 가장 최근 것이 아직 안 돌았으면 그것."""
        sch = self.settings.data["schedules"].get(name, {})
        if not sch.get("enabled"):
            return None
        last = self.settings.data["last_run"].get(name, "")
        best = None
        for t in sorted(x for x in sch.get("times", []) if valid_time(x)):
            slot = slot_str(now.date(), t)
            if slot <= now.strftime("%Y-%m-%d %H:%M"):
                best = slot
        max_age = sch.get("max_age_min")
        if best and max_age:                         # 매시 알림처럼 '지금'이 중요한 작업: 오래 지난 시각은 따라잡지 않는다
            age = (now - dt.datetime.strptime(best, "%Y-%m-%d %H:%M")).total_seconds() / 60
            if age > max_age:
                return None
        if best and best > last:
            return best
        return None

    def tick(self, mono_now: float, now: dt.datetime | None = None):
        if mono_now < self._next:
            return
        self._next = mono_now + CHECK_EVERY
        if self.quiet and self.quiet():
            return                            # 잠자는 시간: 시각이 지난 알림은 깬 뒤 처음 점검 때 가장 최근 것 하나만 따라잡는다
        now = now or dt.datetime.now()
        for name in self.jobs:
            if name in self._running:
                continue
            slot = self.due_slot(name, now)
            if slot:
                self.settings.data["last_run"][name] = slot          # 실행 전에 적어 둔다: 실패해도 같은 시각에 계속 되풀이하지 않는다
                self.settings.save()
                self.run(name)

    def run(self, name: str):
        """지금 바로(시각과 상관없이) 작업을 실행한다. 설정 창의 '지금 시험' 버튼도 이것을 부른다."""
        if name in self._running or name not in self.jobs:
            return False
        self._running.add(name)
        threading.Thread(target=self._work, args=(name,), daemon=True).start()
        return True

    def _work(self, name):
        try:
            result, err = self.jobs[name](), None
        except Exception as e:                           # 작업이 던진 사용자용 메시지(CalendarError 등)를 그대로 넘긴다
            result, err = None, e                        # 예외 객체 그대로: 받는 쪽이 메시지(str)와 retry 표시를 쓴다
        finally:
            self._running.discard(name)
        self.finished.emit(name, result, err)

    # --- 설정이 바뀔 때 ---------------------------------------------------
    def _take(self):
        out = {}
        for name in self.jobs:
            sch = self.settings.data["schedules"].get(name, {})
            out[name] = (bool(sch.get("enabled")), tuple(sch.get("times", [])))
        return out

    def mark_past_done(self, now: dt.datetime | None = None):
        """시각이나 켜짐이 바뀐 알림만, 오늘 이미 지난 시각들을 '한 것'으로 표시한다 (설정 저장 직후 호출).
        (바뀌지 않은 알림은 그대로 둔다: 자리를 비운 사이 놓친 알림이 있는데 설정만 열었다 저장했다고 사라지면 안 된다.)"""
        now = now or dt.datetime.now()
        snap, self._snap = self._snap, self._take()
        for name in self.jobs:
            if snap.get(name) == self._snap[name]:
                continue
            sch = self.settings.data["schedules"].get(name, {})
            past = [slot_str(now.date(), t) for t in sch.get("times", []) if valid_time(t)
                    and slot_str(now.date(), t) <= now.strftime("%Y-%m-%d %H:%M")]
            if past:
                self.settings.data["last_run"][name] = max(past + [self.settings.data["last_run"].get(name, "")])
        self.settings.save()
