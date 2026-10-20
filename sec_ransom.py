"""랜섬웨어 경보: 문서가 한꺼번에 암호화되기 시작하는 순간을 알아챈다.

세 가지 단서를 본다.
 1) 미끼 파일(canary): 감시 폴더에 숨김 속성의 가짜 문서를 두고, 그것이 바뀌거나 지워지거나 이름이 바뀌면 곧바로 '위험'.
    정상적인 사용자는 숨김 파일을 건드릴 일이 없고, 랜섬웨어는 폴더 안의 문서를 닥치는 대로 암호화하므로 가장 빠르고 오탐이 적다.
 2) 대량 변경 + 암호화 흔적: 짧은 시간(기본 10초)에 많은 기존 파일이 여러 폴더에서 바뀌고, 그와 함께
    (가) 낯선 확장자 하나로 이름이 한꺼번에 바뀌거나, (나) 바뀐 파일의 앞부분이 암호화된 것처럼 보이면(원래 형식의 머리글이 깨졌거나 엔트로피가 너무 높음) '위험'.
 3) 몸값 안내 파일 이름(README·DECRYPT·HOW_TO_RECOVER 계열)이 여러 폴더에 생기면 가점.
오탐을 줄이려고: 새로 만든 파일의 쓰기(압축 풀기·복사·다운로드), .git·node_modules·캐시·임시 파일, 이 프로그램의 폴더는 센 대상에서 뺀다.
이 모듈은 '알리기만' 한다. 파일을 지우거나 프로세스를 끝내지 않는다 (사용자가 버튼을 눌러야 하는 일은 화면 쪽이 맡는다).

 · RansomDetector : 화면·파일 감시와 무관한 순수 판단 로직 (가짜 사건을 넣어 시험할 수 있다)
 · Canaries       : 미끼 파일 만들기·확인·지우기
 · RansomWatcher  : sec_watch(윈도우 ReadDirectoryChangesW)로 폴더를 지켜보며 위 둘을 돌리는 스레드
"""
import collections
import ctypes
import hashlib
import io
import math
import os
import re
import threading
import time
import zipfile
from pathlib import Path

SENSITIVITY = {                      # files: 창 안에서 바뀐 기존 파일 수, dirs: 서로 다른 폴더 수, window: 초
    "loose": {"files": 40, "dirs": 3, "window": 10.0},
    "normal": {"files": 25, "dirs": 2, "window": 10.0},
    "strict": {"files": 12, "dirs": 2, "window": 10.0},
}
IGNORE_PARTS = {".git", "node_modules", "__pycache__", "$recycle.bin", ".venv", "venv", "site-packages", ".idea", ".vscode",
                "appdata", "cache", "code cache", "gpucache", "temp", ".svn", ".gradle", "target", "build", "dist"}
IGNORE_EXT = {".tmp", ".temp", ".crdownload", ".part", ".partial", ".swp", ".swo", ".download", ".filepart"}
COMMON_EXT = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".pdf", ".txt", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".hwp", ".hwpx",
              ".zip", ".7z", ".rar", ".mp3", ".mp4", ".avi", ".mkv", ".mov", ".html", ".htm", ".css", ".js", ".json", ".xml", ".csv", ".md",
              ".py", ".java", ".c", ".cpp", ".h", ".exe", ".dll", ".log", ".bak", ".old", ".ini", ".cfg", ".lnk", ".url"}
