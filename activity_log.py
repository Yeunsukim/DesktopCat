"""하루 활동 기록: 어떤 프로그램을 얼마나 썼는지(+ 창 제목)를 날짜별 파일로 이 컴퓨터에만 저장한다.

 · 기록하는 것은 '프로그램 이름 + 창 제목 + 쓴 시간(초)'뿐이다. 키보드로 친 내용·화면 내용은 절대 기록하지 않는다.
 · 5초마다 맨 앞 창을 한 번 본다 (일은 아주 가볍다). 5분 넘게 입력이 없거나 화면이 잠겨 있으면 시간을 세지 않는다.
 · 시크릿 창·암호 관리자·은행 관련 창, 사용자가 정한 단어가 들어간 창은 '(제외됨)'으로만 기록한다.
 · 파일: 데이터폴더\\activity\\YYYY-MM-DD.json = {프로그램: {창 제목: 초}}. 60초마다 한 번 저장(임시 파일 → 바꿔치기), 30일이 지난 파일은 지운다.
 · 기본은 꺼져 있고, 설정에서 동의하고 켠 뒤에만 기록한다.
"""
import ctypes
import datetime as dt
import json
import os
import re
import time
from pathlib import Path

import win32gui
import win32process

SAMPLE_EVERY = 5.0          # 초: 맨 앞 창을 보는 간격
MAX_STEP = 10.0             # 초: 한 번에 더해 주는 시간의 상한 (컴퓨터가 잠들었다 깬 경우 등에 시간이 부풀지 않게)
IDLE_STOP = 300.0           # 초(5분): 이만큼 입력이 없으면 자리 비움으로 보고 세지 않는다
SAVE_EVERY = 60.0
KEEP_DAYS = 30
MAX_TITLES = 300            # 한 프로그램·하루에 따로 적는 제목 수의 상한 (넘으면 '(기타)'로 합친다)
TITLE_MAX = 120
EXCLUDED = "(제외됨)"
WEEKDAY = "월화수목금토일"

EXCLUDE_PROGRAMS = ("keepass", "1password", "bitwarden", "lastpass", "dashlane", "enpass", "nordpass")
EXCLUDE_TITLES = ("inprivate", "incognito", "private browsing", "시크릿", "인프라이빗", "개인 정보 보호 모드", "비밀번호", "password",
                  "은행", "뱅킹", "banking", "bank", "공동인증", "공인인증", "인증서")
_LOCK_PROGRAMS = ("lockapp", "logonui")
_DATE_FILE = re.compile(r"^\d{4}-\d{2}-\d{2}\.json$")


def is_excluded(program: str, title: str, extra=()) -> bool:
    p, t = program.lower(), title.lower()
    if any(k in p for k in EXCLUDE_PROGRAMS):
        return True
    words = EXCLUDE_TITLES + tuple(w.strip().lower() for w in extra if w and w.strip())
    return any(k in t or k in p for k in words)


