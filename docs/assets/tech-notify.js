/* 기술 문서: 스케줄러 시험대 · 보조 프로세스 주고받기 */
(window.PageInits = window.PageInits || []).push(function () {
  const { $, $$, NS } = window.DocUtil;
  const svgEl = (tag, attrs = {}, parent) => { const e = document.createElementNS(NS, tag); for (const k in attrs) { e.setAttribute(k, attrs[k]); } if (parent) { parent.appendChild(e); } return e; };
  const INK = "#5A3A47", PINK = "#F67499", PINK_D = "#E5557E", LINE = "#F6C5D5";
  const hhmm = (m) => String(Math.floor(m / 60)).padStart(2, "0") + ":" + String(m % 60).padStart(2, "0");
  const toMin = (s) => { const m = /^(\d{1,2}):(\d{2})$/.exec((s || "").trim()); return m && +m[1] < 24 && +m[2] < 60 ? +m[1] * 60 + +m[2] : null; };

  /* ================= 스케줄러 시험대 ================= */
  (function sched() {
    const box = $("#sched-sim"); if (!box) { return; }
    const svg = $("#sc-svg"), out = $("#sc-out");
    const ids = ["sc-times", "sc-now", "sc-last", "sc-age", "sc-enabled", "sc-quiet"];
    function draw() {
      const now = +$("#sc-now").value; $("#sc-now-v").textContent = hhmm(now);
      const raw = $("#sc-times").value.split(",").map((s) => s.trim()).filter(Boolean);
      const valid = raw.map(toMin).filter((x) => x != null), bad = raw.filter((s) => toMin(s) == null);
      const times = [...new Set(valid)].sort((a, b) => a - b);
      const lastTxt = $("#sc-last").value.trim(); const last = lastTxt ? toMin(lastTxt) : null;
      const age = +$("#sc-age").value, enabled = $("#sc-enabled").checked, quiet = $("#sc-quiet").checked;
      const X = (m) => 20 + (m / 1440) * 660;
      svg.innerHTML = "";
      svgEl("rect", { x: 20, y: 40, width: 660, height: 22, rx: 8, fill: "#fff", stroke: INK, "stroke-width": 3 }, svg);
      for (let h = 0; h <= 24; h += 3) { const t = svgEl("text", { x: X(h * 60), y: 82, "text-anchor": "middle", style: "font-size:11px;fill:" + INK }, svg); t.textContent = h + "시"; }
      times.forEach((m) => { svgEl("circle", { cx: X(m), cy: 51, r: 7, fill: m <= now ? PINK : "#fff", stroke: INK, "stroke-width": 2.5 }, svg); const t = svgEl("text", { x: X(m), y: 34, "text-anchor": "middle", style: "font-size:10.5px;font-weight:700;fill:" + INK }, svg); if (times.length <= 12) { t.textContent = hhmm(m); } });
      if (last != null) { svgEl("path", { d: `M${X(last)} 64 l-6 10 h12 z`, fill: "#3FA373", stroke: INK, "stroke-width": 1.5 }, svg); const t = svgEl("text", { x: X(last), y: 96, "text-anchor": "middle", style: "font-size:10.5px;font-weight:700;fill:#2F8F5F" }, svg); t.textContent = "last_run"; }
      svgEl("line", { x1: X(now), x2: X(now), y1: 22, y2: 70, stroke: PINK_D, "stroke-width": 4 }, svg);
      const nt = svgEl("text", { x: X(now), y: 16, "text-anchor": "middle", style: "font-size:12px;font-weight:800;fill:" + PINK_D }, svg); nt.textContent = "지금 " + hhmm(now);
      // 판단 (scheduler.due_slot 과 같은 순서)
      const L = [];
      if (bad.length) { L.push(`<span class="bad">잘못된 시각 무시: ${bad.join(", ")}</span> (HH:MM 24시간, 분은 두 자리)`); }
      let best = null; times.forEach((m) => { if (m <= now) { best = m; } });
      if (!enabled) { L.push(`<span class="bad">이 알림이 꺼져 있어요</span> → due_slot = None`); }
      else if (quiet) { L.push(`<span class="bad">잠자는 시간(quiet)</span> → tick 이 아무것도 하지 않아요. 깬 뒤 첫 점검(최대 20초)에서 <b>가장 최근 놓친 칸 하나</b>만 따라잡아요.`); }
      else if (best == null) { L.push(`오늘 아직 지난 알림 시각이 없어요 → None`); }
      else {
        L.push(`오늘 지난 칸 중 가장 최근 = <span class="ok">${hhmm(best)}</span>`);
        const late = now - best;
        if (age > 0 && late > age) { L.push(`<span class="bad">max_age_min=${age}</span>: ${late}분이나 지났으니 따라잡지 않아요 → None (매시 알림처럼 '지금'이 중요한 작업)`); }
        else if (last != null && best <= last) { L.push(`last_run(${hhmm(last)}) ≥ ${hhmm(best)}: <span class="bad">이미 처리한 칸</span> → None`); }
        else { L.push(`<span class="ok">지금 실행해야 해요</span> → 실행 <b>전에</b> last_run = 오늘 ${hhmm(best)} 로 저장하고 작업 스레드 시작 (${late > 0 ? `${late}분 늦게 따라잡는 것` : "제 시각"})`); }
      }
      out.innerHTML = L.join("<br>");
    }
    ids.forEach((i) => $("#" + i).addEventListener("input", draw)); draw();
  })();

  /* ================= 보조 프로세스 주고받기 ================= */
  (function proto() {
    const box = $("#proto"); if (!box) { return; }
    const btns = $("#proto-btns"), reqEl = $("#proto-req"), resEl = $("#proto-res"), cap = $("#proto-cap"), play = $("#proto-play");
    const K = {
      calendar: { req: { kind: "calendar", url: "https://calendar.google.com/calendar/ical/…/basic.ics" }, res: { ok: true, result: ["📅 오늘 일정 2개", "09:30  주간 회의", "종일  휴가"] },
        err: { ok: false, error: "캘린더 주소가 틀렸거나 바뀌었다냥 (비공개 주소를 다시 복사해 달라옹)", retry: false }, note: "주소는 비밀이라 명령줄이 아니라 표준 입력으로만 가요." },
      upcoming: { req: { kind: "upcoming", url: "https://…/basic.ics", hours: 2 }, res: { ok: true, result: ["📅 앞으로 2시간 일정 1개", "10:00~11:00  디자인 리뷰"] },
        err: { ok: false, error: "캘린더에 연결을 못 했다냥 (인터넷을 확인해 달라옹)", retry: true }, note: "일정이 없으면 result 가 빈 목록이고, 본체는 조용히 넘어가요." },
      mail: { req: { kind: "mail", user: "name@gmail.com", password: "(앱 비밀번호)", last_uid: 4821, uidvalidity: 1 }, res: { ok: true, result: { first: false, unseen: 3, new: ["홍길동"], new_count: 1, last_uid: 4822, uidvalidity: 1, lines: ["📧 홍길동에게서 메일 왔다~옹~"] } },
        err: { ok: false, error: "앱 비밀번호가 필요하다냥 (일반 구글 비밀번호가 아니라 ‘앱 비밀번호’ 16자리를 넣어 달라옹)", retry: false }, note: "본체는 새 last_uid·uidvalidity 를 설정 파일(mail_state)에 저장해 다음에는 그 뒤의 메일만 알려요." },
      gemini: { req: { kind: "gemini", key: "(API 키)", model: "", prompt: "'연결 성공' 이라고만 답해.", system: "너는 사용자의 …", search: false }, res: { ok: true, result: { text: "연결 성공", sources: [] } },
        err: { ok: false, error: "요청이 너무 많다냥 (잠시 뒤 다시 해 보겠다옹)", retry: true }, note: "429/503/5xx 는 보조 프로세스 안에서 3초·8초 쉬고 최대 2번 더 시도한 뒤에야 retry=true 로 돌아와요." },
      news: { req: { kind: "news", key: "(API 키)", model: "", prompt: "아래 자료로 오늘의 소식을 정리해 줘. …", system: "너는 사용자의 바탕화면에 사는 비서야. …", city: "자동", quotes: "코스피=^KS11\n…" },
        res: { ok: true, result: { text: "# 날씨 (서울)\n- …", sources: [{ title: "기사 제목 - 언론사", url: "https://news.google.com/…" }] } },
        err: { ok: false, error: "날씨·뉴스·시세를 하나도 못 가져왔다냥 (인터넷을 확인해 달라옹)", retry: true }, note: "자료 수집은 보조 프로세스 안에서 일어나고, Gemini 에는 정리만 시켜요." },
      favicon: { req: { kind: "favicon", url: "https://example.com" }, res: { ok: true, result: { b64: "iVBORw0KGgoAAAANSUhEUg…" } },
        err: { ok: false, error: "작업을 못 했다냥 (URLError)", retry: false }, note: "알려지지 않은 예외는 클래스 이름만 알려 줘요 (주소 같은 내용이 새지 않게)." },
      scan: { req: { kind: "scan", work_dir: "…\\DesktopCat\\security", allow: { process: [], autorun: [], privacy: [] }, self_paths: ["…\\DesktopCat"] }, res: { ok: true, result: { first: false, entries: 73, processes: 118, findings: [] } },
        err: { ok: false, error: "작업을 못 했다냥 (TimeoutExpired)", retry: false }, note: "점검은 PowerShell 을 부를 수 있어 제한 시간이 240초예요." },
      vt: { req: { kind: "vt", key: "(API 키)", sha256: "275a021b…fd0f" }, res: { ok: true, result: { found: true, malicious: 60, suspicious: 0, harmless: 0, undetected: 8, names: ["eicar.com"], link: "https://www.virustotal.com/gui/file/…" } },
        err: { ok: false, error: "VirusTotal 조회 한도를 넘었다냥 (무료는 분당 4건·하루 500건이다옹)", retry: true }, note: "보내는 것은 해시값뿐이에요." },
    };
    let cur = "calendar", errMode = false, timers = [];
    const pretty = (o) => JSON.stringify(o, null, 1).replace(/\n\s*/g, (m) => m);
    function clear() { timers.forEach(clearTimeout); timers = []; }
    function show() { const k = K[cur]; reqEl.textContent = JSON.stringify(k.req); resEl.textContent = ""; cap.innerHTML = `<b>${cur}</b> — ${k.note} <span class="muted">(실제 선로에서는 한글이 <code>\\uXXXX</code> 로 바뀐 순수 ASCII 한 줄이에요.)</span>`; }
    function type(el, text, ms, done) {
      let i = 0; const step = Math.max(1, Math.ceil(text.length / (ms / 20)));
      (function tick() { el.textContent = text.slice(0, i); i += step; if (i <= text.length + step) { timers.push(setTimeout(tick, 20)); } else { el.textContent = text; if (done) { done(); } } })();
    }
    function run() {
      clear(); const k = K[cur]; reqEl.textContent = ""; resEl.textContent = "";
      type(reqEl, JSON.stringify(k.req), 900, () => {
        resEl.textContent = "⏳ 보조 프로세스 실행 중… (요청 1건 처리 후 종료)";
        timers.push(setTimeout(() => type(resEl, JSON.stringify(errMode ? k.err : k.res), 1000, () => { resEl.classList.toggle("bad", errMode); }), 900));
      });
    }
    Object.keys(K).forEach((k) => { const b = document.createElement("button"); b.className = "btn" + (k === cur ? " on" : ""); b.textContent = k; b.onclick = () => { cur = k; $$("button", btns).forEach((x) => { if (!x.dataset.err) { x.classList.toggle("on", x === b); } }); clear(); show(); }; btns.appendChild(b); });
    const eb = document.createElement("button"); eb.className = "btn"; eb.dataset.err = 1; eb.textContent = "오류 응답"; eb.onclick = () => { errMode = !errMode; eb.classList.toggle("on", errMode); }; btns.appendChild(eb);
    play.onclick = run; show();
  })();
});
