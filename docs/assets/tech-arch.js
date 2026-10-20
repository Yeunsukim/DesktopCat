/* 기술 문서: 구성도 · 모듈 표 · import 그래프 · 지킴이 상태 · 프레임 루프 */
(window.PageInits = window.PageInits || []).push(function () {
  const { $, $$, NS } = window.DocUtil;
  const D = window.DOCDATA || {};
  const svgEl = (tag, attrs = {}, parent) => { const e = document.createElementNS(NS, tag); for (const k in attrs) { e.setAttribute(k, attrs[k]); } if (parent) { parent.appendChild(e); } return e; };
  const wrapText = (parent, lines, x, y, cls, lh = 16) => { lines.forEach((t, i) => { const e = svgEl("text", { x, y: y + i * lh, "text-anchor": "middle", class: cls || "" }, parent); e.textContent = t; }); };

  // 자동으로 채우는 숫자
  if (D.totals) { $$(".gen-files").forEach((e) => (e.textContent = D.totals.files)); $$(".gen-lines").forEach((e) => (e.textContent = D.totals.lines.toLocaleString("ko-KR"))); }

  /* ================= 구성도 ================= */
  (function arch() {
    const box = $("#arch-diagram"); if (!box) { return; }
    const svg = $("svg", box), cap = $("#arch-caption");
    const nodes = {
      user: { x: 20, y: 250, w: 170, h: 84, t: "사용자", s: "마우스 · 키보드", info: "고양이 창을 누르거나 끌고, 메뉴·설정을 열어요. 입력이 5분 넘게 없으면 활동 기록이 멈추고, 10분 넘으면 고양이도 멈춰요(자리 비움)." },
      guard: { x: 300, y: 28, w: 250, h: 92, t: "지킴이", s: "launcher.py · DesktopCat.exe", info: "표준 라이브러리만 쓰는 아주 작은 프로세스. 본체를 띄우고(--worker) 2초마다 지켜봐요. 죽으면 3초 뒤, 멈추면(하트비트 90초 없음) 강제로 끄고 다시 살려요. 계속 죽으면 대기 시간을 늘려요(최대 5분). 사용자가 '종료'를 누르면 같이 끝나요." },
      worker: { x: 300, y: 214, w: 270, h: 170, t: "본체 (worker)", s: "cat.py · PyQt6", info: "화면 스레드가 24fps 타이머로 행동 → 그리기를 돌려요. 안에는 CatBrain(행동), PhotoRig(그리기), Scheduler(알림), SecurityGuard(경비), LauncherBubble·Balloon·NoticeWindow·SettingsDialog(화면)가 있고, 작업 스레드가 알림·감시를 해요." },
      helper: { x: 690, y: 236, w: 250, h: 92, t: "보조 프로세스", s: "nethelper.py · --net-helper", info: "요청 1건을 표준 입력(JSON 한 줄)으로 받아 처리하고 표준 출력(JSON 한 줄)으로 돌려준 뒤 끝나요. 종류: calendar·upcoming·gemini·news·mail·favicon·scan·vt. 종류마다 제한 시간이 있고(45~240초) 넘으면 본체가 끝내요." },
      net: { x: 720, y: 30, w: 250, h: 100, t: "인터넷", s: "Google Calendar · Gemini · Gmail", s2: "Open-Meteo · 뉴스 · Yahoo · VirusTotal", info: "모두 https(메일은 imaps 993). 캘린더 비공개 주소, Gemini API, Gmail IMAP, Open-Meteo 날씨, Google News RSS, Yahoo 시세, 위치 조회(ipwho.is 등), 웹사이트 아이콘, VirusTotal." },
      ps: { x: 760, y: 432, w: 210, h: 84, t: "PowerShell", s: "서명 확인 · 작업 목록", info: "경비 점검 때만 보조 프로세스가 띄워요. Get-AuthenticodeSignature(서명)와 Get-ScheduledTask·Win32_Service(작업·서비스 목록). 시작 비용이 커서(CPU 약 3초) 한 번에 모아서 부르고, 결과는 보관해요." },
      win: { x: 300, y: 456, w: 270, h: 92, t: "윈도우", s: "창·레지스트리·파일 알림·DPAPI", info: "열린 창 목록(EnumWindows+DWM), 바탕화면 아이콘(explorer 메모리), 폴더 변경 알림(ReadDirectoryChangesW), 카메라·마이크 사용 기록(레지스트리), 자동 시작 항목, 암호화(DPAPI), 마지막 입력 시각." },
      data: { x: 20, y: 440, w: 220, h: 100, t: "데이터 폴더", s: "JSON · 로그 · 비밀", info: "소스로 돌릴 때는 소스 폴더, 설치본은 %LOCALAPPDATA%\\DesktopCat. launcher_config.json, secrets.json, pet_state.json, activity/, security/ 등. 모두 임시 파일에 쓴 뒤 바꿔치기(os.replace)로 저장해 쓰다 꺼져도 안 깨져요." },
    };
    const edges = {
      spawn: { d: "M350 120 L350 214", label: "Popen --worker", from: "guard", to: "worker", dir: 1, cap: "<b>지킴이 → 본체</b> 지킴이가 <code>DesktopCat.exe --worker</code>(소스에서는 <code>launcher.py --worker</code>)를 창 없이 실행해요. 표준 입출력은 모두 버려요." },
      beat: { d: "M505 214 L505 120", label: "하트비트 5초", from: "worker", to: "guard", dir: 1, cap: "<b>본체 → 지킴이</b> 본체가 5초마다 공유 메모리(<code>Local\\DesktopCatHeartbeat</code>, 16바이트)에 현재 시각(double)을 적어요. 지킴이가 읽고 90초 넘게 그대로면 멈춘 것으로 보고 강제로 끝내요." },
      user: { d: "M190 284 L300 296", label: "클릭·끌기·메뉴", from: "user", to: "worker", dir: 1, cap: "<b>사용자 → 본체</b> 고양이 창의 마우스 이벤트(눌러서 런처/쓰다듬기, 끌어서 집어 올리기, 우클릭 메뉴), 트레이 아이콘 메뉴." },
      req: { d: "M570 278 L690 270", label: "요청 JSON (stdin)", from: "worker", to: "helper", dir: 1, cap: "<b>본체 → 보조</b> 작업 스레드가 <code>nethelper.call(kind, **params)</code> 로 보조 프로세스를 띄우고 <code>{\"kind\":\"mail\",\"user\":…}</code> 한 줄을 표준 입력으로 보내요. 키·비밀번호도 이 길로만 가요." },
      resp: { d: "M690 300 L570 308", label: "결과 JSON (stdout)", from: "helper", to: "worker", dir: 1, cap: "<b>보조 → 본체</b> <code>{\"ok\":true,\"result\":…}</code> 또는 <code>{\"ok\":false,\"error\":\"한글 메시지\",\"retry\":true}</code> 한 줄. 한글도 \\uXXXX 로 이스케이프된 순수 ASCII라 cp949/UTF-8 차이로 깨지지 않아요." },
      net: { d: "M800 236 Q805 190 840 130", label: "https · imaps", from: "helper", to: "net", dir: 1, cap: "<b>보조 → 인터넷</b> 캘린더·Gemini·메일·날씨·뉴스·시세·VirusTotal 호출은 모두 여기서 해요. 본체는 인터넷에 직접 접속하지 않아요." },
      ps: { d: "M820 328 Q830 380 860 432", label: "서명·작업 목록", from: "helper", to: "ps", dir: 1, cap: "<b>보조 → PowerShell</b> 경비 점검(scan)일 때 PowerShell 스크립트를 실행하고 결과 JSON 파일을 읽어요." },
      win: { d: "M435 384 L435 456", label: "win32 · 레지스트리", from: "worker", to: "win", dir: 1, cap: "<b>본체 ↔ 윈도우</b> 창 위치(발판), 바탕화면 아이콘 이동, 폴더 감시, 카메라·마이크 사용 기록, 마지막 입력 시각, 전체 화면 앱 판단, DPAPI 암호화." },
      data: { d: "M310 372 Q262 410 226 444", label: "읽기·저장", from: "worker", to: "data", dir: 1, cap: "<b>본체 ↔ 데이터 폴더</b> 설정·비밀·키우기 상태·활동 기록·경비 기록. 저장은 임시 파일 → <code>os.replace</code>." },
    };
    const order = ["spawn", "beat", "user", "req", "net", "resp", "ps", "win", "data"];
    Object.entries(edges).forEach(([k, e]) => { e.el = svgEl("path", { d: e.d, class: "edge", "data-k": k }, svg); });
    // 선 이름표
    Object.entries(edges).forEach(([k, e]) => {
      const L = e.el.getTotalLength(); const p = e.el.getPointAtLength(L / 2);
      const t = svgEl("text", { x: p.x, y: p.y - 7, "text-anchor": "middle", class: "tl-text", style: "font-size:11.5px;font-weight:700;fill:#5A3A47;paint-order:stroke;stroke:#fff;stroke-width:4px" }, svg);
      t.textContent = e.label;
    });
    const gnodes = {};
    Object.entries(nodes).forEach(([k, n]) => {
      const g = svgEl("g", { class: "svg-node", "data-k": k, tabindex: 0 }, svg); gnodes[k] = g;
      svgEl("rect", { x: n.x, y: n.y, width: n.w, height: n.h, rx: 18 }, g);
      const cx = n.x + n.w / 2;
      const t = svgEl("text", { x: cx, y: n.y + 32, "text-anchor": "middle", style: "font-size:19px" }, g); t.textContent = n.t;
      const s = svgEl("text", { x: cx, y: n.y + 54, "text-anchor": "middle", class: "s" }, g); s.textContent = n.s;
      if (n.s2) { const s2 = svgEl("text", { x: cx, y: n.y + 72, "text-anchor": "middle", class: "s" }, g); s2.textContent = n.s2; }
      g.addEventListener("click", () => select(k));
      g.addEventListener("keydown", (ev) => { if (ev.key === "Enter") { select(k); } });
    });
    // 본체 안쪽 부품 표시
    ["CatBrain", "PhotoRig", "Scheduler", "SecurityGuard"].forEach((t, i) => {
      const x = 316 + (i % 2) * 124, y = 308 + Math.floor(i / 2) * 32;
      svgEl("rect", { x, y, width: 116, height: 26, rx: 9, fill: "#FFE6EE", stroke: "#5A3A47", "stroke-width": 2, "pointer-events": "none" }, svg);
      const e = svgEl("text", { x: x + 58, y: y + 18, "text-anchor": "middle", style: "font-size:12.5px;font-weight:700;fill:#5A3A47;pointer-events:none;font-family:inherit" }, svg); e.textContent = t;
    });
    const packet = svgEl("circle", { r: 9, class: "packet", cx: -50, cy: -50 }, svg);
    let cur = null, running = false, rafId = 0, idx = 0;
    function select(k) {
      cur = k; Object.entries(gnodes).forEach(([n, g]) => g.classList.toggle("on", n === k));
      Object.entries(edges).forEach(([ek, e]) => e.el.classList.toggle("dim", !(e.from === k || e.to === k)));
      const n = nodes[k]; cap.innerHTML = `<b>${n.t}</b> — ${n.info}`;
    }
    function resetSel() { cur = null; Object.values(gnodes).forEach((g) => g.classList.remove("on", "hot")); Object.values(edges).forEach((e) => e.el.classList.remove("dim")); cap.textContent = "상자를 눌러 보세요. 선(점선)은 데이터·신호가 흐르는 길이에요."; }
    function runOne(k, done) {
      const e = edges[k]; const L = e.el.getTotalLength(); const t0 = performance.now(); const dur = 1500;
      Object.values(edges).forEach((x) => x.el.classList.add("dim")); e.el.classList.remove("dim");
      Object.values(gnodes).forEach((g) => g.classList.remove("hot")); gnodes[e.from].classList.add("hot");
      cap.innerHTML = e.cap;
      (function step(now) {
        if (!running) { return; }
        const p = Math.min(1, (now - t0) / dur); const pt = e.el.getPointAtLength(L * (e.dir > 0 ? p : 1 - p));
        packet.setAttribute("cx", pt.x); packet.setAttribute("cy", pt.y);
        if (p < 1) { rafId = requestAnimationFrame(step); } else { gnodes[e.from].classList.remove("hot"); gnodes[e.to].classList.add("hot"); setTimeout(done, 900); }
      })(t0);
    }
    function loop() { if (!running) { return; } runOne(order[idx % order.length], () => { idx++; loop(); }); }
    $("#arch-play").onclick = function () {
      running = !running; this.textContent = running ? "❚❚ 멈춤" : "▶ 데이터 흘려보기"; this.classList.toggle("on", running);
      if (running) { idx = 0; loop(); } else { cancelAnimationFrame(rafId); }
    };
    $("#arch-reset").onclick = () => { running = false; cancelAnimationFrame(rafId); const b = $("#arch-play"); b.textContent = "▶ 데이터 흘려보기"; b.classList.remove("on"); packet.setAttribute("cx", -50); resetSel(); };
    select("worker");
  })();

  /* ================= 모듈 표 ================= */
  (function modules() {
    const tb = $("#mod-table tbody"); if (!tb || !D.modules) { return; }
    const gname = Object.fromEntries(D.groups.map((g) => [g.id, g.name]));
    const filt = $("#mod-filters"); let cur = "all";
    const mk = (id, name) => { const b = document.createElement("button"); b.className = "btn" + (id === "all" ? " on" : ""); b.textContent = name; b.onclick = () => { cur = id; $$("button", filt).forEach((x) => x.classList.toggle("on", x === b)); draw(); }; filt.appendChild(b); };
    mk("all", "전체"); D.groups.forEach((g) => mk(g.id, g.name));
    const inp = document.createElement("input"); inp.className = "search"; inp.placeholder = "파일 이름·설명 검색"; inp.style.cssText = "max-width:240px;margin:0"; inp.setAttribute("data-modsearch", ""); filt.appendChild(inp);
    inp.addEventListener("input", draw);
    function draw() {
      const q = inp.value.trim().toLowerCase();
      tb.innerHTML = "";
      D.modules.filter((m) => (cur === "all" || m.group === cur) && (!q || (m.file + m.role).toLowerCase().includes(q))).forEach((m) => {
        const tr = document.createElement("tr");
        tr.innerHTML = `<td><code>${m.file}</code></td><td style="text-align:right">${m.lines.toLocaleString("ko-KR")}</td><td><span class="tag pink">${gname[m.group] || m.group}</span></td><td>${m.role}</td>`;
        tb.appendChild(tr);
      });
    }
    draw();
  })();

  /* ================= import 그래프 ================= */
  (function importGraph() {
    const box = $("#import-graph"); if (!box || !D.modules) { return; }
    const svg = $("svg", box), info = $("#ig-info");
    const colors = { run: "#F67499", brain: "#7DB7E8", draw: "#B9A2F0", notify: "#F2B34D", guard: "#6FCF97", ui: "#F59BC0", store: "#9AA5B1", pack: "#C9B39A" };
    const cols = 4, gw = 238, gh = 300;
    const pos = {}; const grpPos = {};
    D.groups.forEach((g, gi) => {
      const gx = 12 + (gi % cols) * (gw + 6), gy = 12 + Math.floor(gi / cols) * (gh + 22);
      grpPos[g.id] = { x: gx, y: gy };
      svgEl("rect", { x: gx, y: gy, width: gw, height: gh, rx: 16, fill: colors[g.id], opacity: .22, stroke: "#5A3A47", "stroke-width": 2 }, svg);
      const t = svgEl("text", { x: gx + 14, y: gy + 22, style: "font-weight:800;font-size:14px;fill:#2E1D26;font-family:inherit" }, svg); t.textContent = g.name;
      D.modules.filter((m) => m.group === g.id).forEach((m, i) => { pos[m.file] = { x: gx + 10, y: gy + 34 + i * 23, w: gw - 20, h: 20, g: g.id }; });
    });
    const edgeEls = [];
    D.edges.forEach((e) => {
      const a = pos[e.from], b = pos[e.to]; if (!a || !b) { return; }
      const ax = a.x + a.w / 2, bx = b.x + b.w / 2; const sameCol = Math.abs(a.x - b.x) < 5;
      const x1 = sameCol ? a.x + a.w : (bx > ax ? a.x + a.w : a.x), x2 = sameCol ? b.x + b.w : (bx > ax ? b.x : b.x + b.w);
      const y1 = a.y + a.h / 2, y2 = b.y + b.h / 2; const dx = sameCol ? 34 : Math.max(30, Math.abs(x2 - x1) / 2) * (bx > ax ? 1 : -1);
      const d = `M${x1} ${y1} C${x1 + dx} ${y1} ${x2 - (sameCol ? -34 : dx)} ${y2} ${x2} ${y2}`;
      const p = svgEl("path", { d, fill: "none", stroke: "#5A3A47", "stroke-width": 1.4, opacity: .13, "stroke-dasharray": e.lazy ? "5 4" : "none" }, svg);
      edgeEls.push({ e, p });
    });
    const nodeEls = {};
    D.modules.forEach((m) => {
      const q = pos[m.file]; if (!q) { return; }
      const g = svgEl("g", { class: "svg-node", style: "cursor:pointer" }, svg); nodeEls[m.file] = g;
      svgEl("rect", { x: q.x, y: q.y, width: q.w, height: q.h, rx: 8 }, g);
      const t = svgEl("text", { x: q.x + 8, y: q.y + 14.5, style: "font-size:12px;font-weight:700;font-family:var(--font-mono)" }, g); t.textContent = m.file.replace("installer/", "inst/");
      g.addEventListener("click", () => sel(m.file)); g.addEventListener("mouseenter", () => sel(m.file));
    });
    function sel(f) {
      const outs = new Set(), ins = new Set();
      edgeEls.forEach(({ e, p }) => {
        const hit = e.from === f || e.to === f; p.setAttribute("opacity", hit ? .95 : .06); p.setAttribute("stroke", hit ? (e.from === f ? "#2F6FD0" : "#E5557E") : "#5A3A47"); p.setAttribute("stroke-width", hit ? 2.4 : 1.2);
        if (e.from === f) { outs.add(e.to); } if (e.to === f) { ins.add(e.from); }
      });
      Object.entries(nodeEls).forEach(([k, g]) => { const r = $("rect", g); r.style.fill = k === f ? "#F67499" : outs.has(k) ? "#DCE8FF" : ins.has(k) ? "#FFD3E0" : ""; $("text", g).style.fill = k === f ? "#fff" : ""; });
      info.innerHTML = `<code>${f}</code> → 부르는 모듈 <b>${outs.size}</b>개 (파랑) · 이 모듈을 부르는 곳 <b>${ins.size}</b>개 (분홍)`;
    }
    sel("cat.py");
  })();

  /* ================= 지킴이 상태 ================= */
  (function guardLoop() {
    const box = $("#guard-diagram"); if (!box) { return; }
    const svg = $("svg", box), log = $("#guard-log");
    const S = {
      spawn: { x: 30, y: 60, w: 190, h: 70, t: "① 본체 실행", s: "Popen --worker" },
      watch: { x: 300, y: 60, w: 210, h: 70, t: "② 2초마다 감시", s: "poll() · 하트비트" },
      quit: { x: 620, y: 10, w: 190, h: 64, t: "종료 코드 0", s: "사용자가 끔 → 지킴이도 끝" },
      restart: { x: 620, y: 92, w: 190, h: 64, t: "종료 코드 3", s: "스스로 재시작 요청 → 바로" },
      died: { x: 620, y: 174, w: 190, h: 64, t: "그 밖의 종료", s: "죽음 → 잠시 기다림" },
      hang: { x: 300, y: 190, w: 210, h: 64, t: "신호 90초 없음", s: "강제 종료 → 'hang'" },
      wait: { x: 30, y: 190, w: 190, h: 64, t: "③ 기다림", s: "3초 · 빨리 죽으면 늘림" },
    };
    const arrows = [
      ["spawn", "watch", "M220 95 L300 95"], ["watch", "quit", "M510 80 L620 44"], ["watch", "restart", "M510 100 L620 124"], ["watch", "died", "M510 118 Q570 190 620 206"],
      ["watch", "hang", "M405 130 L405 190"], ["hang", "wait", "M300 222 L220 222"], ["died", "wait", "M620 232 Q400 300 200 254"], ["wait", "spawn", "M125 190 L125 130"], ["restart", "spawn", "M620 140 Q400 -10 125 60"],
    ];
    const els = {}, arEls = [];
    arrows.forEach(([a, b, d]) => { const p = svgEl("path", { d, class: "edge solid", "marker-end": "url(#gar)", style: "stroke-width:2.5" }, svg); arEls.push({ a, b, p }); });
    const defs = svgEl("defs", {}, svg); defs.innerHTML = `<marker id="gar" markerWidth="9" markerHeight="9" refX="7" refY="4.5" orient="auto"><path d="M0 0 L9 4.5 L0 9z" fill="#5A3A47"/></marker>`;
    Object.entries(S).forEach(([k, n]) => {
      const g = svgEl("g", { class: "svg-node" }, svg); els[k] = g; svgEl("rect", { x: n.x, y: n.y, width: n.w, height: n.h, rx: 16 }, g);
      const t = svgEl("text", { x: n.x + n.w / 2, y: n.y + 28, "text-anchor": "middle", style: "font-size:16px" }, g); t.textContent = n.t;
      const s = svgEl("text", { x: n.x + n.w / 2, y: n.y + 49, "text-anchor": "middle", class: "s" }, g); s.textContent = n.s;
    });
    let fast = 0;
    const say = (h) => { log.innerHTML = h + "<br>" + log.innerHTML; };
    const hot = (ks) => { Object.entries(els).forEach(([k, g]) => g.classList.toggle("hot", ks.includes(k))); arEls.forEach(({ a, b, p }) => p.style.opacity = ks.includes(a) && ks.includes(b) ? 1 : .35); };
    const seq = async (steps) => { for (const [ks, msg, ms] of steps) { hot(ks); say(msg); await new Promise((r) => setTimeout(r, ms || 1100)); } };
    $$("[data-guard]", box).forEach((b) => b.addEventListener("click", async () => {
      const k = b.dataset.guard;
      if (k === "quit") { fast = 0; await seq([[["spawn"], "<span class='dim'>본체를 실행해요 (Popen)</span>"], [["watch"], "2초마다 <code>proc.poll()</code> 과 하트비트를 봐요"], [["watch", "quit"], "사용자가 트레이 메뉴 <b>종료</b> → 종료 코드 0 → <span class='ok'>지킴이도 끝</span>", 1500]]); }
      if (k === "restart") { fast = 0; await seq([[["spawn"], "본체 실행"], [["watch"], "감시 중…"], [["watch", "restart"], "자원이 새거나 프레임 오류가 계속돼 본체가 <code>exit(3)</code> → <span class='ok'>대기 없이 바로 다시 시작</span>"], [["restart", "spawn"], "fast_fails = 0 으로 되돌리고 ① 로"]]); }
      if (k === "die") { fast++; const wait = fast <= 1 ? 3 : Math.min(300, 3 * 2 ** Math.min(fast, 7)); await seq([[["spawn"], "본체 실행"], [["watch", "died"], "30초 안에 죽었어요 (연속 " + fast + "번째)"], [["died", "wait"], "대기 <b>" + wait + "초</b> = " + (fast <= 1 ? "3초" : "3 × 2<sup>" + Math.min(fast, 7) + "</sup> (최대 300초)")], [["wait", "spawn"], "다시 ① 로 — 계속 죽어도 포기하지 않아요 (컴퓨터를 괴롭히지 않게 간격만 늘림)"]]); }
      if (k === "hang") { fast = 0; await seq([[["spawn"], "본체 실행"], [["watch"], "하트비트가 멈췄어요… (시작 직후 90초는 봐 줘요)"], [["watch", "hang"], "신호가 90초 넘게 없음 → <code>proc.kill()</code>"], [["hang", "wait"], "'hang' 으로 보고 대기 후 재시작"]]); }
    }));
  })();

  /* ================= 프레임 루프 ================= */
  (function frameLoop() {
    const box = $("#frame-diagram"); if (!box) { return; }
    const svg = $("svg", box), cap = $("#frame-caption");
    const lanes = [
      { name: "매 프레임 (42ms)", p: 0.042, items: "brain.update(행동) → overlay.tick(그리기 요청) → launcher.tick → balloon.tick. 멈춘 동안(자리 비움·전체 화면)에는 건너뛰어요.", live: false },
      { name: "30프레임 (≈1.3초)", p: 1.26, items: "QUIT 이벤트 확인(--quit 신호). 멈춘 동안에는 매 틱마다 확인해요.", live: true },
      { name: "50프레임 (≈2.1초)", p: 2.1, items: "모니터 구성 확인 — 연결·해제·해상도가 바뀌면 World.set_areas + brain.relocate.", live: false },
      { name: "1초 · 전원 상태", p: 1, items: "_power_state: 입력이 AWAY_SECONDS(600초) 넘게 없으면 'away', 전체 화면 앱이 덮으면 'full' → set_paused. 멈춘 동안에도 계속 돌아야 돌아온 걸 알아요.", live: true },
      { name: "1초 · 맨 앞으로", p: 1, items: "keep_cat_on_top: 앞 창이 바뀌었고 시작 메뉴 같은 윈도우 화면이 아니면 고양이를 다시 최상위로.", live: false },
      { name: "2초 · 루틴", p: 2, items: "routine.tick: 잠자는 시간·밥 시간·놀아주기 요구 판단 → handle_routine.", live: false },
      { name: "5초 · 신호/기록", p: 5, items: "하트비트(공유 메모리에 시각) · activity.tick(맨 앞 창 표본, 설정에서 켠 경우만).", live: true },
      { name: "20초 · 알림 점검", p: 20, items: "scheduler.tick: 오늘 지난 알림 시각 중 안 돈 것이 있나. 멈춘 동안에도 제 시각에 일을 시작하고, 결과 보여 주기만 돌아온 뒤로 미뤄요(deliver/held).", live: true },
      { name: "60초 · 자원 점검", p: 60, items: "process_usage: 메모리 400MB·핸들 5000·GDI 7000·USER 7000 초과면 ask_restart. 트레이 아이콘이 사라졌으면 다시 show.", live: true },
    ];

    const W = 1000, LX = 190, RX = 975, TOP = 46, LH = 50, T = 10; // 10초 창
    lanes.forEach((l, i) => {
      const y = TOP + i * LH; svgEl("rect", { x: LX, y, width: RX - LX, height: LH - 8, rx: 10, fill: "#FFF7FA", stroke: "#F6C5D5", "stroke-width": 2 }, svg);
      const t = svgEl("text", { x: LX - 12, y: y + 27, "text-anchor": "end", style: "font-weight:800;font-size:14px;fill:#2E1D26;font-family:inherit" }, svg); t.textContent = l.name; l.y = y; l.ticks = [];
      if (l.p >= 0.5) { for (let s = 0; s <= T; s += l.p) { const x = LX + (s / T) * (RX - LX); l.ticks.push(svgEl("circle", { cx: x + 2, cy: y + 21, r: 8, fill: "#fff", stroke: "#5A3A47", "stroke-width": 2.5 }, svg)); } }
      else { for (let s = 0; s < T; s += l.p) { const x = LX + (s / T) * (RX - LX); l.ticks.push(svgEl("rect", { x: x + 1, y: y + 12, width: 3, height: 18, rx: 1.5, fill: "#F2B8CB" }, svg)); } }
    });
    for (let s = 0; s <= T; s += 2) { const x = LX + (s / T) * (RX - LX); const t = svgEl("text", { x: x + 2, y: 30, "text-anchor": "middle", class: "tl-text" }, svg); t.textContent = s + "초"; svgEl("line", { x1: x + 2, x2: x + 2, y1: 36, y2: TOP + lanes.length * LH - 6, class: "tl-grid" }, svg); }
    const head = svgEl("rect", { x: LX, y: 38, width: 4, height: lanes.length * LH, rx: 2, fill: "#E5557E" }, svg);
    let paused = false, t0 = performance.now(), running = true, last = 0;
    const btnAway = $("#frame-away"), btnRun = $("#frame-run");
    btnAway.onclick = () => { paused = !paused; btnAway.classList.toggle("on", paused); btnAway.textContent = paused ? "자리 비움: 켜짐" : "자리 비움 흉내"; draw(); };
    btnRun.onclick = () => { running = !running; btnRun.textContent = running ? "❚❚ 멈춤" : "▶ 재생"; if (running) { t0 = performance.now() - last * 1000; } };
    function draw() { lanes.forEach((l, i) => { const off = paused && !l.live; const y = l.y; svg.children[i * 0]; l.ticks.forEach((tk) => tk.style.opacity = off ? 0.15 : 1); }); cap.innerHTML = paused ? "<b>자리를 비웠거나 전체 화면 앱이 떠 있는 동안</b>에도 <b>하트비트·활동 표본·알림 점검·자원 점검</b>은 계속 돌아요. 행동·그리기·루틴·런처·풍선만 멈춰요(타이머는 500ms 간격으로 느려져요)." : "한 프레임(42ms)마다 위쪽 작업이 돌고, 느린 작업은 시간 간격으로 걸러서 돌아요. 점이 켜지는 순간이 실제 실행 시각이에요."; }
    draw();
    (function frame() {
      if (running) { last = ((performance.now() - t0) / 1000) % T; head.setAttribute("x", LX + (last / T) * (RX - LX)); lanes.forEach((l) => { l.ticks.forEach((tk, j) => { const s = j * l.p; const near = Math.abs(last - s) < 0.12 || (l.p < 0.5 && Math.abs(last - s) < 0.03); const on = near && !(paused && !l.live); if (tk.tagName === "circle") { tk.setAttribute("fill", on ? "#F67499" : "#fff"); tk.setAttribute("r", on ? 11 : 8); } else { tk.setAttribute("fill", on ? "#E5557E" : "#F2B8CB"); } }); }); }
      requestAnimationFrame(frame);
    })();
    // 줄 이름표 설명
    lanes.forEach((l) => { const r = svgEl("rect", { x: 0, y: l.y, width: LX, height: LH - 8, fill: "transparent", style: "cursor:pointer" }, svg); r.addEventListener("click", () => { cap.innerHTML = `<b>${l.name}</b> — ${l.items}`; }); });
  })();
});
