"""자동 시작·실행 중 프로그램 점검 (스파이웨어·악성코드의 흔적 찾기).

보조 프로세스(nethelper)에서 몇 분마다 한 번 돌고 끝나서, 고양이 본체의 메모리·CPU 를 쓰지 않는다. 일반 사용자 권한으로 읽기만 한다.

 1) 자동 시작 목록을 모은다: 레지스트리 Run/RunOnce, 시작 폴더, 윈도우 로그인 설정(Winlogon Shell/Userinit), IFEO 디버거 가로채기,
    예약 작업(\\Microsoft 밖), 자동 시작 서비스(윈도우 폴더 밖).
    처음 돌 때는 '기준 목록'으로 저장만 하고(지금 있는 것은 평소 쓰던 것으로 본다), 그 뒤에 **새로 생긴 것**만 알린다.
 2) 실행 중 프로그램을 점수로 본다: 임시·휴지통·AppData\\Roaming·Public·ProgramData 에서 실행 중, 서명 없음, 시스템 프로세스 이름 흉내,
    이중 확장자(문서처럼 보이는 exe) 등. 유효한 디지털 서명이 있으면 거의 알리지 않는다.
 3) 같은 일을 되풀이해서 알리지 않는다: 알린 것은 7일 동안 다시 알리지 않고, 허용 목록에 있으면 알리지 않는다.
결과는 'findings'(사건 목록)로 돌려주고, 사건 기록은 본체가 한다. 상태 파일(기준 목록 등)은 데이터폴더\\security 에 둔다.
"""
import hashlib
import json
import os
import re
import subprocess
import time
import winreg
from pathlib import Path

import sec_common
import sec_sig

