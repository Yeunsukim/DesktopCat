"""경비 고양이 점검 모듈(자동 시작·프로세스·서명) 시험 — 가짜 입력으로 판단 규칙을 확인하고, 실제 PC 는 읽기만 해서 형식을 확인한다.

    python tools/test_security.py
"""
import json
import shutil
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import sec_scan as S  # noqa: E402
import sec_sig  # noqa: E402

ok = True


def check(label, cond):
    global ok
    ok &= bool(cond)
    print(("통과 " if cond else "실패 ") + label)


# --- 명령줄에서 실행 파일 경로 뽑기
check("따옴표 경로+인자", S.parse_command_path('"C:\\Program Files\\A B\\x.exe" /silent') == "C:\\Program Files\\A B\\x.exe")
check("따옴표 없는 경로+인자", S.parse_command_path("C:\\tools\\y.exe -k") == "C:\\tools\\y.exe")
check("공백이 든 따옴표 없는 경로(확장자까지)", S.parse_command_path("C:" + chr(92) + "Program Files" + chr(92) + "Z" + chr(92) + "z.exe --x") == "C:" + chr(92) + "Program Files" + chr(92) + "Z" + chr(92) + "z.exe")
check("빈 값", S.parse_command_path("") == "")
check("환경 변수 펼침", S.parse_command_path('"%windir%\\notepad.exe"').lower().endswith("windows\\notepad.exe"))

# --- 실행 중 프로그램 점수
VALID = "Valid"
sc, lv, rs = S.classify_process(r"C:\Users\u\AppData\Local\Programs\Slack\slack.exe", VALID, 30)
check("유효한 서명이 있으면 AppData 에서 돌아도 알리지 않음", lv is None)
sc, lv, rs = S.classify_process(r"C:\Users\u\AppData\Local\Temp\setup123.exe", "NotSigned", 3)
check("서명 없는 exe 가 임시 폴더에서 실행 중 → 의심 (점수 %d)" % sc, lv == "warn")
sc, lv, rs = S.classify_process(r"C:\Users\u\AppData\Local\Temp\svchost.exe", "NotSigned", 0.2)
check("임시 폴더의 svchost.exe → 위험 (점수 %d)" % sc, lv == "danger" and any("시스템 프로그램" in r for r in rs))
sc, lv, rs = S.classify_process(r"C:\Users\u\Downloads\report.pdf.exe", "NotSigned", 0.1)
check("report.pdf.exe (이중 확장자) → 위험/의심 (점수 %d)" % sc, lv in ("warn", "danger") and any("이중" in r for r in rs))
sc, lv, rs = S.classify_process(r"C:\Users\u\Downloads\tool.exe", "NotSigned", 3)
check("다운로드 폴더에서 서명 없는 프로그램을 돌리는 것만으로는 알리지 않음 (점수 %d)" % sc, lv is None)
sc, lv, rs = S.classify_process(r"C:\Users\u\AppData\Roaming\x\updater.exe", "HashMismatch", 40)
check("서명 뒤에 바뀐 파일(HashMismatch)+Roaming → 위험 (점수 %d)" % sc, lv == "danger")
sc, lv, rs = S.classify_process(r"C:\Program Files\Foo\foo.exe", "NotSigned", 40)
check("Program Files 의 서명 없는 프로그램은 알리지 않음", lv is None)
sc, lv, rs = S.classify_process(r"C:\Users\Public\x.exe", "Error", 0.5)
check("서명 확인 실패(Error)는 가볍게만 본다 (점수 %d)" % sc, lv in (None, "warn"))

