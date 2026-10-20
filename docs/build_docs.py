"""문서 사이트(docs/)에 들어가는 '코드에서 뽑아야 정확한' 자료를 만든다.

  python docs/build_docs.py        →  docs/assets/gen-data.js (window.DOCDATA) + docs/tech.html·manual.html (src/ 조각을 이어 붙임)

만드는 것
 · 모듈 목록: 파일 이름·줄 수·묶음·역할 (역할 문장은 아래 ROLES 에 사람이 쓴 것)
 · 모듈 사이의 import 관계 (바로 import / 함수 안에서 필요할 때 import)
 · 합계 (파이썬 파일 수·줄 수)
코드를 고치면 이 스크립트를 다시 돌려서 문서의 숫자·그래프를 새로 맞춘다 (손으로 고치지 않는다).
"""
import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "assets" / "gen-data.js"

# 묶음 (왼쪽 → 오른쪽 순서가 문서의 순서)
GROUPS = [
    ("run", "실행·지킴이"), ("brain", "행동 두뇌"), ("draw", "그리기"), ("notify", "알림"),
    ("guard", "경비"), ("ui", "화면·디자인"), ("store", "저장·설정"), ("pack", "설치·배포"),
]

# 파일 → (묶음, 한 줄 역할)
ROLES = {
    "launcher.py": ("run", "지킴이. 고양이(worker)를 따로 띄워 살려 두고, --quit / --worker / --net-helper 도 여기서 갈라진다"),
    "guard_common.py": ("run", "지킴이와 본체가 같이 쓰는 도구: 데이터 폴더, 로그, 하트비트(공유 메모리), 종료 이벤트, 자원 측정 (표준 라이브러리만)"),
    "cat.py": ("run", "본체: 투명 창(Overlay)·메뉴·트레이를 만들고 모든 부품을 조립해 24fps 프레임 루프를 돌린다"),
    "behavior.py": ("brain", "행동 두뇌: CatBrain 상태머신, World(바닥·창 발판), IconField(차인 아이콘의 물리)"),
    "flow.py": ("brain", "행동 흐름(마르코프 연쇄)과 시간 배분 가중치. 화면과 무관해서 시험하기 쉽다"),
    "routine.py": ("brain", "하루 생활 리듬: 잠자는 시간·밥 시간·놀아 달라는 요구 (시계를 바꿔 끼울 수 있다)"),
    "pet.py": ("brain", "배고픔·기분·털색을 pet_state.json 에 저장"),
    "windows_info.py": ("brain", "열려 있는 창의 윗변(고양이가 올라설 발판)을 수집 (DWM 프레임 기준)"),
    "desktop_icons.py": ("brain", "바탕화면 아이콘(SysListView32)의 위치를 explorer 메모리를 통해 읽고 옮기고 복원"),
    "animations.py": ("draw", "뼈대 방식의 동작 라이브러리 (예전/비상용): f(a) → pose"),
    "animations_runtime.py": ("draw", "Animator: 동작 재생, 이동 거리에 맞춘 걸음 위상, 동작 전환 블렌딩"),
    "photocat.py": ("draw", "기본 그리개: 동작에 맞는 사진 컷을 골라 섞어 그림, 바닥 걸치기, 소품·그림자"),
    "coats.py": ("draw", "털색 바꾸기(털만 골라 색 입히기)와 또렷한 눈 그리기"),
    "catrig.py": ("draw", "뼈대 고양이 렌더러 (사진을 못 불러올 때의 비상용)"),
    "scheduler.py": ("notify", "정해 둔 시각에 알림 작업을 스레드로 실행, 놓친 시각 따라잡기"),
    "nethelper.py": ("notify", "네트워크·무거운 작업을 하는 짧게 사는 보조 프로세스 (JSON 한 줄 요청/응답)"),
    "calendar_ics.py": ("notify", "구글 캘린더 비공개 iCal 주소에서 오늘·앞으로 N시간 일정 가져오기"),
    "gemini_client.py": ("notify", "Gemini API 호출 (Interactions → generateContent 되돌림, 오류 한글화)"),
    "news_sources.py": ("notify", "날씨(Open-Meteo)·뉴스(Google News RSS)·시세(Yahoo)를 직접 모으기"),
    "mail_imap.py": ("notify", "Gmail IMAP: 안 읽은 새 메일의 '보낸 사람'만 읽기 (읽음 표시 안 함)"),
    "favicon.py": ("notify", "웹 주소의 사이트 아이콘 받기·보관"),
    "activity_log.py": ("notify", "5초마다 맨 앞 창을 기록해 하루 사용 기록(JSON) 만들기"),
    "catsound.py": ("notify", "울음소리 합성(numpy → wav)과 재생(winsound)"),
    "security.py": ("guard", "경비 본부 SecurityGuard: 감시기들을 켜고 끄고 사건을 Qt 신호로 연결"),
    "sec_ransom.py": ("guard", "랜섬웨어 감지기: 미끼 파일 + 대량 변경·엔트로피 + 몸값 안내 파일"),
    "sec_watch.py": ("guard", "폴더 감시: ReadDirectoryChangesW 직접 사용 (watchdog 보다 훨씬 가볍다)"),
    "sec_scan.py": ("guard", "자동 시작·실행 중 프로그램 점검 (기준 목록 비교 + 점수)"),
    "sec_sig.py": ("guard", "실행 파일 디지털 서명 확인 (PowerShell Get-AuthenticodeSignature, 결과 보관)"),
    "sec_privacy.py": ("guard", "카메라·마이크를 쓰는 처음 보는 프로그램 알림 (레지스트리 읽기)"),
    "sec_download.py": ("guard", "다운로드 폴더의 새 실행 파일 검사 (출처 표시·서명·이중 확장자)"),
    "sec_events.py": ("guard", "경보('쥐') 기록 저장소 (events.json, 30일·500건)"),
    "sec_common.py": ("guard", "경비 공용: 프로세스 목록·경로·해시·시스템 경로 판단·디스크 쓰기 상위 프로세스"),
    "sec_ui.py": ("guard", "경보 상세 창 AlertWindow와 '지금 해야 할 일' 단계 카드 StepFlow"),
    "vt_client.py": ("guard", "VirusTotal 해시 조회와 한도 지키기(Limiter)"),
    "balloon.py": ("ui", "여러 줄 풍선 창 (고양이 머리 위, 대기열)"),
    "notice_window.py": ("ui", "소식·어제 한 일을 Markdown 으로 보여 주는 창"),
    "launcher_ui.py": ("ui", "고양이를 누르면 열리는 반원 앱 런처, 앱 실행(launch)"),
    "app_register.py": ("ui", "'앱 등록…' 창 (파일·웹·명령·윈도우 도구)"),
    "settings_dialog.py": ("ui", "설정 창 6개 탭과 부품(FoldCard, StatusLabel, TimesEditor)"),
    "theme.py": ("ui", "공통 스타일시트(QSS)와 분홍 색 토큰"),
    "cute.py": ("ui", "분홍 디자인 부품: 팔레트·고양이 얼굴 아바타·아이콘·쥐 그림"),
    "config_store.py": ("store", "설정(launcher_config.json)과 비밀 값(DPAPI, secrets.json) 저장소"),
    "build_installer.py": ("pack", "PyInstaller 로 본체·삭제기·설치기(exe)를 만들어 하나로 묶기"),
    "installer/ops.py": ("pack", "설치·삭제 공용 동작: 바로가기, 시작 프로그램, 삭제 목록 등록, 실행 중인 고양이 끄기"),
    "installer/setup_app.py": ("pack", "설치 프로그램(DesktopCat_Setup.exe)"),
    "installer/uninstall_app.py": ("pack", "삭제 프로그램(uninstall.exe)"),
}


