/* Shared helpers: chrome, theme, formatting, SVG, tooltip, raw links. No dependencies. */
(function () {
  "use strict";
  var BVH = (window.BVH = {});
  var SVGNS = "http://www.w3.org/2000/svg";

  /* ---------- theme ---------- */
  function getStored() { try { return localStorage.getItem("bvh-theme"); } catch (e) { return null; } }
  function setStored(v) { try { localStorage.setItem("bvh-theme", v); } catch (e) { /* private mode */ } }
  BVH.theme = function () {
    var t = document.documentElement.getAttribute("data-theme");
    if (t) return t;
    return window.matchMedia && matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  };
  (function init() { var s = getStored(); if (s === "light" || s === "dark") document.documentElement.setAttribute("data-theme", s); })();
  BVH.onTheme = []; // callbacks for canvas redraws

  /* ---------- chrome ---------- */
  var NAV = [["index.html", "The story"], ["index.html#table", "Every race"], ["explainer.html", "How bots work"], ["evolution.html", "Has it evolved?"], ["methods.html", "Methods and data"], ["paper.html", "Paper"]];
  BVH.chrome = function (active) {
    var skip = document.createElement("a");
    skip.className = "skip"; skip.href = "#main"; skip.textContent = "Skip to content";
    document.body.insertBefore(skip, document.body.firstChild);
    var h = document.createElement("header");
    h.className = "top";
    var links = NAV.map(function (n) {
      var cur = n[0] === active ? ' aria-current="page"' : "";
      return '<a href="' + n[0] + '"' + cur + ">" + n[1] + "</a>";
    }).join("");
    h.innerHTML = '<div class="top-in"><a class="brand" href="index.html"><i></i>The Bot Beat the Hacker</a><button class="menubtn" type="button" id="menubtn" aria-expanded="false" aria-controls="topmenu"><span aria-hidden="true" class="bars"></span>menu</button><div class="topmenu" id="topmenu"><nav aria-label="Main">' + links + '</nav><button class="theme" type="button" id="themebtn" aria-label="Switch between light and dark mode">theme</button></div></div>';
    document.body.insertBefore(h, skip.nextSibling);
    /* phones: the nav and theme switch fold into a menu button (see .menubtn in style.css) */
    var mb = h.querySelector("#menubtn");
    function setMenu(open, refocus) { h.classList.toggle("open", open); mb.setAttribute("aria-expanded", open ? "true" : "false"); if (!open && refocus) mb.focus(); }
    mb.addEventListener("click", function () { setMenu(mb.getAttribute("aria-expanded") !== "true"); });
    h.addEventListener("keydown", function (e) { if ((e.key === "Escape" || e.key === "Esc") && h.classList.contains("open")) { setMenu(false, true); } });
    h.querySelector("nav").addEventListener("click", function (e) { if (e.target.closest && e.target.closest("a")) setMenu(false); });
    document.addEventListener("click", function (e) { if (h.classList.contains("open") && !h.contains(e.target)) setMenu(false); });
    var btn = h.querySelector("#themebtn");
    function label() { btn.textContent = BVH.theme() === "dark" ? "light mode" : "dark mode"; }
    label();
    btn.addEventListener("click", function () {
      var n = BVH.theme() === "dark" ? "light" : "dark";
      document.documentElement.setAttribute("data-theme", n); setStored(n); label();
      BVH.onTheme.forEach(function (f) { try { f(); } catch (e) { /* ignore */ } });
    });
    var f = document.createElement("footer");
    f.className = "foot";
    f.innerHTML = '<div class="wrap"><p>Every number on this site links to the saved response it came from (small <a class="raw" href="methods.html#raw">raw</a> tags). Where a value is derived, the link goes to the response it was derived from.</p>' +
      '<p>Yoink\'s executor is decoded from its on-chain code (<a href="explainer.html">How bots work</a>). Other operators, including c0ffeebabe.eth, appear through their public transactions.</p>' +
      '<p>Compiled with a swarm of AI agents, so there will be mistakes; every number links its saved source; <a href="https://github.com/DicksonWu654/bot-vs-hacker/issues">corrections welcome</a>.</p>' +
      '<p><a href="paper.html">Paper</a> &nbsp; <a href="methods.html">Methods and data</a> &nbsp; <a href="data/incidents.json">incidents.json</a></p></div>';
    document.body.appendChild(f);
  };

  /* ---------- data ---------- */
  BVH.json = function (p) {
    return fetch(p, { cache: "no-cache" }).then(function (r) { if (!r.ok) throw new Error(p + " -> HTTP " + r.status); return r.json(); });
  };

  /* ---------- formatting ---------- */
  BVH.esc = function (s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); };
  BVH.eth = function (x, unit) {
    if (x == null || isNaN(x)) return "n/a";
    var a = Math.abs(x), s;
    if (a >= 1000) s = x.toLocaleString("en-US", { maximumFractionDigits: 1 });
    else if (a >= 100) s = x.toFixed(1);
    else if (a >= 10) s = x.toFixed(2);
    else if (a >= 1) s = x.toFixed(3);
    else if (a >= 0.01) s = x.toFixed(4);
    else s = x.toPrecision(2);
    return s + (unit === false ? "" : " ETH");
  };
  BVH.sec = function (ms, signed) {
    if (ms == null) return "n/a";
    var s = ms / 1000, sign = signed && ms > 0 ? "+" : ms < 0 ? "−" : "";
    var a = Math.abs(s);
    return sign + (a >= 100 ? a.toFixed(0) : a >= 10 ? a.toFixed(2) : a.toFixed(3)) + " s";
  };
  BVH.dur = function (ms) {
    if (ms == null) return "n/a";
    if (ms < 1000) return Math.round(ms) + " ms";
    if (ms < 120000) return (ms / 1000).toFixed(ms < 10000 ? 3 : 1) + " s";
    return Math.round(ms / 60000) + " min";
  };
  function p2(n, w) { n = String(n); while (n.length < (w || 2)) n = "0" + n; return n; }
  BVH.clock = function (ms, withMs) {
    var d = new Date(ms);
    return p2(d.getUTCHours()) + ":" + p2(d.getUTCMinutes()) + ":" + p2(d.getUTCSeconds()) + (withMs === false ? "" : "." + p2(d.getUTCMilliseconds(), 3));
  };
  BVH.utc = function (ms) { var d = new Date(ms); return d.toISOString().slice(0, 10) + " " + BVH.clock(ms) + " UTC"; };
  BVH.dateLong = function (iso) { var d = new Date(iso + "T00:00:00Z"); return d.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" }); };
  BVH.short = function (h, a, b) { h = h || ""; a = a || 8; b = b || 4; return h.length > a + b + 2 ? h.slice(0, a) + "…" + h.slice(-b) : h; };
  BVH.pct = function (x, d) { return x == null ? "n/a" : x.toFixed(d == null ? (x >= 99 || x < 1 ? 2 : 1) : d) + "%"; };

  /* ---------- raw links ---------- */
  BVH.rawA = function (url, text, title) {
    if (!url) return '<span class="raw-none" title="No single saved response backs this value (it is derived, or the source was not archived).">no raw</span>';
    return '<a class="raw" href="' + BVH.esc(url) + '" title="' + BVH.esc(title || "Saved raw response") + '" target="_blank" rel="noopener">' + (text || "raw") + "</a>";
  };
  /* several saved responses back one value: link every one, numbered */
  BVH.derivedTxt = function (e) {
    if (!e || !e.derived || !e.derived.length) return "";
    return e.derived.map(function (d) { return '<br><span class="muted">derived: ' + BVH.esc(d.shown) + " = " + BVH.esc(d.how) + "</span>"; }).join("");
  };
  BVH.rawAs = function (urls, text, title) {
    urls = (urls || []).filter(Boolean);
    if (!urls.length) return BVH.rawA(null);
    return urls.map(function (u, i) { return BVH.rawA(u, urls.length > 1 ? (text || "raw") + " " + (i + 1) : text, title); }).join(" ");
  };
  /* the relay bid files behind a bid total / chart / ledger: one link per relay that returned bids */
  BVH.bidsA = function (A, title) {
    var all = (A && A.raw && A.raw.bids_all) || [];
    title = title || "A relay's saved builder_blocks_received response for this slot. Totals, chart and ledger are drawn from all relay files linked here.";
    if (!all.length) return BVH.rawA(A && A.raw && A.raw.bids, "raw bids", title);
    return '<span class="raw-bids">' + all.map(function (a) { return BVH.rawA(a.url, all.length > 1 ? "raw bids (" + a.relay + ")" : "raw bids", title); }).join(" ") + "</span>";
  };
  /* mempool first-seen: the day file's rows (when the tx is in them) and the per-source log */
  BVH.memA = function (raw) {
    raw = raw || {};
    if (!raw.csv && !raw.sourcelog) return BVH.rawA(null);
    return (raw.csv ? BVH.rawA(raw.csv, "raw rows", "Verbatim mempool-dumpster rows for this tx") : "") + (raw.sourcelog ? BVH.rawA(raw.sourcelog, "per-source log", "Verbatim per-source first-seen rows for this tx") : "");
  };
  BVH.explorer = function (h) { return '<a class="raw" href="https://etherscan.io/tx/' + h + '" target="_blank" rel="noopener" title="Open on Etherscan (external)">scan</a>'; };

  /* ---------- svg ---------- */
  BVH.svg = function (tag, attrs, parent, text) {
    var e = document.createElementNS(SVGNS, tag);
    if (attrs) for (var k in attrs) if (attrs[k] != null) e.setAttribute(k, attrs[k]);
    if (text != null) e.textContent = text;
    if (parent) parent.appendChild(e);
    return e;
  };
  BVH.lin = function (d0, d1, r0, r1) { var f = function (v) { return r0 + (v - d0) * (r1 - r0) / (d1 - d0); }; f.inv = function (p) { return d0 + (p - r0) * (d1 - d0) / (r1 - r0); }; return f; };
  BVH.log = function (d0, d1, r0, r1) {
    var l0 = Math.log10(d0), l1 = Math.log10(d1);
    var f = function (v) { return r0 + (Math.log10(Math.max(v, d0)) - l0) * (r1 - r0) / (l1 - l0); };
    return f;
  };
  BVH.logTicks = function (d0, d1) { var t = [], e0 = Math.ceil(Math.log10(d0)), e1 = Math.floor(Math.log10(d1)); for (var e = e0; e <= e1; e++) t.push(Math.pow(10, e)); return t; };
  BVH.reduced = function () { return window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches; };
  BVH.cssVar = function (n) { return getComputedStyle(document.documentElement).getPropertyValue(n).trim(); };

  /* ---------- tooltip ---------- */
  var tip;
  function ensureTip() { if (!tip) { tip = document.createElement("div"); tip.className = "tip"; tip.setAttribute("role", "tooltip"); document.body.appendChild(tip); } return tip; }
  BVH.tipShow = function (html, x, y) {
    var t = ensureTip(); t.innerHTML = html; t.classList.add("on");
    var w = t.offsetWidth, h = t.offsetHeight;
    var left = Math.min(Math.max(8, x + 14), window.innerWidth - w - 8);
    var top = y + 16 + h > window.innerHeight ? y - h - 12 : y + 16;
    t.style.left = left + "px"; t.style.top = Math.max(8, top) + "px";
  };
  BVH.tipHide = function () { if (tip) tip.classList.remove("on"); };
  BVH.tipFor = function (el, htmlFn, onSelect) {
    function at(ev) { var r = el.getBoundingClientRect(); return ev && ev.clientX != null && ev.type !== "focus" ? [ev.clientX, ev.clientY] : [r.left + r.width / 2, r.top + r.height / 2]; }
    el.addEventListener("mousemove", function (e) { var p = at(e); BVH.tipShow(htmlFn(), p[0], p[1]); });
    el.addEventListener("mouseleave", BVH.tipHide);
    el.addEventListener("focus", function (e) { var p = at(e); BVH.tipShow(htmlFn(), p[0], p[1]); });
    el.addEventListener("blur", BVH.tipHide);
    if (onSelect) {
      el.addEventListener("click", function () { onSelect(); });
      el.addEventListener("keydown", function (e) { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onSelect(); } });
    }
  };

  /* ---------- misc ---------- */
  BVH.qs = function (k) { return new URLSearchParams(location.search).get(k); };
  BVH.slugify = function (s) { return String(s || "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, ""); };
  BVH.RT = {
    "beat-pending-attack": { name: "Beat a pending attack", def: "The bot landed before a pending or in-flight attacker transaction, replaying or adapting it." },
    "deploy-window-copy": { name: "Used the attacker's setup", def: "The bot used the attacker's on-chain setup (a deployed contract or a prepare() call) before the attacker's own call." },
    "beat-whitehat-or-user": { name: "Copied a user or whitehat", def: "The bot copied a transaction sent by someone who was not a hacker: a user's withdrawal, or a whitehat's rescue." },
    "post-failure-replay": { name: "Replayed after a failure", def: "The attacker's transaction had already failed or landed; a bot or whitehat replayed it afterwards." },
    "bot-was-first-exploiter": { name: "The bot was first", def: "There was no separate attacker: the bot found the bug itself." },
    "late-copy": { name: "Late copy", def: "Copied after the attacker had already succeeded." },
    "no-race": { name: "No race", def: "Looked like a race, but the attacker acted alone and nothing copied or beat them. Rejected after checking." }
  };
  BVH.rtName = function (k) { return (BVH.RT[k] || { name: k || "n/a" }).name; };
  BVH.loadError = function (el, e) {
    el.innerHTML = '<div class="callout bad">Could not load the data (' + BVH.esc(e.message || e) + '). Serve the site over http, for example <code>python -m http.server</code> from the site folder, not from file://.</div>';
  };
})();
