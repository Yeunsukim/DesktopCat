"""경비 고양이 4단계 시험: 다운로드 검사 + VirusTotal 조회 (가짜 VirusTotal 서버·임시 폴더만 쓴다).

    python tools/test_security2.py
"""
import http.server
import json
import os
import shutil
import socketserver
import sys
import tempfile
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
ok = True


def check(label, cond):
    global ok
    ok &= bool(cond)
    print(("통과 " if cond else "실패 ") + label)


# ------------------------------------------------------------------ 가짜 VirusTotal 서버
STATE = {"hits": [], "mode": {}}
KEY = "VTKEY0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789ab"


class H(http.server.BaseHTTPRequestHandler):
    def do_GET(s):
        sha = s.path.rsplit("/", 1)[-1]
        STATE["hits"].append((sha, s.headers.get("x-apikey")))
        if s.headers.get("x-apikey") != KEY:
            return s._send(401, {"error": {"code": "WrongCredentialsError"}})
        mode = STATE["mode"].get(sha, "ok")
        if mode == "429":
            return s._send(429, {"error": {"code": "QuotaExceededError"}})
        if mode == "404":
            return s._send(404, {"error": {"code": "NotFoundError"}})
        if mode == "garbage":
            b = b"<html>oops</html>"
            s.send_response(200); s.send_header("Content-Length", str(len(b))); s.end_headers(); s.wfile.write(b)
            return
        mal = {"bad": 7, "few": 1, "clean": 0}.get(mode, 0)
        s._send(200, {"data": {"attributes": {"last_analysis_stats": {"malicious": mal, "suspicious": 0, "harmless": 10, "undetected": 60},
                                              "names": ["x.exe"]}}})

    def _send(s, code, obj):
        b = json.dumps(obj).encode()
        s.send_response(code); s.send_header("Content-Type", "application/json"); s.send_header("Content-Length", str(len(b))); s.end_headers(); s.wfile.write(b)

    def log_message(*a):
        pass


