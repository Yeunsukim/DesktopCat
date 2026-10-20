/* 데스크탑 고양이 문서 사이트 공통 동작: 마스코트, 목차, 진행 막대, 단계 상자, 코드 상자, 검색, 체크리스트 */
(function () {
  "use strict";
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
  const NS = "http://www.w3.org/2000/svg";
  window.DocUtil = { $, $$, NS };

  /* ---------- 마스코트: 앱의 고양이 비서 얼굴(cute.draw_cat_face)을 SVG 로 옮긴 것 ---------- */
  const PINK = "#F67499", PINK_D = "#E5557E", PINK_L = "#EF99B1", INK = "#5A3A47";
  const SAY = ["Huh!?", "냐옹~", "쥐다!", "잡았다옹!", "후아암~", "밥 줘라옹~", "쓰다듬어 달라냥", "문서 읽는 중이다냥"];
  const mascots = [];

  function mascotSVG(uid) {
    // 좌표는 앱과 같은 단위(반지름 1). 위쪽 귀 끝이 -1.0 이라 viewBox 를 위로 조금 넓힌다.
    return `<svg viewBox="-1.12 -1.2 2.24 2.28" xmlns="${NS}" class="mascot-svg" role="img" aria-label="고양이 비서">
  <defs><clipPath id="clip-${uid}"><circle cx="0" cy="0" r="1"/></clipPath></defs>
  <g class="m-bob">
    <circle r="1" fill="${PINK}"/>
    <g clip-path="url(#clip-${uid})"><g class="m-body">
      <rect x="-.62" y=".50" width="1.24" height=".9" rx=".35" fill="${INK}" stroke="${INK}" stroke-width=".075" stroke-linejoin="round"/>
      <circle cx="-.60" cy=".56" r=".15" fill="#fff" stroke="${INK}" stroke-width=".075"/><circle cx=".60" cy=".56" r=".15" fill="#fff" stroke="${INK}" stroke-width=".075"/>
    </g></g>
    <g class="m-head">
      <g class="m-ear-l"><path d="M-.60 -.22 L-.52 -1.0 L-.12 -.52 Z" fill="#fff" stroke="${INK}" stroke-width=".075" stroke-linejoin="round"/><path d="M-.50 -.36 L-.46 -.78 L-.24 -.50 Z" fill="${PINK_L}"/></g>
      <g class="m-ear-r"><path d="M.60 -.22 L.52 -1.0 L.12 -.52 Z" fill="#fff" stroke="${INK}" stroke-width=".075" stroke-linejoin="round"/><path d="M.50 -.36 L.46 -.78 L.24 -.50 Z" fill="${PINK_L}"/></g>
      <ellipse cx="0" cy="-.04" rx=".66" ry=".52" fill="#fff" stroke="${INK}" stroke-width=".075"/>
      <ellipse cx="-.40" cy=".09" rx=".11" ry=".065" fill="${PINK_L}" opacity=".75"/><ellipse cx=".40" cy=".09" rx=".11" ry=".065" fill="${PINK_L}" opacity=".75"/>
      <g class="m-eyes-open">
        <g class="m-pupils"><ellipse cx="-.26" cy="-.07" rx=".065" ry=".085" fill="${INK}"/><circle cx="-.24" cy="-.10" r=".02" fill="#fff"/><ellipse cx=".26" cy="-.07" rx=".065" ry=".085" fill="${INK}"/><circle cx=".28" cy="-.10" r=".02" fill="#fff"/></g>
      </g>
      <g class="m-eyes-happy" style="display:none" fill="none" stroke="${INK}" stroke-width=".07" stroke-linecap="round"><path d="M-.36 -.02 Q-.26 -.19 -.16 -.02"/><path d="M.16 -.02 Q.26 -.19 .36 -.02"/></g>
      <g class="m-eyes-shut" style="display:none" stroke="${INK}" stroke-width=".07" stroke-linecap="round"><path d="M-.36 -.05 L-.16 -.05"/><path d="M.16 -.05 L.36 -.05"/></g>
      <path d="M-.045 .045 L.045 .045 L0 .095 Z" fill="${PINK_D}"/>
      <g class="m-mouth-smile" fill="none" stroke="${INK}" stroke-width=".055" stroke-linecap="round"><path d="M0 .095 L0 .14 M-.11 .14 Q-.055 .215 0 .14 Q.055 .215 .11 .14"/></g>
      <ellipse class="m-mouth-open" cx="0" cy=".20" rx=".07" ry=".06" fill="${PINK_D}" stroke="${INK}" stroke-width=".055" style="display:none"/>
      <g stroke="${INK}" stroke-width=".035" stroke-linecap="round"><path d="M-.56 .07 L-.80 -.03 M-.56 .15 L-.80 .25 M.56 .07 L.80 -.03 M.56 .15 L.80 .25"/></g>
    </g>
  </g></svg>`;
  }

  let uidN = 0;
  function mountMascot(host) {
    const uid = "m" + (++uidN);
    host.innerHTML = mascotSVG(uid);
    const svg = host.firstElementChild;
    const m = {
      host, svg, mood: host.dataset.mood || "normal", t: Math.random() * 3, talkUntil: 0, look: [0, 0],
      bubble: null, bubbleUntil: 0, say(txt, secs = 2.2) {
        if (!this.bubble) { return; }
        this.bubble.textContent = txt; this.bubble.style.opacity = 1; this.bubbleUntil = performance.now() + secs * 1000; this.talkUntil = this.bubbleUntil;
      }
    };
    if (host.dataset.bubble !== undefined) {
      const b = document.createElement("div"); b.className = "bubble mascot-bubble"; b.textContent = host.dataset.bubble || SAY[0];
      b.style.cssText = "position:absolute;left:-6%;top:-6%;opacity:0;transition:opacity .3s;white-space:nowrap";
      if (getComputedStyle(host).position === "static") { host.style.position = "relative"; } host.appendChild(b); m.bubble = b;
      if (host.dataset.bubble) { setTimeout(() => m.say(host.dataset.bubble, 3), 900); }
    }
    host.addEventListener("click", () => { const w = SAY[Math.floor(Math.random() * SAY.length)]; m.say(w); });
    host.addEventListener("mouseenter", () => { m.talkUntil = performance.now() + 700; });
    m.q = (s) => svg.querySelector(s);
    m.els = { bob: m.q(".m-bob"), earR: m.q(".m-ear-r"), open: m.q(".m-eyes-open"), happy: m.q(".m-eyes-happy"), shut: m.q(".m-eyes-shut"), pup: m.q(".m-pupils"),
      smile: m.q(".m-mouth-smile"), mouth: m.q(".m-mouth-open"), body: m.q(".m-body"), head: m.q(".m-head") };
    mascots.push(m);
    return m;
  }
  let mouse = [window.innerWidth / 2, window.innerHeight / 2];
  window.addEventListener("pointermove", (e) => { mouse = [e.clientX, e.clientY]; }, { passive: true });
  function tick(ts) {
    const now = ts || performance.now();
    for (const m of mascots) {
      const r = m.svg.getBoundingClientRect();
      if (r.bottom < -50 || r.top > innerHeight + 50) { continue; }
      m.t = now / 1000;
      const t = m.t, E = m.els;
      const bob = Math.sin(t * 2.2) * 0.025;
      E.bob.setAttribute("transform", `translate(0 ${bob})`);
      const ph = t % 5, tw = ph < 0.35 ? Math.sin(ph / 0.35 * Math.PI) * 0.09 : 0;
      E.earR.setAttribute("transform", `translate(0 ${-tw})`);
      // 눈이 마우스를 따라간다
      const cx = r.left + r.width / 2, cy = r.top + r.height * 0.45;
      let dx = mouse[0] - cx, dy = mouse[1] - cy; const d = Math.hypot(dx, dy) || 1; const k = Math.min(1, d / 260);
      m.look[0] += ((dx / d) * 0.055 * k - m.look[0]) * 0.18; m.look[1] += ((dy / d) * 0.04 * k - m.look[1]) * 0.18;
      E.pup.setAttribute("transform", `translate(${m.look[0]} ${m.look[1]})`);
      const talking = now < m.talkUntil;
      const blink = (t % 3.6) > 3.48;
      const mood = talking ? "talk" : m.mood;
      E.happy.style.display = mood === "happy" ? "" : "none";
      E.shut.style.display = (mood === "sleep" || (blink && mood !== "happy")) ? "" : "none";
      E.open.style.display = (mood === "happy" || mood === "sleep" || blink) ? "none" : "";
      E.mouth.style.display = mood === "talk" ? "" : "none";
      E.smile.style.display = mood === "talk" ? "none" : "";
      if (mood === "talk") { const o = 0.5 + 0.5 * Math.sin(t * 9); E.mouth.setAttribute("rx", 0.06 + 0.02 * o); E.mouth.setAttribute("ry", 0.035 + 0.05 * o); }
      if (m.bubble && m.bubbleUntil && now > m.bubbleUntil) { m.bubble.style.opacity = 0; m.bubbleUntil = 0; }
    }
    requestAnimationFrame(tick);
  }
  window.DocUtil.mountMascot = mountMascot;

  /* ---------- 작은 그림 부품 (발자국·생선·털실·쥐·별) ---------- */
  const DECO = {
    paw: (c = PINK) => `<svg viewBox="0 0 64 64" width="100%"><g fill="${c}" stroke="${INK}" stroke-width="3" stroke-linejoin="round"><ellipse cx="32" cy="42" rx="15" ry="12"/><ellipse cx="14" cy="26" rx="6" ry="8"/><ellipse cx="26" cy="16" rx="6" ry="8.5"/><ellipse cx="38" cy="16" rx="6" ry="8.5"/><ellipse cx="50" cy="26" rx="6" ry="8"/></g></svg>`,
    fish: (c = "#8FD3F4") => `<svg viewBox="0 0 80 48" width="100%"><g stroke="${INK}" stroke-width="3" stroke-linejoin="round" fill="${c}"><path d="M8 24 Q26 4 52 14 L72 4 L68 24 L72 44 L52 34 Q26 44 8 24Z"/></g><circle cx="22" cy="21" r="3" fill="${INK}"/><path d="M36 14 Q40 24 36 34" fill="none" stroke="${INK}" stroke-width="2.5"/></svg>`,
    yarn: (c = PINK_L) => `<svg viewBox="0 0 64 64" width="100%"><circle cx="32" cy="32" r="22" fill="${c}" stroke="${INK}" stroke-width="3"/><path d="M14 26 Q32 40 50 22 M12 38 Q32 52 52 36 M22 14 Q40 30 30 54" fill="none" stroke="${INK}" stroke-width="2.5" stroke-linecap="round"/><path d="M50 46 Q62 52 56 62" fill="none" stroke="${INK}" stroke-width="3" stroke-linecap="round"/></svg>`,
    mouse: (c = "#EEE") => `<svg viewBox="0 0 80 50" width="100%"><g stroke="${INK}" stroke-width="3" stroke-linejoin="round"><circle cx="20" cy="12" r="9" fill="${PINK_L}"/><ellipse cx="40" cy="30" rx="26" ry="15" fill="${c}"/></g><circle cx="58" cy="26" r="2.6" fill="${INK}"/><circle cx="66" cy="31" r="2.6" fill="${PINK_D}"/><path d="M14 36 Q0 38 4 46" fill="none" stroke="${INK}" stroke-width="3" stroke-linecap="round"/></svg>`,
    star: (c = "#FFE08A") => `<svg viewBox="0 0 64 64" width="100%"><path d="M32 4 L39 24 L60 25 L43 38 L49 59 L32 47 L15 59 L21 38 L4 25 L25 24Z" fill="${c}" stroke="${INK}" stroke-width="3" stroke-linejoin="round"/></svg>`,
    bone: () => `<svg viewBox="0 0 80 40" width="100%"><g fill="#fff" stroke="${INK}" stroke-width="3" stroke-linejoin="round"><path d="M18 12 A9 9 0 1 0 14 24 L66 24 A9 9 0 1 0 62 12Z"/></g></svg>`,
    shield: (c = PINK) => `<svg viewBox="0 0 64 64" width="100%"><path d="M32 5 L55 13 V30 C55 45 44 55 32 60 C20 55 9 45 9 30 V13Z" fill="${c}" stroke="${INK}" stroke-width="3.4" stroke-linejoin="round"/><path d="M21 32 L29 40 L44 22" fill="none" stroke="#fff" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/></svg>`,
  };
  window.DocUtil.DECO = DECO;
  function mountDeco() {
    $$("[data-deco]").forEach((el) => {
      const [kind, color] = el.dataset.deco.split(":");
      if (DECO[kind]) { el.innerHTML = DECO[kind](color || undefined); }
    });
  }

  /* ---------- 코드 상자 ---------- */
  function highlight(text, lang) {
    const esc = (s) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    if (lang === "json") {
      return esc(text).replace(/("(?:[^"\\]|\\.)*")(\s*:)?|\b(true|false|null)\b|(-?\d+\.?\d*)/g, (m, s, colon, kw, num) => s ? (colon ? `<span class="k">${s}</span>${colon}` : `<span class="s">${s}</span>`) : kw ? `<span class="k">${kw}</span>` : `<span class="n">${num}</span>`);
    }
    if (lang === "py" || lang === "js") {
      const kw = lang === "py"
        ? "def|class|return|if|elif|else|for|while|in|not|and|or|import|from|as|with|try|except|finally|raise|yield|lambda|None|True|False|self|pass|break|continue|global|nonlocal|is"
        : "function|const|let|var|return|if|else|for|while|of|in|new|class|this|null|true|false|async|await|try|catch|throw";
      const re = new RegExp(`(#.*$|//.*$)|("""[\\s\\S]*?"""|'''[\\s\\S]*?'''|"(?:[^"\\\\\\n]|\\\\.)*"|'(?:[^'\\\\\\n]|\\\\.)*')|\\b(${kw})\\b|\\b(\\d+\\.?\\d*)\\b`, "gm");
      return esc(text).replace(re, (m, c, s, k, n) => c ? `<span class="c">${c}</span>` : s ? `<span class="s">${s}</span>` : k ? `<span class="k">${k}</span>` : `<span class="n">${n}</span>`);
    }
    return esc(text);
  }
  function mountCode() {
    $$(".code").forEach((box) => {
      if (box.dataset.done) { return; } box.dataset.done = 1;
      const pre = $("pre", box); const lang = box.dataset.lang || "";
      const raw = pre.textContent.replace(/^\n/, "").replace(/\s+$/, "");
      pre.innerHTML = "<code>" + highlight(raw, lang) + "</code>";
      const head = document.createElement("header");
      head.innerHTML = `<span>${box.dataset.file || (lang ? lang.toUpperCase() : "코드")}</span>`;
      const btn = document.createElement("button"); btn.textContent = "복사";
      btn.onclick = () => { navigator.clipboard && navigator.clipboard.writeText(raw).then(() => { btn.textContent = "복사됨!"; setTimeout(() => (btn.textContent = "복사"), 1400); }); };
      head.appendChild(btn); box.insertBefore(head, pre);
    });
  }

  /* ---------- 단계 상자(stepper) ---------- */
  function mountSteppers() {
    $$(".stepper").forEach((st) => {
      if (st.dataset.done) { return; } st.dataset.done = 1;
      const steps = $$(":scope > .step", st); steps.forEach((s) => (s.style.display = "none"));
      const head = document.createElement("div"); head.className = "head";
      const body = document.createElement("div"); body.className = "body";
      st.prepend(body); st.prepend(head);
      let cur = 0, timer = null;
      const prev = btn("◀ 이전"), play = btn("▶ 자동 재생"), next = btn("다음 ▶");
      const dots = steps.map((_, i) => { const d = document.createElement("button"); d.className = "step-dot"; d.textContent = i + 1; d.title = steps[i].dataset.title || ""; d.onclick = () => go(i); return d; });
      head.append(prev, ...dots, play, next);
      function btn(t) { const b = document.createElement("button"); b.className = "btn"; b.textContent = t; return b; }
      function go(i) {
        cur = (i + steps.length) % steps.length;
        dots.forEach((d, j) => { d.classList.toggle("on", j === cur); d.classList.toggle("done", j < cur); });
        const s = steps[cur]; body.innerHTML = `<div><h4>${cur + 1}. ${s.dataset.title || ""}</h4>${s.innerHTML}</div>`;
        st.dispatchEvent(new CustomEvent("stepchange", { detail: { index: cur, el: s } }));
      }
      prev.onclick = () => go(cur - 1); next.onclick = () => go(cur + 1);
      play.onclick = () => { if (timer) { clearInterval(timer); timer = null; play.textContent = "▶ 자동 재생"; play.classList.remove("on"); } else { play.textContent = "❚❚ 멈춤"; play.classList.add("on"); timer = setInterval(() => go(cur + 1), +(st.dataset.auto || 3200)); } };
      go(0);
    });
  }

  /* ---------- 목차·스크롤 ---------- */
  function mountToc() {
    const toc = $(".toc"); if (!toc) { return; }
    const panels = $$("main.doc > .panel[id]");
    const list = document.createElement("div");
    panels.forEach((p, i) => {
      const a = document.createElement("a"); a.href = "#" + p.id;
      const num = p.dataset.num || String(i + 1).padStart(2, "0");
      a.innerHTML = `<b>${num}</b><span>${p.dataset.toc || $("h2", p).textContent}</span>`; a.dataset.id = p.id; list.appendChild(a);
      if (!p.querySelector(":scope > .bg-num")) { const n = document.createElement("div"); n.className = "bg-num"; n.textContent = num; p.prepend(n); }
    });
    toc.appendChild(list);
    const links = $$("a", list);
    const io = new IntersectionObserver((es) => {
      es.forEach((e) => { if (e.isIntersecting) { links.forEach((l) => l.classList.toggle("on", l.dataset.id === e.target.id)); } });
    }, { rootMargin: "-20% 0px -70% 0px" });
    panels.forEach((p) => io.observe(p));
    const bar = $(".progress");
    const upd = () => { const h = document.documentElement; const max = h.scrollHeight - innerHeight; if (bar) { bar.style.width = (max > 0 ? (scrollY / max) * 100 : 0) + "%"; } };
    addEventListener("scroll", upd, { passive: true }); upd();
    const burger = $(".burger");
    if (burger) { burger.onclick = () => { burger.classList.toggle("open"); toc.classList.toggle("open"); }; links.forEach((l) => l.addEventListener("click", () => { burger.classList.remove("open"); toc.classList.remove("open"); })); }
    const q = $(".search", toc);
    if (q) { q.addEventListener("input", () => { const s = q.value.trim().toLowerCase(); links.forEach((l) => { const p = document.getElementById(l.dataset.id); l.style.display = !s || (p && p.textContent.toLowerCase().includes(s)) ? "" : "none"; }); }); }
  }
  function mountReveal() {
    const io = new IntersectionObserver((es) => es.forEach((e) => { if (e.isIntersecting) { e.target.classList.add("in"); io.unobserve(e.target); } }), { threshold: 0.06 });
    $$(".reveal").forEach((el) => io.observe(el));
  }

  /* ---------- 표 걸러 보기 ---------- */
  function mountFilters() {
    $$("input[data-filter]").forEach((inp) => {
      const t = document.querySelector(inp.dataset.filter); if (!t) { return; }
      inp.addEventListener("input", () => { const s = inp.value.trim().toLowerCase(); $$("tbody tr", t).forEach((tr) => { tr.style.display = !s || tr.textContent.toLowerCase().includes(s) ? "" : "none"; }); });
    });
  }

  /* ---------- 체크리스트(브라우저에 기억) ---------- */
  function mountChecklists() {
    $$(".checklist").forEach((ul) => {
      const key = "doccat:" + location.pathname + ":" + (ul.id || "list");
      let saved = []; try { saved = JSON.parse(localStorage.getItem(key) || "[]"); } catch (e) { /* 저장 못 해도 동작은 한다 */ }
      const items = $$("li", ul); const meter = ul.parentElement.querySelector(".meter i"); const label = ul.parentElement.querySelector(".meter-label");
      const upd = () => { const n = items.filter((li) => li.querySelector("input").checked).length; if (meter) { meter.style.width = (n / items.length * 100) + "%"; } if (label) { label.textContent = `${n} / ${items.length} 완료`; } try { localStorage.setItem(key, JSON.stringify(items.map((li, i) => li.querySelector("input").checked ? i : -1).filter((i) => i >= 0))); } catch (e) { /* 무시 */ } };
      items.forEach((li, i) => { const cb = li.querySelector("input"); cb.checked = saved.includes(i); li.classList.toggle("done", cb.checked); li.addEventListener("click", (e) => { if (e.target !== cb) { cb.checked = !cb.checked; } li.classList.toggle("done", cb.checked); upd(); }); });
      upd();
    });
  }

  document.addEventListener("DOMContentLoaded", () => {
    $$(".mascot").forEach(mountMascot); mountDeco(); mountCode(); mountSteppers(); mountToc(); mountReveal(); mountFilters(); mountChecklists();
    requestAnimationFrame(tick);
    if (window.PageInit) { window.PageInit(); }
    (window.PageInits || []).forEach((f) => { try { f(); } catch (e) { console.error(e); } });
    // 주소에 ?at=섹션id 를 붙이면 그 섹션으로 바로 이동하고 모든 섹션을 펼쳐 둔다 (화면 캡처·공유용)
    const only = new URLSearchParams(location.search).get("only");               // ?only=섹션id : 그 섹션만 보여 준다 (화면 캡처용)
    if (only) { $$("main.doc > .panel, main.doc > .hero").forEach((e) => { if (e.id !== only) { e.style.display = "none"; } else { e.classList.add("in"); } }); }
    const at = new URLSearchParams(location.search).get("at");
    if (at) { $$(".reveal").forEach((e) => e.classList.add("in")); const t = document.getElementById(at); if (t) { setTimeout(() => t.scrollIntoView({ behavior: "instant" }), 120); } }
  });
})();
