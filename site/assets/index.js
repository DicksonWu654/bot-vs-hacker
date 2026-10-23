(function () {
  "use strict";
  var $ = function (s) { return document.querySelector(s); };
  BVH.chrome("index.html");

  /* ---------- hero background: a quiet night forest of dots ---------- */
  (function forest() {
    var cv = $("#forest"), ctx = cv.getContext("2d"), dots = [], flies = [], W = 0, H = 0, raf = 0, last = 0;
    function size() {
      var r = cv.parentNode.getBoundingClientRect(), dpr = Math.min(window.devicePixelRatio || 1, 2);
      W = r.width; H = r.height; cv.width = W * dpr; cv.height = H * dpr; ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      var n = Math.round(W * H / 5200);
      dots = []; for (var i = 0; i < n; i++) dots.push({ x: Math.random() * W, y: Math.random() * H, r: Math.random() * 1.1 + .3, p: Math.random() * 6.28, s: Math.random() * .8 + .2 });
      flies = []; for (var j = 0; j < 7; j++) flies.push({ x: Math.random() * W, y: Math.random() * H, a: Math.random() * 6.28, c: j % 3 === 0 ? "--atk" : "--bot", v: 6 + Math.random() * 10 });
    }
    function draw(t) {
      ctx.clearRect(0, 0, W, H);
      var star = BVH.cssVar("--star"), i, d;
      ctx.fillStyle = star;
      for (i = 0; i < dots.length; i++) { d = dots[i]; ctx.globalAlpha = .35 + .65 * (.5 + .5 * Math.sin(t / 1800 * d.s + d.p)); ctx.beginPath(); ctx.arc(d.x, d.y, d.r, 0, 6.283); ctx.fill(); }
      ctx.globalAlpha = 1;
      for (i = 0; i < flies.length; i++) {
        var f = flies[i], col = BVH.cssVar(f.c), g = ctx.createRadialGradient(f.x, f.y, 0, f.x, f.y, 16);
        g.addColorStop(0, col); g.addColorStop(1, "transparent"); ctx.globalAlpha = .28; ctx.fillStyle = g; ctx.beginPath(); ctx.arc(f.x, f.y, 16, 0, 6.283); ctx.fill();
        ctx.globalAlpha = .9; ctx.fillStyle = col; ctx.beginPath(); ctx.arc(f.x, f.y, 1.8, 0, 6.283); ctx.fill();
      }
      ctx.globalAlpha = 1;
    }
    function step(t) {
      var dt = Math.min(50, t - last) / 1000; last = t;
      flies.forEach(function (f) { f.a += (Math.random() - .5) * .5; f.x += Math.cos(f.a) * f.v * dt; f.y += Math.sin(f.a) * f.v * dt; if (f.x < 0) f.x = W; if (f.x > W) f.x = 0; if (f.y < 0) f.y = H; if (f.y > H) f.y = 0; });
      draw(t); raf = requestAnimationFrame(step);
    }
    size(); draw(0);
    BVH.onTheme.push(function () { draw(0); });
    if (!BVH.reduced()) { raf = requestAnimationFrame(step); document.addEventListener("visibilitychange", function () { if (document.hidden) cancelAnimationFrame(raf); else { last = performance.now(); raf = requestAnimationFrame(step); } }); }
    var to; window.addEventListener("resize", function () { clearTimeout(to); to = setTimeout(function () { size(); draw(0); }, 150); });
  })();

  var headlineStats = null;
  var rows = [], filter = "head", sortKey = "date", sortDir = 1;

  Promise.all([BVH.json("data/incidents.json"), BVH.json("data/incident/makina-2026.json").catch(function () { return null; }), BVH.json("data/evolution.json").catch(function () { return null; }), BVH.json("data/lineages.json").catch(function () { return null; }), BVH.json("data/headline_stats.json")])
    .then(function (r) { headlineStats = r[4]; rows = r[0]; hook(r[1], rows); stats(); famous(); types(); table(); evo(r[2]); if (r[3]) lineages(r[3]); else { $("#lineages").hidden = true; $("#said").hidden = true; } })
    .catch(function (e) { BVH.loadError($("#hook"), e); });

  /* ---------- the hook: Makina ---------- */
  function hook(D, rows) {
    var row = rows.filter(function (x) { return x.id === "makina-2026"; })[0];
    if (!D || !row) { $("#hook").textContent = "The first race could not be loaded."; return; }
    var dep = (D.events || []).filter(function (e) { return e.kind === "deploy" && /attack contract/i.test(e.detail || ""); })[0];
    var gap = dep && dep.t ? D.block.ts_ms - dep.t : 12000;
    var cb = D.flows.bot_coinbase_eth, rawTrace = D.block.raw.trace, win = D.auction && D.auction.winner;
    /* sources as small numbered superscripts, so the hook reads as plain prose */
    var fn = 0;
    function sup(url, title) { if (!url) return BVH.rawA(null); fn++; return '<sup class="fn">' + BVH.rawA(url, String(fn), "Source " + fn + ": " + (title || "saved raw response")) + "</sup>"; }
    function sups(urls, title) { urls = (urls || []).filter(Boolean); if (!urls.length) return BVH.rawA(null); return urls.map(function (u, i) { return sup(u, title + (urls.length > 1 ? " (" + (i + 1) + " of " + urls.length + ")" : "")); }).join('<sup class="fn">,</sup>'); }
    var p = '<span>On ' + BVH.dateLong(D.date) + ' an attacker deployed a contract built to drain Makina Finance' + (dep && dep.raws && dep.raws.length ? sups(dep.raws, "Deploy transaction trace and its block (carries the timestamp)") : sup(dep && dep.raw, "Deploy transaction trace")) + '. <b>' + Math.round(gap / 1000) + ' seconds later</b>' + sup(D.block.raw.block, "Block timestamp") + ', at position 0 of the next block, a searcher ran the same calls first and paid <b>' + BVH.eth(cb) + '</b> to the block builder' + sup(rawTrace, "Block trace holding the payment to the builder") + ', ' + BVH.pct(row.pct_to_builder) + ' of what it took. The attacker never landed a call.</span>';
    $("#hook").innerHTML = p;
    var p2 = document.createElement("p");
    p2.innerHTML = 'The winning bid, ' + BVH.eth(win.eth) + sup(D.auction.raw.delivered, "Relay record of the payload delivered to the proposer") + ', went to the proposer; the rest of the payment stayed on the builder side, which forwarded it on. ' + (row.returned_pct != null ? 'About ' + Math.round(row.returned_pct) + '% of the bot&rsquo;s payment to the builder was later returned to Makina, by the address that received it from the builder.' : '') + ' <a href="incident.html?slug=makina-2026"><b>Replay this race</b></a>';
    $("#makina").appendChild(p2);
    slotFig(D, row, gap);
  }

  function slotFig(D, row, gap) {
    var fig = $("#hookfig"), W = 520, H = 230, S = BVH.svg;
    var svg = S("svg", { viewBox: "0 0 " + W + " " + H, role: "img", "aria-label": "Two markers 12 seconds apart: the attacker's deploy and the bot's copy at position 0 of the next block. A bar shows 1,299 ETH paid to the builder." }, fig);
    var x0 = 34, x1 = W - 34, y = 64;
    S("line", { x1: x0, x2: x1, y1: y, y2: y, stroke: "var(--line2)", "stroke-width": 2 }, svg);
    for (var i = 0; i <= 12; i += 2) { var x = x0 + (x1 - x0) * i / 12; S("line", { x1: x, x2: x, y1: y - 5, y2: y + 5, stroke: "var(--line2)" }, svg); S("text", { x: x, y: y + 22, "text-anchor": "middle", "font-size": 10, "font-family": "var(--mono)", fill: "var(--muted)" }, svg, i + " s"); }
    var dep = S("circle", { cx: x0, cy: y, r: 8, fill: "var(--atk)" }, svg);
    S("text", { x: x0, y: y - 18, "font-size": 11.5, "font-family": "var(--mono)", fill: "var(--ink)" }, svg, "attacker deploys");
    var bot = S("path", { d: "M" + x1 + " " + (y - 10) + "l10 10-10 10-10-10z", fill: "var(--bot)" }, svg);
    var bt = S("text", { x: x1, y: y - 18, "text-anchor": "end", "font-size": 11.5, "font-family": "var(--mono)", fill: "var(--ink)" }, svg, "bot copies, position 0");
    var prog = S("line", { x1: x0, x2: x0, y1: y, y2: y, stroke: "var(--gold)", "stroke-width": 3 }, svg);
    var clk = S("text", { x: (x0 + x1) / 2, y: y + 54, "text-anchor": "middle", "font-size": 30, "font-family": "var(--mono)", "font-weight": 600, fill: "var(--ink)" }, svg, "0.0 s");
    var by = 152, bw = x1 - x0;
    S("text", { x: x0, y: by - 10, "font-size": 11.5, "font-family": "var(--mono)", fill: "var(--ink2)" }, svg, "paid to the builder: " + BVH.eth(D.flows.bot_coinbase_eth));
    S("rect", { x: x0, y: by, width: bw, height: 16, rx: 3, fill: "var(--bg3)" }, svg);
    var bar = S("rect", { x: x0, y: by, width: 0, height: 16, rx: 3, fill: "var(--gold)" }, svg);
    var win = D.auction.winner.eth, share = win / D.flows.bot_coinbase_eth;
    S("text", { x: x0, y: by + 36, "font-size": 11.5, "font-family": "var(--mono)", fill: "var(--ink2)" }, svg, "winning bid to proposer: " + BVH.eth(win) + " (" + (share * 100).toFixed(0) + "%)");
    var mark = S("rect", { x: x0, y: by - 4, width: 2, height: 24, fill: "var(--ink)" }, svg); mark.setAttribute("x", x0 + bw * share - 1);
    var cap = document.createElement("figcaption");
    cap.innerHTML = 'Slot-by-slot: the deploy lands in one block, the copy in the next' + BVH.rawA(D.block.raw.block) + '. The tick on the bar is the winning bid; everything beyond it stayed with the builder at first.';
    fig.appendChild(cap);
    function set(t) {
      var f = Math.min(1, t / 2600), s = gap / 1000;
      prog.setAttribute("x2", x0 + (x1 - x0) * f); clk.textContent = (s * f).toFixed(1) + " s";
      var g = Math.max(0, Math.min(1, (t - 2600) / 1100));
      bar.setAttribute("width", bw * g); bot.setAttribute("opacity", f >= 1 ? 1 : .15); bt.setAttribute("opacity", f >= 1 ? 1 : .15);
    }
    if (BVH.reduced()) { set(9999); return; }
    set(0); var t0 = null;
    function tick(ts) { if (t0 == null) t0 = ts; var t = ts - t0; set(t); if (t < 4000) requestAnimationFrame(tick); }
    setTimeout(function () { requestAnimationFrame(tick); }, 500);
  }

  /* ---------- headline stats: one big number, one plain sentence; the qualifiers live on methods.html#headline-numbers ---------- */
  function stats() {
    var H = headlineStats, c = H.counts, paid = H.block_producer_share.headline_rows, ret = H.loot.returns.gross.headline_rows, d = H.detection_delay;
    var items = [
      [c.headline_rows + " races", "in " + c.headline_incidents + " incidents where a bot copied a hack in progress and got there first."],
      [Math.round(paid.sum_paid_eth).toLocaleString("en-US") + " ETH", "paid by those bots to block builders, to be put first in line."],
      [Math.round(ret.pooled_pct) + "%", "of what the bots took in those races went back to the victims."],
      [d.median_ms + " ms", "median time from an attack showing up in the public mempool to the winning builder's big bid."]
    ];
    $("#stats").innerHTML = items.map(function (it) { return '<div class="stat" role="listitem"><b>' + it[0] + '</b><span>' + it[1] + '</span></div>'; }).join("");
  }

  /* ---------- famous names first: a compact strip of the best-known incidents ---------- */
  /* editorial pick by recognisability; every value below is read from incidents.json. "all" = include rows outside the headline (clearly labelled). */
  var FAMOUS = [["curve-vyper-2023", "head"], ["ronin-2024", "all"], ["makina-2026", "head"], ["kelp-rseth-2026", "head"], ["blueberry-2024", "head"], ["punk-2021", "head"]];
  function famous() {
    var html = FAMOUS.map(function (f) {
      var rs = rows.filter(function (r) { return r.slug === f[0] && !r.stub && (f[1] === "all" || r.headline); });
      if (!rs.length) return "";
      var counted = rs.some(function (r) { return r.headline; });
      var name = rs[0].title.split(":")[0].trim(), year = rs[0].date.slice(0, 4);
      var gross = rs.reduce(function (a, r) { return a + (r.gross_eth || 0); }, 0);
      var priced = rs.filter(function (r) { return r.returned_pct != null && r.gross_eth; });
      var pg = priced.reduce(function (a, r) { return a + r.gross_eth; }, 0);
      var rp = pg ? priced.reduce(function (a, r) { return a + r.gross_eth * r.returned_pct / 100; }, 0) / pg * 100 : null;
      var ret = rp == null ? ["unknown", "", "Return not established"] : rp >= 90 ? ["mostly returned", "yes", ""] : rp >= 1 ? ["partly returned", "warn", ""] : ["kept", "no", ""];
      var retTxt = rp == null ? ret[0] : ret[0] + ", " + (rp < 100 ? Math.min(99, Math.round(rp)) : 100) + "%";
      var retTitle = priced.length < rs.length ? ' title="Share of the priced part: ' + (rs.length - priced.length) + ' of ' + rs.length + ' rows have no return figure"' : "";
      var bots = [], seen = {};
      rs.forEach(function (r) { var b = String(r.bot || "").replace(/\s*\(.*\)\s*$/, "").trim(); if (b && !seen[b]) { seen[b] = 1; bots.push(b); } });
      var botTxt = bots.length > 2 ? bots.length + " different bots" : bots.join(" and ");
      var lead = rs.filter(function (r) { return r.headline; })[0] || rs.slice().sort(function (a, b) { return (b.gross_eth || 0) - (a.gross_eth || 0); })[0];
      var src = rs.map(function (r) { return r.raw && r.raw.trace; }).filter(Boolean);
      return '<li class="fam"><a class="fam-link" href="' + href(lead) + '"><span class="fam-name">' + BVH.esc(name) + ' <span class="fam-yr">' + year + '</span></span>' +
        '<span class="fam-amt">' + Math.round(gross).toLocaleString("en-US") + ' ETH</span>' +
        '<span class="fam-what">taken first by ' + BVH.esc(botTxt) + '</span></a>' +
        '<span class="fam-foot"><span class="pill ' + ret[1] + '"' + retTitle + '>' + retTxt + '</span>' +
        (counted ? "" : ' <span class="pill no" title="' + BVH.esc(BVH.RT[rs[0].race_type] ? BVH.RT[rs[0].race_type].def : "") + '">not in the headline count</span>') +
        '<span class="fam-src">' + (src.length === 1 ? BVH.rawA(src[0], "raw", "Block trace with the bot's take") : src.map(function (u, i) { return BVH.rawA(u, String(i + 1), "Block trace with a bot's take (" + (i + 1) + " of " + src.length + ")"); }).join("")) + '</span></span></li>';
    }).join("");
    $("#famlist").innerHTML = html;
  }

  function types() {
    var order = ["beat-pending-attack", "deploy-window-copy", "beat-whitehat-or-user", "post-failure-replay", "bot-was-first-exploiter", "late-copy", "no-race"];
    $("#typelist").innerHTML = order.map(function (k) {
      var n = rows.filter(function (r) { return r.race_type === k; }).length, h = rows.filter(function (r) { return r.race_type === k && r.headline; }).length;
      var counted = (k === "beat-pending-attack" || k === "deploy-window-copy");
      return '<div class="type"><h3>' + BVH.RT[k].name + '</h3><p>' + BVH.RT[k].def + '</p><p style="margin-top:8px"><span class="pill ' + (counted ? "yes" : "no") + '">' + (counted ? "counted in the headline" : "not counted") + '</span> <span class="pill">' + n + ' investigated' + (counted ? ", " + h + " confirmed" : "") + '</span></p></div>';
    }).join("");
  }

  /* ---------- table ---------- */
  var COLS = [
    ["date", "Date", false], ["title", "Incident and bot", false], ["race_type", "Race type", false], ["detection_delay_ms", "Builder bid response (ms)", true],
    ["blocks_ahead", "Blocks ahead", true], ["peak", "Bid escalation", true], ["winner_builder", "Winning builder", false],
    ["pct_to_builder", "To builder before refunds", true], ["ret", "Returned", true]
  ];
  function sval(r, k) {
    switch (k) {
      case "peak": return r.winning_bid_eth;
      case "ret": return r.returned_pct != null ? r.returned_pct : null;
      case "detection_delay_ms": return r.detection_delay_ms;
      default: return r[k];
    }
  }
  function sparkSvg(r) {
    var pts = r.spark || [];
    if (pts.length < 2) return '<span class="na" title="' + (r.pre_merge ? "Pre-Merge: no relay, so no bid stream exists." : "No bid history survives for this slot.") + '">' + (r.pre_merge ? "pre-merge, no bids" : "no bid history") + "</span>";
    var W = 110, H = 30, t0 = pts[0][0], t1 = pts[pts.length - 1][0] || 1, lo = Math.max(1e-4, Math.min.apply(null, pts.map(function (p) { return p[1]; }))), hi = Math.max.apply(null, pts.map(function (p) { return p[1]; }));
    if (hi / lo < 3) lo = hi / 3;
    var x = BVH.lin(t0, Math.max(t1, t0 + 1), 3, W - 5), y = BVH.log(lo, hi * 1.0001, H - 4, 4);
    var d = "", px = null, py = null;
    pts.forEach(function (p, i) { var X = x(p[0]), Y = y(p[1]); d += (i ? "H" + X.toFixed(1) + "V" + Y.toFixed(1) : "M" + X.toFixed(1) + " " + Y.toFixed(1)); });
    var last = pts[pts.length - 1];
    return '<svg class="spark" viewBox="0 0 ' + W + " " + H + '" role="img" aria-label="Record bid climbed from ' + BVH.eth(pts[0][1]) + " to " + BVH.eth(last[1]) + '"><path d="' + d + '" fill="none" stroke="var(--bld)" stroke-width="1.6"/><circle cx="' + x(last[0]).toFixed(1) + '" cy="' + y(last[1]).toFixed(1) + '" r="3" fill="var(--gold)"/></svg>';
  }
  function aheadCell(r) {
    if (r.race_type === "bot-was-first-exploiter") return '<span class="na" title="No separate attacker transaction exists.">no attacker</span>';
    var ba = r.blocks_ahead;
    if (r.race_type === "beat-whitehat-or-user" && r.bot_idx != null && r.atk_idx == null) return '<span class="na" title="The copied transaction is a user withdrawal or a whitehat rescue and was not matched to a block, so no distance is given.">no hacker transaction</span>';
    if (ba == null) return '<span class="na" title="The attacker\'s own call never landed, or could not be matched to a block.">' + (r.atk_landed ? "n/a" : "attacker never landed") + "</span>";
    var pos = (r.bot_idx != null && r.atk_idx != null) ? '<span class="sub">position ' + r.bot_idx + " vs " + r.atk_idx + "</span>" : "";
    if (ba === 0) return "same block" + pos;
    if (ba > 0) return ba + " block" + (ba > 1 ? "s" : "") + " earlier" + pos;
    return "<span class=\"na\">" + (-ba) + " block" + (-ba > 1 ? "s" : "") + " after</span>" + pos;
  }
  function reactCell(r) {
    if (r.detection_delay_ms != null) return r.detection_delay_ms + " ms" + BVH.rawA(r.raw && r.raw.mempool, "raw", "Mempool first-seen rows for the attacker's transaction") + '<span class="sub" title="' + BVH.esc(r.delay_method || "") + '">first sight to first big bid</span>';
    var why = r.mempool === "in-block-only" ? "in-block evidence only" : r.mempool === "absent-from-archive" ? "not in mempool archive" : "n/a";
    var tt = r.mempool === "in-block-only" ? "No public mempool archive for this date." : r.mempool === "absent-from-archive" ? "The archive covers the day but never saw the attacker's transaction: private order flow, or missed." : "Attacker not seen before the bot's block.";
    return '<span class="na" title="' + tt + '">' + why + "</span>";
  }
  function retCell(r) {
    var link = r.stub ? "" : '<a class="raw" href="' + href(r) + '#money" title="Transactions and messages behind this are listed on the race page">txs</a>';
    if (r.returned_pct != null) return BVH.pct(r.returned_pct, 1) + '<span class="bar"><i style="width:' + Math.max(1, Math.min(100, r.returned_pct)) + '%"></i></span>' + link;
    var map = { returned: "returned", partial: "partly returned", kept: "kept, no return found", unknown: "unknown", "n-a": "n/a" };
    return '<span class="na" title="' + BVH.esc(r.fate || "") + '">' + (map[r.fate_kind] || "unknown") + "</span>" + link;
  }
  function href(r) { return "incident.html?slug=" + encodeURIComponent(r.slug) + (r.sub ? "&sub=" + encodeURIComponent(r.sub) : ""); }

  function table() {
    var tb = $("#cmp");
    function render() {
      var list = rows.filter(function (r) { return filter === "all" || r.headline; });
      list.sort(function (a, b) {
        var x = sval(a, sortKey), y = sval(b, sortKey);
        if (x == null && y == null) return 0; if (x == null) return 1; if (y == null) return -1;
        return (typeof x === "string" ? x.localeCompare(y) : x - y) * sortDir;
      });
      $("#count").textContent = list.length + " races";
      var head = "<thead><tr>" + COLS.map(function (c) {
        var s = sortKey === c[0] ? (sortDir > 0 ? "ascending" : "descending") : "none";
        return '<th scope="col" class="' + (c[2] ? "num" : "") + '" aria-sort="' + s + '"><button type="button" data-k="' + c[0] + '">' + c[1] + "</button></th>";
      }).join("") + "</tr></thead>";
      var body = "<tbody>" + list.map(function (r) {
        var rt = BVH.rtName(r.race_type);
        var bld = r.pre_merge ? (r.winner_builder ? "miner: " + BVH.esc(r.winner_builder) : '<span class="na">n/a</span>') : (r.winner_builder ? BVH.esc(r.winner_builder) : '<span class="na">n/a</span>');
        var bidtxt = r.winning_bid_eth != null ? '<span class="sub">' + BVH.eth(r.winning_bid_eth) + BVH.rawA(r.raw && (r.raw.delivered || r.raw.bids)) + "</span>" : "";
        var pct = r.pct_to_builder != null ? BVH.pct(r.pct_to_builder) + '<span class="bar bld"><i style="width:' + Math.max(1, Math.min(100, r.pct_to_builder)) + '%"></i></span>' + (r.slug === "sushi-rp2-2023" ? '<span class="sub">all bots in the incident</span>' : BVH.rawA(r.raw && r.raw.trace, "raw", "Block trace holding the coinbase transfer")) + '<span class="sub" title="Payment to the builder before refunds: direct coinbase transfer plus priority fee; Sushi is incident-wide.">' + (r.slug === "sushi-rp2-2023" ? r.paid_to_builder_eth.toFixed(2) + " ETH" : BVH.eth(r.paid_to_builder_eth == null ? r.coinbase_eth : r.paid_to_builder_eth)) + "</span>" : '<span class="na" title="The bot\'s gross take is not established, so the share cannot be computed.">n/a</span>' + (r.coinbase_eth ? '<span class="sub" title="Payment to the builder before refunds: direct coinbase transfer plus priority fee; Sushi is incident-wide.">' + (r.slug === "sushi-rp2-2023" ? r.paid_to_builder_eth.toFixed(2) + " ETH" : BVH.eth(r.paid_to_builder_eth == null ? r.coinbase_eth : r.paid_to_builder_eth)) + BVH.rawA(r.raw && r.raw.trace) + "</span>" : "");
        if (r.loot_scope && r.loot_scope !== "bot-tx" && r.slug !== "sushi-rp2-2023") pct += '<span class="sub">' + BVH.esc(r.loot_scope) + "</span>";
        return "<tr>" +
          '<td data-l="Date" class="mono">' + r.date + "</td>" +
          '<td class="first"><span class="name">' + (r.stub ? BVH.esc(r.title) : '<a href="' + href(r) + '">' + BVH.esc(r.title) + "</a>") + '</span><span class="sub">' + BVH.esc(r.bot) + (r.stub && r.one_liner ? " &middot; " + BVH.esc(r.one_liner.length > 150 ? r.one_liner.slice(0, 147) + "..." : r.one_liner) : "") + "</span></td>" +
          '<td data-l="Race type" class="rt">' + rt + (r.headline ? ' <span class="pill yes" title="Counted in the headline">counted</span>' : ' <span class="pill no" title="' + (r.race_type === "no-race" ? "Rejected: no bot beat or copied anyone here. Shown so the line is visible." : "Not counted in the headline: the bot did not beat a pending attack here.") + '">' + (r.race_type === "no-race" ? "not a race" : "not counted") + "</span>") + "</td>" +
          '<td data-l="Builder bid response (ms)" class="num">' + reactCell(r) + "</td>" +
          '<td data-l="Blocks ahead" class="num">' + aheadCell(r) + "</td>" +
          '<td data-l="Bid escalation" class="num">' + sparkSvg(r) + (r.n_bids ? '<span class="sub">' + r.n_bids + " bids" + BVH.rawA(r.raw && r.raw.bids) + "</span>" : "") + "</td>" +
          '<td data-l="Winning builder" class="">' + bld + bidtxt + "</td>" +
          '<td data-l="To builder before refunds" class="num">' + pct + "</td>" +
          '<td data-l="Returned" class="num">' + retCell(r) + "</td></tr>";
      }).join("") + "</tbody>";
      tb.innerHTML = head + body;
      Array.prototype.forEach.call(tb.querySelectorAll("th button"), function (b) {
        b.addEventListener("click", function () { var k = b.getAttribute("data-k"); if (k === sortKey) sortDir = -sortDir; else { sortKey = k; sortDir = (k === "date" || k === "title" || k === "race_type" || k === "winner_builder") ? 1 : -1; } render(); var nb = tb.querySelector('th button[data-k="' + k + '"]'); if (nb) nb.focus(); });
      });
    }
    function setF(f) { filter = f; $("#f-head").setAttribute("aria-pressed", f === "head"); $("#f-all").setAttribute("aria-pressed", f === "all"); render(); }
    $("#f-head").addEventListener("click", function () { setF("head"); });
    $("#f-all").addEventListener("click", function () { setF("all"); });
    render();
    var bp = headlineStats.block_producer_share.by_era_headline["mature-pbs-2024-26"], sr = headlineStats.sensitivity.excluding_c0ffeebabe_rows, rr = headlineStats.loot.returns.gross.headline_rows;
    $("#tblnote").innerHTML = '<b>Payment to the builder before refunds:</b> median ' + BVH.pct(bp.median_row_pct,1) + ' in ' + bp.rows + ' mature-PBS headline rows; after refunds, ' + BVH.pct(bp.after_refunds.median_row_pct,1) + '. Neemo, Kelp and BiFi paid under 2%. Ronin’s block paid 802.79 ETH before a 791.74 ETH refund (11.04 ETH after); Alkimiya 50.83 → 2.56 ETH; Paraswap 6.45 → 2.11 ETH; DeFi Plaza 66.32 → 61.56 ETH (<a href="paper.html#54-builder-refunds">paper §5.4</a>). <b>Returns:</b> ' + BVH.pct(rr.pooled_pct,1) + ' across ' + rr.rows + ' priced headline rows, ' + rr.known_zero_rows + ' with known zero. <b>Sensitivity:</b> ' + sr.rows + ' rows / ' + sr.incidents + ' incidents excluding c0ffeebabe.eth rows. Our call-level comparison for these rows is withheld by publication policy; anyone can compare the public traces.<br><br>' + "Builder bid response (ms) runs from the trigger (attack, deploy or user withdrawal) first appearing in the public mempool archive to the first big step-up bid from the builder that went on to win the block. Bid contents are never visible, so this is an estimate with a stated upper bound; see the <a href=\"methods.html#delay\">methods page</a>. Rows marked as non-races are shown so the line between a race and a coincidence is visible. Payment to the builder before refunds is the coinbase transfer plus priority fee of the bot's main transaction divided by its gross take, where the take is known; a race page may add further bot transactions in the same block. Pre-Merge races have no relay and no bid stream; they are decided by gas price and position. Data: <a href=\"data/incidents.json\">incidents.json</a>.";
  }

  /* ---------- bot lineages + on-chain messages ---------- */
  function lineages(L) {
    var A = L.a57 || {}, y = L.yoink || {}, mm = L.messages || {}, seen = {}, yRaces = rows.filter(function (r) { return r.bot === "Yoink" && !seen[r.slug + "|" + r.sub] && (seen[r.slug + "|" + r.sub] = 1); }).map(function (r) { return '<a href="' + href(r) + '">' + BVH.esc(r.title) + "</a>"; }).join(", ");
    $("#linlist").innerHTML =
      '<div class="lin"><h3>Yoink, 2022 to 2026</h3><p>One deployer address has put up <b>' + y.contracts + ' contracts</b>' + BVH.rawA(y.raw, "raw", "Contract-creation transactions of Yoink\'s deployer address, cut from the saved Etherscan list") +
      ', the first in August 2022. Each generation brought a new main contract and a small companion contract. Rows in this piece: ' + yRaces + '.</p></div>' +
      '<div class="lin"><h3>The 0xa57 family, 2019 to 2022</h3><p>The searcher that replayed the DODO attack in 2021 (&ldquo;Cheetah&rdquo;) and the one behind the Earning.Farm copy in 2022 look like <b>one operator</b>, not two. The same capital wallet (0x56178a0d) received the DODO take&nbsp;' + BVH.rawAs(A.dodo_take, "raw", "Receipt of Cheetah\'s DODO transaction: 1,139,456.204396 USDT end up at 0x56178a0d") + '&nbsp;and supplied the Earning.Farm capital&nbsp;' + BVH.rawAs(A.ef_capital, "raw", "Call trace of the Earning.Farm copy: 0x56178a0d is the source and the destination of the WETH it moves") + ', and the same deployer wallet (0x8641df2d) put up both generations of the bot&rsquo;s contracts&nbsp;' + BVH.rawAs(A.deployer, "raw", "Etherscan rows of the two deployer transactions, and the creation record of 0xa69babef") + '. Confidence is high, based on an inference from public Etherscan histories. The infrastructure goes back to 2019 and kept running after our two races. Races: <a href="incident.html?slug=dodo-v2-2021">DODO 2021</a> and <a href="incident.html?slug=earningfarm-2022">Earning.Farm 2022</a>.</p></div>';
    $("#msglist").innerHTML = (mm.groups || []).map(function (g) {
      var msgs = g.messages.map(function (m) {
        var mine = m.dir === "from_yoink";
        return '<figure class="msg ' + (mine ? "out" : "in") + '"><blockquote>' + BVH.esc(m.text) + '</blockquote><figcaption>' + (mine ? "Yoink wrote" : "Sent to Yoink") + ', ' + m.time_utc.replace("T", " ").replace("Z", " UTC") + ' &middot; <a class="raw" href="https://etherscan.io/tx/' + m.tx + '" target="_blank" rel="noopener" title="Open on Etherscan (external)">' + BVH.short(m.tx, 10, 6) + '</a>' + BVH.rawA(mm.raw, "raw", "Verbatim Etherscan row for this message transaction") + (m.failed ? ' <span class="pill no" title="The transaction reverted, so the value it names did not move here">reverted</span>' : "") + '</figcaption></figure>';
      }).join("");
      var ex = g.extra ? '<p class="small muted mono">' + BVH.esc(g.extra.label) + ', ' + BVH.esc(g.extra.time_utc) + ': <a class="raw" href="https://etherscan.io/tx/' + g.extra.tx + '" target="_blank" rel="noopener" title="Open on Etherscan (external)">' + BVH.short(g.extra.tx, 10, 6) + '</a>' + BVH.rawA(mm.raw, "raw", "Verbatim Etherscan row") + '</p>' : "";
      return '<div class="msgg"><h3>' + BVH.esc(g.heading) + '</h3><p class="muted">' + BVH.esc(g.context) + (g.incident ? ' <a href="incident.html?slug=' + g.incident + '">Race page</a>' : "") + '</p>' + msgs + ex + '</div>';
    }).join("");
    $("#msgnote").innerHTML = "Messages are the transaction input data of Yoink&rsquo;s address and of transactions sent to it, decoded as text. " + mm.total + " decodable messages exist; these are a selection of " + (mm.groups || []).length + " exchanges. Off-chain Blockscan Chat messages are not on chain and are not included. Who wrote the incoming messages is as claimed in the message itself.";
  }

  function evo(E) {
    if (!E || !E.measured) return;
    var m = E.measured, res = (m.private || 0) + (m.public || 0);
    if (res) $("#evo-teaser").innerHTML = "Since August 2023, when exposure can be measured, " + Math.round(100 * m.private / res) + "% of the " + res + " exploit transactions we could classify were missing from the public mempool archive, while most ordinary transactions in the same blocks were in it. The charts show what else changed" + (E.provisional ? " (provisional numbers, pre-correction)" : "") + ".";
  }
})();
