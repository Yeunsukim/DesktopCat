"""정해 둔 알림이 놓치지 않고 도는지: 켠 직후 따라잡기, 설정만 저장해도 놓친 알림이 사라지지 않기, 옛 설정(20분) 올리기.
사용: python -I -X utf8 tools/test_scheduler_rules.py"""
import datetime as dt
import json
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from PyQt6.QtCore import QCoreApplication  # noqa: E402

app = QCoreApplication.instance() or QCoreApplication([])
from config_store import Settings  # noqa: E402
from scheduler import Scheduler  # noqa: E402

ok = True


def check(label, cond):
    global ok
    ok &= bool(cond)
    print(("통과 " if cond else "실패 ") + label)


def at(h, m):
    return dt.datetime(2026, 10, 20, h, m, 0)


tmp = Path(tempfile.mkdtemp())
st = Settings(tmp)
st.save = lambda: None
st.data["schedules"]["calendar"] = {"enabled": True, "times": ["08:00"]}
st.data["schedules"]["hourly"] = {"enabled": True, "times": ["%02d:00" % h for h in range(24)], "max_age_min": 180}
st.data["last_run"] = {}
sc = Scheduler(st, {"calendar": lambda: None, "hourly": lambda: None})
check("08:30 에 켜도 08:00 매시 알림을 따라잡음 (30분 지남)", sc.due_slot("hourly", at(8, 30)) == "2026-10-20 08:00")
check("3시간 넘게 지난 매시 알림은 따라잡지 않음", sc.due_slot("hourly", at(11, 30)) == "2026-10-20 11:00" and sc.due_slot("hourly", dt.datetime(2026, 10, 20, 8, 30)) is not None)
st.data["last_run"] = {"calendar": "2026-10-20 08:00", "hourly": "2026-10-20 07:00"}
check("이미 한 일일 알림은 다시 안 함", sc.due_slot("calendar", at(9, 0)) is None)
# 설정을 열었다 저장만 했을 때(바뀐 것 없음): 놓친 알림이 그대로 남아야 한다
st.data["last_run"] = {}
sc.mark_past_done(at(8, 31))
check("바뀐 게 없으면 놓친 알림을 ‘한 것’으로 지우지 않음", st.data["last_run"].get("calendar", "") == "" and st.data["last_run"].get("hourly", "") == "")
# 시각을 바꿨을 때: 그 알림의 지난 시각만 한 것으로
st.data["schedules"]["calendar"]["times"] = ["07:00", "18:00"]
sc.mark_past_done(at(8, 31))
check("시각을 바꾼 알림은 지난 시각(07:00)을 한 것으로 표시", st.data["last_run"].get("calendar") == "2026-10-20 07:00")
check("바꾸지 않은 매시 알림은 그대로 (놓친 게 남음)", st.data["last_run"].get("hourly", "") == "")
check("바꾼 알림도 18:00 은 아직 안 한 것", sc.due_slot("calendar", at(18, 0)) == "2026-10-20 18:00")
# 옛 설정 파일(max_age_min 20)이 올라가는지
st2dir = Path(tempfile.mkdtemp())
(st2dir / "launcher_config.json").write_text(json.dumps({"schedules": {"hourly": {"enabled": True, "times": ["08:00"], "max_age_min": 20}}}), encoding="utf-8")
check("저장돼 있던 옛 기본값(20분)은 180분으로 올림", Settings(st2dir).data["schedules"]["hourly"]["max_age_min"] == 180)
print("전체:", "모두 통과" if ok else "실패 있음")
