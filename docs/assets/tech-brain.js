/* 기술 문서: 데이터 폴더 · 그리기 · 두뇌 · 루틴 · 런처 · 디자인 토큰 */
(window.PageInits = window.PageInits || []).push(function () {
  const { $, $$, NS } = window.DocUtil;
  const D = window.DOCDATA || {};
  const svgEl = (tag, attrs = {}, parent) => { const e = document.createElementNS(NS, tag); for (const k in attrs) { e.setAttribute(k, attrs[k]); } if (parent) { parent.appendChild(e); } return e; };
  const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
  const smooth = (x) => { x = clamp(x, 0, 1); return x * x * (3 - 2 * x); };
  const INK = "#5A3A47", PINK = "#F67499", PINK_D = "#E5557E", PINK_L = "#EF99B1", LINE = "#F6C5D5";
  const hhmm = (m) => { m = ((Math.round(m) % 1440) + 1440) % 1440; return String(Math.floor(m / 60)).padStart(2, "0") + ":" + String(m % 60).padStart(2, "0"); };
  const toMin = (s) => { const m = /^(\d{1,2}):(\d{2})$/.exec((s || "").trim()); return m && +m[1] < 24 && +m[2] < 60 ? +m[1] * 60 + +m[2] : null; };

  // 화면에 보일 때만 애니메이션을 돌리는 도우미
  const seen = new Map();
  const io = new IntersectionObserver((es) => es.forEach((e) => seen.set(e.target, e.isIntersecting)), { rootMargin: "80px" });
  function animate(node, fn) {
    seen.set(node, false); io.observe(node);
    let last = performance.now();
    (function f(now) { const dt = Math.min(0.1, (now - last) / 1000); last = now; if (seen.get(node)) { fn(dt, now / 1000); } requestAnimationFrame(f); })(last);
  }

  /* ================= 데이터 폴더 트리 ================= */
  (function dataTree() {
    const tree = $("#data-tree"), det = $("#data-detail"); if (!tree) { return; }
    const rows = [
      { d: 0, n: "데이터 폴더", t: "dir", w: "소스 실행: 프로그램 폴더 자체 · 설치본: <code>%LOCALAPPDATA%\\DesktopCat</code> · 시험: <code>DESKTOPCAT_DATA</code>. <code>guard_common.data_dir()</code> 가 정하고 없으면 만들어요." },
      { d: 1, n: "launcher_config.json", t: "json", id: "d-launcher_config", w: "설정 전부(앱 목록·알림 시각·프롬프트·생활·경비 …). 쓰는 곳 <code>config_store.Settings.save()</code>. 읽는 곳: 거의 모든 모듈." },
      { d: 1, n: "secrets.json", t: "json", id: "d-secrets", w: "DPAPI 로 암호화한 캘린더 주소·Gemini 키·Gmail 앱 비밀번호·VirusTotal 키. 같은 윈도우 계정만 풀 수 있어요." },
      { d: 1, n: "pet_state.json", t: "json", id: "d-pet_state", w: "배고픔·기분·털색·마지막 본 시각. 30초마다와 종료 때 저장." },
      { d: 1, n: "icons_backup.json", t: "json", id: "d-icons_backup", w: "찬 아이콘의 원래 자리 장부. 정상 종료하면 지워져요. 남아 있으면 다음 시작 때 먼저 제자리로 돌려놓아요." },
      { d: 1, n: "activity/", t: "dir", w: "하루 활동 기록 폴더. 기록을 켠 경우에만 생겨요. 30일 지난 것은 자동 삭제." },
      { d: 2, n: "YYYY-MM-DD.json", t: "json", id: "d-activity", w: "{프로그램: {창 제목: 초}}. 60초마다 저장." },
      { d: 1, n: "security/", t: "dir", w: "경비 고양이의 기록·상태·PowerShell 임시 파일." },
      { d: 2, n: "events.json", t: "json", id: "d-events", w: "잡은 쥐(경보) 기록. 30일·500건." },
      { d: 2, n: "canary.json", t: "json", id: "d-canary", w: "숨김 미끼 파일 경로 → SHA-256." },
      { d: 2, n: "baseline.json", t: "json", id: "d-canary", w: "평소에 있던 자동 시작 항목(처음 점검 때 저장)." },
      { d: 2, n: "seen.json", t: "json", id: "d-canary", w: "이미 알린 수상한 프로그램(7일 동안 다시 안 알림)." },
      { d: 2, n: "sigcache.json", t: "json", id: "d-canary", w: "서명 확인 결과 보관(경로|수정시각|크기 키)." },
      { d: 2, n: "privacy_state.json", t: "json", id: "d-canary", w: "카메라·마이크: 처음 켠 시각 + 이미 본 앱." },
      { d: 2, n: "vt_state.json", t: "json", id: "d-canary", w: "VirusTotal 하루/분당 한도 + 결과 보관." },
      { d: 2, n: "_tasks_fp.json · _tasks_out.json", t: "tmp", id: "d-canary", w: "예약 작업·서비스 지문과 PowerShell 결과(6시간 재사용)." },
      { d: 2, n: "_sig_in.json · _sig_out.json · *.ps1", t: "tmp", w: "서명 확인을 PowerShell 과 주고받는 임시 파일과 스크립트." },
      { d: 1, n: "icons/", t: "dir", w: "웹사이트 파비콘 보관: <code>사이트주소.img</code>(원본 그대로), 실패하면 <code>.none</code> 표식(3일 뒤 재시도)." },
      { d: 1, n: "cat_error.log · cat_guard.log · cat_crash.log", t: "log", w: "본체 오류·재시작 요청 / 지킴이가 되살린 기록 / (선택) 파이썬 스택. 각 20만 바이트를 넘으면 비워요." },
      { d: 1, n: "meow.wav · theme_*.png", t: "tmp", w: "울음소리를 합성해 둔 파일(assets/meow.wav 가 없을 때), 스타일시트가 쓰는 체크·화살표 그림." },
      { d: 0, n: "프로그램 폴더 / assets", t: "dir", w: "앱에 포함되는 자료(읽기만 함)." },
      { d: 1, n: "sprites/sprites.json", t: "json", id: "d-sprites", w: "사진 컷 설명서. 동작 33개·컷 331장." },
      { d: 1, n: "sprites/<동작>/f0.png …", t: "img", w: "컷 그림(투명 PNG). 동작 폴더 33개." },
      { d: 1, n: "skin/*.png", t: "img", w: "예비 뼈대 고양이용 질감 조각(털·귀·머리·턱 …)." },
      { d: 1, n: "cat.ico · cat_icon.png · meow.wav", t: "img", w: "앱 아이콘(<code>tools/make_icon.py</code> 가 만듦)과 울음소리." },
    ];
    const icon = { dir: "▸", json: "{ }", tmp: "…", log: "≡", img: "▣" };
    rows.forEach((r, i) => {
      const row = document.createElement("div"); row.className = "row"; row.setAttribute("role", "treeitem"); row.tabIndex = 0;
      row.innerHTML = `<span class="ind">${"  ".repeat(r.d)}${r.d ? "└ " : ""}</span><span>${icon[r.t] || ""}</span><span>${r.n}</span>`;
      const pick = () => {
        $$(".row", tree).forEach((x) => x.classList.toggle("on", x === row));
        const link = r.id ? `<p><a href="#${r.id}" class="btn" data-open="${r.id}">모양(스키마) 보기 ↓</a></p>` : "";
        det.innerHTML = `<h4 style="margin:0 0 6px"><code>${r.n}</code></h4><p>${r.w}</p>${link}`;
        const a = $("[data-open]", det);
        if (a) { a.onclick = (ev) => { ev.preventDefault(); const f = document.getElementById(r.id); if (f) { f.open = true; f.scrollIntoView({ behavior: "smooth", block: "start" }); } }; }
      };
      row.onclick = pick; row.onkeydown = (ev) => { if (ev.key === "Enter") { pick(); } };
      tree.appendChild(row);
      if (i === 1) { pick(); }
    });
  })();

  /* ================= 컷 번호 재생 방식 ================= */
  (function drawModes() {
    const box = $("#draw-modes"); if (!box) { return; }
    const svg = $("svg", box), cap = $(".caption", box);
    const modes = {
      pingpong: { n: 6, text: "<b>왕복</b> 가만히 서 있는 자세·잠·몸 흔들기. 끝에서 튀지 않게 <code>lo..hi</code> 를 오가요: <code>m = x mod 2·span; idx = lo + (m ≤ span ? m : 2·span − m)</code>" },
      loop: { n: 8, text: "<b>순환</b> 몸단장·긁기·꾹꾹이처럼 계속 도는 동작: <code>idx = (t·fps) mod n</code>, 끝 컷에서 첫 컷으로 이어져요." },
      drift: { n: 6, text: "<b>가만히 있다 옮겨 가기</b> 앉기·식빵처럼 쉬는 자세는 대부분 가만히(1.2~4초) 있다가 이웃 1~2컷으로 초당 1.6컷 속도로 천천히 옮겨요 — 짧은 영상을 되감듯 왔다갔다 하면 머리가 기계처럼 끄덕이기 때문이에요." },
      gait: { n: 17, text: "<b>걸음 위상</b> 컷이 시간이 아니라 <b>이동한 거리</b>로 넘어가요. 그래서 출발할 때 천천히, 멈출 때 천천히 넘어가고 서 있을 땐 멈춰서 발이 땅에 미끄러지지 않아요." },
    };
    let mode = "pingpong", t = 0, drift = { pos: 0, goal: 0, until: 1.5 }, phase = 0, samples = [];
    const cellsG = svgEl("g", {}, svg), traceG = svgEl("g", {}, svg);
    function build() {
      cellsG.innerHTML = ""; traceG.innerHTML = ""; samples = [];
      const n = modes[mode].n, w = 960 / n;
      for (let i = 0; i < n; i++) {
        svgEl("rect", { x: 20 + i * w + 2, y: 14, width: w - 4, height: 44, rx: 8, fill: "#fff", stroke: INK, "stroke-width": 2.5, "data-i": i }, cellsG);
        const tx = svgEl("text", { x: 20 + i * w + w / 2, y: 43, "text-anchor": "middle", style: "font-size:14px;font-weight:700;fill:" + INK }, cellsG); tx.textContent = "f" + i;
      }
      svgEl("rect", { x: 20, y: 80, width: 960, height: 150, rx: 10, fill: "#FFF7FA", stroke: LINE, "stroke-width": 2 }, traceG);
      cap.innerHTML = modes[mode].text;
    }
    $$("[data-mode]", box).forEach((b) => b.addEventListener("click", () => { mode = b.dataset.mode; $$("[data-mode]", box).forEach((x) => x.classList.toggle("on", x === b)); t = 0; phase = 0; drift = { pos: 0, goal: 0, until: 1.5 }; build(); }));
    build();
    const line = svgEl("polyline", { fill: "none", stroke: PINK_D, "stroke-width": 3, "stroke-linejoin": "round" }, svg);
    let speedNow = 0;
    animate(box, (dt) => {
      t += dt; const n = modes[mode].n; let idx = 0;
      if (mode === "pingpong") { const span = n - 1, x = t * 1.8, m = x % (2 * span); idx = m <= span ? m : 2 * span - m; }
      else if (mode === "loop") { idx = (t * 2.4) % n; }
      else if (mode === "drift") {
        if (t >= drift.until) { if (Math.abs(drift.goal - drift.pos) < 1e-6) { const g = Math.round(drift.pos) + [-2, -1, -1, 1, 2][Math.floor(Math.random() * 5)]; drift.goal = clamp(g, 0, n - 1); if (drift.goal === drift.pos) { drift.goal = clamp(Math.round(drift.pos) + 1, 0, n - 1); } }
          const d = drift.goal - drift.pos, step = 1.6 * dt; if (Math.abs(d) <= step) { drift.pos = drift.goal; drift.until = t + 1.2 + Math.random() * 2.8; } else { drift.pos += d > 0 ? step : -step; } }
        idx = drift.pos;
      } else {
        const cyc = t % 8; const V = 70; let v = 0; // 0~3 걷기, 3~3.3 멈춤, 나머지 서 있음
        if (cyc < 3) { v = Math.min(V, V / 0.35 * cyc); } else if (cyc < 3.3) { v = Math.max(0, V - V / 0.30 * (cyc - 3)); } else { v = 0; }
        speedNow = v; phase = (phase + (v * dt) * 0.62 / 34 * 0.783) % 1; idx = phase * n;
      }
      $$("rect[data-i]", cellsG).forEach((r) => { const i = +r.dataset.i; const on = Math.floor(idx) === i; r.setAttribute("fill", on ? PINK : (Math.abs(idx - i) < 1 && mode !== "pingpong" ? "#FFE6EE" : "#fff")); });
      samples.push([t, idx]); while (samples.length && t - samples[0][0] > 8) { samples.shift(); }
      const pts = samples.map(([ts, v]) => `${(20 + 10 + ((ts - (t - 8)) / 8) * 940).toFixed(1)},${(222 - (v / (n - 1)) * 130).toFixed(1)}`).join(" ");
      line.setAttribute("points", pts);
    });
  })();

  /* ================= 컷 섞기 ================= */
  (function blend() {
    const sl = $("#bl-gap"); if (!sl) { return; }
    const svg = $("#bl-svg"), out = $("#bl-out");
    function draw() {
      const gap = +sl.value; $("#bl-gap-v").textContent = gap.toFixed(3);
      const FULL = 0.04, ZERO = 0.09, SPAN = 0.45;
      const w = SPAN * clamp((ZERO - gap) / (ZERO - FULL), 0, 1);
      svg.innerHTML = "";
      svgEl("rect", { x: 20, y: 14, width: 520, height: 34, rx: 8, fill: "#fff", stroke: INK, "stroke-width": 2.5 }, svg);
      if (w > 0) { const x0 = 20 + 520 * (1 - w); svgEl("rect", { x: x0, y: 14, width: 520 * w, height: 34, rx: 6, fill: PINK_L, opacity: .75 }, svg); }
      const t1 = svgEl("text", { x: 22, y: 36, style: "font-size:13px;font-weight:700;fill:" + INK }, svg); t1.textContent = "컷 i 만 선명하게";
      const t2 = svgEl("text", { x: 538, y: 36, "text-anchor": "end", style: "font-size:13px;font-weight:700;fill:" + INK }, svg); t2.textContent = w > 0 ? "컷 i+1 이 서서히" : "";
      // k 곡선
      svgEl("rect", { x: 20, y: 62, width: 520, height: 58, rx: 8, fill: "#FFF7FA", stroke: LINE, "stroke-width": 2 }, svg);
      const pts = []; for (let i = 0; i <= 100; i++) { const fr = i / 100; const k = w > 0 ? smooth((fr - (1 - w)) / w) : 0; pts.push(`${(20 + fr * 520).toFixed(1)},${(114 - k * 46).toFixed(1)}`); }
      svgEl("polyline", { points: pts.join(" "), fill: "none", stroke: PINK_D, "stroke-width": 3 }, svg);
      const t3 = svgEl("text", { x: 24, y: 78, style: "font-size:12px;fill:" + INK }, svg); t3.textContent = "다음 컷의 진하기";
      out.innerHTML = w <= 0 ? `gap ${gap.toFixed(3)} ≥ GAP_ZERO(0.09): <span class="bad">섞지 않음</span> — 두 자세가 겹쳐 안개 같은 잔상이 되므로 선명하게 바꿔요`
        : `gap ${gap.toFixed(3)} → 섞는 길이 w = 0.45 × ${((ZERO - gap) / (ZERO - FULL) > 1 ? 1 : (ZERO - gap) / (ZERO - FULL)).toFixed(2)} = <span class="ok">${(w * 100).toFixed(1)}%</span> (컷 사이 시간의 뒤쪽)`;
    }
    sl.addEventListener("input", draw); draw();
  })();

  /* ================= 털색 띠 ================= */
  (function coatRamp() {
    const box = $("#draw-coat"); if (!box) { return; }
    const svg = $("svg", box), cap = $(".caption", box), btns = $("#coat-btns");
    const R = {
      gray: [[0, .35, .70, 1], [[.07, .07, .09], [.34, .35, .39], [.66, .67, .70], [.93, .94, .96]], "회색: 어두운 곳은 거의 검정, 밝은 곳은 은회색"],
      black: [[0, .5, 1], [[0, 0, .01], [.075, .075, .085], [.27, .27, .30]], "검정: 가장 밝은 털도 짙은 회색 (줄무늬 결만 살짝 보임)"],
      white: [[0, .4, .75, 1], [[.60, .60, .64], [.84, .84, .86], [.96, .95, .94], [1, .99, .97]], "흰색: 그림자 쪽도 연한 회색"],
      orange: [[0, .3, .6, .85, 1], [[.30, .13, .04], [.64, .31, .10], [.89, .53, .22], [.97, .75, .46], [1, .91, .73]], "치즈(주황): 어두운 줄무늬는 진한 갈색, 밝은 곳은 크림"],
      calico_white: [[0, .4, .75, 1], [[.84, .83, .84], [.93, .925, .925], [.985, .978, .968], [1, .996, .988]], "삼색의 흰 부분: 거의 흰색(갈색 줄무늬를 흐려 지움)"],
      calico_black: [[0, .5, 1], [[.015, .013, .013], [.085, .078, .075], [.27, .25, .235]], "삼색의 검정 부분: 약간 갈색 기운"],
    };
    const css = (c) => `rgb(${c.map((v) => Math.round(v * 255)).join(",")})`;
    function show(k) {
      svg.innerHTML = ""; const [xs, cs, text] = R[k];
      const defs = svgEl("defs", {}, svg); const g = svgEl("linearGradient", { id: "coat-g", x1: 0, x2: 1, y1: 0, y2: 0 }, defs);
      xs.forEach((x, i) => svgEl("stop", { offset: x, "stop-color": css(cs[i]) }, g));
      svgEl("rect", { x: 20, y: 18, width: 960, height: 50, rx: 12, fill: "url(#coat-g)", stroke: INK, "stroke-width": 3 }, svg);
      xs.forEach((x, i) => { const cx = 20 + x * 960; svgEl("circle", { cx, cy: 90, r: 9, fill: css(cs[i]), stroke: INK, "stroke-width": 2.5 }, svg); const t = svgEl("text", { x: Math.min(940, Math.max(40, cx)), y: 108, "text-anchor": "middle", style: "font-size:12px;fill:" + INK }, svg); t.textContent = x; });
      const l = svgEl("text", { x: 22, y: 12, style: "font-size:12px;fill:" + INK }, svg); l.textContent = "어두운 털 (ln = 0)";
      const r = svgEl("text", { x: 978, y: 12, "text-anchor": "end", style: "font-size:12px;fill:" + INK }, svg); r.textContent = "밝은 털 (ln = 1)";
      cap.innerHTML = `<b>${k}</b> — ${text}. 새 색 = <code>np.interp(밝기, 위 점들, 색)</code>`;
      $$("button", btns).forEach((b) => b.classList.toggle("on", b.dataset.k === k));
    }
    Object.keys(R).forEach((k) => { const b = document.createElement("button"); b.className = "btn"; b.textContent = k; b.dataset.k = k; b.onclick = () => show(k); btns.appendChild(b); });
    show("orange");
  })();

  /* ================= 다음 행동 뽑기 ================= */
  (function markov() {
    const box = $("#markov"); if (!box || !D.flow) { return; }
    const sel = $("#mk-last"), modeSel = $("#mk-mode"), hour = $("#mk-hour"), bars = $("#mk-bars"), out = $("#mk-out");
    const KINDS = Object.keys(D.dur), G = D.group;
    const gcol = { "잠": "#B9A2F0", "쉬기": "#7DB7E8", "그루밍": "#F59BC0", "이동": "#F2B34D", "놀이": "#6FCF97", "하품·기지개": "#C9B39A" };
    const CORNER = ["sit", "sittilt", "loaf", "sleep", "groom", "groomleg", "groomface", "scratchneck", "yawn", "stretch", "knead", "idle"];
    ["start", ...Object.keys(D.flow).filter((k) => k !== "start")].forEach((k) => { const o = document.createElement("option"); o.value = k; o.textContent = k + (G[k] ? ` (${G[k]})` : ""); sel.appendChild(o); });
    sel.value = "run";
    const actMult = (h) => (h >= 7 && h < 10) || (h >= 17 && h < 21) ? [1.35, 0.75] : (h >= 11 && h < 16) ? [0.65, 1.35] : [1, 1];
    function probs(last) {
      const corner = modeSel.value === "corner", h = +hour.value;
      $("#mk-hour-v").textContent = hhmm(h * 60);
      const base = corner ? D.weightsCorner : D.weights;
      let allowed = new Set(corner ? CORNER : KINDS);
      if (!corner) { allowed.delete("kick"); allowed.delete("travel"); if ($("#mk-nojump").checked) { allowed.delete("jump"); } }
      const happy = $("#mk-happy").checked, hungry = $("#mk-hungry").checked;
      const [move, nap] = actMult(h); const mult = {};
      if (!corner) {
        ["walk", "trot", "run", "sneak", "jump", "travel", "kick", "tailplay", "knead"].forEach((k) => (mult[k] = move * (happy ? 1.4 : 1)));
        mult.sleep = nap * (hungry ? 0.7 : 1);
        if (hungry) { ["run", "kick", "tailplay", "knead", "trot"].forEach((k) => (mult[k] = 0)); }
      }
      const row = D.flow[last] || D.flow.start; const cand = [];
      Object.entries(row).forEach(([k, aff]) => { if (allowed.has(k) && base[k] != null && aff > 0) { const w = base[k] * aff * (mult[k] != null ? mult[k] : 1); if (w > 0) { cand.push([k, w, aff, base[k], mult[k] != null ? mult[k] : 1]); } } });
      if (!cand.length) { ["sit", "idle", "sittilt"].filter((k) => allowed.has(k)).forEach((k) => cand.push([k, 1, 1, 1, 1])); }
      const tot = cand.reduce((s, c) => s + c[1], 0);
      return cand.map((c) => ({ k: c[0], p: c[1] / tot, aff: c[2], base: c[3], mult: c[4] })).sort((a, b) => b.p - a.p);
    }
    function render() {
      const pr = probs(sel.value);
      bars.innerHTML = pr.map((r) => `<div style="display:flex;align-items:center;gap:8px;margin:3px 0;font-size:13.5px"><span style="width:92px;font-family:var(--font-mono)">${r.k}</span><span style="flex:1;background:#fff;border:2px solid ${INK};border-radius:8px;height:18px;overflow:hidden"><i style="display:block;height:100%;width:${(r.p * 100).toFixed(1)}%;background:${gcol[G[r.k]] || PINK}"></i></span><b style="width:52px;text-align:right">${(r.p * 100).toFixed(1)}%</b></div>`).join("")
        + `<div class="muted" style="font-size:12.5px;margin-top:4px">막대 = 기본 가중치 × 개연성 × 상황 배수 를 비율로 바꾼 값. 색 = 시간 배분 묶음. (아이콘 차기·모니터 건너가기는 기본 상태에서 꺼져 있어 후보에서 빠져요)</div>`;
      out.innerHTML = `<span class="dim">${sel.value} 다음 후보 ${pr.length}가지 — 가장 높은 것: </span><span class="ok">${pr[0] ? pr[0].k : "-"}</span> ${pr[0] ? `(= ${pr[0].base.toFixed(2)} × ${pr[0].aff} × ${pr[0].mult.toFixed(2)})` : ""}`;
    }
    [sel, modeSel, hour, $("#mk-happy"), $("#mk-hungry"), $("#mk-nojump")].forEach((e) => e.addEventListener("input", render));
    $("#mk-draw").onclick = () => {
      let last = sel.value; const seq = [];
      for (let i = 0; i < 10; i++) { const pr = probs(last); let r = Math.random() * pr.reduce((s, x) => s + x.p, 0), pick = pr[pr.length - 1].k; for (const x of pr) { r -= x.p; if (r <= 0) { pick = x.k; break; } } const [a, b] = D.dur[pick]; seq.push(`${pick}(${(a + Math.random() * (b - a)).toFixed(1)}초)`); last = pick; }
      out.innerHTML = `<span class="dim">${sel.value} 다음에…</span><br>` + seq.join(" → ");
    };
    render();

    // 20,000번 시뮬레이션
    $("#mk-sim").onclick = function () {
      const base = D.weights, allowedAll = KINDS; const mean = (k) => (D.dur[k][0] + D.dur[k][1]) / 2;
      let last = "start", tsum = 0; const share = {}; const n = 20000;
      for (let i = 0; i < n; i++) {
        const row = D.flow[last] || D.flow.start; const c = [], w = [];
        Object.entries(row).forEach(([k, a]) => { if (allowedAll.includes(k) && base[k] != null && a > 0) { c.push(k); w.push(base[k] * a); } });
        let r = Math.random() * w.reduce((s, x) => s + x, 0), pick = c[c.length - 1];
        for (let j = 0; j < c.length; j++) { r -= w[j]; if (r <= 0) { pick = c[j]; break; } }
        const g = G[pick]; share[g] = (share[g] || 0) + mean(pick); tsum += mean(pick); last = pick;
      }
      const target = D.targetDay, tt = Object.values(target).reduce((s, x) => s + x, 0);
      $("#mk-share").innerHTML = Object.keys(target).map((g) => {
        const got = (share[g] || 0) / tsum * 100, want = target[g] / tt * 100;
        return `<div style="display:flex;align-items:center;gap:8px;margin:4px 0;font-size:13.5px"><span style="width:96px">${g}</span><span style="flex:1;position:relative;background:#fff;border:2px solid ${INK};border-radius:8px;height:22px;overflow:hidden"><i style="display:block;height:100%;width:${got.toFixed(1)}%;background:${gcol[g]}"></i><b style="position:absolute;top:-2px;left:${want.toFixed(1)}%;width:3px;height:26px;background:${INK}"></b></span><b style="width:150px;text-align:right">${got.toFixed(1)}% <span class="muted">(목표 ${want.toFixed(1)}%)</span></b></div>`;
      }).join("");
      $("#mk-share-cap").innerHTML = `행동 ${n.toLocaleString("ko-KR")}번을 뽑아 평균 길이를 곱한 시간 비율이에요. 검은 막대 = 목표.`;
    };
  })();

  /* ================= 도약·속도 ================= */
  (function physics() {
    const rise = $("#ph-rise"); if (!rise) { return; }
    const svg = $("#ph-svg"), out = $("#ph-out"), gait = $("#ph-gait");
    function draw() {
      const r = +rise.value, V = +gait.value; $("#ph-rise-v").textContent = r;
      const dur = 0.7 + r / 1500, arc = 70 + 0.2 * r;
      svg.innerHTML = "";
      // 왼쪽: 도약 곡선 (화면 좌표: 위가 작은 y)
      svgEl("rect", { x: 6, y: 6, width: 300, height: 208, rx: 10, fill: "#FFF7FA", stroke: LINE, "stroke-width": 2 }, svg);
      const maxH = 620 + 140, sx = 260 / 380, ground = 196;
      const pts = []; for (let i = 0; i <= 60; i++) { const p = i / 60; const x = 30 + p * 260; const y = ground + (-(r * p) + 4 * arc * p * (1 - p) * -1) * (190 / maxH); pts.push(`${x.toFixed(1)},${y.toFixed(1)}`); }
      svgEl("polyline", { points: pts.join(" "), fill: "none", stroke: PINK_D, "stroke-width": 3 }, svg);
      svgEl("line", { x1: 20, x2: 300, y1: ground, y2: ground, stroke: INK, "stroke-width": 2 }, svg);
      svgEl("rect", { x: 270, y: ground - r * (190 / maxH), width: 36, height: 6, fill: INK }, svg);
      svgEl("circle", { cx: 30, cy: ground, r: 6, fill: PINK, stroke: INK, "stroke-width": 2 }, svg);
      const lab = svgEl("text", { x: 14, y: 24, style: "font-size:12.5px;font-weight:700;fill:" + INK }, svg); lab.textContent = `도약: rise=${r}px → ${dur.toFixed(2)}초 + 웅크림 0.3초`;
      // 오른쪽: 속도 곡선
      svgEl("rect", { x: 320, y: 6, width: 314, height: 208, rx: 10, fill: "#FFF7FA", stroke: LINE, "stroke-width": 2 }, svg);
      const vp = []; for (let i = 0; i <= 100; i++) { const t = i / 100 * 5; let v; if (t < 3) { v = Math.min(V, V / 0.35 * t); } else { v = Math.max(0, V - V / 0.30 * (t - 3)); } vp.push(`${(335 + t / 5 * 285).toFixed(1)},${(196 - v / 320 * 170).toFixed(1)}`); }
      svgEl("polyline", { points: vp.join(" "), fill: "none", stroke: INK, "stroke-width": 3 }, svg);
      svgEl("line", { x1: 335, x2: 620, y1: 196, y2: 196, stroke: INK, "stroke-width": 2 }, svg);
      const l2 = svgEl("text", { x: 330, y: 24, style: "font-size:12.5px;font-weight:700;fill:" + INK }, svg); l2.textContent = `속도 v(t): 최고 ${V}px/s · 가속 0.35초 · 3초에 멈추기 시작 · 감속 0.30초`;
      const tl = svgEl("text", { x: 620, y: 210, "text-anchor": "end", style: "font-size:11px;fill:" + INK }, svg); tl.textContent = "0 ~ 5초";
      const accDist = V * 0.35 / 2, decDist = V * 0.30 / 2;
      out.innerHTML = `점프 시간 = 0.7 + ${r}/1500 = <span class="ok">${dur.toFixed(3)}초</span> · 호 높이 = 70 + 0.2×${r} = <span class="ok">${arc.toFixed(0)}px</span>\n` + `가속하는 동안 이동 ${accDist.toFixed(1)}px · 멈추는 동안 ${decDist.toFixed(1)}px (속도 × scale 을 곱해서 씀)`;
      out.style.whiteSpace = "pre-line";
    }
    rise.addEventListener("input", draw); gait.addEventListener("input", draw); draw();
  })();

  /* ================= 하루 생활 ================= */
  (function routine() {
    const box = $("#routine-sim"); if (!box) { return; }
    const svg = $("#rt-svg"), out = $("#rt-out");
    const ids = ["rt-now", "rt-fed", "rt-ns", "rt-ne", "rt-meals"];
    function draw() {
      const now = +$("#rt-now").value, fed = +$("#rt-fed").value;
      const ns = toMin($("#rt-ns").value), ne = toMin($("#rt-ne").value);
      const meals = $("#rt-meals").value.split(",").map(toMin).filter((x) => x != null).sort((a, b) => a - b).filter((x, i, a) => a.indexOf(x) === i);
      $("#rt-now-v").textContent = hhmm(now); $("#rt-fed-v").textContent = hhmm(fed);
      const X = (m) => 20 + (m / 1440) * 660;
      svg.innerHTML = "";
      svgEl("rect", { x: 20, y: 40, width: 660, height: 40, rx: 10, fill: "#fff", stroke: INK, "stroke-width": 3 }, svg);
      const night = (m) => ns != null && ne != null && ns !== ne && (ns < ne ? m >= ns && m < ne : m >= ns || m < ne);
      if (ns != null && ne != null && ns !== ne) {
        const seg = (a, b) => svgEl("rect", { x: X(a), y: 40, width: X(b) - X(a), height: 40, fill: "#B9A2F0", opacity: .55 }, svg);
        if (ns < ne) { seg(ns, ne); } else { seg(ns, 1440); seg(0, ne); }
      }
      for (let h = 0; h <= 24; h += 3) { const t = svgEl("text", { x: X(h * 60), y: 98, "text-anchor": "middle", style: "font-size:11px;fill:" + INK }, svg); t.textContent = h + "시"; }
      const isNight = night(now);
      // 밥 창
      let due = null;
      meals.forEach((sl, i) => {
        let end = sl + 480; if (i + 1 < meals.length) { end = Math.min(end, meals[i + 1]); } if (ns != null && ns > sl) { end = Math.min(end, ns); }
        const feedOk = fed < sl - 30; const act = !isNight && sl <= now && now < end && feedOk;
        svgEl("rect", { x: X(sl), y: 50, width: Math.max(2, X(Math.min(end, 1440)) - X(sl)), height: 20, rx: 6, fill: feedOk ? "#F2B34D" : "#BFF0D4", opacity: .8, stroke: INK, "stroke-width": 1.5 }, svg);
        svgEl("circle", { cx: X(sl), cy: 60, r: 7, fill: PINK_D, stroke: INK, "stroke-width": 2 }, svg);
        const t = svgEl("text", { x: X(sl), y: 36, "text-anchor": "middle", style: "font-size:11px;font-weight:700;fill:" + INK }, svg); t.textContent = hhmm(sl);
        if (act) { due = sl; }
      });
      svgEl("line", { x1: X(fed), x2: X(fed), y1: 30, y2: 110, stroke: "#3FA373", "stroke-width": 3, "stroke-dasharray": "4 3" }, svg);
      const ft = svgEl("text", { x: X(fed), y: 124, "text-anchor": "middle", style: "font-size:11px;font-weight:700;fill:#2F8F5F" }, svg); ft.textContent = "마지막 밥";
      svgEl("line", { x1: X(now), x2: X(now), y1: 24, y2: 112, stroke: PINK_D, "stroke-width": 4 }, svg);
      const nt = svgEl("text", { x: X(now), y: 18, "text-anchor": "middle", style: "font-size:12px;font-weight:800;fill:" + PINK_D }, svg); nt.textContent = "지금 " + hhmm(now);
      const lines = [];
      lines.push(isNight ? `<span class="ok">잠자는 시간</span> — 구석에서 웅크리고 자요. 일정 알림·졸라대기는 쉬어요 (깨면 'wake' 사건).` : `깨어 있는 시간 — 정해 둔 알림이 돌 수 있어요.`);
      if (due != null) { lines.push(`<span class="bad">${hhmm(due)} 끼니를 안 먹었어요</span> → ('meal', '${due < 660 ? "아침" : due < 960 ? "점심" : "저녁"}', 처음) 사건, 이후 180초마다 최대 10번 '냐옹~ 냐옹~' + 풍선`); }
      else if (!isNight) { lines.push(`졸라댈 끼니가 없어요 (이미 먹었거나, 밥 시간 창 밖이에요). 주황 = 아직 안 먹은 끼니 창, 초록 = 먹은 끼니 창 (밥 시간 30분 전부터 준 밥도 인정).`); }
      out.innerHTML = lines.join("<br>");
    }
    ids.forEach((i) => $("#" + i).addEventListener("input", draw)); draw();
  })();

  /* ================= 런처 기하 ================= */
  (function launcherGeo() {
    const box = $("#launcher-geo"); if (!box) { return; }
    const nS = $("#lg-n"), pS = $("#lg-p"), svg = $("#lg-svg"), out = $("#lg-out");
    const R_MID = 98, BAND = 25, PER = 5, A0 = 12, A1 = 168;
    function draw() {
      const apps = +nS.value, total = 4 + apps, pages = Math.max(1, Math.ceil(total / PER));
      pS.max = pages; if (+pS.value > pages) { pS.value = pages; }
      const page = +pS.value - 1; $("#lg-n-v").textContent = apps; $("#lg-p-v").textContent = (page + 1) + " / " + pages;
      const cx = 160, cy = 168; svg.innerHTML = "";
      const pol = (r, a) => [cx + r * Math.cos(a * Math.PI / 180), cy - r * Math.sin(a * Math.PI / 180)];
      const ro = R_MID + BAND, ri = R_MID - BAND;
      const [x0o, y0o] = pol(ro, A0), [x1o, y1o] = pol(ro, A1), [x1i, y1i] = pol(ri, A1), [x0i, y0i] = pol(ri, A0);
      svgEl("path", { d: `M${x0o} ${y0o} A${ro} ${ro} 0 0 0 ${x1o} ${y1o} L${x1i} ${y1i} A${ri} ${ri} 0 0 1 ${x0i} ${y0i} Z`, fill: "#fff", stroke: INK, "stroke-width": 3 }, svg);
      [A0, A1].forEach((a) => { const [x, y] = pol(R_MID, a); svgEl("circle", { cx: x, cy: y, r: BAND, fill: "#fff", stroke: INK, "stroke-width": 3 }, svg); });
      const names = ["캘린더", "Gmail", "구글", "유튜브"]; const all = names.concat(Array.from({ length: apps }, (_, i) => "앱" + (i + 1)));
      const chunk = all.slice(page * PER, page * PER + PER);
      const entries = pages > 1 ? ["‹", ...chunk, "›"] : chunk; const m = entries.length;
      entries.forEach((nm, i) => {
        const ang = m > 1 ? A1 - 8 - (A1 - A0 - 16) * (i / (m - 1)) : 90; const [x, y] = pol(R_MID, ang);
        const arrow = nm === "‹" || nm === "›";
        svgEl("circle", { cx: x, cy: y, r: 16, fill: arrow ? "#EEE" : "#FFD3E0", stroke: INK, "stroke-width": 2.5 }, svg);
        const t = svgEl("text", { x, y: y + 4.5, "text-anchor": "middle", style: "font-size:" + (arrow ? 18 : 10) + "px;font-weight:800;fill:" + INK }, svg); t.textContent = arrow ? nm : nm.replace("앱", "#").slice(0, 3);
      });
      svgEl("circle", { cx, cy, r: 6, fill: PINK_D }, svg);
      const ct = svgEl("text", { x: cx, y: cy - 12, "text-anchor": "middle", style: "font-size:11px;fill:" + INK }, svg); ct.textContent = "고양이 머리";
      out.innerHTML = `전체 ${total}개(기본 4 + 등록 ${apps}) → ${pages}쪽. 이 쪽에 ${chunk.length}개${pages > 1 ? " + 화살표 2개" : ""}, 각도 간격 ${m > 1 ? ((A1 - A0 - 16) / (m - 1)).toFixed(1) : "-"}°`;
    }
    nS.addEventListener("input", draw); pS.addEventListener("input", draw); draw();
  })();

  /* ================= 디자인 토큰 ================= */
  (function tokens() {
    const g = $("#tokens"); if (!g) { return; }
    [["BG", "#FFE6EE", "창 바탕(연한 분홍)"], ["CARD", "#FFFFFF", "입력 칸·카드·풍선"], ["PINK / ACCENT", "#F67499", "대표 분홍·버튼"], ["PINK_D / ACCENT_D", "#E5557E", "눌렀을 때·제목 글씨"],
      ["PINK_L", "#EF99B1", "옅은 분홍·원 바탕"], ["LINE", "#F6C5D5", "테두리"], ["INK / TEXT", "#5A3A47", "글씨·윤곽선 (검정 대신 자두색)"], ["SUB", "#A8728A", "보조 글씨"],
      ["SOFT", "#FFD3E0", "선택·강조 바탕"], ["WARN", "#D8456F", "경고 글씨"], ["OK", "#3FA373", "성공 표시"], ["URL 파랑", "#2F6FD0", "링크 버튼"]].forEach(([n, c, u]) => {
      const d = document.createElement("div"); d.className = "card"; d.style.padding = "10px";
      d.innerHTML = `<div style="height:42px;border-radius:10px;border:3px solid ${INK};background:${c}"></div><b style="display:block;margin-top:6px;font-size:13px">${n}</b><code>${c}</code><div class="muted" style="font-size:12.5px">${u}</div>`;
      g.appendChild(d);
    });
  })();
});