# --- 새 자동 시작 판단
e = {"kind": "run", "name": "Updater", "where": "HKCU Run", "command": r'"C:\Users\u\AppData\Roaming\u\up.exe"', "path": r"C:\Users\u\AppData\Roaming\u\up.exe"}
check("새 자동 시작: Roaming 의 서명 없는 것 → 위험", S.classify_autorun(e, "NotSigned")[0] == "danger")
check("새 자동 시작: 유효한 서명 → 참고(info)", S.classify_autorun(e, "Valid")[0] == "info")
e2 = dict(e, path=r"C:\Program Files\Tool\t.exe", command=r'"C:\Program Files\Tool\t.exe"')
check("새 자동 시작: Program Files 의 서명 없는 것 → 의심", S.classify_autorun(e2, "NotSigned")[0] == "warn")
check("윈도우 로그인(Shell) 설정 변경 → 위험", S.classify_autorun({"kind": "winlogon", "name": "Shell", "path": "x.exe", "command": "x.exe"}, "Valid")[0] == "danger")
check("시작 폴더의 exe 파일(서명 없음) → 위험", S.classify_autorun({"kind": "startup-exe", "name": "a.exe", "path": r"C:\Users\u\x\a.exe", "command": "a"}, "NotSigned")[0] == "danger")

# --- scan() 전체 흐름 (가짜 수집기)
tmp = Path(tempfile.mkdtemp())
state = {"entries": [{"kind": "run", "where": "HKCU Run", "name": "OneDrive", "command": r'"C:\Program Files\OD\od.exe"', "path": r"C:\Program Files\OD\od.exe"}],
         "procs": [{"pid": 11, "path": r"C:\Users\u\AppData\Local\Temp\evil.exe", "name": "evil.exe"},
                   {"pid": 12, "path": r"C:\Users\u\AppData\Local\Programs\App\app.exe", "name": "app.exe"},
                   {"pid": 13, "path": str(tmp / "DesktopCat" / "cat.exe"), "name": "cat.exe"}]}
calls = []
sig_table = {r"C:\Users\u\AppData\Local\Temp\evil.exe": {"status": "NotSigned", "subject": ""},
             r"C:\Users\u\AppData\Local\Programs\App\app.exe": {"status": "Valid", "subject": "CN=App Inc, O=App"},
             r"C:\Users\u\AppData\Roaming\spy\spy.exe": {"status": "NotSigned", "subject": ""},
             r"C:\Program Files\OD\od.exe": {"status": "Valid", "subject": "CN=Microsoft Corporation"}}


def runner(paths, work_dir):
    calls.append(list(paths))
    return {p: sig_table.get(p, {"status": "NotSigned", "subject": ""}) for p in paths}


# sec_sig 는 실제로 존재하는 파일만 확인하므로, 시험용으로 파일 존재 검사를 우회한다
import os as _os
_real_isfile = _os.path.isfile
_os.path.isfile = lambda p: True if str(p).startswith(("C:\\Users\\u", "C:\\Program Files\\OD")) else _real_isfile(p)
_real_stat = _os.stat
class _St:
    st_mtime = 1700000000; st_size = 1234; st_ctime = time.time() - 3 * 86400
