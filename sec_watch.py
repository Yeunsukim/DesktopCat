"""폴더 감시: 윈도우의 ReadDirectoryChangesW 를 직접 쓴다 (랜섬웨어 경보·다운로드 검사가 함께 쓴다).

watchdog 대신 쓰는 이유: watchdog 은 파일 사건마다 '폴더인지' 디스크에 다시 물어보고(isdir) 사건 객체를 여러 개 만들어서,
파일 수만 개를 한꺼번에 풀거나 지울 때 CPU 를 많이 썼다 (2만 개 압축 풀기·지우기 동안 코어 1개의 약 70%).
여기서는
 · 파일 이름 변화(만들기·지우기·이름 바꾸기)와 내용 쓰기만 받는다. 폴더 이름 변화는 받지 않는다.
 · 사건 목록 해석은 pywin32(C 코드)가 하고, 파이썬은 경로를 이어 붙여 넘기기만 한다.
 · 사건이 너무 많아 윈도우의 버퍼가 넘치면 on_overflow() 를 부른다 (그 사이 사건 일부를 놓쳤다는 뜻: 미끼 파일을 직접 확인하는 데 쓴다).
callback(kind, src, dst): kind 는 "created" / "modified" / "deleted" / "moved" (moved 일 때만 dst 가 있다). 감시 스레드에서 불린다.
"""
import os
import threading

import pywintypes
import win32con
import win32event
import win32file

FILE_LIST_DIRECTORY = 0x0001
DEFAULT_FILTER = win32con.FILE_NOTIFY_CHANGE_FILE_NAME | win32con.FILE_NOTIFY_CHANGE_LAST_WRITE
BUFFER = 64 * 1024                     # 바이트: 한 번에 받는 사건 목록 크기 (네트워크 드라이브 한도와 같은 64KB)
ERROR_NOTIFY_ENUM_DIR = 1022           # 사건이 너무 많아 버퍼가 넘쳤다
BATCH_WAIT = 0.05                      # 초: 사건이 띄엄띄엄 올 때 모아 받는 시간 (그 사이 사건은 윈도우가 쌓아 둔다)


class DirWatcher:
    def __init__(self, folder, callback, recursive=True, on_overflow=None, buffer_size=BUFFER, flags=DEFAULT_FILTER):
        self.folder = os.path.normpath(str(folder))
        self.callback, self.on_overflow = callback, on_overflow
        self.recursive, self.buffer_size, self.flags = recursive, buffer_size, flags
        self.overflows = 0
        self.ready = threading.Event()             # 감시가 실제로 시작되면 켜진다 (시험용)
        self._stop = threading.Event()
        self._thread = None

    def start(self):
        self._thread = threading.Thread(target=self._run, name="DirWatcher", daemon=True)
        self._thread.start()
        return self

    def stop(self):
        self._stop.set()

    def join(self, timeout=None):
        if self._thread is not None:
            self._thread.join(timeout)

    def _run(self):
        try:
            h = win32file.CreateFile(self.folder, FILE_LIST_DIRECTORY,
                                     win32con.FILE_SHARE_READ | win32con.FILE_SHARE_WRITE | win32con.FILE_SHARE_DELETE, None,
                                     win32con.OPEN_EXISTING, win32con.FILE_FLAG_BACKUP_SEMANTICS | win32con.FILE_FLAG_OVERLAPPED, None)
        except pywintypes.error:
            return                                     # 폴더가 없거나 열 수 없다
        ov = pywintypes.OVERLAPPED()
        ov.hEvent = win32event.CreateEvent(None, True, False, None)
        buf = win32file.AllocateReadBuffer(self.buffer_size)
        pending = False
        try:
            while not self._stop.is_set():
                win32event.ResetEvent(ov.hEvent)
                try:
                    win32file.ReadDirectoryChangesW(h, buf, self.recursive, self.flags, ov)
                except pywintypes.error:
                    break                                  # 폴더가 지워졌거나 드라이브가 빠졌다
                pending = True
                self.ready.set()
                while not self._stop.is_set() and win32event.WaitForSingleObject(ov.hEvent, 500) != win32event.WAIT_OBJECT_0:
                    pass
                if self._stop.is_set():
                    break
                try:
                    n = win32file.GetOverlappedResult(h, ov, True)
                except pywintypes.error as e:
                    if e.winerror != ERROR_NOTIFY_ENUM_DIR:
                        break
                    n = 0                                  # 윈도우에 따라 넘침을 오류로 알려 준다
                pending = False
                if n == 0:                                 # 버퍼가 넘쳤다: 그 사이 사건 일부를 놓쳤다
                    self.overflows += 1
                    if self.on_overflow:
                        try:
                            self.on_overflow()
                        except Exception:
                            pass
                    self._stop.wait(0.02)                  # (이상한 상태에서 '넘침'만 계속 오더라도 쉬지 않고 도는 일이 없게)
                    continue
                items = win32file.FILE_NOTIFY_INFORMATION(buf, n)
                self._dispatch(items)
                if len(items) < 64:                        # 사건이 하나둘씩 올 때는 잠깐 모았다가 받는다 (윈도우와 주고받는 횟수를 줄인다)
                    self._stop.wait(BATCH_WAIT)
        finally:
            if pending:
                try:
                    win32file.CancelIo(h)
                    win32file.GetOverlappedResult(h, ov, True)     # 취소가 끝날 때까지 기다린 뒤에 버퍼를 놓는다
                except pywintypes.error:
                    pass
            try:
                h.Close()
            except Exception:
                pass
            try:
                ov.hEvent.Close()
            except Exception:
                pass

    def _dispatch(self, items):
        join, folder, cb = os.path.join, self.folder, self.callback
        old = None                                         # 이름 바꾸기의 '예전 이름' (바로 다음 사건이 '새 이름')
        for action, name in items:
            path = join(folder, name)
            try:
                if old is not None and action != 5:
                    cb("deleted", old, None)               # 짝(새 이름)이 없다: 감시 폴더 밖으로 옮겨 갔다
                    old = None
                if action == 1:                            # FILE_ACTION_ADDED
                    cb("created", path, None)
                elif action == 3:                          # FILE_ACTION_MODIFIED
                    cb("modified", path, None)
                elif action == 2:                          # FILE_ACTION_REMOVED
                    cb("deleted", path, None)
                elif action == 4:                          # FILE_ACTION_RENAMED_OLD_NAME
                    old = path
                elif action == 5:                          # FILE_ACTION_RENAMED_NEW_NAME
                    if old is not None:
                        cb("moved", old, path)
                        old = None
                    else:
                        cb("created", path, None)          # 감시 폴더 밖에서 옮겨 왔다
            except Exception:
                old = None
        if old is not None:
            try:
                cb("deleted", old, None)
            except Exception:
                pass
