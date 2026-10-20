"""데스크탑 고양이 설치 프로그램 (DesktopCat_Setup.exe).

    DesktopCat_Setup.exe                    창을 띄워서 설치
    DesktopCat_Setup.exe --silent           창 없이 설치 (기본 위치, 시작 메뉴 바로가기·윈도우 시작 시 자동 실행 포함)
        --dir <폴더>     설치 위치        --no-shortcut   바로가기 만들지 않기
        --no-startup     자동 실행 등록 안 함   --desktop   바탕화면 바로가기도 만들기   --no-run   설치 후 실행 안 함
"""
import argparse
import os
import queue
import shutil
import subprocess
import sys
import threading
import traceback
import zipfile
from pathlib import Path

import ops


def resource(name: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / name


def payload() -> Path:
    p = resource("payload.zip")
    if not p.exists():
        p = Path(__file__).resolve().parent.parent / "build" / "payload.zip"
    return p


def install_files(target: Path, progress):
    """압축 파일을 임시 폴더에 풀고 → 이전 설치와 바꿔치기. 도중에 실패해도 이전 설치가 남는다."""
    parent = target.parent
    parent.mkdir(parents=True, exist_ok=True)
    tmp = parent / (target.name + ".installing")
    old = parent / (target.name + ".old")
    shutil.rmtree(tmp, ignore_errors=True)
    shutil.rmtree(old, ignore_errors=True)
    total = 0
    with zipfile.ZipFile(payload()) as z:
        members = z.infolist()
        for i, m in enumerate(members):
            z.extract(m, tmp)
            total += m.file_size
            progress(i + 1, len(members))
    if target.exists():
        os.replace(target, old)
    os.replace(tmp, target)
    shutil.rmtree(old, ignore_errors=True)
    return total // 1024


def run_install(opts, progress=lambda a, b: None, say=lambda s: None):
    target = Path(opts.dir)
    say("실행 중인 고양이를 끄는 중…")
    if not ops.stop_app():
        raise RuntimeError("실행 중인 고양이를 끌 수 없습니다. 트레이의 고양이 아이콘에서 '종료'를 누른 뒤 다시 설치해 주세요.")
    say("파일을 설치하는 중…")
    size_kb = install_files(target, progress)
    exe = target / ops.EXE
    say("바로가기와 설정을 만드는 중…")
    ops.register_uninstall(target, size_kb)
    ops.set_autostart(exe, opts.startup)
    if opts.shortcut:
        ops.create_shortcut(ops.start_menu_lnk(), exe, "바탕화면에서 고양이를 키웁니다")
    if opts.desktop:
        ops.create_shortcut(ops.desktop_lnk(), exe, "바탕화면에서 고양이를 키웁니다")
    if opts.run:
        say("고양이를 불러오는 중…")
        subprocess.Popen([str(exe)], cwd=str(target), creationflags=0x00000008 | 0x00000200 | ops.CREATE_NO_WINDOW, close_fds=True)
    return exe


def gui(opts):
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk

    root = tk.Tk()
    root.title(ops.DISPLAY_NAME + " 설치")
    root.geometry("520x470")
    root.resizable(False, False)
    ico = resource("cat.ico")
    if ico.exists():
        try:
            root.iconbitmap(str(ico))
        except tk.TclError:
            pass
    font = ("Malgun Gothic", 10)
    root.option_add("*Font", font)
    pad = {"padx": 18}

    ttk.Label(root, text="데스크탑 고양이 🐾", font=("Malgun Gothic", 16, "bold")).pack(anchor="w", pady=(16, 2), **pad)
    ttk.Label(root, text="바탕화면을 돌아다니며 놀고, 자고, 밥 달라고 조르는 고양이를 키웁니다.\n"
                         "설치하면 작업 표시줄 오른쪽 아래(트레이)에 고양이 아이콘이 생깁니다.", justify="left").pack(anchor="w", **pad)

    ttk.Label(root, text="설치할 위치").pack(anchor="w", pady=(14, 2), **pad)
    row = ttk.Frame(root)
    row.pack(fill="x", **pad)
    path_var = tk.StringVar(value=opts.dir)
    ttk.Entry(row, textvariable=path_var).pack(side="left", fill="x", expand=True)

    def browse():
        d = filedialog.askdirectory(initialdir=str(Path(path_var.get()).parent))
        if d:
            path_var.set(str(Path(d) / ops.APP_ID) if not Path(d).name.lower().startswith("desktopcat") else d)

    ttk.Button(row, text="찾아보기", command=browse).pack(side="left", padx=(6, 0))

    v_startup = tk.BooleanVar(value=opts.startup)
    v_short = tk.BooleanVar(value=opts.shortcut)
    v_desk = tk.BooleanVar(value=opts.desktop)
    v_run = tk.BooleanVar(value=opts.run)
    box = ttk.Frame(root)
    box.pack(fill="x", pady=(12, 0), **pad)
    ttk.Checkbutton(box, text="윈도우를 켤 때 자동으로 실행 (추천: 꺼지면 스스로 다시 켜집니다)", variable=v_startup).pack(anchor="w")
    ttk.Checkbutton(box, text="시작 메뉴에 바로가기 만들기", variable=v_short).pack(anchor="w")
    ttk.Checkbutton(box, text="바탕화면에 바로가기 만들기", variable=v_desk).pack(anchor="w")
    ttk.Checkbutton(box, text="설치가 끝나면 바로 실행", variable=v_run).pack(anchor="w")

    status = tk.StringVar(value="설치 버튼을 누르면 시작합니다.")
    ttk.Label(root, textvariable=status, foreground="#555", wraplength=480, justify="left").pack(anchor="w", pady=(16, 2), **pad)
    bar = ttk.Progressbar(root, maximum=100)
    bar.pack(fill="x", **pad)

    btns = ttk.Frame(root)
    btns.pack(side="bottom", fill="x", pady=14, **pad)
    q: "queue.Queue" = queue.Queue()
    install_btn = ttk.Button(btns, text="설치")
    close_btn = ttk.Button(btns, text="닫기", command=root.destroy)
    close_btn.pack(side="right")
    install_btn.pack(side="right", padx=(0, 8))

    def worker(o):
        try:
            run_install(o, progress=lambda a, b: q.put(("p", a * 100 // max(1, b))), say=lambda s: q.put(("s", s)))
            q.put(("done", None))
        except Exception as e:
            q.put(("err", f"{e}\n\n{traceback.format_exc()[-600:]}"))

    def poll():
        try:
            while True:
                kind, val = q.get_nowait()
                if kind == "p":
                    bar["value"] = val
                elif kind == "s":
                    status.set(val)
                elif kind == "done":
                    bar["value"] = 100
                    status.set("설치가 끝났냐옹~ 🐾  트레이(작업 표시줄 오른쪽 아래)에서 고양이 아이콘을 찾아보세요.")
                    install_btn.state(["disabled"])
                    close_btn.configure(text="마치기")
                    return
                elif kind == "err":
                    status.set("설치하지 못했습니다.")
                    install_btn.state(["!disabled"])
                    messagebox.showerror("설치 오류", val)
                    return
        except queue.Empty:
            pass
        root.after(100, poll)

    def start():
        o = argparse.Namespace(dir=path_var.get(), startup=v_startup.get(), shortcut=v_short.get(), desktop=v_desk.get(),
                               run=v_run.get())
        install_btn.state(["disabled"])
        bar["value"] = 0
        threading.Thread(target=worker, args=(o,), daemon=True).start()
        root.after(100, poll)

    install_btn.configure(command=start)
    root.mainloop()
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--silent", action="store_true")
    ap.add_argument("--dir", default=str(ops.default_dir()))
    ap.add_argument("--no-startup", dest="startup", action="store_false")
    ap.add_argument("--no-shortcut", dest="shortcut", action="store_false")
    ap.add_argument("--desktop", action="store_true")
    ap.add_argument("--no-run", dest="run", action="store_false")
    opts = ap.parse_args()
    if opts.silent:
        try:
            run_install(opts)
            return 0
        except Exception:
            (Path(os.environ.get("TEMP", ".")) / "DesktopCat_setup_error.log").write_text(traceback.format_exc(), encoding="utf-8")
            return 1
    return gui(opts)


if __name__ == "__main__":
    sys.exit(main())
