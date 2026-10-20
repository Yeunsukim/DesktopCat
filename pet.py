"""키우기 상태: 배고픔 / 기분. pet_state.json 으로 저장된다."""
import json
import os
import time
from pathlib import Path

HUNGER_PER_SEC = 1 / 300       # 하루 세 끼에 맞춰서: 밥을 먹고 약 5시간이면 '배고픔'(70%)에 이른다
SLEEP_HUNGER_FACTOR = 0.2      # 잠자는 시간에는 배고픔이 천천히 쌓인다
OFFLINE_HUNGER_CAP = 85        # 꺼둔 동안에는 이 이상 배고파지지 않는다 (굶어 죽지 않음)
OFFLINE_MOOD_FLOOR = 20


def _clamp(v, lo=0.0, hi=100.0):
    return max(lo, min(hi, v))


class Pet:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.hunger = 30.0
        self.mood = 60.0
        self.coat = "brown"                # 고르는 털색 (coats.py 의 이름)
        self.sleeping = False              # 잠자는 시간이면 True (cat.py 가 정한다)
        self._since_save = 0.0
        self._load()

    # --- 저장/불러오기 -------------------------------------------------
    def _load(self):
        try:
            d = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        self.hunger = _clamp(float(d.get("hunger", self.hunger)))
        self.mood = _clamp(float(d.get("mood", self.mood)))
        self.coat = str(d.get("coat", self.coat))
        elapsed = max(0.0, time.time() - float(d.get("last_seen", time.time())))
        if elapsed > 0:
            self.hunger = max(self.hunger, min(OFFLINE_HUNGER_CAP, self.hunger + elapsed * HUNGER_PER_SEC))
            self.mood = max(min(self.mood, OFFLINE_MOOD_FLOOR), self.mood - elapsed / 300)

    def save(self):
        data = {"hunger": round(self.hunger, 2), "mood": round(self.mood, 2), "last_seen": time.time(), "coat": self.coat}
        try:                                # 임시 파일에 쓴 뒤 바꿔치기: 저장하다 꺼져도 기록 파일이 깨지지 않는다
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(data), encoding="utf-8")
            os.replace(tmp, self.path)
        except OSError:
            pass

    # --- 시간 경과 -----------------------------------------------------
    def tick(self, dt: float):
        self.hunger = _clamp(self.hunger + dt * HUNGER_PER_SEC * (SLEEP_HUNGER_FACTOR if self.sleeping else 1.0))
        if self.hunger > 70:
            self.mood = _clamp(self.mood - dt / 45)
        elif self.mood > 50:
            self.mood = _clamp(self.mood - dt / 150)       # 기분 좋은 상태도 서서히 가라앉음
        elif self.hunger < 40:
            self.mood = _clamp(self.mood + dt / 200)
        self._since_save += dt
        if self._since_save >= 30:
            self._since_save = 0
            self.save()

    # --- 행동 ---------------------------------------------------------
    @property
    def is_full(self) -> bool:
        return self.hunger < 10

    def feed(self):
        self.hunger = _clamp(self.hunger - 45)
        self.mood = _clamp(self.mood + 5)

    def feed_meal(self):
        """밥 시간의 정식 식사: 간식(feed)보다 많이 먹는다."""
        self.hunger = _clamp(self.hunger - 70)
        self.mood = _clamp(self.mood + 8)

    def play(self):
        self.mood = _clamp(self.mood + 20)
        self.hunger = _clamp(self.hunger + 5)

    def stroke(self):
        self.mood = _clamp(self.mood + 8)

    @property
    def hungry(self) -> bool:
        return self.hunger > 70

    @property
    def happy(self) -> bool:
        return self.mood > 70
