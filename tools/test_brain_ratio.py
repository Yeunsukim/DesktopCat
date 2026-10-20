"""고양이 두뇌를 몇 시간 돌려서 한 동작에 갇히지 않는지 확인한다 (움직임을 고칠 때마다 돌린다).

예: 걷기 처리 함수를 달리기·살금살금이 같이 쓰는 것을 놓치고 고쳤더니, 두 동작이 끝나지 않아 이동이 99%가 됐는데
다른 시험들은 통과했다. 이 시험은 그런 '갇힘'을 잡는다. (진짜 시간이 아니라 가짜 시간으로 몇 초 만에 돈다)
사용: python -I -X utf8 tools/test_brain_ratio.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sim_behavior as SB  # noqa: E402

ok = True


def check(label, cond):
    global ok
    ok &= bool(cond)
    print(("통과 " if cond else "실패 ") + label)


for seed in (1, 2):
    groups, states, trans = SB.run(hours=3.0, seed=seed)
    top, share = max(states.items(), key=lambda kv: kv[1])
    move = groups.get("이동(걷기·달리기·살금·점프)", 0.0)
    check("씨앗 %d: 한 상태가 60%%를 넘지 않음 (가장 많은 %s %.1f%%)" % (seed, top, share), share <= 60.0)
    check("씨앗 %d: 이동 비율이 2~20%% 사이 (%.1f%%)" % (seed, move), 2.0 <= move <= 20.0)
    check("씨앗 %d: 여러 동작을 오감 (상태 %d가지, 바뀐 횟수 %d)" % (seed, sum(1 for v in states.values() if v > 0.5), sum(trans.values()) if hasattr(trans, "values") else len(trans)),
          sum(1 for v in states.values() if v > 0.5) >= 6)
print("전체:", "모두 통과" if ok else "실패 있음")
