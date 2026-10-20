"""다운로드 파일 검사: 다운로드 폴더에 새로 생긴 실행 파일·스크립트를 살펴본다 (읽기만, 파일을 건드리지 않는다).

살펴보는 것 (모두 이 PC 안에서):
 · 인터넷에서 받은 파일인가: 파일 끝에 붙는 'Zone.Identifier'(Mark of the Web, ZoneId=3 이면 인터넷)와 출처 주소.
 · 디지털 서명: 유효하면 만든 곳이 확인된 프로그램, 없으면 출처를 알 수 없다(악성이라는 뜻은 아님), 서명 뒤 변조(HashMismatch)면 위험.
 · 이중 확장자(report.pdf.exe), 위험한 종류(스크립트·바로가기·디스크 이미지).
 · (선택) VirusTotal 해시 조회: 켜 두었다면 서명이 유효하지 않은 파일의 해시만 보낸다.
'알리기만' 한다. 파일을 지우거나 격리하지 않는다 (그건 백신이 할 일이다).
"""
import os
import re
import threading
import time
from pathlib import Path

import sec_common
import sec_sig

RISKY_EXE = {".exe", ".msi", ".scr", ".com", ".pif", ".dll"}
RISKY_SCRIPT = {".js", ".jse", ".vbs", ".vbe", ".hta", ".ps1", ".bat", ".cmd", ".wsf", ".jar"}
RISKY_OTHER = {".lnk", ".iso", ".img", ".vhd", ".cab", ".reg"}
WATCH_EXT = RISKY_EXE | RISKY_SCRIPT | RISKY_OTHER
PARTIAL_EXT = {".crdownload", ".part", ".partial", ".download", ".tmp", ".filepart", ".opdownload"}
DOUBLE_EXT = re.compile(r"\.(pdf|docx?|xlsx?|pptx?|jpe?g|png|gif|txt|hwp|zip)\.(exe|scr|com|bat|cmd|pif|js|vbs|hta|lnk)$", re.I)


def read_zone(path: str) -> dict:
    """파일에 붙은 출처 표시: {"zone": 3, "host": "...", "referrer": "..."} (없으면 {})."""
    try:
        with open(path + ":Zone.Identifier", "r", encoding="utf-8", errors="replace") as f:
            txt = f.read(4000)
    except OSError:
        return {}
    out = {}
    for line in txt.splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            out[k.strip().lower()] = v.strip()
    try:
        zone = int(out.get("zoneid", "-1"))
    except ValueError:
        zone = -1
    return {"zone": zone, "host": out.get("hosturl", ""), "referrer": out.get("referrerurl", "")}


def analyze(path: str, sig_status: str, publisher: str, zone: dict):
    """(단계 info/warn/danger 또는 None, 제목, 이유들). 알릴 필요가 없으면 단계 None."""
    name = Path(path).name
    ext = Path(path).suffix.lower()
    status = (sig_status or "").lower()
    from_web = zone.get("zone", -1) >= 3
    reasons = []
    if from_web:
        reasons.append("인터넷에서 받은 파일이에요" + (" (출처: %s)" % zone["host"][:80] if zone.get("host") else ""))
    elif zone.get("zone", -1) == -1:
        reasons.append("‘인터넷에서 받음’ 표시가 없어요 (직접 만든 파일이거나 표시가 지워진 파일이에요)")
    score = 0
    if status == "hashmismatch":
        reasons.append("디지털 서명 뒤에 파일이 바뀐 것 같아요")
        score += 8
    elif status == "valid":
        reasons.append("디지털 서명이 유효해요" + (" (서명한 곳: %s)" % publisher if publisher else ""))
    else:
        reasons.append("디지털 서명이 없어요" if status == "notsigned" else "디지털 서명을 확인하지 못했어요")
        score += 2 if status == "notsigned" else 1
    if DOUBLE_EXT.search(name):
        reasons.append("문서·사진처럼 보이게 이중 확장자를 쓴 실행 파일이에요")
        score += 5
    if ext in RISKY_SCRIPT:
        reasons.append("스크립트 파일(%s)이라 열면 바로 실행돼요" % ext)
        score += 2
    elif ext in RISKY_OTHER:
        reasons.append("%s 파일은 악성코드를 숨기는 데 자주 쓰여요" % ext)
        score += 1
    if from_web:
        score += 1
        if status != "valid" and ext in RISKY_EXE:
            score += 2                                        # 인터넷에서 받은 서명 없는 프로그램: 출처를 한 번 확인해 보라고 알린다
    if status == "valid" and not DOUBLE_EXT.search(name):
        return "info", "내려받은 파일을 살펴봤어요 (서명 확인됨)", reasons
    if score >= 8:
        return "danger", "내려받은 파일이 아주 수상해요", reasons
    if score >= 4:
        plain = not DOUBLE_EXT.search(name) and status != "hashmismatch" and ext in RISKY_EXE
        return "warn", ("서명 없는 프로그램을 내려받았어요 (출처를 확인해 보세요)" if plain else "내려받은 파일이 수상해요"), reasons
    return None, "", reasons


