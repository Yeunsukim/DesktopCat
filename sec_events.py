"""경비 고양이가 잡은 '쥐'(수상한 일) 기록 저장소.

 · 한 건 = {id, ts, kind, level, title, text, data, status}
     kind  : ransom(랜섬웨어) / autorun(새 자동 시작) / process(수상한 프로그램) / privacy(카메라·마이크) / download(내려받은 파일) / system
     level : info(참고) / warn(의심) / danger(위험)
     status: new(새 것) / seen(확인함) / ignored(무시) / allowed(허용 목록에 넣음)
 · 이 PC 안에만 저장한다: 데이터폴더\\security\\events.json (임시 파일에 쓴 뒤 바꿔치기), 30일이 지난 것은 지운다.
 · 감시 스레드에서 add() 를 불러도 안전하다 (잠금). 화면 쪽은 on_add 콜백(cat.py 가 Qt 신호로 이어 준다)으로 새 건을 받는다.
"""
import json
import os
import threading
import time
from pathlib import Path

KEEP_DAYS = 30
MAX_ITEMS = 500
LEVELS = ("info", "warn", "danger")
KINDS = ("ransom", "autorun", "process", "privacy", "download", "system")
STATUSES = ("new", "seen", "ignored", "allowed")


class SecEvents:
    def __init__(self, folder, now_fn=time.time):
        self.dir = Path(folder)
        self.path = self.dir / "events.json"
        self.now_fn = now_fn
        self.lock = threading.Lock()
        self.on_add = None                      # 새 건이 생기면 부르는 함수 (감시 스레드에서 불릴 수 있다)
        self.items = []
        self._seq = 0
        self._load()
        self.purge()

    # --- 저장/불러오기 -------------------------------------------------
    def _load(self):
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(data, list):
                self.items = [e for e in data if isinstance(e, dict) and "id" in e and "ts" in e]
        except (OSError, ValueError):
            self.items = []

    def _save(self):
        try:
            self.dir.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(self.items, ensure_ascii=False), encoding="utf-8")
            os.replace(tmp, self.path)
        except OSError:
            pass

    def purge(self):
        limit = self.now_fn() - KEEP_DAYS * 86400
        with self.lock:
            n = len(self.items)
            self.items = [e for e in self.items if e["ts"] >= limit][-MAX_ITEMS:]
            if len(self.items) != n:
                self._save()

    # --- 사건 -----------------------------------------------------------
    def add(self, kind, level, title, text="", data=None, key=None, cooldown=0.0):
        """새 건을 기록하고 돌려준다. key 가 있고 cooldown(초) 안에 같은 key 의 건이 있으면 새로 만들지 않고 None."""
        now = self.now_fn()
        with self.lock:
            if key and cooldown:
                for e in reversed(self.items):
                    if now - e["ts"] > cooldown:
                        break
                    if e.get("key") == key:
                        return None
            self._seq += 1
            ev = {"id": "%d-%d" % (int(now * 1000), self._seq), "ts": now, "kind": kind, "level": level, "title": title, "text": text,
                  "data": data or {}, "status": "new", "key": key}
            self.items.append(ev)
            limit = now - KEEP_DAYS * 86400
            if len(self.items) > MAX_ITEMS or self.items[0]["ts"] < limit:       # 오래 켜 둬도 쌓이지 않게 기록할 때도 정리한다
                self.items = [e for e in self.items if e["ts"] >= limit][-MAX_ITEMS:]
            self._save()
        cb = self.on_add
        if cb:
            try:
                cb(ev)
            except Exception:
                pass
        return ev

    def get(self, ev_id):
        with self.lock:
            return next((e for e in self.items if e["id"] == ev_id), None)

    def update(self, ev_id, text=None, data=None):
        """이미 기록한 건에 뒤늦게 알게 된 정보(의심 프로그램 후보 등)를 덧붙인다."""
        with self.lock:
            for e in self.items:
                if e["id"] == ev_id:
                    if text is not None:
                        e["text"] = text
                    if data:
                        e["data"].update(data)
                    self._save()
                    return True
        return False

    def set_status(self, ev_id, status):
        with self.lock:
            for e in self.items:
                if e["id"] == ev_id:
                    e["status"] = status
                    self._save()
                    return True
        return False

    def recent(self, limit=100, include_ignored=True):
        with self.lock:
            items = [e for e in self.items if include_ignored or e["status"] != "ignored"]
        return list(reversed(items))[:limit]

    def unread(self):
        with self.lock:
            return sum(1 for e in self.items if e["status"] == "new" and e["level"] != "info")

    def clear(self):
        with self.lock:
            self.items = []
            self._save()
