"""고양이 소리 규칙 점검: 가짜 재생기(MCI 흉내)로 '언제 틀고 언제 끊는지'를 확인한다. 실제 소리는 내지 않는다.

    python tools/test_catsound.py

 1) 행동이 시작되면 한 번만 튼다 (소리가 끝나도, 행동이 계속돼도 되풀이하지 않는다)
 2) 행동이 끝나면(바뀌면) 남은 소리를 바로 끊는다
 3) 저절로 하는 행동은 0.3초 이상 이어질 때 틀고, 소리마다 쉬는 시간을 지킨다. 사용자가 시킨 행동은 바로 튼다
 4) 잠자는 시간·멈춘 동안·설정에서 끄면 행동 소리를 내지 않는다. 알림 냐옹은 그대로
 5) 알림·경보·졸라대기 냐옹(meow.mp3)은 **전체를 끝까지** 튼다 (자르지 않고, 나는 중이면 겹치지 않는다)
 6) 고양이를 누르거나 집어 올리면 meow_2s.mp3 를 전체 튼다 (나는 중이면 겹치지 않는다)
 7) 냐옹이 우선: 냐옹이 나는 동안에는 행동 소리를 내지 않고, 나던 행동 소리는 끊고, 냐옹 중에 시작한 행동은 끝난 뒤에도 늦게 틀지 않는다
 8) 다른 PC 대비: MCI 가 mp3 를 못 열거나 틀다가 오류를 내도 wav(메모리 재생)로 대신 나고, 한글·긴 경로에서도 열리며, 이유를 sound_log.txt 에 남긴다
"""
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import catsound as C  # noqa: E402

FAILS = []


def check(name, ok, info=""):
    print(("  통과  " if ok else "  실패  ") + name + ("  — " + info if info else ""))
    if not ok:
        FAILS.append(name)


class Fake:
    def __init__(self):
        self.log = []
        self.playing = set()

    def send(self, cmd):
        self.log.append(cmd)
        parts = cmd.split()
        if parts[0] == "play":
            self.playing.add(parts[1])
        elif parts[0] in ("stop", "close"):
            self.playing.discard(parts[1])
        return 0

    def mode(self, alias):
        return "playing" if alias in self.playing else "stopped"

    def finish(self, name):
        """소리가 끝까지 나서 저절로 멈췄다."""
        self.playing.discard("cat_" + name)

    def plays(self, name=None):
        return [c for c in self.log if c.startswith("play ") and (name is None or c.split()[1] == "cat_" + name)]

    def stops(self, name):
        return [c for c in self.log if c == "stop cat_" + name]


def make():
    fake = Fake()
    d = Path(tempfile.mkdtemp())
    s = C.CatSound(d, d, backend=fake)
    # 파일이 없는 시험 폴더라서 열린 소리가 없다: 열린 것처럼 만든다
    for n in C.SOUNDS:
        s.open[n] = "cat_" + n
    fake.log.clear()
    return s, fake


def run(s, want_by_time, seconds, dt=0.042, interactive=False, allowed=lambda t: True):
    t = 0.0
    while t < seconds:
        s.sync(want_by_time(t), 100.0 + t, interactive, allowed(t))
        s.tick(100.0 + t)
        t += dt