_os.stat = lambda p, *a, **k: _St() if str(p).startswith(("C:\\Users\\u", "C:\\Program Files\\OD")) else _real_stat(p, *a, **k)
coll = {"registry": lambda: [dict(e) for e in state["entries"]], "startup": lambda: [], "tasks": lambda: [], "processes": lambda: [dict(p) for p in state["procs"]]}
work = tmp / "sec"
r1 = S.scan(work, {}, self_paths=[str(tmp / "DesktopCat")], collectors=coll, sig_runner=runner, now=1000.0)
check("첫 점검: 기준 목록만 저장하고 새 자동 시작 알림은 없음", r1["first"] and not [f for f in r1["findings"] if f["kind"] == "autorun"])
check("   실행 중 의심 프로그램(evil.exe)은 첫 점검에도 알림 (단계 %s)" % [f["level"] for f in r1["findings"]], [f["level"] for f in r1["findings"]] == ["warn"])
check("   고양이 자신의 경로(self_paths)와 서명 유효한 프로그램은 건너뜀", len(r1["findings"]) == 1 and "evil.exe" in r1["findings"][0]["data"]["path"])
check("   기준 목록 파일이 저장됨", (work / "baseline.json").exists())
r2 = S.scan(work, {}, self_paths=[str(tmp / "DesktopCat")], collectors=coll, sig_runner=runner, now=1100.0)
check("둘째 점검: 같은 의심 프로그램을 되풀이해서 알리지 않음 (7일)", not r2["findings"])
state["entries"].append({"kind": "run", "where": "HKCU Run", "name": "Spy", "command": r'"C:\Users\u\AppData\Roaming\spy\spy.exe"', "path": r"C:\Users\u\AppData\Roaming\spy\spy.exe"})
n_before = len(calls)
r3 = S.scan(work, {}, self_paths=[], collectors=coll, sig_runner=runner, now=1200.0)
auto = [f for f in r3["findings"] if f["kind"] == "autorun"]
check("새 자동 시작(Spy, 서명 없음·Roaming) → 위험 알림 1건", len(auto) == 1 and auto[0]["level"] == "danger" and "Spy" in auto[0]["text"])
check("   알림에 경로·이유가 들어 있음", "spy.exe" in auto[0]["text"] and "서명이 없어요" in auto[0]["text"])
r4 = S.scan(work, {}, self_paths=[], collectors=coll, sig_runner=runner, now=1300.0)
check("   알린 뒤에는 기준 목록에 들어가서 다시 알리지 않음", not [f for f in r4["findings"] if f["kind"] == "autorun"])
state["entries"].append({"kind": "task", "where": "예약 작업", "name": "\\MyTask", "command": r"C:\Users\u\AppData\Roaming\spy\spy.exe", "path": r"C:\Users\u\AppData\Roaming\spy\spy.exe"})
r5 = S.scan(work, {"autorun": [S.autorun_id("task", "\\MyTask", r"C:\Users\u\AppData\Roaming\spy\spy.exe")]}, collectors=coll, sig_runner=runner, now=1400.0)
check("허용 목록(autorun)에 넣은 항목은 알리지 않음", not [f for f in r5["findings"] if f["kind"] == "autorun"])
r6 = S.scan(work, {"process": [r"C:\Users\u\AppData\Local\Temp\evil.exe"]}, collectors=coll, sig_runner=runner, now=1000.0 + 8 * 86400)
check("허용 목록(process)에 넣은 프로그램은 7일 뒤에도 알리지 않음", not [f for f in r6["findings"] if f["kind"] == "process"])
r7 = S.scan(work, {}, collectors=coll, sig_runner=runner, now=1000.0 + 8 * 86400)
check("7일이 지나면(허용 안 했을 때) 다시 알림", [f["kind"] for f in r7["findings"]] == ["process"])
n_calls = len(calls)
S.scan(work, {}, collectors=coll, sig_runner=runner, now=1000.0 + 9 * 86400)
check("서명 확인 결과는 보관되어 같은 파일은 PowerShell 을 다시 부르지 않음", len(calls) == n_calls)
_os.path.isfile, _os.stat = _real_isfile, _real_stat

# --- 서명 보관 (sec_sig)
cache_dir = Path(tempfile.mkdtemp())
f = cache_dir / "a.exe"
f.write_bytes(b"MZ" + b"0" * 500)
n = []
def r_(paths, wd):
    n.append(1)
    return {p: {"status": "Valid", "subject": 'CN="Test Corp", O=Test'} for p in paths}
a = sec_sig.check_many([str(f)], cache_dir, runner=r_)
b = sec_sig.check_many([str(f)], cache_dir, runner=r_)
check("서명 확인: 게시자 이름 추출 (%s)" % a[str(f)]["publisher"], a[str(f)]["publisher"] == "Test Corp" and a[str(f)]["status"] == "Valid")
check("   같은 파일은 보관된 결과 재사용 (확인 %d번)" % len(n), len(n) == 1 and b == a)
f.write_bytes(b"MZ" + b"1" * 900)
sec_sig.check_many([str(f)], cache_dir, runner=r_)
check("   파일이 바뀌면(크기·시각) 다시 확인", len(n) == 2)
check("   없는 파일은 무시", sec_sig.check_many([str(cache_dir / "none.exe")], cache_dir, runner=r_) == {})
def bad(paths, wd): raise RuntimeError("PowerShell 실패")
g = cache_dir / "b.exe"; g.write_bytes(b"MZ" * 100)
res = sec_sig.check_many([str(g)], cache_dir, runner=bad)
check("   확인 도구가 실패하면 'Error' 로 돌려주고 보관하지 않음(다음에 다시)", res[str(g)]["status"] == "Error" and sec_sig._key(str(g)) not in json.loads((cache_dir / "sigcache.json").read_text(encoding="utf-8")) if (cache_dir / "sigcache.json").exists() else True)

