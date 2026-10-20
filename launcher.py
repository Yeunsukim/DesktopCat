"""데스크탑 고양이 지킴이 (설치된 DesktopCat.exe 의 시작점).

고양이 프로그램을 따로 실행해 두고 계속 지켜본다.
  · 고양이가 죽으면(오류·강제 종료·윈도우가 끔) 몇 초 뒤 다시 살린다.
  · 고양이가 멈춰서 응답이 없으면(5초마다 보내는 신호가 90초 넘게 없으면) 강제로 끄고 다시 살린다.
  · 사용자가 트레이 메뉴의 '종료'로 끈 경우에만 같이 끝난다.
  · 계속 바로 죽는 경우에도 포기하지 않고, 대기 시간을 점점 늘려서(최대 5분) 컴퓨터를 괴롭히지 않으면서 계속 시도한다.

표준 라이브러리만 쓰고 하는 일을 아주 적게 해서, 지킴이 자신은 거의 죽을 일이 없다.

사용:  DesktopCat.exe [옵션]   지킴이로 시작 (고양이 옵션을 그대로 전달: --no-icons --scale 1.0 ...)
       DesktopCat.exe --quit    실행 중인 고양이와 지킴이를 종료
       DesktopCat.exe --worker  지킴이 없이 고양이만 실행 (지킴이가 내부적으로 쓴다)
"""
import ctypes
import os
import subprocess
import sys
import time
import traceback
from pathlib import Path

from guard_common import EXIT_QUIT, EXIT_RESTART, GUARD_MUTEX, Heartbeat, data_dir, log_text, request_quit

HANG_SECONDS = int(os.environ.get("DESKTOPCAT_HANG_SECONDS", 90))    # 이 시간 동안 고양이의 신호가 없으면 멈춘 것으로 본다 (시험할 때만 환경 변수로 바꿈)
STARTUP_GRACE = int(os.environ.get("DESKTOPCAT_STARTUP_GRACE", 90))  # 시작 직후에는 신호가 늦을 수 있으니 이만큼은 기다려 준다
CREATE_NO_WINDOW = 0x08000000

DATA = data_dir()
LOG = DATA / "cat_guard.log"


def _child_command(extra):
    if getattr(sys, "frozen", False):
        return [sys.executable, "--worker", *extra]
    return [sys.executable, str(Path(__file__).resolve()), "--worker", *extra]


def _watch(proc, hb, started):
    """고양이 프로세스가 끝나거나 멈출 때까지 지켜본다. 끝났으면 종료 코드, 멈춰서 우리가 껐으면 'hang'."""
    last_poll = time.time()
    grace_until = started + STARTUP_GRACE
    while True:
        rc = proc.poll()
        if rc is not None:
            return rc
        time.sleep(2.0)
        now = time.time()
        if now - last_poll > 20:                 # 우리도 같이 멈췄다 깨어났다 = 컴퓨터가 절전에서 돌아옴: 잠시 봐 준다
            grace_until = now + 60
        last_poll = now
        if now > grace_until and now - hb.last() > HANG_SECONDS:
            log_text(LOG, f"고양이 응답 없음({now - hb.last():.0f}초) → 강제로 끄고 다시 시작")
            try:
                proc.kill()
                proc.wait(10)
            except Exception:
                pass
            return "hang"


def run_guard(extra):
    k32 = ctypes.windll.kernel32
    k32.CreateMutexW.restype = ctypes.c_void_p
    mutex = k32.CreateMutexW(None, False, GUARD_MUTEX)
    if k32.GetLastError() == 183:                # 이미 지킴이가 떠 있음
        return 0
    hb = Heartbeat()
    fast_fails = 0
    while True:
        try:
            started = time.time()
            hb.beat()
            proc = subprocess.Popen(_child_command(extra), creationflags=CREATE_NO_WINDOW,
                                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            rc = _watch(proc, hb, started)
            if rc == EXIT_QUIT:
                return 0                         # 사용자가 종료함
            uptime = time.time() - started
            if rc == EXIT_RESTART:
                log_text(LOG, "고양이가 스스로 다시 시작을 요청함 → 바로 다시 시작")
                fast_fails = 0
                continue
            fast_fails = fast_fails + 1 if uptime < 30 else 0
            wait = 3 if fast_fails <= 1 else min(300, 3 * 2 ** min(fast_fails, 7))
            log_text(LOG, f"고양이가 꺼짐(종료 코드 {rc}, {uptime:.0f}초 동안 실행) → {wait}초 뒤 다시 시작")
            time.sleep(wait)
        except Exception:
            log_text(LOG, "지킴이 오류(계속함):\n" + traceback.format_exc())
            time.sleep(5)


def main():
    args = sys.argv[1:]
    if "--quit" in args:
        request_quit()
        return 0
    if "--net-helper" in args:
        import nethelper                         # 네트워크 보조 프로세스: 캘린더·인터넷 작업을 본체 밖에서 한다 (본체 메모리를 아끼려고)
        return nethelper.main()
    if "--worker" in args:
        import cat                               # 무거운 부분(PyQt 등)은 고양이 프로세스에서만 가져온다
        sys.argv = [sys.argv[0]] + args
        return cat.main()
    return run_guard(args)


if __name__ == "__main__":
    sys.exit(main())
