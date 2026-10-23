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
      title: "The winning block reaches the relay", short: "winning bid",
      text: "The block that won, " + W.builder + "'s at " + E(W.eth) + ", was first bid to " + relayName(B.relays) + " at " + sgn(W.t_ms) + ". It holds the copy at position " + (D.bot_idx != null ? D.bot_idx : "0") + (W.relays && W.relays.length ? "; the delivery record is from " + W.relays.map(function (x) { return RELAY_NAMES[x] || x; }).join(", ") + ", which does not record when the proposer chose it" : "") + "." });
    var last = rec[rec.length - 1];
    if (last && W.t_ms != null && last[0] > W.t_ms && last[1] > W.eth) ev.push({ id: "late", t: last[0], eth: last[1], raw: A.raw && A.raw.bids, rawTitle: "Relay bid file for this slot",
      title: "Bids keep rising", short: "later bids",
      text: "Later bids reach " + E(last[1]) + " at " + sgn(last[0]) + ". The block delivered to the proposer is the " + E(W.eth) + " one." });
    ev.sort(function (a, b) { return a.t - b.t; });
    ev.forEach(function (e, k) { e.n = k + 1; });
    return ev;
  };

  /* ---------- the auction chart: LINEAR ETH axis against seconds from slot start ----------
     o: { compact, onStep(ev), height } -> { set(tMs), events, tMin, tMax } */
  RV.auction = function (box, D, o) {
    o = o || {};
    var A = D.auction, B = A.bids, W = A.winner || {}, ev = RV.events(D);
    var winIdx = W.builder ? B.builders.indexOf(W.builder) : -1;
    var tMin = Math.min(B.first_ms, ev.length ? ev[0].t : B.first_ms) - 600, tMax = Math.max(B.last_ms, W.t_ms || 0) + 350;
    var state = { t: tMax }, svg, els = [], evEls = [], cursor, cursorLab, insetBox;
    var ystep = tickStep(B.max_eth, 7), ymax = Math.ceil(B.max_eth * 1.03 / ystep) * ystep;
    /* the action is in the last few seconds: compress the quiet early part of the time axis (marked with a break) */
    var tBreak = (tMax - tMin > 9000 && W.t_ms != null) ? Math.min(-3000, W.t_ms - 3000) : null;
    function draw() {
      box.innerHTML = "";
      var w = Math.max(300, box.clientWidth || 700), narrow = w < 640, compact = o.compact || narrow;
      var H = o.height || (compact ? (narrow ? 320 : 340) : 480);
      var m = { l: narrow ? 40 : 64, r: narrow ? 12 : 24, t: compact ? 34 : 44, b: 44 };
      var x = timeScale(tMin, tBreak, tMax, m.l, w - m.r, narrow ? 0.3 : 0.32), y = BVH.lin(0, ymax, H - m.b, m.t);
      svg = S("svg", { viewBox: "0 0 " + w + " " + H, width: w, height: H, class: "auc", role: "img",
        "aria-label": "Builder bids for block " + D.block.number + " on a linear scale, " + B.n_total + " bids from " + sgn(B.first_ms) + " to " + sgn(B.last_ms) + " around the slot start. " + ev.map(function (e) { return sgn(e.t) + ": " + e.text; }).join(" ") }, box);
      els = []; evEls = [];
      /* the two slots */
      var x0 = x(0), xd = x(Math.max(tMin, -12000));
      S("rect", { x: x0, y: m.t - 26, width: w - m.r - x0, height: H - m.b - m.t + 26, class: "auc-slot" }, svg);
      S("text", { x: w - m.r - 6, y: m.t - 12, "text-anchor": "end", class: "auc-slotlab" }, svg, narrow ? "slot starts" : "block " + D.block.number.toLocaleString("en-US") + "'s slot");
      if (!compact) S("text", { x: xd + 8, y: m.t - 12, class: "auc-slotlab" }, svg, "block " + (D.block.number - 1).toLocaleString("en-US") + "'s slot");
      /* grid + axes */
      var ys = compact ? tickStep(ymax, 4) : ystep;
      for (var v = 0; v <= ymax + 1e-9; v += ys) {
        S("line", { x1: m.l, x2: w - m.r, y1: y(v), y2: y(v), class: v === 0 ? "auc-base auc-floor" : "auc-grid" }, svg);
        S("text", { x: m.l - 8, y: y(v) + 4, "text-anchor": "end", class: "auc-tick" }, svg, v === 0 ? "0" : (v >= 1000 ? v.toLocaleString("en-US") : String(+v.toFixed(3))) + (narrow ? "" : " ETH"));
      }
      if (narrow) S("text", { x: m.l - 8, y: m.t - 12, "text-anchor": "end", class: "auc-tick" }, svg, "ETH");
      var ticks = [];
      if (x.rb != null) {
        for (var t = Math.ceil(tMin / 3000) * 3000; t < tBreak - 1500; t += 3000) ticks.push(t);
        for (t = tBreak; t <= tMax; t += 1000) ticks.push(t);
      } else { var xs = narrow ? 4000 : 2000; for (t = Math.ceil(tMin / xs) * xs; t <= tMax; t += xs) ticks.push(t); }
      ticks.forEach(function (t) {
        S("line", { x1: x(t), x2: x(t), y1: H - m.b, y2: H - m.b + 5, class: "auc-base" }, svg);
        S("text", { x: x(t), y: H - m.b + 19, "text-anchor": "middle", class: "auc-tick" }, svg, t === 0 ? "0" : (narrow ? sgn(t, 0).replace(" s", "") : sgn(t, 0)));
      });
      if (x.rb != null) {
        /* the break: a gap in the baseline with two slashes, and a note that the scale changes */
        var bx = x.rb, by = H - m.b;
        S("rect", { x: bx - 5, y: by - 3, width: 10, height: 6, class: "auc-breakgap" }, svg);
        S("path", { d: "M" + (bx - 7) + " " + (by + 5) + "l5 -10M" + (bx + 1) + " " + (by + 5) + "l5 -10", class: "auc-break" }, svg);
        S("line", { x1: bx, x2: bx, y1: m.t - 26, y2: by - 6, class: "auc-breakline" }, svg);
        var ratio = (x(1000) - x(0)) / (x(tMin + 1000) - x(tMin));
        if (!narrow && !o.compact) S("text", { x: bx, y: H - m.b + 36, "text-anchor": "middle", class: "auc-axlab auc-breaklab" }, svg, "time scale " + ratio.toFixed(0) + "× wider from here");
        else if (!narrow) S("text", { x: bx + 6, y: m.t - 12, class: "auc-axlab auc-breaklab" }, svg, ratio.toFixed(0) + "× wider →");
      }
      S("text", { x: w - m.r, y: H - 2, "text-anchor": "end", class: "auc-axlab" }, svg, narrow ? "seconds from slot start" : "seconds from the start of the slot, " + BVH.clock(D.t0_ms, false) + " UTC");
      /* bids as light in the dark: each bid is a thin column rising from the floor (zero ETH) to its price, with a
         point of light on top and a short reflection under the floor. Other builders in pale mist, the winning
         builder in the amber streak. Heights stay linear in ETH; the reflection sits below zero and carries no value. */
      var gC = S("g", { class: "auc-cols" }, svg), gF = S("g", { class: "auc-refl", "aria-hidden": "true" }, svg), gD = S("g", { class: "auc-dots" }, svg), gW = S("g", { class: "auc-dots-w glow-s" }, svg);
      var y0 = y(0);
      B.series.forEach(function (p) {
        var isW = p[2] === winIdx, isWin = (p[3] & 1) === 1;
        if (isWin) return;
        var px = x(p[0]), py = y(p[1]), hh = y0 - py;
        if (hh > 1.5) {
          els.push([p[0], S("rect", { x: (px - 0.6).toFixed(1), y: py.toFixed(1), width: 1.2, height: hh.toFixed(1), class: isW ? "auc-col auc-col-w" : "auc-col" }, gC)]);
          els.push([p[0], S("rect", { x: (px - 0.6).toFixed(1), y: (y0 + 1.5).toFixed(1), width: 1.2, height: Math.min(14, 3 + hh * 0.08).toFixed(1), class: isW ? "auc-rf auc-rf-w" : "auc-rf" }, gF)]);
        }
        els.push([p[0], S("circle", { cx: px.toFixed(1), cy: py.toFixed(1), r: isW ? 2.5 : 1.9, class: isW ? "auc-dot auc-dot-w" : "auc-dot" }, isW ? gW : gD)]);
      });
      /* best bid so far: a step line, drawn in pieces so it can reveal with the cursor; while the winning builder
         holds the best bid the line is the amber streak */
      var rec = B.record, gR = S("g", { class: "auc-recs" }, svg), gRW = S("g", { class: "auc-recs-w glow" }, svg);
      for (var i = 0; i < rec.length; i++) {
        var a = rec[i], b = rec[i + 1], xe = b ? x(b[0]) : x(B.last_ms), isWin = a[2] === winIdx;
        var seg = S("path", { d: "M" + x(a[0]).toFixed(1) + " " + y(a[1]).toFixed(1) + "H" + xe.toFixed(1) + (b ? "V" + y(b[1]).toFixed(1) : ""), class: isWin ? "auc-rec auc-rec-w" : "auc-rec" }, isWin ? gRW : gR);
        els.push([a[0], seg]);
      }
      /* the deploy marker on the time axis */
      ev.forEach(function (e) {
        var g = S("g", { class: "auc-ev auc-ev-" + e.id }, svg), ex = x(e.t);
        if (e.id === "deploy") {
          S("line", { x1: ex, x2: ex, y1: m.t - 22, y2: H - m.b, class: "auc-depline" }, g);
          S("path", { d: "M" + ex + " " + (H - m.b - 8) + "l8 8-8 8-8-8z", class: "auc-dep" }, g);
          S("text", { x: ex + 8, y: H - m.b - (narrow ? 52 : 60), class: "auc-lab auc-lab-atk" }, g, narrow ? "deploy" : "attack contract deployed");
        } else if (e.id === "win") {
          S("circle", { cx: ex, cy: y(e.eth), r: 13, class: "auc-win-halo" }, g);
          S("circle", { cx: ex, cy: y(e.eth), r: 7.5, class: "auc-win glow-s" }, g);
          var right = ex > w * 0.62;
          S("text", { x: right ? ex - 13 : ex + 13, y: y(e.eth) - 10, "text-anchor": right ? "end" : "start", class: "auc-lab auc-lab-big" }, g, "winning bid " + E(e.eth));
          S("text", { x: right ? ex - 13 : ex + 13, y: y(e.eth) + 6, "text-anchor": right ? "end" : "start", class: "auc-lab" }, g, W.builder + " at " + sgn(e.t));
        } else if (e.id === "late") {
          S("circle", { cx: ex, cy: y(e.eth), r: 4.5, class: "auc-late" }, g);
          if (!compact) S("text", { x: ex - 16, y: y(e.eth) - 14, "text-anchor": "end", class: "auc-lab" }, g, "highest later bid " + E(e.eth));
        }
        if (e.id !== "deploy") {
          var ny = e.eth != null ? y(e.eth) : H - m.b, big = e.id === "win";
          if (!big) {
            var lx = ex, ly = Math.max(m.t + 10, ny - 18);
            if (e.id === "first" || e.id === "jump") ly = H - m.b - (e.id === "jump" ? 46 : 24);
            S("line", { x1: ex, x2: lx, y1: ny, y2: ly + 8, class: "auc-lead" }, g);
            var c = S("g", { class: "auc-num" }, g);
            S("circle", { cx: lx, cy: ly, r: 9 }, c); S("text", { x: lx, y: ly + 4, "text-anchor": "middle" }, c, String(e.n));
          }
        } else {
          var c2 = S("g", { class: "auc-num auc-num-atk" }, g);
          S("circle", { cx: ex, cy: H - m.b - 34, r: 9 }, c2); S("text", { x: ex, y: H - m.b - 30, "text-anchor": "middle" }, c2, String(e.n));
        }
        evEls.push([e.t, g]);
      });
      /* winning-bid number marker */
      var we = ev.filter(function (e) { return e.id === "win"; })[0];
      if (we) { var cw = S("g", { class: "auc-num auc-num-win" }), wx = x(we.t), wy = y(we.eth); svg.appendChild(cw); S("circle", { cx: wx, cy: wy - 24, r: 9 }, cw); S("text", { x: wx, y: wy - 20, "text-anchor": "middle" }, cw, String(we.n)); evEls.push([we.t, cw]); }
      /* zoom inset for the bids too small to see on a linear scale */
      insetBox = null;
      var je = ev.filter(function (e) { return e.id === "jump"; })[0];
      if (je && !o.compact) {
        var zx0 = B.first_ms - 300, zx1 = je.t + 1100, zy1 = niceMax(je.eth * 1.15), gi, ib;
        S("rect", { x: x(zx0), y: y(0) - 6, width: x(zx1) - x(zx0), height: 6, class: "auc-zoomsrc" }, svg);
        if (narrow) {
          var svg2 = S("svg", { viewBox: "0 0 " + w + " 170", width: w, height: 170, class: "auc auc-inset2", role: "img", "aria-label": "Zoom on the first bids, 0 to " + zy1 + " ETH: " + je.text }, box);
          ib = { x: 0, y: 4, w: w, h: 160 }; gi = S("g", { class: "auc-inset" }, svg2);
          S("rect", { x: ib.x + 0.5, y: ib.y, width: ib.w - 1, height: ib.h, rx: 6, class: "auc-insetbg" }, gi);
        } else {
          ib = { x: x(Math.max(tMin + 400, -11400)), y: m.t + 10, w: 380, h: 160 };
          ib.w = Math.max(260, Math.min(ib.w, x(-600) - ib.x));
          gi = S("g", { class: "auc-inset" }, svg);
          S("rect", { x: ib.x, y: ib.y, width: ib.w, height: ib.h, rx: 6, class: "auc-insetbg" }, gi);
          S("line", { x1: ib.x + ib.w, y1: ib.y + ib.h, x2: x(zx1), y2: y(0) - 6, class: "auc-zoomline" }, gi);
          S("line", { x1: ib.x, y1: ib.y + ib.h, x2: x(zx0), y2: y(0) - 6, class: "auc-zoomline" }, gi);
        }
        var im = { l: 46, r: 14, t: 34, b: 22 }, ix = BVH.lin(zx0, zx1, ib.x + im.l, ib.x + ib.w - im.r), iy = BVH.lin(0, zy1, ib.y + ib.h - im.b, ib.y + im.t);
        S("text", { x: ib.x + 10, y: ib.y + 16, class: "auc-insettitle" }, gi, "zoom: the first bids, 0 to " + zy1 + " ETH");
        var ist = tickStep(zy1, 2);
        for (var iv = 0; iv <= zy1 + 1e-9; iv += ist) { S("line", { x1: ib.x + im.l, x2: ib.x + ib.w - im.r, y1: iy(iv), y2: iy(iv), class: iv ? "auc-grid" : "auc-base" }, gi); S("text", { x: ib.x + im.l - 6, y: iy(iv) + 3.5, "text-anchor": "end", class: "auc-tick auc-tick-s" }, gi, iv ? +iv.toFixed(3) + "" : "0"); }
        for (var it = Math.ceil(zx0 / 2000) * 2000; it <= zx1; it += 2000) S("text", { x: ix(it), y: ib.y + ib.h - 7, "text-anchor": "middle", class: "auc-tick auc-tick-s" }, gi, sgn(it, 0));
        B.series.forEach(function (p) {
          if (p[0] < zx0 || p[0] > zx1 || p[1] > zy1) return;
          var iw = p[2] === winIdx, ih = iy(0) - iy(p[1]);
          if (ih > 1.5) els.push([p[0], S("rect", { x: (ix(p[0]) - 0.6).toFixed(1), y: iy(p[1]).toFixed(1), width: 1.2, height: ih.toFixed(1), class: iw ? "auc-col auc-col-w" : "auc-col" }, gi)]);
          els.push([p[0], S("circle", { cx: ix(p[0]).toFixed(1), cy: iy(p[1]).toFixed(1), r: 2, class: iw ? "auc-dot auc-dot-w" : "auc-dot" }, gi)]);
        });
        var d = "";
        rec.forEach(function (a, k) { if (a[0] > zx1 || a[1] > zy1) return; var b = rec[k + 1]; var xe = b && b[0] <= zx1 ? ix(b[0]) : ix(Math.min(zx1, b ? b[0] : zx1)); d += (d ? "" : "M" + ix(a[0]).toFixed(1) + " " + iy(a[1]).toFixed(1)) + "H" + xe.toFixed(1) + (b && b[1] <= zy1 && b[0] <= zx1 ? "V" + iy(b[1]).toFixed(1) : ""); });
        var ip = S("path", { d: d, class: "auc-rec" }, gi); els.push([zx0, ip]);
        var jx = ix(je.t), jy = iy(je.eth);
        var jl = S("g", {}, gi);
        S("text", { x: jx - 8, y: jy - 8, "text-anchor": "end", class: "auc-lab" }, jl, BVH.eth(je.prev, false) + " \u2192 " + BVH.eth(je.eth, false) + " ETH");
        evEls.push([je.t, jl]);
        insetBox = ib;
      }
      /* the cursor */
      cursor = S("line", { x1: 0, x2: 0, y1: m.t - 22, y2: H - m.b, class: "auc-cursor" }, svg);
      cursorLab = S("text", { x: 0, y: H - m.b - 4, class: "auc-cursorlab" }, svg);
      state.x = x; state.H = H; state.m = m; state.w = w;
      apply();
    }
    function apply() {
      var t = state.t, x = state.x;
      els.forEach(function (e) { e[1].style.visibility = e[0] <= t ? "" : "hidden"; });
      evEls.forEach(function (e) { e[1].style.visibility = e[0] <= t + 1 ? "" : "hidden"; });
      var full = t >= tMax - 1;
      cursor.style.visibility = full ? "hidden" : "";
      cursorLab.style.visibility = full ? "hidden" : "";
      var cx = x(t);
      cursor.setAttribute("x1", cx); cursor.setAttribute("x2", cx);
      cursorLab.setAttribute("x", cx + (cx > state.w - 70 ? -6 : 6)); cursorLab.setAttribute("text-anchor", cx > state.w - 70 ? "end" : "start");
      cursorLab.textContent = sgn(t);
      if (o.onStep) { var cur = null; ev.forEach(function (e) { if (e.t <= t + 1) cur = e; }); o.onStep(cur, t); }
    }
    draw();
    var rt; window.addEventListener("resize", function () { clearTimeout(rt); rt = setTimeout(draw, 120); });
    BVH.onTheme.push(function () { /* colours are CSS variables: nothing to redraw */ });
    /* playback runs at an even pace across the drawn axis (the compressed quiet seconds pass quickly) */
    var F = tBreak != null ? 0.32 : null;
    function frac(t) { if (F == null) return (t - tMin) / (tMax - tMin); return t <= tBreak ? F * (t - tMin) / (tBreak - tMin) : F + (1 - F) * (t - tBreak) / (tMax - tBreak); }
    function tAt(f) { if (F == null) return tMin + f * (tMax - tMin); return f <= F ? tMin + (f / F) * (tBreak - tMin) : tBreak + ((f - F) / (1 - F)) * (tMax - tBreak); }
    return { set: function (t) { state.t = t; apply(); }, events: ev, tMin: tMin, tMax: tMax, frac: frac, tAt: tAt };
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
    if (row.race_type === "deploy-window-copy") pos = "used the attacker's deployed contract before the attacker called it";
    else if (ahead === 0 && row.bot_idx != null && row.atk_idx != null) pos = "same block, position " + row.bot_idx + " ahead of the attacker's " + row.atk_idx;
    else if (ahead > 0) pos = ahead + " block" + (ahead > 1 ? "s" : "") + " ahead of the attacker";
    var bot = String(row.bot || "").replace(/\s*\(.*\)\s*$/, "").trim();
    var src = row.raw && (row.raw.trace || row.raw.block);
    return '<article class="rc">' +
      '<header class="rc-h"><h3><a href="' + href + '">' + esc(name) + "</a></h3><span class=\"rc-d\">" + BVH.dateLong(row.date) + "</span></header>" +
      (sub ? '<p class="rc-sub">' + esc(sub) + "</p>" : "") +
      '<p class="rc-who"><b>' + esc(bot) + "</b>" + (pos ? " " + esc(pos) : "") + BVH.rawA(row.raw && row.raw.block, "block", "The block: its date, and the bot's position in it") + (row.headline ? "" : ' <span class="pill no" title="' + esc(BVH.RT[row.race_type] ? BVH.RT[row.race_type].def : "") + '">not in the headline count</span>') + "</p>" +
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

  function dodoNote(row) {
    var m = /and ([\d.]+) ETH to/.exec(row.fate || "");
    return "Antelope later sent back tokens" + (m ? " and " + E(+m[1]) : "") + " to DODO; how much of the take that covers is not reconciled.";
  }
  function punkNote(row) { return E(row.gross_eth - ((row.money && row.money.bot_net_eth) || 0) - (row.paid_to_builder_eth || 0), 2, false) + " ETH-equivalent of the take was sent on to the attacker. The bot kept a fee Punk agreed to and returned the rest."; }
  function kelpNote(row) { return "Taken as rsETH and valued in ETH at the swap rate inside the transaction."; }
  var GALLERY = [
    ["blueberry-2024", null, { victim: "Blueberry" }],
    ["curve-vyper-2023--peth", null, { victim: "JPEG'd" }],
    ["curve-vyper-2023--crv-eth-2", null, { victim: "Curve" }],
    ["kelp-rseth-2026", null, { victim: "the Safe's owner", noteFn: kelpNote }],
    ["punk-2021", null, { victim: "Punk", noteFn: punkNote }],
    ["dodo-v2-2021", null, { victim: "DODO", noteFn: dodoNote }],
    ["defiplaza-2024", null, { victim: "DeFi Plaza" }],
    ["transitswap-2022", null, { victim: "Transit Swap" }],
    ["earningfarm-2022", null, { victim: "Earning.Farm" }]
  ];

  Promise.all([BVH.json("data/incidents.json"), BVH.json("data/incident/makina-2026.json")])
    .then(function (r) {
      var rows = r[0], D = r[1], row = rows.filter(function (x) { return x.id === "makina-2026"; })[0];
      beats(D, row); hero(D, row); auction(D); windowStrip(D); block(D); money(D, row); aftermath(D);
      gallery(rows);
    })
    .catch(function (e) { BVH.loadError($("#r-hero-body"), e); });

  var fnHero = RV.footnotes();

  function hero(D, row) {
    var dep = RV.events(D).filter(function (e) { return e.id === "deploy"; })[0], depEv = (D.events || []).filter(function (e) { return e.kind === "deploy" && /attack contract/i.test(e.detail || ""); })[0];
    var gap = dep ? -dep.t : 12000, bot = D.txs.filter(function (t) { return t.role === "bot"; })[0];
    var botEv = (D.events || []).filter(function (e) { return e.kind === "tx" && /Copy of the attack/.test(e.detail || ""); })[0];
    var kept = botEv && botEv.derived && botEv.derived[0] ? botEv.derived[0].shown : null;
    $("#r-dek").innerHTML = "At " + BVH.clock(depEv.t, false) + " UTC on " + BVH.dateLong(D.date) + ", an attacker put a contract on Ethereum built to drain Makina Finance" + fnHero(depEv.raws && depEv.raws[0] || depEv.raw, "Deploy transaction trace") +
      ". " + Math.round(gap / 1000) + " seconds later, at the very top of the next block, someone else ran the same plan and paid " + E(bot.cb_eth) + " to the block builder to go first" + fnHero(D.incident_raw && D.incident_raw.copy_tx_trace || D.block.raw.trace, "Trace of the copy, with the payment to the builder") + ". The attacker never got to press the button.";
    var b0 = depEv.block, b1 = D.block.number;
    $("#r-blocks").innerHTML =
      '<div class="rb rb-atk"><span class="rb-k">Block ' + b0.toLocaleString("en-US") + '</span><span class="rb-t">' + BVH.clock(depEv.t, false) + ' UTC</span><span class="rb-what"><i class="dot-atk" aria-hidden="true"></i>The attacker deploys the drain contract</span>' + '<span class="rb-src">' + BVH.rawA(depEv.raws && depEv.raws[0] || depEv.raw, "raw", "Deploy transaction trace") + "</span></div>" +
      '<div class="rb-gap" aria-label="' + Math.round(gap / 1000) + ' seconds later"><span>' + Math.round(gap / 1000) + ' s</span></div>' +
      '<div class="rb rb-bot"><span class="rb-k">Block ' + b1.toLocaleString("en-US") + ', position ' + D.bot_idx + '</span><span class="rb-t">' + BVH.clock(D.block.ts_ms, false) + ' UTC</span><span class="rb-what"><i class="dot-bot" aria-hidden="true"></i>A searcher runs the same calls, pays ' + E(bot.cb_eth) + " to the builder" + (kept ? " and keeps " + esc(kept) : "") + '</span><span class="rb-src">' + BVH.rawA(D.block.raw.block, "raw", "The block, with its timestamp") + BVH.rawA(D.incident_raw && D.incident_raw.copy_tx_trace, "trace", "Trace of the copy transaction") + "</span></div>";
  }

  function auction(D) {
    var ev = null, cap = $("#auc-cap"), list = $("#auc-steps");
    var chart = RV.auction($("#auc"), D, {
      onStep: function (e) {
        if (!e) { cap.innerHTML = '<span class="cap-t">' + "Before the deploy" + "</span>"; mark(-1); return; }
        cap.innerHTML = '<span class="cap-n">' + e.n + '</span><span class="cap-t"><b>' + sgn(e.t) + "</b> " + esc(e.title) + '</span><span class="cap-x">' + esc(e.text) + "</span>";
        mark(e.n);
      }
    });
    ev = chart.events;
    list.innerHTML = ev.map(function (e) {
      return '<li data-n="' + e.n + '" class="st-' + e.id + '"><span class="st-n">' + e.n + '</span><span class="st-time">' + sgn(e.t) + '<small>' + BVH.clock(D.t0_ms + e.t) + "</small></span><span class=\"st-body\"><b>" + esc(e.title) + "</b> " + esc(e.text) + (e.rawHTML || BVH.rawA(e.raw, "raw", e.rawTitle)) + "</span></li>";
    }).join("");
    function mark(n) { Array.prototype.forEach.call(list.children, function (li) { li.classList.toggle("is-cur", +li.getAttribute("data-n") === n); li.classList.toggle("is-future", +li.getAttribute("data-n") > n && n > 0); }); }
    BVH.player($("#auc-ctrl"), {
      min: 0, max: 1, step: 0.001, duration: 16000, label: "Time from the start of the slot",
      stops: ev.map(function (e) { return { t: chart.frac(e.t), label: e.title }; }),
      format: function (v) { return sgn(chart.tAt(v)); },
      onChange: function (v) { chart.set(chart.tAt(v)); }
    });
    var A = D.auction, B = A.bids;
    $("#auc-src").innerHTML = "Each dot is one block a builder offered the proposer for this slot, at the price it offered. " + B.n_total + " bids from " + (A.n_builders || B.builders.length) + " builders" + BVH.bidsA(A) + "; " + B.n_shown + " are drawn, including every new best bid. Each bid is a thin column of light from zero up to its price. Amber columns are builder " + esc(A.winner.builder) + "'s bids; the line is the best bid so far, amber while " + esc(A.winner.builder) + " holds it. Winning bid from the relay's delivery record" + BVH.rawA(A.raw.delivered, "raw", "Relay record of the payload delivered to the proposer") + ".";
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
    if (k) set("know-copy", "<b>The copy.</b> The attacker never sent a call, so there is no attack transaction to compare with. Instead, " + k[3] + "% of the bot's non-zero calldata bytes (" + k[1] + " of " + k[2] + ") appear verbatim in the attacker's contract code, in runs of 16 bytes or more. Compare the bot's transaction" + BVH.rawA(ir.copy_tx, "raw", "The bot's transaction, with its calldata") + " with the attacker's deployed code" + BVH.rawA(ir.attack_contract_code, "raw", "The attacker contract's runtime code") + "; our count is in the race data" + BVH.rawA("data/incident/makina-2026.json", "data", "Derived: the byte-overlap count, in the race's narrative") + ".");
    set("know-mem", "<b>The mempool.</b> The public mempool archive covers that day" + BVH.rawA(ir.mempool_dumpster_index, "index", "The archive's month index, listing that day's file") + " but has neither the deploy nor the copy" + BVH.rawA(ir.mempool_dumpster_day, "day rows", "Rows cut from that day's archive file for the cited transactions: none matched") + ", so neither was broadcast publicly before landing, or every archive source missed them.");
  }

  function windowStrip(D) {
    var ev = RV.events(D), dep = ev.filter(function (e) { return e.id === "deploy"; })[0], win = ev.filter(function (e) { return e.id === "win"; })[0];
    var depEv = (D.events || []).filter(function (e) { return e.kind === "deploy" && /attack contract/i.test(e.detail || ""); })[0];
    /* the two block timestamps; the off-chain work and the proposer's choice are not timed by anything public */
    var gap = depEv && depEv.t != null ? D.block.ts_ms - depEv.t : null;
    if (gap != null) $("#win-span").textContent = Math.round(gap / 1000) + " seconds";
    $("#win-from").innerHTML = "<b>" + BVH.clock(D.t0_ms + dep.t, false) + "</b> block " + (D.block.number - 1).toLocaleString("en-US") + " carries the contract" + BVH.rawA(D.incident_raw && D.incident_raw.deploy_tx, "raw", "The deploy transaction");
    $("#win-to").innerHTML = "<b>" + BVH.clock(D.block.ts_ms, false) + "</b> block " + D.block.number.toLocaleString("en-US") + "'s timestamp" + BVH.rawA(D.block.raw.block, "raw", "The block, with its timestamp") + (win ? '<small>winning block first bid to the relay at ' + sgn(win.t) + "</small>" : "");
  }

  function block(D) {
    var n = D.block.ntx, strip = D.strip || [], box = $("#blk");
    var bot = D.txs.filter(function (t) { return t.role === "bot"; })[0], pay = D.txs.filter(function (t) { return t.role === "builder" && t.label === "builder payout"; })[0];
    var cells = "";
    for (var i = 0; i < n; i++) {
      var s = strip[i] || [], cls = s[2] === "bot" ? "bc-bot" : s[2] === "builder" ? "bc-bld" : "bc-tx";
      cells += '<i class="' + cls + '" title="position ' + i + (s[2] === "bot" ? ": the copy" : s[2] === "builder" ? ": builder pays the proposer" : "") + '"></i>';
    }
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
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(fit);
    $("#ice-note").innerHTML = "Bars are drawn to scale against the " + E(G) + " taken. The builder kept " + E(F.builder_kept_eth) + " of this payment and later forwarded " + (fwdEth != null ? E(fwdEth, 1) : "it") + " to " + (fwd ? fwd[2].slice(0, 6) : "another address") + (fwdEth != null && fwdEth - F.builder_kept_eth > 1e-6 ? ", adding " + BVH.eth2(fwdEth - F.builder_kept_eth) + " of its own funds" : "") + ". The bot's " + (keptTxt && keptTxt.derived ? esc(keptTxt.derived[0].shown) : "") + " is " + esc(keptTxt && keptTxt.derived ? keptTxt.derived[0].how : "") + ".";
    var split = BVH.moneySplit(row, "Makina");
    $("#money-split").innerHTML = BVH.splitHTML(split, { sources: BVH.moneySrc(row, D) });
  }

  function aftermath(D) {
    var after = (D.events || []).filter(function (e) { return e.t && e.t > D.block.ts_ms && (e.kind === "message" || e.kind === "return") && !/test transaction|Recovery Safe/i.test(e.detail || ""); });
    $("#after").innerHTML = after.map(function (e) {
      var d = e.utc ? BVH.dateLong(e.utc.slice(0, 10)) + " " + e.utc.slice(11, 16) : "";
      return '<li class="af-' + e.kind + '"><span class="af-t">' + d + ' UTC</span><span class="af-k">' + (e.kind === "return" ? "funds move" : "on-chain message") + '</span><span class="af-d">' + esc(e.detail) + BVH.rawA(e.raw, "raw", "Saved source for this event") + '<small>' + esc(e.actor || "") + "</small></span></li>";
    }).join("");
  }

  function gallery(rows) {
    var ids = GALLERY.map(function (g) { return g[0]; });
    Promise.all(ids.map(function (id) { return BVH.json("data/incident/" + id + ".json").catch(function () { return null; }); })).then(function (ds) {
      $("#gal").innerHTML = GALLERY.map(function (g, i) {
        var row = rows.filter(function (r) { return r.id === g[0]; })[0];
        if (!row) return "";
        var o = Object.assign({}, g[2]); if (o.noteFn) o.note = o.noteFn(row);
        return RV.raceCard(ds[i], row, o);
      }).join("");
    });
  }
})();
