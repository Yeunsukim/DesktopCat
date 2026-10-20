"""행동 흐름(flow.py) 점검: 가중치가 낡지 않았는지, 흐름에 막다른 길이 없는지, 목표 시간 비율이 나오는지 확인한다.

    python tools/test_flow.py            점검
    python tools/test_flow.py --print    새 가중치 상수를 뽑는다 (FLOW·DUR·TARGET 을 고친 뒤)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import flow as F  # noqa: E402


def main():
    day, cor = F.solve(F.KINDS, F.TARGET_DAY), F.solve(F.CORNER_KINDS, F.TARGET_CORNER)
    if "--print" in sys.argv:
        print("WEIGHTS_DAY =", {k: round(v, 3) for k, v in day.items()})
        print("WEIGHTS_CORNER =", {k: round(v, 3) for k, v in cor.items()})
        return
    ok = True

    def check(label, cond):
        nonlocal ok
        ok &= bool(cond)
        print(("통과 " if cond else "실패 ") + label)

    check("상수 가중치가 최신(낮)", all(abs(day[k] - F.WEIGHTS_DAY[k]) < 0.01 for k in day))
    check("상수 가중치가 최신(구석)", all(abs(cor[k] - F.WEIGHTS_CORNER[k]) < 0.01 for k in cor))
    for name, kinds, w, tgt in (("낮", F.KINDS, F.WEIGHTS_DAY, F.TARGET_DAY), ("구석", F.CORNER_KINDS, F.WEIGHTS_CORNER, F.TARGET_CORNER)):
        got = F.expected_share(w.keys(), w)
        tot = sum(tgt.values())
        check("%s: 묶음별 시간 비율이 목표와 1%%p 이내 %s" % (name, {k: round(v, 1) for k, v in got.items()}),
              all(abs(got[g] - tgt[g] / tot * 100) < 1.0 for g in tgt))
    check("모든 행동에 다음 행동이 있음(막다른 길 없음)", all(F.row(k, F.KINDS) for k in F.KINDS))
    reach, todo = {"sit"}, ["sit"]
    while todo:
        for nk in F.row(todo.pop(), F.KINDS):
            if nk not in reach:
                reach.add(nk)
                todo.append(nk)
    check("모든 행동에 도달 가능 (빠진 것: %s)" % (set(F.KINDS) - reach or "없음"), reach == set(F.KINDS))
    # 개연성 점검: 이런 급한 전환은 없어야 한다
    bad = [("run", "sleep"), ("run", "loaf"), ("run", "knead"), ("jump", "sleep"), ("kick", "sleep"), ("kick", "loaf"), ("sleep", "run"),
           ("sleep", "jump"), ("sleep", "kick"), ("sleep", "walk"), ("loaf", "run"), ("loaf", "jump"), ("sneak", "sleep"), ("groom", "run")]
    check("뛰다가 갑자기 눕거나 자다가 바로 달리는 전환이 없음", all(F.FLOW[a].get(b, 0) == 0 for a, b in bad))
    check("잠에서 깨면 하품·기지개부터", set(F.FLOW["sleep"]) <= {"yawn", "stretch", "sit", "groomface", "loaf", "idle"})
    print("전체:", "모두 통과" if ok else "실패 있음")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