class DownloadWatcher:
    """다운로드 폴더를 지켜보다가 새 실행 파일이 완전히 받아지면 살펴보고 on_finding 으로 알린다."""

    def __init__(self, folders, on_finding, sig_runner=None, settle=2.0, now_fn=time.time):
        self.folders = [str(f) for f in folders if Path(f).is_dir()]
        self.on_finding = on_finding              # on_finding(dict: kind, level, title, text, data, key, path, sha256_needed)
        self.sig_runner = sig_runner
        self.settle = settle
        self.pending = {}
        self.done = {}
        self.lock = threading.Lock()
        self.watchers = []
        self._stop = threading.Event()
        self.work_dir = None

    def start(self, work_dir):
        self.work_dir = Path(work_dir)
        import sec_watch

        def on_event(kind, src, dst):
            if kind == "moved":                                   # 받기를 마친 브라우저가 임시 이름(.crdownload)을 진짜 이름으로 바꾼다
                self.touch(dst)
            elif kind in ("created", "modified"):
                self.touch(src)

        self.watchers = [sec_watch.DirWatcher(f, on_event, recursive=False).start() for f in self.folders]
        threading.Thread(target=self._loop, daemon=True).start()

    def stop(self):
        self._stop.set()
        for w in self.watchers:
            w.stop()
        self.watchers = []

    def touch(self, path):
        p = Path(path)
        ext = p.suffix.lower()
        if ext in PARTIAL_EXT or ext not in WATCH_EXT:
            return
        with self.lock:
            self.pending[str(path)] = (time.time(), -1)

    def _loop(self):
        while not self._stop.wait(1.0):
            now = time.time()
            ready = []
            with self.lock:
                for path, (t, last_size) in list(self.pending.items()):
                    try:
                        size = os.path.getsize(path)
                    except OSError:
                        self.pending.pop(path, None)
                        continue
                    if size == last_size and now - t >= self.settle:           # 크기가 더 안 변하면 다 받은 것
                        ready.append(path)
                        self.pending.pop(path, None)
                    else:
                        self.pending[path] = (t if size == last_size else now, size)
            for path in ready:
                try:
                    self.inspect(path)
                except Exception:
                    pass

    def inspect(self, path):
        try:
            st = os.stat(path)
        except OSError:
            return None
        if st.st_size == 0 or st.st_size > 2 * 1024 ** 3:           # 0바이트: 브라우저가 받기 시작할 때 만드는 빈 자리 (다 받으면 다시 살펴본다)
            return None
        key = "dl|%s|%d|%d" % (path.lower(), int(st.st_mtime), st.st_size)
        with self.lock:
            if key in self.done:
                return None
            self.done[key] = 1
            if len(self.done) > 5000:                               # 오래 켜 둬도 커지지 않게 오래된 절반을 버린다
                self.done = dict(list(self.done.items())[-2500:])
        zone = read_zone(path)
        kw = {"runner": self.sig_runner} if self.sig_runner else {}
        sig = sec_sig.check_many([path], self.work_dir, **kw).get(path, {"status": "Error", "publisher": ""})
        level, title, reasons = analyze(path, sig["status"], sig.get("publisher", ""), zone)
        if level is None:
            return None
        text = "%s\n%s\n%s" % (Path(path).name, path, "\n".join("· " + r for r in reasons))
        finding = {"kind": "download", "level": level, "title": title, "text": text, "key": key,
                   "data": {"path": path, "name": Path(path).name, "status": sig["status"], "publisher": sig.get("publisher", ""),
                            "zone": zone.get("zone", -1), "origin": zone.get("host", ""), "reasons": reasons, "id": key}}
        self.on_finding(finding)
        return finding
