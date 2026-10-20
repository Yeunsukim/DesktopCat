"""랜섬웨어 경보 점검 — 진짜 악성코드 없이, 임시 폴더에서 '암호화하는 흉내'만 내서 경보가 제때 울리고 정상 작업에는 안 울리는지 본다.

    python tools/test_ransom_sim.py

 A) 가짜 사건을 넣는 단위 점검 (RansomDetector)
 B) 실제 파일 시스템 + 폴더 감시(sec_watch)로 임시 폴더에서 '암호화 흉내'(무작위 바이트로 덮어쓰고 .locked 로 이름 변경)와
    정상 작업(대량 복사·압축 풀기·글자 파일 서식 바꾸기)을 돌려 본다. 사용자의 실제 폴더는 건드리지 않는다.
"""
import os
import random
import shutil
import sys
import tempfile
import time
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import sec_ransom as R  # noqa: E402
from sec_events import SecEvents  # noqa: E402

ok = True


def check(label, cond):
    global ok
    ok &= bool(cond)
    print(("통과 " if cond else "실패 ") + label)


RND = random.Random(7)


def rand_bytes(n=4096):
    return bytes(RND.getrandbits(8) for _ in range(n))


def docx_head():
    return b"PK\x03\x04" + b"\x14\x00\x00\x00\x08\x00" + b"word/document.xml" * 40


def text_head():
    return ("회의록 초안입니다 오늘의 안건은 다음과 같습니다 " * 30).encode("utf-8")[:4096]


# ----------------------------------------------------------------------------- A) 단위
print("== A) 가짜 사건으로 판단 로직 점검 ==")
ROOTS = [r"C:\Users\x\Documents", r"C:\Users\x\Pictures", r"C:\Users\x\Desktop"]


def det(sens="normal", head=None, canaries=None):
    return R.RansomDetector(sens, read_head=head or (lambda p: rand_bytes()), now_fn=lambda: 1000.0, canaries=canaries, roots=ROOTS)


def paths(n, folders=3, ext=".docx"):
    return [r"%s\f%d%s" % (ROOTS[i % folders], i, ext) for i in range(n)]


# 1) 전형적인 랜섬웨어: 덮어쓰고 .locked 로 이름 변경
d = det()
t = 1000.0
for p in paths(60):
    d.feed("modified", p, t=t); d.feed("moved", p, p + ".locked", t=t + 0.01); t += 0.05
a = d.evaluate(t)
check("덮어쓰기+낯선 확장자 이름 변경 60개 → 위험 경보 (%s)" % (a and a["top_ext"]), a and a["level"] == "danger" and a["top_ext"] == ".locked" and a["files"] >= 25)
check("   경보에 이유·파일 예시가 들어 있음", a and a["reasons"] and a["samples"])
check("   120초 안에는 같은 경보를 되풀이하지 않음", d.evaluate(t + 30) is None)
# 2) 이름은 그대로, 내용만 암호화(문서 머리글이 깨짐)
d = det()
t = 1000.0
for p in paths(40):
    d.feed("modified", p, t=t); t += 0.1
a = d.evaluate(t)
check("이름 변경 없이 내용만 암호화(.docx 머리글 깨짐) → 위험 경보", a and a["level"] == "danger" and any("암호화" in r for r in a["reasons"]))
# 3) 원본 삭제 + 암호화본 새로 만들기
d = det()
t = 1000.0
d.created.clear()
for p in paths(40):
    d.feed("created", p + ".crypt", t=t); d.feed("deleted", p, t=t + 0.01); t += 0.05
a = d.evaluate(t)
check("원본을 지우고 .crypt 새 파일을 만드는 방식 → 위험 경보", a and a["level"] == "danger")
# --- 오탐이 없어야 하는 정상 작업들
d = det(head=lambda p: docx_head())
t = 1000.0
for p in paths(400, ext=".dat"):
    d.feed("created", p, t=t); d.feed("modified", p, t=t + 0.01); t += 0.01