CREATE_NO_WINDOW = 0x08000000
SEEN_DAYS = 7
TASKS_REFRESH = 6 * 3600              # 초: 예약 작업·서비스 목록이 그대로여도 이만큼 지나면 PowerShell 로 새로 읽는다
TASKS_KEY = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Schedule\TaskCache\Tasks"
SERVICES_KEY = r"SYSTEM\CurrentControlSet\Services"
RUN_KEYS = [
    (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", "HKCU Run"),
    (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\RunOnce", "HKCU RunOnce"),
    (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Run", "HKLM Run"),
    (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\RunOnce", "HKLM RunOnce"),
    (winreg.HKEY_LOCAL_MACHINE, r"Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Run", "HKLM Run(32비트)"),
]
SYSTEM_NAMES = {"svchost.exe", "explorer.exe", "lsass.exe", "csrss.exe", "winlogon.exe", "services.exe", "smss.exe", "taskhost.exe", "taskhostw.exe",
                "conhost.exe", "dwm.exe", "spoolsv.exe", "wininit.exe", "rundll32.exe", "dllhost.exe", "searchindexer.exe"}
DOUBLE_EXT = re.compile(r"\.(pdf|docx?|xlsx?|pptx?|jpe?g|png|gif|txt|hwp)\.(exe|scr|com|bat|cmd|pif|js|vbs)$", re.I)
GOOD_STATUS = {"valid"}
BAD_STATUS = {"hashmismatch"}


# ---------------------------------------------------------------- 순수 판단 (시험하기 쉽게 분리)
def parse_command_path(cmd: str) -> str:
    """명령줄에서 실행 파일 경로만 뽑는다: '"C:\\a b\\x.exe" /s' → C:\\a b\\x.exe ,  C:\\x.exe /s → C:\\x.exe"""
    cmd = os.path.expandvars((cmd or "").strip())
    if not cmd:
        return ""
    if cmd.startswith('"'):
        end = cmd.find('"', 1)
        return cmd[1:end] if end > 0 else cmd[1:]
    m = re.match(r"^(.+?\.(?:exe|bat|cmd|com|scr|vbs|js|ps1|lnk|msc|cpl))(?:\s|$)", cmd, re.I)
    return m.group(1) if m else cmd.split(" ")[0]


def autorun_id(kind: str, name: str, command: str) -> str:
    return ("%s|%s|%s" % (kind, name, command)).lower()


def location_score(path: str):
    """실행 위치의 수상도 (점수, 설명)."""
    low = str(path).lower()
    if "\\appdata\\local\\temp\\" in low or "\\windows\\temp\\" in low or "\\$recycle.bin\\" in low:
        return 4, "임시 폴더·휴지통에서 실행 중"
    if "\\users\\public\\" in low or ("\\programdata\\" in low and not sec_common.in_program_files(low)):
        return 3, "공용 폴더(Public·ProgramData)에서 실행 중"
    if "\\appdata\\roaming\\" in low:
        return 3, "AppData\\Roaming 폴더에서 실행 중"
    if "\\downloads\\" in low:
        return 2, "다운로드 폴더에서 실행 중"
    if "\\appdata\\local\\" in low and "\\programs\\" not in low:
        return 1, "AppData\\Local 폴더에서 실행 중"
    return 0, ""


def classify_process(path: str, sig_status: str, age_days=None):
    """실행 중 프로그램의 수상도: (점수, 단계, 이유들) — 알릴 필요가 없으면 단계 None."""
    name = Path(path).name.lower()
    status = (sig_status or "").lower()
    score, reasons = 0, []
    pts, why = location_score(path)
    if pts:
        score += pts
        reasons.append(why)
    if status in BAD_STATUS:
        score += 6
        reasons.append("디지털 서명이 있지만 서명 뒤에 파일이 바뀐 것 같아요")
    elif status == "notsigned":
        score += 2
        reasons.append("디지털 서명이 없어요")
    elif status not in GOOD_STATUS:
        score += 1 if status in ("error", "unknownerror", "nottrusted", "") else 2
        reasons.append("디지털 서명을 확인하지 못했어요")
    if name in SYSTEM_NAMES and not sec_common.is_windows_path(path):
        score += 6
        reasons.append("윈도우 시스템 프로그램('%s')인 척하지만 윈도우 폴더 밖에 있어요" % name)
    if DOUBLE_EXT.search(name):
        score += 5
        reasons.append("문서·사진처럼 보이게 이중 확장자를 쓴 실행 파일이에요")
    if age_days is not None and age_days < 1:
        score += 1
        reasons.append("만들어진 지 하루도 안 됐어요")
    if status in GOOD_STATUS and "윈도우 시스템 프로그램" not in " ".join(reasons) and not DOUBLE_EXT.search(name):
        return score, None, reasons                              # 유효한 서명이 있으면 알리지 않는다
    if score >= 9:
        return score, "danger", reasons
    if score >= 6:
        return score, "warn", reasons
    return score, None, reasons


def classify_autorun(entry: dict, sig_status: str):
    """새로 생긴 자동 시작 항목의 단계: (단계, 이유들). 유효한 서명이 있으면 'info'(기록만)."""
    path = entry.get("path", "")
    status = (sig_status or "").lower()
    reasons = []
    pts, why = location_score(path)
    suspicious = pts >= 3
    if why:
        reasons.append(why)
    if entry["kind"] in ("ifeo", "winlogon"):
        return "danger", ["윈도우 핵심 설정이 바뀌었어요: " + entry["name"]] + reasons
    if status in BAD_STATUS:
        return "danger", reasons + ["서명 뒤에 파일이 바뀐 것 같아요"]
    if status in GOOD_STATUS:
        return "info", reasons
    reasons.append("디지털 서명이 없어요" if status == "notsigned" else "디지털 서명을 확인하지 못했어요")
    if suspicious or entry["kind"] == "startup-exe":
        return "danger", reasons
    return "warn", reasons


# ---------------------------------------------------------------- 자동 시작 목록 모으기
def collect_registry():
    out = []
    for root, sub, label in RUN_KEYS:
        try:
            with winreg.OpenKey(root, sub) as k:
                i = 0
                while True:
                    try:
                        name, val, _t = winreg.EnumValue(k, i)
                    except OSError:
                        break
                    i += 1
                    cmd = str(val)
                    out.append({"kind": "run", "where": label, "name": name, "command": cmd, "path": parse_command_path(cmd)})
        except OSError:
            continue
    try:                                                    # 로그인 설정: 보통 explorer.exe / userinit.exe 이다
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows NT\CurrentVersion\Winlogon") as k:
            for name, normal in (("Shell", "explorer.exe"), ("Userinit", "userinit.exe")):
                try:
                    val = str(winreg.QueryValueEx(k, name)[0])
                except OSError:
                    continue
                if val.strip().lower().rstrip(",") .split("\\")[-1] != normal:
                    out.append({"kind": "winlogon", "where": "Winlogon", "name": name, "command": val, "path": parse_command_path(val)})
    except OSError:
        pass
    try:                                                    # 프로그램 실행을 가로채는 디버거 (IFEO)
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows NT\CurrentVersion\Image File Execution Options") as k:
            i = 0
            while True:
                try:
                    sub = winreg.EnumKey(k, i)
                except OSError:
                    break
                i += 1
                try:
                    with winreg.OpenKey(k, sub) as sk:
                        dbg = str(winreg.QueryValueEx(sk, "Debugger")[0])
                        out.append({"kind": "ifeo", "where": "IFEO", "name": sub, "command": dbg, "path": parse_command_path(dbg)})
                except OSError:
                    pass
    except OSError:
        pass
    return out


def collect_startup_folders():
    out = []
    for base in (os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"),
                 os.path.expandvars(r"%ProgramData%\Microsoft\Windows\Start Menu\Programs\Startup")):
        try:
            for f in os.listdir(base):
                p = os.path.join(base, f)
                if os.path.isfile(p) and f.lower() != "desktop.ini":
                    exe = f.lower().endswith((".exe", ".bat", ".cmd", ".vbs", ".js", ".ps1", ".scr"))
                    out.append({"kind": "startup-exe" if exe else "startup", "where": "시작 폴더", "name": f, "command": p, "path": p})
        except OSError:
            pass
    return out


PS_TASKS = r"""
param($OutFile)
$tasks = @(); $svcs = @()
try { Get-ScheduledTask -ErrorAction Stop | Where-Object { $_.TaskPath -notlike '\Microsoft\*' -and $_.State -ne 'Disabled' } | ForEach-Object {
    $a = $_.Actions | Select-Object -First 1
    $tasks += @{ name = [string]$_.TaskName; where = [string]$_.TaskPath; exec = [string]$a.Execute; args = [string]$a.Arguments } } } catch {}
try { Get-CimInstance Win32_Service -Filter "StartMode='Auto'" -ErrorAction Stop | ForEach-Object {
    $svcs += @{ name = [string]$_.Name; display = [string]$_.DisplayName; path = [string]$_.PathName } } } catch {}
@{ tasks = $tasks; services = $svcs } | ConvertTo-Json -Depth 4 -Compress | Out-File -Encoding UTF8 $OutFile
"""


def _reg_value(key, name):
    try:
        return winreg.QueryValueEx(key, name)[0]
    except OSError:
        return None


def task_service_fingerprint():
    """예약 작업·서비스 목록의 '지문' (0.2초 남짓). 점검에 실제로 쓰는 값만 모은다:
    예약 작업(마이크로소프트 것 제외)은 경로·실행할 명령(Actions), 서비스는 시작 방식(Start)과 자동 시작 서비스의 실행 파일(ImagePath).
    (키의 '마지막 변경 시각'은 작업이 실행될 때마다 바뀌어서 쓰지 않는다.) 작업·서비스가 생기거나 지워지거나 위 값이 바뀌면 달라진다. 읽을 수 없으면 None."""
    h = hashlib.sha1()
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, TASKS_KEY) as k:
            for i in range(winreg.QueryInfoKey(k)[0]):
                guid = winreg.EnumKey(k, i)
                try:
                    with winreg.OpenKey(k, guid) as c:
                        path = _reg_value(c, "Path") or ""
                        if not path.lower().startswith("\\microsoft\\"):
                            h.update(repr((guid, path, _reg_value(c, "Actions"))).encode("utf-8", "replace"))
                except OSError:
                    h.update(repr((guid, "?")).encode("utf-8", "replace"))
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, SERVICES_KEY) as k:
            for i in range(winreg.QueryInfoKey(k)[0]):
                name = winreg.EnumKey(k, i)
                try:
                    with winreg.OpenKey(k, name) as c:
                        start = _reg_value(c, "Start")
                        h.update(repr((name, start, _reg_value(c, "ImagePath") if start == 2 else None)).encode("utf-8", "replace"))
                except OSError:
                    h.update(repr((name, "?")).encode("utf-8", "replace"))
    except OSError:
        return None
    return h.hexdigest()


def collect_tasks_services(work_dir: Path, fingerprint=task_service_fingerprint, now_fn=time.time):
    """예약 작업·자동 시작 서비스. [{kind, where, name, command, path}]
    PowerShell 은 무겁다(CPU 약 3초·메모리 100MB). 그래서 레지스트리 지문이 지난번과 같으면 지난번 결과를 그대로 쓰고,
    바뀌었거나 6시간이 지났을 때만 PowerShell 로 새로 읽는다."""
    work_dir.mkdir(parents=True, exist_ok=True)
    ps, outp, fpf = work_dir / "_tasks.ps1", work_dir / "_tasks_out.json", work_dir / "_tasks_fp.json"
    fp = fingerprint()
    data = None
    if fp:
        old = _load(fpf, {})
        if old.get("fp") == fp and 0 <= now_fn() - float(old.get("ts", 0)) < TASKS_REFRESH and outp.exists():
            try:
                data = json.loads(outp.read_text(encoding="utf-8-sig"))
            except (OSError, ValueError):
                data = None
    if data is None:
        ps.write_text(PS_TASKS, encoding="utf-8")
        if outp.exists():
            outp.unlink()
        try:
            subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", str(ps), "-OutFile", str(outp)],
                           capture_output=True, timeout=120, creationflags=CREATE_NO_WINDOW)
            data = json.loads(outp.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError, subprocess.SubprocessError):
            return []
        if fp:
            _save(fpf, {"fp": fp, "ts": now_fn()})
    out = []
    for t in data.get("tasks") or []:
        exe = (t.get("exec") or "").strip()
        if not exe:
            continue
        cmd = ('"%s" %s' % (exe, t.get("args", ""))).strip() if " " in exe and not exe.startswith('"') else (exe + " " + (t.get("args") or "")).strip()
        path = parse_command_path(exe if exe.startswith('"') else cmd)
        if sec_common.is_windows_path(os.path.expandvars(path)):
            continue
        out.append({"kind": "task", "where": "예약 작업", "name": (t.get("where") or "") + (t.get("name") or ""), "command": cmd, "path": os.path.expandvars(path)})
    for s in data.get("services") or []:
        path = parse_command_path(s.get("path") or "")
        if not path or sec_common.is_windows_path(path) or "\\system32\\" in path.lower():
            continue
        out.append({"kind": "service", "where": "서비스", "name": s.get("name") or "", "command": s.get("path") or "", "path": path})
    return out


def collect_processes():
    """실행 중 프로그램들 [{path, name}] (경로 기준으로 중복 제거, 읽을 수 없는 것은 건너뜀)."""
    seen, out = set(), []
    for pid in sec_common.list_pids():
        p = sec_common.exe_path(pid)
        if p and p.lower() not in seen:
            seen.add(p.lower())
            out.append({"pid": pid, "path": p, "name": Path(p).name})
    return out


# ---------------------------------------------------------------- 점검 본체
def _load(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _save(path: Path, data):
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, path)
    except OSError:
        pass


def _age_days(path):
    try:
        return (time.time() - os.stat(path).st_ctime) / 86400.0
    except OSError:
        return None


def scan(work_dir, allow=None, self_paths=(), collectors=None, sig_runner=None, now=None):
    """점검을 한 번 한다. findings: [{kind, level, title, text, data, key}].
    allow: {"process": [소문자 경로…], "autorun": [id…]}.  self_paths: 이 경로 아래의 프로그램(고양이 자신)은 건너뜀.
    collectors/sig_runner/now: 시험에서 바꿔 끼운다."""
    work_dir = Path(work_dir)
    allow = allow or {}
    now = now if now is not None else time.time()
    c = collectors or {"registry": collect_registry, "startup": collect_startup_folders,
                       "tasks": lambda: collect_tasks_services(work_dir), "processes": collect_processes}
    skip = tuple(str(Path(p)).lower() for p in self_paths if p)
    baseline_file, seen_file = work_dir / "baseline.json", work_dir / "seen.json"
    baseline = _load(baseline_file, None)
    first = baseline is None
    baseline = baseline or {}
    seen = {k: v for k, v in _load(seen_file, {}).items() if now - v < SEEN_DAYS * 86400}
    findings = []
    # --- 자동 시작
    entries = []
    for key in ("registry", "startup", "tasks"):
        try:
            entries += c[key]()
        except Exception:
            pass
    for e in entries:
        e["id"] = autorun_id(e["kind"], e["name"], e["command"])
    new_entries = [e for e in entries if e["id"] not in baseline and e["id"] not in allow.get("autorun", [])]
    procs = []
    try:
        procs = [p for p in c["processes"]() if not p["path"].lower().startswith(skip)]
    except Exception:
        pass
    paths = [e["path"] for e in new_entries if e.get("path")] + [p["path"] for p in procs if location_score(p["path"])[0] or Path(p["path"]).name.lower() in SYSTEM_NAMES]
    sigs = sec_sig.check_many(paths, work_dir, **({"runner": sig_runner} if sig_runner else {})) if paths else {}
    if not first:
        for e in new_entries:
            sig = sigs.get(e.get("path"), {})
            level, reasons = classify_autorun(e, sig.get("status", ""))
            title = {"run": "새 자동 시작 프로그램이 생겼어요", "startup": "시작 폴더에 새 항목이 생겼어요", "startup-exe": "시작 폴더에 실행 파일이 생겼어요",
                     "task": "새 예약 작업이 생겼어요", "service": "새 자동 시작 서비스가 생겼어요", "winlogon": "윈도우 로그인 설정이 바뀌었어요",
                     "ifeo": "프로그램 실행을 가로채는 설정이 생겼어요"}.get(e["kind"], "새 자동 시작 항목이 생겼어요")
            text = "%s (%s)\n실행: %s\n%s" % (e["name"], e["where"], e["command"][:300], "\n".join("· " + r for r in reasons))
            if sig.get("publisher"):
                text += "\n· 서명한 곳: " + sig["publisher"]
            findings.append({"kind": "autorun", "level": level, "title": title if level != "info" else title + " (서명 확인됨)", "text": text.strip(),
                             "data": {"path": e.get("path", ""), "command": e["command"][:300], "where": e["where"], "name": e["name"], "id": e["id"],
                                      "status": sig.get("status", ""), "publisher": sig.get("publisher", "")}, "key": "autorun:" + e["id"]})
    for e in entries:                                      # 처음 돌 때는 지금 있는 것을 '평소 것'으로 저장한다. 그 뒤에는 새로 알린 것도 기준에 넣는다
        baseline.setdefault(e["id"], now)
    _save(baseline_file, baseline)
    # --- 실행 중 프로그램
    allow_proc = {p.lower() for p in allow.get("process", [])}
    for p in procs:
        low = p["path"].lower()
        if low in allow_proc:
            continue
        sig = sigs.get(p["path"])
        if sig is None and not (location_score(p["path"])[0] or p["name"].lower() in SYSTEM_NAMES):
            continue
        score, level, reasons = classify_process(p["path"], (sig or {}).get("status", ""), _age_days(p["path"]))
        if not level:
            continue
        k = "proc|%s|%d" % (low, int(os.stat(p["path"]).st_mtime) if os.path.exists(p["path"]) else 0)
        if k in seen:
            continue
        seen[k] = now
        text = "%s\n%s\n%s" % (p["name"], p["path"], "\n".join("· " + r for r in reasons))
        findings.append({"kind": "process", "level": level, "title": "수상한 프로그램이 실행 중이에요", "text": text,
                         "data": {"path": p["path"], "pid": p["pid"], "name": p["name"], "score": score, "status": (sig or {}).get("status", ""),
                                  "publisher": (sig or {}).get("publisher", "")}, "key": "proc:" + low})
    _save(seen_file, seen)
    return {"first": first, "entries": len(entries), "processes": len(procs), "findings": findings}
