/* 사용자 매뉴얼: 조작 연습장 · 메뉴 · 하루 일과표 · 경보 창 예시 · 알림 시뮬레이터 · FAQ 검색 */
(window.PageInits = window.PageInits || []).push(function () {
  const { $, $$, NS, mountMascot } = window.DocUtil;
  const svgEl = (tag, attrs = {}, parent) => { const e = document.createElementNS(NS, tag); for (const k in attrs) { e.setAttribute(k, attrs[k]); } if (parent) { parent.appendChild(e); } return e; };
  const INK = "#5A3A47", PINK = "#F67499", PINK_D = "#E5557E", PINK_L = "#EF99B1", LINE = "#F6C5D5";
  const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
  const hhmm = (m) => String(Math.floor(m / 60)).padStart(2, "0") + ":" + String(m % 60).padStart(2, "0");
  const toMin = (s) => { const m = /^(\d{1,2}):(\d{2})$/.exec((s || "").trim()); return m && +m[1] < 24 && +m[2] < 60 ? +m[1] * 60 + +m[2] : null; };

  /* ================= 조작 연습장 ================= */
  (function playground() {
    const box = $("#pg"); if (!box) { return; }
    const desk = $("#pg-desk"), catEl = $("#pg-cat"), host = $("#pg-mascot"), cap = $("#pg-cap"), launcher = $("#pg-launcher"), ball = $("#pg-ball"), fish = $("#pg-fish");
    const m = mountMascot(host); if (m.bubble) { m.bubble.style.top = "-42px"; m.bubble.style.left = "-16px"; }
    const FLOOR = 34, WIN = { l: 18, r: 188, top: 106 }; // 바닥(아래에서 34px) · 내 작업 창(위에서 106px)
    const S = { x: 0, b: FLOOR, vx: 0, vy: 0, mode: "idle", held: false, energy: 0, hist: [], launcherOpen: false, rest: false, fed: [] };
    const W = () => desk.clientWidth, H = () => desk.clientHeight, CW = 120;
    function setPos() { catEl.style.left = (S.x - CW / 2) + "px"; catEl.style.bottom = S.b + "px"; }
    function reset() { S.x = W() * 0.6; S.b = FLOOR; S.vx = S.vy = 0; S.mode = "idle"; S.rest = false; closeLauncher(); m.mood = "normal"; ball.style.display = fish.style.display = "none"; setPos(); note("고양이를 <b>클릭</b>하면 앱 런처가 열려요. <b>끌어서 놓으면</b> 떨어지고, 몸 위에서 <b>쓱쓱</b> 문지르면 좋아해요."); }
    const note = (h) => (cap.innerHTML = h);
    let moodT = 0; const mood = (k, secs = 1.6) => { m.mood = k; clearTimeout(moodT); moodT = setTimeout(() => { m.mood = S.rest ? "sleep" : "normal"; }, secs * 1000); };

    /* 런처 (반원) */
    const ITEMS = [["캘", "구글 캘린더", "#DCE8FF"], ["G", "Gmail", "#FFD3E0"], ["구", "구글", "#FFF1C9"], ["유", "유튜브", "#FFD3D0"], ["앱", "내가 등록한 앱", "#D7F3E3"]];
    let closeT = 0;
    function openLauncher() {
      launcher.innerHTML = ""; const R = 98, B = 25, w = 2 * (R + B + 8), h = R + B + 40;
      const svg = svgEl("svg", { viewBox: `0 0 ${w} ${h}`, width: w, height: h }, launcher); const cx = w / 2, cy = h - 12;
      const pol = (r, a) => [cx + r * Math.cos(a * Math.PI / 180), cy - r * Math.sin(a * Math.PI / 180)];
      const [x0o, y0o] = pol(R + B, 12), [x1o, y1o] = pol(R + B, 168), [x1i, y1i] = pol(R - B, 168), [x0i, y0i] = pol(R - B, 12);
      svgEl("path", { d: `M${x0o} ${y0o} A${R + B} ${R + B} 0 0 0 ${x1o} ${y1o} L${x1i} ${y1i} A${R - B} ${R - B} 0 0 1 ${x0i} ${y0i} Z`, fill: "#fff", stroke: INK, "stroke-width": 3 }, svg);
      [12, 168].forEach((a) => { const [x, y] = pol(R, a); svgEl("circle", { cx: x, cy: y, r: B, fill: "#fff", stroke: INK, "stroke-width": 3 }, svg); });
      const label = svgEl("text", { x: cx, y: cy - R - B - 8, "text-anchor": "middle", style: "font-size:13px;font-weight:800;fill:" + INK }, svg);
      ITEMS.forEach(([t, name, col], i) => {
        const ang = 168 - 8 - (168 - 12 - 16) * (i / (ITEMS.length - 1)); const [x, y] = pol(R, ang);
        const g = svgEl("g", { style: "cursor:pointer" }, svg);
        svgEl("circle", { cx: x, cy: y, r: 17, fill: col, stroke: INK, "stroke-width": 2.5 }, g);
        const tx = svgEl("text", { x, y: y + 5, "text-anchor": "middle", style: "font-size:14px;font-weight:800;fill:" + INK }, g); tx.textContent = t;
        g.addEventListener("pointerenter", () => { label.textContent = name; });
        g.addEventListener("pointerleave", () => { label.textContent = ""; });
        g.addEventListener("click", (e) => { e.stopPropagation(); m.say(name + " 열었다냥!"); mood("happy", 1.4); closeLauncher(); note(`<b>${name}</b> 아이콘을 눌렀어요. 실제로는 그 프로그램·사이트가 열리고 런처가 닫혀요.`); });
      });
      launcher.style.display = "block"; S.launcherOpen = true; positionLauncher(); clearTimeout(closeT); closeT = setTimeout(closeLauncher, 8000);
      m.say("뭘 할까냥?", 2.4); note("런처가 열렸어요. 아이콘에 마우스를 올리면 <b>이름</b>이 나와요. 고양이를 다시 클릭하거나 바깥을 클릭하면 닫혀요(8초 뒤에도 닫혀요).");
    }
    function positionLauncher() { if (!S.launcherOpen) { return; } const w = parseFloat(launcher.firstChild.getAttribute("width")), h = parseFloat(launcher.firstChild.getAttribute("height")); launcher.style.left = (S.x - w / 2) + "px"; launcher.style.top = (H() - S.b - 70 - h + 20) + "px"; }
    function closeLauncher() { S.launcherOpen = false; launcher.style.display = "none"; clearTimeout(closeT); }
    desk.addEventListener("pointerdown", (e) => { if (S.launcherOpen && !e.target.closest("#pg-launcher") && !e.target.closest("#pg-cat")) { closeLauncher(); } });

    /* 고양이 조작 */
    catEl.addEventListener("click", (e) => e.stopPropagation(), true); // 마스코트의 기본 클릭 말풍선을 막는다
    let pressed = null;
    catEl.addEventListener("pointerdown", (e) => { pressed = { x: e.clientX, y: e.clientY, t: performance.now() }; S.hist = []; catEl.setPointerCapture(e.pointerId); catEl.style.cursor = "grabbing"; });
    catEl.addEventListener("pointermove", (e) => {
      const r = desk.getBoundingClientRect();
      if (pressed) {
        if (!S.held && Math.hypot(e.clientX - pressed.x, e.clientY - pressed.y) > 6) { S.held = true; S.mode = "held"; closeLauncher(); m.say("냥?! 뭐냐옹?!", 1.5); note("매달렸어요! 놓으면 떨어지고, <b>끌면서 놓으면 던져져요</b>."); }
        if (S.held) { S.x = clamp(e.clientX - r.left, CW / 2, W() - CW / 2); S.b = clamp(r.bottom - e.clientY - 70, 0, H() - 90); S.hist.push([performance.now(), S.x, S.b]); S.hist = S.hist.slice(-6); setPos(); }
      } else {
        S.energy = Math.min(140, S.energy + Math.hypot(e.movementX, e.movementY));
        if (S.energy >= 140 && !S.held) { S.energy = 0; m.say("좋다냐옹~ ❤", 1.4); mood("happy", 1.6); note("쓰다듬기! 몸 위에서 마우스를 쓱쓱 움직이면(클릭 아님) 골골 하며 기분이 좋아져요."); }
      }
    });
    catEl.addEventListener("pointerup", (e) => {
      catEl.style.cursor = "grab";
      if (S.held) { const h = S.hist; if (h.length >= 2 && h[h.length - 1][0] > h[0][0]) { const dt = (h[h.length - 1][0] - h[0][0]) / 1000; S.vx = clamp((h[h.length - 1][1] - h[0][1]) / dt, -700, 700); S.vy = clamp((h[h.length - 1][2] - h[0][2]) / dt, -500, 500); } else { S.vx = S.vy = 0; } S.mode = "fall"; S.held = false; }
      else if (pressed) { S.launcherOpen ? closeLauncher() : openLauncher(); }
      pressed = null;
    });
    setInterval(() => { S.energy = Math.max(0, S.energy - 26); }, 100);

    /* 물리 */
    let last = performance.now();
    (function loop(now) {
      const dt = Math.min(0.05, (now - last) / 1000); last = now;
      if (S.mode === "fall") {
        S.vy -= 1800 * dt * 0.6; S.x += S.vx * dt; S.b += S.vy * dt; S.vx *= Math.exp(-1.5 * dt); S.x = clamp(S.x, CW / 2, W() - CW / 2);
        const onWin = S.x > WIN.l + 8 && S.x < WIN.r - 8; const winB = H() - WIN.top;
        if (S.vy <= 0 && onWin && S.b <= winB && S.b - S.vy * dt >= winB - 1) { S.b = winB; S.mode = "idle"; S.vy = 0; m.say("창 위에 착지!", 1.4); note("작업 창 위에 내려앉았어요! 실제 고양이도 열린 창의 윗변을 걸어 다니고 뛰어올라요."); }
        else if (S.b <= FLOOR) { S.b = FLOOR; S.mode = "idle"; S.vy = 0; m.say("착지냥~", 1.2); }
        setPos();
      } else if (S.mode === "idle" && S.b > FLOOR && !(S.x > WIN.l + 8 && S.x < WIN.r - 8 && S.b >= H() - WIN.top - 1)) { S.mode = "fall"; }
      positionLauncher();
      requestAnimationFrame(loop);
    })(last);

    /* 버튼 */
    const go = (x, ms, done) => { catEl.style.transition = `left ${ms}ms ease`; S.x = clamp(x, CW / 2, W() - CW / 2); setPos(); setTimeout(() => { catEl.style.transition = ""; if (done) { done(); } }, ms + 30); };
    $$("[data-act]", box).forEach((b) => b.addEventListener("click", () => {
      const a = b.dataset.act; closeLauncher();
      if (a === "reset") { reset(); return; }
      if (S.mode === "held" || S.mode === "fall") { return; }
      if (a === "feed") {
        const now = performance.now(); S.fed = S.fed.filter((t) => now - t < 9000); S.fed.push(now);
        if (S.fed.length > 3) { m.say("배부르당..옹~ 😾", 2); note("너무 많이 줬어요! 배고픔이 10% 아래(배부름)면 간식을 거절해요."); return; }
        fish.style.left = clamp(S.x + 50, 10, W() - 60) + "px"; fish.style.display = "block"; m.say("🐟 냠냠냥~", 2.2); mood("happy", 2.4);
        setTimeout(() => { fish.style.display = "none"; m.say("😋 맛있당..옹~", 1.8); }, 2400); note("밥을 줬어요. 먹고 나면 세수(그루밍)를 하고 쉬어요. 배고픔 −45%, 기분 +5%.");
      }
      if (a === "play") {
        const bx = S.x < W() / 2 ? S.x + 170 : S.x - 170; ball.style.left = clamp(bx, 10, W() - 40) + "px"; ball.style.display = "block"; m.say("🧶 털실이다냐옹~!", 1.8);
        go(parseFloat(ball.style.left) - 30, 900, () => { mood("happy", 2); m.say("😸 재밌냐옹~", 2); setTimeout(() => (ball.style.display = "none"), 1800); }); note("털실공 놀이! 실제로는 엉덩이 씰룩 → 덮치기 → 툭 치기 → 쫓아가기를 세 번 하고 끌어안아요. 기분 +20%.");
      }
      if (a === "rest") {
        S.rest = !S.rest; b.classList.toggle("on", S.rest);
        if (S.rest) { go(W() - 70, 1200, () => { m.mood = "sleep"; m.say("구석에서 쉬겠다옹~ 🛌", 2.4); }); note("<b>한쪽에서 쉬기</b>: 구석으로 가서 얌전히 쉬어요. 돌아다니지 않아서 일에 방해가 안 돼요."); }
        else { m.mood = "normal"; m.say("다시 놀러 간다냥~ 🐾", 2); go(W() * 0.5, 900); }
      }
    }));
    window.addEventListener("resize", () => { S.x = clamp(S.x, CW / 2, W() - CW / 2); setPos(); });
    reset();
  })();

  /* ================= 우클릭 메뉴 ================= */
  (function menu() {
    const list = $("#menu-items"), desc = $("#menu-desc"); if (!list) { return; }
    const I = [
      ["밥 주기", "간식을 줘요. 배고픔 −45%. 배고픔이 10% 아래(배부름)면 거절해요. 밥 시간에 조를 때는 배불러도 먹어요."],
      ["놀아주기", "털실공 놀이를 시작해요. 기분 +20%. 점프·낙하 중이면 끝난 뒤에 시작해요."],
      ["한쪽에서 쉬기", "체크하면 구석으로 가서 얌전히 쉬어요(체크 해제하면 다시 놀러 다녀요). 일하는 중에 방해될 때 쓰세요.", "check"],
      ["—"],
      ["고양이 색  ▸", "갈색 줄무늬 · 회색 · 검은색 · 흰색 · 치즈(주황) · 삼색(흰·주황·검정). 고른 색은 기억해요. 눈과 귀 안쪽 분홍은 그대로예요."],
      ["—"],
      ["앱 등록…", "런처에 프로그램·웹·명령·윈도우 도구 아이콘을 추가해요."],
      ["등록한 앱 지우기  ▸", "등록한 앱 목록이 펼쳐져요. 이름을 누르면 바로 지워져요(기본 4개는 목록에 없어요)."],
      ["설정…", "탭 6개(캘린더·소식·메일·어제 한 일·생활·경비)가 있는 설정 창을 열어요. 다른 창을 막지 않아요."],
      ["—"],
      ["아이콘 차기", "체크하면 가끔 바탕화면 아이콘을 발로 차요. 처음엔 꺼져 있어요. 바탕화면 '자동 정렬'이 켜져 있으면 쓸 수 없어요.", "check"],
      ["아이콘 원래대로", "찬 아이콘을 모두 제자리로 돌려놓아요. 내가 직접 옮긴 아이콘은 건드리지 않아요."],
      ["—"],
      ["종료", "고양이와 지킴이를 정상 종료해요. 바탕화면 아이콘이 원래 자리로 돌아오고 기록이 저장돼요."],
    ];
    I.forEach((it) => {
      if (it[0] === "—") { const hr = document.createElement("div"); hr.style.cssText = "height:2px;background:#F6C5D5;margin:4px 8px"; list.appendChild(hr); return; }
      const row = document.createElement("div"); row.style.cssText = "padding:5px 12px;border-radius:10px;cursor:pointer;font-size:14px;font-weight:700"; row.textContent = (it[2] === "check" ? "☐  " : "") + it[0];
      const on = () => { $$("div", list).forEach((x) => (x.style.background = "")); row.style.background = "#FFD3E0"; desc.innerHTML = `<h4 style="margin:0 0 6px">${it[0].replace(/\s+▸/, "")}</h4><p>${it[1]}</p>`; };
      row.addEventListener("pointerenter", on); row.addEventListener("click", on); list.appendChild(row);
    });
  })();

  /* ================= 하루 일과표 ================= */
  (function day() {
    const box = $("#day-sim"); if (!box) { return; }
    const svg = $("svg", box), sl = $("#day-slider"), cap = $("#day-cap");
    const X = (m) => 20 + (m / 1440) * 960;
    const night = (m) => m >= 1320 || m < 420, meals = [480, 780, 1140];
    function draw() {
      const now = +sl.value; $("#day-now").textContent = "지금 " + hhmm(now); svg.innerHTML = "";
      svgEl("rect", { x: 20, y: 50, width: 960, height: 40, rx: 10, fill: "#fff", stroke: INK, "stroke-width": 3 }, svg);
      svgEl("rect", { x: X(1320), y: 50, width: X(1440) - X(1320), height: 40, fill: "#B9A2F0", opacity: .6 }, svg);
      svgEl("rect", { x: X(0), y: 50, width: X(420) - X(0), height: 40, fill: "#B9A2F0", opacity: .6 }, svg);
      for (let h = 0; h <= 24; h += 3) { const t = svgEl("text", { x: X(h * 60), y: 112, "text-anchor": "middle", style: "font-size:12px;fill:" + INK }, svg); t.textContent = h + "시"; }
      for (let h = 8; h < 22; h++) { svgEl("circle", { cx: X(h * 60), cy: 70, r: 2.5, fill: "#7DB7E8" }, svg); }
      meals.forEach((mm, i) => { svgEl("circle", { cx: X(mm), cy: 70, r: 9, fill: "#F2B34D", stroke: INK, "stroke-width": 2.5 }, svg); const t = svgEl("text", { x: X(mm), y: 40, "text-anchor": "middle", style: "font-size:12px;font-weight:700;fill:" + INK }, svg); t.textContent = ["아침 밥", "점심 밥", "저녁 밥"][i] + " " + hhmm(mm); });
      const z = svgEl("text", { x: X(180), y: 76, "text-anchor": "middle", style: "font-size:13px;font-weight:800;fill:" + INK }, svg); z.textContent = "잠 😴".replace(" 😴", "");
      const z2 = svgEl("text", { x: X(1380), y: 76, "text-anchor": "middle", style: "font-size:13px;font-weight:800;fill:" + INK }, svg); z2.textContent = "잠";
      svgEl("line", { x1: X(now), x2: X(now), y1: 26, y2: 100, stroke: PINK_D, "stroke-width": 4 }, svg);
      const lg = svgEl("text", { x: 20, y: 138, style: "font-size:12px;fill:" + INK }, svg); lg.textContent = "● 파란 점 = 매시 정각 알림 · 주황 = 밥 시간 · 보라 = 잠자는 시간(22시~7시)";
      const L = [];
      if (night(now)) { L.push("지금은 <b>잠자는 시간</b>이에요. 고양이는 구석에서 웅크리고 자고, 일정·소식 알림과 졸라대기를 쉬어요."); }
      else { L.push("깨어 있어요. 돌아다니고 놀아요."); }
      const nextMeal = meals.find((mm) => mm > now);
      if (!night(now)) { if (nextMeal) { L.push(`다음 밥 시간은 <b>${hhmm(nextMeal)}</b> (${nextMeal - now}분 뒤). 안 주면 3분마다 졸라요.`); } else { L.push("오늘 밥 시간은 모두 지났어요. 22시가 되면 자러 가요."); } }
      if (!night(now) && meals.some((mm) => now >= mm && now < mm + 30)) { L.push("<b>방금 밥 시간이 지났어요</b> — 아직 밥을 안 줬으면 지금쯤 \"밥 줘라옹~\" 하고 졸라요."); }
      if (now >= 420 && now < 424) { L.push("방금 깼어요. \"후아암~ 좋은 아침이다냥\""); }
      cap.innerHTML = L.join("<br>");
    }
    sl.addEventListener("input", draw); draw();
  })();

  /* ================= 경보 창 예시 ================= */
  (function alertDemo() {
    const box = $("#alert-demo"); if (!box) { return; }
    const D = {
      ransom: { title: "쥐 발견! 미끼 파일이 건드려졌어요 (시험)", body: "랜섬웨어가 문서를 암호화하기 시작했을 수 있어요.\n· 미끼 파일의 내용이 바뀌었어요 (사람이 건드릴 일이 없는 숨김 미끼 문서예요)\n\n디스크에 가장 많이 쓰고 있는 프로그램(의심 후보, 확정 아님):\n· example.exe (35.2 MB/초)", steps: ["인터넷을 바로 끊어요", "의심 프로그램을 끝내요", "몸값은 내지 마요", "백업 장치는 연결하지 마요"], btns: [["위치 열기", ""], ["종료…", ""], ["확인했어요", "p"], ["무시", ""]], cap: "<b>위험</b> 단계: 무슨 일이 있었는지 → <b>지금 해야 할 일 4단계</b> → 의심 프로그램 줄(위치 열기·종료…) → 확인/무시. 종료…는 확인 창을 한 번 더 거쳐요." },
      program: { title: "수상한 프로그램이 실행 중이에요 (예시)", body: "sample.exe\nC:\\Users\\나\\AppData\\Roaming\\sample\\sample.exe\n· AppData\\Roaming 폴더에서 실행 중\n· 디지털 서명이 없어요", steps: ["어떤 프로그램인지 확인해요", "내가 아는 프로그램이면 허용해요", "모르는 프로그램이면 검사해요"], btns: [["위치 열기", ""], ["종료…", ""], ["허용 목록에 추가", ""], ["확인했어요", "p"], ["무시", ""]], cap: "<b>의심</b> 단계: 이유가 점수의 근거로 나열돼요. 내가 아는 프로그램이면 <b>허용 목록에 추가</b>(다음부터 안 알려요)." },
      privacy: { title: "처음 보는 프로그램이 카메라를 쓰고 있어요 (예시)", body: "‘sample’ 프로그램이 지금 카메라를 쓰고 있어요.\n처음 보는 프로그램이에요. 내가 시작한 게 맞으면 ‘허용 목록에 추가’를 누르세요.\n모르는 프로그램이면 스파이웨어일 수 있으니 의심해 보세요.", steps: ["지금 내가 쓰는 앱인지 봐요", "내가 쓰는 앱이면 허용해요", "모르는 앱이면 끝내고 검사해요"], btns: [["종료…", ""], ["허용 목록에 추가", ""], ["확인했어요", "p"], ["무시", ""]], cap: "카메라·마이크: 같은 앱은 한 번만 알려요. 화상회의 앱이면 허용하세요." },
      download: { title: "서명 없는 프로그램을 내려받았어요 (예시)", body: "setup_sample.exe\nC:\\Users\\나\\Downloads\\setup_sample.exe\n· 인터넷에서 받은 파일이에요 (출처: example.com)\n· 디지털 서명이 없어요\n· 인터넷에서 받은 서명 없는 프로그램", steps: ["실행하지 말고 출처를 떠올려요", "백신으로 검사해요", "필요 없으면 직접 지워요"], btns: [["위치 열기", ""], ["허용 목록에 추가", ""], ["확인했어요", "p"], ["무시", ""]], cap: "내려받은 파일: 고양이는 파일을 <b>지우지 않아요</b>. 필요 없으면 내가 직접 지워요." },
    };
    function show(k) {
      const d = D[k]; $$("[data-k]", box).forEach((b) => b.classList.toggle("on", b.dataset.k === k));
      $("#ad-title").textContent = d.title; $("#ad-body").textContent = d.body;
      $("#ad-steps").innerHTML = d.steps.map((s, i) => `<div class="f"><b>${i + 1}</b><small>${s}</small></div>`).join("");
      $("#ad-btns").innerHTML = d.btns.map(([t, c]) => `<span class="mbtn ${c}">${t}</span>`).join("");
      $("#ad-cap").innerHTML = d.cap;
    }
    $$("[data-k]", box).forEach((b) => b.addEventListener("click", () => show(b.dataset.k))); show("ransom");
  })();

  /* ================= 알림 시뮬레이터 ================= */
  (function when() {
    const box = $("#when-sim"); if (!box) { return; }
    const svg = $("#ws-svg"), out = $("#ws-out");
    const ids = ["ws-kind", "ws-times", "ws-on", "ws-off", "ws-night"];
    function draw() {
      const kind = $("#ws-kind").value, on = +$("#ws-on").value, off = +$("#ws-off").value, night = $("#ws-night").checked;
      $("#ws-on-v").textContent = hhmm(on); $("#ws-off-v").textContent = hhmm(off);
      let times = $("#ws-times").value.split(",").map(toMin).filter((x) => x != null).sort((a, b) => a - b); times = [...new Set(times)];
      const maxAge = kind === "hourly" ? 180 : 0;
      const isOn = (m) => (on <= off ? m >= on && m < off : m >= on || m < off), isNight = (m) => night && (m >= 1320 || m < 420);
      // 분 단위로 하루를 돌며 scheduler.due_slot 규칙대로 실행
      let last = -1; const ran = {}, rows = [];
      for (let m = 0; m < 1440; m++) {
        if (!isOn(m) || isNight(m)) { continue; }
        let best = null; times.forEach((t) => { if (t <= m) { best = t; } });
        if (best == null) { continue; }
        if (maxAge && m - best > maxAge) { continue; }
        if (best > last) { ran[best] = m; last = best; }
      }
      const X = (m) => 20 + (m / 1440) * 660; svg.innerHTML = "";
      svgEl("rect", { x: 20, y: 30, width: 660, height: 16, rx: 6, fill: "#fff", stroke: INK, "stroke-width": 2.5 }, svg);
      const seg = (a, b, fill, y, h, op) => svgEl("rect", { x: X(a), y, width: Math.max(1, X(b) - X(a)), height: h, fill, opacity: op }, svg);
      if (on <= off) { seg(on, off, "#6FCF97", 30, 16, .8); } else { seg(on, 1440, "#6FCF97", 30, 16, .8); seg(0, off, "#6FCF97", 30, 16, .8); }
      if (night) { seg(1320, 1440, "#B9A2F0", 52, 8, .8); seg(0, 420, "#B9A2F0", 52, 8, .8); }
      const lb = svgEl("text", { x: 22, y: 22, style: "font-size:11px;fill:" + INK }, svg); lb.textContent = "초록 = 컴퓨터 켜짐 · 보라 = 잠자는 시간";
      for (let h = 0; h <= 24; h += 3) { const t = svgEl("text", { x: X(h * 60), y: 134, "text-anchor": "middle", style: "font-size:11px;fill:" + INK }, svg); t.textContent = h + "시"; }
      let nOk = 0, nLate = 0, nLost = 0;
      times.forEach((t) => {
        const r = ran[t]; let col = "#fff", st = "";
        if (r != null) { if (r - t <= 1) { col = PINK; nOk++; rows.push(`<span class="ok">${hhmm(t)}</span> 정시에 알림이 와요`); } else { col = "#F2B34D"; nLate++; rows.push(`<span class="ok">${hhmm(t)}</span> → <b>${hhmm(r)}</b> 에 따라잡아요 (${r - t}분 늦게)`); } }
        else { col = "#EEE"; nLost++; rows.push(`<span class="bad">${hhmm(t)}</span> 알림이 <b>오지 않아요</b> (${maxAge ? "그 시각에 컴퓨터가 꺼져 있었거나 잠자는 시간이었고, 켜진 뒤에는 3시간이 넘게 지나 따라잡지 않아요" : "그 시각에 컴퓨터가 꺼져 있었고, 켜진 뒤에는 더 최근 알림 하나만 따라잡아서 건너뛰어요 (또는 오늘 켜지지 않았어요)"})`); }
        svgEl("circle", { cx: X(t), cy: 38, r: 7, fill: col, stroke: INK, "stroke-width": 2.5 }, svg);
        if (r != null && r - t > 1) { svgEl("path", { d: `M${X(t)} 46 Q${(X(t) + X(r)) / 2} 80 ${X(r)} 46`, fill: "none", stroke: "#F2B34D", "stroke-width": 2.5, "stroke-dasharray": "4 3" }, svg); svgEl("circle", { cx: X(r), cy: 38, r: 4, fill: "#F2B34D" }, svg); }
      });
      const L = []; L.push(`정시 ${nOk}개 · 따라잡음 ${nLate}개 · 안 옴 ${nLost}개`);
      if (kind === "daily" && times.length > 1) { L.push("※ 하루 한 번류는 놓친 여러 개 중 <b>가장 최근 하나만</b> 따라잡아요."); }
      out.innerHTML = L.join("<br>") + "<br><br>" + (rows.length > 14 ? rows.filter((r) => !r.includes("정시에")).slice(0, 12).join("<br>") + "<br>… (정시 알림은 생략)" : rows.join("<br>"));
    }
    $("#ws-kind").addEventListener("input", () => { $("#ws-times").value = $("#ws-kind").value === "hourly" ? Array.from({ length: 24 }, (_, i) => hhmm(i * 60)).join(",") : "09:00"; });
    ids.forEach((i) => $("#" + i).addEventListener("input", draw)); draw();
  })();

  /* ================= FAQ 검색 ================= */
  (function faq() {
    const q = $("#faq-search"); if (!q) { return; }
    q.addEventListener("input", () => { const s = q.value.trim().toLowerCase(); $$("#faq-list details").forEach((d) => { const hit = !s || d.textContent.toLowerCase().includes(s); d.style.display = hit ? "" : "none"; if (s && hit) { d.open = true; } else if (!s) { d.open = false; } }); });
  })();
});
