(function () {
  "use strict";
  var S = BVH.svg, esc = BVH.esc, rawA = BVH.rawA;
  BVH.chrome("none");
  var root = document.getElementById("root");

  BVH.json("data/incidents.json").then(function (rows) {
    var id = BVH.qs("id"), slug = BVH.qs("slug"), sub = BVH.qs("sub"), row = null;
    /* incident.html#<id> (the form the hosted copy uses) also works here when no query is given */
    if (!id && !slug && location.hash.length > 1) { var hk = decodeURIComponent(location.hash.slice(1).split("~")[0]); if (rows.some(function (r) { return r.id === hk; })) id = hk; else if (hk.indexOf("--") > 0) { slug = hk.slice(0, hk.indexOf("--")); sub = hk.slice(hk.indexOf("--") + 2); } else slug = hk; }
    if (id) row = rows.filter(function (r) { return r.id === id; })[0];
    if (!row && slug) {
      var c = rows.filter(function (r) { return r.slug === slug; });
      if (sub) row = c.filter(function (r) { return BVH.slugify(r.sub) === BVH.slugify(sub); })[0];
      if (!row) row = c.filter(function (r) { return r.headline; })[0] || c[0];
    }
    if (!row) { root.innerHTML = '<div class="callout bad" style="margin-top:60px">No race with that name. <a href="index.html#table">Pick one from the table</a>.</div>'; return; }
    if (row.stub) { document.title = row.title + " | The Bot Beat the Hacker"; renderStub(row, rows); return; }
    return BVH.json("data/incident/" + row.id + ".json").then(function (D) {
      document.title = D.title + " | The Bot Beat the Hacker"; render(D, row, rows);
      // the replay is laid out for the width it is given; lay it out again when the window crosses the phone/desktop line
      var mode = isNarrow(), to;
      window.addEventListener("resize", function () { clearTimeout(to); to = setTimeout(function () { if (isNarrow() !== mode) { mode = isNarrow(); render(D, row, rows); } }, 200); });
    });
  }).catch(function (e) { BVH.loadError(root, e); });

  function isNarrow() { return (document.documentElement.clientWidth || window.innerWidth) < 760; }

  /* rows without a replay: investigated and set aside (not a race, or a late copy). Say so plainly. */
  function renderStub(row, rows) {
    var why = { "no-race": "Not a race. We looked, and nothing copied or beat this attacker.", "late-copy": "Not counted. A copy that came after the attacker had already succeeded.", "bot-was-first-exploiter": "Not counted. No separate attacker." }[row.race_type] || "Not counted in the headline.";
    var sibs = rows.filter(function (r) { return r.slug === row.slug; });
    var h = '<div class="ihead"><p class="small mono muted" style="margin:0 0 10px"><a href="index.html#table">All races</a></p><h1>' + esc(row.title) + '</h1><p class="meta"><span>' + BVH.dateLong(row.date) + '</span><span class="pill no">' + (row.race_type === "no-race" ? "not a race" : "not counted") + '</span><span class="pill">' + esc(BVH.rtName(row.race_type)) + '</span><span class="pill warn">no replay: ' + (row.mempool === "in-block-only" ? "in-block evidence only" : "not in the mempool archive") + '</span></p>';
    if (sibs.length > 1) h += '<div class="subtabs" role="navigation" aria-label="Races in this incident">' + sibs.map(function (s) { return '<a href="' + qhref(s) + '"' + (s.id === row.id ? ' aria-current="true"' : "") + ">" + esc(s.sub || "main race") + "</a>"; }).join("") + "</div>";
    h += '<p class="lede" style="margin-top:22px">' + esc(row.one_liner || "") + '</p></div>';
    h += '<section class="sec" style="padding-top:36px"><div class="callout"><b>' + why + '</b> This entry is listed so that the line between a race and a coincidence is visible. There is no replay because there is no race to replay.</div>';
    if (row.fate) h += '<h3 style="font-size:19px">Why it is set aside</h3><p class="prose">' + esc(row.fate) + '</p>';
    h += '<p class="small"><a href="methods.html#evidence">How we judged a race</a> &nbsp; <a href="index.html#table">Back to the table</a></p></section>';
    var idx = rows.findIndex(function (r) { return r.id === row.id; }), prev = rows[idx - 1], next = rows[idx + 1];
    h += '<nav class="pn" aria-label="Neighbouring races">' + (prev ? '<a href="' + qhref(prev) + '">earlier: ' + esc(prev.title) + "</a>" : "<span></span>") + (next ? '<a href="' + qhref(next) + '">later: ' + esc(next.title) + "</a>" : "<span></span>") + "</nav>";
    root.innerHTML = h;
  }

  function qhref(r) { return "incident.html?slug=" + encodeURIComponent(r.slug) + (r.sub ? "&sub=" + encodeURIComponent(r.sub) : ""); }

  function render(D, row, rows) {
    var sibs = rows.filter(function (r) { return r.slug === D.slug; });
    var memPill = { measured: '<span class="pill yes">mempool measured</span>', "in-block-only": '<span class="pill warn">in-block evidence only</span>', "absent-from-archive": '<span class="pill warn">not in the mempool archive</span>' }[D.mempool.state] || "";
    if (D.mempool.state === "measured" && row && row.mempool === "absent-from-archive") memPill = '<span class="pill warn" title="Some other attacker transactions of this incident were seen in the archive, but not the one this race is about.">cited attacker tx not in the mempool archive</span>';
    var h = '<div class="ihead"><p class="small mono muted" style="margin:0 0 10px"><a href="index.html#table">All races</a></p><h1>' + esc(D.title) + (D.sub ? "" : "") + '</h1><p class="meta"><span>' + BVH.dateLong(D.date) + '</span><span class="pill ' + (D.headline ? "yes" : "no") + '">' + (D.headline ? "bot beat the hacker" : D.race_type === "no-race" ? "not a race" : "not counted in the headline") + '</span><span class="pill">' + esc(BVH.rtName(D.race_type)) + "</span>" + '<span class="pill" title="' + esc(D.evidence_strength_basis || "") + '">evidence: ' + esc(D.evidence_strength || "n/a") + "</span>" + memPill + "<span>bot: " + esc(D.bot) + "</span></p>";
    if (sibs.length > 1) h += '<div class="subtabs" role="navigation" aria-label="Races in this incident">' + sibs.map(function (s) { return '<a href="' + qhref(s) + '"' + (s.id === D.id ? ' aria-current="true"' : "") + ">" + esc(s.sub || "main race") + "</a>"; }).join("") + "</div>";
    h += '<p class="lede" style="margin-top:22px">' + esc(D.one_liner || "") + "</p></div>";
    if (D.caveat) h += '<p class="callout">' + esc(D.caveat) + '</p>';
    if (D.public_ordering) {
      var O = D.public_ordering;
      h += '<div class="callout"><p>' + esc(D.comparison_policy || "") + '</p><p>Bot: ' + BVH.explorer(O.bot_tx) + ' block ' + O.bot_block + ', position ' + O.bot_position + '. Raced attacker transaction: ' + BVH.explorer(O.raced_attacker_tx) + ' block ' + O.attacker_block + ', position ' + O.attacker_position + '.</p>' + (O.attacker_deploy ? '<p>Attacker deployment: ' + BVH.explorer(O.attacker_deploy.hash) + ' block ' + O.attacker_deploy.block + ', position ' + O.attacker_deploy.index + '.</p>' : '') + '</div>';
    }
    h += '<section class="player" aria-label="Race replay">' +
      '<div class="ctrl"><button type="button" id="play" aria-label="Play or pause the replay">Play</button><button type="button" class="ghost" id="restart">Restart</button>' +
      '<span class="clock" id="clock" aria-hidden="true"></span>' +
      '<input type="range" id="scrub" aria-label="Scrub through time" min="0" max="1000" value="0">' +
      '<span class="seg" role="group" aria-label="Playback speed"><button type="button" data-s="0.5">0.5x</button><button type="button" data-s="1" aria-pressed="true">1x</button><button type="button" data-s="2">2x</button><button type="button" data-s="4">4x</button></span></div>' +
      '<div class="stage" id="stage" tabindex="0" role="group" aria-label="Replay graphic. Press space to play or pause."></div><div class="cap" id="cap" aria-live="off"></div>' +
      '<div class="legend" id="legend"></div><div id="sel" class="small mono" style="margin-top:10px;min-height:1.5em;color:var(--ink2)"></div></section>';
    h += '<div id="below"></div>';
    root.innerHTML = h;
    var player = buildPlayer(D);
    below(D, row, rows, player);
  }

  /* ================================================================ player */
  function buildPlayer(D) {
    var stageEl = document.getElementById("stage"), avail = Math.round(stageEl.clientWidth) || 1000, narrow = isNarrow();
    var W = narrow ? Math.max(300, Math.min(avail, 700)) : 1000, L = narrow ? 10 : 104, R = narrow ? 10 : 22, HD = narrow ? 26 : 0;
    var pre = D.pre_merge, A = D.auction, B = A && A.bids;
    var hasBids = !!(B && B.series.length);
    var lo, hi;
    if (pre) { lo = -1500; hi = D.next_block ? 9500 : 3000; }
    else {
      lo = -12000;
      D.mempool.entries.forEach(function (e) { if (e.seen && e.rel_ms > -30000 && e.rel_ms < 0) lo = Math.min(lo, Math.floor((e.rel_ms - 1500) / 1000) * 1000); });
      hi = Math.max(1800, hasBids ? Math.ceil((B.last_ms + 300) / 100) * 100 : 0);
      if (D.next_block) hi = 13200;
    }
    var x = BVH.lin(lo, hi, L, W - R);
    var svg = S("svg", { viewBox: "0 0 " + W + " 560", role: "group", "aria-label": "Race replay with three lanes: mempool, builder auction, block. A text ledger of every event follows below." });
    var timed = []; // [el, t]
    var y0 = 34, laneGap = 18;
    // clip for progressive reveal in lane 2
    var defs = S("defs", null, svg);
    var clip = S("clipPath", { id: "revealclip" }, defs); var clipRect = S("rect", { x: 0, y: 0, width: 0, height: 900 }, clip);
    var hatch = S("pattern", { id: "hatch", width: 5, height: 5, patternUnits: "userSpaceOnUse", patternTransform: "rotate(45)" }, defs);
    S("rect", { width: 5, height: 5, fill: "var(--bg2)" }, hatch); S("line", { x1: 0, y1: 0, x2: 0, y2: 5, stroke: "var(--atk)", "stroke-width": 2.2 }, hatch);

    /* axis */
    var axis = S("g", { class: "axis" }, svg);
    if (!pre) {
      var tstep = narrow ? (hi - lo > 16000 ? 6000 : 4000) : 2000;
      for (var s = Math.ceil(lo / tstep) * tstep; s <= hi; s += tstep) {
        var tx = x(s); S("line", { x1: tx, x2: tx, y1: y0 - 6, y2: y0, stroke: "var(--line2)" }, axis);
        S("text", { x: tx, y: y0 - 10, "text-anchor": tx < L + 20 ? "start" : tx > W - R - 20 ? "end" : "middle" }, axis, s === 0 ? (narrow ? "start" : "slot start") : (s > 0 ? "+" : "−") + Math.abs(s / 1000) + " s");
      }
      S("text", { x: L, y: 12, "text-anchor": "start" }, axis, narrow ? "seconds from slot start (" + BVH.clock(D.t0_ms, false) + " UTC)" : "time relative to the start of the slot (" + BVH.utc(D.t0_ms) + ")");
    } else if (narrow) {
      S("text", { x: L, y: 10 }, axis, "Pre-Merge: no slots, no relays.");
      S("text", { x: L, y: 23 }, axis, "The timeline starts when the block is sealed.");
    } else {
      S("text", { x: L, y: 12 }, axis, "Pre-Merge: no slots, no relays. The timeline starts when the block is sealed.");
    }
    function vline(t, color, dash, h0, h1, label) {
      var xx = x(t), g = S("g", null, svg);
      S("line", { x1: xx, x2: xx, y1: h0, y2: h1, stroke: color, "stroke-dasharray": dash || "4 4", "stroke-width": 1.2 }, g);
      return g;
    }

    /* ---------- lane 1: mempool ---------- */
    var M0 = D.mempool, nonMeasured = M0.state !== "measured", l1t = y0 + 8, c1 = l1t + HD;
    var msgTxt = M0.state === "in-block-only" ? "In-block evidence only: no public mempool archive for this date." : "The archive covers this day but did not see the cited transactions. Private order flow, or missed.";
    var mlines = narrow ? wrapWords(msgTxt, 40) : [msgTxt];
    var l1m = narrow && nonMeasured ? c1 + 46 + (mlines.length - 1) * 17 + 24 + 30 : c1 + 88;
    var l1h = narrow ? (nonMeasured ? l1m - l1t + 60 : 132 + HD) : 132;
    laneFrame(svg, "MEMPOOL", l1t, l1h, L, W - R, "first seen", narrow);
    var M = D.mempool, ents = M.entries.filter(function (e) { return e.seen; });
    var groups = [];
    ents.sort(function (a, b) { return a.t_ms - b.t_ms; }).forEach(function (e) { var g = groups[groups.length - 1]; if (g && Math.abs(g.t - e.t_ms) <= 5 && g.role === e.role) g.items.push(e); else groups.push({ t: e.t_ms, rel: e.rel_ms, role: e.role, items: [e] }); });
    var early = [];
    var lastX = -999, flip = 0;
    groups.forEach(function (g) {
      if (g.rel < lo || g.rel > hi) { early.push(g); return; }
      var xx = x(g.rel), col = g.role === "bot" ? "var(--bot)" : g.role === "attacker" ? "var(--atk)" : "var(--ink2)";
      if (xx - lastX < (narrow ? 110 : 150)) flip ^= 1; else flip = 0; lastX = xx;
      var gy = l1m, grp = S("g", { tabindex: 0, role: "button", "aria-label": (g.role || "tx") + " first seen " + BVH.clock(g.t) }, svg);
      grp.style.cursor = "pointer";
      // per-source ticks
      var srcs = {}; g.items.forEach(function (e) { (e.sources || []).forEach(function (s) { srcs[s.s] = Math.min(srcs[s.s] || 1e18, s.t); }); });
      Object.keys(srcs).forEach(function (k, i) { var sx = x(srcs[k] - D.t0_ms); if (sx >= L && sx <= W - R) S("line", { x1: sx, x2: sx, y1: gy + 12, y2: gy + 20 + (i % 2) * 4, stroke: col, "stroke-width": 1.2, opacity: .7 }, grp); });
      if (g.role === "bot") S("path", { d: "M" + xx + " " + (gy - 9) + "l9 9-9 9-9-9z", fill: "var(--bot)" }, grp);
      else S("circle", { cx: xx, cy: gy, r: 7, fill: col, stroke: "var(--bg2)", "stroke-width": 2 }, grp);
      var anchor = xx > (narrow ? W / 2 : W - 200) ? "end" : "start", lx = anchor === "end" ? xx - 12 : xx + 12;
      var lab = (g.role === "attacker" ? "attacker" : g.role === "bot" ? "bot" : "related") + (g.items.length > 1 ? " (" + g.items.length + " txs)" : "") + (narrow ? " seen" : " first seen");
      S("text", { x: lx, y: gy - 30 - flip * 32, "text-anchor": anchor, "font-size": narrow ? 11 : 12, "font-family": "var(--mono)", fill: "var(--ink)" }, grp, lab);
      S("text", { x: lx, y: gy - 17 - flip * 32, "text-anchor": anchor, "font-size": narrow ? 10 : 11, "font-family": "var(--mono)", fill: "var(--muted)" }, grp, BVH.clock(g.t));
      var tm = [grp, g.rel]; timed.push(tm);
      var html = function () { return "<b>" + (g.role || "tx") + " first seen</b><br>" + BVH.utc(g.t) + "<br>" + BVH.sec(g.rel, true) + " from slot start<br>" + Object.keys(srcs).length + " source(s): " + Object.keys(srcs).map(function (k) { return k + " " + BVH.clock(srcs[k]); }).join(", "); };
      BVH.tipFor(grp, html, function () { select("<b>" + esc(g.role || "tx") + " first seen</b> " + BVH.utc(g.t) + " &nbsp; " + g.items.map(function (e) { return '<code>' + BVH.short(e.h, 10, 6) + "</code> " + BVH.explorer(e.h) + BVH.memA(e.raw); }).join(" ") + " &nbsp; per-source times: " + Object.keys(srcs).map(function (k) { return esc(k) + " " + BVH.clock(srcs[k]); }).join(", ")); });
    });
    if (early.length) {
      var e0 = early[0], txt = "◀ " + (e0.role === "attacker" ? "attacker deploy" : e0.role || "tx") + " seen " + BVH.dur(Math.abs(e0.rel)) + " earlier (" + BVH.clock(e0.t, false) + ")";
      S("text", { x: L + 6, y: c1 + 28, "font-size": narrow ? 10.5 : 11.5, "font-family": "var(--mono)", fill: "var(--ink2)" }, svg, txt);
    }
    if (M.state !== "measured") {
      mlines.forEach(function (ln, k) { S("text", { x: L + 6, y: c1 + (narrow ? 46 : 58) + k * 17, "text-anchor": "start", "font-size": 14, "font-family": "var(--serif)", fill: "var(--ink)" }, svg, ln); });
      var mEnd = c1 + (narrow ? 46 : 58) + (mlines.length - 1) * 17;
      if (M.coverage_raw) { var a = S("a", { href: M.coverage_raw, target: "_blank" }, svg); S("text", { x: L + 6, y: mEnd + 20, "text-anchor": "start", class: "svg-raw" }, a, "archive index for that month (raw)"); }
    }
    if (M.covered && D.bot_idx != null) {
      var bx = x(0), g2 = S("g", null, svg);
      S("path", { d: "M" + bx + " " + (l1m - 8) + "l8 8-8 8-8-8z", fill: "none", stroke: "var(--bot)", "stroke-width": 1.6, "stroke-dasharray": "3 2" }, g2);
      var nsx = bx + 14 + (narrow ? 105 : 190) > W; S("text", { x: nsx ? bx - 14 : bx + 14, y: l1m + 34 + (narrow ? 14 : 0), "text-anchor": nsx ? "end" : "start", "font-size": 11, "font-family": "var(--mono)", fill: "var(--ink2)" }, g2, narrow ? "not seen publicly" : "bot tx: never seen publicly");
    }

    /* ---------- lane 2: builder auction ---------- */
    var l2t = l1t + l1h + laneGap, c2 = l2t + HD, l2h = (hasBids ? 256 : 170) + HD + (narrow && !hasBids ? 92 : 0), l2b = l2t + l2h;
    laneFrame(svg, "BUILDER AUCTION", l2t, l2h, L, W - R, hasBids ? "relay bids" : "no bid stream", narrow);
    var revealed = null, recPath = null, winEl = null, winT = null, dotLayer = null;
    if (hasBids) {
      var vmin = Infinity, vmax = 0; B.series.forEach(function (p) { if (p[1] > 0) { vmin = Math.min(vmin, p[1]); vmax = Math.max(vmax, p[1]); } });
      vmin = Math.max(vmin, 1e-4); var ylo = Math.pow(10, Math.floor(Math.log10(vmin))), yhi = Math.pow(10, Math.ceil(Math.log10(vmax * 1.2)));
      if (yhi / ylo < 100) ylo = yhi / 100;
      var y = BVH.log(ylo, yhi, l2b - 24, c2 + 56);
      BVH.logTicks(ylo, yhi).forEach(function (v) {
        var yy = y(v); S("line", { x1: L, x2: W - R, y1: yy, y2: yy, class: "gridl" }, svg);
        S("text", narrow ? { x: L + 2, y: yy - 3, "text-anchor": "start", "font-size": 10, "font-family": "var(--mono)", fill: "var(--muted)" } : { x: L - 8, y: yy + 4, "text-anchor": "end", "font-size": 11, "font-family": "var(--mono)", fill: "var(--muted)" }, svg, (v >= 1 ? v : v.toPrecision(1)) + " ETH");
      });
      var layer = S("g", { "clip-path": "url(#revealclip)" }, svg); dotLayer = layer;
      B.series.forEach(function (p) {
        var cx = x(p[0]), cy = y(p[1]); if (cx < L - 2 || cx > W - R + 2) return;
        var isRec = !!(p[3] & 2), isWin = !!(p[3] & 1);
        if (isWin) return;
        var c = S("circle", { cx: cx, cy: cy, r: isRec ? 3.2 : 2.3, fill: "var(--bld)", opacity: isRec ? .95 : .42 }, layer);
        BVH.tipFor(c, function () { return "<b>" + BVH.eth(p[1]) + "</b> " + (isRec ? "(new record)" : "") + "<br>" + esc(B.builders[p[2]]) + "<br>" + BVH.clock(D.t0_ms + p[0]) + " (" + BVH.sec(p[0], true) + ")<br>" + (p[4] != null ? p[4] + " txs, " : "") + "block " + esc(p[5] || ""); });
        c.addEventListener("click", function () { select("<b>Bid " + BVH.eth(p[1]) + "</b> by " + esc(B.builders[p[2]]) + " at " + BVH.clock(D.t0_ms + p[0]) + " UTC (" + BVH.sec(p[0], true) + ")" + (p[4] != null ? ", " + p[4] + " txs" : "") + " " + BVH.bidsA(A)); });
      });
      recPath = S("path", { fill: "none", stroke: "var(--bld)", "stroke-width": 2, "stroke-linejoin": "round" }, svg);
      // winning bid
      var W0 = A.winner;
      if (W0 && W0.t_ms != null && W0.eth_bid != null) {
        var wx = x(W0.t_ms), wy = y(W0.eth_bid);
        winEl = S("g", { tabindex: 0, role: "button", "aria-label": "Winning bid " + BVH.eth(W0.eth_bid) }, svg); winEl.style.cursor = "pointer"; winT = W0.t_ms;
        S("circle", { cx: wx, cy: wy, r: 8, fill: "var(--gold)", opacity: .25 }, winEl);
        S("circle", { cx: wx, cy: wy, r: 5.5, fill: "var(--gold)", stroke: "var(--bg2)", "stroke-width": 2 }, winEl);
        var wa = narrow ? ((wx + 12 + 150 > W - R && wx - 12 - 150 >= L) ? "end" : "start") : (wx > W - 330 ? "end" : "start"), wlx = wa === "end" ? wx - 12 : wx + 12;
        S("text", { x: wlx, y: wy - 24, "text-anchor": wa, "font-size": narrow ? 11.5 : 12.5, "font-family": "var(--mono)", "font-weight": 600, fill: "var(--ink)" }, winEl, "winning bid " + BVH.eth(W0.eth_bid));
        S("text", { x: wlx, y: wy - 10, "text-anchor": wa, "font-size": narrow ? 10 : 11, "font-family": "var(--mono)", fill: "var(--ink2)" }, winEl, (narrow ? trunc(W0.builder || "", 14) : (W0.builder || "")) + " at " + BVH.sec(W0.t_ms, true));
        timed.push([winEl, W0.t_ms]);
        BVH.tipFor(winEl, function () { return "<b>Winning bid " + BVH.eth(W0.eth_bid) + "</b><br>" + esc(W0.builder || "") + "<br>" + BVH.clock(D.t0_ms + W0.t_ms) + " (" + BVH.sec(W0.t_ms, true) + ")<br>delivered by " + esc((W0.relays || []).join(", ") || "n/a"); }, function () { select("<b>Winning bid " + BVH.eth(W0.eth_bid) + "</b> from " + esc(W0.builder || "") + " at " + BVH.clock(D.t0_ms + W0.t_ms) + " UTC, delivered by " + esc((W0.relays || []).join(", ")) + ". Proposer payment " + BVH.eth(W0.eth) + " " + rawA(A.raw.delivered, "raw delivered", "proposer_payload_delivered response") + BVH.bidsA(A)); });
      }
      // attacker-seen and reaction markers
      if (D.attacker_seen_rel_ms != null) {
        var ax = x(D.attacker_seen_rel_ms);
        var gl = S("g", null, svg); S("line", { x1: ax, x2: ax, y1: l1m + 4, y2: l2b - 6, stroke: "var(--atk)", "stroke-dasharray": "3 4", "stroke-width": 1.2, opacity: .8 }, gl); timed.push([gl, D.attacker_seen_rel_ms]);
        if (D.reaction) {
          var rx = x(D.reaction.t_ms), g3 = S("g", null, svg);
          S("line", { x1: rx, x2: rx, y1: c2 + 20, y2: l2b - 6, stroke: "var(--bot)", "stroke-dasharray": "3 4", "stroke-width": 1.2, opacity: .85 }, g3);
          S("line", { x1: ax, x2: rx, y1: c2 + 22, y2: c2 + 22, stroke: "var(--ink2)", "stroke-width": 1.2 }, g3);
          S("text", { x: narrow ? Math.max(L + 70, Math.min(W - R - 70, (ax + rx) / 2)) : (ax + rx) / 2, y: c2 + 17, "text-anchor": "middle", "font-size": narrow ? 10.5 : 11.5, "font-family": "var(--mono)", fill: "var(--ink)" }, g3, BVH.dur(D.reaction.delay_ms) + (narrow ? " to big bid" : " to first big bid"));
          timed.push([g3, D.reaction.t_ms]);
        }
      }
    } else {
      // fallback: gas-price auction
      var bars = D.strip.slice(0, Math.min(40, D.strip.length)), mx = Math.max.apply(null, bars.map(function (b) { return b[3] || 0; }).concat([1]));
      var gx = BVH.lin(0, bars.length, L + 6, W - R - 6), by = l2b - 28, gh = narrow ? 64 : l2h - 110, gy2 = BVH.log(0.1, Math.max(mx * 1.5, 10), by, by - gh);
      var note = pre ? "Pre-Merge: no relay and no bid stream. Priority was bought with gas price, shown here per block position (gwei)." : (A && A.winner && A.winner.eth != null ? "No bid history survives for this slot (relay retention, or the proposer was not registered with the relay that kept it). The delivered value was " + BVH.eth(A.winner.eth) + "." : "This block was not built through a relay: no bid stream exists. Priority was bought with gas price (gwei by block position).");
      (narrow ? wrapWords(note, 46) : [note]).forEach(function (ln, k) { S("text", { x: L + 6, y: (narrow ? c2 + 12 : l2t + 54) + k * 16, "font-size": 13, "font-family": "var(--serif)", fill: "var(--ink)" }, svg, ln); });
      S("line", { x1: L, x2: W - R, y1: by, y2: by, class: "gridl" }, svg);
      var gl2 = S("g", null, svg);
      bars.forEach(function (b, i) {
        var tip = Math.max(b[3] || 0, 0.1), bh = by - gy2(tip), col = b[2] === "bot" ? "var(--bot)" : b[2] === "attacker" ? "var(--atk)" : b[2] === "builder" ? "var(--bld)" : "var(--line2)";
        var bw = Math.max(3, (W - R - L - 12) / bars.length - 3);
        var r = S("rect", { x: gx(i) , y: by - bh, width: bw, height: Math.max(2, bh), fill: col, opacity: b[2] ? 1 : .6 }, gl2);
        BVH.tipFor(r, function () { return "position " + b[0] + (b[2] ? " (" + b[2] + ")" : "") + "<br>tip " + (b[3] != null ? b[3] : "n/a") + " gwei"; });
      });
      S("text", { x: L + 6, y: by + 16, "font-size": 11, "font-family": "var(--mono)", fill: "var(--muted)" }, svg, (narrow ? "positions 0 to " : "block position 0 → ") + (bars.length - 1) + (D.block.ntx > bars.length ? " (first " + bars.length + " of " + D.block.ntx + ")" : ""));
      timed.push([gl2, pre ? lo : -3000]);
      if (A && A.raw && A.raw.delivered) { var aa = S("a", { href: A.raw.delivered, target: "_blank" }, svg); S("text", { x: W - R, y: narrow ? l2b - 8 : l2t + 20, "text-anchor": "end", class: "svg-raw" }, aa, "raw delivered"); }
    }
    // slot-start line
    if (!pre) {
      var sx0 = x(0);
      S("line", { x1: sx0, x2: sx0, y1: y0, y2: l2b + 6, stroke: "var(--ink2)", "stroke-width": 1.2, opacity: .8 }, svg);
    }

    /* ---------- lane 3: block ---------- */
    var l3t = l2b + laneGap, H3 = narrow ? HD + 14 : 0;
    var blockRow = strip(svg, D, D.strip, D.txs, D.block.ntx, 0, l3t + 34 + H3, L, W - R, timed, select, "block " + D.block.number, true, hatch, narrow);
    var l3h = blockRow.h + 52 + H3;
    var nextH = 0;
    if (D.next_block) {
      var nb = D.next_block, nstrip = [], nnot = nb.notable.map(function (t) { return { i: t.i, h: t.h, role: t.role, ok: t.ok, from_: t.from_, to: t.to, tip: t.tip, value_eth: t.value_eth, cb_eth: 0, err: t.err, raw: nb.raw }; });
      var row2 = strip(svg, D, null, nnot, nb.ntx || 0, 12000, l3t + 34 + H3 + blockRow.h + 40, L, W - R, timed, select, "block " + nb.number + " (next slot)", false, hatch, narrow);
      nextH = row2.h + 44;
    }
    laneFrame(svg, "BLOCK", l3t, l3h + nextH, L, W - R, "tx order", narrow);
    var totalH = l3t + l3h + nextH + 12;
    svg.setAttribute("viewBox", "0 0 " + W + " " + totalH);
    var bl = S("g", null, svg);
    var blockLabelA = S("a", { href: D.block.raw.block || "#", target: "_blank" }, bl);
    S("text", { x: L + 6, y: l3t + (narrow ? 38 : 22), "font-size": narrow ? 11 : 12, "font-family": "var(--mono)", fill: "var(--ink)" }, bl, "block " + D.block.number + " · " + D.block.ntx + " txs" + (narrow ? "" : " · built by " + (D.block.builder || "unknown")));
    if (narrow) S("text", { x: L + 6, y: l3t + 52, "font-size": 11, "font-family": "var(--mono)", fill: "var(--ink2)" }, bl, "built by " + trunc(D.block.builder || "unknown", 30));
    if (D.block.raw.block) S("text", narrow ? { x: L + 6, y: l3t + 66, "text-anchor": "start", class: "svg-raw" } : { x: W - R, y: l3t + 22, "text-anchor": "end", class: "svg-raw" }, blockLabelA, "raw block");

    // sealed marker text for lane 3 if in-window
    document.getElementById("stage").appendChild(svg);

    /* legend */
    document.getElementById("legend").innerHTML = '<span><svg viewBox="0 0 14 14"><circle cx="7" cy="7" r="5" fill="var(--atk)"/></svg>attacker</span><span><svg viewBox="0 0 14 14"><path d="M7 1l6 6-6 6-6-6z" fill="var(--bot)"/></svg>bot</span><span><svg viewBox="0 0 14 14"><rect x="2" y="2" width="10" height="10" fill="var(--bld)"/></svg>builder payout / bid</span><span><svg viewBox="0 0 14 14"><circle cx="7" cy="7" r="5" fill="var(--gold)"/></svg>winning bid</span><span><svg viewBox="0 0 14 14"><rect x="1" y="1" width="12" height="12" fill="url(#hatch)" stroke="var(--atk)" stroke-dasharray="2 2"/></svg>reverted</span><span><svg viewBox="0 0 14 14"><rect x="3" y="4" width="8" height="9" fill="var(--gold)"/></svg>coinbase transfer to the builder</span>' + (hasBids ? '<span>dots: ' + B.n_shown + " of " + ((A.raw.capped || []).length ? "at least " : "") + B.n_total + " bids shown" + BVH.bidsA(A) + "</span>" : "");

    /* ---------- story steps ---------- */
    var steps = makeSteps(D, lo, hi);
    var capEl = document.getElementById("cap");

    /* ---------- playback ---------- */
    var ph = BVH.reduced() ? hi : lo, playing = false, speed = 1, last = 0, raf = 0;
    var scrub = document.getElementById("scrub"), clockEl = document.getElementById("clock"), playBtn = document.getElementById("play");
    scrub.min = lo; scrub.max = hi; scrub.step = 10;
    function select(html) { document.getElementById("sel").innerHTML = html; }
    function update() {
      var xp = x(ph);
      clipRect.setAttribute("width", Math.max(0, xp));
      timed.forEach(function (tm) { tm[0].style.visibility = ph >= tm[1] ? "visible" : "hidden"; tm[0].style.opacity = ph >= tm[1] ? 1 : 0; });
      if (recPath && hasBids) {
        var d = "", px = null, py = null, rec = B.record, yy = recY;
        for (var i = 0; i < rec.length; i++) { if (rec[i][0] > ph) break; var cx = x(rec[i][0]), cy = yy(rec[i][1]); d += (i ? "H" + cx.toFixed(1) + "V" + cy.toFixed(1) : "M" + cx.toFixed(1) + " " + cy.toFixed(1)); px = cx; py = cy; }
        if (px != null) d += "H" + Math.min(xp, W - R).toFixed(1);
        recPath.setAttribute("d", d);
      }
      var rel = ph;
      clockEl.textContent = pre ? (rel < 0 ? "before the block" : "block + " + (rel / 1000).toFixed(2) + " s") : "t " + (rel < 0 ? "−" : "+") + (Math.abs(rel) / 1000).toFixed(3) + " s";
      clockEl.title = pre ? "" : BVH.clock(D.t0_ms + rel) + " UTC";
      scrub.value = ph;
      var cur = null; steps.forEach(function (s) { if (s.t <= ph) cur = s; });
      capEl.innerHTML = cur ? cur.html : '<span class="muted">Press play to watch the race, or drag the slider.</span>';
      playBtn.textContent = playing ? "Pause" : (ph >= hi ? "Replay" : "Play");
    }
    var recY = null;
    if (hasBids) { var vmin2 = Infinity, vmax2 = 0; B.series.forEach(function (p) { vmin2 = Math.min(vmin2, p[1]); vmax2 = Math.max(vmax2, p[1]); }); vmin2 = Math.max(vmin2, 1e-4); var ylo2 = Math.pow(10, Math.floor(Math.log10(vmin2))), yhi2 = Math.pow(10, Math.ceil(Math.log10(vmax2 * 1.2))); if (yhi2 / ylo2 < 100) ylo2 = yhi2 / 100; recY = BVH.log(ylo2, yhi2, l2b - 24, c2 + 56); }
    function frame(ts) {
      if (!playing) return;
      var dt = Math.min(60, ts - last); last = ts;
      ph += dt * speed * (pre ? 1 : 1);
      if (ph >= hi) { ph = hi; playing = false; }
      update(); if (playing) raf = requestAnimationFrame(frame);
    }
    function play() { if (ph >= hi) ph = lo; playing = true; last = performance.now(); raf = requestAnimationFrame(frame); update(); }
    function pause() { playing = false; cancelAnimationFrame(raf); update(); }
    playBtn.addEventListener("click", function () { playing ? pause() : play(); });
    document.getElementById("restart").addEventListener("click", function () { ph = lo; play(); });
    scrub.addEventListener("input", function () { ph = +scrub.value; if (playing) { playing = false; cancelAnimationFrame(raf); } update(); });
    Array.prototype.forEach.call(document.querySelectorAll(".seg [data-s]"), function (b) { b.addEventListener("click", function () { speed = +b.getAttribute("data-s"); Array.prototype.forEach.call(document.querySelectorAll(".seg [data-s]"), function (o) { o.setAttribute("aria-pressed", o === b); }); }); });
    if (window.__bvhKey) document.removeEventListener("keydown", window.__bvhKey);
    window.__bvhKey = function (e) { if ((e.code === "Space" || e.key === " ") && (e.target === document.body || e.target === stageEl)) { e.preventDefault(); playing ? pause() : play(); } };
    document.addEventListener("keydown", window.__bvhKey);
    update();
    if (!BVH.reduced()) setTimeout(function () { if (ph === lo) play(); }, 700);
    return { steps: steps, lo: lo, hi: hi };
  }

  function laneFrame(svg, name, top, h, x0, x1, sub, narrow) {
    S("rect", { x: 0, y: top, width: x1 + (narrow ? 10 : 22), height: h, rx: 4, fill: "none", stroke: "var(--line)" }, svg);
    S("text", { x: 10, y: top + (narrow ? 17 : 20), class: "lanehead" }, svg, name);
    S("text", { x: narrow ? 10 + name.length * 7.4 + 10 : 10, y: top + (narrow ? 17 : 35), "font-size": 10, "font-family": "var(--mono)", fill: "var(--muted)" }, svg, sub);
  }

  function trunc(t, n) { t = String(t); return t.length > n ? t.slice(0, n - 1) + "…" : t; }

  /* greedy word wrap for SVG text (no auto-wrapping in SVG) */
  function wrapWords(t, n) {
    var words = String(t).split(/\s+/), lines = [], cur = "";
    words.forEach(function (w) { if (cur && (cur + " " + w).length > n) { lines.push(cur); cur = w; } else cur = cur ? cur + " " + w : w; });
    if (cur) lines.push(cur);
    return lines;
  }

  /* block strip: cells in tx order. Returns {h}. */
  function strip(svg, D, stripArr, notable, ntx, t0, top, x0, x1, timed, select, label, main, hatch, narrow) {
    var K = Math.min(ntx, main ? (narrow ? 14 : 26) : (narrow ? 5 : 8));
    var byIdx = {}; notable.forEach(function (t) { byIdx[t.i] = t; });
    var strMap = {}; if (stripArr) stripArr.forEach(function (s) { strMap[s[0]] = s; });
    var items = [], last = -1;
    var extra = notable.map(function (t) { return t.i; }).filter(function (i) { return i >= K; }).sort(function (a, b) { return a - b; });
    for (var i = 0; i < K; i++) items.push({ i: i }), last = i;
    extra.forEach(function (i) { if (i - last > 1) items.push({ gap: i - last - 1 }); items.push({ i: i }); last = i; });
    if (ntx - 1 > last) items.push({ gap: ntx - 1 - last });
    var wsum = items.reduce(function (s, it) { return s + (it.gap ? 1.7 : 1); }, 0), unit = Math.min(34, (x1 - x0 - 12) / wsum), cx = x0 + 6;
    var baseY = top + 66, cellH = 34, maxBar = 40;
    var labelsRow = [];
    items.forEach(function (it, k) {
      var w = (it.gap ? 1.7 : 1) * unit;
      if (it.gap) {
        var g = S("g", null, svg); S("text", { x: cx + w / 2, y: baseY + cellH / 2 + 4, "text-anchor": "middle", "font-size": 10.5, "font-family": "var(--mono)", fill: "var(--muted)" }, g, "⋯" + it.gap);
        timed.push([g, t0 + 300]); cx += w; return;
      }
      var t = byIdx[it.i], sv = strMap[it.i], role = t ? t.role : (sv && sv[2]) || "", ok = t ? t.ok : (sv ? sv[1] === 1 : true), cb = t ? (t.cb_eth || 0) : (sv ? sv[4] : 0);
      var fill = role === "bot" ? "var(--bot)" : role === "attacker" ? "var(--atk)" : role === "builder" ? "var(--bld)" : role === "bribe" ? "var(--gold)" : role === "focus" ? "var(--ink2)" : "var(--bg3)";
      var g2 = S("g", { tabindex: (t ? 0 : null), role: t ? "button" : null, "aria-label": t ? ((role || "tx") + " at position " + it.i + (ok ? "" : ", reverted")) : null }, svg);
      var cw = Math.max(2, w - 2);
      S("rect", { x: cx, y: baseY, width: cw, height: cellH, rx: 2, fill: fill, opacity: role ? 1 : .9, stroke: role ? "none" : "var(--line2)" }, g2);
      if (!ok) { S("rect", { x: cx, y: baseY, width: cw, height: cellH, rx: 2, fill: "url(#hatch)", stroke: "var(--atk)", "stroke-dasharray": "3 2" }, g2); if (cw > 12) S("text", { x: cx + cw / 2, y: baseY + cellH / 2 + 5, "text-anchor": "middle", "font-size": 14, "font-weight": 700, fill: "var(--atk)" }, g2, "✕"); }
      if (cb >= 0.01) {
        var bh = Math.min(maxBar, 8 + 10 * Math.log10(cb / 0.01));
        S("rect", { x: cx + cw * 0.18, y: baseY - 4 - bh, width: cw * 0.64, height: bh, fill: "var(--gold)", rx: 1 }, g2);
        if (cb >= 1) S("text", { x: cx + cw / 2, y: baseY - 8 - bh, "text-anchor": cx > x1 - 140 ? "end" : cx < x0 + 110 ? "start" : "middle", "font-size": 11.5, "font-family": "var(--mono)", "font-weight": 600, fill: "var(--ink)" }, g2, BVH.eth(cb) + " to builder");
      }
      if (unit >= 15 || t) S("text", { x: cx + cw / 2, y: baseY + cellH + 13, "text-anchor": "middle", "font-size": 10, "font-family": "var(--mono)", fill: t ? "var(--ink)" : "var(--muted)" }, g2, it.i);
      if (t && (role === "bot" || role === "attacker")) labelsRow.push({ x: cx + cw / 2, role: role, i: it.i, ok: ok });
      timed.push([g2, t0 + Math.min(900, k * 38)]);
      if (t) {
        BVH.tipFor(g2, function () { return "<b>" + (role || "tx") + " at position " + it.i + "</b>" + (ok ? "" : " (reverted)") + "<br>" + BVH.short(t.h, 12, 6) + "<br>" + (t.value_eth ? "value " + BVH.eth(t.value_eth) + "<br>" : "") + (cb ? "coinbase transfer " + BVH.eth(cb) + "<br>" : "") + (t.label ? esc(t.label) + "<br>" : "") + (t.err ? "error: " + esc(t.err) : ""); },
          function () { var r = t.raw || {}; select("<b>" + esc(role || "tx") + " at position " + it.i + "</b>" + (ok ? "" : " (reverted" + (t.err ? ": " + esc(t.err) : "") + ")") + " &nbsp;<code>" + t.h + "</code> " + BVH.explorer(t.h) + " " + (t.label ? esc(t.label) + ". " : "") + (t.value_eth ? "Value " + BVH.eth(t.value_eth) + ". " : "") + (cb ? "Coinbase transfer " + BVH.eth(cb) + ". " : "") + rawA(r.tx || r.block, "raw block") + rawA(r.receipt || r.receipts, "raw receipts") + rawA(r.trace, "raw trace")); });
      }
      cx += w;
    });
    // callout labels under the strip
    var ly = baseY + cellH + 30;
    labelsRow.forEach(function (l, n) {
      var g = S("g", null, svg), yy = ly + (narrow ? n : n % 2) * 14;
      S("line", { x1: l.x, x2: l.x, y1: baseY + cellH + 15, y2: yy - 11, stroke: "var(--line2)" }, g);
      var anchor = l.x > x1 - 150 ? "end" : l.x < x0 + 90 ? "start" : "middle";
      S("text", { x: l.x, y: yy, "text-anchor": anchor, "font-size": 11.5, "font-family": "var(--mono)", fill: l.role === "bot" ? "var(--bot)" : "var(--atk)", "font-weight": 600 }, g, (l.role === "bot" ? "bot" : "attacker") + " · " + (narrow ? "pos " : "position ") + l.i + (l.ok ? "" : " · reverted"));
      timed.push([g, t0 + 700]);
    });
    if (!main) S("text", { x: x0 + 6, y: top + 20, "font-size": 12, "font-family": "var(--mono)", fill: "var(--ink)" }, svg, label + " · +12 s");
    return { h: 66 + cellH + 30 + (narrow ? Math.max(0, labelsRow.length - 1) * 14 : (labelsRow.length > 1 ? 14 : 0)) };
  }

  function makeSteps(D, lo, hi) {
    var st = [], A = D.auction, B = A && A.bids, M = D.mempool, pre = D.pre_merge;
    function add(t, html) { st.push({ t: t, html: html }); }
    if (!pre) {
      if (M.state === "measured") {
        var at = M.entries.filter(function (e) { return e.seen && e.role === "attacker" && e.rel_ms >= lo; });
        if (at.length) { var e0 = at[0]; add(e0.rel_ms, "<b>" + BVH.clock(e0.t_ms) + "</b> The attacker's " + (at.length > 1 ? at.length + " transactions appear" : "transaction appears") + " in the public mempool, " + BVH.sec(-e0.rel_ms) + " before the slot starts." + rawA(e0.raw && e0.raw.csv, "raw rows")); }
      } else add(lo, "<b>Mempool:</b> " + esc(M.note) + (M.coverage_raw ? rawA(M.coverage_raw, "raw archive index") : ""));
      if (D.reaction) add(D.reaction.t_ms, "<b>" + BVH.sec(D.reaction.t_ms, true) + "</b> " + BVH.dur(D.reaction.delay_ms) + " after the trigger transaction was first seen, " + esc(D.reaction.builder) + " submits a block worth <b>" + BVH.eth(D.reaction.eth) + "</b>, many times the going rate." + BVH.bidsA(A));
      if (B) {
        var rec = B.record, jumps = [];
        for (var i = 1; i < rec.length; i++) { var r = rec[i][1] / Math.max(rec[i - 1][1], 1e-6); if (r >= 2.5 && rec[i][1] >= 0.5) jumps.push({ i: i, r: r }); }
        jumps.sort(function (a, b) { return b.r - a.r; }); jumps = jumps.slice(0, 3).sort(function (a, b) { return a.i - b.i; });
        jumps.forEach(function (j) { var p = rec[j.i]; if (D.reaction && Math.abs(p[0] - D.reaction.t_ms) < 40) return; add(p[0], "<b>" + BVH.sec(p[0], true) + "</b> Record bid jumps to <b>" + BVH.eth(p[1]) + "</b> (" + esc(B.builders[p[2]]) + ")." + BVH.bidsA(A)); });
        var w = A.winner; if (w && w.t_ms != null) add(w.t_ms, "<b>" + BVH.sec(w.t_ms, true) + "</b> Winning bid: <b>" + BVH.eth(w.eth_bid || w.eth) + "</b> from " + esc(w.builder || "unknown") + ", delivered by " + esc((w.relays || []).join(" and ") || "n/a") + ". The proposer is paid this amount." + rawA(A.raw.delivered, "raw delivered"));
      } else if (A && A.winner && A.winner.eth != null) add(-1000, "<b>Auction:</b> no bid history survives for this slot. The delivered block paid the proposer " + BVH.eth(A.winner.eth) + "." + rawA(A.raw && A.raw.delivered, "raw delivered"));
    }
    var bot = D.txs.filter(function (t) { return t.role === "bot"; })[0], atk = D.txs.filter(function (t) { return t.role === "attacker"; })[0];
    var fl = D.flows, bt = "<b>" + (pre ? "Block sealed" : "Slot starts") + ":</b> block " + D.block.number + " is published" + rawA(D.block.raw.block) + ". ";
    if (bot) bt += "The bot's transaction is at <b>position " + bot.i + "</b>" + (fl.primary_coinbase_eth > 0.001 ? " and pays <b>" + BVH.eth(fl.primary_coinbase_eth) + "</b> straight to the builder" + rawA(D.block.raw.trace) : "") + ". ";
    if (atk) bt += "The attacker's transaction is at position " + atk.i + (atk.ok ? "." : " and <b>reverts</b>.");
    else if (D.atk_block == null && D.race_type !== "bot-was-first-exploiter") bt += "No attacker call lands in this block.";
    add(0, bt);
    if (D.next_block) {
      var nb = D.next_block, na = nb.notable.filter(function (t) { return t.role === "attacker"; })[0];
      add(12000, "<b>+12 s</b> Next block " + nb.number + ((na) ? ": the attacker's transaction lands at position " + na.i + (na.ok ? " and succeeds, but there is nothing left to take" : " and <b>reverts</b>") + "." : ".") + rawA(nb.raw.block, "raw block"));
    }
    st.sort(function (a, b) { return a.t - b.t; });
    return st;
  }

  /* ================================================================ below the player */
  function below(D, row, rows, P) {
    var el = document.getElementById("below"), h = "";
    h += '<section class="sec" style="padding-top:44px"><div class="cols"><div><h2 style="font-size:28px">What the data says</h2>' + facts(D, row) + '</div><div><h2 style="font-size:28px">The block</h2>' + blockFacts(D) + "</div></div></section>";
    h += '<section class="sec" id="ledger" style="padding-top:36px"><h2 style="font-size:28px">Every timestamp, with its source</h2><p class="prose small muted">The replay above, as text. Each row links to the saved response the time or number came from. Times are UTC; the offset is from the start of the slot.</p>' + ledger(D) + "</section>";
    h += '<section class="sec" id="txs" style="padding-top:36px"><h2 style="font-size:28px">Transactions that matter in the block</h2>' + txTable(D) + "</section>";
    h += '<section class="sec" id="money" style="padding-top:36px"><h2 style="font-size:28px">Where the money went</h2>' + money(D, row) + "</section>";
    if (D.timeline_publication_gaps && D.timeline_publication_gaps.length) h += '<p class="small muted">' + D.timeline_publication_gaps.length + ' source timeline entries are omitted pending complete evidence in the published responses. The repository retains the source records.</p>';
    if (D.narrative) h += '<section class="sec" style="padding-top:36px"><details><summary class="mono small" style="cursor:pointer">Full evidence note from the investigation</summary><p class="prose" style="margin-top:12px">' + esc(D.narrative) + "</p></details></section>";
    h += caveats(D);
    var idx = rows.findIndex ? rows.findIndex(function (r) { return r.id === D.id; }) : -1, prev = rows[idx - 1], next = rows[idx + 1];
    h += '<nav class="pn" aria-label="Neighbouring races">' + (prev ? '<a href="' + qhref(prev) + '">earlier: ' + esc(prev.title) + "</a>" : "<span></span>") + (next ? '<a href="' + qhref(next) + '">later: ' + esc(next.title) + "</a>" : "<span></span>") + "</nav>";
    el.innerHTML = h;
    // label each cell with its column header so wide tables can stack into cards on phones
    el.querySelectorAll("table.led").forEach(function (t) {
      var heads = Array.prototype.map.call(t.querySelectorAll("thead th"), function (th) { return th.textContent; });
      t.querySelectorAll("tbody tr").forEach(function (tr) {
        Array.prototype.forEach.call(tr.children, function (td, i) { if (heads[i]) td.setAttribute("data-label", heads[i]); });
      });
    });
  }

  function kv(pairs) { return '<table class="kv"><tbody>' + pairs.filter(Boolean).map(function (p) { return "<tr><th scope=\"row\">" + p[0] + "</th><td>" + p[1] + "</td></tr>"; }).join("") + "</tbody></table>"; }

  function facts(D, row) {
    var A = D.auction, B = A && A.bids, M = D.mempool, p = [];
    p.push(["Mempool", esc(M.note) + (M.coverage_raw ? rawA(M.coverage_raw, "raw index") : "")]);
    var at = M.entries.filter(function (e) { return e.seen && e.role === "attacker"; })[0];
    if (at) p.push(["Attacker first seen", BVH.utc(at.t_ms) + " (" + BVH.sec(at.rel_ms, true) + " from slot start)" + BVH.memA(at.raw)]);
    if (D.reaction) p.push(["First big bid after that", BVH.dur(D.reaction.delay_ms) + " later, " + BVH.eth(D.reaction.eth) + " by " + esc(D.reaction.builder) + BVH.bidsA(A) + '<br><span class="muted">' + esc(D.reaction.method) + "</span>"]);
    if (A) {
      p.push(["Slot", D.slot != null ? D.slot + " (" + BVH.utc(D.t0_ms) + ")" + (D.block.raw.slot ? rawA(D.block.raw.slot, "raw beacon block", "Beacon-chain block of this slot: slot number, proposer, execution payload block number and timestamp") : "") : "pre-Merge: no slots"]);
      if (B) {
        p.push(["Bids on record", ((A.raw.capped || []).length ? "at least " : "") + B.n_total + " bids from " + (A.n_builders || B.builders.length) + " builders" + BVH.bidsA(A) + (B.n_offslot ? '<br><span class="muted">' + B.n_offslot + " more row" + (B.n_offslot === 1 ? "" : "s") + " in the same files carry another slot (a competing proposal for the same block number) and are not counted</span>" : "") + '<br><span class="muted">first ' + BVH.sec(B.first_ms, true) + ", last " + BVH.sec(B.last_ms, true) + ", median bid " + BVH.eth(B.median_eth) + ", highest " + BVH.eth(B.max_eth) + "</span>"]);
      }
      if (A.winner && A.winner.builder) p.push(["Winner", esc(A.winner.builder) + (A.winner.eth != null ? " with " + BVH.eth(A.winner.eth) : "") + rawA(A.raw.delivered, "raw delivered") + '<br><span class="muted">delivered by ' + esc((A.winner.relays || []).join(", ") || "n/a") + "; proposer fee recipient " + BVH.short(A.winner.fee_recipient || D.block.fee_recipient, 8, 6) + "</span>"]);
      if (A.runner_up) p.push(["Best rival bid (other builder)", BVH.eth(A.runner_up.eth) + " by " + esc(A.runner_up.builder) + " at " + BVH.sec(A.runner_up.t_ms, true) + BVH.bidsA(A) + '<br><span class="muted">can exceed the delivered bid when it arrived too late</span>']);
      var ans = Object.keys(A.relays || {}).map(function (k) { return [k, A.relays[k]]; });
      if (ans.length) {
        var got = ans.filter(function (a) { return a[1].bids; }), none = ans.filter(function (a) { return !a[1].bids && a[1].http === 200; }), dead = ans.filter(function (a) { return !a[1].bids && a[1].http !== 200; });
        p.push(["Relays queried", got.map(function (a) { return esc(a[0]) + " (" + a[1].bids + " bids)" + rawA(a[1].raw_bids); }).join(", ") + (none.length ? "<br>answered with nothing: " + none.map(function (a) { return esc(a[0]); }).join(", ") + "." : "") + (dead.length ? "<br>unreachable or retired: " + dead.map(function (a) { return esc(a[0]) + (a[1].retired ? ' <span class="muted">(' + esc(a[1].retired) + ")</span>" : ""); }).join(", ") + "." : "") + '<br><span class="muted">Bids from builders that did not use a queried relay are invisible. Some relays return at most 500 rows per query, so their counts can be low. Bid contents are never published.</span>']);
      }
    } else p.push(["Auction", "No relay data for this block."]);
    if (D.premerge_note) p.push(["Pre-Merge", esc(D.premerge_note)]);
    return kv(p);
  }

  function blockFacts(D) {
    var b = D.block, p = [];
    p.push(["Block", b.number + (D.slot != null ? ", slot " + D.slot : "") + rawA(b.raw.block)]);
    p.push(["Timestamp", BVH.utc(b.ts_ms)]);
    p.push(["Built by", esc(b.builder || "unknown") + '<br><span class="muted">fee recipient ' + BVH.short(b.fee_recipient, 8, 6) + "</span>"]);
    p.push(["Transactions", b.ntx + rawA(b.raw.receipts, "raw receipts")]);
    p.push(["Bot position", D.bot_idx != null ? "position " + D.bot_idx : "n/a"]);
    if (D.atk_block != null) p.push(["Attacker's call", D.atk_block === b.number ? "same block" + (D.atk_idx != null ? ", position " + D.atk_idx : "") : (D.atk_block - b.number > 0 ? D.atk_block - b.number + " block(s) later" : (b.number - D.atk_block) + " block(s) earlier") + (D.atk_idx != null ? ", position " + D.atk_idx : "")]);
    else p.push(["Attacker's call", D.race_type === "bot-was-first-exploiter" ? "none: no separate attacker" : "never landed, or not matched to a block"]);
    p.push(["Gas used", b.gas_used != null ? b.gas_used.toLocaleString("en-US") : "n/a"]);
    return kv(p);
  }

  function ledger(D) {
    var items = [];
    D.mempool.entries.forEach(function (e) {
      if (e.seen) items.push({ t: e.t_ms, lane: "mempool", txt: (e.role || "tx") + " " + BVH.short(e.h, 10, 6) + " first seen (" + (e.sources || []).length + " sources)", raw: BVH.memA(e.raw) });
    });
    var A = D.auction;
    if (A && A.bids) {
      var B = A.bids;
      if (D.reaction) items.push({ t: D.t0_ms + D.reaction.t_ms, lane: "auction", txt: "first big bid after first sight: " + BVH.eth(D.reaction.eth) + " by " + D.reaction.builder, raw: BVH.bidsA(A) });
      if (A.winner && A.winner.t_ms != null) items.push({ t: D.t0_ms + A.winner.t_ms, lane: "auction", txt: "winning bid " + BVH.eth(A.winner.eth_bid || A.winner.eth) + " by " + (A.winner.builder || ""), raw: rawA(A.raw.delivered, "raw delivered") + BVH.bidsA(A) });
      B.record.forEach(function (r, i) { if (i === 0 || i === B.record.length - 1 || r[1] / B.record[i - 1][1] >= 2.5) items.push({ t: D.t0_ms + r[0], lane: "auction", txt: "record bid " + BVH.eth(r[1]) + " (" + B.builders[r[2]] + ")", raw: BVH.bidsA(A) }); });
    }
    D.events.forEach(function (e) { items.push({ t: e.t, lane: e.kind, txt: e.detail || "", der: BVH.derivedTxt(e), raw: (e.raws && e.raws.length) ? BVH.rawAs(e.raws) : (e.raw ? rawA(e.raw) : (e.raw_note ? '<span class="muted" title="' + esc(e.raw_note) + '">' + esc(e.raw_note) + "</span>" : rawA(null))), tx: e.tx }); });
    items.sort(function (a, b) { return (a.t == null ? 9e18 : a.t) - (b.t == null ? 9e18 : b.t); });
    // dedupe identical text+time
    var seen = {}; items = items.filter(function (i) { var k = i.t + "|" + i.txt; if (seen[k]) return false; seen[k] = 1; return true; });
    return '<div style="overflow-x:auto"><table class="led"><thead><tr><th scope="col">UTC</th><th scope="col">From slot start</th><th scope="col">Lane</th><th scope="col">What</th><th scope="col">Source</th></tr></thead><tbody>' + items.map(function (i) {
      var t = i.t == null ? "untimed" : BVH.utc(i.t).replace(" UTC", ""), rel = i.t == null || D.pre_merge ? "" : (Math.abs(i.t - D.t0_ms) > 36e5 ? BVH.dur(Math.abs(i.t - D.t0_ms)) + (i.t < D.t0_ms ? " before" : " after") : BVH.sec(i.t - D.t0_ms, true));
      return '<tr><td class="t">' + t + '</td><td class="t">' + rel + '</td><td><span class="tag other">' + esc(i.lane) + "</span></td><td>" + esc(i.txt) + (i.der || "") + "</td><td>" + i.raw + "</td></tr>";
    }).join("") + "</tbody></table></div>";
  }

  function txTable(D) {
    var rows = D.txs.slice().sort(function (a, b) { return a.i - b.i; });
    var out = '<div style="overflow-x:auto"><table class="led"><thead><tr><th scope="col">Pos.</th><th scope="col">Role</th><th scope="col">Transaction</th><th scope="col">Status</th><th scope="col">Value</th><th scope="col">Coinbase</th><th scope="col">Tip (gwei)</th><th scope="col">Source</th></tr></thead><tbody>';
    out += rows.map(function (t) {
      var r = t.raw || {};
      return "<tr><td class=\"t\">" + t.i + "</td><td><span class=\"tag " + esc(t.role || "other") + "\">" + esc(t.role || "tx") + "</span>" + (t.label ? '<br><span class="muted">' + esc(t.label) + "</span>" : "") + "</td><td><code>" + BVH.short(t.h, 10, 6) + "</code>" + BVH.explorer(t.h) + "<br><span class=\"muted\">" + BVH.short(t.from_, 8, 4) + " → " + BVH.short(t.to || "", 8, 4) + "</span></td><td>" + (t.ok ? "ok" : '<span style="color:var(--atk)">reverted' + (t.err ? ": " + esc(t.err) : "") + "</span>") + "</td><td>" + (t.value_eth ? BVH.eth(t.value_eth) : "0") + "</td><td>" + (t.cb_eth ? BVH.eth(t.cb_eth) : "") + "</td><td>" + (t.tip != null ? t.tip : "") + "</td><td>" + rawA(r.tx || r.block, "raw block") + rawA(r.trace, "raw trace") + "</td></tr>";
    }).join("") + "</tbody></table></div>";
    if (D.next_block && D.next_block.notable.length) {
      var nb = D.next_block;
      out += '<h3 style="font-size:19px;margin-top:26px">Next block, ' + nb.number + rawA(nb.raw.block) + "</h3><div style=\"overflow-x:auto\"><table class=\"led\"><thead><tr><th>Pos.</th><th>Role</th><th>Transaction</th><th>Status</th></tr></thead><tbody>" + nb.notable.map(function (t) { return "<tr><td class=\"t\">" + t.i + "</td><td><span class=\"tag " + esc(t.role) + "\">" + esc(t.role) + "</span></td><td><code>" + BVH.short(t.h, 10, 6) + "</code>" + BVH.explorer(t.h) + "</td><td>" + (t.ok ? "ok" : '<span style="color:var(--atk)">reverted' + (t.err ? ": " + esc(t.err) : "") + "</span>") + "</td></tr>"; }).join("") + "</tbody></table></div>";
    }
    return out;
  }

  function money(D, row) {
    var f = D.flows, out = "", A = D.auction;
    if (f.meaningful) {
      var C = f.bot_coinbase_eth + (f.bot_priority_fee_eth || 0), P = f.proposer_eth || 0, Rf = f.refund_to_bot_eth || 0, Q = f.payout_other_eth || 0, K = Math.max(0, C - P - Rf - Q);
      var segs = [["Paid on to the proposer (the winning bid)", P, "var(--bld)", A && A.raw && A.raw.delivered], ["Refunded to the bot by the builder", Rf, "var(--bot)", D.block.raw.trace], ["Paid out to another address by the builder", Q, "var(--gold)", D.block.raw.trace], ["Kept by the builder in this block", K, "var(--ink2)", D.block.raw.trace]].filter(function (s) { return s[1] > 0.0005; });
      out += '<p class="prose">In this block the bot paid <b>' + BVH.eth(C) + "</b> to the builder" + rawA(D.block.raw.trace, "raw trace") + (f.n_bot_txs > 1 ? " across " + f.n_bot_txs + " of its transactions" : "") + " (" + BVH.eth(f.bot_coinbase_eth) + " as direct coinbase transfers" + (f.n_bot_txs > 1 ? ", of which " + BVH.eth(f.primary_coinbase_eth) + " in the first transaction, the figure in the table" : "") + (f.bot_priority_fee_eth ? " + " + BVH.eth(f.bot_priority_fee_eth) + " as priority fees" : "") + "). Here is where that went, inside the same block:</p>";
      out += '<div class="flow" role="img" aria-label="Stacked bar of where the builder payment went"><div class="seg-row">' + segs.map(function (s) { return '<div style="flex:' + Math.max(s[1], C * 0.004) + ';background:' + s[2] + '" title="' + esc(s[0]) + ": " + BVH.eth(s[1]) + '"></div>'; }).join("") + '</div></div><div class="flow-key">' + segs.map(function (s) { return "<div><i style=\"background:" + s[2] + "\"></i><span>" + s[0] + rawA(s[3]) + "</span><span>" + BVH.eth(s[1]) + " (" + (100 * s[1] / C).toFixed(1) + "%)</span></div>"; }).join("") + "</div>";
      if (f.payouts && f.payouts.length) out += '<p class="small muted mono">Payout transactions: ' + f.payouts.map(function (p) { return "position " + p.i + " " + BVH.eth(p.eth) + " to " + BVH.short(p.to, 8, 4) + " " + BVH.explorer(p.h); }).join("; ") + ".</p>";
      out += '<p class="small muted mono">The split is read from the block itself: transfers from the builder\'s fee recipient after the bot\'s transaction. Who the builder is working for is not on chain.</p>';
    } else out += '<p class="prose">No direct coinbase payment was made in this block' + (D.pre_merge ? ": before the Merge there were no builder bids, and this race was decided by gas price and position." : ": the bot bought its position with gas price, not a bribe.") + "</p>";
    if (D.dataset_money && D.dataset_money.scope !== "bot-tx") {
      var dm = D.dataset_money;
      out += '<p class="callout"><b>Dataset aggregate (' + esc(dm.scope) + '):</b> ' + BVH.eth(dm.paid_to_builder_eth) + ' paid to the builder before refunds; ' + BVH.eth(dm.builder_refund_eth || 0) + ' refunded. The block replay above covers the selected block. ' + esc(dm.note || '') + '</p>';
    }
    var after = D.events.filter(function (e) { return e.t != null && e.t > D.block.ts_ms + 1000 && ["return", "message", "tx", "fund"].indexOf(e.kind) >= 0; });
    out += '<h3 style="font-size:21px">Afterwards</h3>';
    if (D.fate && D.fate.text) out += '<div class="callout ' + (D.fate.kind === "returned" ? "good" : D.fate.kind === "kept" ? "bad" : "") + '"><b>' + ({ returned: "Returned. ", partial: "Partly returned. ", kept: "No return found. ", unknown: "Unknown. ", "n-a": "" }[D.fate.kind] || "") + "</b>" + esc(D.fate.text) + (D.fate.returned_pct != null ? " That is about " + D.fate.returned_pct + "% of the bot's gross take (our arithmetic from the transfers listed below)." : "") + "</div>";
    if (after.length) out += '<div style="overflow-x:auto"><table class="led"><thead><tr><th scope="col">UTC</th><th scope="col">After the block</th><th scope="col">What</th><th scope="col">Source</th></tr></thead><tbody>' + after.map(function (e) {
      return '<tr><td class="t">' + BVH.utc(e.t).replace(" UTC", "") + '</td><td class="t">' + BVH.dur(e.t - D.block.ts_ms) + '</td><td><span class="tag ' + (e.kind === "return" ? "bot" : "other") + '">' + esc(e.kind) + "</span> " + esc(e.detail || "") + BVH.derivedTxt(e) + "</td><td>" + ((e.raws && e.raws.length) ? BVH.rawAs(e.raws) : rawA(e.raw)) + "</td></tr>";
    }).join("") + "</tbody></table></div>"; else out += '<p class="muted">No later transfers or messages were recorded for this race.</p>';
    return out;
  }

  function caveats(D) {
    var c = [];
    if (D.slug === "kelp-rseth-2026") c.push("Kelp’s higher recorded losing bid and lower delivered winning bid remain unexplained. The queried relay histories contain no submission from the winning builder; the delivery record establishes the winner.");
    c.push("Relays publish a bid's hash, size and value, never its transactions. Which bid carried the bot's transaction is known only for the delivered block.");
    c.push("Bid times are each relay's own receive clock, so cross-relay comparison carries clock skew and network latency.");
    if (D.mempool.state !== "measured") c.push("Mempool: " + D.mempool.note);
    c.push("First seen means first seen by the archive's sources, not by the bot. The bot may have learned of the attack earlier or by another route.");
    return '<section class="sec" style="padding-top:36px"><h3 style="margin-top:0;font-size:19px">Limits of this reconstruction</h3><ul class="prose small" style="padding-left:1.1em">' + c.map(function (x) { return "<li>" + esc(x) + "</li>"; }).join("") + '</ul><p class="small"><a href="methods.html">Methods, evidence levels and limitations</a></p></section>';
  }
})();