check("압축 풀기·복사처럼 새 파일 400개를 만들고 쓰기 → 경보 없음", d.evaluate(t) is None)
d = det(head=lambda p: text_head())
t = 1000.0
for p in paths(80, ext=".py"):
    d.feed("modified", p, t=t); t += 0.05
check("글자 파일 80개의 서식을 바꿈(내용은 평범) → 경보 없음", d.evaluate(t) is None)
d = det(head=lambda p: b"\xff\xd8\xff" + rand_bytes(4000))
t = 1000.0
for p in paths(80, ext=".png"):
    d.feed("modified", p, t=t); d.feed("moved", p, p[:-4] + ".jpg", t=t + 0.01); t += 0.05
check("사진 80장을 .jpg 로 일괄 변환(흔한 확장자·정상 머리글) → 경보 없음", d.evaluate(t) is None)
d = det(head=lambda p: docx_head())
t = 1000.0
for p in paths(120, ext=".docx"):
    d.feed("moved", p, p.replace("Documents", "Pictures"), t=t); t += 0.02
check("폴더를 통째로 옮김(확장자 그대로) → 경보 없음", d.evaluate(t) is None)
d = det()
t = 1000.0
for p in paths(300, ext=".js"):
    d.feed("modified", r"C:\Users\x\Documents\proj\node_modules\a\%s" % os.path.basename(p), t=t); d.feed("modified", r"C:\Users\x\Documents\proj\.git\objects\%s" % os.path.basename(p), t=t); t += 0.01
check(".git·node_modules 안의 대량 변경은 세지 않음 → 경보 없음", d.evaluate(t) is None and not d.events)
d = det()
t = 1000.0
for i in range(100):
    d.feed("modified", r"C:\Users\x\Documents\a\f%d.tmp" % i, t=t); d.feed("created", r"C:\Users\x\Documents\a\~$f%d.docx" % i, t=t)
check("임시 파일(.tmp)·오피스 잠금 파일(~$) 은 세지 않음", d.evaluate(t) is None and not d.events)
d = det("strict", head=lambda p: text_head())
t = 1000.0
for p in paths(20, ext=".txt"):
    d.feed("modified", p, t=t); t += 0.1
check("민감도 '엄격'이어도 평범한 글자 파일 20개 수정은 경보 없음", d.evaluate(t) is None)
# 민감도별 문턱
for sens, expect in (("loose", False), ("normal", False), ("strict", True)):
    d = det(sens)
    t = 1000.0
    for p in paths(18):
        d.feed("modified", p, t=t); d.feed("moved", p, p + ".locked", t=t + 0.01); t += 0.05
    a = d.evaluate(t)
    check("민감도 %s: 18개 변경 → 경보 %s" % (sens, "있음" if expect else "없음"), bool(a) == expect)
# 몸값 안내 파일
d = det(head=lambda p: text_head())
t = 1000.0
for i in range(15):
    d.feed("modified", paths(15)[i], t=t); t += 0.1
for f in ROOTS:
    d.feed("created", f + r"\README_DECRYPT.txt", t=t)
a = d.evaluate(t)
check("몸값 안내 파일이 3개 폴더에 생기고 파일이 바뀌는 중 → 위험 경보", a and any("복구 안내" in r for r in a["reasons"]))
# 10초 창
d = det()
for i, p in enumerate(paths(60)):
    d.feed("modified", p, t=1000.0 + i * 1.0)
