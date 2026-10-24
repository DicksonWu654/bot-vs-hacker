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
    return t === "light" ? "light" : "dark";
  };
  /* night is the default on every page whatever the OS setting; "dawn" (light) only when the reader picked it */
  (function init() { var s = getStored(); document.documentElement.setAttribute("data-theme", s === "light" ? "light" : "dark"); })();
  BVH.onTheme = []; // callbacks for canvas redraws

  /* ---------- series (v2): three parts + the data & evidence layer ---------- */
  BVH.SERIES = [
    { part: 1, href: "race.html", title: "The race", blurb: "Makina, January 2026, second by second: a contract deployed, twelve seconds of bidding, and where 1,299 ETH went." },
    { part: 2, href: "explainer.html", title: "How the bot works", blurb: "How Yoink copied a Ronin bridge withdrawal, step by step: watch, simulate, swap the beneficiary, bid, get in first, pay out." },
    { part: 3, href: "evolution.html", title: "Has the dark forest changed?", blurb: "Sampled attacks often went unseen in public or ran during contract creation, narrowing the copying window." }
  ];
  BVH.DATA_LINKS = [["index.html#data", "Every race"], ["methods.html", "Methods"], ["paper.html", "Paper"], ["data/incidents.json", "Download the data"]];
  var DATA_PAGES = { "methods.html": 1, "paper.html": 1, "incident.html": 1, "index.html#table": 1, "index.html#data": 1 };
  function pageFile() { var f = (location.pathname.split("/").pop() || "index.html"); return f || "index.html"; }
  /* which part a page is: <body data-part="1|2|3|data">, else from the file name */
  BVH.partOf = function (file) {
    var b = document.body && document.body.getAttribute("data-part");
    if (b) return b === "data" ? "data" : +b;
    file = file || pageFile();
    for (var i = 0; i < BVH.SERIES.length; i++) if (BVH.SERIES[i].href === file) return BVH.SERIES[i].part;
    return DATA_PAGES[file] ? "data" : null;
  };
  /* "Part 2 of 3" kicker for a page top */
  BVH.seriesKicker = function (part) {
    var s = BVH.SERIES[(part || BVH.partOf()) - 1];
    if (!s) return "";
    return '<span class="sk-n">Part ' + s.part + ' of 3</span><span class="sk-t">The Bot Beat the Hacker</span>';
  };
  /* "More in this series": the other parts as optional reading (each part stands alone), plus the evidence layer.
     Auto-appended to <main> when the body declares data-part. Same signature as v2. */
  BVH.partNav = function (part) {
    part = part || BVH.partOf();
    var S = BVH.SERIES;
    function card(s) {
      return '<a class="pn-card pn-more" href="' + s.href + '"><span class="pn-dir"><b>Part ' + s.part + "</b> of the series</span><span class=\"pn-title\">" + s.title + '</span><span class="pn-blurb">' + s.blurb + "</span></a>";
    }
    if (part === "data") {
      /* data pages (methods, paper, race pages): all three parts, in order */
      return '<nav class="partnav" aria-label="Series"><p class="pn-head">Read the series</p><div class="pn-row pn-3">' + S.map(function (s) {
        return '<a class="pn-card" href="' + s.href + '"><span class="pn-dir">Part ' + s.part + '</span><span class="pn-title">' + s.title + '</span><span class="pn-blurb">' + s.blurb + "</span></a>";
      }).join("") + "</div></nav>";
    }
    var others = S.filter(function (s) { return s.part !== part; });
    return '<nav class="partnav" aria-label="More in this series"><h2 class="pn-more-h">More in this series</h2><div class="pn-row">' + others.map(card).join("") + "</div>" +
      '<p class="pn-data"><span>Data and evidence:</span> ' + BVH.DATA_LINKS.map(function (l) { return '<a href="' + l[0] + '">' + l[1] + "</a>"; }).join(" ") + ' <a href="index.html">The series home</a></p></nav>';
  };
  /* plain definitions for the terms the parts use; each part shows the ones it needs in a short primer */
  BVH.GLOSSARY = {
    block: ["Block", "A batch of transactions added to Ethereum about every 12 seconds. Inside a block, transactions run strictly in order."],
    slot: ["Slot", "The 12-second window in which one block is proposed. Times on this site count from the start of the slot."],
    builder: ["Block builder", "A company that assembles blocks from waiting transactions. Builders compete to have their block chosen, and pay the proposer for it."],
    proposer: ["Proposer", "The validator whose turn it is to add the next block. It takes the builder's block that pays it the most."],
    relay: ["Relay", "A go-between that passes builders' blocks to the proposer. Relays publish the bids they receive, which is how the auction can be replayed."],
    mempool: ["Public mempool", "The public waiting room for transactions that have been sent but are not yet in a block. Anyone can watch it."],
    "private-flow": ["Private order flow", "Sending a transaction straight to a builder instead of the public mempool, so nobody else sees it before it lands."],
    searcher: ["Searcher", "Someone who runs bots that look for profitable transactions to place, often paying builders to put them first."],
    position0: ["Position 0", "The first transaction in a block. It runs before everything else, so whoever holds it reaches the money first."],
    calldata: ["Calldata", "The instructions a transaction carries: which function to call, and with what values."],
    bribe: ["Payment to go first", "What a bot pays the block builder, directly or as a tip, to have its transaction placed where it wants, usually first."],
    constructor: ["Constructor", "Code that runs once, at the moment a contract is created. An attack that runs entirely inside it is over before anyone can see it waiting."],
    flashloan: ["Flash loan", "A loan taken and repaid inside a single transaction. It lets anyone move huge sums for one transaction without owning them."],
    whitehat: ["Whitehat", "Someone who uses an exploit to rescue funds and hand them back, rather than to steal them."],
    simulate: ["Simulate", "Run a transaction against a copy of the current chain to see what it would do, without sending it."],
    frontrun: ["Front-running bot", "Software that copies a transaction it has seen, puts itself in as the one who gets paid, and pays to go first."],
    attacker: ["Attacker", "The account behind the exploit transaction or setup that the bot beat. It is not always whoever found the bug first, so each race says who lost: the original attacker, probably the original attacker, or a later exploiter."],
    weth: ["WETH", "Wrapped ether: ETH held as a token, so contracts can trade it like any other token. Unwrapping turns it back into plain ETH."],
    safe: ["Safe", "A multisignature wallet: a contract that moves funds only when enough of its owners sign."]
  };
  /* BVH.primer(["mempool", "builder"] or [["Term", "definition"], ...], { title, intro }) -> <aside class="primer"> */
  BVH.primer = function (keys, o) {
    o = o || {};
    var items = (keys || []).map(function (k) { return typeof k === "string" ? BVH.GLOSSARY[k] : k; }).filter(Boolean);
    return '<aside class="primer" aria-label="' + BVH.esc(o.title || "What you need to know") + '"><h2 class="primer-h">' + BVH.esc(o.title || "What you need to know") + "</h2>" +
      (o.intro ? '<p class="primer-intro">' + o.intro + "</p>" : "") +
      "<dl>" + items.map(function (t) { return "<dt>" + BVH.esc(t[0]) + "</dt><dd>" + t[1] + "</dd>"; }).join("") + "</dl></aside>";
  };
  BVH.chrome = function (active) {
    var skip = document.createElement("a");
    skip.className = "skip"; skip.href = "#main"; skip.textContent = "Skip to content";
    document.body.insertBefore(skip, document.body.firstChild);
    var h = document.createElement("header");
    h.className = "top";
    var file = pageFile(), part = BVH.partOf(active && active !== "none" ? active.split("#")[0] : file);
    if (active === "index.html#table") part = "data";
    var links = BVH.SERIES.map(function (s) {
      var cur = part === s.part ? ' aria-current="page"' : "";
      return '<a href="' + s.href + '"' + cur + '><span class="nv-n" aria-hidden="true">' + s.part + '</span><span class="nv-t"><span class="sr">Part ' + s.part + ': </span>' + s.title + "</span></a>";
    }).join("") + '<a class="nv-data" href="index.html#data"' + (part === "data" ? ' aria-current="page"' : "") + ">Data &amp; evidence</a>";
    h.innerHTML = '<div class="top-in"><a class="brand" href="index.html"><i></i>The Bot Beat the Hacker</a><button class="menubtn" type="button" id="menubtn" aria-expanded="false" aria-controls="topmenu"><span aria-hidden="true" class="bars"></span>menu</button><div class="topmenu" id="topmenu"><nav aria-label="Series">' + links + '</nav><button class="theme" type="button" id="themebtn" aria-label="Switch between the night and dawn colour themes"><i aria-hidden="true"></i><span>theme</span></button></div></div>';
    document.body.insertBefore(h, skip.nextSibling);
    BVH.glowDefs();
    /* kicker slots + the part footer */
    Array.prototype.forEach.call(document.querySelectorAll("[data-series-kicker]"), function (el) { el.innerHTML = BVH.seriesKicker(+el.getAttribute("data-series-kicker") || part); el.classList.add("series-kicker"); });
    var mainEl = document.getElementById("main"), slot = document.querySelector("[data-partnav-slot]");
    if (slot) slot.innerHTML = BVH.partNav(part);
    else if (mainEl && document.body.hasAttribute("data-part") && document.body.getAttribute("data-partnav") !== "manual" && !mainEl.querySelector(".partnav")) {
      var pnw = document.createElement("div"); pnw.className = "wrap"; pnw.innerHTML = BVH.partNav(part); mainEl.appendChild(pnw);
    }
    else if (mainEl && part === "data" && document.body.getAttribute("data-partnav") !== "manual") {
      /* after <main>, so pages that re-render their main content keep it */
      var pnd = document.createElement("div"); pnd.className = "wrap pn-after"; pnd.innerHTML = BVH.partNav("data");
      mainEl.parentNode.insertBefore(pnd, mainEl.nextSibling);
    }
    /* phones: the nav and theme switch fold into a menu button (see .menubtn in style.css) */
    var mb = h.querySelector("#menubtn");
    function setMenu(open, refocus) { h.classList.toggle("open", open); mb.setAttribute("aria-expanded", open ? "true" : "false"); if (!open && refocus) mb.focus(); }
    mb.addEventListener("click", function () { setMenu(mb.getAttribute("aria-expanded") !== "true"); });
    h.addEventListener("keydown", function (e) { if ((e.key === "Escape" || e.key === "Esc") && h.classList.contains("open")) { setMenu(false, true); } });
    h.querySelector("nav").addEventListener("click", function (e) { if (e.target.closest && e.target.closest("a")) setMenu(false); });
    document.addEventListener("click", function (e) { if (h.classList.contains("open") && !h.contains(e.target)) setMenu(false); });
    var btn = h.querySelector("#themebtn");
    function label() { btn.querySelector("span").textContent = BVH.theme() === "dark" ? "dawn" : "night"; btn.setAttribute("aria-pressed", BVH.theme() === "light" ? "true" : "false"); }
    label();
    btn.addEventListener("click", function () {
      var n = BVH.theme() === "dark" ? "light" : "dark";
      document.documentElement.setAttribute("data-theme", n); setStored(n); label();
      BVH.onTheme.forEach(function (f) { try { f(); } catch (e) { /* ignore */ } });
    });
    var f = document.createElement("footer");
    f.className = "foot";
    f.innerHTML = '<div class="wrap"><p>Every number on this site links to the saved response it came from (small <a class="raw" href="methods.html#raw">raw</a> tags). Where a value is derived, the link goes to the response it was derived from.</p>' +
      '<p>Yoink\'s executor is decoded from its on-chain code (<a href="explainer.html">How the bot works</a>). Other operators, including c0ffeebabe.eth, appear through their public transactions.</p>' +
      /* the launch pages (the hub and the three parts) end on the story; the data pages carry the full note */
      (part === "data" ? '<p>Compiled with a swarm of AI agents, so there will be mistakes; every number links its saved source; <a href="https://github.com/DicksonWu654/bot-vs-hacker/issues">corrections welcome</a>.</p>'
        : '<p>Found a mistake? <a href="https://github.com/DicksonWu654/bot-vs-hacker/issues">Corrections are welcome</a>; how the data was built is on the <a href="methods.html">methods page</a>.</p>') +
      '<p class="foot-links">' + BVH.SERIES.map(function (s) { return '<a href="' + s.href + '">Part ' + s.part + ": " + s.title + "</a>"; }).join(" ") + ' <a href="index.html#data">Every race</a> <a href="methods.html">Methods and data</a> <a href="paper.html">Paper</a> <a href="data/incidents.json">incidents.json</a></p></div>';
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
    /* every source marker reads as "Source" to assistive technology; the visible tag keeps its short text */
    var tt = title || "Saved raw response", vis = String(text || "raw").replace(/<[^>]*>/g, "");
    return '<a class="raw" href="' + BVH.esc(url) + '" title="' + BVH.esc(tt) + '" aria-label="' + BVH.esc("Source, " + vis + ": " + tt) + '" target="_blank" rel="noopener">' + (text || "raw") + "</a>";
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
  /* shared SVG filters for the "light in the dark" chart language: static glows, referenced from CSS as
     filter: url(#bvh-glow) (soft) or url(#bvh-glow-s) (tight). Dawn turns them off in CSS. Injected once per page. */
  BVH.glowDefs = function () {
    if (document.getElementById("bvh-fx")) return;
    var d = document.createElementNS(SVGNS, "svg");
    d.setAttribute("id", "bvh-fx"); d.setAttribute("aria-hidden", "true"); d.setAttribute("focusable", "false");
    d.setAttribute("style", "position:absolute;width:0;height:0;overflow:hidden");
    d.innerHTML = '<defs><filter id="bvh-glow" x="-50%" y="-50%" width="200%" height="200%" color-interpolation-filters="sRGB"><feGaussianBlur in="SourceGraphic" stdDeviation="3.2" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>' +
      '<filter id="bvh-glow-s" x="-50%" y="-50%" width="200%" height="200%" color-interpolation-filters="sRGB"><feGaussianBlur in="SourceGraphic" stdDeviation="1.6" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>' +
      /* light columns: fade from the floor up to the bid (fill a rect, not a zero-width line) */
      '<linearGradient id="bvh-col-a" x1="0" y1="1" x2="0" y2="0"><stop offset="0" style="stop-color:var(--bot);stop-opacity:.02"/><stop offset=".8" style="stop-color:var(--bot);stop-opacity:.14"/><stop offset="1" style="stop-color:var(--bot);stop-opacity:.5"/></linearGradient>' +
      '<linearGradient id="bvh-col-m" x1="0" y1="1" x2="0" y2="0"><stop offset="0" style="stop-color:var(--mist);stop-opacity:.03"/><stop offset=".8" style="stop-color:var(--mist);stop-opacity:.16"/><stop offset="1" style="stop-color:var(--mist);stop-opacity:.42"/></linearGradient>' +
      '<linearGradient id="bvh-refl" x1="0" y1="0" x2="0" y2="1"><stop offset="0" style="stop-color:var(--mist);stop-opacity:.3"/><stop offset="1" style="stop-color:var(--mist);stop-opacity:0"/></linearGradient>' +
      '<linearGradient id="bvh-refl-a" x1="0" y1="0" x2="0" y2="1"><stop offset="0" style="stop-color:var(--bot);stop-opacity:.5"/><stop offset="1" style="stop-color:var(--bot);stop-opacity:0"/></linearGradient></defs>';
    document.body.insertBefore(d, document.body.firstChild);
  };
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

  /* ---------- player: play / step / scrub over a value range (v2, shared) ----------
     BVH.player(container, { min, max, value?, stops: [{ t, label }], duration: ms for a full play, onChange(v, stopIndex),
       format(v) -> readout text, label: "aria name", autoplay: "inview" })
     Reduced motion: starts at max (the complete end state) and never moves unless the reader presses Play or steps.
     Returns { set(v), play(), pause(), value() }. */
  BVH.player = function (box, o) {
    o = o || {};
    var min = o.min || 0, max = o.max == null ? 1 : o.max, stops = (o.stops || []).slice().sort(function (a, b) { return a.t - b.t; });
    var reduced = BVH.reduced(), v = o.value != null ? o.value : (reduced ? max : (o.autoplay ? min : max)), raf = 0, playing = false, lastTs = 0;
    var uid = "pl" + Math.random().toString(36).slice(2, 8);
    box.classList.add("player-ctrl");
    box.innerHTML = '<button type="button" class="pl-play" aria-describedby="' + uid + '-r"><svg viewBox="0 0 16 16" aria-hidden="true"><path class="i-play" d="M4 2.5v11l9-5.5z"/><path class="i-pause" d="M3.5 2.5h3v11h-3zM9.5 2.5h3v11h-3z"/></svg><span>Play</span></button>' +
      '<button type="button" class="pl-step pl-prev" aria-label="Previous step"><svg viewBox="0 0 16 16" aria-hidden="true"><path d="M3 2.5h2v11H3zM14 2.5v11L6 8z"/></svg></button>' +
      '<button type="button" class="pl-step pl-next" aria-label="Next step"><svg viewBox="0 0 16 16" aria-hidden="true"><path d="M11 2.5h2v11h-2zM2 2.5v11L10 8z"/></svg></button>' +
      '<input type="range" class="pl-range" min="' + min + '" max="' + max + '" step="' + (o.step || (max - min) / 1000) + '" aria-label="' + BVH.esc(o.label || "Scrub through time") + '">' +
      '<output class="pl-read" id="' + uid + '-r" aria-live="off"></output>';
    var bp = box.querySelector(".pl-play"), bl = bp.querySelector("span"), rg = box.querySelector(".pl-range"), rd = box.querySelector(".pl-read");
    function stopIdx(x) { var k = -1; for (var i = 0; i < stops.length; i++) if (stops[i].t <= x + 1e-9) k = i; return k; }
    function render() {
      rg.value = v; var k = stopIdx(v);
      rd.textContent = o.format ? o.format(v, k) : String(v);
      bl.textContent = playing ? "Pause" : (v >= max ? "Replay" : "Play");
      box.classList.toggle("is-playing", playing);
      if (o.onChange) o.onChange(v, k);
    }
    function set(x) { v = Math.max(min, Math.min(max, x)); render(); }
    function frame(ts) {
      if (!playing) return;
      var dt = lastTs ? ts - lastTs : 16; lastTs = ts;
      var nv = v + (max - min) * dt / (o.duration || 8000);
      if (nv >= max) { v = max; playing = false; render(); return; }
      v = nv; render(); raf = requestAnimationFrame(frame);
    }
    function play() { if (v >= max) v = min; playing = true; lastTs = 0; render(); raf = requestAnimationFrame(frame); }
    function pause() { playing = false; cancelAnimationFrame(raf); render(); }
    bp.addEventListener("click", function () { if (playing) pause(); else play(); });
    rg.addEventListener("input", function () { var x = +rg.value; playing = false; cancelAnimationFrame(raf); set(x); });
    box.querySelector(".pl-prev").addEventListener("click", function () {
      pause(); var t = min; for (var i = stops.length - 1; i >= 0; i--) if (stops[i].t < v - 1e-6) { t = stops[i].t; break; } set(t);
    });
    box.querySelector(".pl-next").addEventListener("click", function () {
      pause(); var t = max; for (var i = 0; i < stops.length; i++) if (stops[i].t > v + 1e-6) { t = stops[i].t; break; } set(t);
    });
    render();
    if (o.autoplay === "inview" && !reduced && "IntersectionObserver" in window) {
      var io = new IntersectionObserver(function (es) { es.forEach(function (e) { if (e.isIntersecting) { io.disconnect(); setTimeout(play, 350); } }); }, { threshold: 0.45 });
      io.observe(box.parentNode || box);
    }
    return { set: function (x) { pause(); set(x); }, play: play, pause: pause, value: function () { return v; } };
  };

  /* ---------- money split (v2, shared): where every ETH of a race's take went ----------
     BVH.moneySplit(row from incidents.json) -> { gross, priced, parts: [{ k, eth, label, sub }], extra, note }
     k in: "ret" returned to the victim, "bld" builder + proposer (net of refunds and of builder pass-through),
     "bot" kept by the bot, "oth" other (gas, sent elsewhere, untraced), "unk" fate unknown. */
  /* rows whose ETH amounts cannot be closed into one split, with the reason shown instead of a bar */
  BVH.MIXED_ROWS = {
    "uncx-2026": "Part of the take, and of what came back, was a token we do not price (X), so an ETH-only split would not close."
  };
  BVH.moneySplit = function (r, victim) {
    var m = r.money || {}, G = r.gross_eth, num = function (x) { return typeof x === "number" && isFinite(x); };
    victim = victim || "the victim";
    var out = { gross: G, total: G, priced: num(G) && G > 0, parts: [], extra: 0, extras: [], mixed: null, note: "", row: r };
    if (!out.priced) { out.note = "The take is not priced in ETH (tokens), so the split cannot be drawn."; return out; }
    var P = num(r.paid_to_builder_eth) ? r.paid_to_builder_eth : (num(r.coinbase_eth) ? r.coinbase_eth : 0);
    var F = num(r.builder_refund_eth) ? r.builder_refund_eth : 0;
    var RB = num(m.returned_by_builder_eth) ? m.returned_by_builder_eth : 0;
    var BN = num(m.bot_net_eth) ? m.bot_net_eth : G - P + F;
    var R = num(m.returned_total_eth) ? m.returned_total_eth : (num(r.returned_pct) ? G * r.returned_pct / 100 : null);
    var NB = Math.max(0, P - F - RB);
    var propB = num(r.proposer_paid_eth) ? r.proposer_paid_eth : null;   /* the proposer's payment for the whole block */
    var bounty = num(m.bounty_kept_eth) ? m.bounty_kept_eth : null;
    /* gas and anything else the take paid for: the take less the payment for position and the bot's net */
    var other = G - (P - F) - BN;
    if (Math.abs(other) < 1e-6) other = 0;
    out.known = { taken: G, paid: P - F, returned: R, net: BN };
    if (BVH.MIXED_ROWS[r.id]) out.mixed = BVH.MIXED_ROWS[r.id];
    else if (BN < -1e-9) out.mixed = "The bot's ETH net for this transaction is negative (" + BVH.eth2(BN) + "): its payments and returns span several transactions and tokens, so these amounts do not close into one split.";
    else if (other < 0) out.mixed = "The recorded payment and the bot's net add up to " + BVH.eth2(-other) + " more than the take, so the amounts are on different bases.";
    if (out.mixed) return out;
    /* the builder forwarded the payment on, and the return plus the bounty kept there exceed what it had left: it topped up from its own funds */
    var builderBounty = RB > 0 && bounty != null && propB != null && propB < P - F;
    var topup = builderBounty ? RB + bounty - (P - F - propB) : 0;
    if (topup < 1e-6) topup = 0;
    var bsubs = [];
    if (F > 0.0005) bsubs.push("after a " + BVH.eth2(F) + " refund from the builder");
    if (RB > 0 && !builderBounty) bsubs.push("left after the builder returned " + BVH.eth2(RB) + " to " + victim);
    if (propB != null && NB > 0) bsubs.push(propB > NB + 0.005 ? "this transaction paid " + BVH.eth2(NB) + " toward the " + BVH.eth2(propB) + " the proposer was paid for the whole block" : "the proposer was paid " + BVH.eth2(propB) + " for the whole block");
    if (builderBounty) bsubs.push(BVH.eth2(bounty) + " kept as a bounty on the builder's side" + (topup ? ", including " + BVH.eth2(topup) + " the builder added from its own funds" : ""));
    var bld = { k: "bld", eth: NB + topup, label: "Paid to the block builder and proposer", sub: bsubs.join("; ") };
    var parts = [];
    if (R == null) {
      if (RB) parts.push({ k: "ret", eth: RB, label: "Returned to " + victim });
      parts.push(bld);
      parts.push({ k: "unk", eth: Math.max(0, BN), label: "Held by the bot, fate unknown", sub: "no return established in our sources" });
    } else {
      var RBot = num(m.returned_by_bot_side_eth) ? m.returned_by_bot_side_eth : Math.max(0, R - RB);
      var kept = BN - RBot, extraBot = 0;
      if (kept < 0) { extraBot = -kept; kept = 0; }
      var rsub = RB > 0 && RBot > 0 ? BVH.eth2(RB) + " via the builder, " + BVH.eth2(RBot) + " from the bot" : RB > 0 ? "sent back from the builder's side" : "";
      parts.push({ k: "ret", eth: R, label: "Returned to " + victim, sub: rsub });
      parts.push(bld);
      var ksub = "";
      if (bounty != null && bounty > 0 && kept > 0) {
        if (bounty <= kept + 1e-9) ksub = "including a " + BVH.eth2(bounty) + " bounty";
        else if (/on-chain remainder/i.test(m.bounty_desc || "")) {
          var mv = /moved ([\d,.]+) WETH/i.exec(r.fate || ""), rep = /bounty of ([\d,.]+) WETH/i.exec(m.bounty_desc || "");
          ksub = "the take less the return. Later " + (mv ? parseFloat(mv[1].replace(/,/g, "")).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + " WETH" : "the WETH") + " left the bot's contract; after the return, " + BVH.eth2(bounty).replace(" ETH", " WETH") + " of that remained" + (rep ? ". " + victim.charAt(0).toUpperCase() + victim.slice(1) + " reported a " + rep[1] + " WETH bounty" : "");
        }
      }
      parts.push({ k: "bot", eth: kept, label: "Kept by the bot", sub: ksub });
      if (extraBot > 1e-6) out.extras.push({ eth: extraBot, text: "from the bot's other funds (it later sent " + victim + " " + BVH.eth2(RBot) + " but had kept only " + BVH.eth2(BN) + " of the take)" });
    }
    if (topup) out.extras.push({ eth: topup, text: "the builder added from its own funds when it forwarded " + BVH.eth2(RB + bounty) });
    if (other > 0) parts.push({ k: "oth", eth: other, label: /went to the attacker/i.test(m.captured_desc || "") ? "Sent on to the attacker" : other > Math.max(0.005, G * 0.002) ? "Other: gas, sent elsewhere or untraced" : "Gas and other costs" });
    out.extra = out.extras.reduce(function (a, e) { return a + e.eth; }, 0);
    out.total = G + out.extra;
    if (out.extras.length) out.note = "Shares are of " + BVH.eth2(out.total) + ": the " + BVH.eth2(G) + " taken, plus " + out.extras.map(function (e) { return BVH.eth2(e.eth) + " " + e.text; }).join(", and ") + ".";
    out.parts = parts;
    return out;
  };
  /* where the split's numbers come from: the take and payment (block trace), the proposer payment, and every saved return
     transfer listed on the race page. D = the race's data/incident/<id>.json, optional. */
  BVH.moneySrc = function (r, D) {
    var raw = r.raw || {}, bits = [], ir = (D && D.incident_raw) || {}, seen = {};
    if (raw.trace || raw.block) bits.push("take and payment " + BVH.rawA(raw.trace || raw.block, "trace", "Block trace: the bot's take and its payment to the builder"));
    if (r.proposer_paid_eth != null && (ir.proposer_payment_tx || raw.delivered)) bits.push("proposer " + BVH.rawA(ir.proposer_payment_tx || raw.delivered, "raw", ir.proposer_payment_tx ? "The builder's payment to the proposer" : "Relay record of the block delivered to the proposer"));
    if (ir.builder_to_treasury_tx) bits.push("forward " + BVH.rawA(ir.builder_to_treasury_tx, "raw", "The builder's forward of the payment"));
    if (D && r.fate_kind !== "n-a") {
      var ev = (D.events || []).filter(function (e) { return e.kind === "return" && !/test (transfer|transaction|to)|^withdrawTo 1\.0|Recovery Safe/i.test(e.detail || ""); });
      var R = r.money && r.money.returned_total_eth;
      if (r.sub && R && ev.length > 1) {
        var near = ev.filter(function (e) { return ((e.detail || "").match(/\d[\d,]*(\.\d+)?/g) || []).some(function (s) { var v = parseFloat(s.replace(/,/g, "")); return v > 0 && Math.abs(v - R) <= 0.01 * R; }); });
        if (near.length) ev = near;
      }
      var urls = [];
      ev.forEach(function (e) { (e.raws && e.raws.length ? e.raws : [e.raw]).forEach(function (u) { if (u && !seen[u]) { seen[u] = 1; urls.push(u); } }); });
      if (urls.length) { var chk = r.fate_kind === "kept" || r.fate_kind === "unknown" || R === 0; bits.push((chk ? "return checks " : "returns ") + BVH.rawAs(urls, urls.length > 1 ? "" : "raw", chk ? "Saved transfers checked for a return" : "Saved transfers behind the return")); }
    }
    return bits.length ? "Sources: " + bits.join("; ") + "." : "";
  };
  /* ETH with two decimals from 1 ETH up (276.32 ETH), BVH.eth below */
  BVH.eth2 = function (x) { if (x == null || isNaN(x)) return "n/a"; return Math.abs(x) >= 1 ? x.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + " ETH" : BVH.eth(x); };
  BVH.SPLIT_NAMES = { ret: "returned", bld: "to builder and proposer", bot: "kept by bot", oth: "other", unk: "unknown" };
  /* the bar + key; opts: { compact: bool, labels: {k: text} } */
  BVH.splitHTML = function (s, opts) {
    opts = opts || {};
    var src = opts.sources ? '<div class="split-src">' + opts.sources + "</div>" : "";
    if (s.mixed) {
      var k = s.known || {};
      return '<div class="split split-none split-mixed"><div class="split-bar" role="img" aria-label="Mixed, not reconciled"><i class="s-unk" style="flex:1 1 0"></i></div><p class="split-note"><b>Mixed, not reconciled.</b> ' + BVH.esc(s.mixed) +
        " In ETH alone: taken " + BVH.eth2(k.taken) + ", paid for position " + BVH.eth2(k.paid) + ", returned " + (k.returned != null ? BVH.eth2(k.returned) : "not split by row") + ".</p>" + src + "</div>";
    }
    if (!s.priced) return '<div class="split split-none"><div class="split-bar"><i class="s-unk" style="flex:1 1 0"></i></div><p class="split-note">' + BVH.esc(s.note) + "</p>" + src + "</div>";
    var base = s.parts.reduce(function (a, p) { return a + Math.max(0, p.eth); }, 0) || 1;
    /* percentages are shares of all the money that moved: the take, plus anything added from other funds (s.extras), so they sum to 100% */
    var G = s.total || s.gross;
    var aria = s.parts.map(function (p) { return (p.label) + " " + BVH.eth(p.eth) + " (" + BVH.pct(100 * p.eth / G, 1) + ")"; }).join("; ");
    var bar = '<div class="split-bar" role="img" aria-label="Of ' + BVH.eth(s.gross) + ' taken' + (s.extra > 0 ? ' plus ' + BVH.eth(s.extra) + ' added from other funds' : '') + ': ' + BVH.esc(aria) + '">' + s.parts.map(function (p) {
      if (p.eth <= 0) return "";
      return '<i class="s-' + p.k + '" style="flex:' + (p.eth / base).toFixed(5) + ' 1 0"></i>';
    }).join("") + "</div>";
    var note = s.note && s.extras && s.extras.length ? '<p class="split-note split-denom">' + BVH.esc(s.note) + "</p>" : "";
    function pcTxt(pc) { return pc >= 0.1 ? BVH.pct(pc, pc >= 10 ? 0 : 1) : "&lt;0.1%"; }
    /* "kept" rows: the return checks cover a finite range (fate.text), so a zero return reads "no return found", not "nothing" */
    var R0 = s.row || {}, notFound = R0.fate_kind === "kept";
    function zeroTxt(p) { return p.k === "ret" && notFound ? "no return found" + BVH.rawA("data/incident/" + R0.id + ".json", "basis", "The return checks and the range they cover (fate)") : "nothing"; }
    if (opts.inline) {
      var ik = '<ul class="split-key split-inline">' + s.parts.map(function (p) {
        var pc = 100 * p.eth / G, zero = p.eth < 1e-9, lab = ((opts.labels && opts.labels[p.k]) || p.label);
        return '<li class="sk-' + p.k + (zero ? " is-zero" : "") + '"><i aria-hidden="true"></i><span>' + (zero && p.k === "ret" && notFound ? "<b>No return found</b>" + zeroTxt(p).replace(/^no return found/, "") : "<b>" + (zero && p.k !== "unk" ? "nothing" : BVH.eth2(p.eth)) + "</b> " + BVH.esc(lab.charAt(0).toLowerCase() + lab.slice(1))) + (zero ? "" : ' <small class="sk-pc">' + pcTxt(pc) + "</small>") + (p.sub ? ' <small class="sk-sub">' + BVH.esc(p.sub) + "</small>" : "") + "</span></li>";
      }).join("") + "</ul>";
      return '<div class="split split-compact">' + (opts.bar === false ? "" : bar) + ik + note + src + "</div>";
    }
    var key = '<ul class="split-key">' + s.parts.map(function (p) {
      var pc = 100 * p.eth / G, zero = p.eth < 1e-9;
      var val = zero && p.k !== "unk" ? zeroTxt(p) : BVH.eth2(p.eth);
      return '<li class="sk-' + p.k + (zero ? " is-zero" : "") + '"><i aria-hidden="true"></i><span class="sk-l">' + BVH.esc((opts.labels && opts.labels[p.k]) || p.label) + (p.sub ? '<small>' + BVH.esc(p.sub) + "</small>" : "") + '</span><span class="sk-v">' + val + (zero ? "" : '<small>' + pcTxt(pc) + "</small>") + "</span></li>";
    }).join("") + "</ul>";
    return '<div class="split' + (opts.compact ? " split-compact" : "") + '">' + bar + key + note + src + "</div>";
  };

  /* ---------- misc ---------- */
  BVH.qs = function (k) { return new URLSearchParams(location.search).get(k); };
  BVH.slugify = function (s) { return String(s || "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, ""); };
  BVH.RT = {
    "beat-pending-attack": { name: "Beat a pending attack", def: "The bot landed before a pending or in-flight attacker transaction, replaying or adapting it." },
    "deploy-window-copy": { name: "Used the attacker's setup", def: "The bot used the attacker's on-chain setup (a deployed contract or a prepare() call) before the attacker's own call." },
    "beat-whitehat-or-user": { name: "Copied a user or whitehat", def: "The bot copied a transaction sent by someone who was not a hacker: a user's withdrawal, or a whitehat's rescue." },
    "post-failure-replay": { name: "Replayed after a failure", def: "The attacker's transaction had already failed or landed; a bot or whitehat replayed it afterwards." },
    "bot-was-first-exploiter": { name: "The bot was first", def: "The first observed exploit transaction was the bot's; no separate attacker transaction is established." },
    "late-copy": { name: "Late copy", def: "Copied after the attacker had already succeeded." },
    "no-race": { name: "No race", def: "Looked like a race, but the attacker acted alone and nothing copied or beat them. Rejected after checking." }
  };
  BVH.rtName = function (k) { return (BVH.RT[k] || { name: k || "n/a" }).name; };

  /* ---------- who lost each headline race (owner decision 2026-10-23) ----------
     row.beaten = { verdict, kind: confirmed | likely | later, label, note, evidence: [raw urls] } on the 19 headline
     rows of data/incidents.json (from data/incidents.json beaten_party; audit in launch/reports/v3-adversary.findings.md).
     The series title stays "The Bot Beat the Hacker"; factual copy says who the bot actually beat. */
  BVH.BEATEN = {
    confirmed: { name: "The original attacker", short: "the original attacker", tag: "confirmed", group: "The original attacker, confirmed" },
    likely: { name: "Probably the original attacker", short: "probably the original attacker", tag: "likely", group: "Probably the original attacker" },
    later: { name: "A later exploiter, or we can't tell", short: "a later exploiter, or we can't tell", tag: "later or unknown", group: "A later exploiter, or we can't tell" }
  };
  BVH.beatenCounts = function (rows) {
    var c = { confirmed: 0, likely: 0, later: 0, total: 0, rows: { confirmed: [], likely: [], later: [] } };
    (rows || []).forEach(function (r) { var b = r.headline && r.beaten; if (!b || !c.rows[b.kind]) return; c[b.kind]++; c.total++; c.rows[b.kind].push(r); });
    c.original = c.confirmed + c.likely;
    return c;
  };
  /* a short name for each saved response behind a verdict, read from its file name */
  function evName(u) {
    var f = String(u).split("/").pop();
    if (/^txlistint|_txlistinternal|txlistinternal/.test(f)) return "funding and internal txs";
    if (/tokentx/.test(f)) return "token transfers";
    if (/txlist/.test(f)) return "account history";
    if (/^receipts_/.test(f)) return "receipts";
    if (/^trace_block_/.test(f)) return "block trace";
    if (/^trace_/.test(f)) return "trace";
    if (/^tracefilter_/.test(f)) return "call scan";
    if (/^tx_/.test(f)) return "transaction";
    if (/^block_/.test(f)) return "block";
    if (/\.csv\.rows\.csv$/.test(f)) return "mempool rows";
    if (/\.html$|\.json$/.test(f) && /\/web/.test(u)) return "write-up";
    return "raw";
  }
  BVH.beatenEvidence = function (b) {
    var seen = {}, out = [];
    ((b && b.evidence) || []).forEach(function (u) {
      var n = evName(u); seen[n] = (seen[n] || 0) + 1;
      out.push([u, n]);
    });
    return out.map(function (x, i) {
      var n = x[1], dup = seen[n] > 1 ? " " + (out.slice(0, i + 1).filter(function (y) { return y[1] === n; }).length) : "";
      return BVH.rawA(x[0], n + dup, "Saved response behind who lost this race: " + n);
    }).join(" ");
  };
  BVH.raceShort = function (r) {
    return String(r.title || r.name || r.id).replace(/^Curve \/ Vyper: (.*?)( pool)?$/, "Curve $1").replace(/^Unizen: /, "Unizen ").replace(/: Yoink X-token race$/, "").replace(/ holder Safe$/, "");
  };
  BVH.raceHref = function (r) { return "incident.html?slug=" + encodeURIComponent(r.slug) + (r.sub ? "&sub=" + encodeURIComponent(r.sub) : ""); };
  /* three groups, one marker per race, each race linked to its page (where its verdict and evidence are) */
  BVH.whoLostHTML = function (rows) {
    var c = BVH.beatenCounts(rows);
    return '<div class="wholost">' + ["confirmed", "likely", "later"].map(function (k) {
      var K = BVH.BEATEN[k], list = c.rows[k].slice().sort(function (a, b) { return a.date < b.date ? -1 : 1; });
      return '<div class="wl-g wl-' + k + '"><h3><span class="wl-n">' + c[k] + "</span>" + K.group + '</h3><div class="wl-dots" aria-hidden="true">' + list.map(function () { return '<span class="wl-dot"></span>'; }).join("") + '</div><ul class="wl-list">' +
        list.map(function (r) { return '<li><a href="' + BVH.raceHref(r) + '" title="' + BVH.esc((r.beaten && r.beaten.note) || "") + '">' + BVH.esc(BVH.raceShort(r)) + "</a> " + r.date.slice(0, 4) + "</li>"; }).join("") + "</ul></div>";
    }).join("") + "</div>";
  };
  /* opts.compact: one line (label + links), for tables and gallery cards */
  BVH.beatenHTML = function (row, opts) {
    opts = opts || {};
    var b = row && row.beaten; if (!b || !BVH.BEATEN[b.kind]) return "";
    var K = BVH.BEATEN[b.kind];
    if (opts.compact) return '<p class="beaten beaten-c bt-' + b.kind + '"><i aria-hidden="true"></i><span><span class="bt-k">Who lost: </span><b>' + K.short + "</b>" + (opts.note && b.note ? ' <span class="bt-note">' + BVH.esc(b.note) + "</span>" : "") + " " + BVH.beatenEvidence(b) + "</span></p>";
    return '<div class="beaten bt-' + b.kind + '"><p class="bt-head"><i aria-hidden="true"></i><span class="bt-k">Who lost this race</span><b>' + K.name + '</b><span class="bt-tag">' + K.tag + "</span></p>" +
      (b.note ? '<p class="bt-note">' + BVH.esc(b.note) + "</p>" : "") + '<p class="bt-src">Evidence: ' + BVH.beatenEvidence(b) + ' <a href="methods.html#who-lost">How we judged who lost</a></p></div>';
  };
  BVH.loadError = function (el, e) {
    el.innerHTML = '<div class="callout bad">Could not load the data (' + BVH.esc(e.message || e) + '). Serve the site over http, for example <code>python -m http.server</code> from the site folder, not from file://.</div>';
  };

  /* =====================================================================================
     v4 skim components (launch/v4/shared-api.txt). All return HTML strings unless noted,
     work with keyboard (native <details>/<button>), and render complete without motion.
     ===================================================================================== */

  /* ---------- the decided headline sentence (owner, word for word). Numbers are filled from the data. ---------- */
  BVH.HEADLINE_TEXT = "{races} races where a bot got there first, in {incidents} hacks. In {orig} the loser was the original attacker ({conf} confirmed, {likely} likely); in {later} it was a later exploiter or we can't tell.";
  BVH.headlineVals = function (rows) {
    var c = BVH.beatenCounts(rows), slugs = {};
    (rows || []).forEach(function (r) { if (r.headline) slugs[r.slug] = 1; });
    return { races: (rows || []).filter(function (r) { return r.headline; }).length, incidents: Object.keys(slugs).length, orig: c.original, conf: c.confirmed, likely: c.likely, later: c.later };
  };
  BVH.headline = function (rows) {
    var v = BVH.headlineVals(rows);
    return BVH.HEADLINE_TEXT.replace(/\{(\w+)\}/g, function (m, k) { return v[k] != null ? v[k] : m; });
  };

  /* ---------- drawer: a closed <details> whose summary says what is inside ---------- */
  BVH.drawer = function (title, body, o) {
    o = o || {};
    return '<details class="drawer' + (o.cls ? " " + o.cls : "") + '"' + (o.id ? ' id="' + o.id + '"' : "") + (o.open ? " open" : "") + '><summary><span class="dr-t">' + title + "</span>" +
      (o.meta ? '<span class="dr-m">' + o.meta + "</span>" : "") + '</summary><div class="dr-b">' + body + "</div></details>";
  };
  /* a hash that points into (or at) a closed drawer opens it, so links from elsewhere still land on the rows */
  BVH.openHash = function (hash, scroll) {
    hash = hash == null ? location.hash : hash;
    if (!hash || hash.length < 2) return false;
    var t; try { t = document.getElementById(decodeURIComponent(hash.slice(1))); } catch (e) { t = null; }
    if (!t) return false;
    var n = t, opened = false;
    while (n && n !== document.body) { if (n.tagName === "DETAILS" && !n.open) { n.open = true; opened = true; } n = n.parentNode; }
    if (opened || scroll) t.scrollIntoView();
    return true;
  };
  window.addEventListener("hashchange", function () { BVH.openHash(null, false); });
  document.addEventListener("click", function (e) {
    var a = e.target.closest && e.target.closest('a[href^="#"]');
    if (!a) return;
    var h = a.getAttribute("href"); if (h.length < 2) return;
    var t = document.getElementById(h.slice(1));
    if (t && t.closest("details:not([open])")) { setTimeout(function () { BVH.openHash(h, true); }, 0); }
  });

  /* ---------- "Sources (n)": one toggle per card instead of rows of raw chips ---------- */
  BVH.sources = function (html, o) {
    o = o || {};
    if (!html) return "";
    var n = (String(html).match(/class="raw[" ]/g) || []).length;
    if (n <= (o.inlineMax == null ? 1 : o.inlineMax)) return '<span class="srcs-inline">' + html + "</span>";
    return '<details class="srcs' + (o.cls ? " " + o.cls : "") + '"><summary>' + (o.label || "Sources") + " (" + n + ')</summary><div class="srcs-b">' + html + "</div></details>";
  };

  /* ---------- chapter opener: ONE big number + ONE plain sentence ---------- */
  BVH.opener = function (o) {
    return '<div class="opener' + (o.cls ? " " + o.cls : "") + '"><p class="op-big">' + o.big + (o.src ? '<sup class="fn">' + o.src + "</sup>" : "") + "</p>" +
      '<p class="op-line">' + o.text + "</p></div>";
  };

  /* ---------- tile grid (2x3 on desktop, 2 columns on phones): each tile jumps to its chapter; one share icon ---------- */
  var SHARE_ICON = '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M8 1.5l3.2 3.2-.9.9L8.6 3.9V10H7.4V3.9L5.7 5.6l-.9-.9z"/><path d="M3 7h2v1.2H4.2v5.6h7.6V8.2H11V7h2v8H3z"/></svg>';
  BVH.tiles = function (items, o) {
    o = o || {};
    return '<div class="tiles' + (o.cls ? " " + o.cls : "") + '"' + (o.label ? ' role="list" aria-label="' + BVH.esc(o.label) + '"' : ' role="list"') + ">" + items.map(function (t) {
      /* a tile without a link carries its source as a superscript beside the number; a linked tile keeps it outside the link */
      var inner = (t.badge ? '<span class="tile-badge">' + t.badge + "</span>" : "") + '<b class="tile-big">' + t.big + (!t.href && t.src ? '<sup class="fn">' + t.src + "</sup>" : "") + '</b><span class="tile-l">' + t.label + "</span>";
      var plain = String(t.big).replace(/<[^>]*>/g, "") + " " + String(t.label).replace(/<[^>]*>/g, "");
      return '<div class="tile' + (t.cls ? " " + t.cls : "") + '" role="listitem">' + (t.href ? '<a class="tile-a" href="' + t.href + '">' + inner + "</a>" : '<div class="tile-a">' + inner + "</div>") +
        (t.src && t.href ? '<span class="tile-src">' + t.src + "</span>" : "") +
        (t.share !== false && t.href ? '<button type="button" class="tile-share" data-share="' + BVH.esc(t.href) + '" data-share-text="' + BVH.esc(t.shareText || plain) + '" aria-label="' + BVH.esc("Share: " + plain) + '">' + SHARE_ICON + "</button>" : "") + "</div>";
    }).join("") + "</div>";
  };
  /* share a link to a place on this page: the system share sheet where there is one, else copy the link */
  BVH.toast = function (msg) {
    var t = document.getElementById("bvh-toast");
    if (!t) { t = document.createElement("div"); t.id = "bvh-toast"; t.className = "toast"; t.setAttribute("role", "status"); document.body.appendChild(t); }
    t.textContent = msg; t.classList.add("on"); clearTimeout(t._h); t._h = setTimeout(function () { t.classList.remove("on"); }, 2200);
  };
  BVH.share = function (href, text) {
    var url = new URL(href || "", location.href).href;
    if (navigator.share) { navigator.share({ title: document.title, text: text || "", url: url }).catch(function () { /* dismissed */ }); return; }
    var done = function () { BVH.toast("Link copied"); };
    if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(url).then(done, function () { window.prompt("Copy this link", url); });
    else window.prompt("Copy this link", url);
  };
  document.addEventListener("click", function (e) {
    var b = e.target.closest && e.target.closest("[data-share]");
    if (b) { e.preventDefault(); BVH.share(b.getAttribute("data-share"), b.getAttribute("data-share-text")); }
  });

  /* ---------- tap-to-define: <button class="term" data-term="builder">block builder</button> ---------- */
  BVH.term = function (key, text, def) {
    var g = BVH.GLOSSARY[key];
    return '<button type="button" class="term" data-term="' + BVH.esc(key) + '"' + (def ? ' data-def="' + BVH.esc(def) + '"' : "") + ' aria-expanded="false">' + (text || (g ? g[0].toLowerCase() : key)) + "</button>";
  };
  var termPop = null, termBtn = null;
  function closeTerm(refocus) {
    if (!termPop || termPop.hidden) return;
    termPop.hidden = true; if (termBtn) { termBtn.setAttribute("aria-expanded", "false"); if (refocus) termBtn.focus(); } termBtn = null;
  }
  function openTerm(btn) {
    if (!termPop) { termPop = document.createElement("div"); termPop.className = "term-pop"; termPop.id = "bvh-termpop"; termPop.setAttribute("role", "note"); termPop.hidden = true; document.body.appendChild(termPop); }
    var k = btn.getAttribute("data-term"), g = BVH.GLOSSARY[k], def = btn.getAttribute("data-def") || (g ? g[1] : "");
    termPop.innerHTML = "<b>" + BVH.esc(g ? g[0] : btn.textContent) + "</b> " + def;
    termPop.hidden = false; termBtn = btn; btn.setAttribute("aria-expanded", "true"); btn.setAttribute("aria-controls", "bvh-termpop");
    var r = btn.getBoundingClientRect(), w = Math.min(340, window.innerWidth - 24);
    termPop.style.width = w + "px";
    var left = Math.max(12, Math.min(window.innerWidth - w - 12, r.left + r.width / 2 - w / 2));
    termPop.style.left = (left + window.scrollX) + "px";
    var below = r.bottom + 10 + termPop.offsetHeight < window.innerHeight || r.top < termPop.offsetHeight + 20;
    termPop.style.top = (below ? r.bottom + 8 + window.scrollY : r.top - termPop.offsetHeight - 8 + window.scrollY) + "px";
  }
  document.addEventListener("click", function (e) {
    var b = e.target.closest && e.target.closest("button.term");
    if (b) { if (termBtn === b && !termPop.hidden) closeTerm(); else openTerm(b); return; }
    if (termPop && !termPop.hidden && !termPop.contains(e.target)) closeTerm();
  });
  document.addEventListener("keydown", function (e) { if (e.key === "Escape" || e.key === "Esc") closeTerm(true); });
  window.addEventListener("resize", function () { closeTerm(); });
  /* the glossary as a closed drawer: "7 words this story uses" */
  BVH.glossary = function (keys, o) {
    o = o || {};
    var items = (keys || []).map(function (k) { return typeof k === "string" ? BVH.GLOSSARY[k] : k; }).filter(Boolean);
    return BVH.drawer(o.title || (items.length + " words this story uses"), (o.intro ? '<p class="dr-intro">' + o.intro + "</p>" : "") + '<dl class="gloss">' + items.map(function (t) { return "<dt>" + BVH.esc(t[0]) + "</dt><dd>" + t[1] + "</dd>"; }).join("") + "</dl>",
      { cls: "drawer-gloss" + (o.cls ? " " + o.cls : ""), id: o.id, meta: o.meta || "tap to open" });
  };

  /* ---------- build once on scroll ----------
     BVH.onView(el, fn, {threshold, rootMargin}) calls fn(el, reduced) once, when el first scrolls into view
     (immediately when IntersectionObserver is missing or the reader prefers reduced motion).
     BVH.buildIn(el|selector, kind) marks content that should build in: "bars" (split bars and .bi-bar fill
     left to right), "rise" (.bi-item children fade up one after another), "grow" (.bi-col scale up from the floor).
     The waiting state is only applied by script when motion is allowed and the element is below the fold, so the
     page is complete if the animation never fires. Each build runs once and takes 600 ms or less. */
  BVH.onView = function (el, fn, o) {
    o = o || {};
    if (!el) return;
    var red = BVH.reduced();
    if (red || !("IntersectionObserver" in window)) { fn(el, red); return; }
    var io = new IntersectionObserver(function (es) { es.forEach(function (e) { if (e.isIntersecting) { io.disconnect(); fn(el, false); } }); }, { threshold: o.threshold == null ? 0.15 : o.threshold, rootMargin: o.rootMargin || "0px 0px -8% 0px" });
    io.observe(el);
  };
  BVH.buildIn = function (els, kind) {
    var list = typeof els === "string" ? document.querySelectorAll(els) : (els && els.length != null && !els.tagName ? els : [els]);
    Array.prototype.forEach.call(list, function (el) {
      if (!el || el.classList.contains("bi")) return;
      el.classList.add("bi", "bi-" + (kind || "bars"));
      Array.prototype.forEach.call(el.querySelectorAll(".bi-item, .split-bar"), function (c, i) { c.style.setProperty("--bi-i", Math.min(i, 12)); });
      if (BVH.reduced() || !("IntersectionObserver" in window)) return;
      var r = el.getBoundingClientRect();
      if (r.top < window.innerHeight * 0.92) return;   /* already on screen: leave it drawn */
      el.classList.add("bi-wait");
      BVH.onView(el, function () { el.classList.remove("bi-wait"); el.classList.add("bi-go"); });
    });
  };
  window.addEventListener("beforeprint", function () { Array.prototype.forEach.call(document.querySelectorAll(".bi-wait"), function (el) { el.classList.remove("bi-wait"); }); });

  /* ---------- chat: on-chain messages as a two-sided thread, tx details behind a toggle ----------
     msgs: [{ side: "in"|"out", who, when, text, tx: HTML for the toggle (hash link, raw), note }] */
  BVH.chat = function (msgs, o) {
    o = o || {};
    return '<div class="chat' + (o.cls ? " " + o.cls : "") + '"' + (o.label ? ' aria-label="' + BVH.esc(o.label) + '" role="group"' : "") + ">" + msgs.map(function (m) {
      if (m.gap) return '<p class="cb-gap bi-item">' + m.gap + "</p>";
      return '<figure class="cb cb-' + (m.side === "out" ? "out" : "in") + ' bi-item"><figcaption class="cb-who">' + m.who + (m.when ? ' <span class="cb-when">' + m.when + "</span>" : "") + "</figcaption>" +
        '<blockquote class="cb-text">' + m.text + "</blockquote>" + (m.note ? '<p class="cb-note">' + m.note + "</p>" : "") +
        (m.tx ? '<details class="cb-tx"><summary>tx</summary><div class="cb-txb">' + m.tx + "</div></details>" : "") + "</figure>";
    }).join("") + "</div>";
  };

  /* ---------- who lost, as 19 dots (8 solid confirmed, 5 ring likely, 6 dashed later / can't tell) ---------- */
  BVH.lostStrip = function (rows, o) {
    o = o || {};
    var c = BVH.beatenCounts(rows), href = o.href || function (r) { return "#sb-" + r.id; };
    var dots = ["confirmed", "likely", "later"].map(function (k) {
      return '<span class="ls-g ls-' + k + '">' + c.rows[k].slice().sort(function (a, b) { return a.date < b.date ? -1 : 1; }).map(function (r) {
        return '<a class="ls-dot bt-' + k + '" href="' + href(r) + '" aria-label="' + BVH.esc(BVH.raceShort(r) + " " + r.date.slice(0, 4) + ": " + BVH.BEATEN[k].short) + '" title="' + BVH.esc(BVH.raceShort(r) + " " + r.date.slice(0, 4)) + '"><i></i></a>';
      }).join("") + "</span>";
    }).join("");
    return '<div class="lstrip"><div class="ls-dots" role="group" aria-label="Who lost each of the ' + c.total + ' races">' + dots + '</div><p class="ls-key"><span class="bt-confirmed"><i></i>' + c.confirmed + ' original attacker, confirmed</span><span class="bt-likely"><i></i>' + c.likely + ' probably the original attacker</span><span class="bt-later"><i></i>' + c.later + " later exploiter or can't tell</span></p></div>";
  };

  /* ---------- the scoreboard: one row per headline race, grouped by who lost ----------
     BVH.scoreboard(el, rows, { victims: {id: "Makina"}, ids: [subset], extra: function(row, D) -> HTML,
       idPrefix: "sb-", group: true, keyText }) renders into el. Each row is a <details>: the summary shows the
     marker, name, year, bot, what it took and the full money split bar; opening it shows the split amounts, who
     lost, the sources (one "Sources (n)" toggle) and a link to the race page. The race file is loaded on first open. */
  function victimOf(r) {
    var n = String(r.title || r.name || r.id);
    if (/^Curve \/ Vyper: (.*?)( pool)?$/.test(n)) return { "curve-vyper-2023--peth": "JPEG'd", "curve-vyper-2023--crv-eth-2": "Curve", "curve-vyper-2023--mseth": "Metronome" }[r.id] || "Curve";
    if (r.id === "kelp-rseth-2026") return "the Safe's owner";
    return n.split(":")[0].replace(/ Protocol$| Finance$| Lending$| token vesting$| SilicaPools$| V2$| token$/, "").trim();
  }
  BVH.victimOf = victimOf;
  BVH.botShort = function (r) { return String(r.bot || "").replace(/\s*\(.*\)\s*$/, "").replace(/^anonymous /, "anon ").trim(); };
  BVH.SPLIT_KEY = '<div class="fig-key sb-key" aria-hidden="true"><span><i class="s-ret"></i>returned to the victim</span><span><i class="s-bld"></i>builder and proposer</span><span><i class="s-bot"></i>kept by the bot</span><span><i class="s-oth"></i>gas and other</span><span><i class="s-unk"></i>unknown</span></div>';
  BVH.scoreboard = function (el, rows, o) {
    o = o || {};
    var pre = o.idPrefix || "sb-", V = o.victims || {};
    var list = rows.filter(function (r) { return r.headline && r.beaten && (!o.ids || o.ids.indexOf(r.id) >= 0); });
    function rowHTML(r) {
      var vic = V[r.id] || victimOf(r), s = BVH.moneySplit(r, vic), k = r.beaten.kind;
      var took = s.priced ? (s.gross >= 100 ? Math.round(s.gross).toLocaleString("en-US") : s.gross >= 10 ? s.gross.toFixed(1) : s.gross.toFixed(2)) + " ETH" + (BVH.MIXED_ROWS[r.id] ? " + tokens" : "") : "tokens";
      var tr0 = r.raw && (r.raw.trace || r.raw.block);
      var bar = s.mixed || !s.priced ? '<div class="split-bar"><i class="s-unk" style="flex:1 1 0"></i></div>' : (BVH.splitHTML(s, { compact: true }).match(/<div class="split-bar"[\s\S]*?<\/div>/) || [""])[0];
      return '<details class="sb-row sb-' + k + '" id="' + pre + r.id + '" data-id="' + r.id + '"><summary class="sb-sum">' +
        '<span class="sb-mk" aria-hidden="true"><i></i></span>' +
        '<span class="sb-name"><b>' + BVH.esc(BVH.raceShort(r)) + "</b> <span class=\"sb-meta\">" + r.date.slice(0, 4) + " &middot; " + BVH.esc(BVH.botShort(r)) + "</span>" + "</span>" +
        '<span class="sb-took"><span class="sr">took </span>' + took + '<sup class="fn">' + BVH.rawA(tr0, "raw", "Block trace with the bot's take") + "</sup></span>" +
        '<span class="sb-bar">' + bar + '</span><span class="sr">. Who lost: ' + BVH.BEATEN[k].short + ". Open for the split and sources.</span></summary>" +
        '<div class="sb-body"><div class="sb-fill" aria-live="polite"></div></div></details>';
    }
    function fill(det, D) {
      var r = rows.filter(function (x) { return x.id === det.getAttribute("data-id"); })[0]; if (!r) return;
      var vic = V[r.id] || victimOf(r), s = BVH.moneySplit(r, vic), b = r.beaten, K = BVH.BEATEN[b.kind];
      var trace = r.raw && (r.raw.trace || r.raw.block);
      var takeTxt = s.priced ? "Took <b>" + BVH.eth2(s.gross) + "</b>" + (BVH.MIXED_ROWS[r.id] ? " plus unpriced tokens" : "") + BVH.rawA(trace, "raw", "Block trace with the bot's take") : "Took an amount in tokens, not priced in ETH";
      var srcs = [BVH.moneySrc(r, D).replace(/^Sources: /, "").replace(/\.$/, ""), "who lost " + BVH.beatenEvidence(b)].filter(Boolean).join("; ");
      var dodo = !s.priced && r.id === "dodo-v2-2021" ? (function () { var dm = /and ([\d.]+) ETH to/.exec(r.fate || ""); return '<p class="sb-plain">Antelope returned tokens' + (dm ? " and " + BVH.eth2(+dm[1]) : "") + " to DODO; the return is not reconciled with the take.</p>"; })() : "";
      det.querySelector(".sb-fill").innerHTML =
        '<p class="sb-take">' + takeTxt + (r.loot_scope && r.loot_scope !== "bot-tx" ? ' <span class="sb-scope">' + BVH.esc(r.loot_scope) + "</span>" : "") + "</p>" +
        BVH.splitHTML(s, { inline: true, bar: false, labels: { bld: "To the builder and proposer", ret: "Returned to " + vic } }) + dodo +
        '<p class="sb-lost bt-' + b.kind + '"><i aria-hidden="true"></i><span><span class="bt-k">Who lost: </span><b>' + K.short + "</b>" + (b.note ? " " + BVH.esc(b.note) : "") + "</span></p>" +
        (o.extra ? '<div class="sb-extra">' + (o.extra(r, D) || "") + "</div>" : "") +
        '<div class="sb-foot">' + BVH.sources(srcs, { inlineMax: 0 }) + '<a class="sb-go" href="' + BVH.raceHref(r) + '">Replay this race <span aria-hidden="true">&rarr;</span></a></div>';
    }
    var groups = o.group === false ? [["all", list]] : ["confirmed", "likely", "later"].map(function (k) { return [k, list.filter(function (r) { return r.beaten.kind === k; })]; });
    el.classList.add("sb");
    el.innerHTML = (o.key === false ? "" : BVH.SPLIT_KEY) + groups.map(function (g) {
      if (!g[1].length) return "";
      var rs = g[1].slice().sort(function (a, b) { return a.date < b.date ? -1 : a.date > b.date ? 1 : 0; });
      return (g[0] === "all" ? "" : '<h3 class="sb-g bt-' + g[0] + '"><i aria-hidden="true"></i><span class="sb-gn">' + rs.length + '<sup class="fn">' + BVH.rawA("data/beaten_party.json", "data", "Who-lost verdicts and their counts") + "</sup></span> " + BVH.BEATEN[g[0]].group + "</h3>") + '<div class="sb-list">' + rs.map(rowHTML).join("") + "</div>";
    }).join("");
    Array.prototype.forEach.call(el.querySelectorAll(".sb-row"), function (det) {
      det.addEventListener("toggle", function () {
        if (!det.open || det._filled) return;
        det._filled = true;
        var r = rows.filter(function (x) { return x.id === det.getAttribute("data-id"); })[0];
        fill(det, null);
        BVH.json("data/incident/" + r.id + ".json").then(function (D) { fill(det, D); }).catch(function () { /* keep the row-level sources */ });
      });
    });
    BVH.buildIn(el, "bars");
    return el;
  };
})();
