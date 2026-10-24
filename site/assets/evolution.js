/* Part 3: Has the dark forest changed? Every number is read from site/data at render time.
   The art on this page is drawn in code from the same data (EVART below); no image files. */
(function () {
  "use strict";

  /* =====================================================================================
     EVART: code-drawn, data-driven art. Canvas at device pixel ratio, static (no animation),
     seeded so it draws the same picture on every load. Exported so the link-preview card
     (launch/v3/og-C/og-evolution.html) draws the same scene.
     ===================================================================================== */
  var EVART = (window.EVART = {});
  function rng(seed) { var a = seed >>> 0; return function () { a = (a + 0x6D2B79F5) >>> 0; var t = a; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }; }
  EVART.rng = rng;
  /* mount a canvas that fills el and redraws on resize; draw(ctx, w, h) works in CSS pixels */
  EVART.mount = function (el, draw) {
    var cv = document.createElement("canvas"), last = "";
    cv.setAttribute("aria-hidden", "true");
    el.appendChild(cv);
    function go(force) {
      var w = Math.max(1, Math.round(el.clientWidth)), h = Math.max(1, Math.round(el.clientHeight)), dpr = Math.min(3, window.devicePixelRatio || 1);
      var key = w + "x" + h + "@" + dpr; if (key === last && force !== true) return; last = key;
      cv.width = Math.round(w * dpr); cv.height = Math.round(h * dpr); cv.style.width = w + "px"; cv.style.height = h + "px";
      var ctx = cv.getContext("2d"); ctx.setTransform(dpr, 0, 0, dpr, 0, 0); ctx.clearRect(0, 0, w, h);
      draw(ctx, w, h);
    }
    go();
    var timer;
    if (window.ResizeObserver) new ResizeObserver(function () { clearTimeout(timer); timer = setTimeout(go, 80); }).observe(el);
    else window.addEventListener("resize", function () { clearTimeout(timer); timer = setTimeout(go, 80); });
    return go;
  };
  function rgba(c, a) { return "rgba(" + c[0] + "," + c[1] + "," + c[2] + "," + a + ")"; }
  var C = { bg: [5, 11, 8], mist: [169, 194, 180], gold: [255, 226, 122], amber: [255, 146, 56], ink: [233, 241, 235], trail: [95, 227, 161] };
  function blob(ctx, x, y, r, col, a, sx) {
    ctx.save(); ctx.translate(x, y); ctx.scale(sx || 1, 1);
    var g = ctx.createRadialGradient(0, 0, 0, 0, 0, r);
    g.addColorStop(0, rgba(col, a)); g.addColorStop(1, rgba(col, 0));
    ctx.fillStyle = g; ctx.beginPath(); ctx.arc(0, 0, r, 0, Math.PI * 2); ctx.fill(); ctx.restore();
  }
  /* one pine: stacked tiers with a slightly ragged outline */
  function pine(ctx, x, base, h, R) {
    var tiers = 4 + Math.floor(R() * 2), top = base - h;
    ctx.moveTo(x, top);
    for (var k = 0; k < tiers; k++) {
      var ty = top + h * (k + 1) / (tiers + 0.6), hw = h * (0.1 + 0.075 * (k + 1)) * (0.85 + R() * 0.3);
      ctx.lineTo(x + hw, ty); ctx.lineTo(x + hw * 0.42, ty - h * 0.03);
    }
    ctx.lineTo(x + h * 0.035, base); ctx.lineTo(x - h * 0.035, base);
    for (k = tiers - 1; k >= 0; k--) {
      ty = top + h * (k + 1) / (tiers + 0.6); hw = h * (0.1 + 0.075 * (k + 1)) * (0.85 + R() * 0.3);
      ctx.lineTo(x - hw * 0.42, ty - h * 0.03); ctx.lineTo(x - hw, ty);
    }
    ctx.closePath();
  }
  /* a treeline: rows of pines from back (lighter, misted) to front (darkest) */
  EVART.treeline = function (ctx, w, h, opt) {
    var R = rng(opt.seed || 7), layers = opt.layers || [
      { y: 0.80, hmin: 0.10, hmax: 0.22, col: "#0d1a14", gap: 0.55 },
      { y: 0.88, hmin: 0.13, hmax: 0.28, col: "#08120d", gap: 0.6 },
      { y: 0.99, hmin: 0.16, hmax: 0.36, col: "#030805", gap: 0.62 }
    ];
    var unit = opt.unit || Math.min(h, 520);
    layers.forEach(function (L, li) {
      ctx.fillStyle = L.col; ctx.beginPath();
      var x = -20;
      while (x < w + 20) {
        var th = unit * (L.hmin + R() * (L.hmax - L.hmin));
        pine(ctx, x, h * L.y + R() * unit * 0.02, th, R);
        x += th * (0.18 + R() * 0.22) * L.gap * 1.6;
      }
      ctx.fill();
      ctx.fillRect(0, h * L.y, w, h);
      /* mist between layers gives depth */
      if (li < layers.length - 1) {
        var g = ctx.createLinearGradient(0, h * (L.y - 0.16), 0, h * L.y + 4);
        g.addColorStop(0, rgba(C.mist, 0)); g.addColorStop(1, rgba(C.mist, opt.mist == null ? 0.07 : opt.mist));
        ctx.fillStyle = g; ctx.fillRect(0, h * (L.y - 0.16), w, h * 0.16 + 4);
      }
    });
  };
  /* THE FOG: the public mempool as fog, one mote of light per attacker transaction since the archive began
     (x = date, left to right). The ones the archive saw in public are lit, with a column of light down to the canopy.
     dots: [{d: "YYYY-MM-DD", lit: bool}], opt: {x0, x1 (fractions), seed, labels: [left, right], small} */
  EVART.fog = function (ctx, w, h, dots, opt) {
    opt = opt || {};
    var R = rng(opt.seed || 20230807);
    var sky = ctx.createLinearGradient(0, 0, 0, h);
    sky.addColorStop(0, "#030806"); sky.addColorStop(0.55, "#07120d"); sky.addColorStop(1, "#050b08");
    ctx.fillStyle = sky; ctx.fillRect(0, 0, w, h);
    var X0 = w * (opt.x0 == null ? 0.05 : opt.x0), X1 = w * (opt.x1 == null ? 0.95 : opt.x1);
    /* moonlight behind the fog, over the motes */
    blob(ctx, X0 + (X1 - X0) * 0.62, h * 0.30, Math.max(w, h) * 0.55, C.mist, 0.10, 1.4);
    blob(ctx, X0 + (X1 - X0) * 0.25, h * 0.55, Math.max(w, h) * 0.35, C.trail, 0.025, 1.6);
    /* fog banks: wide soft ellipses, densest in the band where the motes float */
    var n = Math.round(60 + w * h / 9000);
    for (var i = 0; i < n; i++) {
      var fx = X0 - 80 + R() * (X1 - X0 + 160), fy = h * (0.12 + R() * 0.62), fr = 40 + R() * Math.min(w, 900) * 0.18;
      blob(ctx, fx, fy, fr, C.mist, 0.012 + R() * 0.03, 1.8 + R() * 1.6);
    }
    var t0 = Date.parse(dots[0].d), t1 = Date.parse(dots[dots.length - 1].d);
    var bandT = h * 0.16, bandB = h * (opt.bandB || 0.70), sc = opt.small ? 0.8 : 1;
    var P = dots.map(function (d) {
      var x = X0 + (Date.parse(d.d) - t0) / (t1 - t0 || 1) * (X1 - X0) + (R() - 0.5) * 6;
      var y = bandT + Math.pow(R(), 0.85) * (bandB - bandT);
      return { x: x, y: y, lit: d.lit, r: R() };
    });
    /* dim motes first */
    P.forEach(function (p) {
      if (p.lit) return;
      blob(ctx, p.x, p.y, 7 * sc, C.mist, 0.07);
      ctx.fillStyle = rgba(C.mist, 0.34 + p.r * 0.2); ctx.beginPath(); ctx.arc(p.x, p.y, (1.15 + p.r * 0.6) * sc, 0, Math.PI * 2); ctx.fill();
    });
    /* the canopy sits over the motes' columns */
    var canopy = h * 0.80;
    P.forEach(function (p) {
      if (!p.lit) return;
      var col = ctx.createLinearGradient(0, p.y, 0, canopy);
      col.addColorStop(0, rgba(C.gold, 0.30)); col.addColorStop(1, rgba(C.gold, 0));
      ctx.fillStyle = col; ctx.fillRect(p.x - 1.1 * sc, p.y, 2.2 * sc, canopy - p.y);
      blob(ctx, p.x, canopy - 4, 26 * sc, C.gold, 0.08, 2.2);
      blob(ctx, p.x, p.y, 34 * sc, C.gold, 0.26);
      blob(ctx, p.x, p.y, 10 * sc, C.gold, 0.55);
      ctx.fillStyle = "#fff6cf"; ctx.beginPath(); ctx.arc(p.x, p.y, 2.6 * sc, 0, Math.PI * 2); ctx.fill();
    });
    EVART.treeline(ctx, w, h, { seed: 31, unit: Math.min(h, 560) * (opt.small ? 0.8 : 1) });
    /* low fog over the trees, then fade into the page */
    for (i = 0; i < 18; i++) blob(ctx, R() * w, h * (0.84 + R() * 0.1), 80 + R() * 220, C.mist, 0.02 + R() * 0.02, 3);
    var fade = ctx.createLinearGradient(0, h * 0.86, 0, h);
    fade.addColorStop(0, rgba(C.bg, 0)); fade.addColorStop(1, rgba(C.bg, 1));
    ctx.fillStyle = fade; ctx.fillRect(0, h * 0.86, w, h * 0.14 + 1);
    if (opt.labels) {
      ctx.font = "500 " + (opt.small ? 12.5 : 13.5) + "px 'Spline Sans Mono', ui-monospace, monospace";
      ctx.fillStyle = "rgba(233,241,235,.78)"; ctx.textBaseline = "alphabetic";
      ctx.textAlign = "left"; ctx.fillText(opt.labels[0], X0, h * 0.13);
      ctx.textAlign = "right"; ctx.fillText(opt.labels[1], X1, h * 0.13);
      ctx.strokeStyle = "rgba(233,241,235,.28)"; ctx.lineWidth = 1; ctx.beginPath();
      var mid = ctx.measureText(opt.labels[1]).width;
      ctx.moveTo(X0 + ctx.measureText(opt.labels[0]).width + 12, h * 0.13 - 4.5); ctx.lineTo(X1 - mid - 12, h * 0.13 - 4.5); ctx.stroke();
    }
    return P;
  };
  /* THE END BAND: the treeline at night with one lamp per race a bot won, placed by date */
  EVART.lamps = function (ctx, w, h, races, opt) {
    opt = opt || {};
    var R = rng(19);
    var sky = ctx.createLinearGradient(0, 0, 0, h);
    sky.addColorStop(0, "#050b08"); sky.addColorStop(0.6, "#08140f"); sky.addColorStop(1, "#050b08");
    ctx.fillStyle = sky; ctx.fillRect(0, 0, w, h);
    for (var i = 0; i < 40; i++) blob(ctx, R() * w, h * (0.3 + R() * 0.45), 60 + R() * 200, C.mist, 0.012 + R() * 0.025, 2.4);
    var X0 = w * (opt.x0 == null ? 0.06 : opt.x0), X1 = w * (opt.x1 == null ? 0.94 : opt.x1);
    var t0 = Date.parse(opt.from || "2021-01-01"), t1 = Date.parse(opt.to || "2026-12-31"), canopy = h * 0.74;
    var seenX = {};
    races.forEach(function (r) {
      var x = X0 + (Date.parse(r.d) - t0) / (t1 - t0) * (X1 - X0), k = Math.round(x / 8);
      seenX[k] = (seenX[k] || 0) + 1;
      var y = h * (0.20 + 0.12 * ((seenX[k] - 1) % 4)) + R() * h * 0.10;
      var col = r.alt ? C.gold : C.amber;
      var g = ctx.createLinearGradient(0, y, 0, canopy);
      g.addColorStop(0, rgba(col, 0.32)); g.addColorStop(1, rgba(col, 0));
      ctx.fillStyle = g; ctx.fillRect(x - 1, y, 2, canopy - y);
      blob(ctx, x, canopy - 2, 30, col, 0.10, 2.4);
      blob(ctx, x, y, 30, col, 0.30);
      blob(ctx, x, y, 9, col, 0.6);
      ctx.fillStyle = r.alt ? "#fff6cf" : "#ffe0c2"; ctx.beginPath(); ctx.arc(x, y, 2.4, 0, Math.PI * 2); ctx.fill();
    });
    EVART.treeline(ctx, w, h, { seed: 5, unit: Math.min(h, 420), layers: [
      { y: 0.80, hmin: 0.14, hmax: 0.26, col: "#0c1913", gap: 0.55 },
      { y: 0.90, hmin: 0.16, hmax: 0.34, col: "#07100c", gap: 0.6 },
      { y: 1.01, hmin: 0.2, hmax: 0.42, col: "#030805", gap: 0.62 }] });
    var fade = ctx.createLinearGradient(0, 0, 0, h * 0.14);
    fade.addColorStop(0, rgba(C.bg, 1)); fade.addColorStop(1, rgba(C.bg, 0));
    ctx.fillStyle = fade; ctx.fillRect(0, 0, w, h * 0.14);
    if (opt.labels) {
      ctx.font = "500 13px 'Spline Sans Mono', ui-monospace, monospace"; ctx.fillStyle = "rgba(233,241,235,.8)";
      for (var yr = 2021; yr <= 2026; yr++) {
        var xx = X0 + (Date.parse(yr + "-07-01") - t0) / (t1 - t0) * (X1 - X0);
        ctx.textAlign = "center"; ctx.fillText(String(yr), xx, h * 0.97);
      }
    }
  };

  /* the page itself (the og card loads this file for EVART only) */
  if (!document.body || !document.body.classList.contains("ev")) return;

  var $ = function (s) { return document.querySelector(s); };
  var esc = BVH.esc;
  BVH.chrome("evolution.html");

  /* evidence files */
  var F = {
    find: "downloads/evolution/findings_v2.txt",
    era: "downloads/evolution/by_era_v2.json",
    per: "downloads/evolution/per_exploit_v2.json",
    evo: "data/evolution.json",
    hs: "data/headline_stats.json",
    inc: "data/incidents.json"
  };
  function src(u, t) { return '<sup class="fn">' + BVH.rawA(u, "src", t || "Source file for this number") + "</sup>"; }
  var SF = function () { return src(F.find, "Evolution study findings (v2): the text that states this number"); };
  var SE = function () { return src(F.evo, "evolution.json: the aggregates this page draws"); };
  var SH = function () { return src(F.hs, "headline_stats.json: race-level totals"); };

  /* ---------- helpers ---------- */
  function S(tag, a, p, t) { return BVH.svg(tag, a, p, t); }
  function T(p, x, y, s, cls, anchor, extra) {
    var a = { x: x, y: y, "class": cls || "t-ax", "text-anchor": anchor || "start" };
    if (extra) for (var k in extra) a[k] = extra[k];
    return S("text", a, p, s);
  }
  function pct(x, d) { return x == null ? "n/a" : (+x).toFixed(d == null ? 1 : d) + "%"; }
  function pctT(x) { return x == null ? "n/a" : x >= 99 && x < 100 ? (+x).toFixed(2) + "%" : x > 0 && x < 0.1 ? "under 0.1%" : pctS(x); }
  function pctS(x) { return x == null ? "n/a" : (Math.abs(x - Math.round(x)) < 0.05 ? Math.round(x) : (+x).toFixed(1)) + "%"; }
  function num(x, d) { return x == null ? "n/a" : Number(x).toLocaleString("en-US", { minimumFractionDigits: d || 0, maximumFractionDigits: d || 0 }); }
  /* big ETH amounts in running text: rounded and said plainly, so "1,906.02" cannot be read as a decimal;
     the exact value always appears in the figure, caption or "How we know" next to it */
  function aboutEth(x) { return x >= 1000 ? "about " + num(Math.round(x)) + " ETH" : BVH.eth(x); }
  function wilson(k, n) {
    if (!n) return [0, 0];
    var z = 1.96, p = k / n, den = 1 + z * z / n, c = (p + z * z / (2 * n)) / den, h = z * Math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den;
    return [Math.max(0, 100 * (c - h)), Math.min(100, 100 * (c + h))];
  }
  function gapTxt(s) {
    if (s == null) return "n/a";
    if (s < 120) return Math.round(s) + " s";
    if (s < 7200) return (s / 60).toFixed(1) + " min";
    return (s / 3600).toFixed(1) + " h";
  }
  function month(iso) { var d = new Date(iso + "T00:00:00Z"); return d.toLocaleDateString("en-GB", { month: "short", year: "numeric", timeZone: "UTC" }); }
  function monthLong(iso) { var d = new Date(iso + "T00:00:00Z"); return d.toLocaleDateString("en-GB", { month: "long", year: "numeric", timeZone: "UTC" }); }
  function tms(iso) { return Date.parse(iso + "T00:00:00Z"); }
  function utcTime(s) { return s ? s.slice(11, 19) : "n/a"; }
  function short(r) { return (r.title || r.id).split(":")[0].trim(); }
  function incA(r, text) { return '<a href="incident.html?slug=' + encodeURIComponent(r.id) + '">' + esc(text || short(r)) + "</a>"; }
  function list(a) { return a.length < 2 ? a.join("") : a.slice(0, -1).join(", ") + " and " + a[a.length - 1]; }
  var WORDS = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"];
  function word(n) { return WORDS[n] || String(n); }
  function Word(n) { var s = word(n); return s.charAt(0).toUpperCase() + s.slice(1); }

  /* SVG chart mount: redraws at container width (ResizeObserver) and on theme change */
  function mount(el, label, draw) {
    var last = 0, timer;
    function go() {
      var w = Math.max(280, Math.floor(el.clientWidth || 600));
      if (w === last) return; last = w;
      el.innerHTML = "";
      var svg = S("svg", { width: w, role: "img", "aria-label": label }, el);
      var h = draw(svg, w);
      svg.setAttribute("height", h); svg.setAttribute("viewBox", "0 0 " + w + " " + h);
    }
    go();
    if (window.ResizeObserver) new ResizeObserver(function () { clearTimeout(timer); timer = setTimeout(go, 60); }).observe(el);
    else window.addEventListener("resize", function () { clearTimeout(timer); timer = setTimeout(go, 60); });
    BVH.onTheme.push(function () { last = 0; go(); });
  }
  function hit(parent, attrs, html) {
    attrs["class"] = "hit"; attrs.tabindex = 0; attrs.role = "img"; attrs["aria-label"] = html.replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim();
    var r = S(attrs.r != null ? "circle" : "rect", attrs, parent);
    BVH.tipFor(r, function () { return html; });
    return r;
  }
  function gridY(svg, y, x0, x1, ticks, fmt) {
    ticks.forEach(function (t) {
      S("line", { x1: x0, x2: x1, y1: y(t), y2: y(t), "class": t === 0 ? "g-base" : "g-grid" }, svg);
      T(svg, x0 - 8, y(t) + 4.5, fmt(t), "t-ax", "end");
    });
  }
  function halo(svg, id, color) {
    var d = S("defs", {}, svg), g = S("radialGradient", { id: id }, d);
    S("stop", { offset: "0", style: "stop-color:" + color + ";stop-opacity:.55" }, g);
    S("stop", { offset: ".45", style: "stop-color:" + color + ";stop-opacity:.16" }, g);
    S("stop", { offset: "1", style: "stop-color:" + color + ";stop-opacity:0" }, g);
    return "url(#" + id + ")";
  }

  /* ---------- build once on scroll ----------
     A chart below the fold is armed (its marks hidden) and builds once, in 600 ms or less, when it scrolls into view.
     Under reduced motion, without IntersectionObserver, inside a closed drawer, or when already on screen at load,
     nothing is armed and the chart is simply drawn in full. There are no play or pause buttons. */
  var RM = BVH.reduced();
  var BIO = !RM && "IntersectionObserver" in window ? new IntersectionObserver(function (es) {
    es.forEach(function (e) { if (e.isIntersecting) fireBuild(e.target); });
  }, { rootMargin: "0px 0px -15% 0px", threshold: 0 }) : null;
  function armBuild(el, onArm, onGo) {
    if (!BIO || !el || el.closest("details")) return;
    if (el.getBoundingClientRect().top < window.innerHeight * 0.85) return;
    el.classList.add("ev-arm"); el._onGo = onGo; if (onArm) onArm(); BIO.observe(el);
  }
  function fireBuild(el) {
    if (BIO) BIO.unobserve(el);
    if (!el.classList.contains("ev-arm")) return;
    el.classList.remove("ev-arm"); el.classList.add("ev-go");
    if (el._onGo) el._onGo();
    setTimeout(function () { el.classList.remove("ev-go"); }, 900);
  }
  window.addEventListener("beforeprint", function () { [].forEach.call(document.querySelectorAll(".ev-arm"), fireBuild); });
  /* per-mark stagger, read by the CSS build animations */
  function dl(ms) { return "--d:" + Math.round(ms) + "ms"; }

  /* tap to define (shared BVH.term, launch/v4/shared-api.txt) with this page's own wording */
  var DEFS = {};
  function term(text, key) { var d = DEFS[key || text.toLowerCase()]; return BVH.term("ev-" + BVH.slugify(d ? d[0] : text), text, d ? d[1].replace(/<[^>]*>/g, "").replace(/&ldquo;|&rdquo;/g, '"') : ""); }

  /* =====================================================================================
     HEADLINE COPY. Every sentence that makes a headline claim lives here, so it can be edited in one place
     (who lost each race follows the owner's 2026-10-23 wording, from data/incidents.json `beaten`). Numbers are filled
     from the data (d) at render time; keep the source marks (d.SE, d.SF, d.SH) next to the numbers.
     The page <title>, description and link-preview text are static in evolution.html <head>.
     ===================================================================================== */
  var COPY = {
    /* answer first: the takeaway sentence sits under the title */
    dek: function (d) { return COPY.endLede(d); },
    /* the decided series headline (owner, 2026-10-24), word for word: shared BVH.headline, counts from the data */
    headline: function () { return BVH.headline(INC); },
    open: function (d) {
      return "<p>In 2020, two researchers at Paradigm gave Ethereum a nickname: <a href=\"https://www.paradigm.xyz/writing/ethereum-is-a-dark-forest\" target=\"_blank\" rel=\"noopener\">a dark forest</a>. Anything sent to the network waited a few seconds in a public room where anyone could read it. Bots watched that room. If a transaction would make money, a bot copied it, sent the money to itself, and paid to go first.</p>";
    },
    open2: function (d) {
      return "<p>Part 3 asks whether the forest is still that dark. We followed a sample of " + num(d.ov.n) + " reproduced exploits on Ethereum mainnet from " + d.y0 + " to " + d.y1 + " and measured what attackers did differently." + d.SE + "</p>";
    },
    /* the 2x3 jump grid: [hash, value, colour, label of 8 words or fewer, chapter badge, source] */
    tiles: function (d) {
      return [
        ["#ch1", d.m.public + " of " + d.resolved, "gold", "resolved attacker transactions in our sample, seen since " + month(d.m.since), "Chapter 1", d.SF],
        ["#ch2", pctS(d.y25.constructor_pct), "atk", "of sampled " + d.y25.year + " exploits ran entirely in the constructor", "Chapter 2", d.SE],
        ["#ch3", gapTxt(d.y25.gap_s_median), "ink", "median " + d.y25.year + " wait for fresh, separately deployed contracts", "Chapter 3", d.SE],
        ["#ch4", pctS(d.bot.bribe_paid_pct_of_measured), "bot", "of traced bot transactions paid builders directly", "Chapter 4", d.SE],
        ["#ch5", d.dw.length + " of " + d.head.length, "gold", "races won by copying the attacker's setup", "Chapter 5", d.SH],
        ["#end", "Yes, darker for the bots", "text", "the archive saw few sampled attacker transactions", "The answer", ""]
      ];
    },
    endLede: function (d) { return "Yes. The forest got darker for the bots: since " + month(d.m.since) + " the public mempool archive saw very few sampled attacker transactions before they landed."; },
    close: function () { return "Bots still won some races by using exposed on-chain setup. Part 1 shows one of those races second by second. Part 2 shows what a bot does inside it."; }
  };

  /* the terms, page-specific wording (the closed "words this story uses" drawer, and the tap-to-define popovers) */
  var PRIMER = [
    ["Public mempool", "The waiting room. A transaction sent the normal way sits here for a few seconds before it lands in a block, and anyone can read it."],
    ["Private route", "Sending a transaction straight to a block builder, so it skips the waiting room. Nobody outside sees it until the block is out."],
    ["Builder and proposer", "Builders pack transactions into blocks and bid to have theirs used. Every 12 seconds one proposer, an Ethereum validator, takes one of those blocks."],
    ["Position 0", "The first transaction in a block. If two transactions try to take the same money, the earlier one gets it."],
    ["Front-running bot", "A program that copies a profitable transaction, points the payout at itself, and pays the builder to land first. In this series the profit is a live hack."],
    ["Attack contract", "A small program the attacker puts on chain to run the exploit. Deploying it and using it can be two steps, or one."],
    ["Constructor", "Code that runs once, at the moment a contract is created. An attack that runs entirely inside it is over before anyone can see it waiting."]
  ];
  /* the terms the charts and tables use (formerly a second glossary at the bottom of the page) */
  var PRIMER2 = [
    ["Seen in the public mempool", "The Mempool Dumpster archive recorded the transaction before its block was proposed. Not seen, when the archive saw many of the other transactions in the same block, is strong evidence that the transaction went privately to a builder."],
    ["Ordinary transactions in the same blocks", "The other transactions in each exploit's block. Their seen share is the control for how much the archive was catching that day."],
    ["Constructor-only exploit", "The attack runs inside the attack contract's constructor, so creating the contract and attacking are one transaction."],
    ["No watchable window", "A constructor-only exploit, an attack contract created inside the attack transaction, or one deployed in the same block as the attack."],
    ["Fresh deploy-to-attack gap", "Time from the block that created an attacker-owned contract to the block of the attack, for contracts created at most seven days before."],
    ["Paid the builder", "A direct ETH transfer to the block's fee recipient (the builder) inside the transaction. It is how a transaction buys its place in the block."],
    ["Deploy-window copy", "A bot used the attacker's own on-chain setup (a deployed contract, an upgrade or a prepare() call) before the attacker's own attack call landed."],
    ["PBS (proposer-builder separation)", "The system since the Merge in which builders assemble blocks and the proposer chooses one. &ldquo;Early PBS&rdquo; is September 2022 to 2023, &ldquo;mature PBS&rdquo; 2024 onward; elsewhere on this page they are the early and mature builder eras."],
    ["Sample", "Ethereum mainnet exploits reproduced in the DeFiHackLabs repository, with the sender of each listed transaction classified. It is a sample of public, reproduced incidents, not of all attacks."]
  ];
  PRIMER.concat(PRIMER2).forEach(function (t) { DEFS[t[0].toLowerCase()] = t; });
  DEFS["block builder"] = DEFS["builder and proposer"];

  /* a chapter opener: one big number (with its source) and one plain sentence (shared BVH.opener) */
  function opener(el, big, sentence, cls) {
    var m = /^([\s\S]*?)(<sup class="fn">([\s\S]*)<\/sup>)$/.exec(big);
    el.innerHTML = BVH.opener({ big: m ? m[1] : big, src: m ? m[3] : "", text: sentence, cls: cls });
  }

  var E, HS, INC, MK, META;
  Promise.all([BVH.json(F.evo), BVH.json(F.hs), BVH.json(F.inc), BVH.json("data/incident/makina-2026.json"), BVH.json("data/meta.json")])
    .then(function (r) { E = r[0]; HS = r[1]; INC = r[2]; MK = r[3]; META = r[4]; build(); })
    .catch(function (e) { var d = document.createElement("div"); d.className = "ev-col"; $("#main").insertBefore(d, $(".ev-short")); BVH.loadError(d, e); });

  function build() {
    var Y = {}; E.years.forEach(function (y) { Y[y.year] = y; });
    var m = E.measured, ov = E.overall, eras = E.eras, bot = E.bot_side.overall, vv = E.v1_vs_v2;
    var head = INC.filter(function (r) { return r.headline; });
    var dw = head.filter(function (r) { return r.race_type === "deploy-window-copy"; }).sort(function (a, b) { return a.date < b.date ? -1 : 1; });
    var dwY = dw.map(function (r) { return +r.date.slice(0, 4); }), dwMin = Math.min.apply(null, dwY), dwMax = Math.max.apply(null, dwY);
    var archive = E.dots.filter(function (d) { return d.d >= m.since && (d.exp === "public" || d.exp === "private-bundle"); })
      .sort(function (a, b) { return a.d < b.d ? -1 : a.d > b.d ? 1 : 0; });
    var seen = archive.filter(function (d) { return d.exp === "public"; });
    var lastSeen = seen[seen.length - 1];
    var raceDates = head.map(function (r) { return r.date; }).sort();
    var D = {
      m: m, ov: ov, bot: bot, head: head, dw: dw, y25: Y[2025], y26: Y[2026], e1: eras[0], resolved: m.public + m.private,
      y0: E.years[0].year, y1: E.years[E.years.length - 1].year, raceY0: raceDates[0].slice(0, 4), raceY1: raceDates[raceDates.length - 1].slice(0, 4),
      dwYears: dwMin === dwMax ? String(dwMin) : dwMin + " and " + dwMax, lastSeen: lastSeen,
      SE: SE(), SF: SF(), SH: SH(),
      headInc: head.map(function (r) { return r.slug; }).filter(function (s, i, a) { return a.indexOf(s) === i; }).length,
      wl: (function () { var c = BVH.beatenCounts(INC); return c.total === head.length ? c : null; })(),
      SB: src("data/beaten_party.json", "Who lost each headline race: verdict, note and evidence per race")
    };

    hero(archive, seen, m);
    $("#ev-dek").innerHTML = COPY.dek(D);
    tiles(D);
    story(D, head);
    $("#primer-box").innerHTML = BVH.glossary(PRIMER.concat(PRIMER2), { id: "words", intro: "The first " + word(PRIMER.length) + " are stops on the path into a block, drawn above; the rest are the words the charts and tables use." });
    route();

    ch1(m, D.resolved, archive, seen, lastSeen);
    ch2(Y, D.y25, D.y26);
    ch3(Y, D.y25, D.y26, eras, dw);
    ch4(Y, ov, bot, head);
    ch5(head, bot, vv, dw);
    ending(D, head, dw);
    tables(head);
    downloads();
    BVH.openHash();
  }

  /* ================= the short answer: a 2x3 grid that jumps to each chapter (shared BVH.tiles) ================= */
  function tiles(D) {
    $("#toc").innerHTML = BVH.tiles(COPY.tiles(D).map(function (t) {
      return { href: t[0], big: esc(t[1]), label: esc(t[3]), badge: esc(t[4]), cls: "t-" + t[2], src: t[5] ? t[5].replace(/^<sup class="fn">|<\/sup>$/g, "") : "" };
    }), { label: "The short answer, one tile per chapter" });
  }

  /* ================= the cold open, with the series headline and its 19-dot who-lost strip ================= */
  function story(D, head) {
    var html = COPY.open(D);
    if (D.wl) html += '<div class="ev-hl"><p class="ev-hlk">The series so far</p><p class="ev-hlt">' + COPY.headline(D) + D.SH + D.SB + "</p>" + BVH.lostStrip(INC, { href: BVH.raceHref }) + "</div>";
    html += COPY.open2(D);
    $("#open-story").innerHTML = html;
  }

  /* ================= opener art ================= */
  function hero(archive, seen, m) {
    var dots = archive.map(function (d) { return { d: d.d, lit: d.exp === "public" }; });
    var el = $("#hero-art");
    EVART.mount(el, function (ctx, w, h) {
      var wide = w >= 900;
      EVART.fog(ctx, w, h, dots, { x0: wide ? 0.5 : 0.06, x1: wide ? 0.96 : 0.94, small: !wide, bandB: wide ? 0.68 : 0.7, labels: [month(archive[0].d), month(archive[archive.length - 1].d)] });
    });
    $("#hero-note").innerHTML = "One light per resolved attacker transaction in our archive-era sample: " + archive.length + ". " + Word(seen.length) + " were seen before their block." + SE();
  }

  /* ================= primer: the two routes into a block ================= */
  function route() {
    mount($("#route"), "Diagram. A transaction can take the public route, waiting a few seconds in the public mempool where anyone, including bots, can read it, or the private route straight to a block builder. The builder packs a block; position 0 is the first slot. Every 12 seconds a proposer takes one block.", function (svg, w) {
      var wide = w >= 680;
      var hg = halo(svg, "ev-rt-halo", "var(--bot)");
      function box(x, y, bw, bh, title, sub, cls) {
        S("rect", { x: x, y: y, width: bw, height: bh, rx: 10, "class": "rt-box " + (cls || "") }, svg);
        T(svg, x + 14, y + 25, title, "t-labb");
        if (sub) [].concat(sub).forEach(function (s, i) { T(svg, x + 14, y + 46 + i * 18, s, "t-lab"); });
      }
      function arrow(d, dashed) {
        S("path", { d: d, "class": "rt-line" + (dashed ? " dash" : "") }, svg);
      }
      function head(x, y, dir) {
        var a = dir === "down" ? "M" + (x - 5) + " " + (y - 8) + "L" + x + " " + y + "L" + (x + 5) + " " + (y - 8) : "M" + (x - 8) + " " + (y - 5) + "L" + x + " " + y + "L" + (x - 8) + " " + (y + 5);
        S("path", { d: a, "class": "rt-line" }, svg);
      }
      function fogBox(x, y, bw, bh) {
        S("rect", { x: x, y: y, width: bw, height: bh, rx: bh / 2, "class": "rt-fog" }, svg);
        var R = rng(4);
        for (var i = 0; i < 30; i++) { var top = i % 2 === 0; S("circle", { cx: x + 30 + R() * (bw - 60), cy: top ? y + 7 + R() * 7 : y + bh - 14 + R() * 7, r: 1.4 + R() * 1.2, "class": "rt-mote" }, svg); }
        /* bots watching: three amber eyes of light at the edge of the fog */
        [0.3, 0.55, 0.8].forEach(function (f) { var cx = x + bw * f, cy = y + bh + 2; S("circle", { cx: cx, cy: cy, r: 14, fill: hg }, svg); S("circle", { cx: cx, cy: cy, r: 3.6, "class": "rt-bot" }, svg); });
      }
      function block(x, y, bw, bh) {
        var n = 18, cw = bw / n;
        for (var k = 0; k < n; k++) S("rect", { x: x + k * cw + 1, y: y, width: Math.max(1, cw - 2), height: bh, rx: 1.5, "class": k === 0 ? "rt-p0" : "rt-tx" }, svg);
      }
      if (wide) {
        var H = 290, bx = Math.round(w * 0.56), blx = Math.round(w * 0.78);
        box(0, 108, 150, 70, "A transaction", "someone sends it");
        /* public route */
        arrow("M150 130 C 175 130, 180 70, 205 70");
        var fx = 205, fw = bx - 30 - fx;
        fogBox(fx, 22, fw, 96);
        T(svg, fx + fw / 2, 52, "Public mempool", "t-labb", "middle");
        T(svg, fx + fw / 2, 74, "waits a few seconds, readable by anyone", "t-lab", "middle");
        T(svg, fx + fw / 2, 148, "front-running bots watch here", "t-lab rt-botlab", "middle");
        arrow("M" + (fx + fw) + " 70 C " + (bx - 10) + " 70, " + (bx - 14) + " 112, " + bx + " 118"); head(bx, 118);
        /* private route */
        arrow("M150 158 C 200 158, 200 236, 250 236 L " + (bx - 60) + " 236 C " + (bx - 20) + " 236, " + (bx - 20) + " 164, " + bx + " 160", true); head(bx, 160);
        T(svg, 262, 258, "private route: straight to a builder, unseen", "t-lab");
        box(bx, 96, blx - bx - 34, 86, "Block builder", ["packs a block,", "bids to have it used"]);
        arrow("M" + (blx - 34) + " 139 L " + (blx - 4) + " 139"); head(blx - 4, 139);
        var bw2 = w - blx - 2;
        T(svg, blx, 92, "The block", "t-labb");
        block(blx, 104, bw2, 70);
        T(svg, blx, 196, "position 0: first in line", "t-lab rt-botlab");
        S("path", { d: "M" + (blx + bw2 / 36) + " 176 L " + (blx + bw2 / 36) + " 182", "class": "rt-line" }, svg);
        T(svg, blx, 236, "Proposer: takes one", "t-lab");
        T(svg, blx, 255, "block every 12 seconds", "t-lab");
        return H;
      }
      /* phones: top to bottom */
      var cx = w / 2, y = 0;
      box(0, y, w, 62, "A transaction", "someone sends it"); y += 62;
      var lx = 0, lw = Math.round(w * 0.6);
      arrow("M" + (lw / 2) + " " + y + " L " + (lw / 2) + " " + (y + 26)); head(lw / 2, y + 26, "down");
      arrow("M" + (w - 40) + " " + y + " L " + (w - 40) + " " + (y + 196), true); head(w - 40, y + 196, "down");
      T(svg, w - 52, y + 54, "private", "t-lab", "end"); T(svg, w - 52, y + 72, "route,", "t-lab", "end"); T(svg, w - 52, y + 90, "unseen", "t-lab", "end");
      y += 28;
      fogBox(lx, y, lw, 110);
      T(svg, lw / 2, y + 38, "Public mempool", "t-labb", "middle");
      T(svg, lw / 2, y + 60, "readable by anyone", "t-lab", "middle");
      T(svg, lw / 2, y + 142, "bots watch here", "t-lab rt-botlab", "middle");
      y += 150;
      arrow("M" + (lw / 2) + " " + y + " L " + (lw / 2) + " " + (y + 18)); head(lw / 2, y + 18, "down");
      y += 18;
      box(0, y, w, 64, "Block builder", "packs a block, bids to have it used"); y += 64;
      arrow("M" + cx + " " + y + " L " + cx + " " + (y + 20)); head(cx, y + 20, "down"); y += 30;
      T(svg, 0, y + 14, "The block", "t-labb"); y += 24;
      block(0, y, w, 46); y += 46;
      T(svg, 0, y + 22, "position 0: first in line", "t-lab rt-botlab");
      T(svg, 0, y + 46, "Proposer: takes one block every 12 seconds", "t-lab");
      return y + 56;
    });
    $("#route-cap").innerHTML = "The public route waits in the " + term("mempool", "public mempool") + ", readable by bots. The " + term("private route") + " goes to a builder, hidden from public observers until the block is out.";
  }

  /* ================= 1. visibility ================= */
  function ch1(m, resolved, archive, seen, lastSeen) {
    var since = BVH.dateLong(m.since);
    var timesLess = Math.round(1 / m.relative_visibility);
    opener($("#ch1-open"), '<span class="gold">' + m.public + " of " + resolved + "</span>" + SF(), "in our resolved attacker sample, seen by the " + term("public mempool") + " archive since " + month(m.since) + ". Same-block ordinary transactions: <b>" + pct(m.control_seen_pct) + "</b>." + SE());

    var rows = [
      ["ctl", "Ordinary transactions", "in the same blocks", m.control_seen_pct, pct(m.control_seen_pct)],
      ["atk", "Attacker transactions", m.public + " of " + resolved, m.attacker_seen_pct, pct(m.attacker_seen_pct)]
    ];
    $("#c1-vs").innerHTML = rows.map(function (r) {
      return '<div class="ev-vsrow ' + r[0] + '"><div class="l"><b>' + r[1] + "</b><span>" + esc(r[2]) + '</span></div><div class="track" role="img" aria-label="' + r[1] + ": " + r[4] + ' seen in the public mempool"><div class="fill bx bx-x" style="width:' + r[3] + '%"></div></div><div class="v">' + r[4] + "</div></div>";
    }).join("") + '<div class="ev-vsaxis" aria-hidden="true"><div></div><div><span style="left:0">0%</span><span style="left:25%">25%</span><span style="left:50%">50%</span><span style="left:75%">75%</span><span style="left:100%">100%</span></div><div></div></div>';
    armBuild($("#c1-vs"));
    $("#f1cap").innerHTML = "Share seen by the archive before the block, " + since + " to Oct 2026. Sampled attackers were about " + timesLess + " times less visible; most likely they used private routes. If so, public-pool bots had no pending copy." + SF();

    /* lights over time: one dot per attacker transaction, stacked by month */
    $("#c1-gridt").textContent = archive.length + " resolved attacker transactions since the archive began, one dot each" + (m.unknown ? "; " + m.unknown + (m.unknown === 1 ? " more could not be resolved and is not drawn" : " more could not be resolved and are not drawn") : "");
    $("#c1-key").innerHTML = '<li><i class="k-lit"></i>seen in the public mempool (' + seen.length + ')</li><li><i class="k-dim"></i>never seen in public (' + (archive.length - seen.length) + ")</li>";
    var months = [], mi = {};
    (function () {
      var y = +archive[0].d.slice(0, 4), mo = +archive[0].d.slice(5, 7), ly = +archive[archive.length - 1].d.slice(0, 4), lm = +archive[archive.length - 1].d.slice(5, 7);
      while (y < ly || (y === ly && mo <= lm)) { var k = y + "-" + (mo < 10 ? "0" : "") + mo; mi[k] = months.length; months.push({ k: k, items: [] }); mo++; if (mo > 12) { mo = 1; y++; } }
    })();
    archive.forEach(function (d) { months[mi[d.d.slice(0, 7)]].items.push(d); });
    var maxN = Math.max.apply(null, months.map(function (x) { return x.items.length; }));
    var early = seen.filter(function (d) { return d.d < "2024-05-01"; });
    mount($("#c1-lights"), archive.length + " dots by month from " + month(archive[0].d) + " to " + month(archive[archive.length - 1].d) + ". " + seen.length + " are lit: " + seen.map(function (d) { return d.n + " (" + month(d.d) + ")"; }).join(", ") + ".", function (svg, w) {
      var wide = w >= 700, l = 4, r = 4, cw = (w - l - r) / months.length;
      var pitch = Math.max(6, Math.min(15, cw * 0.9)), rad = pitch * 0.36, top = wide ? 74 : 54, ph = maxN * pitch, base = top + ph;
      var hl = halo(svg, "ev-lit-halo", "var(--gold)");
      /* the "lights went out" bracket */
      var iMay = mi["2024-05"];
      if (iMay != null) {
        var xa = l + iMay * cw, xb = w - r;
        S("path", { d: "M" + xa + " " + (top - 18) + " L " + xa + " " + (top - 26) + " L " + xb + " " + (top - 26) + " L " + xb + " " + (top - 18), "class": "g-ann", fill: "none" }, svg);
        var after = seen.length - early.length;
        T(svg, xa + 8, top - 34, wide ? "From May 2024: " + word(after) + " sighting" + (after === 1 ? "" : "s") + " in " + (months.length - iMay) + " months" : "From May 2024: " + after + " sighting" + (after === 1 ? "" : "s"), "t-lab", "start");
        var xe = l + (mi[early[early.length - 1].d.slice(0, 7)] + 1) * cw, x0e = l + mi[early[0].d.slice(0, 7)] * cw;
        S("path", { d: "M" + x0e + " " + (top - 18) + " L " + x0e + " " + (top - 26) + " L " + xe + " " + (top - 26) + " L " + xe + " " + (top - 18), "class": "g-ann-lit", fill: "none" }, svg);
        if (wide) T(svg, x0e, top - 34, early.length + " sightings", "t-lab t-gold", "start");
      }
      months.forEach(function (mo, i) {
        var cx = l + (i + 0.5) * cw;
        mo.items.forEach(function (d, j) {
          var cy = base - (j + 0.5) * pitch;
          var st = dl(560 * i / months.length);
          if (d.exp === "public") {
            S("circle", { cx: cx, cy: cy, r: rad * 3.4, fill: hl, "class": "bx bx-f", style: st }, svg);
            S("circle", { cx: cx, cy: cy, r: rad * 1.12, "class": "lt-on bx bx-f", style: st }, svg);
            hit(svg, { cx: cx, cy: cy, r: Math.max(9, rad * 2) }, "<b>" + esc(d.n) + "</b>, " + BVH.dateLong(d.d) + "<br>seen in the public mempool before its block");
          } else S("circle", { cx: cx, cy: cy, r: rad, "class": "lt-off bx bx-f", style: st }, svg);
        });
        if (mo.k.slice(5) === "01" || i === 0) {
          S("line", { x1: l + i * cw, x2: l + i * cw, y1: base + 4, y2: base + 12, "class": "g-tick" }, svg);
          T(svg, l + i * cw + (i === 0 ? 0 : 4), base + 28, i === 0 ? (wide ? month(archive[0].d) : mo.k.slice(0, 4)) : mo.k.slice(0, 4), "t-ax", "start");
        }
      });
      if (lastSeen && wide) {
        var li = mi[lastSeen.d.slice(0, 7)], lx = l + (li + 0.5) * cw, ly = base - 0.5 * pitch;
        S("line", { x1: lx, x2: lx, y1: ly - rad * 2.2, y2: top - 2, "class": "g-ann-lit" }, svg);
        T(svg, lx + 6, top + 12, esc(lastSeen.n) + ", " + month(lastSeen.d) + ": the last one seen", "t-lab t-gold", "start");
      }
      return base + 40;
    });
    armBuild($("#c1-lights"));
    $("#f1bcap").innerHTML = "Each column is one month, " + month(archive[0].d) + " to " + month(archive[archive.length - 1].d) + ". The " + word(seen.length) + " that were seen are named under &ldquo;More from the data&rdquo;." + src(F.per, "per_exploit_v2.json: one row per exploit, with its mempool label");

    var Q = E.quarters;
    $("#ch1-side").innerHTML =
      "<p>The " + word(seen.length) + " that were seen: " + list(seen.map(function (d) { return esc(d.n) + " (" + month(d.d) + ")"; })) + "." + src(F.per, "per_exploit_v2.json: one row per exploit, with its mempool label") + "</p>" +
      "<p>The lights went out early. " + Word(early.length) + " of the " + word(seen.length) + " sightings came before May 2024. Since then the archive has caught one attacker in public: " + esc(lastSeen.n) + ", in " + monthLong(lastSeen.d) + ". No later sampled attacker transaction was seen by the archive." + SE() + "</p>" +
      "<p>Even the ones that were seen gave little warning: a median of " + m.lead_time_s_median.toFixed(1) + " seconds before their block." + SF() + "</p>" +
      "<p>The archive itself caught less over time, " + pct(Y_(2023).control_pct) + " of ordinary transactions in 2023 and " + pct(Y_(2026).control_pct) + " in 2026. That is why every comparison here is against the other transactions in the same blocks.</p>";

    mount($("#c1-q"), "Quarterly share seen in the public mempool: ordinary transactions stay between " + Math.round(Math.min.apply(null, Q.map(function (q) { return q.control_pct; }))) + " and " + Math.round(Math.max.apply(null, Q.map(function (q) { return q.control_pct; }))) + " percent, attacker transactions between 0 and " + Math.round(Math.max.apply(null, Q.map(function (q) { return q.attacker_pct; }))) + " percent.", function (svg, w) {
      var wide = w >= 640, l = 50, r = wide ? 16 : 8, t = 20, ph = wide ? 240 : 200, b = wide ? 76 : 48;
      var n = Q.length, bw = (w - l - r) / n;
      var x = function (i) { return l + (i + .5) * bw; }, y = BVH.lin(0, 100, t + ph, t);
      gridY(svg, y, l, w - r, [0, 25, 50, 75, 100], function (v) { return v + "%"; });
      S("polyline", { points: Q.map(function (q, i) { return x(i) + "," + y(q.control_pct); }).join(" "), fill: "none", stroke: "var(--mist)", "stroke-width": 2 }, svg);
      Q.forEach(function (q, i) { S("circle", { cx: x(i), cy: y(q.control_pct), r: 4, fill: "var(--mist)", stroke: "var(--bg)", "stroke-width": 2 }, svg); });
      S("polyline", { points: Q.map(function (q, i) { return x(i) + "," + y(q.attacker_pct); }).join(" "), fill: "none", stroke: "var(--atk)", "stroke-width": 2 }, svg);
      Q.forEach(function (q, i) { S("circle", { cx: x(i), cy: y(q.attacker_pct), r: 5, fill: "var(--atk)", stroke: "var(--bg)", "stroke-width": 2 }, svg); });
      T(svg, x(0) - 4, y(Q[0].control_pct) - 14, "ordinary transactions", "t-labb", "start");
      var qn = Q.length - 1;
      T(svg, x(qn) + 4, wide ? y(Math.max.apply(null, Q.slice(-3).map(function (q) { return q.attacker_pct; }))) - 16 : y(30), "attacker transactions", "t-labb t-atk", "end");
      Q.forEach(function (q, i) {
        var yr = q.q.slice(0, 4), qq = q.q.slice(4);
        if (wide) T(svg, x(i), t + ph + 20, qq, "t-ax", "middle");
        if (i === 0 || qq === "Q1") T(svg, x(i) - bw / 2 + 2, t + ph + (wide ? 40 : 22), wide ? yr : "'" + yr.slice(2), "t-lab", "start");
        if (wide) T(svg, x(i), t + ph + 64, q.public + "/" + (q.public + q.private), "t-ax", "middle");
        hit(svg, { x: x(i) - bw / 2, y: t, width: bw, height: ph }, "<b>" + yr + " " + qq + "</b><br>attacker transactions seen: " + q.public + " of " + (q.public + q.private) + " (" + pct(q.attacker_pct) + ")<br>ordinary transactions seen: " + pct(q.control_pct));
      });
      if (wide) T(svg, l - 8, t + ph + 64, "seen", "t-ax", "end");
      return t + ph + b;
    });
    $("#f1ccap").innerHTML = "Share seen in the public mempool archive, by quarter. Grey: the other transactions in the same blocks. Red: attacker transactions. Some quarters hold only a handful of exploits; on wide screens the row under the axis gives seen / total for each, and every quarter is in the tables at the end." + SE();

    var bc = HS.backrunner_comparison, bp = bc.backrunner_paper, ow = bc.ours_w6_v2_same_window_attacker_only;
    $("#ch1-how").innerHTML = "<p>The Mempool Dumpster archive starts on " + since + "; we have no mempool archive for earlier exploits, so they have in-block evidence only. A transaction counts as private when the archive covered that day, saw many other transactions in the same block, and never saw this one. That is strong evidence, not proof.</p><p>An independent study (BACKRUNNER) found " + bp.visible_in_public_mempool + " of " + bp.attack_txs + " attack transactions public from January 2023 to May 2024 (" + pct(bp.public_pct) + "); over the overlapping window we find " + ow.public + " of " + ow.resolved + " (" + pct(ow.public_pct) + ")." + SH() + "</p>";
  }
  var _Y = null;
  function Y_(yr) { if (!_Y) { _Y = {}; E.years.forEach(function (y) { _Y[y.year] = y; }); } return _Y[yr]; }

  /* ================= 2. constructor-only ================= */
  function ch2(Y, y25, y26) {
    var pre = E.years.filter(function (y) { return y.year >= 2020 && y.year < 2025; });
    var lo = Math.min.apply(null, pre.map(function (y) { return y.constructor_pct; })), hi = Math.max.apply(null, pre.map(function (y) { return y.constructor_pct; }));
    opener($("#ch2-open"), '<span class="atk">' + pctS(y25.constructor_pct) + "</span>" + SE(), "of sampled " + y25.year + " exploits (" + y25.constructor_k + " of " + y25.constructor_n + ") ran entirely in the attack contract's " + term("constructor") + ".", "op-atk");
    $("#ch2-more").innerHTML = "<p>In a two-step attack the contract sits on chain before it is used, and a bot can read it. In " + y25.year + ", " + pctS(y25.constructor_pct) + " of sampled exploits skipped that step: the attack ran inside the " + term("constructor") + ". Through 2024 the share had been between " + pctS(lo) + " and " + pctS(hi) + ". In " + y25.year + ", " + pctS(y25.same_tx_pct) + " deployed and attacked in the same transaction." + SE() + "</p>";

    $("#c2-shapes").innerHTML =
      '<div class="ev-shape"><h4>Two steps</h4><p>Deploy a contract, wait, then call it.</p>' +
      '<ol class="ev-track"><li class="ev-tx">Deploy the attack contract<small>lands in a block, readable by anyone</small></li><li class="ev-wait">the contract waits on chain, seconds to minutes</li><li class="ev-tx">Call attack()<small>usually never seen in the public pool</small></li></ol>' +
      '<p class="ev-copy yes">A copier can read the deployed contract and run the same plan first. That is how the Makina race was won.</p></div>' +
      '<div class="ev-shape one"><h4>One step, constructor-only</h4><p>The attack runs while the contract is being created.</p>' +
      '<ol class="ev-track"><li class="ev-tx">Create the contract; its constructor runs the whole attack<small>one transaction</small></li><li class="ev-wait none">no wait, nothing sits on chain</li><li class="ev-tx ghost">No second step<small>the attack is already over</small></li></ol>' +
      '<p class="ev-copy no">Nothing exists on chain until the attack has landed. If the transaction also skipped the public pool, nothing is available in the public mempool or in prior on-chain state for an outside copier.</p></div>';

    /* the forest: one tree per exploit; constructor-only trees burn ember, other no-window trees are ember outlines */
    var yrs = E.years.filter(function (y) { return y.year >= 2020; });
    yrs.forEach(function (y) { y._nw = Math.round(y.no_window_pct * y.n / 100); y._c = y.constructor_k; });
    $("#c2-key").innerHTML = '<li><i class="k-ctor"></i>constructor-only, one transaction</li><li><i class="k-nw"></i>other ways to leave no window</li><li><i class="k-tree"></i>left a window</li>';
    mount($("#c2-forest"), "One tree per exploit, by year from 2020. " + yrs.map(function (y) { return y.year + ": " + y.n + " exploits, " + y._c + " constructor-only (" + pctS(y.constructor_pct) + "), " + pctS(y.no_window_pct) + " left no window"; }).join("; "), function (svg, w) {
      var wide = w >= 700, n = yrs.length, gap = wide ? 22 : 6, gw = (w - gap * (n - 1)) / n;
      var per = wide ? 6 : (w < 420 ? 4 : 5), slot = gw / per, th = slot * 1.18, rows = Math.max.apply(null, yrs.map(function (y) { return Math.ceil(y.n / per); }));
      var top = wide ? 64 : 46, base = top + rows * th;
      yrs.forEach(function (d, gi) {
        var gx = gi * (gw + gap), hlY = d.year >= 2025;
        for (var k = 0; k < d.n; k++) {
          var row = Math.floor(k / per), col = k % per;
          var cx = gx + (col + 0.5) * slot, b = base - row * th, hh = th * 0.92, hw = slot * 0.42;
          var cls = k < d._c ? "tr-ctor" : k < d._nw ? "tr-nw" : "tr-tree";
          S("path", { d: "M" + cx + " " + (b - hh) + " L " + (cx + hw) + " " + (b - hh * 0.18) + " L " + (cx + hw * 0.2) + " " + (b - hh * 0.18) + " L " + (cx + hw * 0.2) + " " + b + " L " + (cx - hw * 0.2) + " " + b + " L " + (cx - hw * 0.2) + " " + (b - hh * 0.18) + " L " + (cx - hw) + " " + (b - hh * 0.18) + " Z", "class": cls + " bx bx-y", style: dl(gi * 300 / n + row * 14) }, svg);
        }
        var stackTop = base - Math.ceil(d.n / per) * th;
        T(svg, gx + gw / 2, stackTop - (wide ? 30 : 10), pctS(d.constructor_pct), hlY ? "t-big t-atk" : "t-labb", "middle");
        if (wide) T(svg, gx + gw / 2, stackTop - 10, pctS(d.no_window_pct) + " no window", "t-ax", "middle");
        T(svg, gx + gw / 2, base + 22, String(d.year), hlY ? "t-labb" : "t-lab", "middle");
        T(svg, gx + gw / 2, base + 40, wide ? d.n + " exploits" : "n=" + d.n, "t-ax", "middle");
        hit(svg, { x: gx, y: stackTop - 40, width: gw, height: base - stackTop + 40 }, "<b>" + d.year + "</b> (" + d.n + " exploits)<br>constructor-only: " + pct(d.constructor_pct) + " (" + d.constructor_k + " of " + d.constructor_n + ", 95% interval " + d.constructor_ci[0].toFixed(1) + " to " + d.constructor_ci[1].toFixed(1) + "%)<br>no watchable window at all: " + pct(d.no_window_pct));
      });
      S("line", { x1: 0, x2: w, y1: base + 1, y2: base + 1, "class": "g-base" }, svg);
      return base + 50;
    });
    armBuild($("#c2-forest"));
    var x0Years = E.years.filter(function (y) { return y.year < 2020; });
    var preN = x0Years.reduce(function (s, y) { return s + y.n; }, 0), preK = x0Years.reduce(function (s, y) { return s + y.constructor_k; }, 0);
    $("#f2bcap").innerHTML = "The big number over each year is the constructor-only share; " + (window.innerWidth >= 700 ? "the line under it is the share that left no window at all. " : "the no-window share is in the tables at the end. ") + "Trees are counted from the published shares. " + x0Years.map(function (y) { return y.year; }).join(" and ") + " (" + preN + " exploits, " + preK + " constructor-only) are left off. " + y26.year + " runs to October." + SE();
    $("#ch2-how").innerHTML = "<p>We traced the first attacker transaction of each exploit. Constructor-only means the attack calls happen inside the creation of the attack contract; the detection is a lower bound. Other ways to leave no window: an attack contract created inside the attack transaction, or deployed in the same block as the attack.</p><p>The jump from 2024 (" + pct(Y[2024].constructor_pct) + ", 95% interval " + Y[2024].constructor_ci[0] + " to " + Y[2024].constructor_ci[1] + "%) to 2025 (" + pct(y25.constructor_pct) + ", " + y25.constructor_ci[0] + " to " + y25.constructor_ci[1] + "%) is larger than the uncertainty. In " + y26.year + " so far the share is " + pct(y26.constructor_pct) + " (" + y26.constructor_k + " of " + y26.constructor_n + "). 2020 has only " + Y[2020].n + " exploits." + SF() + "</p>";
  }

  /* ================= 3. the window ================= */
  function ch3(Y, y25, y26, eras, dw) {
    opener($("#ch3-open"), gapTxt(y25.gap_s_median) + SE(), "sample median for separately deployed " + term("attack contracts", "attack contract") + " up to seven days old in " + y25.year + "; <b>" + gapTxt(eras[0].gap_s) + "</b> before 2021.", "op-ink");
    $("#ch3-more").innerHTML = "In our sample, yearly median waits fell from 2022. In " + y25.year + ", " + gapTxt(y25.gap_s_median) + " is about " + Math.round(y25.gap_s_median / 12) + " blocks of 12 seconds; the " + y26.year + " median was " + gapTxt(y26.gap_s_median) + ". Of " + y25.gap_n + " separately deployed contracts at most seven days old in " + y25.year + ", " + pctS(y25.same_block_deploy_pct) + " were deployed in the attack block." + SE();
    $("#ch3-watch").innerHTML = '<span class="k">Part 1</span><span class="t">Watch one of these blocks second by second: Makina, January 2026</span><span class="a" aria-hidden="true">&rarr;</span>';

    var yrs = E.years.filter(function (y) { return y.year >= 2020 && y.gap_s_median != null; });
    mount($("#c3-gap"), "Median deploy-to-attack gap by year: " + yrs.map(function (y) { return y.year + " " + gapTxt(y.gap_s_median); }).join(", "), function (svg, w) {
      var wide = w >= 640, l = wide ? 96 : 62, r = wide ? 130 : 70, t = 40, rh = wide ? 46 : 44, n = yrs.length, ph = n * rh;
      var maxMin = 16, x = BVH.lin(0, maxMin, l, w - r);
      [0, 4, 8, 12, 16].forEach(function (v) {
        S("line", { x1: x(v), x2: x(v), y1: t - 6, y2: t + ph, "class": v === 0 ? "g-base" : "g-grid" }, svg);
        T(svg, x(v), t + ph + 20, v + (v === 16 ? " min" : ""), "t-ax", "middle");
      });
      var xb = x(12 / 60);
      S("line", { x1: xb, x2: xb, y1: t - 18, y2: t + ph, "class": "g-ref" }, svg);
      T(svg, xb + 6, t - 22, "one block, 12 s", "t-lab t-gold", "start");
      yrs.forEach(function (d, i) {
        var cy = t + i * rh + rh / 2, mins = d.gap_s_median / 60, faint = d.gap_n < 10, g = S("g", faint ? { "class": "faint" } : {}, svg);
        var hl = d.year >= 2025;
        T(g, l - 14, cy + 1, String(d.year), hl ? "t-labb" : "t-lab", "end");
        T(g, l - 14, cy + 17, "n=" + d.gap_n, "t-ax", "end");
        var bh = 18, off = mins > maxMin, xe = off ? x(maxMin) : x(mins);
        S("rect", { x: l, y: cy - bh / 2, width: Math.max(3, xe - l), height: bh, rx: 3, "class": (hl ? "gb-hl" : "gb") + " bx bx-x", style: dl(i * 40) }, g);
        if (off) {
          /* off the linear scale: the bar is clipped at the axis end, and its value is printed on it */
          var chip = S("rect", { y: cy - bh / 2 - 3, height: bh + 6, rx: 4, "class": "gb-chip bx bx-f", style: dl(300) }, svg);
          var lab = T(svg, xe - 10, cy + 5, gapTxt(d.gap_s_median) + ", off scale", "t-labb bx bx-f", "end", { style: dl(300) });
          var tw = lab.getComputedTextLength ? lab.getComputedTextLength() : 110;
          chip.setAttribute("x", xe - tw - 18); chip.setAttribute("width", tw + 16);
        } else T(g, xe + 8, cy + 5, gapTxt(d.gap_s_median), hl ? "t-big" : "t-labb", "start");
        hit(svg, { x: 0, y: cy - rh / 2, width: w, height: rh }, "<b>" + d.year + "</b><br>median fresh deploy-to-attack gap: " + gapTxt(d.gap_s_median) + " (" + d.gap_s_median + " s)<br>from " + d.gap_n + " attacker-owned contracts deployed at most 7 days before<br>deployed in the attack's own block: " + pct(d.same_block_deploy_pct));
      });
      return t + ph + 30;
    });
    armBuild($("#c3-gap"));
    $("#f3acap").innerHTML = "Median over attacker-owned contracts created at most seven days before the attack; n is how many such contracts that year. Years with fewer than ten are drawn faint. The scale is linear; 2021's median runs off it, so its bar stops at the axis end and is labelled off scale. By era: " + eras.map(function (e) { return e.era.replace(/^E\d /, "").replace(/ \(.*$/, "") + " " + gapTxt(e.gap_s); }).join(", ") + "." + SE();

    /* Makina: the two blocks */
    var evs = MK.events || [];
    var dep = evs.filter(function (e) { return e.kind === "deploy" && /attack contract/.test(e.detail); })[0];
    var helper = evs.filter(function (e) { return e.kind === "deploy" && /helper/.test(e.detail); })[0];
    var btx = evs.filter(function (e) { return e.kind === "tx" && e.block === MK.block.number && /searcher/i.test(e.actor); })[0];
    var payout = (MK.txs || []).filter(function (x) { return x.role === "builder"; })[0];
    var gapS = dep && btx ? Math.round((Date.parse(btx.utc) - Date.parse(dep.utc)) / 1000) : null;
    var cb = MK.dataset_money.coinbase_eth;
    $("#ch3-mk").innerHTML = "Makina's attacker prepared for about " + (helper && dep ? Math.round((Date.parse(dep.utc) - Date.parse(helper.utc)) / 60000) : "n/a") + " minutes, then deployed the attack contract at " + utcTime(dep && dep.utc) + " UTC" + (dep ? src(dep.raw, "Trace of the deploy transaction") : "") + ". It never got to call it. In the next block, " + gapS + " seconds later, a searcher ran the same plan at position " + MK.bot_idx + " and paid " + aboutEth(cb) + " to the block builder for that spot." + (btx ? src(btx.raw, "Trace of the searcher's transaction") : "");

    mount($("#c3-mk"), "Two blocks, " + gapS + " seconds apart. Block " + (dep && dep.block) + ": the attacker deploys its attack contract. Block " + MK.block.number + ": a searcher's copy runs at position 0 of " + MK.block.ntx + " transactions and pays " + BVH.eth(cb) + " to the builder. The attacker's own call never lands.", function (svg, w) {
      var wide = w >= 700, strip = MK.strip || [], nt = MK.block.ntx || strip.length, gh = wide ? 120 : 84;
      var hlA = halo(svg, "ev-mk-halo", "var(--bot)"), y = 0;
      /* block 1: a gate with one ember sliver (we draw only the deploy, not the block's other transactions) */
      T(svg, 0, y + 18, "Block " + num(dep ? dep.block : null), "t-labb");
      T(svg, w, y + 18, (dep ? utcTime(dep.utc) : "") + " UTC", "t-lab", "end");
      y += 30;
      S("rect", { x: 0, y: y, width: w, height: gh * 0.5, rx: 6, "class": "mk-gate" }, svg);
      S("rect", { x: 14, y: y + 12, width: 6, height: gh * 0.5 - 24, rx: 2, "class": "mk-atk" }, svg);
      T(svg, 32, y + gh * 0.25 + 5, wide ? "the attacker deploys its attack contract, and waits" : "attacker deploys its contract", "t-lab");
      y += gh * 0.5 + 10;
      /* the 12 s */
      S("line", { x1: 17, x2: 17, y1: y, y2: y + 34, "class": "g-ref" }, svg);
      T(svg, 30, y + 23, "+" + gapS + " s: the next block", "t-lab t-gold");
      y += 46;
      /* block 2: the lit gate of 105 slivers */
      T(svg, 0, y + 18, "Block " + num(MK.block.number), "t-labb");
      T(svg, w, y + 18, utcTime(btx && btx.utc) + " UTC", "t-lab", "end");
      y += 30;
      var cw = w / nt;
      S("rect", { x: 0, y: y - 6, width: w, height: gh + 12, rx: 6, "class": "mk-gate" }, svg);
      for (var k = 0; k < nt; k++) {
        var role = (strip[k] || [])[2], hgt = gh * (0.52 + 0.4 * Math.abs(Math.sin(k * 1.7 + 0.4)));
        var cls = role === "bot" ? "mk-bot" : (k === nt - 1 && payout ? "mk-bld" : "mk-tx");
        if (role === "bot") hgt = gh;
        S("rect", { x: k * cw + cw * 0.18, y: y + gh - hgt, width: Math.max(1, cw * 0.64), height: hgt, rx: Math.min(2, cw * 0.3), "class": cls }, svg);
      }
      S("circle", { cx: cw / 2, cy: y + gh * 0.15, r: wide ? 46 : 30, fill: hlA }, svg);
      y += gh + 14;
      S("line", { x1: cw / 2, x2: cw / 2, y1: y - 6, y2: y + 6, "class": "g-ann" }, svg);
      T(svg, 0, y + 24, "position 0: the searcher's copy", "t-labb t-bot");
      T(svg, 0, y + 46, "paid " + BVH.eth(cb) + " to the builder", "t-lab");
      if (payout) {
        if (wide) { T(svg, w, y + 24, "last: the builder pays the proposer", "t-lab", "end"); T(svg, w, y + 46, BVH.eth(payout.value_eth), "t-lab", "end"); }
        else { T(svg, 0, y + 72, "last sliver: the builder pays the", "t-lab"); T(svg, 0, y + 92, "proposer " + BVH.eth(payout.value_eth), "t-lab"); }
      }
      y += wide ? 70 : 112;
      /* the call that never came */
      S("rect", { x: 0, y: y, width: Math.min(w, 420), height: 44, rx: 6, "class": "mk-never" }, svg);
      T(svg, 16, y + 28, "the attacker's own call: never sent", "t-lab t-atk");
      return y + 48;
    });
    $("#f3bcap").innerHTML = "Block " + num(MK.block.number) + " held " + MK.block.ntx + " transactions; each sliver is one (sliver heights are decoration). The copy sits first; " + (payout ? "the last transaction is the builder paying the proposer " + BVH.eth(payout.value_eth) + "." : "") + BVH.rawA(MK.block.raw.block, "block") + BVH.rawA(MK.block.raw.trace, "trace") + ' <a href="race.html">Part 1 plays this race second by second.</a>';

    var y0 = +dw[0].date.slice(0, 4), y1 = +dw[dw.length - 1].date.slice(0, 4);
    $("#ch3-mk2").innerHTML = "That is the deploy-window copy: the bot copies the attacker's setup instead of the attack. Of the " + INC.filter(function (r) { return r.headline; }).length + " races a bot won, " + dw.length + " worked this way, all in " + (y0 === y1 ? y0 : y0 + " and " + y1) + ". In each one the bot moved in the very next block." + SH();
    $("#c3-dw").innerHTML = dw.map(function (r) {
      return '<li><h4>' + incA(r) + '</h4><div class="meta">' + BVH.dateLong(r.date) + ", " + esc(r.bot.replace(/\s*\(.*$/, "")) + ", position " + r.bot_idx + "</div><p>" + esc(r.one_liner) + BVH.rawA(r.raw.trace, "trace") + "</p></li>";
    }).join("");
    $("#ch3-how").innerHTML = "<p>Times are block timestamps, so they move in 12-second steps. Gaps count only contracts the attacker owned and created within seven days; an attack contract created inside the attack transaction counts as zero. How the Makina searcher learned the plan is not visible on chain; its calldata matches the deployed contract, so the contract alone was enough.</p><p>Makina's searcher paid exactly " + BVH.eth(cb) + " to the builder." + BVH.rawA(MK.block.raw.trace, "trace") + "</p>";
  }

  /* ================= 4. paying the builder ================= */
  function ch4(Y, ov, bot, head) {
    opener($("#ch4-open"), '<span class="atk">' + pct(ov.bribe_pct) + '</span> <span class="vs">vs</span> <span class="bot">' + pct(bot.bribe_paid_pct_of_measured) + "</span>" + SE(), "of sampled attacker transactions paid " + term("block producers", "block builder") + " directly, versus " + bot.bribe_paid_n + " of " + bot.n_measured + " traced bot transactions in a separate sample.");

    var yrs = E.years.filter(function (y) { return y.year >= 2020; });
    mount($("#c4-att"), "Bars by year of the share of attacker transactions that paid the builder, between 0 and " + Math.round(Math.max.apply(null, yrs.map(function (y) { return y.bribe_pct; }))) + " percent, and one bar for bots at " + pct(bot.bribe_paid_pct_of_measured), function (svg, w) {
      var wide = w >= 640;
      if (!wide) {
        /* phones: one row per year, horizontal bars on the same linear 0 to 100% scale */
        var L = 64, R2 = 62, rh = 40, t0 = 8, rowsN = yrs.length + 1, xs = BVH.lin(0, 100, L, w - R2);
        [0, 50, 100].forEach(function (v) {
          S("line", { x1: xs(v), x2: xs(v), y1: t0, y2: t0 + rowsN * rh + 6, "class": v === 0 ? "g-base" : "g-grid" }, svg);
          T(svg, xs(v), t0 + rowsN * rh + 24, v + "%", "t-ax", v === 0 ? "start" : v === 100 ? "end" : "middle");
        });
        function hbar(i, v, k, n, cls, lab, sub, tip, faint) {
          var cy = t0 + i * rh + rh / 2 + (i === yrs.length ? 6 : 0), g = S("g", faint ? { "class": "faint" } : {}, svg), ci = wilson(k, n);
          S("rect", { x: L, y: cy - 8, width: Math.max(2, xs(v) - L), height: 16, rx: 3, "class": cls + " bx bx-x", style: dl(i * 45) }, g);
          if (!faint) S("line", { x1: xs(ci[0]), x2: xs(ci[1]), y1: cy, y2: cy, "class": "g-ci" }, g);
          T(g, L - 10, cy - 1, lab, "t-lab", "end");
          T(g, L - 10, cy + 15, sub, "t-ax", "end");
          T(g, w - R2 + 8, cy + 5, pctS(v), "t-labb", "start");
          hit(svg, { x: 0, y: cy - rh / 2, width: w, height: rh }, tip);
        }
        yrs.forEach(function (d, i) { hbar(i, d.bribe_pct, Math.round(d.bribe_pct * d.n / 100), d.n, "b-atk", String(d.year), "n=" + d.n, "<b>" + d.year + "</b>, attackers<br>paid the builder: " + pct(d.bribe_pct) + " of " + d.n + " exploits", d.n < 10); });
        hbar(yrs.length, bot.bribe_paid_pct_of_measured, bot.bribe_paid_n, bot.n_measured, "b-bot", "bots", "n=" + bot.n_measured, "<b>Bot transactions</b> in the same exploit records<br>paid the builder: " + bot.bribe_paid_n + " of " + bot.n_measured + " (" + pct(bot.bribe_paid_pct_of_measured) + ")<br>" + num(bot.bribe_eth_total, 2) + " ETH in total");
        return t0 + rowsN * rh + 34;
      }
      var l = 50, r = 8, t = 30, ph = 230, b = 52;
      var slots = yrs.length + 1.6, bw = (w - l - r) / slots, barW = Math.min(52, bw * .6);
      var y = BVH.lin(0, 100, t + ph, t);
      gridY(svg, y, l, w - r, [0, 25, 50, 75, 100], function (v) { return v + "%"; });
      function bar(cx, v, k, n, cls, lab, sub, tip, faint) {
        var g = S("g", faint ? { "class": "faint" } : {}, svg), ci = wilson(k, n);
        if (v > 0) S("rect", { x: cx - barW / 2, y: y(v), width: barW, height: y(0) - y(v), rx: 3, "class": cls + " bx bx-y", style: dl((cx - l) / (w - l) * 300) }, g);
        else S("rect", { x: cx - barW / 2, y: y(0) - 2, width: barW, height: 2, "class": cls }, g);
        if (!faint) {
          S("line", { x1: cx, x2: cx, y1: y(ci[0]), y2: y(ci[1]), "class": "g-ci" }, g);
          S("line", { x1: cx - 4, x2: cx + 4, y1: y(ci[1]), y2: y(ci[1]), "class": "g-ci" }, g);
          S("line", { x1: cx - 4, x2: cx + 4, y1: y(ci[0]), y2: y(ci[0]), "class": "g-ci" }, g);
        }
        T(g, cx, Math.min(y(v), y(faint ? v : ci[1])) - 8, pctS(v), "t-labb", "middle");
        T(g, cx, t + ph + 20, lab, "t-lab", "middle");
        T(g, cx, t + ph + 38, sub, "t-ax", "middle");
        hit(svg, { x: cx - bw / 2, y: t, width: bw, height: ph }, tip);
      }
      yrs.forEach(function (d, i) {
        var k = Math.round(d.bribe_pct * d.n / 100);
        bar(l + (i + .5) * bw, d.bribe_pct, k, d.n, "b-atk", wide ? String(d.year) : "'" + String(d.year).slice(2), "n=" + d.n, "<b>" + d.year + "</b>, attackers<br>paid the builder: " + pct(d.bribe_pct) + " of " + d.n + " exploits", d.n < 10);
      });
      var bx = l + (yrs.length + 1.1) * bw;
      S("line", { x1: bx - bw * .8, x2: bx - bw * .8, y1: t, y2: t + ph + 40, "class": "g-grid" }, svg);
      bar(bx, bot.bribe_paid_pct_of_measured, bot.bribe_paid_n, bot.n_measured, "b-bot", "bots", "n=" + bot.n_measured, "<b>Bot transactions</b> in the same exploit records<br>paid the builder: " + bot.bribe_paid_n + " of " + bot.n_measured + " (" + pct(bot.bribe_paid_pct_of_measured) + ")<br>" + num(bot.bribe_eth_total, 2) + " ETH in total");
      return t + ph + b;
    });
    armBuild($("#c4-att"));
    $("#f4acap").innerHTML = "A transaction can pay a block producer directly for priority; sampled attackers show no clear rise over time. Red: attacker transactions, by year of the exploit. Amber: every bot transaction we traced in the same exploit records (Sept 2022 to 2026), " + num(bot.bribe_eth_total, 2) + " ETH paid in total. Thin lines: 95% intervals. 2020 and 2021 have few exploits and are drawn faint." + SE() + " The bot bar comes from " + bot.n_measured + " transactions found in exploit records, so it says nothing about how common bots are." + SF();
    $("#ch4-mid").innerHTML = "In the races a bot won, the price of going first changed with the market. Before 2024 the winners paid builders almost nothing. Since then, most paid nearly everything they took, and some of it came back.";

    /* races: share of take to builder, drawn as columns of light */
    var BE = HS.block_producer_share.by_era_headline;
    var MERGE = "2022-09-15", PBS2 = "2024-01-01";
    var pts = head.filter(function (r) { return r.pct_to_builder != null; }).map(function (r) {
      var after = r.builder_refund_eth > 0 && r.gross_eth ? 100 * (r.paid_to_builder_eth - r.builder_refund_eth) / r.gross_eth : null;
      return { r: r, t: tms(r.date), v: r.pct_to_builder, after: after };
    });
    var bandsDef = [
      ["2021-01-01", MERGE, "mev-geth-2021-22", "Before the Merge", "Pre-Merge"],
      [MERGE, PBS2, "early-pbs-2022-23", "Early builder era", "Early"],
      [PBS2, "2026-12-31", "mature-pbs-2024-26", "Mature builder era", "Mature"]
    ];
    $("#c4-key").innerHTML = '<li><i class="k-col"></i>paid to the builder, share of the take</li><li><i class="k-ring"></i>after the builder refunded part of it</li>';
    mount($("#c4-races"), "Columns of light, one per race a bot won, by date: the share of the take paid to the block builder. Before 2024 every race paid under " + Math.ceil(Math.max.apply(null, pts.filter(function (p) { return p.r.date < PBS2; }).map(function (p) { return p.v; }))) + " percent; from 2024 the median race paid " + pct(BE["mature-pbs-2024-26"].median_row_pct) + ".", function (svg, w) {
      var wide = w >= 700, l = 50, r = wide ? 18 : 10, t = wide ? 60 : 26, ph = wide ? 300 : 250, b = wide ? 40 : 60;
      var x = BVH.lin(tms("2021-01-01"), tms("2026-12-31"), l, w - r), y = BVH.lin(0, 100, t + ph, t);
      var gA = S("linearGradient", { id: "ev-colg", x1: 0, y1: 1, x2: 0, y2: 0 }, S("defs", {}, svg));
      S("stop", { offset: "0", style: "stop-color:var(--bot);stop-opacity:.06" }, gA);
      S("stop", { offset: "1", style: "stop-color:var(--bot);stop-opacity:.75" }, gA);
      var hb = halo(svg, "ev-col-halo", "var(--bot)");
      bandsDef.forEach(function (bd, i) {
        var xa = x(tms(bd[0])), xb = x(tms(bd[1])), e = BE[bd[2]];
        if (i % 2 === 1) S("rect", { x: xa, y: wide ? t - 54 : t - 16, width: xb - xa, height: ph + (wide ? 54 : 16) + (wide ? 0 : 54), "class": "era-band" }, svg);
        if (wide) {
          T(svg, xa + 8, t - 34, bd[3], "t-labb", "start");
          T(svg, xa + 8, t - 14, e.rows + " race" + (e.rows === 1 ? "" : "s"), "t-ax", "start");
        } else T(svg, (xa + xb) / 2, t + ph + 50, bd[4], "t-ax", "middle");
      });
      gridY(svg, y, l, w - r, [0, 25, 50, 75, 100], function (v) { return v + "%"; });
      for (var yr = 2021; yr <= 2026; yr++) T(svg, x(tms(yr + "-07-01")), t + ph + 22, wide ? String(yr) : "'" + String(yr).slice(2), "t-ax", "middle");
      var xm = x(tms(MERGE));
      S("line", { x1: xm, x2: xm, y1: t, y2: t + ph, "class": "g-mark" }, svg);
      if (wide) { T(svg, xm + 8, y(62), "The Merge, Sep 2022:", "t-lab", "start"); T(svg, xm + 8, y(62) + 18, "builders and relays", "t-lab", "start"); T(svg, xm + 8, y(62) + 36, "start building blocks", "t-lab", "start"); }
      var cw = wide ? 5 : 3.5;
      pts.forEach(function (p) {
        var cx = x(p.t), cy = y(p.v), st = dl((cx - l) / (w - l - r) * 380);
        if (p.v > 0.5) S("circle", { cx: cx, cy: cy, r: wide ? 20 : 13, fill: hb, "class": "bx bx-f", style: st }, svg);
        S("rect", { x: cx - cw / 2, y: cy, width: cw, height: Math.max(1.5, y(0) - cy), rx: cw / 2, fill: "url(#ev-colg)", "class": "bx bx-y", style: st }, svg);
        if (p.after != null) S("circle", { cx: cx, cy: y(p.after), r: 6, "class": "c-ring bx bx-f", style: st }, svg);
        S("circle", { cx: cx, cy: cy, r: wide ? 5 : 4, "class": "c-top bx bx-f", style: st }, svg);
      });
      var labels = wide ? { "earningfarm-2022": [8, -14, "start"], "blueberry-2024": [-12, 5, "end"], "alkimiya-2025": [-12, 5, "end", "after"], "makina-2026": [0, -16, "middle"], "kelp-rseth-2026": [-12, -10, "end"], "punk-2021": [0, -16, "middle"] }
        : { "makina-2026": [-8, -12, "end"] };
      pts.forEach(function (p) {
        var L = labels[p.r.id]; if (!L) return;
        var vy = L[3] === "after" ? p.after : p.v;
        T(svg, x(p.t) + L[0], y(vy) + L[1], short(p.r).replace(/ (Protocol|SilicaPools|rsETH holder Safe)$/, "") + (L[3] === "after" ? " after refund " : " ") + pctT(vy), "t-labb", L[2]);
      });
      pts.forEach(function (p) {
        hit(svg, { cx: x(p.t), cy: y(p.v), r: 14 }, "<b>" + esc(short(p.r)) + "</b>, " + BVH.dateLong(p.r.date) + "<br>" + esc(p.r.bot) + "<br>paid to the builder: " + BVH.eth(p.r.paid_to_builder_eth) + " of " + BVH.eth(p.r.gross_eth) + " (" + pct(p.v) + ")" + (p.after != null ? "<br>after the builder's refund: " + pct(p.after) : ""));
      });
      return t + ph + b;
    });
    armBuild($("#c4-races"));
    $("#c4-eras").innerHTML = bandsDef.map(function (bd) { var e = BE[bd[2]]; return "<li><b>" + pctT(e.median_row_pct) + SH() + "</b><span>" + bd[3] + ": the median race paid the builder this share of its take (" + e.rows + " race" + (e.rows === 1 ? "" : "s") + ")</span></li>"; }).join("");
    $("#f4bcap").innerHTML = "Each column is one race a bot won: what its transaction paid the builder, including the priority fee, as a share of what it took. " + pts.length + " of " + head.length + " races are priced; " + head.filter(function (r) { return r.pct_to_builder == null; }).map(short).join(", ") + "'s take is not priced in ETH. The era medians are of these races." + SH() + " Builder eras follow the paper; the Merge is block 15,537,394.";

    var mb = BE["mature-pbs-2024-26"], paid = mb.sum_paid_eth, refund = paid - mb.after_refunds.sum_paid_minus_refund_eth;
    var pass = HS.loot.returns.headline_rows_returned_by_builder_or_proposer, toVictim = pass.sum_eth, kept = paid - refund - toVictim;
    var passNames = Object.keys(pass.rows).map(function (k) { var r = INC.filter(function (x) { return x.id === k; })[0]; return r ? short(r) : k; });
    $("#c4-split-t").innerHTML = "Where the money the winning bots paid builders since 2024 ended up (" + mb.rows + " races, " + num(paid, 2) + " ETH" + SH() + ")";
    var segs = [[toVictim, "var(--ret)", "back to the victims", "the builder passed it on (" + passNames.join(" and ") + ")"], [kept, "var(--bld)", "stayed with builders and proposers", "the price of going first"], [refund, "var(--bot)", "refunded to the bots", "by the same builder, in the same block"]];
    $("#c4-split").innerHTML = '<div class="ev-sbar" role="img" aria-label="' + segs.map(function (s) { return s[2] + " " + num(s[0], 2) + " ETH"; }).join(", ") + '">' + segs.map(function (s) { return '<div style="flex-grow:' + s[0].toFixed(3) + ';background:' + s[1] + '"></div>'; }).join("") + '</div><div class="k">' +
      segs.map(function (s) { return '<div style="border-color:' + s[1] + '"><b>' + pct(100 * s[0] / paid) + SH() + "</b><span>" + s[2] + "</span><small>" + num(s[0], 2) + " ETH, " + s[3] + "</small></div>"; }).join("") + "</div>";
    $("#f4ccap").innerHTML = "Payment before refunds, followed to where it landed. Blueberry's builder sent most of the bot's payment to the protocol's multisig in the same block; Makina's builder forwarded 1,023 ETH to an address that returned 920.7 ETH after a 10% bounty. The rest is what remains with builders and proposers under the flows we traced." + SH();
    $("#ch4-how").innerHTML = "<p>A payment to the builder is a direct ETH transfer to the block's fee recipient inside the transaction, read from the trace. In the races chart a ring shows the share after the builder refunded part of the payment to the bot, where it did.</p><p>An earlier pass of this study counted bot transactions as attackers and showed attackers paying builders more and more; with each sender classified, that trend disappears (" + pct(E.v1_vs_v2.coinbase_bribe_pct.v1) + " before the correction, " + pct(E.v1_vs_v2.coinbase_bribe_pct.v2) + " after). Two large attacker payments remain, Hopelend (263.9 ETH) and Ambient (33.9 ETH); both look like searcher transactions but nothing identifies them as bots." + SF() + "</p>";
  }

  /* ================= 5. the winning bots ================= */
  function ch5(head, bot, vv, dw) {
    var oi = HS.backrunner_comparison.ours_incident_set;
    var name = function (id) { id = id.replace("/", "--"); var r = INC.filter(function (x) { return x.id === id; })[0]; return r ? short(r) : id; };
    var seenNames = oi.seen.map(name), uniq = seenNames.filter(function (s, i) { return seenNames.indexOf(s) === i; }).map(function (s) {
      var k = seenNames.filter(function (x) { return x === s; }).length; return k > 1 ? (k === 2 ? "two" : k) + " " + s + " races" : s; });
    opener($("#ch5-open"), '<span class="gold">' + dw.length + " of " + head.length + "</span>" + SH(), "races were won by copying the attacker's on-chain setup. All " + dw.length + " came in " + (+dw[0].date.slice(0, 4) === +dw[dw.length - 1].date.slice(0, 4) ? dw[0].date.slice(0, 4) : dw[0].date.slice(0, 4) + " and " + dw[dw.length - 1].date.slice(0, 4)) + ".");
    var lede = "Among " + oi.headline_races_in_dumpster_era + " headline races on archive-covered days, " + oi.attacker_trigger_tx_seen_public_before_inclusion + " attacker transactions were seen in public. Unseen transactions may have used private routes. Winners sometimes used exposed on-chain setup." + SH();

    var atk0 = vv.tx_index_0_pct.v2;
    var rows = [
      ["At position 0, the top of the block", atk0, bot.tx_index_0_pct, bot.tx_index_0_n + " of " + bot.n_rows],
      ["Paid the block builder directly", E.overall.bribe_pct, bot.bribe_paid_pct_of_measured, bot.bribe_paid_n + " of " + bot.n_measured]
    ];
    function lab(v, cls, who, val, extra) {
      var right = v > 55;
      return '<span class="lab ' + cls + '" style="left:' + v + '%;' + (right ? "transform:translateX(-100%);text-align:right" : "") + '">' + who + " <b>" + val + "</b>" + (extra ? " (" + extra + ")" : "") + "</span>";
    }
    $("#c5-db").innerHTML = rows.map(function (r) {
      var lo = Math.min(r[1], r[2]), hi = Math.max(r[1], r[2]);
      return '<div class="ev-dbrow"><div class="l">' + r[0] + '</div><div class="ev-dbtrack" role="img" aria-label="' + r[0] + ": attackers " + pct(r[1]) + ", bots " + pct(r[2]) + '"><div class="base"></div><div class="span" style="left:' + lo + "%;width:" + (hi - lo) + '%"></div>' +
        '<div class="dot atk" style="left:' + r[1] + '%"></div><div class="dot bot" style="left:' + r[2] + '%"></div>' + lab(r[1], "up", "attackers", pct(r[1])) + lab(r[2], "dn", "bots", pct(r[2]), r[3]) + "</div></div>";
    }).join("") + '<div class="ev-dbaxis" aria-hidden="true"><div></div><div><span style="left:0">0%</span><span style="left:50%">50%</span><span style="left:100%">100%</span></div></div>';
    $("#f5acap").innerHTML = "Attackers: the first attacker transaction of each of " + E.overall.n + " exploits." + SE() + " Bots: the " + bot.n_rows + " bot transactions listed in the same records (" + bot.n_measured + " traced for payments; the other " + (bot.n_rows - bot.n_measured) + " are c0ffeebabe.eth rows we record by block and position only)." + SF();

    $("#c5-lanes-t").textContent = "The " + head.length + " races a bot won, by year and by what the bot copied";
    var years = []; for (var yv = +head.reduce(function (a, r) { return r.date < a ? r.date : a; }, "9999").slice(0, 4); yv <= 2026; yv++) years.push(yv);
    function chip(r) {
      return '<a class="ev-chip' + (r.race_type === "deploy-window-copy" ? " dw" : "") + '" href="incident.html?slug=' + encodeURIComponent(r.id) + '">' + esc(r.sub_label ? short(r) + ", " + r.sub_label : short(r)) + "<small>" + esc(BVH.botShort(r)) + ", " + month(r.date) + "</small></a>";
    }
    var html = '<div class="lrow lhd"><div class="yr"></div><div class="la"><i class="sw"></i>Copied a pending attack<small>' + head.filter(function (r) { return r.race_type === "beat-pending-attack"; }).length + ' races</small></div><div class="lb"><i class="sw dw"></i>Copied the attacker\'s setup<small>' + dw.length + " races</small></div></div>";
    years.forEach(function (yy) {
      var inY = head.filter(function (r) { return +r.date.slice(0, 4) === yy; }).sort(function (a, b) { return a.date < b.date ? -1 : 1; });
      var a = inY.filter(function (r) { return r.race_type === "beat-pending-attack"; }), b = inY.filter(function (r) { return r.race_type === "deploy-window-copy"; });
      html += '<div class="lrow"><div class="yr">' + yy + '</div><div class="la' + (a.length ? "" : " empty") + '">' + (a.map(chip).join("") || '<span class="ev-empty">none</span>') + '</div><div class="lb' + (b.length ? "" : " empty") + '">' + (b.map(chip).join("") || '<span class="ev-empty">none</span>') + "</div></div>";
    });
    $("#c5-lanes").innerHTML = html;
    $("#f5bcap").innerHTML = "Amber edge: the bot copied an attack transaction that was still pending, or landed ahead of it in the same block. Gold: the bot used the attacker's deployed contract, upgrade or prepare() call before the attacker's own attack. Each chip opens the race and its saved evidence." + SH();

    $("#ch5-side").innerHTML = "<p>" + lede + "</p>" +
      "<p>Look at the amber chips. Through " + (+dw[0].date.slice(0, 4) - 1) + ", every one of these races was won against a pending attack transaction. Since then, " + dw.length + " wins came from the attacker's setup: a contract, an upgrade or a prepare() call that landed one block before the attack.</p>" +
      "<p>The data cannot say why. It fits the first three chapters: when the attack itself is private and runs in one step, what a copier can still see is the setup that lands on chain first, and only for a block or two.</p>" +
      "<p>Of the races since the archive began, the attacker's transaction was seen in public in " + list(uniq) + ". In the other " + oi.not_seen.length + " the archive never saw the attacker's transaction before its block.</p>";

    var cbRows = head.filter(function (r) { return r.bot === "c0ffeebabe.eth"; }).sort(function (a, b) { return a.date < b.date ? -1 : 1; });
    /* the scoreboard rows for these races (shared BVH.scoreboard): public transaction facts only */
    $("#c5-cb").innerHTML = "<h3>Where c0ffeebabe.eth appears</h3><p>" + Word(cbRows.length) + " of the " + head.length + " races. Public transaction facts only: which block, which position, and where the money went; we do not analyse its bot. Tap a race for its numbers and saved sources.</p><div id=\"c5-sb\"></div>";
    BVH.scoreboard($("#c5-sb"), INC, {
      ids: cbRows.map(function (r) { return r.id; }), group: false, idPrefix: "sb-",
      extra: function (r) { return '<p class="sb-plain">' + BVH.dateLong(r.date) + ", block " + num(r.block) + ", position " + r.bot_idx + BVH.rawA(r.raw.block, "block") + BVH.rawA(r.raw.trace, "trace") + "</p>"; }
    });
    /* where no return was found within the saved checks, say so instead of "nothing returned"
       (the checks and their block range are in the incident file); the shared row already links the take's trace */
    cbRows.forEach(function (r) {
      var det = document.getElementById("sb-" + r.id); if (!det) return;
      if (r.fate_kind !== "kept") return;
      var fill = det.querySelector(".sb-fill");
      function patch() {
        var ret = fill.querySelector(".sk-ret"), keep = fill.querySelector(".sk-bot > span");
        if (ret && !ret.getAttribute("data-ev") && /nothing/i.test(ret.textContent)) {
          ret.setAttribute("data-ev", "1");
          ret.querySelector("span").innerHTML = "<b>No return found</b> " + BVH.rawA("data/incident/" + r.id + ".json", "basis", "Saved incident record: which later transactions were checked for a return");
        }
        if (keep && !keep.getAttribute("data-ev") && !/no return found/i.test(keep.textContent)) {
          keep.setAttribute("data-ev", "1");
          var b = keep.querySelector("b"), t = b && b.nextSibling;
          if (t && t.nodeType === 3) t.nodeValue = t.nodeValue.replace(/\s*$/, "; no return found ");
        }
      }
      new MutationObserver(patch).observe(fill, { childList: true, subtree: true });
    });

    $("#ch5-how").innerHTML = "<p>The " + head.length + " races are those confirmed on chain where a bot beat a pending attack or used the attacker's setup. Euler (2023), an earlier setup copy, is left out because the copier's identity is unresolved. Positions and payments come from each block's trace.</p><p>The bot-side counts come from bot transactions that happen to appear in exploit records, not from a census of bots. For c0ffeebabe.eth we describe public transactions only." + SH() + "</p>";
  }

  /* ================= the takeaway ================= */
  function ending(D, head, dw) {
    /* the lamps light in date order once, as the band scrolls in (drawn in full under reduced motion) */
    var races = head.map(function (r) { return { d: r.date, alt: r.race_type === "deploy-window-copy" }; }).sort(function (a, b) { return a.d < b.d ? -1 : 1; });
    var shown = races.length, el = $("#end-art");
    var redraw = EVART.mount(el, function (ctx, w, h) { EVART.lamps(ctx, w, h, races.slice(0, shown), { labels: true, x0: w < 700 ? 0.07 : 0.05, x1: w < 700 ? 0.93 : 0.95 }); });
    armBuild(el, function () { shown = 0; redraw(true); }, function () {
      var t0 = performance.now();
      (function step(now) {
        var n = Math.min(races.length, Math.ceil(races.length * (now - t0) / 600));
        if (n !== shown) { shown = n; redraw(true); }
        if (shown < races.length) requestAnimationFrame(step);
      })(t0);
    });
    $("#end-lede").textContent = COPY.endLede(D);
    $("#end-close").innerHTML = COPY.close(D);
    $("#end-note").innerHTML = "The picture above is drawn from the data: " + head.length + " lamps over the forest, one for each race a bot won, placed by date from 2021 to 2026. The " + word(dw.length) + " pale gold lamps are the races won by copying the attacker's setup." + SH();
  }

  /* ================= tables ================= */
  function tbl(title, hd, rows, note) {
    return "<section><h3>" + title + '</h3><div class="ev-tw"><table><thead><tr>' + hd.map(function (h) { return "<th>" + h + "</th>"; }).join("") + "</tr></thead><tbody>" +
      rows.map(function (r) { return "<tr>" + r.map(function (c) { return "<td>" + (c == null ? "n/a" : c) + "</td>"; }).join("") + "</tr>"; }).join("") + "</tbody></table></div>" + (note ? '<p class="ev-cap">' + note + "</p>" : "") + "</section>";
  }
  function tables(head) {
    $("#data-intro").innerHTML = "Each chart above is drawn from these rows. Attacker-side numbers come from " + BVH.rawA(F.evo, "evolution.json") + ", built from " + BVH.rawA(F.per, "per_exploit_v2.json") + " and " + BVH.rawA(F.era, "by_era_v2.json") + "; the " + BVH.rawA(F.find, "findings text") + " explains every column. Race-level numbers come from " + BVH.rawA(F.inc, "incidents.json") + " and " + BVH.rawA(F.hs, "headline_stats.json") + ".";
    var yrs = E.years;
    var t1 = tbl("By year, attacker transactions", ["year", "exploits", "constructor-only (95% interval)", "no window", "median gap (n)", "paid builder", "seen in public", "ordinary seen"],
      yrs.map(function (y) { return [y.year, y.n, pct(y.constructor_pct) + " (" + y.constructor_ci[0] + " to " + y.constructor_ci[1] + ")", pct(y.no_window_pct), y.gap_s_median == null ? "n/a" : gapTxt(y.gap_s_median) + " (" + y.gap_n + ")", pct(y.bribe_pct), y.public_pct == null ? "no archive" : pct(y.public_pct), y.control_pct == null ? "no archive" : pct(y.control_pct)]; }));
    var t2 = tbl("By quarter, since the archive began", ["quarter", "seen / total", "attacker seen", "ordinary seen", "constructor-only"],
      E.quarters.map(function (q) { return [q.q, q.public + " / " + (q.public + q.private) + (q.unknown ? " (+" + q.unknown + " unknown)" : ""), pct(q.attacker_pct), pct(q.control_pct), pct(q.constructor_pct)]; }));
    var t3 = tbl("By era", ["era", "exploits", "constructor-only", "seen in public", "ordinary seen", "median gap"],
      E.eras.map(function (e) { return [esc(e.era), e.n, pct(e.constructor_pct), e.public_pct == null ? "no archive" : pct(e.public_pct), e.control_pct == null ? "no archive" : pct(e.control_pct), gapTxt(e.gap_s)]; }));
    var hrows = head.slice().sort(function (a, b) { return a.date < b.date ? -1 : 1; }).map(function (r) {
      var after = r.builder_refund_eth > 0 && r.gross_eth ? pct(100 * (r.paid_to_builder_eth - r.builder_refund_eth) / r.gross_eth) : "";
      return [incA(r, short(r) + (r.sub_label ? ", " + r.sub_label : "")), r.date, r.race_type === "deploy-window-copy" ? "setup" : "pending", r.bot_idx, r.pct_to_builder == null ? "n/a" : pct(r.pct_to_builder), after, r.fate_kind];
    });
    var t4 = tbl("The " + head.length + " races a bot won", ["race", "date", "copied", "position", "to builder", "after refund", "funds"], hrows);
    $("#tables").innerHTML = t1 + t2 + t3 + t4;
  }
  function downloads() {
    var lst = (META.downloads || []).filter(function (x) { return /^downloads\/evolution\/.*v2/.test(x.path); });
    lst = lst.concat([{ path: F.evo, desc: "Aggregates drawn on this page" }, { path: F.hs, desc: "Race-level totals: payments to builders, returns" }, { path: F.inc, desc: "One row per race" }]);
    $("#data-sum").textContent = "4 tables and " + lst.length + " downloads, each linked to its file";
    $("#t-dl").innerHTML = "<thead><tr><th>download</th><th>what is in it</th></tr></thead><tbody>" + lst.map(function (x) {
      return '<tr><td><a href="' + esc(x.path) + '">' + esc(x.path.split("/").pop()) + "</a></td><td>" + esc(x.desc) + "</td></tr>";
    }).join("") + "</tbody>";
  }
})();