check("파일 변경이 1분에 걸쳐 천천히 일어나면(10초 창에 몇 개뿐) 경보 없음", d.evaluate(1060.0) is None)
# 머리글 판정
check("진짜 .docx 머리글은 정상", not R.looks_corrupt(".docx", docx_head()))
check("무작위 바이트의 .docx 는 깨진 것", R.looks_corrupt(".docx", rand_bytes()))
check("무작위 바이트의 .txt 는 깨진 것, 평범한 글은 정상", R.looks_corrupt(".txt", rand_bytes()) and not R.looks_corrupt(".txt", text_head()))
check("아주 짧은 파일은 판단 보류", not R.looks_corrupt(".docx", b"abc"))
# 미끼
tmp = Path(tempfile.mkdtemp())
(tmp / "Docs").mkdir()
can = R.Canaries(tmp / "canary.json")
made = can.ensure([tmp / "Docs"])
check("미끼 파일 2개 생성(숨김 속성)", len(made) == 2 and all(os.stat(m).st_file_attributes & 2 for m in made))
check("미끼는 진짜 .docx(zip) 형식", zipfile.is_zipfile(made[0]))
d = R.RansomDetector("normal", canaries=can, now_fn=lambda: 5000.0, roots=[str(tmp)])
check("미끼에 '만들기' 사건은 무시", d.feed("created", made[0], t=5000.0) is None)
check("내용이 그대로인 '수정' 사건(속성 변경 등)은 무시", d.feed("modified", made[0], t=5000.0) is None)
with open(made[0], "r+b") as _f:
    _f.write(rand_bytes(500))          # 숨김 파일은 덮어쓰기로 새로 만들 수 없어서 열어서 고친다
a = d.feed("modified", made[0], t=5001.0)
check("미끼 내용이 바뀌면 즉시 위험 경보 (파일 1개만으로)", a and a["level"] == "danger" and a["source"] == "canary")
check("   60초 안에 같은 미끼 경보는 되풀이하지 않음", d.feed("deleted", made[1], t=5002.0) is None)
a = d.feed("deleted", made[1], t=5100.0)
check("   60초 뒤에는 다시 경보 (미끼 삭제)", a and "지워졌" in a["reason"])
check("프로그램이 꺼져 있는 동안 바뀐 미끼를 시작할 때 찾아냄", len(can.tampered()) >= 1)
n = can.remove_all()
check("미끼 지우기는 우리가 만든 미끼만 지움 (%d개)" % n, not any(Path(m).exists() for m in made) and (tmp / "Docs").exists())
shutil.rmtree(tmp, ignore_errors=True)

# ----------------------------------------------------------------------------- B) 실제 파일 + 폴더 감시
print("== B) 실제 폴더 + 폴더 감시로 암호화 흉내 ==")
base = Path(tempfile.mkdtemp(prefix="sectest_"))
docs, pics = base / "Documents", base / "Pictures"
for d_ in (docs, pics):
    (d_ / "a").mkdir(parents=True)
    (d_ / "b").mkdir()


def encrypt(p, rename=True):
    """랜섬웨어 흉내: 숨김·읽기 전용 속성을 풀고 → 무작위 바이트로 덮어쓰고 → .locked 로 이름 변경 (실제 랜섬웨어가 흔히 하는 순서)."""
    import ctypes
    ctypes.windll.kernel32.SetFileAttributesW(str(p), 0x80)
    try:
        Path(p).write_bytes(os.urandom(3000))
    except PermissionError:
        return False                                     # 못 쓰는 파일은 건너뜀
    if rename:
        try:
            os.replace(p, str(p) + ".locked")
        except PermissionError:
            pass                                         # (감시가 파일을 읽는 순간과 겹치면 이름 변경이 막힐 수 있다 — 흉내 쪽은 그냥 넘어감)
    return True


def make_files(n=150):
    out = []
    for i in range(n):
        folder = [docs / "a", docs / "b", pics / "a", pics / "b"][i % 4]
        p = folder / ("문서%03d.docx" % i)
        with zipfile.ZipFile(p, "w") as z:
            z.writestr("word/document.xml", "<w>%s</w>" % ("가나다라마바사 " * 60))
        out.append(p)
    return out


files = make_files()
ev = SecEvents(base / "sec")
w = R.RansomWatcher(ev, [docs, pics], "normal", base / "canary.json", use_canary=True)
w.start()
time.sleep(1.5)
check("감시 시작: 폴더 2곳, 미끼 %d개" % len(w.canaries.files), len(w.canaries.files) == 4)
time.sleep(1.0)
check("   미끼를 만든 것 때문에 경보가 울리지 않음", not ev.items)
# 정상 작업 1: 대량 복사
shutil.copytree(docs, base / "복사본")
for p in (base / "복사본").rglob("*.docx"):
    pass
