"""VirusTotal 해시 조회 (선택 기능: 사용자가 키를 넣고 켠 경우에만).

 · 보내는 것은 파일의 SHA-256 '해시값'(지문)뿐이다. 파일 내용·이름·경로는 보내지 않는다.
 · 요청: GET https://www.virustotal.com/api/v3/files/{sha256}  (헤더 x-apikey). 404 = VirusTotal 이 모르는 파일('안전'하다는 뜻이 아니다).
 · lookup() 은 보조 프로세스(nethelper) 안에서 돌고, 키는 표준 입력으로만 받는다(명령줄·로그에 안 남는다).
 · 한도(무료: 분당 4건, 하루 500건)를 지키려고 본체 쪽에서 Limiter 로 16초 간격·하루 450건을 넘기지 않고, 결과는 해시별로 30일 보관한다.
 · 시험용: DESKTOPCAT_VT_BASE=http://127.0.0.1:포트/api/v3 (이 컴퓨터의 가짜 서버로만 연결할 수 있다).
"""
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = "https://www.virustotal.com/api/v3"
_override = os.environ.get("DESKTOPCAT_VT_BASE", "")
if _override.startswith("http://127.0.0.1"):
    BASE = _override
MIN_GAP = 16.0                  # 초: 요청 사이 간격 (분당 4건)
DAILY_MAX = 450                 # 하루에 보내는 최대 요청 (무료 한도 500건보다 여유 있게)
CACHE_DAYS = 30
EICAR_SHA256 = "275a021bbfb6489e54d471899f7db9d1663fc695ec2fe2a2c4538aabf651fd0f"      # 모든 백신이 잡는 표준 '시험용 가짜 바이러스' 파일의 해시 (연결 시험용)


class VTError(Exception):
    def __init__(self, message, retry=False):
        super().__init__(message)
        self.retry = retry


def lookup(key: str, sha256: str, timeout: float = 25.0) -> dict:
    """{"found": bool, "malicious": n, "suspicious": n, "harmless": n, "undetected": n, "names": [...], "link": 주소}. 실패하면 VTError."""
    key, sha256 = (key or "").strip(), (sha256 or "").strip().lower()
    if not key or len(sha256) != 64 or not key.isascii() or any(c.isspace() for c in key):
        raise VTError("VirusTotal 키나 해시가 올바르지 않다냥 (키는 공백·한글 없이 영문·숫자만이다옹)")
    req = urllib.request.Request("%s/files/%s" % (BASE, sha256), headers={"x-apikey": key, "User-Agent": "DesktopCat/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read(2 * 1024 * 1024).decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return {"found": False, "malicious": 0, "suspicious": 0, "harmless": 0, "undetected": 0, "names": [], "link": "https://www.virustotal.com/gui/file/" + sha256}
        if e.code in (401, 403):
            raise VTError("VirusTotal 키가 틀렸거나 쓸 수 없다냥 (키를 다시 확인해 달라옹)") from None
        if e.code == 429:
            raise VTError("VirusTotal 조회 한도를 넘었다냥 (무료는 분당 4건·하루 500건이다옹)", True) from None
        raise VTError("VirusTotal이 요청을 거절했다냥 (%d)" % e.code) from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise VTError("VirusTotal에 연결을 못 했다냥 (인터넷을 확인해 달라옹)", True) from None
    except ValueError:
        raise VTError("VirusTotal 대답을 읽지 못했다냥") from None
    attr = (data.get("data") or {}).get("attributes") or {}
    st = attr.get("last_analysis_stats") or {}
    return {"found": True, "malicious": int(st.get("malicious", 0)), "suspicious": int(st.get("suspicious", 0)), "harmless": int(st.get("harmless", 0)),
            "undetected": int(st.get("undetected", 0)), "names": list(attr.get("names") or [])[:3], "link": "https://www.virustotal.com/gui/file/" + sha256}


def verdict(res: dict):
    """조회 결과 → (단계 변화, 문장). 단계 변화: 'danger'(위험으로 올림) / 'warn' / 'ok'(문제 없음) / None(정보 없음)."""
    if not res.get("found"):
        return None, "VirusTotal에 이 파일의 정보가 없어요(처음 보는 파일이라는 뜻이고, 안전하다는 뜻은 아니에요)."
    m, s = res["malicious"], res["suspicious"]
    total = m + s + res["harmless"] + res["undetected"]
    if m >= 3:
        return "danger", "VirusTotal: 백신 %d곳이 악성으로 판정했어요 (전체 %d곳 중)." % (m, total)
    if m >= 1 or s >= 3:
        return "warn", "VirusTotal: 백신 %d곳이 악성/의심으로 판정했어요 (전체 %d곳 중, 오탐일 수도 있어요)." % (m + s, total)
    return "ok", "VirusTotal: 알려진 문제가 없어요 (전체 %d곳 중 악성 0)." % total


class Limiter:
    """분당·하루 한도를 지키고 결과를 해시별로 보관한다 (본체 쪽, 작업 스레드에서 쓴다)."""

    def __init__(self, state_path, now_fn=time.time):
        self.path = Path(state_path)
        self.now = now_fn
        try:
            self.state = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self.state = {}
        self.state.setdefault("cache", {})
        self.state.setdefault("day", "")
        self.state.setdefault("count", 0)
        self.state.setdefault("last", 0.0)

    def _save(self):
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self.state, ensure_ascii=False), encoding="utf-8")
            os.replace(tmp, self.path)
        except OSError:
            pass

    def cached(self, sha):
        c = self.state["cache"].get(sha)
        if c and self.now() - c["ts"] < CACHE_DAYS * 86400:
            return c["res"]
        return None

    def wait_time(self):
        """다음 요청까지 기다려야 하는 초. 하루 한도를 넘었으면 None (오늘은 더 못 한다)."""
        today = time.strftime("%Y-%m-%d", time.localtime(self.now()))
        if self.state["day"] != today:
            self.state["day"], self.state["count"] = today, 0
        if self.state["count"] >= DAILY_MAX:
            return None
        return max(0.0, self.state["last"] + MIN_GAP - self.now())

    def record(self, sha, res):
        self.state["last"] = self.now()
        self.state["count"] += 1
        if res is not None:
            self.state["cache"][sha] = {"ts": self.now(), "res": res}
            if len(self.state["cache"]) > 3000:
                old = sorted(self.state["cache"].items(), key=lambda kv: kv[1]["ts"])[:1000]
                for k, _ in old:
                    self.state["cache"].pop(k, None)
        self._save()
