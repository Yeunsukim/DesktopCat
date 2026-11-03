"""고양이 소리: 냐옹(알림·경보·졸라대기·반응) + 행동에 맞는 소리(골골·채터링·트릴).

소리 파일(mp3)은 assets/sounds 에 둔다. mp3 는 윈도우 기본 재생기(MCI, winmm)로 틀어서 별도 라이브러리가 필요 없다.
 · meow.mp3     밥·놀아 달라고 졸라댈 때, 1시간마다 쉬라고 할 때, 일정·소식·메일 같은 알림, 경보. 파일 전체(약 10초)를 끝까지 튼다.
 · meow_2s.mp3  사용자가 고양이를 집어 올리거나 마우스(왼쪽·오른쪽)로 눌렀을 때의 반응 (약 2초, 전체).
 · golgol.mp3   잠잘 때(잠자기 1 동그랗게·2 옆으로. 식빵 자세로 턱 괴고 자는 3 은 뺀다)   · chatter.mp3  털실공 놀이·밥 먹기·종종걸음·나비잡기 놀이(달리기는 소리 없음)
 · trill.mp3    꾹꾹이·꼬리 가지고 놀기·쓰다듬기

**냐옹이 우선**: 냐옹(알림·경보·졸라대기·반응)이 나는 동안에는 행동 소리를 내지 않는다. 틀던 행동 소리는 바로 끊고, 냐옹 중에 시작한 행동의 소리는 냐옹이 끝난 뒤에도 늦게 틀지 않는다(소리가 겹쳐 들리지 않게).
행동 소리의 규칙 (sync): 행동이 **시작될 때 한 번만** 틀고, 소리가 남았어도 **행동이 끝나면 바로 끊는다**. 끝까지 계속 되풀이하지 않는다.
 · 사용자가 시킨 행동(밥 주기·놀아주기·쓰다듬기)은 바로 틀고, 저절로 하는 행동(잠·종종걸음·꾹꾹이 …)은 0.3초 이상 이어질 때 틀고 소리마다 쉬는 시간을 둔다.
 · 잠자는 시간·고양이가 멈춘 동안(자리 비움·전체 화면)·설정에서 끈 경우에는 행동 소리를 내지 않는다 (알림용 냐옹은 그대로).
**다른 PC 에서도 나게 (3단계)**: ① mp3 를 MCI 로 튼다. ② MCI 가 mp3 를 못 열거나(윈도우 N 판처럼 mp3 해독기가 없음·경로 문제) 틀다가 오류를 내면,
같은 이름의 wav(assets/sounds, tools/make_sound_wavs.py 가 만든다)를 메모리에서 읽어 PlaySound 로 소리마다 대신 튼다 (코덱·경로와 상관없이 소리 장치만 있으면 난다. 음량은 소리 데이터에 곱해서 맞춘다).
③ 그것도 안 되면 합성한 냐옹(meow.wav). 어느 단계로 났는지는 데이터 폴더의 sound_log.txt 에 남긴다 (파일 이름과 오류 문구만, 경로는 안 적는다).
"""
import ctypes
import io
import re
import threading
import time
import wave
from pathlib import Path

import numpy as np

RATE = 22050
# 소리 이름: (파일, 음량 0~1000, 같은 소리를 다시 틀기까지 쉬는 시간(초; 저절로 하는 행동에만))
# 음량은 파일마다 녹음 크기가 달라서(golgol 은 다른 것보다 약 9배 크다) 비슷하게 들리게 맞춘 값이다.
SOUNDS = {
    "meow": ("meow.mp3", 1000, 0.0),
    "meow2": ("meow_2s.mp3", 1000, 0.0),
    "golgol": ("golgol.mp3", 130, 60.0),
    "chatter": ("chatter.mp3", 1000, 10.0),
    "trill": ("trill.mp3", 850, 12.0),
}
MEOW_MAX = 12.0                 # 초: 냐옹 파일(약 10초)이 이보다 오래 날 수는 없다 (그 뒤에는 재생 상태를 묻지 않는다)
DEBOUNCE = 0.3                  # 초: 저절로 하는 행동이 이만큼 이어져야 소리를 낸다 (잠깐 스치는 동작에는 안 낸다)

_winmm = ctypes.windll.winmm
_winmm.mciSendStringW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint, ctypes.c_void_p]
_winmm.mciSendStringW.restype = ctypes.c_uint