# --- 실제 PC (읽기만)
reg = S.collect_registry()
check("실제 레지스트리 자동 시작 읽기: %d개, 형식 정상" % len(reg), isinstance(reg, list) and all({"kind", "name", "command", "path"} <= set(e) for e in reg))
st_ = S.collect_startup_folders()
check("실제 시작 폴더 읽기: %d개" % len(st_), isinstance(st_, list))
pr = S.collect_processes()
check("실제 실행 중 프로그램 목록: %d개 (경로 읽힌 것)" % len(pr), len(pr) > 5)
# --- 카메라·마이크
import sec_privacy as P  # noqa: E402
T0 = 1_000_000.0
def row(name, cap="webcam", in_use=True, path=""):
    return {"cap": cap, "name": name, "path": path, "key": ("%s|%s" % (cap, name)).lower(), "start": T0 if in_use else 0, "stop": 0 if in_use else T0, "in_use": in_use}
ev, st = P.check_usage([row("Zoom.exe"), row("chrome.exe", "microphone")], {}, now=T0 + 10 * 3600)
check("줌·크롬 같은 널리 쓰는 프로그램은 처음부터 믿음", ev == [])
ev, st = P.check_usage([row("spy.exe", "microphone", path="C:/u/spy.exe")], {"first": T0, "known": {}}, now=T0 + 3600)
check("배우는 기간(처음 하루)에는 알리지 않고 기억만", ev == [] and "microphone|spy.exe" in st["known"])
ev, st = P.check_usage([row("spy.exe", "microphone")], st, now=T0 + 3 * 86400)
check("배운 프로그램은 하루가 지나도 알리지 않음", ev == [])
ev, st = P.check_usage([row("newapp.exe")], st, now=T0 + 3 * 86400)
check("하루 뒤 처음 보는 프로그램이 카메라를 쓰면 의심 알림 1건", len(ev) == 1 and ev[0]["level"] == "warn" and "카메라" in ev[0]["title"] and "newapp.exe" in ev[0]["text"])
ev, st = P.check_usage([row("newapp.exe")], st, now=T0 + 3 * 86400 + 60)
check("   같은 프로그램은 다시 알리지 않음", ev == [])
ev, _ = P.check_usage([row("other.exe", "microphone")], st, allow=["microphone|other.exe"], now=T0 + 3 * 86400)
check("허용 목록(키)에 넣은 프로그램은 알리지 않음", ev == [])
ev, _ = P.check_usage([row("quiet.exe", in_use=False)], st, now=T0 + 3 * 86400)
check("쓰는 중이 아니면(끈 기록만 있으면) 알리지 않음", ev == [])
ev, _ = P.check_usage([row("MyApp.exe", "microphone")], st, allow=["myapp.exe"], now=T0 + 3 * 86400)
check("허용 목록(이름, 대소문자 무시)도 통함", ev == [])
check("파일 시간 변환(FILETIME → 초)", abs(P._filetime(133000000000000000) - (133000000000000000 - 116444736000000000) / 1e7) < 1 and P._filetime(0) == 0.0)
rows = P.read_usage()
check("실제 PC의 카메라·마이크 기록 읽기: %d건, 형식 정상" % len(rows), isinstance(rows, list) and all({"cap", "name", "key", "in_use"} <= set(r) for r in rows))
shutil.rmtree(tmp, ignore_errors=True)
shutil.rmtree(cache_dir, ignore_errors=True)
print("전체:", "모두 통과" if ok else "실패 있음")
sys.exit(0 if ok else 1)
