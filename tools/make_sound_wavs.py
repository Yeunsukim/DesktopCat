"""assets/sounds 의 mp3 를 같은 이름의 wav(모노, 16비트)로 바꿔 둔다.

    pip install miniaudio        (이 변환에만 필요한 개발용 도구. 고양이 프로그램에는 필요 없다)
    python tools/make_sound_wavs.py

왜 wav 가 또 필요한가: 고양이는 mp3 를 윈도우 MCI 로 틀지만, 윈도우 N 판처럼 mp3 해독기가 없거나 MCI 가 경로를 못 여는 PC 에서는 소리가 안 난다.
그럴 때 catsound.py 가 이 wav 를 메모리에서 읽어 PlaySound 로 대신 튼다(코덱·경로와 상관없이 소리 장치만 있으면 난다).
용량을 줄이려고 모노로 섞는다 (고양이 소리는 스테레오 효과가 필요 없다).
"""
import sys
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
SOUNDS = ROOT / "assets" / "sounds"


def main():
    try:
        import miniaudio
    except ImportError:
        print("miniaudio 가 없습니다: pip install miniaudio")
        return 1
    for mp3 in sorted(SOUNDS.glob("*.mp3")):
        d = miniaudio.decode_file(str(mp3), output_format=miniaudio.SampleFormat.SIGNED16, nchannels=2, sample_rate=44100)
        st = np.array(d.samples, dtype=np.int16).reshape(-1, 2).astype(np.float64)
        a = st.mean(axis=1)
        # 왼쪽·오른쪽 크기가 다른 파일(골골 등)은 섞으면 작아지므로, 스테레오로 들릴 때와 같은 크기(실효값)가 되게 키운다 (찌그러지지 않는 범위까지)
        want, have = np.sqrt((st ** 2).mean()), np.sqrt((a ** 2).mean())
        a = a * min(want / max(have, 1e-9), 30000.0 / max(np.abs(a).max(), 1.0))
        pcm = np.clip(np.round(a), -32768, 32767).astype("<i2")
        out = mp3.with_suffix(".wav")
        with wave.open(str(out), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(44100)
            w.writeframes(pcm.tobytes())
        print("%-14s %5.2f초  %4.0f KB  최대 %d" % (out.name, len(pcm) / 44100, out.stat().st_size / 1024, int(np.abs(pcm).max())))
    return 0


if __name__ == "__main__":
    sys.exit(main())