def main():
    print("== 1) 한 번만 틀기 ==")
    s, f = make()
    run(s, lambda t: "golgol", 40.0)
    check("잠을 40초 자도 골골은 한 번만", len(f.plays("golgol")) == 1, str(len(f.plays("golgol"))))
    check("  처음부터(from 0) 틀고 음량을 정함", f.plays("golgol")[0] == "play cat_golgol from 0" and any("setaudio cat_golgol volume" in c for c in f.log))

    print("== 2) 행동이 끝나면 바로 끊기 ==")
    s, f = make()
    run(s, lambda t: "chatter" if t < 3.0 else None, 6.0, interactive=True)
    check("행동이 끝나면 남은 소리를 끊음", len(f.stops("chatter")) >= 1 and f.log.index("stop cat_chatter") > f.log.index("play cat_chatter from 0"))
    check("  끝난 뒤 다시 틀지 않음", len(f.plays("chatter")) == 1)
    s, f = make()
    run(s, lambda t: "trill" if t < 2 else "chatter", 4.0, interactive=True)
    check("다른 행동 소리로 바뀌면 앞 소리는 끊고 새 소리를 틈", len(f.stops("trill")) == 1 and len(f.plays("chatter")) == 1)

    print("== 3) 시작 규칙 ==")
    s, f = make()
    run(s, lambda t: "chatter" if t < 0.2 else None, 1.0)
    check("저절로 하는 행동이 0.3초도 안 되면 소리 없음", len(f.plays()) == 0)
    s, f = make()
    run(s, lambda t: "chatter", 0.2, interactive=True)
    check("사용자가 시킨 행동은 바로 틈", len(f.plays("chatter")) == 1)
    s, f = make()
    run(s, lambda t: "chatter" if (t % 8.0) < 4.0 else None, 30.0)
    n = len(f.plays("chatter"))
    check("저절로 하는 행동은 쉬는 시간(10초)을 지킴 (30초 동안 4초씩 4번 해도 %d번만)" % n, n == 2 or n == 3, str(n))
    s, f = make()
    run(s, lambda t: "golgol" if (t % 20.0) < 10.0 else None, 130.0)
    check("골골은 60초에 한 번보다 자주 내지 않음", len(f.plays("golgol")) <= 3, str(len(f.plays("golgol"))))

    print("== 4) 내지 않는 때 ==")
    s, f = make()
    run(s, lambda t: "golgol", 5.0, allowed=lambda t: False)
    check("잠자는 시간·멈춘 동안(allowed=False)에는 행동 소리 없음", len(f.plays()) == 0)
    s, f = make()
    run(s, lambda t: "golgol", 3.0, allowed=lambda t: t < 1.0 or t > 2.0)
    check("tick 중에 허용이 끊기면 틀던 소리를 바로 끊음", len(f.stops("golgol")) >= 1)
    s, f = make()
    s.configure({"enabled": False, "volume": 80})
    run(s, lambda t: "chatter", 3.0, interactive=True)
    s.meow()
    check("설정에서 끄면 행동 소리 없음, 알림 냐옹은 냄", len(f.plays("chatter")) == 0 and len(f.plays("meow")) == 1)
    s, f = make()
    s.configure({"enabled": True, "volume": 40})
    run(s, lambda t: "trill", 0.2, interactive=True)
    vol = [c for c in f.log if c.startswith("setaudio cat_trill")][0]
    check("전체 음량 40% 가 반영됨 (850 × 0.4 = 340)", vol.endswith("340"), vol)
    s, f = make()
    s.configure({"enabled": True, "volume": 70})
    run(s, lambda t: "chatter", 0.2, interactive=True)
    s.configure({"enabled": False})
    check("설정을 끄는 순간 틀던 행동 소리도 끊음", len(f.stops("chatter")) == 1)

    print("== 5) 알림·경보·졸라대기 냐옹: 전체 재생 ==")
    s, f = make()
    s.meow(2)
    check("냐옹을 바로 틈 (meow.mp3, 처음부터)", f.plays("meow") == ["play cat_meow from 0"])
    now = time.monotonic()
    for k in range(0, 400):
        s.tick(now + 0.05 * k)
    check("20초가 지나도 중간에 끊지 않음 (stop 없음: 파일 전체를 끝까지)", len(f.stops("meow")) == 0)
    s.meow()
    check("나는 중에 또 부르면 끊고 다시 틀거나 겹치지 않음", len(f.plays("meow")) == 1)
    f.finish("meow")
    s.meow()
    check("끝난 뒤에는 다음 알림에 다시 틈", len(f.plays("meow")) == 2)
    check("meow(2) 라고 해도 두 번 따로 틀지 않고 파일 전체를 한 번만", len(f.plays("meow")) == 2)

    print("== 6) 누르거나 집어 올릴 때 반응 냐옹 ==")
    s, f = make()
    s.react()
    check("meow_2s.mp3 를 처음부터 틈", f.plays("meow2") == ["play cat_meow2 from 0"] and len(f.plays("meow")) == 0)
    s.react()
    check("눌렀다가 바로 집어 올려도(나는 중) 겹치지 않음", len(f.plays("meow2")) == 1)
    f.finish("meow2")
    s.react()
    check("끝난 뒤에 다시 누르면 또 틈", len(f.plays("meow2")) == 2)
    s.configure({"enabled": False, "volume": 80})
    f.finish("meow2")
    s.react()
    s.meow()
    check("행동 소리를 꺼도 반응·알림 냐옹은 냄", len(f.plays("meow2")) == 3 and len(f.plays("meow")) == 1)

    print("== 7) 냐옹이 우선 (소리가 겹치지 않게) ==")
    s, f = make()
    t0 = time.monotonic()
    s.sync("chatter", t0, True, True)
    check("(준비) 행동 소리(채터링)가 나는 중", f.plays("chatter") == ["play cat_chatter from 0"])
    s.meow()
    check("알림 냐옹을 틀면 나던 행동 소리를 바로 끊음", len(f.stops("chatter")) == 1 and len(f.plays("meow")) == 1)
    s.sync("chatter", t0 + 0.5, True, True)
    s.sync("trill", t0 + 1.0, True, True)
    check("냐옹이 나는 동안 새 행동 소리도 내지 않음", len(f.plays("chatter")) == 1 and len(f.plays("trill")) == 0)
    f.finish("meow")
    s.sync("trill", t0 + 12.0, True, True)
    check("냐옹 중에 시작한 행동의 소리는 냐옹이 끝난 뒤에도 늦게 틀지 않음", len(f.plays("trill")) == 0)
    s.sync(None, t0 + 13.0, True, True)
    s.sync("chatter", t0 + 14.0, True, True)
    check("냐옹이 끝난 뒤 새로 시작한 행동은 다시 소리를 냄", len(f.plays("chatter")) == 2)
    s, f = make()
    s.meow()
    s.react()
    check("알림 냐옹이 나는 중에는 반응 냐옹(meow_2s)을 틀지 않음", len(f.plays("meow2")) == 0)
    s, f = make()
    s.react()
    s.meow()
    check("반응 냐옹이 나는 중에 알림이 오면 반응은 끊고 알림을 틂", len(f.stops("meow2")) == 1 and len(f.plays("meow")) == 1)
    s, f = make()
    s.react()
    now = time.monotonic()
    s.sync("chatter", now, True, True)
    check("반응 냐옹이 나는 동안에도 행동 소리는 내지 않음", len(f.plays("chatter")) == 0)

    s.close()
    check("끝낼 때 모든 소리를 닫음", all(("close cat_" + n) in f.log for n in C.SOUNDS))

    print("== 8) 다른 PC 에서도 나게: mp3 가 안 되면 wav 로 대신 ==")

    class BadMci:
        """mp3 해독기가 없는 PC 흉내: 열기는 되는데 틀기가 오류, 또는 열기부터 오류."""

        def __init__(self, fail_open):
            self.fail_open, self.log = fail_open, []

        def send(self, cmd):
            self.log.append(cmd)
            if cmd.startswith("open"):
                return 275 if self.fail_open else 0
            if cmd.startswith("play"):
                return 296
            return 0

        def mode(self, alias):
            return "stopped"

    class FakeMem:
        def __init__(self):
            self.log, self.cur = [], None

        def send(self, cmd):
            self.log.append(cmd)
            if cmd.startswith("play"):
                self.cur = cmd.split()[1]
            return 0

        def mode(self, alias):
            return "playing" if self.cur == alias else "stopped"

    notes = []
    r = C._Router(BadMci(True), FakeMem(), notes.append)
    ok = r.open("cat_meow", Path("x/meow.mp3"), Path("x/meow.wav"), "meow")
    check("MCI 가 mp3 를 못 열면 wav(메모리 재생)로 열림", ok and r.route["cat_meow"] is r.mem and any("못 엶" in n for n in notes))
    r.send("play cat_meow from 0")
    check("그 뒤 틀기는 메모리 재생기로 감", any(c.startswith("play") for c in r.mem.log) and r.mode("cat_meow") == "playing")
    ok2 = C._Router(BadMci(True), FakeMem(), notes.append).open("cat_x", Path("x/a.mp3"), None, "x")
    check("wav 도 없으면 열리지 않음(소리 없음, 죽지 않음)", ok2 is False)

    notes.clear()
    bad = BadMci(False)
    r = C._Router(bad, FakeMem(), notes.append)
    r.open("cat_trill", Path("x/trill.mp3"), Path("x/trill.wav"), "trill")
    r.send("setaudio cat_trill volume to 425")
    rc = r.send("play cat_trill from 0")
    check("mp3 는 열렸지만 틀다가 오류면 그 소리를 wav 로 바꿔 바로 다시 틂", rc == 0 and r.route["cat_trill"] is r.mem and r.mode("cat_trill") == "playing")
    check("바꿀 때 정해 둔 음량(425)을 그대로 넘김", any(c == "setaudio cat_trill volume to 425" for c in r.mem.log))
    check("오류 이유를 기록함 (MCI 오류 번호 포함)", any("재생 오류" in n and "296" in n for n in notes))

    # 진짜 재생기(메모리): 음량 0 으로 틀어서 소리는 내지 않고 동작만 확인
    mem = C._MemPlayer()
    snd = Path(C.__file__).resolve().parent / "assets" / "sounds"
    opened = [n for n in C.SOUNDS if mem.send('open "%s" type waveaudio alias cat_%s' % (snd / Path(C.SOUNDS[n][0]).with_suffix(".wav").name, n)) == 0]
    check("5개 소리의 wav 를 모두 읽음", len(opened) == len(C.SOUNDS), "%d/%d" % (len(opened), len(C.SOUNDS)))
    mem.send("setaudio cat_meow2 volume to 0")
    check("틀면 소리가 나는 중(playing)으로 보임", mem.send("play cat_meow2 from 0") == 0 and mem.mode("cat_meow2") == "playing")
    mem.send("stop cat_meow2")
    check("끊으면 멈춤(stopped)", mem.mode("cat_meow2") == "stopped")
    a, rate = mem.pcm["cat_meow2"]
    check("meow_2s 는 약 1.8초", 1.5 < len(a) / rate < 2.1, "%.2f초" % (len(a) / rate))
    mem.send("play cat_meow2 from 0")
    mem.end = time.monotonic() - 1
    check("길이만큼 지나면 저절로 끝난 것으로 봄", mem.mode("cat_meow2") == "stopped")
    mem.send("stop cat_meow2")

    # 진짜 CatSound: 이 PC 에서 MCI 가 mp3 를 못 여는 것처럼 만들어 본다
    orig = C._Mci.send
    C._Mci.send = lambda self, cmd: 275 if cmd.startswith("open") else orig(self, cmd)
    try:
        d = Path(tempfile.mkdtemp())
        s = C.CatSound(Path(C.__file__).resolve().parent / "assets", d)
        s.configure({"enabled": True, "volume": 0})
        check("MCI 가 mp3 를 못 열어도 5개 소리가 모두 준비됨", len(s.open) == len(C.SOUNDS), "%d/%d" % (len(s.open), len(C.SOUNDS)))
        s.meow()
        check("알림 냐옹이 wav 로 남 (나는 중)", s.mci.mode("cat_meow") == "playing")
        log = (d / "sound_log.txt").read_text(encoding="utf-8")
        check("sound_log.txt 에 이유와 대체 방식이 적힘", "못 엶" in log and "wav(메모리 재생)" in log)
        check("기록에 폴더 경로는 안 적힘", "Users" not in log and ":\\" not in log)
        s.close()
    finally:
        C._Mci.send = orig

    # 진짜 CatSound: 한글·긴 폴더 경로 (이 경로에서도 최소한 wav 로 열려야 한다)
    top = Path(tempfile.mkdtemp())
    base = top / ("한글폴더 이름_" * 6) / "고양이 프로그램" / "assets"
    (base / "sounds").mkdir(parents=True)
    import shutil
    for f in (Path(C.__file__).resolve().parent / "assets" / "sounds").glob("*"):
        shutil.copy(f, base / "sounds" / f.name)
    d2 = Path(tempfile.mkdtemp())
    s = C.CatSound(base, d2)
    s.configure({"enabled": True, "volume": 0})
    check("한글·긴 경로(%d자)에서도 5개 소리가 준비됨" % len(str(base)), len(s.open) == len(C.SOUNDS), "%d/%d" % (len(s.open), len(C.SOUNDS)))
    s.meow()
    check("그 경로에서도 냐옹이 남", s.mci.mode("cat_meow") == "playing")
    s.close()
    shutil.rmtree(top, ignore_errors=True)


    print()
    print("모두 통과" if not FAILS else "실패 %d건: %s" % (len(FAILS), ", ".join(FAILS)))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
