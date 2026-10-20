"""데스크탑 고양이 삭제 프로그램 (설치 폴더의 uninstall.exe).

    uninstall.exe            물어보면서 삭제
    uninstall.exe --silent   묻지 않고 삭제 (고양이 기록은 남김)
    uninstall.exe --silent --purge   묻지 않고 기록까지 모두 삭제
"""
import ctypes
import os
import shutil
import sys
import time
from pathlib import Path

import ops

MB_YESNO, MB_ICONQUESTION, MB_ICONINFO, IDYES = 0x4, 0x20, 0x40, 6


def trace(msg):
    if os.environ.get("DESKTOPCAT_TRACE"):
        with open(os.path.join(os.environ.get("TEMP", "."), "uninstall_trace.log"), "a", encoding="utf-8") as f:
            f.write(time.strftime("%H:%M:%S ") + msg + "\n")


# 안내창을 항상 맨 앞에 띄운다. 고양이를 끄는 사이에 윈도우가 맨 앞 창을 다른 프로그램으로 넘겨서, 이 옵션이 없으면
# 마지막 안내창이 다른 창 뒤에 숨어 버리고 삭제 프로그램이 사용자 클릭을 기다리며 끝나지 않는다.
FRONT = 0x40000 | 0x10000          # MB_TOPMOST | MB_SETFOREGROUND


def ask(text, title):
    return ctypes.windll.user32.MessageBoxW(0, text, title, MB_YESNO | MB_ICONQUESTION | FRONT) == IDYES


def tell(text, title):
    """마지막 안내는 삭제 프로그램 밖의 작은 별도 프로세스(wscript)로 띄운다.
    삭제 프로그램이 안내창을 기다리고 있으면, 안내창이 다른 창 뒤에 숨었을 때 삭제 작업(폴더 지우기)이 끝나지 않기 때문이다."""
    vbs = Path(os.environ.get("TEMP", ".")) / f"{ops.APP_ID}_bye.vbs"
    quote = lambda s: s.replace('"', '""')
    vbs.write_text(f'MsgBox "{quote(text)}", 4160, "{quote(title)}"\r\n'          # 4160 = 정보 아이콘 + 항상 맨 앞
                   'CreateObject("Scripting.FileSystemObject").DeleteFile WScript.ScriptFullName\r\n', encoding="utf-16")
    try:
        import subprocess
        subprocess.Popen(["wscript.exe", "//nologo", str(vbs)], creationflags=0x00000008 | ops.CREATE_NO_WINDOW, close_fds=True)
    except OSError:
        ctypes.windll.user32.MessageBoxW(0, text, title, MB_ICONINFO | FRONT)       # 비상용: 직접 띄운다


def main():
    silent = "--silent" in sys.argv
    purge = "--purge" in sys.argv
    install_dir = Path(sys.executable).resolve().parent
    title = ops.DISPLAY_NAME + " 삭제"
    if not silent:
        if not ask("데스크탑 고양이를 컴퓨터에서 삭제할까요?\n\n고양이가 실행 중이면 먼저 끕니다.", title):
            return 0
        purge = ask("고양이의 기록도 함께 지울까요?\n\n배고픔·기분, 설정(등록한 앱·알림 시각), 암호화해 저장한 캘린더 주소와 Gemini 키, 활동 기록(어제 한 일), 경비 기록·VirusTotal 키가 모두 지워집니다.\n"
                    "'아니요'를 고르면 나중에 다시 설치했을 때 이어서 쓸 수 있습니다.", title)

    trace("before ops.stop_app()")
    ops.stop_app()
    trace("after ops.stop_app()")
    trace("before ops.set_autostart(install_dir / ops.EXE, False)")
    ops.set_autostart(install_dir / ops.EXE, False)
    trace("after ops.set_autostart(install_dir / ops.EXE, False)")
    ops.remove_file(ops.start_menu_lnk())
    ops.remove_file(ops.desktop_lnk())
    try:
        ops.remove_canaries()                                         # 경비용 숨김 미끼 파일은 기록을 남기는 삭제에서도 항상 치운다
    except Exception:
        pass
    trace("before ops.unregister_uninstall()")
    ops.unregister_uninstall()
    trace("after ops.unregister_uninstall()")
    if purge:
        shutil.rmtree(ops.user_data_dir(), ignore_errors=True)
    trace("before ops.delete_tree_after_exit(install_dir)")
    ops.delete_tree_after_exit(install_dir)
    trace("after ops.delete_tree_after_exit(install_dir)")                # 이 프로그램이 끝난 뒤에 폴더를 지운다
    trace("before final message")
    if not silent:
        tell("삭제했냐옹~ 그동안 고마웠다냥. 🐾", title)
    trace("main returns")
    return 0


if __name__ == "__main__":
    sys.exit(main())