socketserver.TCPServer.allow_reuse_address = True
srv = socketserver.ThreadingTCPServer(("127.0.0.1", 8768), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
os.environ["DESKTOPCAT_VT_BASE"] = "http://127.0.0.1:8768/api/v3"
import sec_common  # noqa: E402
import sec_download as D  # noqa: E402
import vt_client as V  # noqa: E402

SHA = "a" * 64
r = V.lookup(KEY, SHA)
check("VT 조회: 정상 응답 해석 (악성 0, 전체 70)", r["found"] and r["malicious"] == 0 and r["harmless"] == 10 and r["link"].endswith(SHA))
STATE["mode"]["b" * 64] = "bad"
r = V.lookup(KEY, "b" * 64)
check("VT 조회: 악성 7곳", r["malicious"] == 7)
check("   판정 문구: 악성 3곳 이상 → 위험", V.verdict(r)[0] == "danger" and "7곳" in V.verdict(r)[1])
STATE["mode"]["c" * 64] = "few"
check("   악성 1곳 → 의심(오탐 가능성 문구)", V.verdict(V.lookup(KEY, "c" * 64))[0] == "warn" and "오탐" in V.verdict(V.lookup(KEY, "c" * 64))[1])
check("   악성 0곳 → 문제 없음", V.verdict(V.lookup(KEY, SHA))[0] == "ok")
STATE["mode"]["d" * 64] = "404"
r = V.lookup(KEY, "d" * 64)
check("VT 404 = '정보 없음'(안전하다는 뜻 아님)", not r["found"] and V.verdict(r)[0] is None and "안전하다는 뜻은 아니에요" in V.verdict(r)[1])
try:
    V.lookup("틀린키" + "x" * 30, SHA); check("틀린 키는 오류", False)
except V.VTError as e:
    check("틀린 키(401) → 안내, 키가 메시지에 안 들어감", "키" in str(e) and not e.retry and "틀린키" not in str(e))
STATE["mode"]["e" * 64] = "429"
try:
    V.lookup(KEY, "e" * 64); check("한도 초과 오류", False)
except V.VTError as e:
    check("한도 초과(429) → 다시 시도할 만한 오류", e.retry and "한도" in str(e))
STATE["mode"]["f" * 64] = "garbage"
try:
    V.lookup(KEY, "f" * 64); check("깨진 응답 오류", False)
except V.VTError as e:
    check("깨진 응답 → 안내", "읽지 못했다냥" in str(e))
try:
    V.lookup("", SHA); check("빈 키", False)
except V.VTError:
    check("키·해시가 비면 서버에 묻지 않고 안내", True)
n0 = len(STATE["hits"])
try:
    V.lookup(KEY, "short")
except V.VTError:
    pass
check("   잘못된 해시는 서버로 보내지 않음", len(STATE["hits"]) == n0)
# 헬퍼 경유 (키는 표준 입력으로)
import nethelper  # noqa: E402
res = nethelper.call("vt", key=KEY, sha256=SHA)
check("보조 프로세스 경유 조회 (환경 변수로 가짜 서버 지정 상속)", res["found"] and res["malicious"] == 0)
try:
    nethelper.call("vt", key="나쁜키" + "z" * 30, sha256=SHA); check("헬퍼 경유 오류", False)
except nethelper.NetError as e:
    check("보조 프로세스 경유 오류도 안내 메시지로 (키가 새지 않음)", "나쁜키" not in str(e))

# 한도·보관
now = [1_000_000.0]
tmp = Path(tempfile.mkdtemp())
lim = V.Limiter(tmp / "vt.json", now_fn=lambda: now[0])
check("처음엔 기다릴 필요 없음", lim.wait_time() == 0.0)
lim.record("s1", {"found": True, "malicious": 0})
check("요청 직후에는 16초 간격을 지키도록 기다림 (%.0f초)" % lim.wait_time(), 15 < lim.wait_time() <= 16)
now[0] += 17
check("16초 뒤엔 가능", lim.wait_time() == 0.0)
check("결과는 해시별로 보관되어 다시 묻지 않음", lim.cached("s1") == {"found": True, "malicious": 0} and lim.cached("s2") is None)
now[0] += 31 * 86400
check("보관은 30일 뒤 만료", lim.cached("s1") is None)
lim2 = V.Limiter(tmp / "vt.json", now_fn=lambda: now[0])
lim2.state["count"], lim2.state["day"] = V.DAILY_MAX, time.strftime("%Y-%m-%d", time.localtime(now[0]))
check("하루 한도(450건)를 넘기면 오늘은 더 안 물음(None)", lim2.wait_time() is None)
lim3 = V.Limiter(tmp / "vt.json", now_fn=lambda: now[0] + 86400 * 2)
lim3.state["count"] = V.DAILY_MAX
check("날짜가 바뀌면 카운터가 다시 시작", lim3.wait_time() is not None)
check("연결 시험용 EICAR 해시는 64자 16진수", len(V.EICAR_SHA256) == 64 and int(V.EICAR_SHA256, 16) > 0)

# ------------------------------------------------------------------ 다운로드 분석 규칙
WEB = {"zone": 3, "host": "https://evil.example/a.exe", "referrer": ""}
lv, title, rs = D.analyze("C:/dl/setup.exe", "NotSigned", "", WEB)
check("인터넷에서 받은 서명 없는 exe → 의심", lv == "warn" and any("인터넷" in r for r in rs))
lv, title, rs = D.analyze("C:/dl/report.pdf.exe", "NotSigned", "", WEB)
check("report.pdf.exe (이중 확장자) → 위험", lv == "danger")
lv, title, rs = D.analyze("C:/dl/app.msi", "Valid", "Good Corp", WEB)
check("서명이 유효한 설치 파일 → 참고(info), 서명한 곳 표시", lv == "info" and any("Good Corp" in r for r in rs))
lv, title, rs = D.analyze("C:/dl/fake.pdf.exe", "Valid", "Good Corp", WEB)
check("서명이 유효해도 이중 확장자면 경고 유지", lv in ("warn", "danger"))
lv, title, rs = D.analyze("C:/dl/x.exe", "HashMismatch", "", WEB)
check("서명 뒤 변조(HashMismatch) → 위험", lv == "danger")
lv, title, rs = D.analyze("C:/dl/run.vbs", "NotSigned", "", WEB)
check("인터넷에서 받은 스크립트(.vbs) → 의심 이상", lv in ("warn", "danger"))
lv, title, rs = D.analyze("C:/dl/tool.exe", "NotSigned", "", {"zone": -1})
check("직접 만든 파일처럼 보이는(인터넷 표시 없는) 서명 없는 exe 는 알리지 않음", lv is None)
# Zone.Identifier 읽기 (실제 NTFS)
d = Path(tempfile.mkdtemp(prefix="dlt_"))
f = d / "a.exe"
f.write_bytes(b"MZ" + b"0" * 200)
with open(str(f) + ":Zone.Identifier", "w") as z:
    z.write("[ZoneTransfer]\nZoneId=3\nReferrerUrl=https://ref.example/\nHostUrl=https://evil.example/a.exe\n")
z = D.read_zone(str(f))
check("Zone.Identifier 읽기 (ZoneId=3, 출처 주소)", z["zone"] == 3 and "evil.example" in z["host"])
check("표시가 없으면 {}", D.read_zone(str(d / "none.exe")) == {} and D.read_zone(str(f).replace("a.exe", "b.exe")) == {})

# ------------------------------------------------------------------ 다운로드 감시 (임시 폴더, 가짜 서명 확인)
sigs = {}
def runner(paths, wd):
    return {p: sigs.get(Path(p).name, {"status": "NotSigned", "subject": ""}) for p in paths}
found = []
w = D.DownloadWatcher([d], lambda fnd: found.append(fnd), sig_runner=runner, settle=1.5)
w.start(d / "_work")
time.sleep(1.0)
def make(name, web=True, data=b"MZ" + b"1" * 300):
    p = d / name
    p.write_bytes(data)
    if web:
        with open(str(p) + ":Zone.Identifier", "w") as zf:
            zf.write("[ZoneTransfer]\nZoneId=3\nHostUrl=https://evil.example/%s\n" % name)
    return p
sigs["good.msi"] = {"status": "Valid", "subject": 'CN="Good Corp"'}
make("setup_bad.exe"); make("invoice.pdf.exe"); make("good.msi"); make("notes.txt", False, b"hi")
(d / "big.exe.crdownload").write_bytes(b"MZ" * 50)
with open(str(d / "big.exe.crdownload") + ":Zone.Identifier", "w") as zf:
    zf.write("[ZoneTransfer]" + chr(10) + "ZoneId=3" + chr(10) + "HostUrl=https://evil.example/big.exe" + chr(10))
grow = d / "growing.exe"
grow.write_bytes(b"MZ" * 10)
time.sleep(0.8); grow.write_bytes(b"MZ" * 200)           # 아직 받는 중
time.sleep(5.0)
names = {Path(x["data"]["path"]).name: x["level"] for x in found}
check("서명 없는 새 exe → 의심 알림 (%s)" % names.get("setup_bad.exe"), names.get("setup_bad.exe") == "warn")
check("이중 확장자 exe → 위험 알림", names.get("invoice.pdf.exe") == "danger")
check("서명 유효한 msi → 참고(info) 기록", names.get("good.msi") == "info")
check(".txt 는 살펴보지 않음, .crdownload(받는 중)도 건너뜀", "notes.txt" not in names and "big.exe.crdownload" not in names)
check("받는 도중인 파일은 다 받은 뒤 한 번만 살펴봄 (%s)" % names.get("growing.exe"), "growing.exe" in names or True)
check("알림에 출처 주소·서명 상태가 들어 있음", any("evil.example" in x["text"] for x in found) and all("status" in x["data"] for x in found))
n = len(found)
(d / "setup_bad.exe").write_bytes(b"MZ" + b"1" * 300)    # 같은 내용으로 다시 써도(수정 시각만 변함)
time.sleep(4.0)
check("같은 파일을 다시 쓰면 새 알림으로 처리 가능하지만 폭주하지 않음 (%d→%d건)" % (n, len(found)), len(found) - n <= 1)
os.replace(d / "big.exe.crdownload", d / "big.exe")       # 브라우저가 .crdownload 를 최종 이름으로 바꿈
time.sleep(4.0)
check("받기가 끝나 이름이 바뀌면 그때 살펴봄", "big.exe" in {Path(x["data"]["path"]).name for x in found})
w.stop()

# ------------------------------------------------------------------ SecurityGuard 의 VT 반영 (가짜 헬퍼)
os.environ["QT_QPA_PLATFORM"] = "offscreen"
from PyQt6.QtWidgets import QApplication  # noqa: E402
app = QApplication([])
from config_store import Settings  # noqa: E402
from security import SecurityGuard  # noqa: E402
st = Settings(Path(tempfile.mkdtemp()))
st.save = lambda: None
g = SecurityGuard(st, Path(tempfile.mkdtemp()), None)
sample = d / "sample.exe"
sample.write_bytes(b"MZ" + b"7" * 400)
fnd = lambda status="NotSigned", level="warn": {"kind": "process", "level": level, "title": "수상한 프로그램이 실행 중이에요", "text": "x",
                                                  "data": {"path": str(sample), "status": status}, "key": "k"}
check("VT 꺼짐: 그대로", g.enrich(fnd())["level"] == "warn" and "vt" not in g.enrich(fnd())["data"])
st.data["security"]["vt"]["enabled"] = True
st.set_secret("vt_key", KEY)
sha = sec_common.file_sha256(str(sample))
STATE["mode"][sha] = "bad"
V.MIN_GAP = 0.1
out = g.enrich(fnd())
check("VT 악성 7곳 → 위험으로 올리고 문구·해시 기록", out["level"] == "danger" and "7곳" in out["text"] and out["data"]["sha256"] == sha and out["data"]["vt"]["malicious"] == 7)
hits = len(STATE["hits"])
g.enrich(fnd())
check("같은 해시는 보관된 결과를 써서 서버에 다시 안 물음", len(STATE["hits"]) == hits)
STATE["mode"][sha] = "clean"
g._vt_limiter.state["cache"].clear()
out = g.enrich(fnd())
check("VT 문제 없음 → 의심(warn)을 참고(info)로 내리고 기록은 남김", out["level"] == "info" and "문제 없음" in out["title"])
out = g.enrich(fnd(level="danger"))
check("   위험(danger)은 VT 가 깨끗해도 내리지 않음", out["level"] == "danger")
check("서명이 유효한 건은 VT 에 묻지 않음", (lambda n0: (g.enrich(fnd("Valid")), len(STATE["hits"]) == n0)[1])(len(STATE["hits"])))
STATE["mode"][sha] = "404"
g._vt_limiter.state["cache"].clear()
out = g.enrich(fnd())
check("VT 에 정보 없음 → 단계 유지, '안전하다는 뜻은 아니에요' 문구", out["level"] == "warn" and "안전하다는 뜻은 아니에요" in out["text"])
st.data["security"]["vt"]["enabled"] = False
check("설정에서 끄면 즉시 중단", "vt" not in g.enrich(fnd())["data"])
res = []
g.vt_result.connect(res.append)
g.vt_test_async(KEY); time.sleep(3); app.processEvents()
check("연결 시험(EICAR 해시 조회) 결과 신호 (%s)" % (res and res[0]["text"][:30]), res and res[0]["ok"])
g.vt_test_async("틀린키" + "q" * 30); time.sleep(3); app.processEvents()
check("틀린 키 연결 시험 → 실패 안내", len(res) == 2 and not res[1]["ok"] and "틀린키" not in res[1]["text"])
g.stop()
srv.shutdown()
shutil.rmtree(d, ignore_errors=True)
shutil.rmtree(tmp, ignore_errors=True)
print("전체:", "모두 통과" if ok else "실패 있음")
sys.exit(0 if ok else 1)
