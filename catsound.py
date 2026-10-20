"""고양이 울음소리 "냐옹~" 재생.

assets/meow.wav 가 있으면 그것을 쓴다(진짜 고양이 소리 wav 를 넣으면 바뀐다). 없으면 numpy 로 간단한 울음소리를 합성해서
데이터 폴더에 meow.wav 로 한 번 만들어 두고 쓴다. 재생은 winsound(윈도우 기본)를 별도 스레드에서 해서 고양이 움직임을 막지 않는다.
"""
import threading
import wave
from pathlib import Path

import numpy as np

RATE = 22050


def synth_meow(path: Path):
    """'냐~옹' 모양의 울음소리를 합성한다: 음높이가 올라갔다 내려오고, 입이 열리는 만큼 밝은 소리가 늘어난다."""
    dur = 0.75
    n = int(RATE * dur)
    t = np.arange(n) / RATE
    u = t / dur
    # 음높이(Hz): 낮게 시작 → 위로 솟음 → 천천히 내려옴 (+ 가벼운 떨림)
    fall = np.clip((u - 0.62) / 0.38, 0, 1)                      # 0.62 이후 내려오는 정도 0~1
    f0 = 330 + 520 * np.sin(np.pi * np.clip(u / 0.62, 0, 1)) ** 1.4 * (1.0 - 0.55 * fall ** 1.2)
    f0 *= 1 + 0.012 * np.sin(2 * np.pi * 6.0 * t)
    phase = 2 * np.pi * np.cumsum(f0) / RATE
    # 입 모양에 따른 밝기(포먼트): 'ㄴ'(닫힘)에서 'ㅑ'(열림)로, 다시 'ㅗ'로
    formant = 700 + 1500 * np.sin(np.pi * np.clip(u / 0.5, 0, 1)) - 500 * np.clip((u - 0.55) / 0.45, 0, 1)
    sig = np.zeros(n)
    for h in range(1, 14):
        freq = f0 * h
        amp = np.exp(-0.5 * ((freq - formant) / 650.0) ** 2) / h ** 0.6
        sig += amp * np.sin(h * phase)
    sig += 0.02 * np.random.default_rng(3).standard_normal(n) * np.exp(-0.5 * ((u - 0.15) / 0.1) ** 2)   # 처음의 숨소리
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
    def __init__(self, assets_dir: Path, data_dir: Path):
        self.path = Path(assets_dir) / "meow.wav"
        if not self.path.exists():
            self.path = Path(data_dir) / "meow.wav"
            if not self.path.exists():
                try:
                    synth_meow(self.path)
                except Exception:
                    self.path = None

    def meow(self, times=1):
        """울음소리를 비동기로 재생한다 (times=2 면 '냐옹~ 냐옹~'). 실패해도(소리 장치가 없는 컴퓨터 등) 조용히 넘어간다."""
        if not self.path:
            return
        threading.Thread(target=self._play, args=(times,), daemon=True).start()      # 소리 장치를 처음 열 때 0.2초쯤 걸려서 화면 스레드에서 하지 않는다

    def _play(self, times=1):
        try:
            import time
            import winsound
            for i in range(max(1, times)):
                if i:
                    time.sleep(0.25)                      # 울음 사이의 짧은 쉼
                winsound.PlaySound(str(self.path), winsound.SND_FILENAME | winsound.SND_NODEFAULT)       # 동기 재생: 이 스레드가 소리가 끝날 때까지 기다린다(화면은 안 멈춘다)
        except Exception:
            pass