NOTE_RE = re.compile(r"(readme|read_me|how[_ \-]?to|decrypt|recover|restore|restoration|unlock|ransom|!+help|_help_|your[_ \-]?files)", re.I)
NOTE_EXT = {".txt", ".html", ".htm", ".hta", ".url", ".rtf", ".md"}
MAGIC = {
    ".docx": (b"PK\x03\x04", b"PK\x05\x06"), ".xlsx": (b"PK\x03\x04", b"PK\x05\x06"), ".pptx": (b"PK\x03\x04", b"PK\x05\x06"),
    ".hwpx": (b"PK\x03\x04",), ".zip": (b"PK\x03\x04", b"PK\x05\x06"), ".jar": (b"PK\x03\x04",),
    ".pdf": (b"%PDF",), ".jpg": (b"\xff\xd8\xff",), ".jpeg": (b"\xff\xd8\xff",), ".png": (b"\x89PNG",), ".gif": (b"GIF8",),
    ".doc": (b"\xd0\xcf\x11\xe0",), ".xls": (b"\xd0\xcf\x11\xe0",), ".ppt": (b"\xd0\xcf\x11\xe0",), ".hwp": (b"\xd0\xcf\x11\xe0",),
    ".7z": (b"7z\xbc\xaf",), ".rar": (b"Rar!",), ".gz": (b"\x1f\x8b",),
}
TEXT_EXT = {".txt", ".csv", ".md", ".py", ".json", ".xml", ".html", ".htm", ".js", ".css", ".log", ".ini", ".cfg", ".java", ".c", ".cpp", ".h"}
ANY_MAGIC = tuple({m for ms in MAGIC.values() for m in ms}) + (b"ID3", b"OggS", b"RIFF", b"MZ")
EVAL_MAX = 5000                      # 한 번 판단할 때 살펴보는 최근 사건 수 상한 (파일 수만 개를 한꺼번에 다룰 때도 판단 비용이 일정하게)


def entropy(data: bytes) -> float:
    """바이트 분포의 섀넌 엔트로피 (0~8). 무작위(암호화된) 데이터는 8에 가깝다."""
    if not data:
        return 0.0
    n = len(data)
    return -sum(c / n * math.log2(c / n) for c in collections.Counter(data).values())


def looks_corrupt(ext: str, head: bytes) -> bool:
    """이 확장자의 파일 앞부분(head)이 '암호화되거나 깨진 것처럼' 보이는가."""
    if len(head) < 64:
        return False
    ext = ext.lower()
    if ext in MAGIC:
        if any(head.startswith(m) for m in MAGIC[ext]):
            return False
        return True                                          # 머리글이 원래 형식과 다름
    if ext in (".mp4", ".mov", ".m4a"):
        return head[4:8] != b"ftyp" and entropy(head) > 7.2
    e = entropy(head)
    if ext in TEXT_EXT:
        return e > 6.6
    return e > 7.6 and not head.startswith(ANY_MAGIC)


def default_read_head(path, n=4096):
    try:
        with open(path, "rb") as f:
            return f.read(n)
    except OSError:
        return None