def flow_data():
    """flow.py 의 실제 값(행동 흐름·길이·가중치·묶음)을 문서의 '다음 행동 뽑기' 그림에 쓴다."""
    import sys
    sys.path.insert(0, str(ROOT))
    import flow
    return {"flow": {k: v for k, v in flow.FLOW.items() if isinstance(v, dict)}, "dur": {k: list(v) for k, v in flow.DUR.items()},
            "weights": flow.WEIGHTS_DAY, "weightsCorner": flow.WEIGHTS_CORNER, "group": flow.GROUP_OF, "targetDay": flow.TARGET_DAY, "targetCorner": flow.TARGET_CORNER}


def assemble(page):
    """docs/src/<page>/*.html 조각들을 이어 붙여 docs/<page>.html 을 만든다 (조각 파일 이름 순서가 문서 순서)."""
    src = ROOT / "docs" / "src"
    head = (src / ("_%s_head.html" % page)).read_text(encoding="utf-8")
    foot = (src / ("_%s_foot.html" % page)).read_text(encoding="utf-8")
    parts = sorted((src / page).glob("*.html"))
    body = chr(10).join(p.read_text(encoding="utf-8") for p in parts)
    (ROOT / "docs" / ("%s.html" % page)).write_text(head + body + foot, encoding="utf-8")
    print("%s.html ← 조각 %d개" % (page, len(parts)))


def main():
    files = sorted(ROOT.glob("*.py")) + sorted((ROOT / "installer").glob("*.py"))
    names = {}
    for f in files:
        rel = f.relative_to(ROOT).as_posix()
        names[f.stem if f.parent == ROOT else "installer." + f.stem] = rel
    mods, edges, lines_total = [], [], 0
    for f in files:
        rel = f.relative_to(ROOT).as_posix()
        if rel == "docs/build_docs.py":
            continue
        src = f.read_text(encoding="utf-8-sig")
        n = src.count("\n") + 1
        lines_total += n
        group, role = ROLES.get(rel, ("pack", ""))
        tree = ast.parse(src)
        top_level = {id(x) for x in tree.body}
        for node in ast.walk(tree):
            mod = None
            if isinstance(node, ast.Import):
                targets = [a.name.split(".")[0] for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                targets = [node.module.split(".")[0]]
            else:
                continue
            for t in targets:
                if t in names and names[t] != rel:
                    lazy = id(node) not in top_level
                    edges.append({"from": rel, "to": names[t], "lazy": lazy})
        mods.append({"file": rel, "lines": n, "group": group, "role": role})
    # 같은 쌍은 하나로 (바로 import 가 있으면 바로)
    uniq = {}
    for e in edges:
        k = (e["from"], e["to"])
        if k not in uniq or (uniq[k]["lazy"] and not e["lazy"]):
            uniq[k] = e
    data = {
        "groups": [{"id": g, "name": n} for g, n in GROUPS],
        "modules": mods,
        "edges": list(uniq.values()),
        "totals": {"files": len(mods), "lines": lines_total},
        "missingRoles": [m["file"] for m in mods if not m["role"]],
    }
    data.update(flow_data())
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("/* 자동 생성: python docs/build_docs.py (손으로 고치지 않는다) */\nwindow.DOCDATA = " + json.dumps(data, ensure_ascii=False, indent=1) + ";\n", encoding="utf-8")
    print("모듈 %d개, 합계 %d줄, import 관계 %d개 → %s" % (len(mods), lines_total, len(uniq), OUT))
    if data["missingRoles"]:
        print("역할 설명이 없는 파일:", data["missingRoles"])
    for page in ("tech", "manual"):
        if (ROOT / "docs" / "src" / ("_%s_head.html" % page)).exists():
            assemble(page)


if __name__ == "__main__":
    main()