def fmt_duration(sec: float) -> str:
    sec = int(round(sec))
    if sec < 60:
        return "%d초" % sec
    m = sec // 60
    if m < 60:
        return "%d분" % m
    return "%d시간 %d분" % (m // 60, m % 60) if m % 60 else "%d시간" % (m // 60)


def day_label(day: dt.date, today: dt.date | None = None) -> str:
    today = today or dt.date.today()
    base = "%d월 %d일(%s)" % (day.month, day.day, WEEKDAY[day.weekday()])
    if day == today - dt.timedelta(days=1):
        return "어제 " + base
    if day == today:
        return "오늘 " + base
    return base


def digest_text(day: dt.date, data: dict, max_chars: int = 6000):
    """Gemini 에게 줄 기록 글. (글, 총 초). 기록이 너무 적으면 ("", 총 초)."""
    progs = sorted(((sum(t.values()), p, t) for p, t in data.items()), reverse=True)
    grand = sum(x[0] for x in progs)
    if grand < 120:
        return "", grand
    lines = ["날짜: %s" % day_label(day), "총 활동 시간: %s" % fmt_duration(grand), ""]
    for tot, p, titles in progs[:15]:
        if tot < 60:
            break
        lines.append("[%s] %s" % (p, fmt_duration(tot)))
        for title, s in sorted(titles.items(), key=lambda x: -x[1])[:8]:
            if s < 30:
                break
            lines.append("  - %s: %s" % (fmt_duration(s), title[:80]))
    return "\n".join(lines)[:max_chars], grand


_MD_SPECIAL = re.compile(r"([\\`*_{}\[\]<>#+!|~])")


def raw_markdown(data: dict) -> str:
    """기록 그대로 보기: 프로그램별 시간과 창 제목 목록 (제목 속 Markdown 기호는 무력화)."""
    progs = sorted(((sum(t.values()), p, t) for p, t in data.items()), reverse=True)
    out = []
    for tot, p, titles in progs:
        if tot < 30:
            continue
        out.append("### %s — %s\n" % (_MD_SPECIAL.sub(r"\\\1", p), fmt_duration(tot)))
        for title, s in sorted(titles.items(), key=lambda x: -x[1])[:10]:
            if s >= 20:
                out.append("* %s — %s" % (fmt_duration(s), _MD_SPECIAL.sub(r"\\\1", title[:100])))
        out.append("")
    return "\n".join(out)


# ---------------------------------------------------------------- 맨 앞 창 읽기
_name_cache = {}


def _exe_name(pid: int) -> str:
    if pid in _name_cache:
        return _name_cache[pid]
    name = "알 수 없음"
    try:
        k32 = ctypes.windll.kernel32
        k32.OpenProcess.restype = ctypes.c_void_p
        h = k32.OpenProcess(0x1000, False, pid)                  # PROCESS_QUERY_LIMITED_INFORMATION
        if h:
            buf = ctypes.create_unicode_buffer(520)
            size = ctypes.c_ulong(520)
            if k32.QueryFullProcessImageNameW(ctypes.c_void_p(h), 0, buf, ctypes.byref(size)):
                name = os.path.basename(buf.value)
                name = name[:-4] if name.lower().endswith(".exe") else name
            k32.CloseHandle(ctypes.c_void_p(h))
    except Exception:
        pass
    if len(_name_cache) > 300:
        _name_cache.clear()
    _name_cache[pid] = name
    return name


def screen_locked() -> bool:
    """잠금 화면(보안 데스크톱)이면 입력 데스크톱을 열 수 없다."""
    try:
        u = ctypes.windll.user32
        u.OpenInputDesktop.restype = ctypes.c_void_p
        h = u.OpenInputDesktop(0, False, 0x0100)                 # DESKTOP_SWITCHDESKTOP
        if not h:
            return True
        u.CloseDesktop(ctypes.c_void_p(h))
    except Exception:
        pass
    return False


def foreground():
    """(프로그램 이름, 창 제목, pid) 또는 None (맨 앞 창이 없을 때)."""
    hwnd = win32gui.GetForegroundWindow()
    if not hwnd:
        return None
    _, pid = win32process.GetWindowThreadProcessId(hwnd)
    return _exe_name(pid), win32gui.GetWindowText(hwnd), pid


def idle_seconds() -> float:
    import win32api
    return ((win32api.GetTickCount() - win32api.GetLastInputInfo()) & 0xFFFFFFFF) / 1000.0


# ---------------------------------------------------------------- 기록기
class ActivityLog:
    def __init__(self, folder, settings, read_fg=foreground, read_idle=idle_seconds, is_locked=screen_locked, today=dt.date.today):
        """read_fg / read_idle / is_locked / today 는 시험에서 바꿔 끼울 수 있다."""
        self.dir = Path(folder)
        self.settings = settings
        self.read_fg, self.read_idle, self.is_locked, self.today = read_fg, read_idle, is_locked, today
        self.day = None                    # 지금 모으고 있는 날짜(dt.date)
        self.data = {}
        self.dirty = False
        self._next = 0.0
        self._last = None                  # 직전 표본의 monotonic 시각
        self._next_save = 0.0
        self.own_pid = os.getpid()
        self.error = None                  # 마지막 오류 (한 번만 알리려고)

    # --- 파일 ----------------------------------------------------------
    def _path(self, day) -> Path:
        return self.dir / ("%s.json" % day.isoformat())

    def dates(self):
        """기록이 있는 날짜 목록(오래된 순)."""
        try:
            names = sorted(n[:-5] for n in os.listdir(self.dir) if _DATE_FILE.match(n))
        except OSError:
            return []
        out = []
        for n in names:
            try:
                out.append(dt.date.fromisoformat(n))
            except ValueError:
                pass
        return out

    def load(self, day) -> dict:
        """그 날의 기록 {프로그램: {제목: 초}}. 오늘 것은 아직 저장 안 된 최신 값까지 포함한다."""
        if self.day == day:
            for _ in range(3):                      # 화면 스레드가 동시에 고치는 중이면 잠깐 뒤 다시
                try:
                    return {p: dict(t) for p, t in self.data.items()}
                except RuntimeError:
                    continue
            return {}
        return self.load_file_only(day)

    def flush(self):
        if not (self.dirty and self.day):
            return
        try:
            self.dir.mkdir(parents=True, exist_ok=True)
            path = self._path(self.day)
            tmp = path.with_suffix(".json.tmp")
            tmp.write_text(json.dumps({p: {t: round(s) for t, s in titles.items()} for p, titles in self.data.items()},
                                      ensure_ascii=False), encoding="utf-8")
            os.replace(tmp, path)
            self.dirty = False
        except OSError:
            pass

    def purge_old(self):
        limit = self.today() - dt.timedelta(days=KEEP_DAYS)
        for d in self.dates():
            if d < limit:
                try:
                    self._path(d).unlink()
                except OSError:
                    pass

    def clear_all(self):
        """저장된 기록을 모두 지운다 (설정 창의 '기록 모두 지우기')."""
        for d in self.dates():
            try:
                self._path(d).unlink()
            except OSError:
                pass
        self.data, self.dirty = {}, False

    # --- 표본 ----------------------------------------------------------
    def _switch_day(self, today):
        self.flush()
        self.day = today
        self.data = self.load_file_only(today)
        self.dirty = False
        self.purge_old()

    def load_file_only(self, day) -> dict:
        try:
            raw = json.loads(self._path(day).read_text(encoding="utf-8"))
            return {str(p): {str(t): float(s) for t, s in titles.items()} for p, titles in raw.items()}
        except (OSError, ValueError, AttributeError):
            return {}

    def tick(self, mono: float):
        """프레임마다 부른다. 5초에 한 번만 실제로 본다. 설정에서 꺼져 있으면 아무것도 안 한다."""
        if mono < self._next:
            return
        self._next = mono + SAMPLE_EVERY
        act = self.settings.data.get("activity", {})
        if not (act.get("enabled") and act.get("consented")):
            self._last = None
            self.flush()
            return
        try:
            self._sample(mono, act)
            self.error = None
        except Exception as e:                                   # 기록 때문에 고양이가 멈추면 안 된다
            self.error = "%s: %s" % (e.__class__.__name__, e)
        if mono >= self._next_save:
            self._next_save = mono + SAVE_EVERY
            self.flush()

    def _sample(self, mono, act):
        today = self.today()
        if self.day != today:
            self._switch_day(today)
        last, self._last = self._last, mono
        if self.read_idle() >= IDLE_STOP or self.is_locked():
            return
        fg = self.read_fg()
        if not fg or fg[2] == self.own_pid or fg[0].lower() in _LOCK_PROGRAMS:
            return
        step = min(MAX_STEP, mono - last) if last is not None else SAMPLE_EVERY
        prog, title = fg[0], re.sub(r"\s+", " ", fg[1]).strip()[:TITLE_MAX] or "(제목 없음)"
        if is_excluded(prog, title, act.get("exclude", ())):
            prog, title = EXCLUDED, EXCLUDED
        titles = self.data.setdefault(prog, {})
        if title not in titles and len(titles) >= MAX_TITLES:
            title = "(기타)"
        titles[title] = titles.get(title, 0.0) + step
        self.dirty = True