# 정상 작업 2: 압축 풀기
zp = base / "x.zip"
with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as z:
    for i in range(200):
        z.writestr("out/f%d.txt" % i, "내용 %d " % i * 20)
with zipfile.ZipFile(zp) as z:
    z.extractall(docs / "a")
# 정상 작업 3: 글자 파일 서식 바꾸기
txts = []
for i in range(80):
    p = docs / "b" / ("메모%d.txt" % i)
    p.write_text("회의 메모 " * 80, encoding="utf-8"); txts.append(p)
time.sleep(1.0)
for p in txts:
    p.write_text("회의 메모입니다 " * 80, encoding="utf-8")
time.sleep(14.0)
check("정상 작업(복사·압축 풀기·서식 바꾸기) 동안 경보 없음 (이벤트 %d건 처리)" % w.count, not ev.items)

# 암호화 흉내 (미끼 먼저: 폴더 안을 이름 순으로 걷는 랜섬웨어)
t0 = time.time()
n_done = 0
for p in sorted(docs.rglob("*"), key=lambda q: q.name):
    if p.is_file() and p.suffix == ".docx":
        encrypt(p)
        n_done += 1
        if ev.items:
            break
        time.sleep(0.01)
deadline = time.time() + 8
while not ev.items and time.time() < deadline:
    time.sleep(0.1)
lat = time.time() - t0
check("암호화 흉내 시작 후 경보 기록됨 (%.1f초, 건드린 파일 %d개)" % (lat, n_done), bool(ev.items))
a = ev.items[0] if ev.items else {}
check("   경보 단계 '위험', 종류 '랜섬웨어'", a.get("level") == "danger" and a.get("kind") == "ransom")
check("   미끼 파일이 먼저 걸림 (건드린 파일 %d개, 경보까지 %.2f초)" % (n_done, lat), a.get("data", {}).get("source") == "canary" and n_done <= 3 and lat < 1.0)
time.sleep(2.5)
check("   의심 프로그램 후보가 포함됨 (%s)" % [s["name"] for s in a.get("data", {}).get("suspects", [])][:3], isinstance(a.get("data", {}).get("suspects"), list))
check("   경보 문구에 할 일 안내가 있음", "인터넷" in a.get("text", ""))
check("   기록 파일에 저장됨", (base / "sec" / "events.json").exists())
w.stop()

# 미끼 없이 행동 감지만
shutil.rmtree(base, ignore_errors=True)
base = Path(tempfile.mkdtemp(prefix="sectest_"))
docs, pics = base / "Documents", base / "Pictures"
for d_ in (docs, pics):
    (d_ / "a").mkdir(parents=True)
    (d_ / "b").mkdir()
files = make_files(200)
ev = SecEvents(base / "sec")
w = R.RansomWatcher(ev, [docs, pics], "normal", None, use_canary=False)
w.start()
time.sleep(1.5)
t0 = time.time()
n_done = 0
for p in files:
    encrypt(p)
    n_done += 1
    if ev.items:
        break
    time.sleep(0.005)
deadline = time.time() + 12
while not ev.items and time.time() < deadline:
    time.sleep(0.1)
lat = time.time() - t0
check("미끼 없이 행동만으로 경보 (%.1f초, 건드린 파일 %d개)" % (lat, n_done), bool(ev.items) and ev.items[0]["data"].get("source") == "behavior")
check("   그때까지 건드린 파일이 전체(200개)의 절반 이하 (%d개, %.2f초)" % (n_done, lat), n_done <= 100)
w.stop()
shutil.rmtree(base, ignore_errors=True)
print("전체:", "모두 통과" if ok else "실패 있음")
sys.exit(0 if ok else 1)
