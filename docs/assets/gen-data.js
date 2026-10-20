/* 자동 생성: python docs/build_docs.py (손으로 고치지 않는다) */
window.DOCDATA = {
 "groups": [
  {
   "id": "run",
   "name": "실행·지킴이"
  },
  {
   "id": "brain",
   "name": "행동 두뇌"
  },
  {
   "id": "draw",
   "name": "그리기"
  },
  {
   "id": "notify",
   "name": "알림"
  },
  {
   "id": "guard",
   "name": "경비"
  },
  {
   "id": "ui",
   "name": "화면·디자인"
  },
  {
   "id": "store",
   "name": "저장·설정"
  },
  {
   "id": "pack",
   "name": "설치·배포"
  }
 ],
 "modules": [
  {
   "file": "activity_log.py",
   "lines": 286,
   "group": "notify",
   "role": "5초마다 맨 앞 창을 기록해 하루 사용 기록(JSON) 만들기"
  },
  {
   "file": "animations.py",
   "lines": 565,
   "group": "draw",
   "role": "뼈대 방식의 동작 라이브러리 (예전/비상용): f(a) → pose"
  },
  {
   "file": "animations_runtime.py",
   "lines": 48,
   "group": "draw",
   "role": "Animator: 동작 재생, 이동 거리에 맞춘 걸음 위상, 동작 전환 블렌딩"
  },
  {
   "file": "app_register.py",
   "lines": 204,
   "group": "ui",
   "role": "'앱 등록…' 창 (파일·웹·명령·윈도우 도구)"
  },
  {
   "file": "balloon.py",
   "lines": 171,
   "group": "ui",
   "role": "여러 줄 풍선 창 (고양이 머리 위, 대기열)"
  },
  {
   "file": "behavior.py",
   "lines": 1154,
   "group": "brain",
   "role": "행동 두뇌: CatBrain 상태머신, World(바닥·창 발판), IconField(차인 아이콘의 물리)"
  },
  {
   "file": "build_installer.py",
   "lines": 96,
   "group": "pack",
   "role": "PyInstaller 로 본체·삭제기·설치기(exe)를 만들어 하나로 묶기"
  },
  {
   "file": "calendar_ics.py",
   "lines": 167,
   "group": "notify",
   "role": "구글 캘린더 비공개 iCal 주소에서 오늘·앞으로 N시간 일정 가져오기"
  },
  {
   "file": "cat.py",
   "lines": 1168,
   "group": "run",
   "role": "본체: 투명 창(Overlay)·메뉴·트레이를 만들고 모든 부품을 조립해 24fps 프레임 루프를 돌린다"
  },
  {
   "file": "catrig.py",
   "lines": 1190,
   "group": "draw",
   "role": "뼈대 고양이 렌더러 (사진을 못 불러올 때의 비상용)"
  },
  {
   "file": "catsound.py",
   "lines": 72,
   "group": "notify",
   "role": "울음소리 합성(numpy → wav)과 재생(winsound)"
  },
  {
   "file": "coats.py",
   "lines": 275,
   "group": "draw",
   "role": "털색 바꾸기(털만 골라 색 입히기)와 또렷한 눈 그리기"
  },
  {
   "file": "config_store.py",
   "lines": 138,
   "group": "store",
   "role": "설정(launcher_config.json)과 비밀 값(DPAPI, secrets.json) 저장소"
  },
  {
   "file": "cute.py",
   "lines": 621,
   "group": "ui",
   "role": "분홍 디자인 부품: 팔레트·고양이 얼굴 아바타·아이콘·쥐 그림"
  },
  {
   "file": "desktop_icons.py",
   "lines": 319,
   "group": "brain",
   "role": "바탕화면 아이콘(SysListView32)의 위치를 explorer 메모리를 통해 읽고 옮기고 복원"
  },
  {
   "file": "favicon.py",
   "lines": 173,
   "group": "notify",
   "role": "웹 주소의 사이트 아이콘 받기·보관"
  },
  {
   "file": "flow.py",
   "lines": 179,
   "group": "brain",
   "role": "행동 흐름(마르코프 연쇄)과 시간 배분 가중치. 화면과 무관해서 시험하기 쉽다"
  },
  {
   "file": "gemini_client.py",
   "lines": 207,
   "group": "notify",
   "role": "Gemini API 호출 (Interactions → generateContent 되돌림, 오류 한글화)"
  },
  {
   "file": "guard_common.py",
   "lines": 101,
   "group": "run",
   "role": "지킴이와 본체가 같이 쓰는 도구: 데이터 폴더, 로그, 하트비트(공유 메모리), 종료 이벤트, 자원 측정 (표준 라이브러리만)"
  },
  {
   "file": "launcher.py",
   "lines": 110,
   "group": "run",
   "role": "지킴이. 고양이(worker)를 따로 띄워 살려 두고, --quit / --worker / --net-helper 도 여기서 갈라진다"
  },
  {
   "file": "launcher_ui.py",
   "lines": 534,
   "group": "ui",
   "role": "고양이를 누르면 열리는 반원 앱 런처, 앱 실행(launch)"
  },
  {
   "file": "mail_imap.py",
   "lines": 142,
   "group": "notify",
   "role": "Gmail IMAP: 안 읽은 새 메일의 '보낸 사람'만 읽기 (읽음 표시 안 함)"
  },
  {
   "file": "nethelper.py",
   "lines": 130,
   "group": "notify",
   "role": "네트워크·무거운 작업을 하는 짧게 사는 보조 프로세스 (JSON 한 줄 요청/응답)"
  },
  {
   "file": "news_sources.py",
   "lines": 194,
   "group": "notify",
   "role": "날씨(Open-Meteo)·뉴스(Google News RSS)·시세(Yahoo)를 직접 모으기"
  },
  {
   "file": "notice_window.py",
   "lines": 141,
   "group": "ui",
   "role": "소식·어제 한 일을 Markdown 으로 보여 주는 창"
  },
  {
   "file": "pet.py",
   "lines": 92,
   "group": "brain",
   "role": "배고픔·기분·털색을 pet_state.json 에 저장"
  },
  {
   "file": "photocat.py",
   "lines": 507,
   "group": "draw",
   "role": "기본 그리개: 동작에 맞는 사진 컷을 골라 섞어 그림, 바닥 걸치기, 소품·그림자"
  },
  {
   "file": "routine.py",
   "lines": 163,
   "group": "brain",
   "role": "하루 생활 리듬: 잠자는 시간·밥 시간·놀아 달라는 요구 (시계를 바꿔 끼울 수 있다)"
  },
  {
   "file": "scheduler.py",
   "lines": 117,
   "group": "notify",
   "role": "정해 둔 시각에 알림 작업을 스레드로 실행, 놓친 시각 따라잡기"
  },
  {
   "file": "sec_common.py",
   "lines": 154,
   "group": "guard",
   "role": "경비 공용: 프로세스 목록·경로·해시·시스템 경로 판단·디스크 쓰기 상위 프로세스"
  },
  {
   "file": "sec_download.py",
   "lines": 179,
   "group": "guard",
   "role": "다운로드 폴더의 새 실행 파일 검사 (출처 표시·서명·이중 확장자)"
  },
  {
   "file": "sec_events.py",
   "lines": 127,
   "group": "guard",
   "role": "경보('쥐') 기록 저장소 (events.json, 30일·500건)"
  },
  {
   "file": "sec_privacy.py",
   "lines": 136,
   "group": "guard",
   "role": "카메라·마이크를 쓰는 처음 보는 프로그램 알림 (레지스트리 읽기)"
  },
  {
   "file": "sec_ransom.py",
   "lines": 512,
   "group": "guard",
   "role": "랜섬웨어 감지기: 미끼 파일 + 대량 변경·엔트로피 + 몸값 안내 파일"
  },
  {
   "file": "sec_scan.py",
   "lines": 398,
   "group": "guard",
   "role": "자동 시작·실행 중 프로그램 점검 (기준 목록 비교 + 점수)"
  },
  {
   "file": "sec_sig.py",
   "lines": 102,
   "group": "guard",
   "role": "실행 파일 디지털 서명 확인 (PowerShell Get-AuthenticodeSignature, 결과 보관)"
  },
  {
   "file": "sec_ui.py",
   "lines": 306,
   "group": "guard",
   "role": "경보 상세 창 AlertWindow와 '지금 해야 할 일' 단계 카드 StepFlow"
  },
  {
   "file": "sec_watch.py",
   "lines": 138,
   "group": "guard",
   "role": "폴더 감시: ReadDirectoryChangesW 직접 사용 (watchdog 보다 훨씬 가볍다)"
  },
  {
   "file": "security.py",
   "lines": 289,
   "group": "guard",
   "role": "경비 본부 SecurityGuard: 감시기들을 켜고 끄고 사건을 Qt 신호로 연결"
  },
  {
   "file": "settings_dialog.py",
   "lines": 1037,
   "group": "ui",
   "role": "설정 창 6개 탭과 부품(FoldCard, StatusLabel, TimesEditor)"
  },
  {
   "file": "theme.py",
   "lines": 163,
   "group": "ui",
   "role": "공통 스타일시트(QSS)와 분홍 색 토큰"
  },
  {
   "file": "vt_client.py",
   "lines": 121,
   "group": "guard",
   "role": "VirusTotal 해시 조회와 한도 지키기(Limiter)"
  },
  {
   "file": "windows_info.py",
   "lines": 90,
   "group": "brain",
   "role": "열려 있는 창의 윗변(고양이가 올라설 발판)을 수집 (DWM 프레임 기준)"
  },
  {
   "file": "installer/ops.py",
   "lines": 168,
   "group": "pack",
   "role": "설치·삭제 공용 동작: 바로가기, 시작 프로그램, 삭제 목록 등록, 실행 중인 고양이 끄기"
  },
  {
   "file": "installer/setup_app.py",
   "lines": 200,
   "group": "pack",
   "role": "설치 프로그램(DesktopCat_Setup.exe)"
  },
  {
   "file": "installer/uninstall_app.py",
   "lines": 88,
   "group": "pack",
   "role": "삭제 프로그램(uninstall.exe)"
  }
 ],
 "edges": [
  {
   "from": "animations.py",
   "to": "catrig.py",
   "lazy": false
  },
  {
   "from": "animations_runtime.py",
   "to": "animations.py",
   "lazy": false
  },
  {
   "from": "animations_runtime.py",
   "to": "catrig.py",
   "lazy": false
  },
  {
   "from": "app_register.py",
   "to": "cute.py",
   "lazy": false
  },
  {
   "from": "balloon.py",
   "to": "cute.py",
   "lazy": false
  },
  {
   "from": "behavior.py",
   "to": "flow.py",
   "lazy": false
  },
  {
   "from": "behavior.py",
   "to": "animations_runtime.py",
   "lazy": false
  },
  {
   "from": "behavior.py",
   "to": "windows_info.py",
   "lazy": false
  },
  {
   "from": "cat.py",
   "to": "guard_common.py",
   "lazy": false
  },
  {
   "from": "cat.py",
   "to": "animations.py",
   "lazy": false
  },
  {
   "from": "cat.py",
   "to": "coats.py",
   "lazy": false
  },
  {
   "from": "cat.py",
   "to": "nethelper.py",
   "lazy": false
  },
  {
   "from": "cat.py",
   "to": "behavior.py",
   "lazy": false
  },
  {
   "from": "cat.py",
   "to": "animations_runtime.py",
   "lazy": false
  },
  {
   "from": "cat.py",
   "to": "catrig.py",
   "lazy": false
  },
  {
   "from": "cat.py",
   "to": "app_register.py",
   "lazy": false
  },
  {
   "from": "cat.py",
   "to": "activity_log.py",
   "lazy": false
  },
  {
   "from": "cat.py",
   "to": "balloon.py",
   "lazy": false
  },
  {
   "from": "cat.py",
   "to": "catsound.py",
   "lazy": false
  },
  {
   "from": "cat.py",
   "to": "gemini_client.py",
   "lazy": false
  },
  {
   "from": "cat.py",
   "to": "config_store.py",
   "lazy": false
  },
  {
   "from": "cat.py",
   "to": "desktop_icons.py",
   "lazy": false
  },
  {
   "from": "cat.py",
   "to": "favicon.py",
   "lazy": false
  },
  {
   "from": "cat.py",
   "to": "launcher_ui.py",
   "lazy": false
  },
  {
   "from": "cat.py",
   "to": "cute.py",
   "lazy": false
  },
  {
   "from": "cat.py",
   "to": "theme.py",
   "lazy": false
  },
  {
   "from": "cat.py",
   "to": "notice_window.py",
   "lazy": false
  },
  {
   "from": "cat.py",
   "to": "pet.py",
   "lazy": false
  },
  {
   "from": "cat.py",
   "to": "photocat.py",
   "lazy": false
  },
  {
   "from": "cat.py",
   "to": "routine.py",
   "lazy": false
  },
  {
   "from": "cat.py",
   "to": "sec_ui.py",
   "lazy": false
  },
  {
   "from": "cat.py",
   "to": "security.py",
   "lazy": false
  },
  {
   "from": "cat.py",
   "to": "scheduler.py",
   "lazy": false
  },
  {
   "from": "cat.py",
   "to": "settings_dialog.py",
   "lazy": false
  },
  {
   "from": "cat.py",
   "to": "windows_info.py",
   "lazy": false
  },
  {
   "from": "catrig.py",
   "to": "coats.py",
   "lazy": false
  },
  {
   "from": "launcher.py",
   "to": "guard_common.py",
   "lazy": false
  },
  {
   "from": "launcher.py",
   "to": "nethelper.py",
   "lazy": true
  },
  {
   "from": "launcher.py",
   "to": "cat.py",
   "lazy": true
  },
  {
   "from": "launcher_ui.py",
   "to": "cute.py",
   "lazy": false
  },
  {
   "from": "launcher_ui.py",
   "to": "favicon.py",
   "lazy": false
  },
  {
   "from": "nethelper.py",
   "to": "calendar_ics.py",
   "lazy": true
  },
  {
   "from": "nethelper.py",
   "to": "gemini_client.py",
   "lazy": true
  },
  {
   "from": "nethelper.py",
   "to": "vt_client.py",
   "lazy": true
  },
  {
   "from": "nethelper.py",
   "to": "sec_scan.py",
   "lazy": true
  },
  {
   "from": "nethelper.py",
   "to": "favicon.py",
   "lazy": true
  },
  {
   "from": "nethelper.py",
   "to": "mail_imap.py",
   "lazy": true
  },
  {
   "from": "nethelper.py",
   "to": "news_sources.py",
   "lazy": true
  },
  {
   "from": "notice_window.py",
   "to": "cute.py",
   "lazy": false
  },
  {
   "from": "photocat.py",
   "to": "coats.py",
   "lazy": false
  },
  {
   "from": "sec_download.py",
   "to": "sec_common.py",
   "lazy": false
  },
  {
   "from": "sec_download.py",
   "to": "sec_sig.py",
   "lazy": false
  },
  {
   "from": "sec_download.py",
   "to": "sec_watch.py",
   "lazy": true
  },
  {
   "from": "sec_privacy.py",
   "to": "sec_common.py",
   "lazy": true
  },
  {
   "from": "sec_ransom.py",
   "to": "sec_watch.py",
   "lazy": true
  },
  {
   "from": "sec_ransom.py",
   "to": "sec_common.py",
   "lazy": true
  },
  {
   "from": "sec_scan.py",
   "to": "sec_common.py",
   "lazy": false
  },
  {
   "from": "sec_scan.py",
   "to": "sec_sig.py",
   "lazy": false
  },
  {
   "from": "sec_ui.py",
   "to": "cute.py",
   "lazy": false
  },
  {
   "from": "sec_ui.py",
   "to": "sec_common.py",
   "lazy": false
  },
  {
   "from": "security.py",
   "to": "sec_common.py",
   "lazy": false
  },
  {
   "from": "security.py",
   "to": "sec_events.py",
   "lazy": false
  },
  {
   "from": "security.py",
   "to": "nethelper.py",
   "lazy": true
  },
  {
   "from": "security.py",
   "to": "vt_client.py",
   "lazy": true
  },
  {
   "from": "security.py",
   "to": "sec_privacy.py",
   "lazy": true
  },
  {
   "from": "security.py",
   "to": "sec_ransom.py",
   "lazy": true
  },
  {
   "from": "security.py",
   "to": "sec_download.py",
   "lazy": true
  },
  {
   "from": "settings_dialog.py",
   "to": "calendar_ics.py",
   "lazy": false
  },
  {
   "from": "settings_dialog.py",
   "to": "cute.py",
   "lazy": false
  },
  {
   "from": "settings_dialog.py",
   "to": "gemini_client.py",
   "lazy": false
  },
  {
   "from": "settings_dialog.py",
   "to": "news_sources.py",
   "lazy": false
  },
  {
   "from": "settings_dialog.py",
   "to": "activity_log.py",
   "lazy": true
  },
  {
   "from": "installer/ops.py",
   "to": "guard_common.py",
   "lazy": false
  }
 ],
 "totals": {
  "files": 46,
  "lines": 13472
 },
 "missingRoles": [],
 "flow": {
  "start": {
   "sit": 3,
   "idle": 3,
   "sittilt": 2,
   "walk": 2,
   "groom": 1,
   "loaf": 1,
   "yawn": 0.5
  },
  "walk": {
   "idle": 3,
   "sit": 2,
   "walk": 2,
   "trot": 0.5,
   "sneak": 1,
   "jump": 1.5,
   "kick": 1,
   "scratch": 1,
   "groom": 1,
   "sittilt": 1,
   "run": 0.5,
   "travel": 1
  },
  "trot": {
   "walk": 2,
   "idle": 3,
   "sit": 2,
   "run": 1,
   "jump": 1,
   "kick": 1,
   "groom": 1
  },
  "run": {
   "walk": 3,
   "trot": 1,
   "idle": 4,
   "sit": 2,
   "groomface": 2,
   "groom": 2,
   "tailplay": 0.5
  },
  "sneak": {
   "kick": 3,
   "run": 2,
   "walk": 2,
   "idle": 1.5,
   "jump": 1,
   "sit": 0.5
  },
  "jump": {
   "idle": 3,
   "sit": 3,
   "walk": 2,
   "groom": 1,
   "sittilt": 1,
   "scratch": 0.5
  },
  "kick": {
   "idle": 3,
   "walk": 3,
   "trot": 1,
   "sit": 2,
   "groom": 1,
   "run": 1
  },
  "travel": {
   "idle": 3,
   "sit": 2,
   "walk": 2,
   "groom": 1,
   "sittilt": 1
  },
  "idle": {
   "walk": 3,
   "sit": 3,
   "sittilt": 2,
   "sneak": 1,
   "groom": 1.5,
   "yawn": 1,
   "stretch": 1,
   "scratch": 1,
   "jump": 1,
   "trot": 1,
   "kick": 0.5,
   "travel": 0.5,
   "tailplay": 0.5,
   "loaf": 0.5
  },
  "sit": {
   "sittilt": 3,
   "groom": 2,
   "groomface": 1.5,
   "groomleg": 1,
   "scratchneck": 1,
   "loaf": 2.5,
   "idle": 2,
   "yawn": 1.2,
   "walk": 1.2,
   "sleep": 1,
   "stretch": 0.5,
   "tailplay": 1
  },
  "sittilt": {
   "sit": 3,
   "idle": 2,
   "walk": 2,
   "jump": 1,
   "groom": 1,
   "groomface": 1,
   "loaf": 1,
   "yawn": 0.5,
   "sleep": 0.5
  },
  "loaf": {
   "sleep": 4,
   "groom": 2,
   "groomface": 1,
   "yawn": 1.5,
   "sit": 1,
   "knead": 1,
   "stretch": 1,
   "idle": 0.5
  },
  "knead": {
   "loaf": 4,
   "sleep": 3,
   "sit": 1,
   "groom": 1,
   "yawn": 0.5
  },
  "sleep": {
   "yawn": 4,
   "stretch": 4,
   "sit": 2,
   "groomface": 2,
   "loaf": 1,
   "idle": 1
  },
  "yawn": {
   "stretch": 3,
   "sit": 3,
   "idle": 2,
   "groomface": 2,
   "loaf": 1.5,
   "sleep": 1.5,
   "walk": 1,
   "scratchneck": 1
  },
  "stretch": {
   "walk": 4,
   "trot": 1,
   "idle": 3,
   "sit": 2,
   "scratch": 1,
   "sneak": 0.5,
   "groom": 0.5,
   "jump": 0.5
  },
  "groom": {
   "groomface": 2.0,
   "groomleg": 1.5,
   "groom": 0.6,
   "scratchneck": 1.0,
   "sit": 2.0,
   "loaf": 2.0,
   "sleep": 1.5,
   "yawn": 1.0,
   "idle": 1.0,
   "walk": 0.8
  },
  "groomface": {
   "groomface": 2.0,
   "groomleg": 1.5,
   "groom": 0.6,
   "scratchneck": 1.0,
   "sit": 2.0,
   "loaf": 2.0,
   "sleep": 1.5,
   "yawn": 1.0,
   "idle": 1.0,
   "walk": 0.8
  },
  "groomleg": {
   "groomface": 2.0,
   "groomleg": 1.5,
   "groom": 0.6,
   "scratchneck": 1.0,
   "sit": 2.0,
   "loaf": 2.0,
   "sleep": 1.5,
   "yawn": 1.0,
   "idle": 1.0,
   "walk": 0.8
  },
  "scratchneck": {
   "groom": 1,
   "sit": 2,
   "idle": 2,
   "walk": 1.5,
   "loaf": 1
  },
  "scratch": {
   "walk": 2,
   "sit": 2,
   "idle": 2,
   "groom": 1,
   "stretch": 1
  },
  "tailplay": {
   "groom": 2,
   "sit": 2,
   "idle": 2,
   "run": 1,
   "walk": 1,
   "loaf": 0.5
  },
  "eat": {
   "groomface": 4,
   "sit": 2,
   "loaf": 2,
   "sleep": 2,
   "walk": 1,
   "idle": 1
  },
  "play": {
   "sit": 3,
   "idle": 3,
   "groomface": 2,
   "loaf": 1,
   "yawn": 1,
   "trot": 0.5
  }
 },
 "dur": {
  "walk": [
   3,
   7
  ],
  "trot": [
   3,
   6
  ],
  "run": [
   2,
   3.5
  ],
  "sneak": [
   3,
   6
  ],
  "jump": [
   1.2,
   2.0
  ],
  "kick": [
   6,
   10
  ],
  "travel": [
   8,
   20
  ],
  "idle": [
   3,
   8
  ],
  "sit": [
   8,
   22
  ],
  "sittilt": [
   10,
   25
  ],
  "loaf": [
   15,
   40
  ],
  "sleep": [
   40,
   150
  ],
  "groom": [
   6,
   12
  ],
  "groomleg": [
   5,
   8
  ],
  "groomface": [
   6,
   10
  ],
  "scratchneck": [
   3,
   5
  ],
  "scratch": [
   2.5,
   4
  ],
  "yawn": [
   2.4,
   2.4
  ],
  "stretch": [
   3.6,
   3.6
  ],
  "knead": [
   6,
   10
  ],
  "tailplay": [
   4,
   7
  ]
 },
 "weights": {
  "walk": 1.014,
  "trot": 1.014,
  "run": 1.014,
  "sneak": 1.014,
  "jump": 1.014,
  "kick": 4.348,
  "travel": 1.014,
  "idle": 0.757,
  "sit": 0.757,
  "sittilt": 0.757,
  "loaf": 0.757,
  "sleep": 1.002,
  "groom": 1.163,
  "groomleg": 1.163,
  "groomface": 1.163,
  "scratchneck": 1.163,
  "scratch": 1.163,
  "yawn": 1.672,
  "stretch": 1.672,
  "knead": 4.348,
  "tailplay": 4.348
 },
 "weightsCorner": {
  "sit": 0.547,
  "sittilt": 0.547,
  "loaf": 0.547,
  "sleep": 1.27,
  "groom": 1.071,
  "groomleg": 1.071,
  "groomface": 1.071,
  "scratchneck": 1.071,
  "yawn": 1.609,
  "stretch": 1.609,
  "knead": 23.205,
  "idle": 0.547
 },
 "group": {
  "sleep": "잠",
  "idle": "쉬기",
  "sit": "쉬기",
  "sittilt": "쉬기",
  "loaf": "쉬기",
  "groom": "그루밍",
  "groomleg": "그루밍",
  "groomface": "그루밍",
  "scratchneck": "그루밍",
  "scratch": "그루밍",
  "walk": "이동",
  "trot": "이동",
  "run": "이동",
  "sneak": "이동",
  "jump": "이동",
  "travel": "이동",
  "kick": "놀이",
  "knead": "놀이",
  "tailplay": "놀이",
  "yawn": "하품·기지개",
  "stretch": "하품·기지개"
 },
 "targetDay": {
  "잠": 36,
  "쉬기": 32,
  "그루밍": 13,
  "이동": 8,
  "놀이": 6,
  "하품·기지개": 3
 },
 "targetCorner": {
  "잠": 54,
  "쉬기": 28,
  "그루밍": 12,
  "놀이": 2,
  "하품·기지개": 4
 }
};