class Canaries:
    """미끼 파일: 폴더마다 숨김 속성의 가짜 문서를 맨 앞·맨 뒤 이름으로 하나씩 둔다 (알파벳 순으로 걷는 랜섬웨어가 가장 먼저/마지막에 건드린다)."""
    NAMES = ("!_고양이미끼_회의록.docx", "~_고양이미끼_견적서.docx")

    def __init__(self, state_path=None):
        self.state_path = Path(state_path) if state_path else None
        self.files = {}                                     # 소문자 경로 → (원래 경로, sha256)
        self._load()

    def _load(self):
        if not self.state_path:
            return
        try:
            import json
            for p, h in json.loads(self.state_path.read_text(encoding="utf-8")).items():
                self.files[p.lower()] = (p, h)
        except (OSError, ValueError):
            pass

    def _save(self):
        if not self.state_path:
            return
        try:
            import json
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.state_path.with_suffix(".tmp")
            tmp.write_text(json.dumps({p: h for p, h in self.files.values()}, ensure_ascii=False), encoding="utf-8")
            os.replace(tmp, self.state_path)
        except OSError:
            pass

    @staticmethod
    def _docx_bytes(seed: str) -> bytes:
        """아주 작은 진짜 .docx (열면 열린다). 내용은 폴더마다 다르게 해서 해시가 같지 않게 한다."""
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("[Content_Types].xml", '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                       '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                       '<Default Extension="xml" ContentType="application/xml"/>'
                       '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>')
            z.writestr("_rels/.rels", '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                       '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>')
            z.writestr("word/document.xml", '<?xml version="1.0" encoding="UTF-8"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>'
                       "<w:p><w:r><w:t>회의록 초안 (%s)</w:t></w:r></w:p><w:p><w:r><w:t>고양이 경비원이 둔 미끼 문서입니다. 지우거나 고치지 마세요.</w:t></w:r></w:p>"
                       "</w:body></w:document>" % hashlib.sha1(seed.encode("utf-8")).hexdigest()[:12])
        return buf.getvalue()

    @staticmethod
    def _hide(path):
        try:
            ctypes.windll.kernel32.SetFileAttributesW(str(path), 0x2)       # FILE_ATTRIBUTE_HIDDEN
        except Exception:
            pass

    def ensure(self, folders):
        """폴더마다 미끼를 만든다(이미 있으면 그대로). 만든 목록을 돌려준다."""
        made = []
        adopted = False
        for folder in folders:
            d = Path(folder)
            if not d.is_dir():
                continue
            for name in self.NAMES:
                p = d / name
                key = str(p).lower()
                if p.exists() and key in self.files:
                    continue
                if p.exists() and self._adopt(p, key):                       # 기록이 없어도(데이터 폴더를 따로 쓰는 다른 실행·기록 삭제) 멀쩡한 미끼 문서는 새로 쓰지 않고 그대로 이어받는다
                    adopted = True
                    continue
                try:
                    data = self._docx_bytes(str(p))
                    if p.exists():                                  # 상태 기록이 사라진 뒤 다시 만들 때: 숨김·읽기 전용 속성을 풀어야 덮어쓸 수 있다
                        ctypes.windll.kernel32.SetFileAttributesW(str(p), 0x80)
                    p.write_bytes(data)
                    self._hide(p)
                except OSError:
                    continue
                self.files[key] = (str(p), hashlib.sha256(data).hexdigest())
                made.append(str(p))
        if made or adopted:
            self._save()
        return made

    def _adopt(self, p, key):
        """이미 있는 파일이 우리가 만든 것 같은 멀쩡한 .docx(zip) 이면 현재 내용을 기준으로 기록한다. 아니면(암호화돼 깨졌거나 다른 파일) False → 새로 쓴다."""
        try:
            data = Path(p).read_bytes()
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                ok = "word/document.xml" in z.namelist() and "미끼 문서" in z.read("word/document.xml").decode("utf-8", "replace")
        except (OSError, zipfile.BadZipFile, KeyError):
            return False
        if not ok:
            return False
        self.files[key] = (str(p), hashlib.sha256(data).hexdigest())
        return True

    def tampered(self):
        """지금 상태가 만든 때와 다른 미끼들 [(경로, 이유)] — 프로그램을 켤 때 점검한다 (꺼져 있는 동안 일어난 일)."""
        bad = []
        for key, (p, h) in self.files.items():
            if not Path(p).exists():
                bad.append((p, "없어졌어요"))
            else:
                try:
                    if hashlib.sha256(Path(p).read_bytes()).hexdigest() != h:
                        bad.append((p, "내용이 바뀌었어요"))
                except OSError:
                    pass
        return bad

    def hit(self, kind, src, dst=None):
        """이 사건이 미끼를 건드린 것이면 이유 문장, 아니면 None."""
        ent = self.files.get(str(src).lower())
        if not ent or kind == "created":
            return None
        if kind == "deleted":
            return "미끼 파일이 지워졌어요"
        if kind == "moved":
            return "미끼 파일의 이름이 바뀌었어요"
        try:
            ok = hashlib.sha256(Path(ent[0]).read_bytes()).hexdigest() == ent[1]
        except OSError:
            return "미끼 파일을 읽을 수 없어요"
        return None if ok else "미끼 파일의 내용이 바뀌었어요"      # 내용이 그대로면(속성만 바뀐 것 등) 무시

    def remove_all(self):
        """우리가 만든 미끼 파일만 지운다."""
        n = 0
        for key, (p, h) in list(self.files.items()):
            try:
                os.chmod(p, 0o666)
                Path(p).unlink()
                n += 1
            except OSError:
                pass
        self.files = {}
        self._save()
        return n


class RansomDetector:
    def __init__(self, sensitivity="normal", read_head=default_read_head, now_fn=time.time, canaries=None, ignore_roots=(), roots=()):
        cfg = SENSITIVITY.get(sensitivity, SENSITIVITY["normal"])
        self.files_needed, self.dirs_needed, self.window = cfg["files"], cfg["dirs"], cfg["window"]
        self.read_head, self.now_fn, self.canaries = read_head, now_fn, canaries
        self.ignore_roots = tuple(str(Path(r)).lower() for r in ignore_roots if r)
        self.roots = tuple(str(Path(r)).lower().rstrip("\\") for r in roots if r)       # 감시 폴더: 이 아래쪽 경로만 보고 무시할지 정한다
        self.events = collections.deque()                  # (t, kind, src, dst, 폴더, 확장자, 몸값 안내 파일인가) — 판단 때 다시 계산하지 않게 미리 넣어 둔다
        self.created = {}                                  # 경로 → 만든 시각 (새로 만든 파일의 쓰기는 '기존 파일 변경'이 아니다)
        self._dir_ign = {}                                 # 폴더 → 무시할 폴더인가 (같은 폴더의 사건이 쏟아질 때 다시 따지지 않는다)
        self.cooldown_until = 0.0
        self.canary_cooldown_until = 0.0

    # --- 센 대상인가 ----------------------------------------------------
    def ignored(self, path):
        low = str(path).lower().replace("/", "\\")
        i = low.rfind("\\")
        d, name = (low[:i], low[i + 1:]) if i >= 0 else ("", low)
        v = self._dir_ign.get(d)
        if v is None:
            v = self._dir_ignored(d)
            if len(self._dir_ign) > 4000:
                self._dir_ign.clear()
            self._dir_ign[d] = v
        if v or name in IGNORE_PARTS:
            return True
        if name.startswith("~$") or name.startswith(".~lock"):
            return True
        return os.path.splitext(name)[1] in IGNORE_EXT

    def _dir_ignored(self, d):
        """이 폴더 안의 사건은 세지 않는가 (이 프로그램 폴더, .git·node_modules·캐시·임시 폴더 등)."""
        if any(d.startswith(r) for r in self.ignore_roots):
            return True
        rel = d
        for r in self.roots:
            if d == r or d.startswith(r + "\\"):
                rel = d[len(r) + 1:]                           # 감시 폴더 자체가 AppData 같은 곳 아래에 있어도 그 아래쪽만 본다
                break
        return bool(rel and set(rel.split("\\")) & IGNORE_PARTS)

    # --- 사건 넣기 ------------------------------------------------------
    def feed(self, kind, src, dst=None, t=None):
        """파일 사건 하나를 넣는다. 미끼를 건드린 것이면 바로 경보를 돌려준다."""
        now = t if t is not None else self.now_fn()
        if self.canaries is not None and now >= self.canary_cooldown_until:
            why = self.canaries.hit(kind, src, dst)
            if why:
                self.canary_cooldown_until = now + 60.0
                return {"kind": "ransom", "level": "danger", "source": "canary", "reason": why, "path": str(src),
                        "files": 1, "dirs": 1, "reasons": [why + " (사람이 건드릴 일이 없는 숨김 미끼 문서예요)"], "samples": [os.path.basename(str(src))]}
        if self.ignored(src) and (dst is None or self.ignored(dst)):
            return None
        s = str(src)
        sd, name = os.path.split(s)                         # 폴더·확장자·몸값 안내 파일 여부는 여기서 한 번만 계산한다
        ext = os.path.splitext(name)[1].lower()
        note = kind == "created" and ext in NOTE_EXT and NOTE_RE.search(name) is not None
        self.events.append((now, kind, s, str(dst) if dst else None, sd, ext, note))
        if kind == "created":
            self.created[str(src)] = now
            if len(self.created) > 20000:
                self.created = dict(list(self.created.items())[-10000:])
        while len(self.events) > 30000:
            self.events.popleft()
        return None

    # --- 판단 -----------------------------------------------------------
    def evaluate(self, now=None):
        now = now if now is not None else self.now_fn()
        while self.events and now - self.events[0][0] > self.window * 3:
            self.events.popleft()
        if now < self.cooldown_until or not self.events:
            return None
        cutoff = now - self.window
        changed, dirs, created, deleted, renames, note_dirs = {}, set(), {}, set(), [], set()     # changed·created: 경로 → 확장자
        seen_n = 0
        made_at = self.created.get
        for t, k, s, d, sd, ext, note in reversed(self.events):
            if t < cutoff:
                break
            seen_n += 1
            if seen_n > EVAL_MAX:                              # 최근 사건만 봐도 충분하다 (문턱은 수십 개)
                break
            if k == "created":
                created[s] = ext
                dirs.add(sd)
                if note:
                    note_dirs.add(sd)
            elif k == "modified":
                if s not in created and made_at(s, 0.0) < t - 30.0:
                    changed[s] = ext
                    dirs.add(sd)
            elif k == "deleted":
                if s not in created and made_at(s, 0.0) < t - 30.0:
                    deleted.add(s)
                    changed[s] = ext
                    dirs.add(sd)
            elif k == "moved":
                renames.append((s, d))
                changed[s] = ext
                dirs.add(sd)
        big = len(changed) >= self.files_needed and len(dirs) >= self.dirs_needed
        mid = len(changed) >= self.files_needed // 2 and len(dirs) >= self.dirs_needed        # 몸값 안내 파일 단서가 있을 때는 문턱을 절반으로
        if not mid:
            return None
        reasons, flags = [], 0
        # 가) 낯선 확장자 하나로 한꺼번에 바뀜
        new_ext = collections.Counter()
        for s, d in renames:
            e1, e2 = os.path.splitext(s)[1].lower(), os.path.splitext(d or "")[1].lower()
            if e2 and e2 != e1:
                new_ext[e2] += 1
        if len(deleted) >= 5:                                  # 원본을 지우고 암호화한 새 파일을 만드는 방식
            for e in created.values():
                if e:
                    new_ext[e] += 1
        top_ext, top_n = (new_ext.most_common(1)[0] if new_ext else ("", 0))
        total_new = sum(new_ext.values())
        ext_flag = big and bool(top_ext) and top_ext not in COMMON_EXT and top_n >= max(8, self.files_needed // 3) and top_n / max(1, total_new) >= 0.6
        if ext_flag:
            flags += 1
            reasons.append("파일 %d개의 이름이 한꺼번에 낯선 확장자 '%s'로 바뀌었어요" % (top_n, top_ext))
        # 나) 바뀐 파일의 앞부분이 암호화된 것처럼 보임
        rn = [(s_, d_) for s_, d_ in renames if d_]
        ch = [p for p in changed if p not in deleted]
        n_all = len(rn) + len(ch)
        step = max(1, n_all // 8)
        sample = []                                            # 고르게 8개만 뽑아서 앞부분을 읽어 본다
        for i in range(0, n_all, step):
            if len(sample) >= 8:
                break
            if i < len(rn):
                s_, d_ = rn[i]
                e_dst, e_src = os.path.splitext(d_)[1].lower(), os.path.splitext(s_)[1]
                sample.append((d_, e_dst if e_dst in COMMON_EXT else e_src))   # 흔한 확장자로 바꾼 건 형식 변환(예: png→jpg)일 수 있어 새 확장자 기준으로 본다
            else:
                p = ch[i - len(rn)]
                sample.append((p, changed[p]))
        bad = tot = 0
        for path, orig_ext in sample:
            head = self.read_head(path)
            if head is None:
                continue
            tot += 1
            bad += 1 if looks_corrupt(orig_ext, head) else 0
        ent_flag = big and tot >= 4 and bad / tot >= 0.6
        if ent_flag:
            flags += 1
            reasons.append("바뀐 파일 %d개 중 %d개가 암호화된 것처럼 보여요(원래 형식이 깨졌어요)" % (tot, bad))
        # 다) 몸값 안내 파일
        note_flag = len(note_dirs) >= 3
        if note_flag:
            reasons.append("'복구 안내'처럼 보이는 파일이 %d개 폴더에 생겼어요" % len(note_dirs))
        if not (flags or (note_flag and len(changed) >= self.files_needed // 2)):
            return None
        self.cooldown_until = now + 120.0
        names = [os.path.basename(p) for p, _ in sample][:5]
        return {"kind": "ransom", "level": "danger", "source": "behavior", "files": len(changed), "dirs": len(dirs), "seconds": int(self.window),
                "top_ext": top_ext, "reasons": reasons, "samples": names, "note_dirs": len(note_dirs)}


def advice_text() -> str:
    return ("지금 해야 할 일: ① 인터넷(와이파이·랜선)을 바로 끊고 ② 의심 프로그램을 끝내거나 컴퓨터를 종료하세요(켜 둘수록 더 많이 암호화돼요). "
            "③ 몸값은 내지 말고 백신(알약)과 전문가에게 알리고, ④ 백업(외장 디스크·클라우드)이 있으면 연결하지 마세요.")


def build_alert(raw: dict, suspects):
    """감지 결과(raw)와 의심 프로그램 후보를 사건 한 건(SecEvents.add 인자)으로 만든다."""
    if raw["source"] == "canary":
        title = "쥐 발견! 미끼 파일이 건드려졌어요"
        lead = "랜섬웨어가 문서를 암호화하기 시작했을 수 있어요."
    else:
        title = "쥐 발견! 랜섬웨어가 의심돼요"
        lead = "%d초 사이에 파일 %d개가 폴더 %d곳에서 바뀌었어요." % (raw.get("seconds", 10), raw["files"], raw["dirs"])
    text = lead + "\n" + "\n".join("· " + r for r in raw["reasons"])
    if suspects:
        text += "\n\n디스크에 가장 많이 쓰고 있는 프로그램(의심 후보, 확정 아님):\n" + "\n".join(
            "· %s (%.1f MB/초)  %s" % (s["name"], s["mb_s"], s["path"]) for s in suspects)
    text += "\n\n" + advice_text()
    data = {"source": raw["source"], "files": raw["files"], "dirs": raw["dirs"], "samples": raw["samples"], "suspects": suspects, "reasons": raw["reasons"]}
    return {"kind": "ransom", "level": "danger", "title": title, "text": text, "data": data}


class RansomWatcher:
    """sec_watch 로 폴더를 지켜보며 감지기를 돌린다. 경보는 events(SecEvents)에 기록한다."""

    def __init__(self, events, folders, sensitivity="normal", canary_state=None, use_canary=True, ignore_roots=(), skip_pids=(), canary_folders=None):
        self.events = events
        self.folders = [str(Path(f)) for f in folders if Path(f).is_dir()]                  # 슬래시(C:/…)로 적힌 폴더도 윈도우 형식(C:\…)으로 통일 (미끼 경로 비교가 어긋나지 않게)
        self.canary_folders = [str(Path(f)) for f in (self.folders if canary_folders is None else canary_folders) if Path(f).is_dir()]
        self.canaries = Canaries(canary_state) if use_canary else None
        self.detector = RansomDetector(sensitivity, canaries=self.canaries, ignore_roots=ignore_roots, roots=self.folders)
        self.skip_pids = tuple(skip_pids) + (os.getpid(),)
        self.watchers = []
        self._stop = threading.Event()
        self._thread = None
        self._last_eval = 0.0
        self._last_overflow_check = 0.0
        self._lock = threading.Lock()                     # 감시 스레드(폴더마다 하나)와 1초 점검 스레드가 감지기를 함께 쓰므로 한 번에 하나씩만
        self.count = 0
        self.overflows = 0

    # --- 시작/끝 ---------------------------------------------------------
    def start(self):
        if self.canaries is not None:
            self.canaries.ensure(self.canary_folders)
            for p, why in self.canaries.tampered():                       # 꺼져 있는 동안 미끼가 건드려졌다면
                raw = {"kind": "ransom", "level": "danger", "source": "canary", "reason": "프로그램이 꺼져 있는 동안 미끼 파일이 %s" % why, "path": p,
                       "files": 1, "dirs": 1, "reasons": ["프로그램이 꺼져 있는 동안 미끼 파일이 %s" % why], "samples": [os.path.basename(p)]}
                self._raise(raw)
                self.canaries.files.pop(p.lower(), None)
            self.canaries.ensure(self.canary_folders)
        import sec_watch
        self.watchers = [sec_watch.DirWatcher(f, self._on, recursive=True, on_overflow=self._on_overflow).start() for f in self.folders]
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        for w in self.watchers:
            w.stop()
        self.watchers = []

    # --- 사건 처리 --------------------------------------------------------
    def _on_overflow(self):
        """사건이 너무 많아 윈도우가 일부를 버렸다: 버려진 사건 속에 미끼가 있었을 수 있으니 미끼 파일을 직접 확인한다 (1초에 한 번까지)."""
        self.overflows += 1
        now = time.time()
        if self.canaries is None or now - self._last_overflow_check < 1.0 or now < self.detector.canary_cooldown_until:
            return
        self._last_overflow_check = now
        with self._lock:
            bad = self.canaries.tampered()
            if bad:
                self.detector.canary_cooldown_until = now + 60.0
        if bad:
            p, why = bad[0]
            reason = "미끼 파일이 %s" % why
            self._raise({"kind": "ransom", "level": "danger", "source": "canary", "reason": reason, "path": p, "files": 1, "dirs": 1,
                         "reasons": [reason + " (사람이 건드릴 일이 없는 숨김 미끼 문서예요)"], "samples": [os.path.basename(p)]})

    def _on(self, kind, src, dst=None):
        self.count += 1
        try:
            if "/" in src or (dst and "/" in dst):               # 폴더 감시는 이미 윈도우 형식으로 준다 (다른 곳에서 부를 때만 정리)
                src = os.path.normpath(src)
                dst = os.path.normpath(dst) if dst else dst
            with self._lock:
                raw = self.detector.feed(kind, src, dst)
                if raw is None:
                    now = time.time()
                    if now - self._last_eval >= 0.25:                # 사건이 쏟아질 때도 0.25초 안에 판단 (점검 주기를 기다리지 않는다)
                        self._last_eval = now
                        raw = self.detector.evaluate()
        except Exception:
            return
        if raw:
            self._raise(raw)

    def _loop(self):
        while not self._stop.wait(1.0):
            try:
                with self._lock:
                    raw = self.detector.evaluate()
            except Exception:
                raw = None
            if raw:
                self._raise(raw)

    def _raise(self, raw):
        """경보는 바로 기록하고(화면이 곧장 알리도록), 의심 프로그램 후보는 재는 데 1.5초쯤 걸리므로 따로 재서 나중에 덧붙인다."""
        alert = build_alert(raw, [])
        ev = self.events.add(alert["kind"], alert["level"], alert["title"], alert["text"], alert["data"], key="ransom", cooldown=30.0)
        if ev is None:
            return

        def work():
            try:
                from sec_common import top_writers
                suspects = top_writers(1.5, 3, self.skip_pids)
            except Exception:
                suspects = []
            full = build_alert(raw, suspects)
            self.events.update(ev["id"], text=full["text"], data={"suspects": suspects})
        threading.Thread(target=work, daemon=True).start()
