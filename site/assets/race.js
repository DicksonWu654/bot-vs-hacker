/* Part 1, The race: Makina second by second, plus the gallery of other races.
   window.RaceViz holds the reusable visuals (the linear auction chart, the mini race cards); index.html uses them too.
   Every number is read from site/data at render time; sources are BVH.rawA links (numbered superscripts in prose). */
(function () {
  "use strict";
  var RV = (window.RaceViz = {});
  var S = BVH.svg, esc = BVH.esc;

  /* ---------- small formatters ---------- */
  function sgn(ms, d) { var s = ms / 1000, a = Math.abs(s); return (ms < 0 ? "\u2212" : ms > 0 ? "+" : "") + a.toFixed(d == null ? (a < 10 ? 2 : 1) : d) + " s"; }
  RV.sgn = sgn;
  function ethShort(x) {
    if (x == null) return "n/a";
    var a = Math.abs(x);
    if (a >= 1000) return Math.round(x).toLocaleString("en-US") + " ETH";
    if (a >= 100) return x.toFixed(1) + " ETH";
    if (a >= 10) return x.toFixed(1) + " ETH";
    if (a >= 1) return x.toFixed(2) + " ETH";
    if (a >= 0.01) return x.toFixed(2) + " ETH";
    return x.toPrecision(2) + " ETH";
  }
  RV.ethShort = ethShort;
  /* exact ETH with fixed decimals: E(1299.0499, 2) -> "1,299.05 ETH" */
  function E(x, d, unit) { if (x == null || isNaN(x)) return "n/a"; return x.toLocaleString("en-US", { minimumFractionDigits: d == null ? 2 : d, maximumFractionDigits: d == null ? 2 : d }) + (unit === false ? "" : " ETH"); }
  RV.E = E;
  /* time scale with an optional break: [t0, tb] gets `frac` of the width, [tb, t1] the rest; both linear */
  function timeScale(t0, tb, t1, r0, r1, frac) {
    if (tb == null || tb <= t0 || tb >= t1) { var l = BVH.lin(t0, t1, r0, r1); l.rb = null; return l; }
    var rb = r0 + (r1 - r0) * frac, a = BVH.lin(t0, tb, r0, rb), b = BVH.lin(tb, t1, rb, r1);
    var f = function (t) { return t <= tb ? a(t) : b(t); };
    f.rb = rb; f.tb = tb;
    return f;
  }
  function niceMax(v) {
    var steps = [1, 2, 2.5, 5, 10], p = Math.pow(10, Math.floor(Math.log10(v || 1)));
    for (var i = 0; i < steps.length; i++) if (steps[i] * p >= v) return steps[i] * p;
    return 10 * p;
  }
  function tickStep(max, n) {
    var raw = max / (n || 5), p = Math.pow(10, Math.floor(Math.log10(raw))), m = raw / p;
    return (m <= 1 ? 1 : m <= 2 ? 2 : m <= 2.5 ? 2.5 : m <= 5 ? 5 : 10) * p;
  }
  /* numbered source markers for prose */
  RV.footnotes = function () {
    var n = 0;
    return function (url, title) {
      if (!url) return "";
      n++;
      return '<sup class="fn">' + BVH.rawA(url, String(n), "Source " + n + ": " + (title || "saved raw response")) + "</sup>";
    };
  };

  var RELAY_NAMES = { flashbots: "Flashbots", ultrasound: "Ultra Sound", titan: "Titan", aestus: "Aestus", agnostic: "Agnostic", "bloxroute-regulated": "bloXroute", ethgas: "ETHGas" };
  function relayName(rs) { return rs && rs.length === 1 ? "the " + (RELAY_NAMES[rs[0]] || rs[0]) + " relay" : "a relay"; }
  /* ---------- the race's key moments, computed from the bid data ---------- */
  RV.events = function (D) {
    var A = D.auction || {}, B = A.bids || {}, W = A.winner || {}, rec = B.record || [], ser = B.series || [], ev = [];
    var dep = (D.events || []).filter(function (e) { return e.kind === "deploy" && /attack contract/i.test(e.detail || ""); })[0];
    if (dep && dep.t != null) {
      var size = /CREATE ([\d,]+) B/.exec(dep.detail || "");
      ev.push({ id: "deploy", t: dep.t - D.t0_ms, eth: null, raw: (dep.raws && dep.raws[0]) || dep.raw, rawTitle: "Trace of the deploy transaction",
        title: "The attack contract goes up", short: "contract deployed",
        text: "Block " + (dep.block || "").toLocaleString("en-US") + " includes the attacker's " + (size ? size[1] + "-byte " : "") + "contract. From this moment its code is public." });
    }
    if (ser.length) ev.push({ id: "first", t: B.first_ms, eth: ser[0][1], raw: A.raw && A.raw.bids, rawTitle: "Relay bid file for this slot",
      title: "Bidding opens for the next block", short: "first bid",
      text: "First bid: " + BVH.eth(ser[0][1]) + " from " + (B.builders[ser[0][2]] || "a builder") + ". An ordinary block pays very little." });
    var jump = null;
    for (var i = 1; i < rec.length; i++) { var r = rec[i][1] / Math.max(rec[i - 1][1], 1e-9); if (!jump || r > jump.r) jump = { r: r, i: i }; }
    if (jump && jump.r >= 20) {
      var j = rec[jump.i], pj = rec[jump.i - 1];
      ev.push({ id: "jump", t: j[0], eth: j[1], prev: pj[1], raw: A.raw && A.raw.bids, rawTitle: "Relay bid file for this slot",
        title: "The first big jump", short: "first jump",
        text: "A bid leaps from " + BVH.eth(pj[1]) + " to " + BVH.eth(j[1]) + " (" + (B.builders[j[2]] || "a builder") + "), about " + Math.round(jump.r).toLocaleString("en-US") + " times the best bid so far." });
    }
    var p10 = rec.filter(function (x) { return x[1] >= 10; })[0];
    if (p10 && (!jump || p10[0] > rec[jump.i][0])) ev.push({ id: "ten", t: p10[0], eth: p10[1], raw: A.raw && A.raw.bids, rawTitle: "Relay bid file for this slot",
      title: "A bidding war", short: "past 10 ETH",
      text: "Bids pass 10 ETH (" + BVH.eth(p10[1]) + "). Within a second they are in the tens of ETH." });
    var lead = W.builder ? rec.filter(function (x) { return B.builders[x[2]] === W.builder; })[0] : null;
    if (lead && W.t_ms != null && lead[0] < W.t_ms) ev.push({ id: "lead", t: lead[0], eth: lead[1], raw: A.raw && A.raw.bids, rawTitle: "Relay bid file for this slot",
      title: "The winning builder takes the lead", short: W.builder + " leads",
      text: "Builder " + W.builder + " takes the lead at " + BVH.eth(lead[1]) + " and keeps raising." });
    if (W.eth != null && W.t_ms != null) ev.push({ id: "win", t: W.t_ms, eth: W.eth, raw: A.raw && A.raw.delivered, rawTitle: "Relay record of the block delivered to the proposer (it has no timestamp)",
      rawHTML: BVH.bidsA(A, "Relay bid file: the winning block's bid, its value and arrival time") + BVH.rawA(A.raw && A.raw.delivered, "delivered", "Relay record of the block delivered to the proposer (it has no timestamp)"),
      title: "The winning builder sends its block to a relay", short: "winning bid",
      text: "The block that won, " + W.builder + "'s at " + E(W.eth) + ", was first bid to " + relayName(B.relays) + " at " + sgn(W.t_ms) + ". It holds the copy at position " + (D.bot_idx != null ? D.bot_idx : "0") + (W.relays && W.relays.length ? "; the delivery record is from " + W.relays.map(function (x) { return RELAY_NAMES[x] || x; }).join(", ") + ", which does not record when the proposer chose it" : "") + "." });
    var last = rec[rec.length - 1];
    if (last && W.t_ms != null && last[0] > W.t_ms && last[1] > W.eth) ev.push({ id: "late", t: last[0], eth: last[1], raw: A.raw && A.raw.bids, rawTitle: "Relay bid file for this slot",
      title: "Bids keep rising", short: "later bids",
      text: "Later bids reach " + E(last[1]) + " at " + sgn(last[0]) + ". The block delivered to the proposer is the " + E(W.eth) + " one." });
    ev.sort(function (a, b) { return a.t - b.t; });
    ev.forEach(function (e, k) { e.n = k + 1; });
    return ev;
  };

  /* ---------- the auction chart: LINEAR ETH axis against seconds from slot start (v3) ----------
     RV.auction(box, D, o) draws every relay bid as a column of light, the best bid so far, the winning bid and the
     race's key moments. The ETH axis is always linear with labelled ticks; it can rescale smoothly as the bids grow
     (start zoomed on the tiny early bids, end on the full scale plus a zoom inset). Driven by RV.warp (the player).
     o: { events (default RV.events(D)), compact, height, onStep(e, t), label }
     -> { update(t, {hold, holdFrac, playing, dt}), events, timed, tMin, tMax, frac(t), tAt(f), ymaxAt(t), full } */
  function fmtTick(v) { if (v === 0) return "0"; if (v >= 1000) return v.toLocaleString("en-US"); if (v >= 1) return String(+v.toFixed(2)); return String(+v.toPrecision(2)); }
  RV.fmtTick = fmtTick;
  function bsearch(arr, t) { var lo = 0, hi = arr.length; while (lo < hi) { var mid = (lo + hi) >> 1; if (arr[mid] <= t) lo = mid + 1; else hi = mid; } return lo; }
  RV.auction = function (box, D, o) {
    o = o || {};
    var A = D.auction, B = A.bids, W = A.winner || {}, winBid = W.eth_bid != null ? W.eth_bid : W.eth;
    var ev = o.events || RV.events(D), timed = ev.filter(function (e) { return e.t != null; });
    var winIdx = W.builder ? B.builders.indexOf(W.builder) : -1;
    var tMin = Math.min(B.first_ms, timed.length ? timed[0].t : B.first_ms, 0) - 600;
    var tMax = Math.max(B.last_ms, W.t_ms != null ? W.t_ms : -1e12, 0) + 350;
    var top = Math.max(B.max_eth || 0, winBid || 0) || 1, ystep = tickStep(top, 6), fullY = Math.ceil(top * 1.04 / ystep) * ystep;
    /* v4: the time axis is linear end to end (no break). The last seconds, where the bidding war happens, are shown
       again in a zoom inset on the same linear ETH scale (see "zoom inset" below). */
    var tBreak = null, F = null;
    /* bids drawn (the winning bid itself is the gold marker when its time is known) */
    var bids = B.series.filter(function (p) { return !((p[3] & 1) === 1 && W.t_ms != null); }).slice().sort(function (a, b) { return a[0] - b[0]; });
    var bidT = bids.map(function (p) { return p[0]; }), pmax = [], mx = 0;
    bids.forEach(function (p) { mx = Math.max(mx, p[1]); pmax.push(mx); });
    var rec = B.record.slice().sort(function (a, b) { return a[0] - b[0]; });
    var jumpE = ev.filter(function (e) { return e.id === "jump"; })[0];
    var yFloor = bids.length ? Math.max(bids[0][1] * 2, 1e-6) : fullY;
    /* the axis top that fits every bid seen by time t (linear, a little headroom); the full scale at the end */
    function ymaxAt(t) {
      if (t >= tMax - 1) return fullY;
      var k = bsearch(bidT, t), m2 = k ? pmax[k - 1] : 0;
      return Math.min(fullY, Math.max(yFloor, m2 * 1.22));
    }
    var st = { t: tMax, ymax: fullY, hold: null, holdFrac: 0, playing: false }, L = {};
    var call = document.createElement("div");
    call.className = "auc-call"; call.setAttribute("aria-live", "polite"); call.hidden = true;
    var uid = "au" + Math.random().toString(36).slice(2, 7);

    function draw() {
      box.innerHTML = ""; box.classList.add("auc-host");
      var w = Math.max(300, Math.round(box.clientWidth) || 700), narrow = w < 640, compact = o.compact || narrow;
      var band = 0;
      var H = band + (o.height || (compact ? (narrow ? 330 : 380) : 500));
      var m = { l: narrow ? 44 : 70, r: narrow ? 14 : 26, t: band + (compact ? 40 : 48), b: 48 };
      var x = timeScale(tMin, tBreak, tMax, m.l, w - m.r, F || 0.32);
      L = { w: w, H: H, m: m, x: x, narrow: narrow, compact: compact, band: band };
      var svg = L.svg = S("svg", { viewBox: "0 0 " + w + " " + H, width: w, height: H, class: "auc", role: "img",
        "aria-label": (o.label || "Builder bids for block " + D.block.number) + " on a linear ETH scale: " + B.n_total + " bids from " + sgn(B.first_ms) + " to " + sgn(B.last_ms) + " around the slot start. " + timed.map(function (e) { return sgn(e.t) + ": " + e.title + ". " + e.text; }).join(" ") }, box);
      var defs = S("defs", null, svg), cp = S("clipPath", { id: uid + "-plot" }, defs);
      S("rect", { x: m.l - 6, y: m.t - 18, width: w - m.r - m.l + 12, height: H - m.t + 18 }, cp);
      /* static: this block's slot, the slot labels, the time axis and its break */
      var x0 = x(0);
      S("rect", { x: x0, y: m.t - 30, width: Math.max(0, w - m.r - x0), height: H - m.b - m.t + 30, class: "auc-slot" }, svg);
      S("line", { x1: x0, x2: x0, y1: m.t - 30, y2: H - m.b, class: "inc-slotline" }, svg);
      var room = w - m.r - x0, slotTxt = narrow ? "slot starts" : "block " + D.block.number.toLocaleString("en-US") + "'s slot";
      S("text", room > slotTxt.length * 8 + 14 ? { x: x0 + 8, y: m.t - 14, class: "auc-slotlab" } : { x: x0 - 8, y: m.t - 14, "text-anchor": "end", class: "auc-slotlab" }, svg, slotTxt);
      if (!compact && x0 - m.l > 260) S("text", { x: Math.max(m.l, x(Math.max(tMin, -12000))) + 8, y: m.t - 14, class: "auc-slotlab inc-prevslot" }, svg, "block " + (D.block.number - 1).toLocaleString("en-US") + "'s slot");
      var ticks = [], t;
      if (x.rb != null) {
        for (t = Math.ceil(tMin / 3000) * 3000; t < tBreak - 1500; t += 3000) ticks.push(t);
        var stp = (tMax - tBreak) > 9000 && narrow ? 2000 : 1000;
        for (t = tBreak; t <= tMax; t += stp) ticks.push(t);
      } else { var xs = narrow ? (tMax - tMin > 8000 ? 4000 : 2000) : (tMax - tMin > 16000 ? 4000 : 2000); for (t = Math.ceil(tMin / xs) * xs; t <= tMax; t += xs) ticks.push(t); }
      ticks.forEach(function (t) {
        S("line", { x1: x(t), x2: x(t), y1: H - m.b, y2: H - m.b + 5, class: "auc-base" }, svg);
        S("text", { x: x(t), y: H - m.b + 21, "text-anchor": "middle", class: "auc-tick" }, svg, t === 0 ? "0" : (narrow ? sgn(t, 0).replace(" s", "") : sgn(t, 0)));
      });
      if (x.rb != null) {
        var bx = x.rb, by = H - m.b;
        S("rect", { x: bx - 5, y: by - 3, width: 10, height: 6, class: "auc-breakgap" }, svg);
        S("path", { d: "M" + (bx - 7) + " " + (by + 5) + "l5 -10M" + (bx + 1) + " " + (by + 5) + "l5 -10", class: "auc-break" }, svg);
        S("line", { x1: bx, x2: bx, y1: m.t - 30, y2: by - 6, class: "auc-breakline" }, svg);
        var ratio = (x(tBreak + 1000) - x(tBreak)) / (x(tMin + 1000) - x(tMin));
        var breakTxt = "from here, time is drawn " + ratio.toFixed(0) + "× wider";
      }
      /* bottom-row labels: the long forms only when both fit side by side (about 7.9px per mono character at 13px) */
      var axTxt = "seconds from the start of the slot, " + BVH.clock(D.t0_ms, false) + " UTC", CW = 7.9;
      if (narrow || (breakTxt && x.rb + 8 + CW * breakTxt.length + 24 > w - m.r - CW * axTxt.length)) axTxt = "seconds from slot start";
      if (breakTxt && !narrow) {
        if (x.rb + 8 + CW * breakTxt.length + 24 > w - m.r - CW * axTxt.length) breakTxt = "time " + ratio.toFixed(0) + "× wider from here";
        if (x.rb + 8 + CW * breakTxt.length + 24 <= w - m.r - CW * axTxt.length) S("text", { x: x.rb + 8, y: H - 4, class: "auc-axlab auc-breaklab" }, svg, breakTxt);
      }
      S("text", { x: w - m.r, y: H - 4, "text-anchor": "end", class: "auc-axlab" }, svg, axTxt);
      /* dynamic layers (their y follows the axis) */
      L.gGrid = S("g", { class: "auc-ygrid" }, svg);
      var plot = S("g", { "clip-path": "url(#" + uid + "-plot)" }, svg);
      L.gC = S("g", { class: "auc-cols" }, plot); L.gF = S("g", { class: "auc-refl", "aria-hidden": "true" }, svg);
      L.gD = S("g", { class: "auc-dots" }, plot); L.gW = S("g", { class: "auc-dots-w glow-s" }, plot);
      L.gR = S("g", { class: "auc-recs" }, plot); L.gRW = S("g", { class: "auc-recs-w glow" }, plot);
      L.bids = bids.map(function (p) {
        var isW = p[2] === winIdx, px = x(p[0]);
        return { t: p[0], eth: p[1], x: px, w: isW,
          col: S("rect", { x: (px - 0.6).toFixed(1), width: 1.2, class: isW ? "auc-col auc-col-w" : "auc-col" }, L.gC),
          rf: S("rect", { x: (px - 0.6).toFixed(1), width: 1.2, class: isW ? "auc-rf auc-rf-w" : "auc-rf" }, L.gF),
          dot: S("circle", { cx: px.toFixed(1), r: isW ? 2.6 : 2, class: isW ? "auc-dot auc-dot-w" : "auc-dot" }, isW ? L.gW : L.gD), on: null };
      });
      L.recs = rec.map(function (a, i) { var isW = winIdx >= 0 && a[2] === winIdx; return { a: a, b: rec[i + 1], el: S("path", { class: isW ? "auc-rec auc-rec-w" : "auc-rec" }, isW ? L.gRW : L.gR) }; });
      /* events: eth-independent parts are static, the rest are moved every frame */
      L.gE = S("g", { class: "auc-evs" }, svg);
      L.ev = ev.map(function (e) {
        var g = S("g", { class: "auc-ev auc-ev-" + e.id }, L.gE), ex = e.t != null ? x(e.t) : null, r = { e: e, g: g, x: ex };
        if (e.id === "deploy" || e.id === "seen") {
          S("line", { x1: ex, x2: ex, y1: m.t - 26, y2: H - m.b, class: e.id === "deploy" ? "auc-depline" : "auc-seen" }, g);
          if (e.id === "deploy") S("path", { d: "M" + ex + " " + (H - m.b - 8) + "l8 8-8 8-8-8z", class: "auc-dep" }, g);
          var left = e.id === "seen" && ex - 8 - (narrow ? 110 : 190) > m.l;
          S("text", { x: left ? ex - 9 : ex + 9, y: H - m.b - (e.id === "deploy" ? 62 : 14), "text-anchor": left ? "end" : "start", class: "auc-lab auc-lab-atk" }, g, narrow ? (e.id === "deploy" ? "deploy" : "seen in public") : e.short);
          r.badge = badge(g, e, "auc-num-atk"); place(r.badge, ex, H - m.b - 36);
        } else if (e.id === "slot") {
          r.badge = badge(g, e, "inc-num-slot"); place(r.badge, ex, m.t - 2);
        } else if (e.id === "win") {
          r.halo = S("circle", { cx: ex, r: 14, class: "auc-win-halo" }, g); r.dot = S("circle", { cx: ex, r: 7.5, class: "auc-win glow-s" }, g);
          r.l1 = S("text", { class: "auc-lab auc-lab-big" }, g, "winning bid " + E(e.eth)); r.l2 = S("text", { class: "auc-lab" }, g, (narrow ? trunc(W.builder || "", 16) : W.builder) + " at " + sgn(e.t));
          r.badge = badge(g, e, "auc-num-win");
        } else if (e.id === "late") {
          r.dot = S("circle", { cx: ex, r: 4.5, class: "auc-late" }, g);
          if (!compact) r.l1 = S("text", { "text-anchor": "end", class: "auc-lab" }, g, "highest later bid " + E(e.eth));
          r.badge = badge(g, e);
        } else if (e.id === "winline") {
          r.line = S("line", { x1: m.l, x2: w - m.r, class: "auc-winline" }, g);
          r.l1 = S("text", { x: narrow ? m.l + 8 : w - m.r - 8, "text-anchor": narrow ? "start" : "end", class: "auc-lab auc-lab-big inc-lab-win" }, g, "winning bid " + E(e.eth) + (narrow ? "" : ", time not recorded"));
        } else if (e.id === "nowin") {
          S("text", { x: w - m.r - 6, y: m.t + 22, "text-anchor": "end", class: "auc-lab inc-lab-nowin" }, g, narrow ? "no winning bid on record" : "winning bid not in the relay records");
        } else if (e.eth != null) {
          r.lead = S("line", { x1: ex, x2: ex, class: "auc-lead" }, g); r.badge = badge(g, e);
        }
        return r;
      });
      /* zoom inset (v4): the last seconds, where the bids climb, stretched in time on the SAME linear ETH scale
         (0 to the full axis top). Drawn when the war is squeezed into a small part of the linear time axis. */
      L.inset = null;
      var bigRec = rec.filter(function (r) { return r[1] > fullY * 0.02; })[0];
      var zx0 = bigRec ? Math.max(tMin, Math.floor((bigRec[0] - 200) / 500) * 500) : null, zx1 = tMax;
      if (o.inset !== false && zx0 != null && tMax - tMin > 6000 && (zx1 - zx0) < 0.45 * (tMax - tMin)) {
        var avail = x(zx0) - 40 - (m.l + 14), host = svg, inChart = !narrow && avail >= 300, ib, gi;
        var zLab = "Zoom: the last seconds, same ETH scale";
        if (inChart) {
          ib = { x: m.l + 14, y: m.t + 4, w: Math.min(560, avail), h: Math.min(230, H - m.t - m.b - 40) };
          gi = S("g", { class: "auc-inset" }, svg);
          S("rect", { x: ib.x, y: ib.y, width: ib.w, height: ib.h, rx: 8, class: "auc-insetbg" }, gi);
          S("line", { x1: ib.x + ib.w, y1: ib.y + ib.h, x2: x(zx1), y2: H - m.b - 6, class: "auc-zoomline" }, gi);
          S("line", { x1: ib.x + ib.w, y1: ib.y, x2: x(zx0), y2: H - m.b - 6, class: "auc-zoomline" }, gi);
          S("rect", { x: x(zx0), y: H - m.b - 6, width: Math.max(4, x(zx1) - x(zx0)), height: 6, class: "auc-zoomsrc" }, gi);
        } else {
          host = S("svg", { viewBox: "0 0 " + w + " 206", width: w, height: 206, class: "auc auc-inset2", role: "img", "aria-label": zLab + ", 0 to " + fmtTick(fullY) + " ETH: the bids from " + sgn(zx0) + " to " + sgn(B.last_ms) + "." }, box);
          ib = { x: 0, y: 4, w: w, h: 196 }; gi = S("g", { class: "auc-inset" }, host);
          S("rect", { x: ib.x + 0.5, y: ib.y, width: ib.w - 1, height: ib.h, rx: 8, class: "auc-insetbg" }, gi);
        }
        var im = { l: 46, r: 14, t: 34, b: 24 }, ix = BVH.lin(zx0, zx1, ib.x + im.l, ib.x + ib.w - im.r), iy = BVH.lin(0, fullY, ib.y + ib.h - im.b, ib.y + im.t);
        var dd = S("defs", null, host), cp2 = S("clipPath", { id: uid + "-zc" }, dd);
        S("rect", { x: ib.x + im.l - 3, y: ib.y + im.t - 8, width: ib.w - im.l - im.r + 6, height: ib.h - im.t - im.b + 11 }, cp2);
        S("text", { x: ib.x + 12, y: ib.y + 20, class: "auc-insettitle" }, gi, zLab);
        var ist = tickStep(fullY, 2);
        for (var iv = 0; iv <= fullY + 1e-9; iv += ist) { S("line", { x1: ib.x + im.l, x2: ib.x + ib.w - im.r, y1: iy(iv), y2: iy(iv), class: iv ? "auc-grid" : "auc-base" }, gi); S("text", { x: ib.x + im.l - 7, y: iy(iv) + 4, "text-anchor": "end", class: "auc-tick auc-tick-s" }, gi, iv ? fmtTick(+iv.toPrecision(6)) : "0"); }
        for (var it = Math.ceil(zx0 / 1000) * 1000; it <= zx1; it += 1000) S("text", { x: ix(it), y: ib.y + ib.h - 6, "text-anchor": "middle", class: "auc-tick auc-tick-s" }, gi, it === 0 ? "0" : sgn(it, 0));
        if (zx0 < 0 && zx1 > 0) S("line", { x1: ix(0), x2: ix(0), y1: ib.y + im.t - 6, y2: iy(0), class: "inc-slotline" }, gi);
        var gcz = S("g", { "clip-path": "url(#" + uid + "-zc)" }, gi), zel = [];
        bids.forEach(function (p) {
          if (p[0] < zx0 || p[0] > zx1) return;
          var iw = p[2] === winIdx, ipy = iy(p[1]), ih = iy(0) - ipy;
          if (ih > 1.5) zel.push([p[0], S("rect", { x: (ix(p[0]) - 0.6).toFixed(1), y: ipy.toFixed(1), width: 1.2, height: ih.toFixed(1), class: iw ? "auc-col auc-col-w" : "auc-col" }, gcz)]);
          zel.push([p[0], S("circle", { cx: ix(p[0]).toFixed(1), cy: ipy.toFixed(1), r: 2, class: iw ? "auc-dot auc-dot-w" : "auc-dot" }, gcz)]);
        });
        rec.forEach(function (a, k) {
          var b = rec[k + 1], aT = Math.max(a[0], zx0), bT = b ? b[0] : B.last_ms;
          if (bT < zx0 || a[0] > zx1) return;
          zel.push([a[0], S("path", { d: "M" + ix(aT).toFixed(1) + " " + iy(a[1]).toFixed(1) + "H" + ix(Math.min(zx1, bT)).toFixed(1) + (b && b[0] <= zx1 ? "V" + iy(b[1]).toFixed(1) : ""), class: (winIdx >= 0 && a[2] === winIdx) ? "auc-rec auc-rec-w" : "auc-rec" }, gcz)]);
        });
        if (W.t_ms != null && winBid != null && W.t_ms >= zx0) {
          var wx2 = ix(W.t_ms), wy2 = iy(winBid);
          zel.push([W.t_ms, S("circle", { cx: wx2.toFixed(1), cy: wy2.toFixed(1), r: 5, class: "auc-win glow-s" }, gi)]);
          var wr = wx2 > ib.x + ib.w * 0.6;
          zel.push([W.t_ms, S("text", { x: wr ? wx2 - 9 : wx2 + 9, y: wy2 + 4, "text-anchor": wr ? "end" : "start", class: "auc-lab" }, gi, E(W.eth))]);
        }
        L.inset = { g: gi, inChart: inChart, els: zel, zy1: fullY };
      }
      /* the cursor: a line of light at the current moment */
      L.cursor = S("line", { y1: m.t - 26, y2: H - m.b, class: "auc-cursor" }, svg);
      L.cursorLab = S("text", { y: H - m.b - 6, class: "auc-cursorlab" }, svg);
      L.leader = S("path", { class: "auc-callead" }, svg);
      if (narrow) {
        /* phones: the caption sits in its own band above the plot, sized for the longest caption so nothing jumps */
        box.insertBefore(call, svg); call.className = "auc-call auc-call-band"; call.hidden = false; call.style.minHeight = "";
        var mh = 0;
        timed.forEach(function (e) { call.innerHTML = '<span class="ac-n">' + e.n + '</span><span class="ac-t"><b>' + sgn(e.t) + "</b> " + esc(e.title) + '</span><span class="ac-x">' + esc(e.text) + '</span><span class="ac-hold"><i></i></span>'; mh = Math.max(mh, call.offsetHeight); });
        L.callMin = mh + "px"; lastCall = null;
      } else box.appendChild(call);
      render(true);
    }
    function badge(g, e, cls) {
      var c = S("g", { class: "auc-num" + (cls ? " " + cls : "") }, g);
      S("circle", { r: 10.5 }, c); S("text", { y: 4.5, "text-anchor": "middle" }, c, String(e.n));
      return c;
    }
    function place(b, x, y) { b.setAttribute("transform", "translate(" + x.toFixed(1) + "," + y.toFixed(1) + ")"); b._x = x; b._y = y; }

    /* draw the state: bids up to t, the axis at st.ymax */
    function render(snap) {
      var t = st.t, m = L.m, H = L.H, x = L.x, ym = st.ymax, y = BVH.lin(0, ym, H - m.b, m.t), y0 = y(0);
      /* y axis: linear, labelled ticks at every moment */
      L.gGrid.textContent = "";
      var ys = tickStep(ym, L.compact ? 4 : 5);
      for (var k = 0; k * ys <= ym * 1.0001; k++) {
        var v = +(k * ys).toPrecision(8), yy = y(v);
        S("line", { x1: m.l, x2: L.w - m.r, y1: yy, y2: yy, class: v === 0 ? "auc-base auc-floor" : "auc-grid" }, L.gGrid);
        S("text", { x: m.l - 9, y: yy + 4.5, "text-anchor": "end", class: "auc-tick" }, L.gGrid, fmtTick(v));
      }
      S("text", { x: m.l - 9, y: m.t - 14, "text-anchor": "end", class: "auc-tick auc-yunit" }, L.gGrid, "ETH");
      /* bids */
      L.bids.forEach(function (b) {
        var on = b.t <= t;
        if (on !== b.on) { b.col.style.visibility = b.rf.style.visibility = b.dot.style.visibility = on ? "" : "hidden"; b.on = on; }
        if (!on) return;
        var py = Math.max(m.t - 16, y(b.eth)), hh = y0 - py;
        b.col.setAttribute("y", py.toFixed(1)); b.col.setAttribute("height", Math.max(0, hh).toFixed(1));
        b.rf.setAttribute("y", (y0 + 1.5).toFixed(1)); b.rf.setAttribute("height", (hh > 1.5 ? Math.min(14, 3 + hh * 0.08) : 0).toFixed(1));
        b.dot.setAttribute("cy", py.toFixed(1));
      });
      /* best bid so far: the line grows with the cursor */
      L.recs.forEach(function (r) {
        var a = r.a, b = r.b;
        if (a[0] > t) { r.el.style.visibility = "hidden"; return; }
        r.el.style.visibility = "";
        var xe = b && b[0] <= t ? x(b[0]) : x(Math.min(t, b ? b[0] : B.last_ms));
        r.el.setAttribute("d", "M" + x(a[0]).toFixed(1) + " " + y(a[1]).toFixed(1) + "H" + xe.toFixed(1) + (b && b[0] <= t ? "V" + y(b[1]).toFixed(1) : ""));
      });
      /* events */
      var placed = [];
      /* the winning-bid line's label (untimed) is reserved first so numbered badges step around it */
      L.ev.forEach(function (r) {
        if (r.e.id !== "winline" || !r.l1) return;
        var wl0 = y(r.e.eth); if (wl0 < m.t - 10) return;
        var ly0 = L.narrow || wl0 - 8 < m.t + 4 ? wl0 + 18 : wl0 - 8, len = (r.l1.textContent || "").length * 7.9;
        var px0 = r.l1.getAttribute("text-anchor") === "end" ? L.w - m.r - 8 - len : m.l + 8;
        for (var px = px0; px <= px0 + len; px += 16) placed.push([px, ly0 - 4]);
      });
      L.ev.forEach(function (r) {
        var e = r.e, on = e.t == null || e.t <= t + 1;
        r.g.style.visibility = on ? "" : "hidden";
        if (!on) return;
        if (r.badge && (e.id === "deploy" || e.id === "seen" || e.id === "slot")) { placed.push([r.badge._x, r.badge._y]); return; }
        if (e.id === "win") {
          var wy = y(e.eth), right = r.x + 14 + 190 > L.w - m.r, below = wy - 14 < m.t + 4;
          r.halo.setAttribute("cy", wy); r.dot.setAttribute("cy", wy);
          var lx = right ? r.x - 15 : r.x + 15;
          [r.l1, r.l2].forEach(function (l) { l.setAttribute("x", lx); l.setAttribute("text-anchor", right ? "end" : "start"); });
          r.l1.setAttribute("y", below ? wy + 26 : wy - 11); r.l2.setAttribute("y", below ? wy + 43 : wy + 7);
          var by2 = below ? wy + 60 : wy - 28; place(r.badge, r.x, avoid(placed, r.x, by2)); placed.push([r.x, r.badge._y]);
        } else if (e.id === "late") {
          var ly = y(e.eth); r.dot.setAttribute("cy", ly);
          if (r.l1) { r.l1.setAttribute("x", r.x - 16); r.l1.setAttribute("y", ly - 14); }
          place(r.badge, r.x + 16, avoid(placed, r.x + 16, ly + 4)); placed.push([r.badge._x, r.badge._y]);
        } else if (e.id === "winline") {
          var wl = y(e.eth), vis = wl >= m.t - 10;
          r.line.style.visibility = r.l1.style.visibility = vis ? "" : "hidden";
          r.line.setAttribute("y1", wl); r.line.setAttribute("y2", wl); r.l1.setAttribute("y", L.narrow || wl - 8 < m.t + 4 ? wl + 18 : wl - 8);
        } else if (r.lead) {
          var ny = Math.max(m.t - 10, y(e.eth)), by = ny - 24;
          if ((e.id === "first" || e.id === "jump") && ny > H - m.b - 30) by = H - m.b - (e.id === "jump" ? 50 : 26);
          by = avoid(placed, r.x, Math.max(m.t - 2, by)); place(r.badge, r.x, by); placed.push([r.x, by]);
          r.lead.setAttribute("y1", ny); r.lead.setAttribute("y2", by + 10);
        }
      });
      /* the inset shows on the full scale, and whenever the reader stops on a scale too big for the first bids */
      if (L.inset) {
        var showIn = !L.inset.inChart || (!st.playing && !st.hold && t >= tMax - 1);
        L.inset.g.style.visibility = showIn ? "" : "hidden";
        L.inset.els.forEach(function (z) { z[1].style.visibility = z[0] <= t ? "" : "hidden"; });
      }
      var full = t >= tMax - 1, cx = x(Math.min(t, tMax));
      L.cursor.style.visibility = L.cursorLab.style.visibility = full ? "hidden" : "";
      L.cursor.setAttribute("x1", cx); L.cursor.setAttribute("x2", cx);
      var labRight = cx > L.w - 90;
      L.cursorLab.setAttribute("x", cx + (labRight ? -7 : 7)); L.cursorLab.setAttribute("text-anchor", labRight ? "end" : "start");
      L.cursorLab.textContent = sgn(t);
      callout(y);
    }
    function avoid(placed, cx, cy) {
      var tries = 0;
      while (tries < 8 && placed.some(function (p) { return Math.abs(p[0] - cx) < 22 && Math.abs(p[1] - cy) < 22; })) { cy -= 24; tries++; }
      return Math.max(L.m.t - 4, cy);
    }
    /* the caption sits next to its moment in the chart (on phones, in a band above the plot with a leader line) */
    var lastCall = null;
    function current() { var c = null; timed.forEach(function (e) { if (e.t <= st.t + 1) c = e; }); return c; }
    function callout(y) {
      var e = st.hold || current(), full = st.t >= tMax - 1 && !st.hold;
      if (o.onStep) o.onStep(e, st.t);
      L.svg.setAttribute("data-call", full || !e ? "" : e.id);
      if (full || !e) {
        L.leader.style.visibility = "hidden";
        if (L.narrow) {
          call.hidden = false; call.className = "auc-call auc-call-band is-idle"; call.style.minHeight = "";
          call.innerHTML = full ? '<span class="ac-t">' + (o.idleText || "The whole race, every bid on the full linear scale.") + '</span><span class="ac-x">Press play to watch it from the start, slowed down where it matters.</span>' : '<span class="ac-t">' + sgn(st.t) + '</span><span class="ac-x">Waiting for the first moment.</span>';
          lastCall = null;
        } else { call.hidden = true; lastCall = null; }
        return;
      }
      var key = e.n + "|" + (st.hold ? 1 : 0);
      if (key !== lastCall) {
        call.innerHTML = '<span class="ac-n' + (e.id === "deploy" || e.id === "seen" ? " ac-atk" : e.id === "win" ? " ac-win" : "") + '">' + e.n + '</span><span class="ac-t"><b>' + sgn(e.t) + "</b> " + esc(e.title) + '</span><span class="ac-x">' + esc(e.text) + '</span><span class="ac-hold" aria-hidden="true"><i></i></span>';
        lastCall = key;
      }
      call.hidden = false;
      call.className = "auc-call" + (L.narrow ? " auc-call-band" : "") + (st.hold ? " is-hold" : "");
      if (L.narrow) call.style.minHeight = L.callMin || "";
      var bar = call.querySelector(".ac-hold i"); if (bar) bar.style.transform = "scaleX(" + (st.hold ? st.holdFrac : 0).toFixed(3) + ")";
      /* the anchor point of the moment */
      var m = L.m, px = L.x(e.t), py = e.eth != null ? Math.max(m.t - 10, y(e.eth)) : (e.id === "slot" ? m.t : L.H - m.b - 40);
      var cw = call.offsetWidth, ch = call.offsetHeight;
      if (L.narrow) {
        var ax = Math.max(14, Math.min(L.w - 14, px));
        L.leader.setAttribute("d", "M" + ax.toFixed(1) + " 0V" + (py - 12).toFixed(1));
        L.leader.style.visibility = "";
        return;
      }
      /* prefer the empty sky above and to the left of the moment; inside the slot, stay left of the slot line so the
         bidding war itself stays visible */
      var x0 = L.x(0), re = px - 30;
      if (px > x0 + 20 && x0 - 12 - cw > m.l + 4) re = Math.min(re, x0 - 12);
      var leftSide = re - cw > m.l + 4, cl = leftSide ? re - cw : Math.min(px + 30, L.w - m.r - cw);
      var ct = Math.max(m.t - 26, Math.min(py - ch - 40, L.H - m.b - ch - 8));
      call.style.left = cl.toFixed(0) + "px"; call.style.top = ct.toFixed(0) + "px";
      var ex = leftSide ? cl + cw : cl, ey = Math.max(ct + 14, Math.min(ct + ch - 14, py));
      L.leader.setAttribute("d", "M" + ex.toFixed(1) + " " + ey.toFixed(1) + "L" + (px + (leftSide ? -11 : 11)).toFixed(1) + " " + py.toFixed(1));
      L.leader.style.visibility = "";
    }
    draw();
    var rt; window.addEventListener("resize", function () { clearTimeout(rt); rt = setTimeout(function () { if (Math.round(box.clientWidth) !== L.w) draw(); }, 120); });
    function frac(t) { if (F == null) return (t - tMin) / (tMax - tMin); return t <= tBreak ? F * (t - tMin) / (tBreak - tMin) : F + (1 - F) * (t - tBreak) / (tMax - tBreak); }
    function tAt(f) { if (F == null) return tMin + f * (tMax - tMin); return f <= F ? tMin + (f / F) * (tBreak - tMin) : tBreak + ((f - F) / (1 - F)) * (tMax - tBreak); }
    return {
      /* s: { hold: event|null, holdFrac, playing, dt: wall ms since the last frame (smooth axis) or undefined (snap) } */
      update: function (t, s) {
        s = s || {};
        st.t = Math.max(tMin, Math.min(tMax, t)); st.hold = s.hold || null; st.holdFrac = s.holdFrac || 0; st.playing = !!s.playing;
        var target = ymaxAt(st.t);
        if (s.dt == null || target < st.ymax) st.ymax = target;
        else st.ymax += (target - st.ymax) * (1 - Math.exp(-s.dt / 260));
        render();
      },
      events: ev, timed: timed, tMin: tMin, tMax: tMax, frac: frac, tAt: tAt, ymaxAt: ymaxAt, fullY: fullY,
      bidTimes: bidT, state: st
    };
  };
  function trunc(t, n) { t = String(t); return t.length > n ? t.slice(0, n - 1) + "…" : t; }

  /* ---------- the race player: an event-driven time-warp (v3) ----------
     RV.warp(ctrlBox, chart, o) builds the controls and plays chart from its first moment to its last.
     Quiet stretches run fast, playback slows to near real time or slower where the bids are dense and around each
     key moment, and it HOLDS on every key moment long enough to read its caption. The real clock and the current
     playback speed are always shown ("slowed 3x"), so the warp is honest. Pause, step and scrub work at any time.
     Reduced motion: loads on the complete end state with a big "Play the race from the start" button; motion only
     ever starts when the reader presses it. o: { t0 (slot start, ms epoch), autoplay: "inview", fast, slow } */
  RV.warp = function (box, chart, o) {
    o = o || {};
    var tMin = chart.tMin, tMax = chart.tMax, timed = chart.timed, reduced = BVH.reduced();
    var FAST = o.fast || 5, SLOW = o.slow || 0.3, STEP = 10;
    /* speed profile on a 10 ms grid: sim ms per wall ms */
    var n = Math.ceil((tMax - tMin) / STEP) + 1, sp = new Float32Array(n), bt = chart.bidTimes;
    var dens = new Float32Array(n);
    bt.forEach(function (t) { var i = Math.round((t - tMin) / STEP); for (var k = -10; k <= 10; k++) if (i + k >= 0 && i + k < n) dens[i + k] += 1; });
    for (var i = 0; i < n; i++) {
      var t = tMin + i * STEP, v = FAST / (1 + dens[i] / 1.6);
      timed.forEach(function (e) { var d = Math.abs(t - e.t); if (d < 700) v = Math.min(v, SLOW + (FAST - SLOW) * Math.pow(d / 700, 1.5)); });
      sp[i] = Math.max(SLOW * 0.85, Math.min(FAST, v));
    }
    /* smooth the slowness so the warp eases in and out */
    var slow = new Float32Array(n), R = 18;
    for (i = 0; i < n; i++) { var s = 0, c = 0; for (var k = -R; k <= R; k++) if (i + k >= 0 && i + k < n) { s += 1 / sp[i + k]; c++; } slow[i] = s / c; }
    function speedAt(t) { var j = Math.max(0, Math.min(n - 1, Math.floor((t - tMin) / STEP))); return 1 / slow[j]; }
    function holdMs(e) { return Math.max(2800, Math.min(7000, 900 + 36 * ((e.title || "").length + (e.text || "").length))); }

    var uid = "rp" + Math.random().toString(36).slice(2, 7);
    box.classList.add("rp");
    box.innerHTML =
      '<div class="rp-row">' +
        '<button type="button" class="rp-play" aria-describedby="' + uid + '-st"><svg viewBox="0 0 16 16" aria-hidden="true"><path class="i-play" d="M4 2.5v11l9-5.5z"/><path class="i-pause" d="M3.5 2.5h3v11h-3zM9.5 2.5h3v11h-3z"/></svg><span>Play the race from the start</span></button>' +
        '<button type="button" class="rp-step rp-prev" aria-label="Previous moment"><svg viewBox="0 0 16 16" aria-hidden="true"><path d="M3 2.5h2v11H3zM14 2.5v11L6 8z"/></svg></button>' +
        '<button type="button" class="rp-step rp-next" aria-label="Next moment"><svg viewBox="0 0 16 16" aria-hidden="true"><path d="M11 2.5h2v11h-2zM2 2.5v11L10 8z"/></svg></button>' +
        '<div class="rp-read" id="' + uid + '-st"><span class="rp-clock"></span><span class="rp-speed" data-mode="full"></span></div>' +
      '</div>' +
      '<div class="rp-track"><input type="range" class="rp-range" min="0" max="1000" step="1" aria-label="' + BVH.esc(o.label || "Moment in the race (drag to scrub)") + '"><div class="rp-stops"></div></div>';
    var bp = box.querySelector(".rp-play"), bl = bp.querySelector("span"), rg = box.querySelector(".rp-range"), clk = box.querySelector(".rp-clock"), spd = box.querySelector(".rp-speed"), stops = box.querySelector(".rp-stops");
    stops.innerHTML = timed.map(function (e) { return '<button type="button" class="rp-stop' + (e.id === "deploy" || e.id === "seen" ? " is-atk" : e.id === "win" ? " is-win" : "") + '" style="left:' + (100 * chart.frac(e.t)).toFixed(2) + '%" data-n="' + e.n + '" aria-label="Jump to moment ' + e.n + ": " + BVH.esc(e.title) + '"><span>' + e.n + "</span></button>"; }).join("");
    /* keep the moment buttons on the track at least 26 px apart (they sit at their moment's place, nudged if crowded) */
    function layoutStops() {
      var stopsW = stops.clientWidth; if (!stopsW) return;
      var bs = Array.prototype.slice.call(stops.children), xs = bs.map(function (b, k) { return chart.frac(timed[k].t) * stopsW; }), gap = 26;
      for (var k = 1; k < xs.length; k++) xs[k] = Math.max(xs[k], xs[k - 1] + gap);
      if (xs.length && xs[xs.length - 1] > stopsW) { xs[xs.length - 1] = stopsW; for (k = xs.length - 2; k >= 0; k--) xs[k] = Math.min(xs[k], xs[k + 1] - gap); }
      bs.forEach(function (b, k) { b.style.left = xs[k].toFixed(1) + "px"; });
    }
    layoutStops(); window.addEventListener("resize", layoutStops);
    var t = tMax, playing = false, hold = null, holdLeft = 0, holdTotal = 1, raf = 0, last = 0, started = false;
    var nextI = 0;
    function idxAfter(tt) { for (var j = 0; j < timed.length; j++) if (timed[j].t > tt + 0.5) return j; return timed.length; }
    function label() {
      var atEnd = t >= tMax - 1;
      bl.textContent = playing ? "Pause" : atEnd ? "Play the race from the start" : started ? "Resume" : "Play";
      box.classList.toggle("is-playing", playing); box.classList.toggle("is-end", atEnd && !playing);
      bp.setAttribute("aria-pressed", playing ? "true" : "false");
    }
    function readout() {
      var abs = o.t0 != null ? BVH.clock(o.t0 + t) + " UTC" : "";
      clk.innerHTML = (abs ? "<b>" + abs.replace(" UTC", "") + "</b> UTC " : "") + '<span class="rp-rel">' + sgn(t) + " from the slot start</span>";
      var mode, txt;
      if (hold) { mode = "hold"; txt = "Paused on moment " + hold.n + " of " + timed.length + " to read it"; }
      else if (playing) {
        var v = speedAt(t);
        if (v > 1.2) { mode = "fast"; txt = "Sped up " + (v >= 2 ? Math.round(v) : v.toFixed(1)) + "× (quiet)"; }
        else if (v < 0.85) { mode = "slow"; txt = "Slowed " + (1 / v >= 2 ? Math.round(1 / v) : (1 / v).toFixed(1)) + "×"; }
        else { mode = "real"; txt = "Real time"; }
      } else if (t >= tMax - 1) { mode = "full"; txt = "The whole race"; }
      else { mode = "paused"; txt = "Paused"; }
      spd.setAttribute("data-mode", mode); spd.textContent = txt;
      Array.prototype.forEach.call(stops.children, function (b) { var k = +b.getAttribute("data-n"), e = timed[k - 1]; b.classList.toggle("is-past", !!e && e.t <= t + 1); b.classList.toggle("is-cur", !!hold && hold.n === k); });
    }
    function sync(dt) {
      chart.update(t, { hold: hold, holdFrac: hold ? 1 - holdLeft / holdTotal : 0, playing: playing, dt: dt });
      rg.value = Math.round(1000 * chart.frac(t)); label(); readout();
    }
    function frame(ts) {
      if (!playing) return;
      var dt = last ? Math.min(100, ts - last) : 16; last = ts;
      var wall = dt;
      if (hold) {
        holdLeft -= wall;
        if (holdLeft > 0) { sync(dt); raf = requestAnimationFrame(frame); return; }
        wall = -holdLeft; hold = null;
      }
      while (wall > 0 && t < tMax) {
        var v = speedAt(t), cellEnd = tMin + (Math.floor((t - tMin) / STEP) + 1) * STEP, nxt = nextI < timed.length ? timed[nextI].t : Infinity;
        var lim = Math.min(cellEnd, nxt, tMax), need = (lim - t) / v;
        if (need <= wall) { wall -= need; t = lim; } else { t += wall * v; wall = 0; }
        if (nextI < timed.length && t >= timed[nextI].t) { hold = timed[nextI]; nextI++; holdTotal = holdLeft = holdMs(hold); break; }
      }
      if (t >= tMax && !hold) { t = tMax; playing = false; sync(); return; }
      sync(dt); raf = requestAnimationFrame(frame);
    }
    function play() {
      if (t >= tMax - 1) { t = tMin; nextI = 0; hold = null; }
      else nextI = idxAfter(t - 1);
      started = true; playing = true; last = 0; sync(); raf = requestAnimationFrame(frame);
    }
    function pause() { playing = false; cancelAnimationFrame(raf); if (hold) { t = hold.t; hold = null; } sync(); }
    function jump(tt) { playing = false; cancelAnimationFrame(raf); hold = null; t = Math.max(tMin, Math.min(tMax, tt)); started = t < tMax - 1; nextI = idxAfter(t); sync(); }
    bp.addEventListener("click", function () { if (playing) pause(); else play(); });
    rg.addEventListener("input", function () { jump(chart.tAt(+rg.value / 1000)); });
    box.querySelector(".rp-prev").addEventListener("click", function () {
      var ref = hold ? hold.t - 1 : t - 1, tt = tMin;
      for (var j = timed.length - 1; j >= 0; j--) if (timed[j].t < ref) { tt = timed[j].t; break; }
      jump(tt);
    });
    box.querySelector(".rp-next").addEventListener("click", function () {
      /* while playing, Next skips the rest of a hold (or jumps to the next moment and holds there) */
      if (playing) {
        if (hold) { holdLeft = 0; return; }
        if (nextI < timed.length) { t = timed[nextI].t; hold = timed[nextI]; nextI++; holdTotal = holdLeft = holdMs(hold); sync(); }
        return;
      }
      var tt = tMax;
      for (var j = 0; j < timed.length; j++) if (timed[j].t > t + 1) { tt = timed[j].t; break; }
      jump(tt);
    });
    stops.addEventListener("click", function (ev) { var b = ev.target.closest && ev.target.closest(".rp-stop"); if (!b) return; var e = timed[+b.getAttribute("data-n") - 1]; if (e) jump(e.t); });
    sync();
    if (o.autoplay === "inview" && !reduced && "IntersectionObserver" in window) {
      /* v4: observe the chart itself with a small threshold, so a tall figure on a phone still starts */
      var io = new IntersectionObserver(function (es) { es.forEach(function (e) { if (e.isIntersecting) { io.disconnect(); setTimeout(function () { if (!started) play(); }, 500); } }); }, { threshold: o.threshold == null ? 0.3 : o.threshold });
      io.observe(o.observe || box.parentNode || box);
    }
    return { play: play, pause: pause, jump: jump, time: function () { return t; }, speedAt: speedAt, holdMs: holdMs, isPlaying: function () { return playing; }, holding: function () { return hold; } };
  };

  /* ---------- mini race card visuals (gallery + landing) ---------- */
  /* linear mini bid chart: best-bid step line, winning builder's bids, winning bid; red tick = attack first seen in the public mempool */
  RV.miniAuction = function (D, w, h) {
    var A = D.auction || {}, B = A.bids, W = A.winner || {};
    if (!B || !B.series || B.series.length < 2) return "";
    w = w || 320; h = h || 120;
    var winIdx = W.builder ? B.builders.indexOf(W.builder) : -1, rec = B.record;
    var seen = D.attacker_seen_rel_ms;
    var t0 = Math.min(B.first_ms, seen != null ? seen : 0) - 300, t1 = Math.max(B.last_ms, W.t_ms || 0, 0) + 600;
    var ymax = niceMax(B.max_eth * 1.08), m = { l: 6, r: 6, t: 18, b: 18 };
    var x = BVH.lin(t0, t1, m.l, w - m.r), y = BVH.lin(0, ymax, h - m.b, m.t);
    var o = '<svg viewBox="0 0 ' + w + " " + h + '" class="mini-auc" role="img" aria-label="Bids for block ' + D.block.number + " on a linear scale from 0 to " + ymax + " ETH" + (W.eth != null ? "; winning bid " + BVH.eth(W.eth) : "") + '">';
    o += '<rect x="' + x(0) + '" y="' + (m.t - 14) + '" width="' + (w - m.r - x(0)) + '" height="' + (h - m.b - m.t + 14) + '" class="auc-slot"/>';
    o += '<line x1="' + m.l + '" x2="' + (w - m.r) + '" y1="' + y(0) + '" y2="' + y(0) + '" class="auc-base auc-floor"/>';
    o += '<line x1="' + m.l + '" x2="' + (w - m.r) + '" y1="' + y(ymax) + '" y2="' + y(ymax) + '" class="auc-grid"/>';
    o += '<text x="' + m.l + '" y="' + (y(ymax) - 4) + '" class="auc-tick auc-tick-s">' + ymax + ' ETH</text>';
    o += x(0) > w - 60 ? '<text x="' + (x(0) - 3) + '" y="' + (h - 5) + '" text-anchor="end" class="auc-tick auc-tick-s">slot start</text>' : '<text x="' + (x(0) + 3) + '" y="' + (h - 5) + '" class="auc-tick auc-tick-s">slot start</text>';
    /* the same light columns as the big chart: mist for other builders, amber for the winning builder */
    var cols = "", refl = "", dots = "", dotsW = "", y0 = y(0);
    B.series.forEach(function (p) {
      if ((p[3] & 1) === 1) return;
      var iw = p[2] === winIdx, px = x(p[0]), py = y(p[1]), hh = y0 - py;
      if (hh > 1.5) {
        cols += '<rect x="' + (px - 0.5).toFixed(1) + '" y="' + py.toFixed(1) + '" width="1" height="' + hh.toFixed(1) + '" class="auc-col' + (iw ? " auc-col-w" : "") + '"/>';
        refl += '<rect x="' + (px - 0.5).toFixed(1) + '" y="' + (y0 + 1.5).toFixed(1) + '" width="1" height="' + Math.min(9, 2 + hh * 0.08).toFixed(1) + '" class="auc-rf' + (iw ? " auc-rf-w" : "") + '"/>';
      }
      var c = '<circle cx="' + px.toFixed(1) + '" cy="' + py.toFixed(1) + '" r="' + (iw ? 2 : 1.5) + '" class="auc-dot' + (iw ? " auc-dot-w" : "") + '"/>';
      if (iw) dotsW += c; else dots += c;
    });
    o += '<g class="auc-cols">' + cols + '</g><g class="auc-refl" aria-hidden="true">' + refl + '</g><g class="auc-dots">' + dots + '</g><g class="auc-dots-w glow-s">' + dotsW + "</g>";
    var d = "", dW = "";
    rec.forEach(function (a, k) {
      var b = rec[k + 1], sd = "M" + x(a[0]).toFixed(1) + " " + y(a[1]).toFixed(1) + "H" + (b ? x(b[0]) : x(B.last_ms)).toFixed(1) + (b ? "V" + y(b[1]).toFixed(1) : "");
      if (a[2] === winIdx) dW += sd; else d += sd;
    });
    o += '<path d="' + d + '" class="auc-rec"/>' + (dW ? '<path d="' + dW + '" class="auc-rec auc-rec-w glow"/>' : "");
    if (seen != null) {
      /* when the winning-bid label sits at the top too, the "attack seen" label drops to just above the baseline */
      var winTop = W.eth != null && W.t_ms != null && y(W.eth) - 8 < m.t + 6, sy = winTop ? y(0) - 6 : m.t - 4;
      o += '<line x1="' + x(seen) + '" x2="' + x(seen) + '" y1="' + (m.t - 6) + '" y2="' + y(0) + '" class="auc-seen"/><text x="' + (x(seen) - 4) + '" y="' + sy + '" text-anchor="end" class="auc-tick auc-tick-s auc-tick-atk">attack seen</text>';
    }
    if (W.eth != null && W.t_ms != null) {
      var wx = x(W.t_ms), wy = y(W.eth), right = wx > w * 0.6;
      o += '<circle cx="' + wx + '" cy="' + wy + '" r="9" class="auc-win-halo"/><circle cx="' + wx + '" cy="' + wy + '" r="5" class="auc-win glow-s"/><text x="' + (right ? wx - 7 : wx + 7) + '" y="' + (wy - 8) + '" text-anchor="' + (right ? "end" : "start") + '" class="auc-lab auc-lab-s">winning bid ' + ethShort(W.eth) + "</text>";
    } else if (W.eth != null) {
      /* the relay records the winning value but not when it was bid: a level line, no point in time */
      var ly = y(W.eth);
      o += '<line x1="' + m.l + '" x2="' + (w - m.r) + '" y1="' + ly + '" y2="' + ly + '" class="auc-winline"/><text x="' + (w - m.r - 2) + '" y="' + (ly - 5) + '" text-anchor="end" class="auc-lab auc-lab-s">winning bid ' + ethShort(W.eth) + ', time not recorded</text>';
    } else {
      o += '<text x="' + (w - m.r - 2) + '" y="' + (m.t - 4) + '" text-anchor="end" class="auc-tick auc-tick-s">winning bid not in the relay records</text>';
    }
    return o + "</svg>";
  };
  /* pre-Merge or no bids: the block as a row of cells, bot vs attacker position */
  RV.miniBlock = function (D, w, h) {
    w = w || 320; h = h || 120;
    var n = D.block.ntx || (D.strip || []).length || 1, cw = (w - 12) / n, botI = D.bot_idx, atkI = D.atk_idx;
    var sameBlock = D.atk_block == null || D.atk_block === D.block.number;
    var o = '<svg viewBox="0 0 ' + w + " " + h + '" class="mini-blk" role="img" aria-label="Block ' + D.block.number + " with " + n + " transactions: the bot at position " + botI + (atkI != null && sameBlock ? ", the attacker at position " + atkI : "") + '">';
    var y0 = 50, bh = 28;
    o += '<text x="6" y="12" class="auc-tick auc-tick-s">block ' + D.block.number.toLocaleString("en-US") + ", " + n + " transactions, in order</text>";
    for (var i = 0; i < n; i++) {
      var cls = i === botI ? "mb-bot" : (i === atkI && sameBlock) ? "mb-atk" : "mb-tx";
      o += '<rect x="' + (6 + i * cw).toFixed(2) + '" y="' + (cls === "mb-tx" ? y0 + 8 : y0) + '" width="' + Math.max(1, cw - (cw > 3 ? 1 : 0.3)).toFixed(2) + '" height="' + (cls === "mb-tx" ? bh - 16 : bh) + '" class="' + cls + '"/>';
    }
    var close = botI != null && atkI != null && sameBlock && Math.abs(botI - atkI) * cw < 140;
    function lab(i, txt, cls, below, force) {
      var xx = 6 + i * cw + cw / 2, anchor = force || (xx < 60 ? "start" : xx > w - 60 ? "end" : "middle");
      if (anchor === "end" && xx < 120) anchor = "start";
      if (anchor === "start" && xx > w - 120) anchor = "end";
      return '<line x1="' + xx + '" x2="' + xx + '" y1="' + (below ? y0 + bh : y0) + '" y2="' + (below ? y0 + bh + 10 : y0 - 4) + '" class="mb-lead"/><text x="' + xx + '" y="' + (below ? y0 + bh + 22 : y0 - 6) + '" text-anchor="' + anchor + '" class="auc-lab auc-lab-s ' + cls + '">' + txt + "</text>";
    }
    if (botI != null) o += lab(botI, "bot, position " + botI, "t-bot", true, null);
    if (atkI != null && sameBlock) o += lab(atkI, "attacker, position " + atkI, "t-atk", false, null);
    o += '<text x="' + (w - 6) + '" y="' + (h - 4) + '" text-anchor="end" class="auc-tick auc-tick-s">' + (D.pre_merge ? "before the Merge: no relay bids" : "no relay bid history") + "</text>";
    return o + "</svg>";
  };

  /* ---------- gallery card ---------- */
  RV.raceCard = function (D, row, opts) {
    opts = opts || {};
    var hasBids = D && D.auction && D.auction.bids && D.auction.bids.series && D.auction.bids.series.length > 1;
    var vis = D ? (hasBids ? RV.miniAuction(D, 340, 128) : RV.miniBlock(D, 340, 128)) : "";
    var name = (row.title || "").split(":")[0].replace(/^Curve \/ Vyper$/, "Curve").trim();
    var sub = row.sub && row.title.indexOf(":") > 0 ? row.title.split(":").slice(1).join(":").trim() : "";
    var victim = opts.victim || name;
    var split = BVH.moneySplit(row, victim);
    var href = "incident.html?slug=" + encodeURIComponent(row.slug) + (row.sub ? "&sub=" + encodeURIComponent(row.sub) : "");
    var ahead = row.blocks_ahead, pos = "";
    /* who the bot beat is not always the original attacker (row.beaten); the card says "the exploiter" when it was not */
    var them = row.beaten && row.beaten.kind === "later" ? "the exploiter" : "the attacker";
    if (row.race_type === "deploy-window-copy") pos = "used " + them + "'s deployed contract before " + them + " called it";
    else if (ahead === 0 && row.bot_idx != null && row.atk_idx != null) pos = "same block, position " + row.bot_idx + " ahead of " + them + "'s " + row.atk_idx;
    else if (ahead > 0) pos = ahead + " block" + (ahead > 1 ? "s" : "") + " ahead of " + them;
    var bot = String(row.bot || "").replace(/\s*\(.*\)\s*$/, "").trim();
    var src = row.raw && (row.raw.trace || row.raw.block);
    return '<article class="rc">' +
      '<header class="rc-h"><h3><a href="' + href + '">' + esc(name) + "</a></h3><span class=\"rc-d\">" + BVH.dateLong(row.date) + "</span></header>" +
      (sub ? '<p class="rc-sub">' + esc(sub) + "</p>" : "") +
      '<p class="rc-who"><b>' + esc(bot) + "</b>" + (pos ? " " + esc(pos) : "") + BVH.rawA(row.raw && row.raw.block, "block", "The block: its date, and the bot's position in it") + (row.headline ? "" : ' <span class="pill no" title="' + esc(BVH.RT[row.race_type] ? BVH.RT[row.race_type].def : "") + '">not in the headline count</span>') + "</p>" + (row.headline ? BVH.beatenHTML(row, { compact: true, note: true }) : "") +
      '<div class="rc-vis">' + vis + "</div>" +
      '<p class="rc-take">Took <b>' + (split.priced ? BVH.eth(split.gross) : "an unpriced token amount") + "</b>" + (split.priced ? BVH.rawA(src, "raw", "Block trace with the bot's take") : "") + "</p>" +
      BVH.splitHTML(split, { compact: true, labels: { bld: "Builder and proposer", ret: "Returned to " + victim }, sources: BVH.moneySrc(row, D) }) +
      (opts.note ? '<p class="rc-note">' + opts.note + "</p>" : "") +
      '<p class="rc-more"><a href="' + href + '">Replay this race</a></p></article>';
  };

  /* ========================================================================================
     race.html
     ======================================================================================== */
  if (document.body.getAttribute("data-page") !== "race") return;
  var $ = function (s) { return document.querySelector(s); };
  BVH.chrome("race.html");

  function punkNote(row) { return E(row.gross_eth - ((row.money && row.money.bot_net_eth) || 0) - (row.paid_to_builder_eth || 0), 2, false) + " ETH-equivalent of the take was sent on to the attacker. The bot kept a fee Punk agreed to and returned the rest."; }
  function kelpNote(row) { return "Taken as rsETH and valued in ETH at the swap rate inside the transaction."; }
  Promise.all([BVH.json("data/incidents.json"), BVH.json("data/incident/makina-2026.json"), BVH.json("data/lineages.json").catch(function () { return null; })])
    .then(function (r) {
      var rows = r[0], D = r[1], row = rows.filter(function (x) { return x.id === "makina-2026"; })[0];
      beats(D, row); hero(D, row); answer(D, row, rows); primer(); auction(D); windowStrip(D); block(D); money(D, row); aftermath(D); chat(r[2]);
      gallery(rows);
      BVH.openHash(null, true);
    })
    .catch(function (e) { BVH.loadError($("#r-hero-body"), e); });

  var fnHero = RV.footnotes();

  function hero(D, row) {
    var dep = RV.events(D).filter(function (e) { return e.id === "deploy"; })[0], depEv = (D.events || []).filter(function (e) { return e.kind === "deploy" && /attack contract/i.test(e.detail || ""); })[0];
    var gap = dep ? -dep.t : 12000, bot = D.txs.filter(function (t) { return t.role === "bot"; })[0];
    var botEv = (D.events || []).filter(function (e) { return e.kind === "tx" && /Copy of the attack/.test(e.detail || ""); })[0];
    var kept = botEv && botEv.derived && botEv.derived[0] ? botEv.derived[0].shown : null;
    /* the old dek, word for word, now opens the "four steps" drawer */
    $("#r-setup").innerHTML = "At " + BVH.clock(depEv.t, false) + " UTC on " + BVH.dateLong(D.date) + ", an attacker put a contract on Ethereum built to drain Makina Finance, a DeFi protocol, through its DUSD/USDC pool on Curve" + fnHero(depEv.raws && depEv.raws[0] || depEv.raw, "Deploy transaction trace") +
      ". The next block, timestamped " + Math.round(gap / 1000) + " seconds later, held the copy and its " + E(bot.cb_eth) + " builder payment" + fnHero(D.incident_raw && D.incident_raw.copy_tx_trace || D.block.raw.trace, "Trace of the copy, with the payment to the builder") + ".";
    $("#r-hero-note").innerHTML = "No attacker call was observed landing: the copy ran first.";
    var b0 = depEv.block, b1 = D.block.number;
    $("#r-blocks").innerHTML =
      '<div class="rb rb-atk"><span class="rb-k">Block ' + b0.toLocaleString("en-US") + '</span><span class="rb-t">' + BVH.clock(depEv.t, false) + ' UTC</span><span class="rb-what"><i class="dot-atk" aria-hidden="true"></i><span>The attacker deploys the drain contract' + '<sup class="fn">' + BVH.rawA(depEv.raws && depEv.raws[0] || depEv.raw, "raw", "Deploy transaction trace") + "</sup></span></span></div>" +
      '<div class="rb-gap" aria-label="' + Math.round(gap / 1000) + ' seconds later"><span>' + Math.round(gap / 1000) + ' s</span></div>' +
      '<div class="rb rb-bot"><span class="rb-k">Block ' + b1.toLocaleString("en-US") + ', position ' + D.bot_idx + '</span><span class="rb-t">' + BVH.clock(D.block.ts_ms, false) + ' UTC</span><span class="rb-what"><i class="dot-bot" aria-hidden="true"></i><span>A ' + BVH.term("searcher") + " runs the same calls first" + '<sup class="fn">' + BVH.rawA(D.block.raw.block, "raw", "The block, with its timestamp") + BVH.rawA(D.incident_raw && D.incident_raw.copy_tx_trace, "trace", "Trace of the copy transaction") + "</sup></span></span></div>";
  }

  /* answer first: the price of going first, and where it ended up */
  function answer(D, row, rows) {
    var bot = D.txs.filter(function (t) { return t.role === "bot"; })[0], ir = D.incident_raw || {};
    var split = BVH.moneySplit(row, "Makina");
    $("#r-ans").innerHTML = '<div class="opener op-bot"><p class="op-big">' + E(bot.cb_eth, 2, false) + '<small>ETH</small><sup class="fn">' + BVH.rawA(ir.copy_tx_trace, "raw", "Trace of the copy: the coinbase transfer to the builder") + "</sup></p>" +
      '<p class="op-line">paid to the ' + BVH.term("builder", "block builder") + " to go first, out of the " + E(row.gross_eth) + " the copy took.</p></div>" +
      '<div class="r-ans-split">' + BVH.splitHTML(split, { inline: true, labels: { bld: "To the builder and proposer", ret: "Returned to Makina" }, sources: BVH.sources(BVH.moneySrc(row, D)) }) + "</div>";
    BVH.buildIn($("#r-ans"), "bars");
    var n = rows.filter(function (x) { return x.headline; }).length;
    Array.prototype.forEach.call(document.querySelectorAll('a[href="#gallery"]'), function (a) { a.textContent = "All " + n + " races"; });
  }

  function auction(D) {
    var list = $("#auc-steps");
    var chart = RV.auction($("#auc"), D, {
      onStep: function (e) { mark(e ? e.n : -1); }
    });
    var ev = chart.events;
    list.innerHTML = ev.map(function (e) {
      return '<li data-n="' + e.n + '" class="st-' + e.id + '"><span class="st-n">' + e.n + '</span><span class="st-time">' + sgn(e.t) + '<small>' + BVH.clock(D.t0_ms + e.t) + " UTC</small></span><span class=\"st-body\"><b>" + esc(e.title) + "</b> " + esc(e.text) + (e.rawHTML || BVH.rawA(e.raw, "raw", e.rawTitle)) + "</span></li>";
    }).join("");
    $("#auc-moments-m").textContent = ev.length + " moments, each with its time and source";
    function mark(n) { Array.prototype.forEach.call(list.children, function (li) { li.classList.toggle("is-cur", +li.getAttribute("data-n") === n); li.classList.toggle("is-future", +li.getAttribute("data-n") > n && n > 0); }); }
    RV.warp($("#auc-ctrl"), chart, { t0: D.t0_ms, label: "Moment in the race, from the deploy to the last bid (drag to scrub)" });
    var A = D.auction, B = A.bids, ser = B.series || [], W = A.winner || {};
    /* chapter opener: the first bid and the winning bid */
    $("#auc-open").innerHTML = BVH.opener({ big: BVH.eth(ser[0][1], false) + ' <span class="op-arrow" aria-hidden="true">&rarr;</span><span class="sr"> to </span> ' + E(W.eth, 2, false) + "<small>ETH</small>",
      src: BVH.rawA(A.raw && A.raw.bids, "bids", "Relay bid file for this slot: the first bid") + BVH.rawA(A.raw && A.raw.delivered, "won", "Relay record of the block delivered to the proposer: the winning bid"),
      text: "First saved bid and winning bid for block " + D.block.number.toLocaleString("en-US") + ", which held the copy.", cls: "op-bot op-sm" });
    $("#auc-src").innerHTML = B.n_total + " bids from " + (A.n_builders || B.builders.length) + " builders" + BVH.sources(BVH.bidsA(A) + BVH.rawA(A.raw.delivered, "delivered", "Relay record of the payload delivered to the proposer"), { inlineMax: 1 }) + ", on a linear ETH scale. Amber is builder " + esc(W.builder) + ", the winner.";
    $("#auc-how").innerHTML = "Each column of light is one block a builder offered the proposer for this slot, rising to the price it offered. " + B.n_total + " bids from " + (A.n_builders || B.builders.length) + " builders" + BVH.bidsA(A) + "; " + B.n_shown + " are drawn, including every new best bid. Amber columns are builder " + esc(W.builder) + "'s bids; the line is the best bid so far, amber while " + esc(W.builder) + " holds it. Winning bid from the relay's delivery record" + BVH.rawA(A.raw.delivered, "raw", "Relay record of the payload delivered to the proposer") + ". The ETH axis is linear throughout; during playback it widens as the bids grow. Time is linear too; the zoom under the chart stretches the last seconds, where the bids climb, on the same ETH scale.";
  }
  /* section markers are times, read from the data */
  function beats(D, row) {
    var B = D.auction.bids, ev = RV.events(D), dep = ev[0], ret = (D.events || []).filter(function (e) { return e.kind === "return" && /RETURN/.test(e.detail || ""); })[0];
    function set(id, html) { var el = document.getElementById(id); if (el) el.innerHTML = html; }
    set("beat-auc", BVH.clock(D.t0_ms + B.first_ms, false) + " to " + BVH.clock(D.t0_ms + B.last_ms, false) + " UTC");
    set("beat-win", BVH.clock(D.t0_ms + dep.t, false) + " to " + BVH.clock(D.block.ts_ms, false) + " UTC");
    set("beat-blk", BVH.clock(D.block.ts_ms, false) + " UTC");
    set("beat-money", BVH.dateLong(D.date) + " to " + (ret ? BVH.dateLong(ret.utc.slice(0, 10)) : "later"));
    set("auc-blockno", D.block.number.toLocaleString("en-US"));
    set("blk-no", D.block.number.toLocaleString("en-US")); set("blk-ntx", String(D.block.ntx));
    set("money-amt", Math.floor(row.gross_eth).toLocaleString("en-US") + " ETH");
    /* the byte overlap: both raw inputs (the bot's calldata, the attacker's deployed code) and our count, which is derived */
    var ir = D.incident_raw || {}, k = /shares ([\d,]+) of ([\d,]+) non-zero bytes \((\d+)%\)/.exec((D.narrative || []).join(" "));
    if (k) set("know-copy", "<b>The copy.</b> No call from the attacker was ever observed, so there is no attack transaction to compare with. We match the copy to the deployed contract by long runs of identical bytes: " + k[3] + "% of the bot's non-zero calldata bytes (" + k[1] + " of " + k[2] + ") appear verbatim in the attacker's contract code, in runs of 16 bytes or more. Compare the bot's transaction" + BVH.rawA(ir.copy_tx, "raw", "The bot's transaction, with its calldata") + " with the attacker's deployed code" + BVH.rawA(ir.attack_contract_code, "raw", "The attacker contract's runtime code") + "; our count is in the race data" + BVH.rawA("data/incident/makina-2026.json", "data", "Derived: the byte-overlap count, in the race's narrative") + ".");
    set("know-mem", "<b>The mempool.</b> The public mempool archive covers that day" + BVH.rawA(ir.mempool_dumpster_index, "index", "The archive's month index, listing that day's file") + " but has neither the deploy nor the copy" + BVH.rawA(ir.mempool_dumpster_day, "day rows", "Rows cut from that day's archive file for the cited transactions: none matched") + ", so neither was broadcast publicly before landing, or every archive source missed them.");
  }

  function windowStrip(D) {
    var ev = RV.events(D), dep = ev.filter(function (e) { return e.id === "deploy"; })[0], win = ev.filter(function (e) { return e.id === "win"; })[0];
    var depEv = (D.events || []).filter(function (e) { return e.kind === "deploy" && /attack contract/i.test(e.detail || ""); })[0];
    /* the two block timestamps; the off-chain work and the proposer's choice are not timed by anything public */
    var gap = depEv && depEv.t != null ? D.block.ts_ms - depEv.t : null;
    if (gap != null) { $("#win-span2").textContent = Math.round(gap / 1000) + " seconds"; }
    $("#win-from").innerHTML = "<b>" + BVH.clock(D.t0_ms + dep.t, false) + "</b> block " + (D.block.number - 1).toLocaleString("en-US") + " carries the contract" + BVH.rawA(D.incident_raw && D.incident_raw.deploy_tx, "raw", "The deploy transaction");
    $("#win-to").innerHTML = "<b>" + BVH.clock(D.block.ts_ms, false) + "</b> block " + D.block.number.toLocaleString("en-US") + "'s timestamp" + BVH.rawA(D.block.raw.block, "raw", "The block, with its timestamp") + (win ? '<small>winning block first bid to the relay at ' + sgn(win.t) + "</small>" : "");
  }

  function block(D) {
    var n = D.block.ntx, strip = D.strip || [], box = $("#blk");
    var bot = D.txs.filter(function (t) { return t.role === "bot"; })[0], pay = D.txs.filter(function (t) { return t.role === "builder" && t.label === "builder payout"; })[0];
    var cells = "";
    for (var i = 0; i < n; i++) {
      var s = strip[i] || [], cls = s[2] === "bot" ? "bc-bot" : s[2] === "builder" ? "bc-bld" : "bc-tx";
      cells += '<i class="bi-col ' + cls + '" title="position ' + i + (s[2] === "bot" ? ": the copy" : s[2] === "builder" ? ": builder pays the proposer" : "") + '"></i>';
    }
    setTimeout(function () { BVH.buildIn($("#blk .blk-cells"), "grow"); }, 0);
    $("#blk-open").innerHTML = BVH.opener({ big: "1st <small>of " + n + "</small>", src: BVH.rawA(D.block.raw.block, "raw", "The block, with its transactions in order"),
      text: "The copy ran first in block " + D.block.number.toLocaleString("en-US") + ". The builder's payment to the " + BVH.term("proposer") + " ran last.", cls: "op-bot" });
    box.innerHTML = '<div class="blk-cells" role="img" aria-label="Block ' + D.block.number + ": " + n + " transactions. Position 0 is the copy; the last one is the builder paying the proposer.\">" + cells + "</div>" +
      '<div class="blk-keys"><div class="bk bk-bot"><span class="bk-p">Position 0</span><b>The copy.</b> Pays ' + E(bot.cb_eth) + " straight to the block's builder" + BVH.rawA(bot.raw && bot.raw.trace, "raw", "Block trace") + "</div>" +
      '<div class="bk bk-mid"><span class="bk-p">Positions 1 to ' + (n - 2) + "</span>" + (n - 2) + " ordinary transactions</div>" +
      (pay ? '<div class="bk bk-bld"><span class="bk-p">Position ' + pay.i + "</span><b>The builder pays the proposer</b> " + E(pay.value_eth) + ", exactly the winning bid" + BVH.rawA(pay.raw && pay.raw.tx, "raw", "The block, with the payment transaction") + "</div>" : "") + "</div>";
  }

  function money(D, row) {
    var F = D.flows, G = row.gross_eth, bot = D.txs.filter(function (t) { return t.role === "bot"; })[0], m = row.money || {};
    var fwd = /forwarded ([\d.,]+) ETH to (0x[0-9a-f]+) \(block (\d+), ([0-9T:\-]+)Z\)/i.exec(D.fate.text || "");
    var fwdEth = fwd ? parseFloat(fwd[1].replace(/,/g, "")) : null;
    var ret = m.returned_by_builder_eth, bounty = m.bounty_kept_eth;
    var retEv = (D.events || []).filter(function (e) { return e.kind === "return" && /RETURN/.test(e.detail || ""); })[0];
    var ir = D.incident_raw || {};
    var keptTxt = (D.events || []).filter(function (e) { return e.kind === "tx" && e.derived; })[0];
    /* icicle: each row splits its parent; widths are linear in ETH against the take */
    function pct(v) { return (100 * v / G).toFixed(3) + "%"; }
    function bar(left, v, cls, label, val, extra) {
      return '<div class="ic-bar ' + cls + '" style="left:' + pct(left) + ";width:" + pct(v) + '"' + (left + v > G * 0.995 && left > G * 0.5 ? ' data-end="1"' : "") + '><span class="ic-lab"><b>' + val + "</b><span>" + label + (extra || "") + "</span></span></div>";
    }
    var rowsH = [
      ['<span class="ic-when">' + BVH.clock(D.block.ts_ms, false) + "</span><span>the copy runs</span>", bar(0, G, "ic-take", "taken from Makina", E(G), BVH.rawA(ir.copy_tx_trace, "raw", "Trace of the copy"))],
      ['<span class="ic-when">same transaction</span><span>the bot pays for position 0</span>', bar(0, bot.cb_eth, "ic-bld", "paid to builder " + esc(F.builder_name), E(bot.cb_eth), BVH.rawA(ir.copy_tx_trace, "raw", "Trace: the coinbase transfer")) + bar(bot.cb_eth, G - bot.cb_eth, "ic-bot ic-thin", "kept by the bot", esc(keptTxt && keptTxt.derived ? keptTxt.derived[0].shown : BVH.eth(m.bot_net_eth)), "")],
      ['<span class="ic-when">end of the block</span><span>the builder pays the winning bid to the proposer</span>', bar(0, F.proposer_eth, "ic-gold", "to the proposer", E(F.proposer_eth), BVH.rawA(ir.proposer_payment_tx, "raw", "The proposer payment transaction")) + bar(F.proposer_eth, F.builder_kept_eth, "ic-bld2", "stays with the builder", E(F.builder_kept_eth), "")],
      fwd ? ['<span class="ic-when">' + fwd[4].slice(11, 16) + " UTC, " + Math.round((Date.parse(fwd[4] + "Z") - D.block.ts_ms) / 60000) + " min later</span><span>the builder moves it on</span>", bar(F.proposer_eth, Math.min(fwdEth, G - F.proposer_eth), "ic-bld2", "forwarded to " + fwd[2].slice(0, 6), E(fwdEth, 1), BVH.rawA(ir.builder_to_treasury_tx, "raw", "The forward transaction"))] : null,
      ret != null ? ['<span class="ic-when">' + (retEv ? BVH.dateLong(retEv.utc.slice(0, 10)) + ", " + retEv.utc.slice(11, 16) + " UTC" : "later") + "</span><span>after a Safe Harbor offer</span>", bar(F.proposer_eth, ret, "ic-ret", "returned to Makina", E(ret, 1), BVH.rawA(retEv && retEv.raw, "raw", "The return transaction")) + (bounty != null ? bar(F.proposer_eth + ret, bounty, "ic-bounty", "kept as a " + (fwdEth ? Math.round(100 * bounty / fwdEth) + "% " : "") + "bounty", E(bounty, 1), "") : "")] : null
    ].filter(Boolean);
    $("#ice").innerHTML = rowsH.map(function (r) { return '<div class="ic-row"><div class="ic-when-c">' + r[0] + '</div><div class="ic-track">' + r[1] + "</div></div>"; }).join("");
    /* a label that does not fit inside its bar moves just below it */
    function fit() {
      Array.prototype.forEach.call(document.querySelectorAll("#ice .ic-bar"), function (b) {
        b.classList.remove("ic-out"); var l = b.querySelector(".ic-lab");
        if (l.offsetWidth + 14 > b.offsetWidth) b.classList.add("ic-out");
      });
      Array.prototype.forEach.call(document.querySelectorAll("#ice .ic-row"), function (r) { r.classList.toggle("has-out", !!r.querySelector(".ic-out")); });
    }
    fit(); var ft; window.addEventListener("resize", function () { clearTimeout(ft); ft = setTimeout(fit, 100); });
    var hm = document.getElementById("how-it-moved"); if (hm) hm.addEventListener("toggle", function () { if (hm.open) fit(); });
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(fit);
    $("#ice-note").innerHTML = "Bars are drawn to scale against the " + E(G) + " taken. The builder kept " + E(F.builder_kept_eth) + " of this payment and later forwarded " + (fwdEth != null ? E(fwdEth, 1) : "it") + " to " + (fwd ? fwd[2].slice(0, 6) : "another address") + (fwdEth != null && fwdEth - F.builder_kept_eth > 1e-6 ? ", adding " + BVH.eth2(fwdEth - F.builder_kept_eth) + " of its own funds" : "") + ". The bot's " + (keptTxt && keptTxt.derived ? esc(keptTxt.derived[0].shown) : "") + " is " + esc(keptTxt && keptTxt.derived ? keptTxt.derived[0].how : "") + ".";
    /* the full split is the answer tile under the hero; this section draws how the money moved */
  }

  /* the words this story uses: a closed drawer (Part 1 launches on its own); first uses in the text are tap-to-define */
  function primer() {
    var el = $("#primer"); if (!el) return;
    el.innerHTML = BVH.glossary(["block", "builder", "proposer", "relay", "mempool", "position0", "searcher"], {
      intro: "The words this story uses, each in one line. Nothing else is assumed.", id: "words"
    });
  }

  /* the human beat: the one on-chain message about this race, as a chat bubble (lineages.json messages, key "makina") */
  function chat(L) {
    var mm = L && L.messages, g = mm && (mm.groups || []).filter(function (x) { return x.key === "makina"; })[0];
    if (!g) return;
    $("#money-chat").innerHTML = '<p class="r-chat-k">About twelve hours later, on chain</p>' + BVH.chat(g.messages.map(function (m) {
      var mine = m.dir === "from_yoink";
      return { side: mine ? "out" : "in", who: mine ? "Yoink, another bot, wrote" : "Sent to Yoink", when: BVH.dateLong(m.time_utc.slice(0, 10)) + ", " + m.time_utc.slice(11, 16) + " UTC",
        text: esc(m.text), tx: '<a class="raw" href="https://etherscan.io/tx/' + m.tx + '" target="_blank" rel="noopener" title="Open on Etherscan (external)">' + BVH.short(m.tx, 10, 6) + "</a>" + BVH.rawA(mm.raw, "raw", "Verbatim Etherscan row for this message transaction") + " block " + m.block.toLocaleString("en-US") };
    }), { label: g.heading }) + '<p class="r-chat-x">' + esc(g.context) + "</p>";
  }

  function aftermath(D) {
    var after = (D.events || []).filter(function (e) { return e.t && e.t > D.block.ts_ms && (e.kind === "message" || e.kind === "return") && !/test transaction|Recovery Safe/i.test(e.detail || ""); });
    $("#after-m").textContent = after.length + " messages and transfers, each with its source";
    $("#after").innerHTML = after.map(function (e) {
      var d = e.utc ? BVH.dateLong(e.utc.slice(0, 10)) + " " + e.utc.slice(11, 16) : "";
      return '<li class="af-' + e.kind + '"><span class="af-t">' + d + ' UTC</span><span class="af-k">' + (e.kind === "return" ? "funds move" : "on-chain message") + '</span><span class="af-d">' + esc(e.detail) + BVH.rawA(e.raw, "raw", "Saved source for this event") + '<small>' + esc(e.actor || "") + "</small></span></li>";
    }).join("");
  }

  /* other races: the headline sentence, the who-lost dots, and the 19-race scoreboard; each row opens its bids */
  /* DODO's return sentence is part of the shared scoreboard row, so it is not repeated here */
  var NOTES = { "punk-2021": punkNote, "kelp-rseth-2026": kelpNote };
  function gallery(rows) {
    $("#gal-head").innerHTML = esc(BVH.headline(rows)) + '<sup class="fn">' + BVH.rawA("data/beaten_party.json", "data", "Who lost each headline race: verdict, note and evidence per race") + "</sup>";
    $("#gal-strip").innerHTML = BVH.lostStrip(rows);
    var KEY = '<div class="fig-key gal-key" aria-hidden="true"><span><i class="k-dot"></i>a builder\'s bid</span><span><i class="k-dot k-w"></i>winning builder\'s bids</span><span><i class="k-line"></i>best bid so far</span><span><i class="k-win"></i>winning bid</span><span><i class="k-seen"></i>attack first seen in the public mempool</span></div>';
    BVH.scoreboard($("#gal"), rows, {
      victims: { "makina-2026": "Makina", "kelp-rseth-2026": "the Safe's owner" },
      extra: function (row, D) {
        var note = NOTES[row.id] ? '<p class="rc-note">' + NOTES[row.id](row) + "</p>" : "";
        if (!D) return note;
        var hasBids = D.auction && D.auction.bids && D.auction.bids.series && D.auction.bids.series.length > 1;
        return note + '<figure class="sb-bids"><figcaption>' + (hasBids ? "The bids for the bot's block, on a linear scale" + BVH.bidsA(D.auction) : "The bot's block, in order" + BVH.rawA(row.raw && row.raw.block, "block", "The block, with the bot's position in it")) + "</figcaption>" +
          (hasBids ? RV.miniAuction(D, 340, 128) + KEY : RV.miniBlock(D, 340, 128)) + "</figure>";
      }
    });
  }
})();
