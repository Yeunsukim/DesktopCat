"""카메라·마이크 사용 알림 (스파이웨어 단서).

윈도우는 어떤 프로그램이 카메라·마이크를 언제 썼는지 레지스트리에 적어 둔다:
  HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\CapabilityAccessManager\\ConsentStore\\(webcam|microphone)\\(NonPackaged\\<경로>|<스토어 앱 이름>)
  LastUsedTimeStart(켠 시각) > LastUsedTimeStop(끈 시각, 쓰는 중이면 0) 이면 '지금 쓰는 중'이다.
이 정보로 '지금 카메라·마이크를 쓰고 있는 프로그램'을 알아내고, **처음 보는 프로그램**이 쓰면 알린다 (읽기만 하고, 관리자 권한이 필요 없다).

 · 널리 쓰는 화상회의·브라우저·메신저는 처음부터 믿는다(KNOWN_OK). 그 밖의 프로그램은 처음 쓰는 것을 알리고, 허용하면 다시 알리지 않는다.
 · 켠 지 처음 하루(LEARN_SECONDS)는 '배우는 기간': 쓰는 프로그램을 알림 없이 기억만 한다 (평소 쓰던 프로그램으로 본다).
 · 알림은 한 프로그램당 한 번이고, 사용 기록은 이 PC 안에서만 쓴다.
"""
import datetime as dt
import json
import os
import time
import winreg
from pathlib import Path

CAPS = {"webcam": "카메라", "microphone": "마이크"}
BASE = r"Software\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore"
LEARN_SECONDS = 24 * 3600
KNOWN_OK = {"chrome.exe", "msedge.exe", "firefox.exe", "brave.exe", "whale.exe", "opera.exe", "teams.exe", "ms-teams.exe", "zoom.exe", "slack.exe",
            "discord.exe", "skype.exe", "kakaotalk.exe", "webex.exe", "webexmta.exe", "obs64.exe", "obs32.exe", "line.exe", "telegram.exe",
            "windowscamera", "microsoft.windowscamera", "microsoft.windows.soundrecorder", "audiodg.exe", "searchhost.exe"}
EPOCH_DIFF = 116444736000000000


def _filetime(v):
    try:
        v = int(v)
    except (TypeError, ValueError):
        return 0.0
    return (v - EPOCH_DIFF) / 1e7 if v > 0 else 0.0


def _app_name(subkey: str, packaged: bool):
    """(표시 이름, 실행 파일 경로 또는 '')"""
    if packaged:
        return subkey.split("_")[0], ""
    path = subkey.replace("#", "\\")
    return Path(path).name or path, path


def read_usage():
    """[{cap, name, path, key, start, stop, in_use}] — 카메라·마이크를 쓴 적 있는 프로그램 전부 (레지스트리 읽기만)."""
    rows = []
    for cap in CAPS:
        base = "%s\\%s" % (BASE, cap)
        for packaged, sub in ((False, base + "\\NonPackaged"), (True, base)):
            try:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, sub) as k:
                    i = 0
                    while True:
                        try:
                            name = winreg.EnumKey(k, i)
                        except OSError:
                            break
                        i += 1
                        if not packaged and False:
                            continue
                        if packaged and name == "NonPackaged":
                            continue
                        try:
                            with winreg.OpenKey(k, name) as sk:
                                start = _filetime(winreg.QueryValueEx(sk, "LastUsedTimeStart")[0])
                                stop = _filetime(winreg.QueryValueEx(sk, "LastUsedTimeStop")[0])
                        except OSError:
                            continue
                        disp, path = _app_name(name, packaged)
                        rows.append({"cap": cap, "name": disp, "path": path, "key": ("%s|%s" % (cap, name)).lower(), "start": start, "stop": stop,
                                     "in_use": start > 0 and start > stop})
            except OSError:
                continue
    return rows


def check_usage(rows, state, allow=(), now=None, learn_seconds=LEARN_SECONDS):
    """지금 쓰는 중인 프로그램을 보고 알릴 것을 정한다. (사건 목록, 새 상태). state: {"first": 처음 본 시각, "known": {앱 키: 시각}}.
    사건: {kind, level, title, text, data, key}. 시험에서는 rows 와 now 를 직접 넣는다."""
    now = now if now is not None else time.time()
    state = dict(state or {})
    state.setdefault("first", now)
    known = dict(state.get("known", {}))
    learning = now - state["first"] < learn_seconds
    allow_l = {a.lower() for a in allow}
    events = []
    for r in rows:
        if not r["in_use"]:
            continue
        low_name = r["name"].lower()
        if low_name in KNOWN_OK or low_name in allow_l or r["key"] in allow_l:
            continue
        if r["key"] in known:
            continue
        known[r["key"]] = now
        if learning:                                         # 배우는 기간: 알리지 않고 평소 프로그램으로 기억한다
            continue
        what = CAPS[r["cap"]]
        text = ("‘%s’ 프로그램이 지금 %s를 쓰고 있어요.\n처음 보는 프로그램이에요. 내가 시작한 게 맞으면 ‘허용 목록에 추가’를 누르세요.\n"
                "모르는 프로그램이면 스파이웨어일 수 있으니 의심해 보세요.%s") % (r["name"], what, ("\n\n실행 파일: " + r["path"]) if r["path"] else "")
        events.append({"kind": "privacy", "level": "warn", "title": "처음 보는 프로그램이 %s를 쓰고 있어요" % what, "text": text,
                       "data": {"app": r["key"], "name": r["name"], "path": r["path"], "cap": r["cap"]}, "key": "privacy:" + r["key"]})
    state["known"] = known
    return events, state


def running_suspects(path: str):
    """이 실행 파일로 지금 돌고 있는 프로세스들 → 경보 창의 '종료…' 버튼용 [{pid, name, path}]."""
    import sec_common
    out = []
    if not path:
        return out
    for pid in sec_common.list_pids():
        p = sec_common.exe_path(pid)
        if p and p.lower() == path.lower():
            out.append({"pid": pid, "name": Path(p).name, "path": p})
    return out[:3]


def load_state(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_state(path, state):
    try:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, p)
    except OSError:
        pass
