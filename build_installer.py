"""설치 파일(exe) 만들기.

    python build_installer.py

만들어지는 것:
    build/dist/DesktopCat/            고양이 프로그램 (폴더째 설치됨)
    build/dist/DesktopCat_Setup.exe   설치 프로그램 (위 폴더를 압축해서 안에 담음)  ← 이것만 나눠 주면 된다

필요한 것: PyInstaller (pip install pyinstaller), 그리고 고양이 실행에 필요한 PyQt6·numpy·pywin32.
"""
import shutil
import subprocess
import time
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BUILD = ROOT / "build"
DIST = BUILD / "dist"
WORK = BUILD / "work"


def run(cmd):
    print(">", " ".join(str(c) for c in cmd), flush=True)
    subprocess.run([str(c) for c in cmd], cwd=ROOT, check=True)


def pyinstaller(*args):
    run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--distpath", DIST, "--workpath", WORK,
         "--specpath", BUILD / "spec", *args])


def main():
    for _ in range(5):                      # 백신이 파일을 잠깐 붙잡고 있으면 지우기가 실패할 수 있어서 몇 번 다시 시도
        shutil.rmtree(BUILD, ignore_errors=True)
        if not BUILD.exists():
            break
        time.sleep(2)
    BUILD.mkdir(parents=True, exist_ok=True)
    run([sys.executable, ROOT / "tools" / "make_icon.py"])
    ico = ROOT / "assets" / "cat.ico"

    # 1) 고양이 프로그램 (폴더 형태: 켤 때마다 압축을 푸는 시간이 없다)
    pyinstaller("--onedir", "--windowed", "--name", "DesktopCat", "--icon", ico, "--paths", ROOT,
                "--add-data", f"{ROOT / 'assets' / 'skin'};assets/skin",
                "--add-data", f"{ROOT / 'assets' / 'sprites'};assets/sprites",
                # 캘린더 알림: 일정 해석(icalendar·recurring_ical_events)과 시간대 자료(tzdata). 보조 프로세스에서 필요할 때만 불러오는 모듈이라 명시해 둔다
                "--collect-all", "icalendar", "--collect-all", "recurring_ical_events", "--collect-all", "x_wr_timezone",
                "--collect-data", "tzdata", "--collect-submodules", "dateutil", "--hidden-import", "zoneinfo",
                "--hidden-import", "calendar_ics", "--hidden-import", "gemini_client", "--hidden-import", "news_sources",
                "--hidden-import", "activity_log", "--hidden-import", "nethelper",
                # 경비 고양이·메일·디자인: 필요할 때 불러오는 모듈과 폴더 감시(sec_watch: 윈도우 기능을 pywin32 로 직접 쓴다)
                "--hidden-import", "security", "--hidden-import", "sec_events", "--hidden-import", "sec_common",
                "--hidden-import", "sec_ransom", "--hidden-import", "sec_ui", "--hidden-import", "sec_sig",
                "--hidden-import", "sec_scan", "--hidden-import", "sec_privacy", "--hidden-import", "sec_download",
                "--hidden-import", "vt_client", "--hidden-import", "mail_imap", "--hidden-import", "favicon",
                "--hidden-import", "flow", "--hidden-import", "routine", "--hidden-import", "cute", "--hidden-import", "theme",
                "--hidden-import", "sec_watch", "--hidden-import", "win32file", "--hidden-import", "win32event",
                "--exclude-module", "scipy", "--exclude-module", "PIL", "--exclude-module", "tkinter",
                "--exclude-module", "matplotlib", "--exclude-module", "pytest", "--exclude-module", "unittest",
                ROOT / "launcher.py")
    # 2) 삭제 프로그램
    pyinstaller("--onefile", "--windowed", "--name", "uninstall", "--icon", ico, "--paths", ROOT, "--paths", ROOT / "installer",
                "--exclude-module", "tkinter", "--exclude-module", "numpy", "--exclude-module", "PyQt6",
                ROOT / "installer" / "uninstall_app.py")
    app_dir = DIST / "DesktopCat"
    # 쓰지 않는 Qt 구성물을 뺀다 (소프트웨어 그래픽·PDF·번역 파일·시험용 화면 플러그인 등, 약 30MB). 고양이는 일반 창 그리기만 쓴다.
    qt = app_dir / "_internal" / "PyQt6" / "Qt6"
    for rel in ("bin/opengl32sw.dll", "bin/Qt6Pdf.dll", "plugins/imageformats/qpdf.dll", "plugins/platforms/qminimal.dll",
                "plugins/platforms/qoffscreen.dll"):
        (qt / rel).unlink(missing_ok=True)
    shutil.rmtree(qt / "plugins" / "generic", ignore_errors=True)
    shutil.rmtree(qt / "translations", ignore_errors=True)
    shutil.copy2(DIST / "uninstall.exe", app_dir / "uninstall.exe")

    # 3) 압축 (LZMA: 용량이 가장 작게)
    payload = BUILD / "payload.zip"
    with zipfile.ZipFile(payload, "w", zipfile.ZIP_LZMA) as z:
        for f in sorted(app_dir.rglob("*")):
            if f.is_file():
                z.write(f, f.relative_to(app_dir))
    print(f"압축 파일: {payload.stat().st_size / 1e6:.1f} MB (원본 {sum(f.stat().st_size for f in app_dir.rglob('*') if f.is_file()) / 1e6:.1f} MB)")

    # 4) 설치 프로그램 (압축 파일을 안에 담는다)
    pyinstaller("--onefile", "--windowed", "--name", "DesktopCat_Setup", "--icon", ico, "--paths", ROOT, "--paths", ROOT / "installer",
                "--add-data", f"{payload};.", "--add-data", f"{ico};.",
                "--exclude-module", "numpy", "--exclude-module", "PyQt6", "--exclude-module", "scipy",
                ROOT / "installer" / "setup_app.py")
    setup = DIST / "DesktopCat_Setup.exe"
    print(f"\n완성: {setup}  ({setup.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
