/* 기술 문서: 경비 구성도 · 랜섬웨어 실험실 · 수상도 계산기 · 다운로드 계산기 */
(window.PageInits = window.PageInits || []).push(function () {
  const { $, $$, NS } = window.DocUtil;
  const svgEl = (tag, attrs = {}, parent) => { const e = document.createElementNS(NS, tag); for (const k in attrs) { e.setAttribute(k, attrs[k]); } if (parent) { parent.appendChild(e); } return e; };
  const INK = "#5A3A47", PINK = "#F67499", PINK_D = "#E5557E", LINE = "#F6C5D5";
  const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
  const LV = { danger: ["위험", "#FFB3C9"], warn: ["의심", "#FFEBC7"], info: ["참고", "#DCE8FF"], none: ["알리지 않음", "#D7F3E3"] };
  const levelHtml = (l) => `<span style="display:inline-block;border:2px solid ${INK};border-radius:20px;padding:0 12px;font-weight:800;background:${LV[l][1]};color:${INK}">${LV[l][0]}</span>`;
  function meter(el, score, max, marks) {
    const pct = (v) => (clamp(v, 0, max) / max * 100).toFixed(1);
    const color = score >= (marks[1] ? marks[1][0] : 99) ? "#E5557E" : score >= marks[0][0] ? "#F2B34D" : "#6FCF97";
    el.innerHTML = `<div style="position:relative;height:22px;border:3px solid ${INK};border-radius:12px;background:#fff;overflow:hidden"><i style="display:block;height:100%;width:${pct(score)}%;background:${color};transition:width .3s"></i>`
      + marks.map(([v, t]) => `<b style="position:absolute;top:0;left:${pct(v)}%;height:100%;border-left:3px dashed ${INK}"></b><span style="position:absolute;top:1px;left:calc(${pct(v)}% + 4px);font-size:11px;font-weight:700">${t}</span>`).join("")
      + `</div><div style="font-size:13px;margin-top:2px">점수 <b>${score}</b></div>`;
  }

  /* ================= 경비 구성도 ================= */
  (function arch() {
    const box = $("#sec-arch"); if (!box) { return; }
    const svg = $("svg", box), cap = $("#sec-arch-cap");
    const N = {
      ransom: { x: 20, y: 20, w: 240, h: 74, t: "랜섬웨어 감시", s: "sec_ransom.py · sec_watch.py", i: "폴더마다 <code>ReadDirectoryChangesW</code> 감시 스레드 + 1초 판단 스레드. 미끼 파일·대량 변경·엔트로피·안내 파일을 봐요. 위험(danger) 경보를 내요." },
      scan: { x: 20, y: 108, w: 240, h: 74, t: "자동 시작·프로세스 점검", s: "sec_scan.py · sec_sig.py", i: "스캔 스레드가 90초 뒤부터 10분마다 보조 프로세스(<code>scan</code>)를 불러요. 새 자동 시작 항목과 수상한 위치에서 도는 서명 없는 프로그램을 점수로 판단해요." },
      priv: { x: 20, y: 196, w: 240, h: 74, t: "카메라·마이크", s: "sec_privacy.py", i: "30초마다 레지스트리 <code>CapabilityAccessManager</code> 를 읽어요. 처음 보는 프로그램이 지금 쓰고 있으면 의심(warn)." },
      dl: { x: 20, y: 284, w: 240, h: 74, t: "다운로드 검사", s: "sec_download.py", i: "다운로드 폴더에 새 실행 파일·스크립트가 완전히 받아지면 서명·출처(Zone.Identifier)·이중 확장자를 확인해요." },
      guard: { x: 380, y: 100, w: 240, h: 90, t: "SecurityGuard", s: "security.py (본부)", i: "감시기들을 켜고 끄고(<code>start/stop/reload</code>), 허용 목록(<code>allow</code>)과 VirusTotal 보강(<code>enrich</code>)을 맡아요. cat.py 는 이 클래스 하나만 다뤄요." },
      ev: { x: 380, y: 250, w: 240, h: 90, t: "SecEvents", s: "sec_events.py → events.json", i: "경보 한 건 = <code>{id, ts, kind, level, title, text, data, status}</code>. 잠금으로 스레드 안전, 30일·500건, <code>key+cooldown</code> 으로 중복 방지. 새 건이 생기면 <code>on_add</code> 콜백 → Qt 신호." },
      ui: { x: 740, y: 20, w: 240, h: 90, t: "화면 스레드", s: "cat.on_security_event", i: "위험이면 소리 + 풍선 + 쥐 잡기(<code>brain.hunt</code>) + 경보 창, 의심이면 1.5초 모아 풍선 하나, 참고면 기록만." },
      alert: { x: 740, y: 140, w: 240, h: 74, t: "경보 창", s: "sec_ui.AlertWindow", i: "무슨 일이 있었는지 + '지금 해야 할 일' 카드 + 의심 프로그램 줄(위치 열기·종료…) + 확인/무시/허용 버튼. 조치는 사용자가 누를 때만." },
      helper: { x: 740, y: 240, w: 240, h: 60, t: "보조 프로세스", s: "nethelper: scan · vt", i: "PowerShell(서명·작업 목록)과 VirusTotal 요청은 본체 밖에서 해요." },
      win: { x: 740, y: 320, w: 240, h: 60, t: "윈도우 · 인터넷", s: "파일 알림 · 레지스트리 · VT", i: "폴더 변경 알림, 레지스트리(Run·작업·카메라 기록), Zone.Identifier, VirusTotal API." },
    };
    const E = [["ransom", "guard"], ["scan", "guard"], ["priv", "guard"], ["dl", "guard"], ["guard", "ev"], ["ev", "ui"], ["ui", "alert"], ["scan", "helper"], ["guard", "helper"], ["helper", "win"]];
    const center = (n) => [n.x + n.w / 2, n.y + n.h / 2];
    E.forEach(([a, b]) => { const A = N[a], B = N[b]; const [ax, ay] = center(A), [bx, by] = center(B); const x1 = ax < bx ? A.x + A.w : A.x, x2 = ax < bx ? B.x : B.x + B.w; svgEl("path", { d: `M${x1} ${ay} C${(x1 + x2) / 2} ${ay} ${(x1 + x2) / 2} ${by} ${x2} ${by}`, class: "edge" }, svg); });
    const gs = {};
    Object.entries(N).forEach(([k, n]) => {
      const g = svgEl("g", { class: "svg-node", tabindex: 0 }, svg); gs[k] = g;
      svgEl("rect", { x: n.x, y: n.y, width: n.w, height: n.h, rx: 14 }, g);
      const t = svgEl("text", { x: n.x + n.w / 2, y: n.y + n.h / 2 - 4, "text-anchor": "middle", style: "font-size:16px" }, g); t.textContent = n.t;
      const s = svgEl("text", { x: n.x + n.w / 2, y: n.y + n.h / 2 + 17, "text-anchor": "middle", class: "s" }, g); s.textContent = n.s;
      const sel = () => { Object.entries(gs).forEach(([kk, gg]) => gg.classList.toggle("on", kk === k)); cap.innerHTML = `<b>${n.t}</b> — ${n.i}`; };
      g.addEventListener("click", sel); g.addEventListener("keydown", (e) => { if (e.key === "Enter") { sel(); } });
    });
    gs.guard.dispatchEvent(new Event("click"));
  })();

  /* ================= 랜섬웨어 실험실 ================= */
  (function lab() {
    const box = $("#ransom-lab"); if (!box) { return; }
    const svg = $("#rl-svg"), out = $("#rl-out");
    const S = { loose: [40, 3], normal: [25, 2], strict: [12, 2] };
    const presets = {
      unzip: { n: 0, d: 8, x: 0, e: 0, m: 0, c: false, note: "새로 만든 파일 400개를 풀고 있어요. 새 파일의 쓰기는 '기존 파일 변경'이 아니라서 센 대상에서 빠져요 (만든 지 30초 안)." },
      copy: { n: 0, d: 2, x: 0, e: 0, m: 0, c: false, note: "사진 100장을 복사하는 중 — 모두 새로 만든 파일이에요." },
      edit: { n: 3, d: 1, x: 0, e: 0, m: 0, c: false, note: "문서 3개를 저장 — 문턱 아래예요." },
      rename: { n: 200, d: 6, x: 180, e: 6, m: 0, c: false, note: "파일 이름이 한꺼번에 낯선 확장자(.locked)로 바뀌고 내용도 깨졌어요." },
      overwrite: { n: 150, d: 5, x: 0, e: 7, m: 0, c: false, note: "이름은 그대로인데 내용이 암호화된 데이터로 덮어써졌어요 (머리글 깨짐·엔트로피 높음)." },
      note: { n: 30, d: 4, x: 0, e: 2, m: 4, c: false, note: "파일 30개가 바뀌고 '복구 안내' 파일이 4개 폴더에 생겼어요." },
      canary: { n: 1, d: 1, x: 0, e: 0, m: 0, c: true, note: "숨김 미끼 문서가 건드려졌어요 — 문턱과 상관없이 즉시 위험." },
    };
    const get = (id) => $("#" + id);
    const fields = { n: "rl-n", d: "rl-d", x: "rl-x", e: "rl-e", m: "rl-m" };
    function draw() {
      const [F, Dn] = S[get("rl-sens").value];
      const v = {}; Object.entries(fields).forEach(([k, id]) => { v[k] = +get(id).value; get(id + "-v").textContent = v[k]; });
      const canary = get("rl-c").checked;
      svg.innerHTML = "";
      // 파일 타일 100칸
      const cols = 25, tile = 18;
      for (let i = 0; i < 100; i++) { const r = Math.floor(i / cols), c = i % cols; const hit = i < Math.min(100, v.n); svgEl("rect", { x: 10 + c * (tile + 2), y: 10 + r * (tile + 2), width: tile, height: tile, rx: 4, fill: hit ? PINK_D : "#fff", stroke: INK, "stroke-width": 1.5, opacity: hit ? 1 : .9 }, svg); }
      const t = svgEl("text", { x: 10, y: 100, style: "font-size:12px;fill:" + INK }, svg); t.textContent = `변경된 기존 파일 ${v.n}개 (칸 하나 = 파일 1개, 100개까지 표시)`;
      // 게이지
      const gx = 10, gw = 540;
      const bar = (y, val, need, label) => { svgEl("rect", { x: gx, y, width: gw, height: 14, rx: 7, fill: "#fff", stroke: INK, "stroke-width": 2 }, svg); const max = Math.max(need * 2, val, 1); svgEl("rect", { x: gx, y, width: gw * clamp(val / max, 0, 1), height: 14, rx: 7, fill: val >= need ? PINK_D : "#6FCF97" }, svg); svgEl("line", { x1: gx + gw * need / max, x2: gx + gw * need / max, y1: y - 3, y2: y + 17, stroke: INK, "stroke-width": 3 }, svg); const tx = svgEl("text", { x: gx + gw + 2, y: y + 11, style: "font-size:11px;fill:" + INK }, svg); tx.textContent = ""; const lt = svgEl("text", { x: gx + 4, y: y + 11, style: "font-size:10.5px;font-weight:700;fill:" + INK }, svg); lt.textContent = label; };
      bar(112, v.n, F, `파일 ${v.n} / 문턱 ${F}`); bar(132, v.d, Dn, `폴더 ${v.d} / 문턱 ${Dn}`);
      // 판단
      const L = [];
      const big = v.n >= F && v.d >= Dn, mid = v.n >= Math.floor(F / 2) && v.d >= Dn;
      let level = "none";
      if (canary) { level = "danger"; L.push(`<span class="bad">미끼 파일이 건드려졌어요</span> → 문턱과 상관없이 즉시 위험 (source=canary, 60초 쿨다운)`); }
      else if (!mid) { L.push(`변경 ${v.n}개·폴더 ${v.d}곳 < 판단 문턱(파일 ${Math.floor(F / 2)}개 이상 & 폴더 ${Dn}곳 이상) → <span class="ok">아직 판단하지 않아요</span>`); }
      else {
        const extFlag = big && v.x >= Math.max(8, Math.floor(F / 3)) && v.x > 0;
        const entFlag = big && 8 >= 4 && v.e / 8 >= 0.6;
        const noteFlag = v.m >= 3;
        L.push(`big = ${big} (파일 ≥ ${F} & 폴더 ≥ ${Dn}) · mid = ${mid}`);
        L.push(`(가) 낯선 확장자로 한꺼번에: ${extFlag ? '<span class="bad">예</span>' : "아니오"} (이름이 바뀐 ${v.x}개, 필요 ≥ ${Math.max(8, Math.floor(F / 3))}개 & big)`);
        L.push(`(나) 암호화된 것처럼 보임: ${entFlag ? '<span class="bad">예</span>' : "아니오"} (표본 8개 중 ${v.e}개 = ${(v.e / 8 * 100).toFixed(0)}%, 필요 ≥ 60% & big)`);
        L.push(`(다) 안내 파일: ${noteFlag ? '<span class="bad">예</span>' : "아니오"} (${v.m}개 폴더, 필요 ≥ 3)`);
        if (extFlag || entFlag || (noteFlag && v.n >= Math.floor(F / 2))) { level = "danger"; L.push(`→ <span class="bad">경보!</span> 120초 쿨다운, 의심 프로그램 후보를 1.5초 재서 덧붙임`); }
        else { L.push(`→ <span class="ok">경보 없음</span> (단서가 모자라요)`); }
      }
      out.innerHTML = levelHtml(level) + "<br>" + L.join("<br>");
    }
    Object.values(fields).concat(["rl-sens", "rl-c"]).forEach((id) => get(id).addEventListener("input", draw));
    get("rl-sc").addEventListener("input", () => { const p = presets[get("rl-sc").value]; if (!p) { return; } Object.entries(fields).forEach(([k, id]) => (get(id).value = p[k])); get("rl-c").checked = p.c; draw(); out.insertAdjacentHTML("afterbegin", `<span class="dim">${p.note}</span><br>`); });
    draw();
  })();

  /* ================= 수상도 계산기 ================= */
  (function score() {
    const box = $("#score-calc"); if (!box) { return; }
    const ids = ["sc2-loc", "sc2-sig", "sc2-sys", "sc2-dbl", "sc2-new", "sc2-auto"];
    const LOC = { "0": [0, ""], "1": [1, "AppData\\Local 폴더에서 실행 중"], "2": [2, "다운로드 폴더에서 실행 중"], "3": [3, "AppData\\Roaming 폴더에서 실행 중"], "3p": [3, "공용 폴더(Public·ProgramData)에서 실행 중"], "4": [4, "임시 폴더·휴지통에서 실행 중"] };
    function draw() {
      const [pts, why] = LOC[$("#sc2-loc").value], st = $("#sc2-sig").value;
      const sys = $("#sc2-sys").checked, dbl = $("#sc2-dbl").checked, nw = $("#sc2-new").checked, auto = $("#sc2-auto").checked;
      let score = 0; const R = [];
      if (pts) { score += pts; R.push(`+${pts} ${why}`); }
      if (st === "hashmismatch") { score += 6; R.push("+6 서명이 있지만 서명 뒤에 파일이 바뀐 것 같아요"); }
      else if (st === "notsigned") { score += 2; R.push("+2 디지털 서명이 없어요"); }
      else if (st === "unknown") { score += 1; R.push("+1 디지털 서명을 확인하지 못했어요"); }
      if (sys) { score += 6; R.push("+6 윈도우 시스템 프로그램인 척하지만 윈도우 폴더 밖에 있어요"); }
      if (dbl) { score += 5; R.push("+5 문서처럼 보이게 이중 확장자를 쓴 실행 파일이에요"); }
      if (nw) { score += 1; R.push("+1 만들어진 지 하루도 안 됐어요"); }
      let level = "none";
      if (!(st === "valid" && !sys && !dbl)) { level = score >= 9 ? "danger" : score >= 6 ? "warn" : "none"; }
      else { R.push("유효한 서명이 있어서 알리지 않아요 (점수가 높아도)"); }
      meter($("#sc2-meter"), score, 16, [[6, "의심 6"], [9, "위험 9"]]);
      let html = `<b>실행 중 프로그램:</b> ${levelHtml(level)}<br>` + (R.length ? R.map((r) => "· " + r).join("<br>") : "· 평범한 위치에서 도는 프로그램이에요");
      if (auto) {
        let al, ar = [];
        if (st === "hashmismatch") { al = "danger"; ar = ["서명 뒤에 파일이 바뀐 것 같아요"]; }
        else if (st === "valid") { al = "info"; ar = ["유효한 서명 — 기록만 남겨요 (참고)"]; }
        else { const sus = pts >= 3; al = sus ? "danger" : "warn"; ar = [st === "notsigned" ? "디지털 서명이 없어요" : "디지털 서명을 확인하지 못했어요", sus ? "수상한 위치(점수 ≥ 3)라 위험으로 올려요" : "의심으로 알려요"]; }
        html += `<br><br><b>새 자동 시작 항목이라면:</b> ${levelHtml(al)}<br>` + ar.map((r) => "· " + r).join("<br>");
      }
      $("#sc2-out").innerHTML = html;
    }
    ids.forEach((i) => $("#" + i).addEventListener("input", draw)); draw();
  })();

  /* ================= 다운로드 계산기 ================= */
  (function dl() {
    const box = $("#dl-calc"); if (!box) { return; }
    const ids = ["dl-ext", "dl-sig", "dl-zone", "dl-dbl"];
    function draw() {
      const ext = $("#dl-ext").value, st = $("#dl-sig").value, zone = +$("#dl-zone").value, dbl = $("#dl-dbl").checked;
      const web = zone >= 3; let score = 0; const R = [];
      R.push(web ? "인터넷에서 받은 파일이에요" : "‘인터넷에서 받음’ 표시가 없어요");
      if (st === "hashmismatch") { score += 8; R.push("+8 디지털 서명 뒤에 파일이 바뀐 것 같아요"); }
      else if (st === "valid") { R.push("디지털 서명이 유효해요"); }
      else { score += 2; R.push("+2 디지털 서명이 없어요"); }
      if (dbl) { score += 5; R.push("+5 이중 확장자를 쓴 실행 파일이에요"); }
      if (ext === "js") { score += 2; R.push("+2 스크립트 파일이라 열면 바로 실행돼요"); } else if (ext === "lnk") { score += 1; R.push("+1 이 종류의 파일은 악성코드를 숨기는 데 자주 쓰여요"); }
      if (web) { score += 1; R.push("+1 인터넷 출처"); if (st !== "valid" && ext === "exe") { score += 2; R.push("+2 인터넷에서 받은 서명 없는 프로그램"); } }
      let level, title;
      if (st === "valid" && !dbl) { level = "info"; title = "내려받은 파일을 살펴봤어요 (서명 확인됨)"; }
      else if (score >= 8) { level = "danger"; title = "내려받은 파일이 아주 수상해요"; }
      else if (score >= 4) { level = "warn"; title = (!dbl && st !== "hashmismatch" && ext === "exe") ? "서명 없는 프로그램을 내려받았어요 (출처를 확인해 보세요)" : "내려받은 파일이 수상해요"; }
      else { level = "none"; title = "알리지 않아요"; }
      meter($("#dl-meter"), score, 14, [[4, "의심 4"], [8, "위험 8"]]);
      $("#dl-out").innerHTML = `${levelHtml(level)} <b>${title}</b><br>` + R.map((r) => "· " + r).join("<br>") + (level === "warn" || level === "danger" ? `<br><span class="dim">VirusTotal 이 켜져 있으면 서명이 유효하지 않은 이 파일의 해시를 물어봐요.</span>` : "");
    }
    ids.forEach((i) => $("#" + i).addEventListener("input", draw)); draw();
  })();
});
