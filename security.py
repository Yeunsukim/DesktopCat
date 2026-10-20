"""경비 고양이의 본부: 사건 저장소와 감시기들(랜섬웨어 …)을 만들고 켜고 끈다.

cat.py 는 이 클래스 하나만 다룬다.
 · event 신호: 새 사건(경보)이 생기면 화면 스레드에서 받을 수 있게 Qt 신호로 이어 준다 (감시는 다른 스레드에서 돈다).
 · start()/stop()/reload(): 설정(settings.data["security"])대로 감시기를 켜고 끈다.
 · test_alert(level): 시험 경보를 하나 만든다 (설정 창의 '시험 경보 보기').
"""
import os
import sys
import threading
from pathlib import Path

from PyQt6.QtCore import QObject, pyqtSignal

import sec_common
from sec_events import SecEvents


class SecurityGuard(QObject):
    event = pyqtSignal(dict)
    vt_result = pyqtSignal(dict)                      # VirusTotal 연결 시험 결과 {ok, text}
    scanned = pyqtSignal(dict)                        # 점검이 한 번 끝났다 (결과 요약: 자동 시작 수, 프로그램 수, 알림 수, 오류)

    def __init__(self, settings, data_dir, project_root=None, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.dir = Path(data_dir) / "security"
        self.ignore_roots = [str(data_dir), str(project_root)] if project_root else [str(data_dir)]
        self.events = SecEvents(self.dir)
        self.events.on_add = lambda ev: self.event.emit(ev)             # 다른 스레드에서 불려도 Qt 가 화면 스레드로 넘겨 준다
        self.ransom = None
        self._scan_stop = threading.Event()
        self._scan_thread = None
        self._scan_lock = threading.Lock()
        self._priv_thread = None
        self.downloads = None
        self._vt_limiter = None

    @property
    def cfg(self):
        return self.settings.data["security"]

    def folders(self):
        f = [x for x in self.cfg["ransom"].get("folders", []) if Path(x).is_dir()]
        return f or sec_common.default_folders()

    def start(self):
        cfg = self.cfg
        if not cfg.get("enabled"):
            return
        if self._scan_stop.is_set():                                      # 멈췄다가 다시 켤 때: 새 신호 (예전 스레드는 예전 신호를 보고 끝난다)
            self._scan_stop = threading.Event()
        self._start_scanner()
        self._start_privacy()
        self._start_downloads()
        r = cfg["ransom"]
        if r.get("enabled") and self.ransom is None:
            try:
                from sec_ransom import RansomWatcher
                folders = self.folders()
                self.ransom = RansomWatcher(self.events, folders, r.get("sensitivity", "normal"), self.dir / "canary.json",
                                            use_canary=bool(r.get("canary")), ignore_roots=self.ignore_roots, canary_folders=self.canary_folders(folders))
                self.ransom.start()
            except Exception as e:                                        # 경비가 못 켜져도 고양이는 계속 돌아야 한다
                self.ransom = None
                self.events.add("system", "info", "랜섬웨어 감시를 시작하지 못했어요", "%s: %s" % (e.__class__.__name__, e), key="ransom-start", cooldown=3600)

    @staticmethod
    def canary_folders(folders):
        """미끼 파일은 바탕화면(아이콘이 있는 곳)에는 두지 않는다."""
        desk = sec_common._known_folder(0x10)
        return [f for f in folders if not (desk and Path(f).resolve() == Path(desk).resolve())]

    # --- 자동 시작·프로세스 점검 (보조 프로세스에서 몇 분마다) -----------------------
    def _start_scanner(self):
        if self._scan_thread is not None or not self.cfg.get("scan", {}).get("enabled"):
            return
        self._scan_thread = threading.Thread(target=self._scan_loop, args=(self._scan_stop,), daemon=True)
        self._scan_thread.start()

    # --- VirusTotal (선택) ---------------------------------------------------
    def vt_key(self):
        if not self.cfg.get("vt", {}).get("enabled"):
            return ""
        try:
            return self.settings.get_secret("vt_key")
        except Exception:
            return ""

    def _vt_query(self, sha, key):
        """해시 하나를 VirusTotal 에 묻는다 (보관된 결과가 있으면 그것). 실패하거나 한도를 넘었으면 None. 작업 스레드에서 부를 것."""
        import time
        import nethelper
        import vt_client
        if self._vt_limiter is None:
            self._vt_limiter = vt_client.Limiter(self.dir / "vt_state.json")
        lim = self._vt_limiter
        res = lim.cached(sha)
        if res is not None:
            return res
        wait = lim.wait_time()
        if wait is None:
            return None                                                   # 오늘 한도를 다 썼다
        if wait > 0:
            time.sleep(min(wait, vt_client.MIN_GAP))
        try:
            res = nethelper.call("vt", key=key, sha256=sha)
        except Exception:
            lim.record(sha, None)
            return None
        lim.record(sha, res)
        return res

    def enrich(self, finding):
        """수상한 건에 VirusTotal 결과를 반영한다 (켜 있고 키가 있고, 서명이 유효하지 않은 파일만). 단계·문장·data 를 고쳐서 돌려준다."""
        key = self.vt_key()
        d = finding.get("data", {})
        path = d.get("path", "")
        if not key or not path or str(d.get("status", "")).lower() == "valid":
            return finding
        import sec_common
        import vt_client
        sha = sec_common.file_sha256(path)
        if not sha:
            return finding
        res = self._vt_query(sha, key)
        if res is None:
            return finding
        change, line = vt_client.verdict(res)
        d["vt"] = {"found": res["found"], "malicious": res["malicious"], "link": res["link"]}
        d["sha256"] = sha
        finding["text"] = finding["text"] + "\n· " + line + "\n  (파일의 해시값만 조회했고 파일 내용은 보내지 않았어요)"
        if change == "danger":
            finding["level"] = "danger"
        elif change == "warn" and finding["level"] == "info":
            finding["level"] = "warn"
        elif change == "ok" and finding["level"] == "warn":
            finding["level"] = "info"                                     # 널리 알려진 안전한 파일이면 의심을 거둔다 (기록은 남긴다)
            finding["title"] = finding["title"] + " (VirusTotal에서 문제 없음)"
        return finding

    def vt_test_async(self, key):
        """설정 창의 'VirusTotal 연결 시험': 모든 백신이 잡는 표준 시험 파일(EICAR)의 해시로 조회해 본다."""
        def work():
            import nethelper
            import vt_client
            try:
                res = nethelper.call("vt", key=key, sha256=vt_client.EICAR_SHA256)
                if res.get("found"):
                    self.vt_result.emit({"ok": True, "text": "연결 성공이다냥. 시험 파일을 백신 %d곳이 악성으로 판정했다옹." % res["malicious"]})
                else:
                    self.vt_result.emit({"ok": True, "text": "연결은 됐다냥 (시험 파일 정보는 없다옹)."})
            except Exception as e:
                self.vt_result.emit({"ok": False, "text": str(e)})
        threading.Thread(target=work, daemon=True).start()

    # --- 다운로드 폴더 검사 ----------------------------------------------------
    def _start_downloads(self):
        if self.downloads is not None or not self.cfg.get("download", {}).get("enabled", True):
            return
        try:
            from sec_download import DownloadWatcher
            self.downloads = DownloadWatcher([Path.home() / "Downloads"], self._on_download)
            self.downloads.start(self.dir)
        except Exception:
            self.downloads = None

    def _on_download(self, f):
        d = f.get("data", {})
        if d.get("path", "").lower() in [p.lower() for p in self.cfg.get("allow", {}).get("process", [])]:
            return
        f = self.enrich(f)
        self.events.add(f["kind"], f["level"], f["title"], f["text"], f["data"], key=f["key"], cooldown=86400)

    # --- 카메라·마이크 사용 감시 (레지스트리 읽기만, 30초마다) -------------------------
    def _start_privacy(self):
        if self._priv_thread is not None or not self.cfg.get("privacy", {}).get("enabled", True):
            return
        self._priv_thread = threading.Thread(target=self._priv_loop, args=(self._scan_stop,), daemon=True)
        self._priv_thread.start()

    def _priv_loop(self, stop):
        import sec_privacy
        state_file = self.dir / "privacy_state.json"
        state = sec_privacy.load_state(state_file)
        while not stop.wait(30.0):
            try:
                rows = sec_privacy.read_usage()
                evs, new_state = sec_privacy.check_usage(rows, state, self.cfg.get("allow", {}).get("privacy", []))
                if new_state != state:                                    # 바뀐 때만 저장 (디스크 쓰기를 줄인다)
                    sec_privacy.save_state(state_file, new_state)
                state = new_state
                for e in evs:
                    e["data"]["suspects"] = [dict(s, mb_s="") for s in sec_privacy.running_suspects(e["data"].get("path", ""))]
                    self.events.add(e["kind"], e["level"], e["title"], e["text"], e["data"], key=e["key"], cooldown=86400)
            except Exception:
                pass

    def _scan_loop(self, stop):
        delay = 90.0                                                      # 켠 직후에는 고양이가 자리 잡도록 잠깐 기다린다
        while not stop.wait(delay):
            self.scan_now()
            delay = max(5, int(self.cfg.get("scan", {}).get("interval_min", 10))) * 60.0

    def self_paths(self):
        paths = [os.path.dirname(sys.executable)]
        paths += [str(p) for p in self.ignore_roots]
        return paths

    def scan_async(self):
        """설정 창의 '지금 점검': 백그라운드에서 점검하고 끝나면 scanned 신호(manual=True)로 알린다."""
        threading.Thread(target=self.scan_now, args=(True,), daemon=True).start()

    def scan_now(self, manual=False):
        """점검을 한 번 한다 (작업 스레드에서 부를 것: 몇 초~몇십 초 걸린다). 사건은 events 에 기록하고 scanned 신호로 요약을 알린다."""
        if not self._scan_lock.acquire(blocking=False):
            if manual:
                self.scanned.emit({"error": "이미 점검 중이다냥", "entries": 0, "processes": 0, "found": 0, "manual": True})
            return None                                                   # 이미 점검 중
        try:
            import nethelper
            res = nethelper.call("scan", work_dir=str(self.dir), allow=self.cfg.get("allow", {}), self_paths=self.self_paths())
        except Exception as e:
            summary = {"error": str(e), "entries": 0, "processes": 0, "found": 0, "manual": manual}
            self.scanned.emit(summary)
            return summary
        finally:
            self._scan_lock.release()
        n = 0
        for i, f in enumerate(res.get("findings", [])):
            if i < 5 and f["level"] in ("warn", "danger"):
                try:
                    f = self.enrich(f)                                    # 켜져 있으면 VirusTotal 로 한 번 더 (한 번에 최대 5건)
                except Exception:
                    pass
            if self.events.add(f["kind"], f["level"], f["title"], f["text"], f["data"], key=f["key"], cooldown=86400):
                n += 1
        summary = {"entries": res.get("entries", 0), "processes": res.get("processes", 0), "found": n, "first": res.get("first", False), "manual": manual}
        self.scanned.emit(summary)
        return summary

    def allow(self, ev):
        """경보를 '허용 목록'에 넣는다 (같은 프로그램·항목은 다시 알리지 않는다)."""
        a = self.cfg.setdefault("allow", {"process": [], "autorun": [], "privacy": []})
        d = ev.get("data", {})
        if ev["kind"] in ("process", "download") and d.get("path"):
            a.setdefault("process", []).append(d["path"].lower())             # (다운로드한 파일도 같은 허용 목록: 경로 기준)
        elif ev["kind"] == "autorun" and d.get("id"):
            a.setdefault("autorun", []).append(d["id"])
        elif ev["kind"] == "privacy" and d.get("app"):
            a.setdefault("privacy", []).append(d["app"].lower())
        self.settings.save()

    def stop(self):
        self._scan_stop.set()
        if self.downloads is not None:
            self.downloads.stop()
            self.downloads = None
        self._scan_thread = None
        self._priv_thread = None
        if self.ransom is not None:
            self.ransom.stop()
            self.ransom = None

    def reload(self):
        self.stop()
        self.start()

    def remove_canaries(self):
        """우리가 만든 미끼 파일만 지운다 (감시 중이면 감시를 멈췄다가 지움). 지운 개수를 돌려준다."""
        was = self.ransom is not None
        self.stop()
        from sec_ransom import Canaries
        n = Canaries(self.dir / "canary.json").remove_all()
        if was:
            self.cfg["ransom"]["canary"] = False
            self.settings.save()
            self.start()
        return n

    def test_alert(self, level="danger"):
        """시험 경보 (진짜 문제가 아니라 화면·소리·쥐 잡기가 어떻게 보이는지 확인하는 용도)."""
        if level == "danger":
            return self.events.add("ransom", "danger", "쥐 발견! (시험 경보)", "이것은 시험 경보예요. 진짜 문제가 아니니 걱정하지 않아도 돼요.\n"
                                   "진짜 랜섬웨어가 의심되면 이 창에 어떤 일이 일어났는지, 어떤 프로그램이 의심되는지, 지금 해야 할 일이 나와요.",
                                   {"test": True, "source": "test", "files": 0, "dirs": 0, "samples": [], "suspects": [], "reasons": []})
        return self.events.add("process", "warn", "수상한 쥐 후보 (시험 경보)", "이것은 시험 경보예요. 의심 단계(노란 경고)는 풍선으로만 알려 주고, 눌러야 자세히 보여요.",
                               {"test": True})