class _Mci:
    """윈도우 MCI 로 mp3 를 튼다 (틀기는 기다리지 않고 바로 돌아온다). 화면 스레드에서만 부를 것."""

    def send(self, cmd: str) -> int:
        try:
            return int(_winmm.mciSendStringW(cmd, None, 0, None))
        except Exception:
            return 1

    def mode(self, alias: str) -> str:
        """재생 상태: 'playing' / 'stopped' / ... (알 수 없으면 빈 글자)."""
        try:
            buf = ctypes.create_unicode_buffer(64)
            if _winmm.mciSendStringW("status %s mode" % alias, buf, 63, None) == 0:
                return buf.value
        except Exception:
            pass
        return ""


def _mci_error(code: int) -> str:
    """MCI 오류 번호를 글로 (기록용)."""
    try:
        buf = ctypes.create_unicode_buffer(256)
        if _winmm.mciGetErrorStringW(code, buf, 255):
            return "%d %s" % (code, buf.value)
    except Exception:
        pass
    return str(code)


_SND_ASYNC, _SND_NODEFAULT, _SND_MEMORY, _SND_PURGE = 0x0001, 0x0002, 0x0004, 0x0040
_OPEN_RE = re.compile(r'open "(.*)" type \w+ alias (\S+)')


class _MemPlayer:
    """MCI 와 같은 명령(open/setaudio/play/stop/close, status mode)을 알아듣는 대신 재생기: wav 를 메모리에 읽어 두고 PlaySound(메모리)로 튼다.
    mp3 해독기·파일 경로와 상관없이 소리 장치만 있으면 난다. 한 번에 한 소리만 난다(고양이는 원래 한 번에 하나만 튼다). 음량은 소리 데이터에 곱한다."""

    def __init__(self):
        self.pcm = {}                 # 이름 -> (모노 16비트 numpy, 표본 속도)
        self.gain = {}                # 이름 -> 0~1
        self.cur = None               # 지금 나는 소리 이름
        self.end = 0.0                # 그 소리가 끝나는 시각 (PlaySound 는 끝났는지 알려 주지 않아서 길이로 센다)
        self._buf = None              # 틀고 있는 데이터 (PlaySound 가 비동기로 읽는 동안 살려 둬야 한다)

    def send(self, cmd: str) -> int:
        try:
            parts = cmd.split()
            if parts[0] == "open":
                m = _OPEN_RE.match(cmd)
                if not m:
                    return 1
                with wave.open(m.group(1), "rb") as w:
                    ch, rate, width = w.getnchannels(), w.getframerate(), w.getsampwidth()
                    raw = w.readframes(w.getnframes())
                if width != 2:
                    return 1
                a = np.frombuffer(raw, dtype="<i2").reshape(-1, ch).astype(np.float32).mean(axis=1)
                self.pcm[m.group(2)], self.gain[m.group(2)] = (a, rate), 1.0
                return 0
            name = parts[1]
            if parts[0] == "setaudio":
                self.gain[name] = max(0.0, min(1.0, int(parts[-1]) / 1000.0))
                return 0
            if parts[0] == "play":
                return self._play(name)
            if parts[0] in ("stop", "close"):
                if self.cur == name:
                    self._purge()
                if parts[0] == "close":
                    self.pcm.pop(name, None)
                return 0
        except Exception:
            return 1
        return 1

    def _play(self, name: str) -> int:
        if name not in self.pcm:
            return 1
        a, rate = self.pcm[name]
        pcm = np.clip(a * self.gain.get(name, 1.0), -32768, 32767).astype("<i2")
        bio = io.BytesIO()
        with wave.open(bio, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(rate)
            w.writeframes(pcm.tobytes())
        self._buf = ctypes.create_string_buffer(bio.getvalue())          # (이전 소리는 새 소리를 틀면 알아서 끊긴다)
        if not _winmm.PlaySoundW(self._buf, None, _SND_MEMORY | _SND_ASYNC | _SND_NODEFAULT):
            return 1
        self.cur, self.end = name, time.monotonic() + len(a) / rate
        return 0

    def _purge(self):
        try:
            _winmm.PlaySoundW(None, None, _SND_PURGE)
        except Exception:
            pass
        self.cur = None

    def mode(self, alias: str) -> str:
        return "playing" if self.cur == alias and time.monotonic() < self.end else "stopped"


class _Router:
    """소리마다 재생기를 고른다: 기본은 MCI(mp3). MCI 가 못 열거나 틀다가 오류를 내면 그 소리만 메모리 재생기(wav)로 넘긴다."""

    def __init__(self, mci, mem, log):
        self.mci, self.mem, self.log = mci, mem, log
        self.route = {}               # 별칭 -> 재생기
        self.wavs = {}                # 별칭 -> 대신 쓸 wav 경로
        self.vol = {}                 # 별칭 -> 마지막으로 정한 음량 (재생기를 바꿀 때 그대로 넘긴다)

    def open(self, alias: str, mp3, wav, name: str) -> bool:
        """mp3 → wav 순서로 열어 본다. 열리면 True."""
        if mp3 is not None:
            r = self.mci.send('open "%s" type mpegvideo alias %s' % (mp3, alias))
            if r == 0:
                self.route[alias] = self.mci
                if wav is not None:
                    self.wavs[alias] = wav
                self.log("%s: mp3(MCI) 열림" % name)
                return True
            self.log("%s: mp3(MCI) 못 엶 — %s" % (name, _mci_error(r)))
        return self._to_mem(alias, wav, name)

    def _to_mem(self, alias: str, wav, name: str) -> bool:
        if wav is not None and self.mem.send('open "%s" type waveaudio alias %s' % (wav, alias)) == 0:
            self.route[alias] = self.mem
            self.log("%s: wav(메모리 재생)로 대신함" % name)
            return True
        self.log("%s: wav 도 못 엶 → 소리 없음" % name)
        return False

    def send(self, cmd: str) -> int:
        parts = cmd.split()
        dev = self.route.get(parts[1], self.mci) if len(parts) > 1 else self.mci
        if parts[0] == "setaudio":
            self.vol[parts[1]] = parts[-1]
        r = dev.send(cmd)
        if r != 0 and parts[0] == "play" and dev is self.mci and parts[1] in self.wavs:
            self.log("%s: mp3(MCI) 재생 오류 — %s" % (parts[1][4:], _mci_error(r)))
            if self._to_mem(parts[1], self.wavs[parts[1]], parts[1][4:]):          # 틀다가 안 되면 이 소리부터 wav 로 바꿔서 바로 다시 튼다
                self.mem.send("setaudio %s volume to %s" % (parts[1], self.vol.get(parts[1], "1000")))
                return self.mem.send(cmd)
        return r

    def mode(self, alias: str) -> str:
        return self.route.get(alias, self.mci).mode(alias)


def synth_meow(path: Path):
    """'냐~옹' 모양의 울음소리를 합성한다 (mp3 가 없을 때 쓰는 예비): 음높이가 올라갔다 내려오고, 입이 열리는 만큼 밝은 소리가 늘어난다."""
    dur = 0.75
    n = int(RATE * dur)
    t = np.arange(n) / RATE
    u = t / dur
    fall = np.clip((u - 0.62) / 0.38, 0, 1)
    f0 = 330 + 520 * np.sin(np.pi * np.clip(u / 0.62, 0, 1)) ** 1.4 * (1.0 - 0.55 * fall ** 1.2)
    f0 *= 1 + 0.012 * np.sin(2 * np.pi * 6.0 * t)
    phase = 2 * np.pi * np.cumsum(f0) / RATE
    formant = 700 + 1500 * np.sin(np.pi * np.clip(u / 0.5, 0, 1)) - 500 * np.clip((u - 0.55) / 0.45, 0, 1)
    sig = np.zeros(n)
    for h in range(1, 14):
        freq = f0 * h
        amp = np.exp(-0.5 * ((freq - formant) / 650.0) ** 2) / h ** 0.6
        sig += amp * np.sin(h * phase)
    sig += 0.02 * np.random.default_rng(3).standard_normal(n) * np.exp(-0.5 * ((u - 0.15) / 0.1) ** 2)
    env = np.minimum(1.0, u / 0.08) * np.minimum(1.0, (1.0 - u) / 0.22) ** 1.2
    sig *= env
    sig = sig / (np.abs(sig).max() + 1e-9) * 0.7
    pcm = (sig * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(pcm.tobytes())


class CatSound:
    def __init__(self, assets_dir: Path, data_dir: Path, backend=None):
        """backend: MCI 흉내(시험용). 없으면 윈도우 MCI."""
        assets_dir, data_dir = Path(assets_dir), Path(data_dir)
        self.logs = []                            # 어떤 방식으로 소리가 났는지/안 났는지 (데이터 폴더 sound_log.txt)
        self.router = None
        if backend is None:
            self.router = _Router(_Mci(), _MemPlayer(), self.logs.append)
        self.mci = backend or self.router
        self.enabled = True                       # 행동 소리를 낼까 (설정). 알림 냐옹은 늘 낸다
        self.master = 1.0                         # 전체 음량 0~1 (설정)
        self.open = {}                            # 소리 이름 -> 열린 MCI 이름
        self._cur = None                          # 지금 틀고 있는 행동 소리
        self._want = None                         # 지금 해야 하는 행동의 소리
        self._want_since = 0.0
        self._played = False                      # 이 행동 동안 이미 틀었나 (한 번만)
        self._last_start = {}                     # 소리 이름 -> 마지막으로 튼 시각
        self._meow_t0 = -1e9                      # 냐옹을 튼 시각 (냐옹이 나는 동안 행동 소리를 막는 데 쓴다)
        sdir = [assets_dir / "sounds", assets_dir, assets_dir.parent]
        for name, (fname, _vol, _gap) in SOUNDS.items():
            path = next((d / fname for d in sdir if (d / fname).exists()), None)
            wav = next((d / Path(fname).with_suffix(".wav").name for d in sdir[:1] if (d / Path(fname).with_suffix(".wav").name).exists()), None)
            if self.router is not None:
                if self.router.open("cat_" + name, path, wav, name):
                    self.open[name] = "cat_" + name
            elif path is not None and self.mci.send('open "%s" type mpegvideo alias cat_%s' % (path, name)) == 0:
                self.open[name] = "cat_" + name
        if self.router is not None:
            self._write_log(data_dir)
        self.wav = None                           # 냐옹 예비(mp3 가 없을 때): assets/meow.wav, 없으면 합성
        if "meow" not in self.open:
            p = assets_dir / "meow.wav"
            if not p.exists():
                p = data_dir / "meow.wav"
                if not p.exists():
                    try:
                        synth_meow(p)
                    except Exception:
                        p = None
            self.wav = p

    def _write_log(self, data_dir: Path):
        """소리가 안 나는 PC 를 살펴볼 수 있게 어떤 방식으로 열렸는지 적는다 (파일 이름과 오류 문구만, 경로는 안 적는다)."""
        try:
            Path(data_dir).mkdir(parents=True, exist_ok=True)
            head = "%s  소리 장치 점검 (mp3 는 MCI, 안 되면 wav 를 메모리에서 재생)\n" % time.strftime("%Y-%m-%d %H:%M:%S")
            (Path(data_dir) / "sound_log.txt").write_text(head + "\n".join(self.logs) + "\n", encoding="utf-8")
        except Exception:
            pass

    # --- 설정 -----------------------------------------------------------
    def configure(self, cfg: dict):
        """설정(care.sound: {"enabled", "volume"(0~100)})을 반영한다."""
        cfg = cfg or {}
        self.enabled = bool(cfg.get("enabled", True))
        try:
            self.master = max(0.0, min(1.0, float(cfg.get("volume", 80)) / 100.0))
        except (TypeError, ValueError):
            self.master = 0.8
        if not self.enabled:
            self._stop_current()

    # --- 틀기·끊기 ---------------------------------------------------------
    def _play(self, name: str, now: float):
        alias = self.open.get(name)
        if not alias:
            return False
        vol = int(SOUNDS[name][1] * self.master)
        self.mci.send("setaudio %s volume to %d" % (alias, vol))
        self.mci.send("play %s from 0" % alias)
        self._last_start[name] = now
        return True

    def _stop(self, name: str):
        alias = self.open.get(name)
        if alias:
            self.mci.send("stop %s" % alias)

    def _stop_current(self):
        if self._cur:
            self._stop(self._cur)
            self._cur = None

    # --- 냐옹 ---------------------------------------------------------------------
    def _once(self, name: str) -> bool:
        """name 소리를 처음부터 끝까지 한 번 튼다. 같은 소리가 아직 나는 중이면 겹쳐 틀거나 끊고 다시 틀지 않고 그대로 둔다. 소리를 낼 수 있으면 True."""
        alias = self.open.get(name)
        if not alias:
            return False
        if self.mci.mode(alias) == "playing":
            return True
        return self._play(name, time.monotonic())

    def _meow_busy(self, now: float, alert_only: bool = False) -> bool:
        """냐옹이 지금 나는 중인가 (alert_only: 알림 냐옹 meow.mp3 만 본다)."""
        if now - self._meow_t0 > MEOW_MAX:
            return False
        names = ("meow",) if alert_only else ("meow", "meow2")
        return any(self.mci.mode(self.open[n]) == "playing" for n in names if n in self.open)

    def meow(self, times=1):
        """알림·경보·졸라대기의 냐옹: meow.mp3 를 전체(약 10초) 끝까지 튼다 (times 는 예전 호출과 맞추려고 받기만 한다).
        냐옹이 먼저라서, 나던 행동 소리와 반응 냐옹은 끊고 튼다. 실패해도(소리 장치가 없는 컴퓨터 등) 조용히 넘어간다. mp3 가 없으면 합성한 냐옹(wav)으로 대신한다."""
        if "meow" in self.open:
            self._stop_current()
            self._stop("meow2")
            self._once("meow")
            self._meow_t0 = time.monotonic()
        elif self.wav:
            threading.Thread(target=self._play_wav, args=(times,), daemon=True).start()      # 소리 장치를 처음 열 때 0.2초쯤 걸려서 화면 스레드에서 하지 않는다

    def react(self):
        """사용자가 고양이를 집어 올리거나 마우스로 눌렀을 때의 반응 냐옹: meow_2s.mp3 를 전체(약 2초) 튼다. 이미 나는 중이거나 알림 냐옹이 나는 중이면 겹치지 않는다."""
        if "meow2" not in self.open or self._meow_busy(time.monotonic(), alert_only=True):
            return
        self._stop_current()
        self._once("meow2")
        self._meow_t0 = time.monotonic()

    def _play_wav(self, times=1):
        try:
            import winsound
            for i in range(max(1, times)):
                if i:
                    time.sleep(0.25)
                winsound.PlaySound(str(self.wav), winsound.SND_FILENAME | winsound.SND_NODEFAULT)
        except Exception:
            pass

    # --- 행동 소리 ---------------------------------------------------------------
    def sync(self, want, now: float, interactive: bool = False, allowed: bool = True):
        """프레임마다 부른다. want: 지금 하는 행동에 맞는 소리 이름 또는 None.
        interactive: 사용자가 시킨 행동인가 (바로 틀고 쉬는 시간이 없다). allowed: False 면(잠자는 시간·멈춘 동안) 소리를 내지 않는다."""
        if not allowed or not self.enabled or want not in self.open:
            want = None
        if self._meow_busy(now):                    # 냐옹이 나는 동안은 행동 소리를 내지 않는다 (끊고, 이 행동의 소리는 냐옹이 끝나도 늦게 틀지 않는다)
            self._stop_current()
            self._want, self._want_since, self._played = want, now, True
            return
        if want != self._want:                      # 하는 행동이 바뀌었다: 틀던 소리가 이 행동의 소리가 아니면 남았어도 바로 끊는다
            self._want, self._want_since, self._played = want, now, False
            if self._cur and self._cur != want:
                self._stop_current()
        if want is None or self._played:
            return                                  # 이 행동 동안 이미 한 번 틀었다: 되풀이하지 않는다
        if not interactive:
            if now - self._want_since < DEBOUNCE:
                return
            if now - self._last_start.get(want, -1e9) < SOUNDS[want][2]:
                self._played = True                 # 쉬는 시간 안이다: 이 행동에서는 아예 안 낸다 (끝나기 직전에 뒤늦게 내지 않게)
                return
        self._played = True
        if self._play(want, now):
            self._cur = want

    def tick(self, now: float):
        """(프레임 루프에서 부른다. 냐옹은 틀어 두면 끝까지 나므로 할 일이 없다.)"""

    def close(self):
        for name, alias in list(self.open.items()):
            self.mci.send("stop %s" % alias)
            self.mci.send("close %s" % alias)
        self.open = {}
        self._cur = None
