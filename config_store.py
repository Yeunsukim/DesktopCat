"""비서 기능의 설정 저장소: 등록한 앱, 알림 시각, 프롬프트, 캘린더 주소 등을 launcher_config.json 에 둔다.

 · 저장은 임시 파일에 쓴 뒤 바꿔치기(os.replace)라서 저장하다 꺼져도 파일이 깨지지 않는다 (pet.py 와 같은 방식).
 · Gemini API 키 같은 비밀 값은 설정 파일에 평문으로 두지 않고, 윈도우 사용자 계정에 묶인 DPAPI(CryptProtectData)로 암호화해서
   secrets.json 에 따로 둔다. 같은 윈도우 계정에서만 풀 수 있다.
"""
import base64
import copy
import json
import os
from pathlib import Path

DEFAULTS = {
    "version": 1,
    "apps": [],                                   # [{"name": 표시 이름, "target": 경로 또는 주소, "kind": "file" | "url"}]
    "calendar_url": "",                           # 구글 캘린더 '비공개 주소(iCal 형식)'
    "gemini_model": "",
    "schedules": {                                # 하루에 알릴 시각들 (24시간 'HH:MM')
        "calendar": {"enabled": True, "times": ["09:00"]},
        "news": {"enabled": False, "times": ["08:00"]},
        "yesterday": {"enabled": False, "times": ["09:30"]},
        "hourly": {"enabled": True, "times": ["%02d:00" % h for h in range(24)], "max_age_min": 180},     # 매시 정각: 앞으로 N시간 일정 + 새 메일 (놓친 정각은 3시간 안이면 켠 직후·돌아온 뒤 바로 한 번 따라잡음. 가져오는 내용은 '지금' 기준이라 괜찮다)
    },
    "prompts": {"news": "", "yesterday": ""},
    "hourly_opts": {"calendar": True, "hours": 2, "mail": False},       # 매시 정각에 무엇을 알릴지 (메일은 Gmail 연결 후 켠다)
    "mail": {"address": ""},                      # 앱 비밀번호는 secrets 에 암호화해서 둔다
    "mail_state": {},                             # 마지막으로 확인한 메일 번호 {"last_uid", "uidvalidity"}
    "news_opts": {"city": "자동", "quotes": "", "use_search": False},   # city '자동'은 IP 로 위치 찾기, quotes 가 비면 기본 시세 목록, use_search 는 유료 등급용 구글 검색 사용
    "activity": {"enabled": False, "consented": False, "exclude": []},    # exclude: 사용자가 정한 제외 단어 (창 제목·프로그램 이름에 들어 있으면 '(제외됨)'으로만 기록)
    "care": {                                     # 고양이의 하루 생활 (routine.py)
        "night": {"enabled": True, "start": "22:00", "end": "07:00"},        # 잠자는 시간: 구석에서 웅크리고 자고, 알림·졸라대기를 쉰다
        "meals": {"enabled": True, "times": ["08:00", "13:00", "19:00"]},    # 밥 시간(하루 세 번): 안 주면 냐옹~ 냐옹~
        "play": {"enabled": True, "every_min": 60},                          # 이 간격마다 놀아 달라고 한다
        "corner": {"side": "right"},                                         # '한쪽에서 쉬기'의 구석: right / left
    },
    "security": {                                 # 경비 고양이 (랜섬웨어·스파이웨어 조기 경보, 자세한 설명은 README)
        "enabled": True,
        "ransom": {"enabled": True, "canary": True, "sensitivity": "normal", "folders": []},     # folders 가 비면 문서·사진·다운로드·바탕화면
        "download": {"enabled": True},                                                             # 내려받은 실행 파일 검사 (서명·인터넷 출처)
        "vt": {"enabled": False},                                                                  # VirusTotal 해시 조회 (키 필요, 해시만 보냄)
        "privacy": {"enabled": True},                                                              # 카메라·마이크를 쓰는 처음 보는 프로그램 알림
        "scan": {"enabled": True, "interval_min": 10},                                             # 자동 시작·실행 중 프로그램 점검 (보조 프로세스에서 몇 분마다)
        "allow": {"process": [], "autorun": [], "privacy": []},                                    # 허용 목록 (경보를 다시 안 울린다)
    },
    "care_state": {"last_fed": 0.0},              # 마지막으로 밥 준 시각(epoch 초)
    "last_run": {},                               # {"calendar": "2026-10-16 09:00", ...}: 같은 시각에 두 번 알리지 않으려고 기록
}


def _merge(base: dict, over: dict) -> dict:
    """base 위에 over 를 덮어쓰되, 빠진 키는 기본값으로 채운다 (새 버전에서 항목이 늘어도 예전 설정 파일이 그대로 쓰이게)."""
    out = copy.deepcopy(base)
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def _atomic_write(path: Path, text: str):
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


class Settings:
    def __init__(self, folder: Path):
        self.dir = Path(folder)
        self.path = self.dir / "launcher_config.json"
        self.secret_path = self.dir / "secrets.json"
        self.data = copy.deepcopy(DEFAULTS)
        self.load()

    # --- 불러오기/저장 -------------------------------------------------
    def load(self):
        try:
            self.data = _merge(DEFAULTS, json.loads(self.path.read_text(encoding="utf-8")))
            hs = self.data.get("schedules", {}).get("hourly", {})
            if isinstance(hs, dict) and 0 < (hs.get("max_age_min") or 0) < 180:        # 예전 기본값(20분)이 저장돼 있으면 새 기본값으로 (켠 직후 놓친 매시 알림을 따라잡게)
                hs["max_age_min"] = 180
        except (OSError, ValueError):
            self.data = copy.deepcopy(DEFAULTS)

    def save(self):
        try:
            _atomic_write(self.path, json.dumps(self.data, ensure_ascii=False, indent=1))
        except OSError:
            pass

    # --- 등록한 앱 -----------------------------------------------------
    @property
    def apps(self) -> list:
        return self.data["apps"]

    def add_app(self, name: str, target: str, kind: str = "file", **extra) -> bool:
        """같은 대상이 이미 있으면 추가하지 않는다 (False). kind: file / url / cmd(명령 실행) / sys(윈도우 도구). extra: 셸 종류 등 부가 정보."""
        target = target.strip()
        if not target or any(a["target"].lower() == target.lower() and a.get("kind", "file") == kind for a in self.apps):
            return False
        item = {"name": name.strip() or target, "target": target, "kind": kind}
        item.update(extra)
        self.apps.append(item)
        self.save()
        return True

    def remove_app(self, index: int):
        if 0 <= index < len(self.apps):
            del self.apps[index]
            self.save()

    # --- 비밀 값 (DPAPI) ------------------------------------------------
    def set_secret(self, name: str, value: str):
        """value 를 이 윈도우 계정으로만 풀 수 있게 암호화해서 저장한다. 빈 문자열이면 지운다."""
        import win32crypt
        try:
            store = json.loads(self.secret_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            store = {}
        if value:
            blob = win32crypt.CryptProtectData(value.encode("utf-8"), name, None, None, None, 0)
            store[name] = base64.b64encode(blob).decode("ascii")
        else:
            store.pop(name, None)
        try:
            _atomic_write(self.secret_path, json.dumps(store))
        except OSError:
            pass

    def get_secret(self, name: str) -> str:
        import win32crypt
        try:
            store = json.loads(self.secret_path.read_text(encoding="utf-8"))
            blob = base64.b64decode(store[name])
            return win32crypt.CryptUnprotectData(blob, None, None, None, 0)[1].decode("utf-8")
        except Exception:
            return ""
