/* One race, every source (incident.html?slug=...): the data & evidence page for a single race.
   The auction chart is the Part 1 chart (race.js RaceViz.auction) generalised to every race: LINEAR ETH axis against
   seconds from slot start, best-bid step line, the winning builder's bids highlighted, a zoom inset for tiny early bids,
   numbered events read from the data. A log axis exists only as a secondary toggle. Colours come from CSS classes and
   tokens (style.css, race.css, incident.css). Every number keeps its raw link (BVH.rawA). */
(function () {
  "use strict";
  var S = BVH.svg, esc = BVH.esc, rawA = BVH.rawA;
  BVH.chrome("none");
  var root = document.getElementById("root");

  /* the victim named in "Returned to ..." (same names as the Part 1 gallery) */
  var VICTIM = { "makina-2026": "Makina", "blueberry-2024": "Blueberry", "curve-vyper-2023--peth": "JPEG'd", "curve-vyper-2023--crv-eth-2": "Curve", "curve-vyper-2023--mseth": "Metronome", "kelp-rseth-2026": "the Safe's owner", "punk-2021": "Punk", "dodo-v2-2021": "DODO", "defiplaza-2024": "DeFi Plaza", "transitswap-2022": "Transit Swap", "earningfarm-2022": "Earning.Farm" };
  /* races told in Part 1 */
  var PART1 = { "makina-2026": "race.html", "blueberry-2024": "race.html#gallery", "curve-vyper-2023--peth": "race.html#gallery", "curve-vyper-2023--crv-eth-2": "race.html#gallery", "kelp-rseth-2026": "race.html#gallery", "punk-2021": "race.html#gallery", "dodo-v2-2021": "race.html#gallery", "defiplaza-2024": "race.html#gallery", "transitswap-2022": "race.html#gallery", "earningfarm-2022": "race.html#gallery" };
  function victimOf(row) { return VICTIM[row.id] || String(row.title || "the victim").split(":")[0].replace(/\s*\(.*\)\s*$/, "").replace(/^Curve \/ Vyper$/, "Curve").trim(); }

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
    if (!row) { root.innerHTML = '<div class="callout bad" style="margin-top:60px">No race with that name. <a href="index.html#data">Pick one from the table</a>.</div>'; return; }
    if (row.stub) { document.title = row.title + " | The Bot Beat the Hacker"; renderStub(row, rows); return; }
    return BVH.json("data/incident/" + row.id + ".json").then(function (D) {
      document.title = D.title + " | The Bot Beat the Hacker"; render(D, row, rows);
    });
  }).catch(function (e) { BVH.loadError(root, e); });

  /* ---------- small formatters (ported from race.js) ---------- */
  function sgn(ms, d) { var a = Math.abs(ms / 1000); return (ms < 0 ? "−" : ms > 0 ? "+" : "") + a.toFixed(d == null ? (a < 10 ? 2 : 1) : d) + " s"; }
  function E(x, d) { if (x == null || isNaN(x)) return "n/a"; if (Math.abs(x) < 1 && d == null) return BVH.eth(x); return x.toLocaleString("en-US", { minimumFractionDigits: d == null ? 2 : d, maximumFractionDigits: d == null ? 2 : d }) + " ETH"; }
  function num(n) { return n == null ? "" : Number(n).toLocaleString("en-US"); }
  function cap1(t) { return t.charAt(0).toUpperCase() + t.slice(1); }
  function niceMax(v) { var st = [1, 2, 2.5, 5, 10], p = Math.pow(10, Math.floor(Math.log10(v || 1))); for (var i = 0; i < st.length; i++) if (st[i] * p >= v) return st[i] * p; return 10 * p; }
  function tickStep(max, n) { var raw = max / (n || 5), p = Math.pow(10, Math.floor(Math.log10(raw))), m = raw / p; return (m <= 1 ? 1 : m <= 2 ? 2 : m <= 2.5 ? 2.5 : m <= 5 ? 5 : 10) * p; }
  function fmtTick(v) { if (v === 0) return "0"; if (v >= 1000) return v.toLocaleString("en-US"); if (v >= 1) return String(+v.toFixed(2)); return String(+v.toPrecision(2)); }
  /* time scale with an optional break: [t0, tb] gets `frac` of the width, [tb, t1] the rest; both linear */
  function timeScale(t0, tb, t1, r0, r1, frac) {
    if (tb == null || tb <= t0 || tb >= t1) { var l = BVH.lin(t0, t1, r0, r1); l.rb = null; return l; }
    var rb = r0 + (r1 - r0) * frac, a = BVH.lin(t0, tb, r0, rb), b = BVH.lin(tb, t1, rb, r1);
    var f = function (t) { return t <= tb ? a(t) : b(t); };
    f.rb = rb; f.tb = tb; return f;
  }
  function qhref(r) { return "incident.html?slug=" + encodeURIComponent(r.slug) + (r.sub ? "&sub=" + encodeURIComponent(r.sub) : ""); }
  function kicker() { return '<p class="series-kicker inc-kicker"><span class="sk-n">Data &amp; evidence</span><span class="sk-t"><a href="index.html#data">Every race</a> / one race, every source</span></p>'; }
  function subtabs(sibs, curId) {
    if (sibs.length < 2) return "";
    return '<div class="subtabs" role="navigation" aria-label="Races in this incident">' + sibs.map(function (s) { return '<a href="' + qhref(s) + '"' + (s.id === curId ? ' aria-current="true"' : "") + ">" + esc(s.sub || "main race") + "</a>"; }).join("") + "</div>";
  }
  function neighbours(rows, curId) {
    var idx = rows.findIndex(function (r) { return r.id === curId; }), prev = rows[idx - 1], next = rows[idx + 1];
    return '<nav class="pn" aria-label="Neighbouring races">' + (prev ? '<a href="' + qhref(prev) + '">earlier: ' + esc(prev.title) + "</a>" : "<span></span>") + (next ? '<a href="' + qhref(next) + '">later: ' + esc(next.title) + "</a>" : "<span></span>") + "</nav>";
  }

  /* rows without a replay: investigated and set aside (not a race, or a late copy). Say so plainly. */
  function renderStub(row, rows) {
    var why = { "no-race": "Not a race. We looked, and nothing copied or beat this attacker.", "late-copy": "Not counted. A copy that came after the attacker had already succeeded.", "bot-was-first-exploiter": "Not counted. No separate attacker." }[row.race_type] || "Not counted in the headline.";
    var sibs = rows.filter(function (r) { return r.slug === row.slug; });
    var h = '<header class="ihead inc-head">' + kicker() + '<h1>' + esc(row.title) + '</h1><p class="meta"><span>' + BVH.dateLong(row.date) + '</span><span class="pill no">' + (row.race_type === "no-race" ? "not a race" : "not counted") + '</span><span class="pill">' + esc(BVH.rtName(row.race_type)) + '</span><span class="pill warn">no replay: ' + (row.mempool === "in-block-only" ? "in-block evidence only" : "not in the mempool archive") + '</span></p>';
    h += subtabs(sibs, row.id);
    h += '<p class="lede">' + esc(row.one_liner || "") + '</p></header>';
    h += '<section class="inc-sec"><div class="callout"><b>' + why + '</b> This entry is listed so that the line between a race and a coincidence is visible. There is no replay because there is no race to replay.</div>';
    if (row.fate) h += '<h3>Why it is set aside</h3><p class="prose">' + esc(row.fate) + '</p>';
    h += '<p class="small"><a href="methods.html#evidence">How we judged a race</a> &nbsp; <a href="index.html#data">Back to the table</a></p></section>';
    h += neighbours(rows, row.id);
    root.innerHTML = h;
  }

  /* ================================================================ page */
  function render(D, row, rows) {
    var sibs = rows.filter(function (r) { return r.slug === D.slug; });
    var memPill = { measured: '<span class="pill yes">mempool measured</span>', "in-block-only": '<span class="pill warn">in-block evidence only</span>', "absent-from-archive": '<span class="pill warn">not in the mempool archive</span>' }[D.mempool.state] || "";
    if (D.mempool.state === "measured" && row && row.mempool === "absent-from-archive") memPill = '<span class="pill warn" title="Some other attacker transactions of this incident were seen in the archive, but not the one this race is about.">cited attacker tx not in the mempool archive</span>';
    var h = '<header class="ihead inc-head">' + kicker() + '<h1>' + esc(D.title) + '</h1><p class="meta"><span>' + BVH.dateLong(D.date) + '</span><span class="pill ' + (D.headline ? "yes" : "no") + '">' + (D.headline ? "bot beat the hacker" : D.race_type === "no-race" ? "not a race" : "not counted in the headline") + '</span><span class="pill">' + esc(BVH.rtName(D.race_type)) + "</span>" + '<span class="pill" title="' + esc(D.evidence_strength_basis || "") + '">evidence: ' + esc(D.evidence_strength || "n/a") + "</span>" + memPill + "<span>bot: " + esc(D.bot) + "</span></p>";
    h += subtabs(sibs, D.id);
    h += '<p class="lede">' + esc(D.one_liner || "") + "</p>";
    if (PART1[D.id]) h += '<p class="inc-p1"><a href="' + PART1[D.id] + '">' + (D.id === "makina-2026" ? "Read this race as a story in Part 1: The race" : "This race is in the Part 1 gallery: The race") + "</a></p>";
    h += "</header>";
    h += keyNumbers(D, row);
    if (D.caveat) h += '<p class="callout">' + esc(D.caveat) + '</p>';
    if (D.public_ordering) {
      var O = D.public_ordering;
      h += '<div class="callout"><p>' + esc(D.comparison_policy || "") + '</p><p>Bot: ' + BVH.explorer(O.bot_tx) + ' block ' + O.bot_block + ', position ' + O.bot_position + '. Raced attacker transaction: ' + BVH.explorer(O.raced_attacker_tx) + ' block ' + O.attacker_block + ', position ' + O.attacker_position + '.</p>' + (O.attacker_deploy ? '<p>Attacker deployment: ' + BVH.explorer(O.attacker_deploy.hash) + ' block ' + O.attacker_deploy.block + ', position ' + O.attacker_deploy.index + '.</p>' : '') + '</div>';
    }
    h += '<section class="inc-sec" id="auction" aria-labelledby="auc-h"></section>';
    h += '<section class="inc-sec" id="block" aria-labelledby="blk-h"></section>';
    h += '<section class="inc-sec" id="money" aria-labelledby="money-h"></section>';
    h += '<div id="below"></div>';
    root.innerHTML = h;
    auctionSection(D, row);
    blockSection(D);
    moneySection(D, row);
    below(D, row, rows);
  }

  /* big numbers at the top, each with its source */
  function keyNumbers(D, row) {
    var A = D.auction || {}, W = A.winner || {}, bot = D.txs.filter(function (t) { return t.role === "bot"; })[0];
    var tr = (row.raw && row.raw.trace) || D.block.raw.trace, cards = [];
    var paid = row.paid_to_builder_eth != null ? row.paid_to_builder_eth : row.coinbase_eth;
    cards.push(["Taken by the bot", row.gross_eth != null ? E(row.gross_eth) : "not priced in ETH", rawA(tr, "raw", "Block trace with the bot's take"), "ik-take"]);
    var cbx = row.coinbase_eth || 0, paySub = paid > 0.0005 ? (cbx > 0.0005 ? "direct transfer to the " + (D.pre_merge ? "miner" : "builder") + (paid - cbx > 0.0005 ? ", plus gas tip" : "") : "as gas fee; no direct transfer") : "";
    cards.push(["Paid to go first", paid != null && paid > 0.0005 ? E(paid) : (D.pre_merge ? "gas price only" : "no direct payment"), paid > 0.0005 ? rawA(tr, "raw", "Block trace: transfers to the builder") : "", "ik-bld", paySub]);
    if (!D.pre_merge) cards.push(["Winning bid", W.eth != null ? E(W.eth) : "not in the relay records", W.eth != null ? rawA(A.raw && A.raw.delivered, "raw", "Relay record of the block delivered to the proposer") : "", "ik-win"]);
    var pos = D.bot_idx != null ? "position " + D.bot_idx : "n/a", sub = "block " + num(D.block.number);
    if (D.atk_block != null && D.atk_idx != null) sub += D.atk_block === D.block.number ? "; attacker at " + D.atk_idx : "; attacker " + (D.atk_block - D.block.number) + " block" + (Math.abs(D.atk_block - D.block.number) === 1 ? "" : "s") + " later";
    cards.push(["Bot's place in the block", pos, rawA(D.block.raw.block, "raw", "The block, with its transaction order"), "ik-bot", sub]);
    return '<div class="inc-keys">' + cards.map(function (c) { return '<div class="ik ' + c[3] + '"><span class="ik-k">' + c[0] + '</span><span class="ik-v">' + c[1] + "</span>" + (c[4] ? '<span class="ik-s">' + esc(c[4]) + "</span>" : "") + '<span class="ik-r">' + c[2] + "</span></div>"; }).join("") + "</div>";
  }

  /* ================================================================ the race's key moments, from the data */
  function events(D) {
    var A = D.auction || {}, B = A.bids || {}, W = A.winner || {}, rec = B.record || [], ser = B.series || [], ev = [], t0 = D.t0_ms;
    var hasBids = ser.length > 0, bidsRaw = A.raw && A.raw.bids, bidsT = "Relay bid file for this slot";
    var tgt = D.race_type === "beat-whitehat-or-user" ? "the copied transaction" : "the attack";
    var bname = function (i) { return cleanName(B.builders && B.builders[i]); };
    var winBid = W.eth_bid != null ? W.eth_bid : W.eth;
    /* a deploy in the last 30 s before the slot */
    var deps = (D.events || []).filter(function (e) { return e.kind === "deploy" && e.t != null && e.t - t0 >= -30000 && e.t - t0 <= 1000; });
    if (deps.length) {
      var dep = deps[deps.length - 1], size = /CREATE ([\d,]+) B/.exec(dep.detail || ""), atkC = /attack contract/i.test(dep.detail || "");
      ev.push({ id: "deploy", t: dep.t - t0, raw: (dep.raws && dep.raws[0]) || dep.raw, rawTitle: "The deploy transaction", title: "A contract goes up", short: atkC ? "attack contract deployed" : "contract deployed",
        text: "Block " + num(dep.block) + " includes " + (atkC ? "the attacker's " + (size ? size[1] + "-byte " : "") + "contract" : "a new contract") + ". From this moment its code is public.", note: dep.detail });
    }
    /* the copied/attack transaction first seen in the public mempool */
    var seenE = (D.mempool.entries || []).filter(function (e) { return e.seen && e.role === "attacker"; }).sort(function (a, b) { return a.rel_ms - b.rel_ms; })[0];
    var seen = D.attacker_seen_rel_ms;
    if (hasBids && seen != null && seen >= -30000 && seen <= B.last_ms + 1500) ev.push({ id: "seen", t: seen, rawHTML: seenE ? BVH.memA(seenE.raw) : "", title: cap1(tgt) + " shows up in public", short: tgt === "the attack" ? "attack seen in public" : "copied tx seen in public",
      text: cap1(tgt) + " first appears in the public mempool archive, " + (seen < 0 ? BVH.sec(-seen) + " before the slot starts." : BVH.sec(seen) + " after the slot starts.") });
    ev.push({ id: "slot", t: 0, raw: D.block.raw.block, rawTitle: "The block, with its timestamp", title: "The slot starts", short: "slot starts",
      text: "Block " + num(D.block.number) + "'s 12-second slot starts at " + BVH.clock(t0, false) + " UTC (the block's timestamp)." });
    if (hasBids) {
      ev.push({ id: "first", t: B.first_ms, eth: ser[0][1], raw: bidsRaw, rawTitle: bidsT, title: "Bidding opens", short: "first bid",
        text: "First bid in the relay files: " + BVH.eth(ser[0][1]) + " from " + bname(ser[0][2]) + "." });
      var jump = null;
      for (var i = 1; i < rec.length; i++) { var pv = rec[i - 1][1], r = rec[i][1] / Math.max(pv, 1e-9); if (pv >= 1e-4 && rec[i][1] >= 0.01 && r >= 10 && (!jump || r > jump.r)) jump = { r: r, i: i }; }
      var R = D.reaction;
      if (R && R.t_ms != null) ev.push({ id: "react", t: R.t_ms, eth: R.eth, raw: bidsRaw, rawTitle: bidsT, title: "First big bid after " + tgt + " was seen", short: "big bid",
        text: BVH.dur(R.delay_ms) + " after " + tgt + " was first seen, " + cleanName(R.builder) + " bids " + BVH.eth(R.eth) + ", many times the going rate." });
      if (jump && !(R && R.t_ms != null && Math.abs(rec[jump.i][0] - R.t_ms) < 150)) {
        var j = rec[jump.i], pj = rec[jump.i - 1];
        ev.push({ id: "jump", t: j[0], eth: j[1], prev: pj[1], raw: bidsRaw, rawTitle: bidsT, title: "The first big jump", short: "first big jump",
          text: "The best bid leaps from " + BVH.eth(pj[1]) + " to " + BVH.eth(j[1]) + " (" + bname(j[2]) + "), about " + Math.round(jump.r).toLocaleString("en-US") + " times the best bid so far." });
      }
      var jt = jump ? rec[jump.i][0] : -1e9;
      if (B.max_eth >= 100) {
        var p10 = rec.filter(function (x) { return x[1] >= 10; })[0];
        if (p10 && p10[0] > jt + 50) ev.push({ id: "ten", t: p10[0], eth: p10[1], raw: bidsRaw, rawTitle: bidsT, title: "A bidding war", short: "past 10 ETH", text: "Bids pass 10 ETH (" + BVH.eth(p10[1]) + ")." });
      }
      var lead = W.builder ? rec.filter(function (x) { return bname(x[2]) === W.builder; })[0] : null;
      var near = function (t, ms) { return ev.some(function (e) { return (e.id === "react" || e.id === "jump") && Math.abs(e.t - t) < ms; }); };
      if (lead && W.t_ms != null && lead[0] < W.t_ms - 200 && lead[0] > jt + 50 && !near(lead[0], 150) && lead[1] < winBid * 0.98) ev.push({ id: "lead", t: lead[0], eth: lead[1], raw: bidsRaw, rawTitle: bidsT, title: "The winning builder takes the lead", short: W.builder + " leads",
        text: "Builder " + W.builder + " takes the lead at " + BVH.eth(lead[1]) + "." });
      if (winBid != null && W.t_ms != null) {
        ev.push({ id: "win", t: W.t_ms, eth: winBid, raw: A.raw && A.raw.delivered, rawTitle: "Relay record of the block delivered to the proposer (it has no timestamp)", title: "The winning block reaches a relay", short: "winning bid",
          text: "The block that won, " + W.builder + "'s at " + E(winBid) + ", was first bid to a relay at " + BVH.sec(W.t_ms, true) + ". It holds the bot's transaction at position " + (D.bot_idx != null ? D.bot_idx : "n/a") + (W.relays && W.relays.length ? "; the delivery record is from " + W.relays.join(", ") + ", which does not record when the proposer chose it" : "") + "." });
        var hi = rec.filter(function (x) { return x[0] > W.t_ms && x[1] > winBid * 1.0005; }).pop();
        if (hi) ev.push({ id: "late", t: hi[0], eth: hi[1], raw: bidsRaw, rawTitle: bidsT, title: "Bids keep rising", short: "later bids", text: "Later bids reach " + E(hi[1]) + ". The block delivered to the proposer is the " + E(winBid) + " one." });
      } else if (winBid != null) {
        ev.push({ id: "winline", t: null, eth: winBid, raw: A.raw && A.raw.delivered, rawTitle: "Relay record of the block delivered to the proposer", title: "Winning bid, time not recorded", short: "winning bid",
          text: "The relay that delivered the block records the winning value, " + E(winBid) + " from " + (W.builder || "an unnamed builder") + (W.relays && W.relays.length ? " (" + W.relays.join(", ") + ")" : "") + ", but not when it was bid. The chart draws it as a level line." + (B.max_eth > winBid * 1.0005 ? " The bid files also hold higher bids, up to " + E(B.max_eth) + ", that did not win." : "") });
      } else {
        ev.push({ id: "nowin", t: null, raw: null, title: "Winning bid not in the relay records", short: "no winning bid",
          text: "None of the relays we queried has a delivery record for this block, so the winning bid and its builder are unknown. The bids still show how the auction moved." });
      }
    }
    var timed = ev.filter(function (e) { return e.t != null; }).sort(function (a, b) { return a.t - b.t; }), untimed = ev.filter(function (e) { return e.t == null; });
    timed.forEach(function (e, k) { e.n = k + 1; });
    return timed.concat(untimed);
  }

  /* ================================================================ the auction chart (linear) */
  var chartSeq = 0;
  function auctionChart(box, D, ev, o) {
    o = o || {};
    var A = D.auction, B = A.bids, W = A.winner || {}, winBid = W.eth_bid != null ? W.eth_bid : W.eth;
    var winIdx = W.builder ? B.builders.indexOf(W.builder) : -1, uid = "ic" + (++chartSeq);
    var timed = ev.filter(function (e) { return e.t != null; });
    var tMin = Math.min(B.first_ms, timed.length ? timed[0].t : 0, 0) - 600;
    var tMax = Math.max(B.last_ms, W.t_ms != null ? W.t_ms : -1e12, 0) + 400;
    var top = Math.max(B.max_eth || 0, winBid || 0) || 1;
    var ystep = tickStep(top, 6), ymax = Math.ceil(top * 1.04 / ystep) * ystep;
    var act = timed.filter(function (e) { return /^(jump|react|lead|ten|win)$/.test(e.id); })[0];
    var tBreak = null;
    if (act && tMax - tMin > 9000) { var tb = Math.floor((act.t - 1200) / 1000) * 1000; if (tb - tMin > 3500 && tMax - tb > 2500) tBreak = tb; }
    var F = tBreak != null ? 0.3 : null;
    var jumpE = ev.filter(function (e) { return e.id === "jump"; })[0];
    var scale = "lin", state = { t: tMax }, els = [], evEls = [], cursor, cursorLab, lastW = 0;
    function draw() {
      box.innerHTML = "";
      var w = Math.max(300, Math.round(box.clientWidth) || 700), narrow = w < 640; lastW = w;
      var H = narrow ? 340 : 470, m = { l: narrow ? 40 : 70, r: narrow ? 12 : 24, t: 44, b: 46 };
      var x = timeScale(tMin, tBreak, tMax, m.l, w - m.r, F || 0.3), y, yt = [], log = scale === "log";
      if (log) {
        var pos = B.series.map(function (p) { return p[1]; }).filter(function (v) { return v > 0; });
        var vmin = Math.max(1e-5, Math.min.apply(null, pos.length ? pos : [1e-4])), ylo = Math.pow(10, Math.floor(Math.log10(vmin))), yhi = Math.pow(10, Math.ceil(Math.log10(top * 1.05)));
        if (yhi / ylo < 100) ylo = yhi / 100;
        y = BVH.log(ylo, yhi, H - m.b, m.t); yt = BVH.logTicks(ylo, yhi);
      } else {
        y = BVH.lin(0, ymax, H - m.b, m.t);
        var ys = narrow ? tickStep(ymax, 4) : ystep;
        for (var v = 0; v <= ymax + ys * 1e-6; v += ys) yt.push(+v.toPrecision(10));
      }
      var summary = "Builder bids for block " + D.block.number + " on a " + (log ? "logarithmic" : "linear") + " ETH scale, " + B.n_total + " bids from " + sgn(B.first_ms) + " to " + sgn(B.last_ms) + " around the slot start. " + ev.map(function (e) { return (e.t != null ? sgn(e.t) + ": " : "") + e.title + ". " + e.text; }).join(" ");
      var svg = S("svg", { viewBox: "0 0 " + w + " " + H, width: w, height: H, class: "auc inc-auc", role: "img", "aria-label": summary }, box);
      els = []; evEls = [];
      var defs = S("defs", null, svg);
      /* this block's slot, shaded; the slot start as a labelled line */
      var x0 = x(0);
      S("rect", { x: x0, y: m.t - 26, width: Math.max(0, w - m.r - x0), height: H - m.b - m.t + 26, class: "auc-slot" }, svg);
      S("line", { x1: x0, x2: x0, y1: m.t - 26, y2: H - m.b, class: "inc-slotline" }, svg);
      var room = w - m.r - x0, slotTxt = narrow ? "slot starts" : "block " + num(D.block.number) + "'s slot starts, " + BVH.clock(D.t0_ms, false) + " UTC";
      if (!narrow && room < 300) slotTxt = "slot starts " + BVH.clock(D.t0_ms, false);
      S("text", room > (narrow ? 90 : slotTxt.length * 7 + 12) ? { x: x0 + 7, y: m.t - 12, class: "auc-slotlab" } : { x: x0 - 7, y: m.t - 12, "text-anchor": "end", class: "auc-slotlab" }, svg, slotTxt);
      if (!narrow && x0 - m.l > 260) S("text", { x: Math.max(m.l, x(Math.max(tMin, -12000))) + 8, y: m.t - 12, class: "auc-slotlab inc-prevslot" }, svg, "block " + num(D.block.number - 1) + "'s slot");
      /* grid + axes */
      yt.forEach(function (v) {
        S("line", { x1: m.l, x2: w - m.r, y1: y(v), y2: y(v), class: (log ? v === yt[0] : v === 0) ? "auc-base auc-floor" : "auc-grid" }, svg);
        S("text", { x: m.l - 8, y: y(v) + 4, "text-anchor": "end", class: "auc-tick" }, svg, fmtTick(v) + (narrow ? "" : " ETH"));
      });
      if (narrow) S("text", { x: m.l - 8, y: m.t - 12, "text-anchor": "end", class: "auc-tick" }, svg, "ETH");
      var ticks = [], t;
      if (x.rb != null) {
        for (t = Math.ceil(tMin / 3000) * 3000; t < tBreak - 1500; t += 3000) ticks.push(t);
        var st = (tMax - tBreak) > 9000 && narrow ? 2000 : 1000;
        for (t = tBreak; t <= tMax; t += st) ticks.push(t);
      } else { var xs = narrow ? (tMax - tMin > 8000 ? 4000 : 2000) : (tMax - tMin > 16000 ? 4000 : 2000); for (t = Math.ceil(tMin / xs) * xs; t <= tMax; t += xs) ticks.push(t); }
      ticks.forEach(function (t) {
        S("line", { x1: x(t), x2: x(t), y1: H - m.b, y2: H - m.b + 5, class: "auc-base" }, svg);
        S("text", { x: x(t), y: H - m.b + 19, "text-anchor": "middle", class: "auc-tick" }, svg, t === 0 ? "0" : (narrow ? sgn(t, 0).replace(" s", "") : sgn(t, 0)));
      });
      if (x.rb != null) {
        var bx = x.rb, by = H - m.b;
        S("rect", { x: bx - 5, y: by - 3, width: 10, height: 6, class: "auc-breakgap" }, svg);
        S("path", { d: "M" + (bx - 7) + " " + (by + 5) + "l5 -10M" + (bx + 1) + " " + (by + 5) + "l5 -10", class: "auc-break" }, svg);
        S("line", { x1: bx, x2: bx, y1: m.t - 26, y2: by - 6, class: "auc-breakline" }, svg);
        var ratio = (x(tBreak + 1000) - x(tBreak)) / (x(tMin + 1000) - x(tMin));
        if (!narrow) S("text", { x: bx, y: H - m.b + 36, "text-anchor": "middle", class: "auc-axlab auc-breaklab" }, svg, "time scale " + ratio.toFixed(0) + "× wider from here");
      }
      S("text", { x: w - m.r, y: H - 2, "text-anchor": "end", class: "auc-axlab" }, svg, narrow ? "seconds from slot start" : "seconds from the start of the slot");
      S("text", { x: 0, y: H - 2, class: "auc-axlab inc-scalelab" }, svg, log ? "ETH axis: log scale" : "ETH axis: linear");
      /* bids as light columns (race.js RaceViz.auction): a thin column from zero ETH to the price, a point of light
         on top, a short reflection under the floor. Other builders in mist, the winning builder in the amber streak.
         Columns only on the linear axis; the log view keeps the points. */
      var gC = S("g", { class: "auc-cols" }, svg), gF = S("g", { class: "auc-refl", "aria-hidden": "true" }, svg), gD = S("g", { class: "auc-dots" }, svg), gW = S("g", { class: "auc-dots-w glow-s" }, svg), yb = y(log ? yt[0] : 0);
      B.series.forEach(function (p) {
        if ((p[3] & 1) === 1 && W.t_ms != null) return;
        var isW = p[2] === winIdx, px = x(p[0]), py = y(p[1]), hh = yb - py;
        if (!log && hh > 1.5) {
          els.push([p[0], S("rect", { x: (px - 0.6).toFixed(1), y: py.toFixed(1), width: 1.2, height: hh.toFixed(1), class: isW ? "auc-col auc-col-w" : "auc-col" }, gC)]);
          els.push([p[0], S("rect", { x: (px - 0.6).toFixed(1), y: (yb + 1.5).toFixed(1), width: 1.2, height: Math.min(14, 3 + hh * 0.08).toFixed(1), class: isW ? "auc-rf auc-rf-w" : "auc-rf" }, gF)]);
        }
        els.push([p[0], S("circle", { cx: px.toFixed(1), cy: py.toFixed(1), r: isW ? 2.5 : 1.9, class: isW ? "auc-dot auc-dot-w" : "auc-dot" }, isW ? gW : gD)]);
      });
      /* best bid so far: a step line in pieces, so it reveals with the cursor; amber while the winning builder holds it */
      var rec = B.record, gR = S("g", { class: "auc-recs" }, svg), gRW = S("g", { class: "auc-recs-w glow" }, svg);
      for (var i = 0; i < rec.length; i++) {
        var a = rec[i], b = rec[i + 1], xe = b ? x(b[0]) : x(B.last_ms), isWin = winIdx >= 0 && a[2] === winIdx;
        els.push([a[0], S("path", { d: "M" + x(a[0]).toFixed(1) + " " + y(a[1]).toFixed(1) + "H" + xe.toFixed(1) + (b ? "V" + y(b[1]).toFixed(1) : ""), class: isWin ? "auc-rec auc-rec-w" : "auc-rec" }, isWin ? gRW : gR)]);
      }
      /* events */
      var placed = [], winLineY = null;
      function marker(g, e, cx, cy, cls) {
        var tries = 0;
        while (tries < 8 && placed.some(function (p) { return Math.abs(p[0] - cx) < 20 && Math.abs(p[1] - cy) < 20; })) { cy -= 22; tries++; }
        cy = Math.max(m.t - 4, cy); placed.push([cx, cy]);
        var c = S("g", { class: "auc-num" + (cls ? " " + cls : "") }, g);
        S("circle", { cx: cx, cy: cy, r: 9 }, c); S("text", { x: cx, y: cy + 4, "text-anchor": "middle" }, c, String(e.n));
        return cy;
      }
      ev.forEach(function (e) {
        var g = S("g", { class: "auc-ev auc-ev-" + e.id }, svg), ex = e.t != null ? x(e.t) : null, right = ex != null && ex > w * 0.62;
        if (e.id === "deploy") {
          S("line", { x1: ex, x2: ex, y1: m.t - 22, y2: H - m.b, class: "auc-depline" }, g);
          S("path", { d: "M" + ex + " " + (H - m.b - 8) + "l8 8-8 8-8-8z", class: "auc-dep" }, g);
          S("text", { x: ex + 8, y: H - m.b - (narrow ? 54 : 62), class: "auc-lab auc-lab-atk" }, g, narrow ? "deploy" : e.short);
          marker(g, e, ex, H - m.b - 34, "auc-num-atk");
        } else if (e.id === "seen") {
          S("line", { x1: ex, x2: ex, y1: m.t - 22, y2: H - m.b, class: "auc-seen" }, g);
          var sl = ex - 8 - (narrow ? 100 : 180) > m.l;
          S("text", { x: sl ? ex - 8 : ex + 8, y: H - m.b - 12, "text-anchor": sl ? "end" : "start", class: "auc-lab auc-lab-atk" }, g, narrow ? "seen in public" : e.short);
          marker(g, e, ex, H - m.b - 34, "auc-num-atk");
        } else if (e.id === "slot") {
          marker(g, e, ex, m.t + 18, "inc-num-slot");
        } else if (e.id === "win") {
          var lateE = ev.filter(function (q) { return q.id === "late"; })[0];
          var wl1 = "winning bid " + E(e.eth), wl2 = (narrow ? trunc(W.builder || "", 16) : W.builder) + " at " + sgn(e.t);
          var wlw = Math.max(wl1.length * 8.6, wl2.length * 7.3), squeeze = false;
          right = ex + 13 + wlw > w - m.r;
          if (right && ex - 13 - wlw < 2) { squeeze = true; right = false; }
          var wy = y(e.eth), below = squeeze || wy - 12 < m.t + 4 || (lateE && Math.abs(y(lateE.eth) - wy) < 34), wlx = squeeze ? Math.max(2, w - m.r - wlw) : right ? ex - 13 : ex + 13;
          S("circle", { cx: ex, cy: wy, r: 13, class: "auc-win-halo" }, g);
          S("circle", { cx: ex, cy: wy, r: 7.5, class: "auc-win glow-s" }, g);
          S("text", { x: wlx, y: below ? wy + (squeeze ? 28 : 22) : wy - 10, "text-anchor": right ? "end" : "start", class: "auc-lab auc-lab-big" }, g, wl1);
          S("text", { x: wlx, y: below ? wy + (squeeze ? 44 : 38) : wy + 6, "text-anchor": right ? "end" : "start", class: "auc-lab" }, g, wl2);
          marker(g, e, ex, below && !(squeeze && wy - 24 > m.t) ? wy + 24 : wy - 24, "auc-num-win");
          if (below) placed.push([ex, wy + 30]);
        } else if (e.id === "late") {
          S("circle", { cx: ex, cy: y(e.eth), r: 4.5, class: "auc-late" }, g);
          if (!narrow) S("text", { x: ex - 16, y: y(e.eth) - 14, "text-anchor": "end", class: "auc-lab" }, g, "highest later bid " + E(e.eth));
          marker(g, e, ex + 14, y(e.eth) + 2);
        } else if (e.id === "winline") {
          var ly = y(e.eth), lb = ly - 8 < m.t + 4;
          S("line", { x1: m.l, x2: w - m.r, y1: ly, y2: ly, class: "auc-winline" }, g);
          S("text", { x: m.l + 8, y: lb ? ly + 18 : ly - 8, class: "auc-lab auc-lab-big inc-lab-win" }, g, "winning bid " + E(e.eth) + (narrow ? "" : ", time not recorded"));
          if (narrow) S("text", { x: m.l + 8, y: lb ? ly + 33 : ly + 16, class: "auc-lab" }, g, "time not recorded");
          winLineY = ly;
        } else if (e.id === "nowin") {
          S("text", { x: w - m.r - 6, y: m.t + 46, "text-anchor": "end", class: "auc-lab inc-lab-nowin" }, g, narrow ? "no winning bid on record" : "winning bid not in the relay records");
        } else if (e.eth != null) {
          var ny = y(e.eth), lyy = ny - 22;
          if ((e.id === "first" || e.id === "jump") && ny > H - m.b - 30) lyy = H - m.b - (e.id === "jump" ? 46 : 24);
          var yy = marker(g, e, ex, lyy);
          S("line", { x1: ex, x2: ex, y1: ny, y2: yy + 9, class: "auc-lead" }, g);
        }
        evEls.push([e.t == null ? -1e12 : e.t, g]);
      });
      /* zoom inset for the bids too small to see on a linear scale */
      var showInset = !log && jumpE && jumpE.prev < ymax * 0.02 && jumpE.eth < ymax * 0.5;
      if (showInset) {
        var zx0 = Math.max(tMin, B.first_ms - 300), zx1 = Math.min(tMax, jumpE.t + 1100), zy1 = niceMax(jumpE.eth * 1.15);
        var big = rec.filter(function (r) { return r[1] > ymax * 0.2; })[0], limT = Math.min(jumpE.t, big ? big[0] : tMax);
        var avail = Math.min(x(limT) - 36, x(0) - (m.l + 14) >= 260 ? x(0) - 24 : 1e9) - (m.l + 14), ib, gi, host = svg, inChart = !narrow && avail >= 250;
        S("rect", { x: x(zx0), y: y(0) - 6, width: Math.max(4, x(zx1) - x(zx0)), height: 6, class: "auc-zoomsrc" }, svg);
        if (inChart) {
          ib = { x: m.l + 14, y: m.t + 8, w: Math.min(420, avail), h: 156 };
          if (winLineY != null && winLineY > ib.y - 24 && winLineY < ib.y + ib.h + 10) ib.y = Math.min(winLineY + 26, y(0) - ib.h - 40);
          gi = S("g", { class: "auc-inset" }, svg);
          S("rect", { x: ib.x, y: ib.y, width: ib.w, height: ib.h, rx: 6, class: "auc-insetbg" }, gi);
          S("line", { x1: ib.x + ib.w, y1: ib.y + ib.h, x2: x(zx1), y2: y(0) - 6, class: "auc-zoomline" }, gi);
          S("line", { x1: ib.x, y1: ib.y + ib.h, x2: x(zx0), y2: y(0) - 6, class: "auc-zoomline" }, gi);
        } else {
          host = S("svg", { viewBox: "0 0 " + w + " 170", width: w, height: 170, class: "auc auc-inset2", role: "img", "aria-label": "Zoom on the first bids, 0 to " + zy1 + " ETH. " + jumpE.text }, box);
          ib = { x: 0, y: 4, w: w, h: 160 }; gi = S("g", { class: "auc-inset" }, host);
          S("rect", { x: ib.x + 0.5, y: ib.y, width: ib.w - 1, height: ib.h, rx: 6, class: "auc-insetbg" }, gi);
        }
        var im = { l: 50, r: 14, t: 34, b: 22 }, ix = BVH.lin(zx0, zx1, ib.x + im.l, ib.x + ib.w - im.r), iy = BVH.lin(0, zy1, ib.y + ib.h - im.b, ib.y + im.t);
        var cp = S("clipPath", { id: uid + "-clip" }, defs); S("rect", { x: ib.x + im.l - 3, y: ib.y + im.t - 6, width: ib.w - im.l - im.r + 6, height: ib.h - im.t - im.b + 9 }, cp);
        if (!inChart) { var d2 = S("defs", null, host); var cp2 = S("clipPath", { id: uid + "-clip2" }, d2); S("rect", { x: ib.x + im.l - 3, y: ib.y + im.t - 6, width: ib.w - im.l - im.r + 6, height: ib.h - im.t - im.b + 9 }, cp2); }
        S("text", { x: ib.x + 10, y: ib.y + 17, class: "auc-insettitle" }, gi, "zoom: the first bids, 0 to " + zy1 + " ETH");
        var ist = tickStep(zy1, 2);
        for (var iv = 0; iv <= zy1 + 1e-9; iv += ist) { S("line", { x1: ib.x + im.l, x2: ib.x + ib.w - im.r, y1: iy(iv), y2: iy(iv), class: iv ? "auc-grid" : "auc-base" }, gi); S("text", { x: ib.x + im.l - 6, y: iy(iv) + 3.5, "text-anchor": "end", class: "auc-tick auc-tick-s" }, gi, iv ? fmtTick(+iv.toPrecision(6)) : "0"); }
        var its = (zx1 - zx0) > 6000 ? 2000 : 1000;
        for (var it = Math.ceil(zx0 / its) * its; it <= zx1; it += its) S("text", { x: ix(it), y: ib.y + ib.h - 7, "text-anchor": "middle", class: "auc-tick auc-tick-s" }, gi, sgn(it, 0));
        var gc = S("g", { "clip-path": "url(#" + uid + (inChart ? "-clip" : "-clip2") + ")" }, gi);
        B.series.forEach(function (p) {
          if (p[0] < zx0 || p[0] > zx1) return;
          var iw = p[2] === winIdx, ipy = iy(Math.min(p[1], zy1 * 1.2)), ih = iy(0) - ipy;
          if (ih > 1.5) els.push([p[0], S("rect", { x: (ix(p[0]) - 0.6).toFixed(1), y: ipy.toFixed(1), width: 1.2, height: ih.toFixed(1), class: iw ? "auc-col auc-col-w" : "auc-col" }, gc)]);
          els.push([p[0], S("circle", { cx: ix(p[0]).toFixed(1), cy: ipy.toFixed(1), r: 2, class: iw ? "auc-dot auc-dot-w" : "auc-dot" }, gc)]);
        });
        rec.forEach(function (a, k) {
          if (a[0] > zx1) return; var b = rec[k + 1], xe2 = ix(Math.min(zx1, b ? b[0] : B.last_ms));
          els.push([a[0], S("path", { d: "M" + ix(a[0]).toFixed(1) + " " + iy(Math.min(a[1], zy1 * 1.2)).toFixed(1) + "H" + xe2.toFixed(1) + (b && b[0] <= zx1 ? "V" + iy(Math.min(b[1], zy1 * 1.2)).toFixed(1) : ""), class: "auc-rec" }, gc)]);
        });
        var jx = ix(jumpE.t), jy = iy(jumpE.eth), jl = S("g", {}, gi), jr = jx > ib.x + ib.w * 0.55;
        S("text", { x: jr ? jx - 8 : jx + 8, y: Math.max(ib.y + im.t + 8, jy + 4), "text-anchor": jr ? "end" : "start", class: "auc-lab" }, jl, BVH.eth(jumpE.prev, false) + " → " + BVH.eth(jumpE.eth, false) + " ETH");
        evEls.push([jumpE.t, jl]);
      }
      /* the cursor */
      cursor = S("line", { x1: 0, x2: 0, y1: m.t - 22, y2: H - m.b, class: "auc-cursor" }, svg);
      cursorLab = S("text", { x: 0, y: H - m.b - 4, class: "auc-cursorlab" }, svg);
      state.x = x; state.w = w;
      apply();
    }
    function apply() {
      var t = state.t, x = state.x;
      els.forEach(function (e) { e[1].style.visibility = e[0] <= t ? "" : "hidden"; });
      evEls.forEach(function (e) { e[1].style.visibility = e[0] <= t + 1 ? "" : "hidden"; });
      var full = t >= tMax - 1, cx = x(t);
      cursor.style.visibility = full ? "hidden" : ""; cursorLab.style.visibility = full ? "hidden" : "";
      cursor.setAttribute("x1", cx); cursor.setAttribute("x2", cx);
      cursorLab.setAttribute("x", cx + (cx > state.w - 70 ? -6 : 6)); cursorLab.setAttribute("text-anchor", cx > state.w - 70 ? "end" : "start");
      cursorLab.textContent = sgn(t);
      if (o.onStep) { var cur = null; timed.forEach(function (e) { if (e.t <= t + 1) cur = e; }); o.onStep(cur, t); }
    }
    draw();
    var rt; window.addEventListener("resize", function () { clearTimeout(rt); rt = setTimeout(function () { if (Math.round(box.clientWidth) !== lastW) draw(); }, 140); });
    /* playback runs at an even pace across the drawn axis (compressed quiet seconds pass quickly) */
    function frac(t) { if (F == null) return (t - tMin) / (tMax - tMin); return t <= tBreak ? F * (t - tMin) / (tBreak - tMin) : F + (1 - F) * (t - tBreak) / (tMax - tBreak); }
    function tAt(f) { if (F == null) return tMin + f * (tMax - tMin); return f <= F ? tMin + (f / F) * (tBreak - tMin) : tBreak + ((f - F) / (1 - F)) * (tMax - tBreak); }
    return { set: function (t) { state.t = t; apply(); }, setScale: function (s) { scale = s; draw(); }, frac: frac, tAt: tAt, tMin: tMin, tMax: tMax };
  }
  /* builder names come from block extraData; some are raw bytes */
  function cleanName(n) { n = String(n == null ? "" : n).trim(); return (!n || /^(unknown|""|n\/a)$/i.test(n) || /[\u0000-\u001f\ufffd]/.test(n)) ? "an unnamed builder" : n; }
  function trunc(t, n) { t = String(t); return t.length > n ? t.slice(0, n - 1) + "…" : t; }

  /* ================================================================ section: the auction */
  function auctionSection(D, row) {
    var el = document.getElementById("auction"), A = D.auction, B = A && A.bids, hasBids = !!(B && B.series && B.series.length > 1);
    var M = D.mempool, h = '<div class="inc-head2"><p class="r-beat">' + (D.pre_merge ? "Before the Merge" : BVH.dateLong(D.date) + ", slot " + (D.slot != null ? num(D.slot) : "n/a")) + '</p><h2 id="auc-h">' + (hasBids ? "How the bids for block " + num(D.block.number) + " moved" : D.pre_merge ? "How the bot bought its place" : "No bid history for this block") + "</h2>";
    if (hasBids) h += '<p class="r-lede">Block builders bid for the right to fill the block, and the proposer picks one. Every bid in the relay files, in ETH on a linear scale, against seconds from the start of the slot.</p>';
    h += "</div>";
    if (!hasBids) { el.innerHTML = h + noBids(D); var gb = document.getElementById("gasbox"); if (gb) drawGas(gb, D); return; }
    var ev = events(D);
    h += '<figure class="auc-fig inc-fig"><div class="auc-ctrl" id="auc-ctrl"></div><div class="auc-cap" id="auc-cap" aria-live="polite"></div>' +
      '<ul class="fig-key inc-key" aria-label="Chart key"><li><i class="k-dot"></i>bids from other builders</li>' + (A.winner && A.winner.builder && B.builders.indexOf(A.winner.builder) >= 0 ? '<li><i class="k-dotw"></i>bids from ' + esc(A.winner.builder) + " (won)</li>" : "") + '<li><i class="k-rec"></i>best bid so far</li>' + (A.winner && A.winner.builder && B.record.some(function (r) { return B.builders[r[2]] === A.winner.builder; }) ? '<li><i class="k-recw"></i>best bid, held by the winning builder</li>' : "") + (A.winner && A.winner.eth != null ? '<li><i class="k-win"></i>winning bid</li>' : "") + (ev.some(function (e) { return e.id === "deploy" || e.id === "seen"; }) ? '<li><i class="k-atk"></i>' + (D.race_type === "beat-whitehat-or-user" ? "copied transaction" : "attacker") + "</li>" : "") + "</ul>" +
      '<div class="auc-box" id="auc"></div><div class="inc-scale" role="group" aria-label="ETH axis scale"><span>ETH axis</span><button type="button" data-scale="lin" aria-pressed="true">linear</button><button type="button" data-scale="log" aria-pressed="false">log</button><small id="scale-note"></small></div>' +
      '<figcaption class="auc-src" id="auc-src"></figcaption></figure>' +
      '<ol class="auc-steps inc-steps" id="auc-steps" aria-label="Key moments, in order"></ol>';
    el.innerHTML = h;
    var cap = document.getElementById("auc-cap"), list = document.getElementById("auc-steps");
    var chart = auctionChart(document.getElementById("auc"), D, ev, {
      onStep: function (e) {
        if (!e) { cap.innerHTML = '<span class="cap-n">·</span><span class="cap-t">Before the first event</span><span class="cap-x">Press Play or step forward.</span>'; mark(-1); return; }
        cap.innerHTML = '<span class="cap-n">' + e.n + '</span><span class="cap-t"><b>' + sgn(e.t) + "</b> " + esc(e.title) + '</span><span class="cap-x">' + esc(e.text) + "</span>";
        mark(e.n);
      }
    });
    list.innerHTML = ev.map(function (e) {
      var src = e.rawHTML || (e.raw ? rawA(e.raw, "raw", e.rawTitle) : "");
      return '<li data-n="' + (e.n || 0) + '" class="st-' + e.id + (e.t == null ? " st-untimed" : "") + '"><span class="st-n">' + (e.n || "–") + '</span><span class="st-time">' + (e.t != null ? sgn(e.t) + "<small>" + BVH.clock(D.t0_ms + e.t) + " UTC</small>" : "time not recorded") + '</span><span class="st-body"><b>' + esc(e.title) + "</b> " + esc(e.text) + src + (e.note ? '<small class="st-note">' + esc(e.note) + "</small>" : "") + "</span></li>";
    }).join("");
    function mark(n) { Array.prototype.forEach.call(list.children, function (li) { var k = +li.getAttribute("data-n"); li.classList.toggle("is-cur", k === n); li.classList.toggle("is-future", k > n && n > 0); }); }
    var tev = ev.filter(function (e) { return e.t != null; });
    BVH.player(document.getElementById("auc-ctrl"), {
      min: 0, max: 1, step: 0.001, duration: 14000, label: "Time from the start of the slot",
      stops: tev.map(function (e) { return { t: chart.frac(e.t), label: e.title }; }),
      format: function (v) { return sgn(chart.tAt(v)); },
      onChange: function (v) { chart.set(chart.tAt(v)); }
    });
    /* the log axis: a secondary view for reading tiny bids, never the default */
    var note = document.getElementById("scale-note");
    Array.prototype.forEach.call(el.querySelectorAll(".inc-scale button"), function (b) {
      b.addEventListener("click", function () {
        var s = b.getAttribute("data-scale");
        Array.prototype.forEach.call(el.querySelectorAll(".inc-scale button"), function (o) { o.setAttribute("aria-pressed", o === b ? "true" : "false"); });
        chart.setScale(s);
        note.textContent = s === "log" ? "Each gridline is 10 times the one below: good for reading tiny bids, misleading about size. Linear shows the real amounts." : "";
      });
    });
    var W = A.winner || {}, winInFiles = W.builder && B.builders.indexOf(W.builder) >= 0;
    var mem = M.state === "measured" ? "" : " Mempool: " + esc(M.note) + (M.coverage_raw ? rawA(M.coverage_raw, "raw", "Mempool archive index for that month") : "");
    document.getElementById("auc-src").innerHTML = "Each column is one block a builder offered the proposer, rising to the price it offered. " + ((A.raw.capped || []).length ? "At least " : "") + B.n_total + " bids from " + (A.n_builders || B.builders.length) + " builders" + BVH.bidsA(A) + "; " + B.n_shown + " are drawn, including every new best bid" + (B.n_offslot ? " (" + B.n_offslot + " rows for a competing slot left out)" : "") + "." +
      (W.builder ? (winInFiles ? " Amber columns are " + esc(W.builder) + "'s bids; the best-bid line is amber while " + esc(W.builder) + " holds it." : " The winning builder, " + esc(W.builder) + ", has no bids in these files.") : "") +
      (W.eth != null ? " Winning bid from the relay's delivery record" + rawA(A.raw.delivered, "raw", "Relay record of the payload delivered to the proposer") + "." : " No relay we queried recorded the delivered block.") +
      " Bid times are each relay's own clock." + mem;
  }

  /* no relay bids: pre-Merge (gas price) or a block not built through a queried relay */
  function noBids(D) {
    var A = D.auction, W = A && A.winner, pre = D.pre_merge;
    var why = pre ? "Before the Merge (September 2022) there were no slots, relays or builder bids. Position in a block was bought with gas price, or with a direct payment to the miner." :
      (W && W.eth != null ? "No bid history survives for this slot (relay retention, or the proposer was not registered with the relay that kept it). The delivered block paid the proposer " + E(W.eth) + rawA(A.raw && A.raw.delivered, "raw", "Relay delivery record") + "." : "This block was not built through a relay we could query, so there is no bid stream. Priority was bought with gas price and direct payments.");
    var h = '<div class="inc-nobids"><p class="inc-why">' + why + "</p>";
    if (D.premerge_note) h += '<p class="small muted mono">' + esc(D.premerge_note) + "</p>";
    h += '<figure class="auc-fig inc-fig"><figcaption class="inc-figt">What each transaction at the top of block ' + num(D.block.number) + " paid per unit of gas, in gwei (linear)" + rawA(D.block.raw.block, "raw", "The block") + "</figcaption>" + gasChart(D) + "</figure></div>";
    return h;
  }
  function gasChart(D) {
    var strip = D.strip || [];
    if (!strip.length) return '<p class="muted">No transaction list for this block.</p>';
    var atk = D.txs.filter(function (t) { return t.role === "attacker"; })[0], K = Math.min(strip.length, 32);
    var off = atk && atk.i >= K ? '<p class="small muted mono">The attacker\'s transaction is at position ' + atk.i + (atk.ok ? "" : " and reverted") + ", off this chart; the block below shows it.</p>" : "";
    return '<div class="inc-gasbox" id="gasbox"></div><ul class="fig-key inc-key"><li><i class="k-bot"></i>bot</li><li><i class="k-atk"></i>attacker</li><li><i class="k-gold"></i>direct payment to the ' + (D.pre_merge ? "miner" : "builder") + ' (in ETH, on top of gas)</li><li><i class="k-tx"></i>other transactions</li></ul>' + off;
  }
  /* gas price by block position, linear gwei axis; drawn at the measured width so text stays at its real size */
  function drawGas(box, D) {
    var lastW = 0;
    function draw() {
      var w = Math.max(300, Math.round(box.clientWidth) || 700), narrow = w < 640; lastW = w;
      var K = Math.min((D.strip || []).length, 32), bars = D.strip.slice(0, K), h = narrow ? 250 : 280, m = { l: narrow ? 36 : 48, r: 8, t: 58, b: 38 };
      var mx = Math.max.apply(null, bars.map(function (b) { return b[3] || 0; }).concat([1]));
      var st = tickStep(mx, 4), ymx = Math.ceil(mx * 1.05 / st) * st, y = BVH.lin(0, ymx, h - m.b, m.t), bw = (w - m.l - m.r) / K;
      var who = D.pre_merge ? "miner" : "builder";
      var aria = bars.filter(function (b) { return b[2]; }).map(function (b) { return (b[2] === "bribe" ? "direct payment" : b[2]) + " at position " + b[0] + ": " + (b[3] != null ? b[3] + " gwei" : "n/a") + (b[4] >= 0.001 ? ", plus " + BVH.eth(b[4]) + " paid directly to the " + who : ""); }).join("; ");
      var o = '<svg viewBox="0 0 ' + w + " " + h + '" width="' + w + '" height="' + h + '" class="inc-gas" role="img" aria-label="' + esc("Gas price by block position, linear scale up to " + ymx + " gwei. " + aria) + '">';
      for (var v = 0; v <= ymx + 1e-9; v += st) o += '<line x1="' + m.l + '" x2="' + (w - m.r) + '" y1="' + y(v) + '" y2="' + y(v) + '" class="' + (v ? "auc-grid" : "auc-base") + '"/><text x="' + (m.l - 6) + '" y="' + (y(v) + 4) + '" text-anchor="end" class="auc-tick">' + fmtTick(+v.toPrecision(6)) + "</text>";
      o += '<text x="' + (m.l - 6) + '" y="' + (m.t - 14) + '" text-anchor="end" class="auc-tick">gwei</text>';
      var tops = [];
      bars.forEach(function (b, i) {
        var gw = b[3] || 0, cls = b[2] === "bot" ? "g-bot" : b[2] === "attacker" ? "g-atk" : b[2] === "builder" ? "g-bld" : b[2] === "bribe" ? "g-gold" : b[2] === "focus" ? "g-focus" : "g-tx", bx = m.l + i * bw + 1, cx = bx + bw / 2;
        var anc = cx > w - 120 ? "end" : cx < m.l + 70 ? "start" : "middle";
        o += '<rect x="' + bx.toFixed(1) + '" y="' + y(gw).toFixed(1) + '" width="' + Math.max(2, bw - 2).toFixed(1) + '" height="' + Math.max(1.5, y(0) - y(gw)).toFixed(1) + '" class="' + cls + (b[1] === 1 ? "" : " g-rev") + '"/>';
        if (b[2] === "bot" || b[2] === "attacker") o += '<text x="' + cx.toFixed(1) + '" y="' + (y(gw) - 7).toFixed(1) + '" text-anchor="' + anc + '" class="auc-lab ' + (b[2] === "bot" ? "t-bot" : "t-atk") + '">' + b[2] + " " + fmtTick(gw) + " gwei</text>";
        if (b[4] >= 0.01) tops.push([cx, anc, b]);
      });
      /* direct payments are ETH, not gwei: called out above the plot with a leader line */
      tops.forEach(function (t, k) {
        var ly = 16 + k * 16;
        o += '<line x1="' + t[0].toFixed(1) + '" x2="' + t[0].toFixed(1) + '" y1="' + (ly + 5) + '" y2="' + (y(t[2][3] || 0) - 2).toFixed(1) + '" class="inc-lead-gold"/>';
        o += '<text x="' + t[0].toFixed(1) + '" y="' + ly + '" text-anchor="' + (t[1] === "middle" ? "start" : t[1]) + '" class="auc-lab inc-lab-gold">position ' + t[2][0] + ": +" + E(t[2][4]) + " direct to the " + who + "</text>";
      });
      bars.forEach(function (b, i) { if (i % (K > 20 ? 5 : 2) === 0 || b[2]) o += '<text x="' + (m.l + i * bw + 1 + bw / 2).toFixed(1) + '" y="' + (h - m.b + 15) + '" text-anchor="middle" class="auc-tick auc-tick-s">' + b[0] + "</text>"; });
      o += '<text x="' + (w - m.r) + '" y="' + (h - 3) + '" text-anchor="end" class="auc-axlab">block position' + (D.block.ntx > K ? " (first " + K + " of " + D.block.ntx + ")" : "") + "</text></svg>";
      box.innerHTML = o;
    }
    draw();
    var rt; window.addEventListener("resize", function () { clearTimeout(rt); rt = setTimeout(function () { if (Math.round(box.clientWidth) !== lastW) draw(); }, 140); });
  }

  /* ================================================================ section: the block */
  function blockSection(D) {
    var el = document.getElementById("block"), b = D.block;
    var h = '<div class="inc-head2"><p class="r-beat">' + BVH.clock(b.ts_ms, false) + ' UTC</p><h2 id="blk-h">' + (D.bot_idx === 0 ? "Position 0" : "The block") + '</h2><p class="r-lede">Block ' + num(b.number) + " holds " + b.ntx + " transactions" + (b.builder ? (D.pre_merge ? ", mined by " : ", built by ") + esc(b.builder) : "") + rawA(b.raw.block, "raw", "The block") + ". Each cell is one transaction, in order.</p></div>";
    h += blockStrip(D.strip, D.txs, b.ntx, "Block " + b.number);
    h += blockKeys(D.txs, D, false);
    if (D.next_block) {
      var nb = D.next_block;
      h += '<h3 class="inc-h3">The next block, ' + num(nb.number) + rawA(nb.raw && nb.raw.block, "raw", "The next block") + "</h3>";
      h += blockStrip(null, nb.notable, nb.ntx || 0, "Block " + nb.number);
      h += blockKeys(nb.notable, D, true);
    }
    el.innerHTML = h;
  }
  function blockStrip(strip, notable, n, label) {
    var by = {}; (notable || []).forEach(function (t) { by[t.i] = t; });
    var sm = {}; (strip || []).forEach(function (s) { sm[s[0]] = s; });
    var cells = "", roles = [];
    for (var i = 0; i < n; i++) {
      var t = by[i], s = sm[i], role = t ? t.role : (s && s[2]) || "", ok = t ? t.ok : (s ? s[1] === 1 : true);
      var cls = role === "bot" ? "bc-bot" : role === "attacker" ? "bc-atk" : role === "builder" ? "bc-bld" : role === "bribe" ? "bc-bribe" : role === "focus" ? "bc-focus" : "bc-tx";
      if (role) roles.push(role + " at position " + i + (ok ? "" : " (reverted)"));
      cells += '<i class="' + cls + (ok ? "" : " bc-rev") + '" title="position ' + i + (role ? ": " + role : "") + (ok ? "" : ", reverted") + '"></i>';
    }
    return '<div class="blk-cells inc-cells' + (n > 200 ? " is-dense2" : n > 70 ? " is-dense" : "") + '" role="img" aria-label="' + esc(label + ": " + n + " transactions. " + roles.join("; ")) + '">' + cells + "</div>";
  }
  function blockKeys(txs, D, next) {
    var items = (txs || []).slice().sort(function (a, b) { return a.i - b.i; }), out = [];
    var groups = {};
    items.forEach(function (t) { (groups[t.role || "tx"] = groups[t.role || "tx"] || []).push(t); });
    function src(t) { var r = t.raw || {}; return rawA(r.tx || r.block, "raw", "The transaction in its block") + (r.trace ? rawA(r.trace, "trace", "Trace of the block") : ""); }
    function pos(arr) { return arr.length === 1 ? "Position " + arr[0].i : "Positions " + arr.map(function (t) { return t.i; }).join(", "); }
    if (groups.bot) {
      var cb = groups.bot.reduce(function (a, t) { return a + (t.cb_eth || 0); }, 0);
      out.push('<div class="bk bk-bot"><span class="bk-p">' + pos(groups.bot) + "</span><b>The bot" + (groups.bot.length > 1 ? "'s " + groups.bot.length + " transactions" : "") + ".</b> " + (cb >= 0.0005 ? "Pays " + E(cb) + " straight to the block's " + (D.pre_merge ? "miner" : "builder") + ". " : "") + (groups.bot.some(function (t) { return !t.ok; }) ? "One reverted. " : "") + src(groups.bot[0]) + "</div>");
    }
    if (groups.attacker) out.push('<div class="bk bk-atk"><span class="bk-p">' + pos(groups.attacker) + "</span><b>" + (D.race_type === "beat-whitehat-or-user" ? "The copied transaction" : "The attacker") + ".</b> " + (groups.attacker.every(function (t) { return t.ok; }) ? (next ? "Lands, but the money is already gone. " : "Lands after the bot. ") : "Reverts: nothing left to take. ") + src(groups.attacker[0]) + "</div>");
    if (groups.bribe) out.push('<div class="bk bk-bld"><span class="bk-p">' + pos(groups.bribe) + "</span><b>A direct payment to the " + (D.pre_merge ? "miner" : "builder") + ".</b> " + E(groups.bribe.reduce(function (a, t) { return a + (t.cb_eth || 0); }, 0)) + ". " + src(groups.bribe[0]) + "</div>");
    if (groups.focus) out.push('<div class="bk"><span class="bk-p">' + pos(groups.focus) + "</span><b>Related transaction" + (groups.focus.length > 1 ? "s" : "") + ".</b> " + esc(groups.focus[0].label || "") + " " + src(groups.focus[0]) + "</div>");
    if (groups.builder) groups.builder.forEach(function (t) {
      out.push('<div class="bk bk-bld"><span class="bk-p">Position ' + t.i + "</span><b>" + (t.label === "builder payout" ? "The builder pays the proposer" : cap1(t.label || "builder transaction")) + ".</b> " + (t.value_eth ? E(t.value_eth) + ". " : "") + src(t) + "</div>");
    });
    return out.length ? '<div class="blk-keys inc-bkeys">' + out.join("") + "</div>" : "";
  }

  /* ================================================================ section: the money */
  function moneySection(D, row) {
    var el = document.getElementById("money"), victim = victimOf(row), split = BVH.moneySplit(row, victim);
    var tr = (row.raw && row.raw.trace) || D.block.raw.trace;
    var h = '<div class="inc-head2"><p class="r-beat">Where the money went</p><h2 id="money-h">' + (split.priced ? "Where the " + E(split.gross, split.gross >= 100 ? 0 : 2) + " went" : "Where the money went") + "</h2>";
    h += '<p class="r-lede">' + (split.priced ? "The bot took " + E(split.gross) + rawA(tr, "raw", "Block trace with the bot's take") + ". The whole split: what went back to " + esc(victim) + ", what the bot paid the block builder and proposer for going first, and what the bot kept." : "The bot took tokens, not ETH" + rawA(tr, "raw", "Block trace with the bot's take") + ", and we do not price them, so the split cannot be drawn to scale. What is known is written out under Afterwards.") + "</p></div>";
    h += '<div class="inc-split">' + BVH.splitHTML(split, { labels: { ret: "Returned to " + victim }, sources: BVH.moneySrc(row, D) }) + (split.priced && !split.mixed ? '<p class="inc-split-x">The builder-and-proposer share is the bot\'s payment for going first.' + (split.parts.some(function (p) { return p.k === "unk"; }) ? " Unknown means no return is established in our sources; it is shown, not hidden." : "") + (split.parts.some(function (p) { return p.k === "bot" && p.eth < 0.0005; }) ? " The bot kept nothing." : "") + "</p>" : "") + "</div>";
    h += '<h3 class="inc-h3">Inside the block: what happened to the payment</h3>' + inBlock(D);
    if (D.dataset_money && D.dataset_money.scope !== "bot-tx") {
      var dm = D.dataset_money;
      h += '<p class="callout"><b>Dataset aggregate (' + esc(dm.scope) + '):</b> ' + E(dm.paid_to_builder_eth) + ' paid to the builder before refunds; ' + E(dm.builder_refund_eth || 0) + ' refunded. The block above covers the selected block. ' + esc(dm.note || '') + '</p>';
    }
    h += '<h3 class="inc-h3">Afterwards</h3>' + afterwards(D);
    el.innerHTML = h;
  }
  function inBlock(D) {
    var f = D.flows, A = D.auction;
    if (!f.meaningful) return '<p class="prose">No direct payment to the ' + (D.pre_merge ? "miner" : "builder") + " was made in this block" + (D.pre_merge ? ": before the Merge there were no builder bids, and this race was decided by gas price and position." : ": the bot bought its position with gas price.") + (f.bot_priority_fee_eth > 0.0005 ? " The bot's transaction fee was " + E(f.bot_priority_fee_eth) + rawA(D.block.raw.trace || D.block.raw.block, "raw", "The block") + "." : "") + (f.payout_other_eth > 0.0005 ? " The " + (D.pre_merge ? "miner" : "builder") + " paid out " + E(f.payout_other_eth) + " to other addresses in this block." : "") + "</p>";
    var C = f.bot_coinbase_eth + (f.bot_priority_fee_eth || 0), P = f.proposer_eth || 0, Rf = f.refund_to_bot_eth || 0, Q = f.payout_other_eth || 0, K = Math.max(0, C - P - Rf - Q);
    var segs = [["Paid on to the proposer (the winning bid)", P, "f-prop", A && A.raw && A.raw.delivered, "Relay delivery record"], ["Refunded to the bot by the builder", Rf, "f-bot", D.block.raw.trace, "Block trace"], ["Paid out to another address by the builder", Q, "f-oth", D.block.raw.trace, "Block trace"], ["Kept by the builder in this block", K, "f-bld", D.block.raw.trace, "Block trace"]].filter(function (s) { return s[1] > 0.0005; });
    var over = P > C + 0.0005;
    var out = '<p class="prose">The bot paid <b>' + E(C) + "</b> to the " + (D.pre_merge ? "miner" : "builder") + rawA(D.block.raw.trace, "raw", "Block trace") + (f.n_bot_txs > 1 ? " across " + f.n_bot_txs + " of its transactions" : "") + " (" + E(f.bot_coinbase_eth) + " as direct transfers" + (f.bot_priority_fee_eth ? " and " + E(f.bot_priority_fee_eth) + " as priority fees" : "") + "). Where that went, inside the same block:</p>";
    out += '<div class="inc-flow" role="img" aria-label="' + esc("Of " + BVH.eth(C) + " paid: " + segs.map(function (s) { return s[0] + " " + BVH.eth(s[1]); }).join("; ")) + '">' + segs.map(function (s) { return '<i class="' + s[2] + '" style="flex:' + Math.max(s[1], C * 0.004).toFixed(6) + ' 1 0"></i>'; }).join("") + "</div>";
    out += '<ul class="split-key inc-flowkey">' + segs.map(function (s) { return '<li class="' + s[2] + '"><i aria-hidden="true"></i><span class="sk-l">' + s[0] + rawA(s[3], "raw", s[4]) + '</span><span class="sk-v">' + E(s[1]) + (over ? "" : "<small>" + (100 * s[1] / C >= 0.1 ? (100 * s[1] / C).toFixed(1) + "%" : "&lt;0.1%") + "</small>") + "</span></li>"; }).join("") + "</ul>";
    if (over) out += '<p class="small muted mono">The proposer got ' + E(P - C) + " more than the bot paid: the builder added that from its own funds.</p>";
    if (f.payouts && f.payouts.length) out += '<p class="small muted mono">Payout transactions: ' + f.payouts.map(function (p) { return "position " + p.i + " " + E(p.eth) + " to " + BVH.short(p.to, 8, 4) + " " + BVH.explorer(p.h); }).join("; ") + ".</p>";
    out += '<p class="small muted mono">Read from the block itself: transfers from the builder\'s fee recipient after the bot\'s transaction. Who the builder works for is not on chain.</p>';
    return out;
  }
  function afterwards(D) {
    var out = "", after = D.events.filter(function (e) { return e.t != null && e.t > D.block.ts_ms + 1000 && ["return", "message", "tx", "fund"].indexOf(e.kind) >= 0; });
    if (D.fate && D.fate.text) out += '<div class="callout ' + (D.fate.kind === "returned" ? "good" : D.fate.kind === "kept" ? "bad" : "") + '"><b>' + ({ returned: "Returned. ", partial: "Partly returned. ", kept: "No return found. ", unknown: "Unknown. ", "n-a": "" }[D.fate.kind] || "") + "</b>" + esc(D.fate.text) + (D.fate.returned_pct != null ? " That is about " + D.fate.returned_pct + "% of the bot's gross take (our arithmetic from the transfers listed below)." : "") + "</div>";
    if (after.length) out += '<ol class="after inc-after">' + after.map(function (e) {
      return '<li class="af-' + esc(e.kind) + '"><span class="af-t">' + BVH.utc(e.t).replace(" UTC", "") + ' UTC<small>' + BVH.dur(e.t - D.block.ts_ms) + ' after the block</small></span><span class="af-k">' + esc(e.kind === "return" ? "funds move" : e.kind === "message" ? "on-chain message" : e.kind) + '</span><span class="af-d">' + esc(e.detail || "") + BVH.derivedTxt(e) + ((e.raws && e.raws.length) ? BVH.rawAs(e.raws) : rawA(e.raw)) + (e.actor ? "<small>" + esc(e.actor) + "</small>" : "") + "</span></li>";
    }).join("") + "</ol>";
    else out += '<p class="muted">No later transfers or messages were recorded for this race.</p>';
    return out;
  }

  /* ================================================================ the evidence below */
  function below(D, row, rows) {
    var el = document.getElementById("below"), h = "";
    h += '<section class="inc-sec inc-ev" aria-labelledby="ev-h"><div class="inc-head2"><p class="r-beat">The evidence</p><h2 id="ev-h">Every source for this race</h2></div><div class="cols"><div><h3 class="inc-h3">What the data says</h3>' + facts(D, row) + '</div><div><h3 class="inc-h3">The block</h3>' + blockFacts(D) + "</div></div></section>";
    h += '<section class="inc-sec" id="ledger"><h3 class="inc-h3">Every timestamp, with its source</h3><p class="prose small muted">Each row links to the saved response the time or number came from. Times are UTC; the offset is from the start of the slot.</p>' + ledger(D) + "</section>";
    h += '<section class="inc-sec" id="txs"><h3 class="inc-h3">Transactions that matter in the block</h3>' + txTable(D) + "</section>";
    if (D.timeline_publication_gaps && D.timeline_publication_gaps.length) h += '<p class="small muted">' + D.timeline_publication_gaps.length + ' source timeline entries are omitted pending complete evidence in the published responses. The repository retains the source records.</p>';
    if (D.narrative) h += '<section class="inc-sec"><details><summary class="mono small" style="cursor:pointer">Full evidence note from the investigation</summary><p class="prose" style="margin-top:12px">' + esc(D.narrative) + "</p></details></section>";
    h += caveats(D);
    h += neighbours(rows, D.id);
    el.innerHTML = h;
    el.querySelectorAll("table.led").forEach(function (t) {
      var heads = Array.prototype.map.call(t.querySelectorAll("thead th"), function (th) { return th.textContent; });
      t.querySelectorAll("tbody tr").forEach(function (tr) { Array.prototype.forEach.call(tr.children, function (td, i) { if (heads[i]) td.setAttribute("data-label", heads[i]); }); });
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
      if (B) p.push(["Bids on record", ((A.raw.capped || []).length ? "at least " : "") + B.n_total + " bids from " + (A.n_builders || B.builders.length) + " builders" + BVH.bidsA(A) + (B.n_offslot ? '<br><span class="muted">' + B.n_offslot + " more row" + (B.n_offslot === 1 ? "" : "s") + " in the same files carry another slot (a competing proposal for the same block number) and are not counted</span>" : "") + '<br><span class="muted">first ' + BVH.sec(B.first_ms, true) + ", last " + BVH.sec(B.last_ms, true) + ", median bid " + BVH.eth(B.median_eth) + ", highest " + BVH.eth(B.max_eth) + "</span>"]);
      if (A.winner && A.winner.builder) p.push(["Winner", esc(A.winner.builder) + (A.winner.eth != null ? " with " + BVH.eth(A.winner.eth) : "") + rawA(A.raw.delivered, "raw delivered") + '<br><span class="muted">delivered by ' + esc((A.winner.relays || []).join(", ") || "n/a") + "; proposer fee recipient " + BVH.short(A.winner.fee_recipient || D.block.fee_recipient, 8, 6) + "</span>"]);
      else p.push(["Winner", "not in the relay records we hold"]);
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
    D.mempool.entries.forEach(function (e) { if (e.seen) items.push({ t: e.t_ms, lane: "mempool", txt: (e.role || "tx") + " " + BVH.short(e.h, 10, 6) + " first seen (" + (e.sources || []).length + " sources)", raw: BVH.memA(e.raw) }); });
    var A = D.auction;
    if (A && A.bids) {
      var B = A.bids;
      if (D.reaction) items.push({ t: D.t0_ms + D.reaction.t_ms, lane: "auction", txt: "first big bid after first sight: " + BVH.eth(D.reaction.eth) + " by " + D.reaction.builder, raw: BVH.bidsA(A) });
      if (A.winner && A.winner.t_ms != null) items.push({ t: D.t0_ms + A.winner.t_ms, lane: "auction", txt: "winning bid " + BVH.eth(A.winner.eth_bid || A.winner.eth) + " by " + (A.winner.builder || ""), raw: rawA(A.raw.delivered, "raw delivered") + BVH.bidsA(A) });
      B.record.forEach(function (r, i) { if (i === 0 || i === B.record.length - 1 || r[1] / B.record[i - 1][1] >= 2.5) items.push({ t: D.t0_ms + r[0], lane: "auction", txt: "record bid " + BVH.eth(r[1]) + " (" + B.builders[r[2]] + ")", raw: BVH.bidsA(A) }); });
    }
    D.events.forEach(function (e) { items.push({ t: e.t, lane: e.kind, txt: e.detail || "", der: BVH.derivedTxt(e), raw: (e.raws && e.raws.length) ? BVH.rawAs(e.raws) : (e.raw ? rawA(e.raw) : (e.raw_note ? '<span class="muted" title="' + esc(e.raw_note) + '">' + esc(e.raw_note) + "</span>" : rawA(null))) }); });
    items.sort(function (a, b) { return (a.t == null ? 9e18 : a.t) - (b.t == null ? 9e18 : b.t); });
    var seen = {}; items = items.filter(function (i) { var k = i.t + "|" + i.txt; if (seen[k]) return false; seen[k] = 1; return true; });
    return '<div class="inc-tbl"><table class="led"><thead><tr><th scope="col">UTC</th><th scope="col">From slot start</th><th scope="col">Lane</th><th scope="col">What</th><th scope="col">Source</th></tr></thead><tbody>' + items.map(function (i) {
      var t = i.t == null ? "untimed" : BVH.utc(i.t).replace(" UTC", ""), rel = i.t == null || D.pre_merge ? "" : (Math.abs(i.t - D.t0_ms) > 36e5 ? BVH.dur(Math.abs(i.t - D.t0_ms)) + (i.t < D.t0_ms ? " before" : " after") : BVH.sec(i.t - D.t0_ms, true));
      return '<tr><td class="t">' + t + '</td><td class="t">' + rel + '</td><td><span class="tag other">' + esc(i.lane) + "</span></td><td>" + esc(i.txt) + (i.der || "") + "</td><td>" + i.raw + "</td></tr>";
    }).join("") + "</tbody></table></div>";
  }

  function txTable(D) {
    var rows = D.txs.slice().sort(function (a, b) { return a.i - b.i; });
    var out = '<div class="inc-tbl"><table class="led"><thead><tr><th scope="col">Pos.</th><th scope="col">Role</th><th scope="col">Transaction</th><th scope="col">Status</th><th scope="col">Value</th><th scope="col">Coinbase</th><th scope="col">Tip (gwei)</th><th scope="col">Source</th></tr></thead><tbody>';
    out += rows.map(function (t) {
      var r = t.raw || {};
      return "<tr><td class=\"t\">" + t.i + "</td><td><span class=\"tag " + esc(t.role || "other") + "\">" + esc(t.role || "tx") + "</span>" + (t.label ? '<br><span class="muted">' + esc(t.label) + "</span>" : "") + "</td><td><code>" + BVH.short(t.h, 10, 6) + "</code>" + BVH.explorer(t.h) + "<br><span class=\"muted\">" + BVH.short(t.from_, 8, 4) + " → " + BVH.short(t.to || "", 8, 4) + "</span></td><td>" + (t.ok ? "ok" : '<span class="inc-rev">reverted' + (t.err ? ": " + esc(t.err) : "") + "</span>") + "</td><td>" + (t.value_eth ? BVH.eth(t.value_eth) : "0") + "</td><td>" + (t.cb_eth ? BVH.eth(t.cb_eth) : "") + "</td><td>" + (t.tip != null ? t.tip : "") + "</td><td>" + rawA(r.tx || r.block, "raw block") + rawA(r.trace, "raw trace") + "</td></tr>";
    }).join("") + "</tbody></table></div>";
    if (D.next_block && D.next_block.notable.length) {
      var nb = D.next_block;
      out += '<h3 class="inc-h3">Next block, ' + nb.number + rawA(nb.raw.block) + '</h3><div class="inc-tbl"><table class="led"><thead><tr><th>Pos.</th><th>Role</th><th>Transaction</th><th>Status</th></tr></thead><tbody>' + nb.notable.map(function (t) { return "<tr><td class=\"t\">" + t.i + "</td><td><span class=\"tag " + esc(t.role) + "\">" + esc(t.role) + "</span></td><td><code>" + BVH.short(t.h, 10, 6) + "</code>" + BVH.explorer(t.h) + "</td><td>" + (t.ok ? "ok" : '<span class="inc-rev">reverted' + (t.err ? ": " + esc(t.err) : "") + "</span>") + "</td></tr>"; }).join("") + "</tbody></table></div>";
    }
    return out;
  }

  function caveats(D) {
    var c = [];
    if (D.slug === "kelp-rseth-2026") c.push("Kelp’s higher recorded losing bid and lower delivered winning bid remain unexplained. The queried relay histories contain no submission from the winning builder; the delivery record establishes the winner.");
    c.push("Relays publish a bid's hash, size and value, never its transactions. Which bid carried the bot's transaction is known only for the delivered block.");
    c.push("Bid times are each relay's own receive clock, so cross-relay comparison carries clock skew and network latency.");
    if (D.mempool.state !== "measured") c.push("Mempool: " + D.mempool.note);
    c.push("First seen means first seen by the archive's sources, not by the bot. The bot may have learned of the attack earlier or by another route.");
    return '<section class="inc-sec"><h3 class="inc-h3">Limits of this reconstruction</h3><ul class="prose small" style="padding-left:1.1em">' + c.map(function (x) { return "<li>" + esc(x) + "</li>"; }).join("") + '</ul><p class="small"><a href="methods.html">Methods, evidence levels and limitations</a></p></section>';
  }
})();
