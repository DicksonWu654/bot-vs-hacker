(function () {
  "use strict";
  /* The landing page: the series intro, a playable Makina race, the three parts, famous races with their full money
     split, the headline numbers, and the data & evidence layer (race table, race types, lineages, messages). */
  var $ = function (s) { return document.querySelector(s); };
  var RV = window.RaceViz, esc = BVH.esc;
  BVH.chrome("index.html");

  var headlineStats = null;
  var rows = [], filter = "head", sortKey = "date", sortDir = 1;

  Promise.all([BVH.json("data/incidents.json"), BVH.json("data/incident/makina-2026.json").catch(function () { return null; }), BVH.json("data/evolution.json").catch(function () { return null; }), BVH.json("data/lineages.json").catch(function () { return null; }), BVH.json("data/headline_stats.json"), BVH.json("data/explainer.json").catch(function () { return null; })])
    .then(function (r) {
      headlineStats = r[4]; rows = r[0];
      hero(r[1], rows); stats(); parts(r[1], r[5], r[2]); famous(); types(); table();
      if (r[3]) lineages(r[3]); else { $("#lineages").hidden = true; $("#said").hidden = true; }
      if (location.hash) { var t = document.getElementById(location.hash.slice(1)); if (t) t.scrollIntoView(); }
    })
    .catch(function (e) { BVH.loadError($("#hx-sum"), e); });

  /* ---------- hero: the Makina race, playable ---------- */
  function hero(D, rows) {
    var row = rows.filter(function (x) { return x.id === "makina-2026"; })[0];
    if (!D || !row) { $("#hx-sum").textContent = "The race could not be loaded."; return; }
    var E = RV.E, ev = RV.events(D), dep = ev.filter(function (e) { return e.id === "deploy"; })[0];
    var bot = D.txs.filter(function (t) { return t.role === "bot"; })[0], m = row.money || {};
    var fn = RV.footnotes();
    $("#hx-date").textContent = BVH.dateLong(D.date);
    $("#hx-sum").innerHTML = "Every bid for block " + D.block.number.toLocaleString("en-US") + ", the block the bot's copy ran in, against the clock. Press play to watch from the attacker's deploy; the replay slows down and pauses at each key moment.";
    var nOther = headlineStats && headlineStats.counts ? headlineStats.counts.headline_rows - 1 : null;
    $("#hx-dek").innerHTML = "On " + BVH.dateLong(D.date) + ", an attacker put a contract on Ethereum built to drain Makina. " + Math.round(-dep.t / 1000) +
      " seconds later a bot ran the same plan first and paid " + E(bot.cb_eth) + " to the block builder for the right to go first" + fn(D.incident_raw && D.incident_raw.copy_tx_trace, "Trace of the copy, with the payment to the builder") + "." +
      (nOther ? " This series replays that race and " + nOther + " others where a bot got to a live exploit first." : "");
    var chart = RV.auction($("#hx-chart"), D, { compact: true });
    RV.warp($("#hx-ctrl"), chart, { t0: D.t0_ms, label: "Time in the Makina race", autoplay: "inview" });
    $("#hx-split").innerHTML = '<p class="hx-split-h">Where the ' + E(row.gross_eth) + " it took went" + BVH.rawA(D.incident_raw && D.incident_raw.copy_tx_trace, "raw", "Trace of the copy") + "</p>" + BVH.splitHTML(BVH.moneySplit(row, "Makina"), { compact: true, labels: { bld: "Builder and proposer" }, sources: BVH.moneySrc(row, D) });
    $("#hx-src").innerHTML = "Bids for block " + D.block.number.toLocaleString("en-US") + " on a linear scale" + BVH.bidsA(D.auction) + ". <a href=\"race.html\">The whole race, second by second</a>";
  }

  /* ---------- headline numbers: one big figure, one plain sentence, a source marker ---------- */
  /* ======================================================================================
     HEADLINE COPY. Edit the words here; {names} are filled from data/headline_stats.json and
     data/incidents.json so the numbers never drift from the data. Big numbers are rounded for
     reading ("about 18,400 ETH"); the exact value is printed in the note under the numbers.
     ====================================================================================== */
  var HEADLINE = {
    races:    ["{races}<small> races</small>", "in {incidents} hacks, {y0} to {y1}, where a bot got to a live exploit first. In {orig} the loser was the original attacker ({conf} confirmed, {likely} likely); in {later} it was a later exploiter or we can't tell."],
    taken:    ["<small class=\"num-pre\">about </small>{takenRound}<small> ETH</small>", "taken first by the bots in those races. That total covers {priced} of the {races}: one take was paid in tokens that have no ETH price."],
    returned: ["{retPct}%", "of what the bots took went back to the victims, across the {retRows} races where the outcome is known. In {retZero} of them, nothing came back."],
    paid:     ["{paidPct}%", "of the take was paid to block builders for the right to go first: {paidEth} ETH, before any refunds."],
    exact:    "Exact values: {takenExact} ETH taken in the {priced} priced races; {retExact} ETH returned of the {retGross} ETH taken in the {retRows} races with a known outcome; {paidExact} ETH paid to builders.",
    /* who lost each race: one sentence over the three groups, one under them */
    lostLede: "The series is called The Bot Beat the Hacker, but the one a bot beats is not always the person who started the hack. We checked who sent each losing transaction or setup. In {orig} of the {races} races it was the original attacker ({conf} confirmed, {likely} likely). In {later} it was a later exploiter, or we can't tell.",
    lostFoot: "\u201cConfirmed\u201d means the loser's own setup trail or the victim's report ties it to the attack being intercepted; \u201clikely\u201d means a prepared attack with its origin not fully traced. Each race page shows its verdict and the saved responses behind it. <a href=\"methods.html#who-lost\">How we judged who lost</a>."
  };
  function fill(t, v) { return t.replace(/\{(\w+)\}/g, function (m, k) { return v[k] != null ? v[k] : m; }); }
  function n0(x) { return Math.round(x).toLocaleString("en-US"); }
  function n2(x) { return x.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 }); }

  function stats() {
    var H = headlineStats, c = H.counts, paid = H.block_producer_share.headline_rows, ret = H.loot.returns.gross.headline_rows, L = H.loot;
    var hr = rows.filter(function (r) { return r.headline; }), yrs = hr.map(function (r) { return +r.date.slice(0, 4); });
    var v = {
      races: c.headline_rows, incidents: c.headline_incidents, y0: Math.min.apply(null, yrs), y1: Math.max.apply(null, yrs),
      takenRound: n0(Math.round(L.total_gross_loot_eth_headline_rows / 100) * 100), takenExact: n2(L.total_gross_loot_eth_headline_rows),
      priced: c.headline_rows - (L.headline_rows_without_eth_price || []).length,
      retPct: Math.round(ret.pooled_pct), retRows: ret.rows, retZero: ret.known_zero_rows,
      retExact: n2(ret.sum_returned_eth), retGross: n2(ret.sum_denominator_eth),
      paidPct: Math.round(paid.pooled_pct), paidEth: n0(paid.sum_paid_eth), paidExact: n2(paid.sum_paid_eth)
    };
    var bc = BVH.beatenCounts(rows);
    v.orig = bc.original; v.conf = bc.confirmed; v.likely = bc.likely; v.later = bc.later;
    var src = '<sup class="fn">' + BVH.rawA("data/headline_stats.json", "data", "Computed in data/headline_stats.json from the race rows; method on the methods page") + "</sup>";
    var items = [HEADLINE.races, HEADLINE.taken, HEADLINE.returned, HEADLINE.paid];
    $("#stats").innerHTML = items.map(function (it) { return '<div class="num" role="listitem"><b>' + fill(it[0], v) + src + "</b><span>" + fill(it[1], v) + "</span></div>"; }).join("");
    var ex = $("#statexact"); if (ex) ex.textContent = fill(HEADLINE.exact, v);
    /* who lost: only drawn when every headline race carries a verdict */
    if (bc.total === c.headline_rows) {
      $("#wl-lede").innerHTML = fill(HEADLINE.lostLede, v) + '<sup class="fn">' + BVH.rawA("data/beaten_party.json", "data", "Who lost each headline race: verdict, note and evidence per race") + "</sup>";
      $("#wholost").innerHTML = BVH.whoLostHTML(rows);
      $("#wl-foot").innerHTML = HEADLINE.lostFoot;
    } else { $("#who-lost").hidden = true; }
  }

  /* ---------- the three parts ---------- */
  function parts(D, X, Ev) {
    var tz = {};
    if (D) { var dep = RV.events(D)[0]; tz[1] = ['<span class="pt-big">' + Math.round(-dep.t / 1000) + " s</span>", "from the attacker's deploy to the bot's copy at position 0"]; }
    if (X && X.words_total) tz[2] = ['<span class="pt-big">' + (X.words_total - X.words_different) + " of " + X.words_total + "</span>", "calldata words identical between the Ronin withdrawal and the bot's copy"];
    if (Ev && Ev.measured) tz[3] = ['<span class="pt-big">' + Ev.measured.attacker_seen_pct + "%</span>", "of attacker transactions were visible in the public mempool, against " + Ev.measured.control_seen_pct + "% of ordinary ones"];
    $("#parts").innerHTML = BVH.SERIES.map(function (s) {
      var t = tz[s.part];
      return '<a class="part" href="' + s.href + '"><span class="pt-art night" data-pt-art="' + s.part + '" aria-hidden="true"></span><span class="pt-n">Part ' + s.part + '</span><h3>' + s.title + "</h3><p>" + s.blurb + "</p>" + (t ? '<p class="pt-tz">' + t[0] + "<span>" + t[1] + "</span></p>" : "") + '<span class="pt-go">Read part ' + s.part + "</span></a>";
    }).join("");
    /* each card carries a small piece of its part's code-made art (same data as the part's opener) */
    var ART = { 1: ["gate", { id: "makina-2026", x: 0.7, trails: false, fade: "none" }], 2: ["rain", { fade: "none" }], 3: ["fog", { fade: "none" }] };
    if (window.BVHArt) Array.prototype.forEach.call(document.querySelectorAll("[data-pt-art]"), function (el) {
      var a = ART[el.getAttribute("data-pt-art")]; if (a) BVHArt.draw(el, a[0], a[1]);
    });
  }

  /* ---------- famous names first, each with the whole money split ---------- */
  var FAMOUS = [
    ["makina-2026", "Makina"], ["curve-vyper-2023--peth", "JPEG'd"], ["curve-vyper-2023--crv-eth-2", "Curve"], ["kelp-rseth-2026", "the Safe's owner"],
    ["ronin-2024--eth-leg", "Ronin"], ["blueberry-2024", "Blueberry"], ["punk-2021", "Punk"], ["earningfarm-2022", "Earning.Farm"], ["dodo-v2-2021", "DODO"]
  ];
  function famous() {
    Promise.all(FAMOUS.map(function (f) { return BVH.json("data/incident/" + f[0] + ".json").catch(function () { return null; }); })).then(drawFamous);
  }
  function drawFamous(DS) {
    var E = RV.E;
    $("#famlist").innerHTML = FAMOUS.map(function (f, fi) {
      var r = rows.filter(function (x) { return x.id === f[0]; })[0];
      if (!r) return "";
      var s = BVH.moneySplit(r, f[1]), name = r.title.split(":")[0].replace(/^Curve \/ Vyper$/, "Curve").trim();
      var sub = r.sub && r.title.indexOf(":") > 0 ? r.title.split(":").slice(1).join(":").trim() : "";
      var bot = String(r.bot || "").replace(/\s*\(.*\)\s*$/, "").trim();
      var href = "incident.html?slug=" + encodeURIComponent(r.slug) + (r.sub ? "&sub=" + encodeURIComponent(r.sub) : "");
      var kept = s.parts.filter(function (p) { return p.k === "bot"; })[0];
      var plain = "";
      if (!s.priced && r.id === "dodo-v2-2021") { var dm = /and ([\d.]+) ETH to/.exec(r.fate || ""); plain = "Antelope later sent back tokens" + (dm ? " and " + RV.E(+dm[1]) : "") + " to DODO; the return is not reconciled with the take."; }
      if (kept && kept.eth < 0.0005) plain = "The bot kept nothing.";
      else if (kept && s.priced && kept.eth / s.gross < 0.001) plain = "The bot kept next to nothing.";
      return '<li class="fx"><div class="fx-id"><a class="fx-name" href="' + href + '">' + esc(name) + "</a>" + '<span class="fx-meta">' + r.date.slice(0, 4) + (sub ? ", " + esc(sub) : "") + "</span>" +
        '<span class="fx-bot">' + esc(bot) + (r.headline ? "" : ' <span class="pill no" title="' + esc(BVH.RT[r.race_type] ? BVH.RT[r.race_type].def : "") + '">not in the headline count</span>') + "</span>" + (r.headline ? BVH.beatenHTML(r, { compact: true, note: true }) : '<p class="beaten-c fx-notrace">' + esc(BVH.RT[r.race_type] ? BVH.RT[r.race_type].def : "") + "</p>") + "</div>" +
        '<div class="fx-amt">' + (s.priced ? E(s.gross, s.gross >= 100 ? 0 : 2) : "tokens") + (s.priced ? '<small>taken' + BVH.rawA(r.raw && r.raw.trace, "raw", "Block trace with the bot's take") + "</small>" : "<small>not priced in ETH</small>") + "</div>" +
        '<div class="fx-split">' + BVH.splitHTML(s, { inline: true, labels: { bld: "To the builder and proposer", ret: "Returned to " + f[1] }, sources: BVH.moneySrc(r, DS[fi]) }) + (plain ? '<p class="fx-plain' + (s.priced ? "" : " fx-muted") + '">' + plain + "</p>" : "") + "</div></li>";
    }).join("");
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
    /* linear from zero, like every other bid chart on the site */
    var x = BVH.lin(t0, Math.max(t1, t0 + 1), 3, W - 5), y = BVH.lin(0, hi * 1.0001, H - 4, 4);
    var d = "", px = null, py = null;
    pts.forEach(function (p, i) { var X = x(p[0]), Y = y(p[1]); d += (i ? "H" + X.toFixed(1) + "V" + Y.toFixed(1) : "M" + X.toFixed(1) + " " + Y.toFixed(1)); });
    var last = pts[pts.length - 1];
    return '<svg class="spark" viewBox="0 0 ' + W + " " + H + '" role="img" aria-label="Record bid climbed from ' + BVH.eth(pts[0][1]) + " to " + BVH.eth(last[1]) + '"><path d="' + d + '" fill="none" stroke="var(--bot)" stroke-width="1.6"/><circle cx="' + x(last[0]).toFixed(1) + '" cy="' + y(last[1]).toFixed(1) + '" r="3" fill="var(--gold)"/></svg>';
  }
  function aheadCell(r) {
    if (r.race_type === "bot-was-first-exploiter") return '<span class="na" title="No separate attacker transaction is established; the first observed exploit transaction was the bot\'s.">no attacker</span>';
    var ba = r.blocks_ahead;
    if (r.race_type === "beat-whitehat-or-user" && r.bot_idx != null && r.atk_idx == null) return '<span class="na" title="The copied transaction is a user withdrawal or a whitehat rescue and was not matched to a block, so no distance is given.">no hacker transaction</span>';
    if (ba == null) return '<span class="na" title="The attacker\'s own call never landed, or could not be matched to a block.">' + (r.atk_landed ? "n/a" : "attacker never landed") + "</span>";
    var pos = (r.bot_idx != null && r.atk_idx != null) ? '<span class="sub">position ' + r.bot_idx + " vs " + r.atk_idx + "</span>" : "";
    if (ba === 0) return "same block" + pos;
    if (ba > 0) return ba + " block" + (ba > 1 ? "s" : "") + " earlier" + pos;
    return "<span class=\"na\">" + (-ba) + " block" + (-ba > 1 ? "s" : "") + " after</span>" + pos;
  }
  function reactCell(r) {
    if (r.detection_delay_ms != null) return r.detection_delay_ms + " ms" + BVH.rawA(r.raw && r.raw.mempool, "seen", "Start: mempool first-seen rows for the trigger transaction") + BVH.rawA(r.raw && r.raw.bids, "bid", "End: the relay bid file with the winning builder's first big bid") + '<span class="sub" title="' + BVH.esc(r.delay_method || "") + '">first sight to first big bid</span>';
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
      $("#count").textContent = list.length + " races" + (filter === "all" ? "" : ", each with who lost");
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
          '<td class="first"><span class="name">' + (r.stub ? BVH.esc(r.title) : '<a href="' + href(r) + '">' + BVH.esc(r.title) + "</a>") + '</span><span class="sub">' + BVH.esc(r.bot) + (r.stub && r.one_liner ? " &middot; " + BVH.esc(r.one_liner.length > 150 ? r.one_liner.slice(0, 147) + "..." : r.one_liner) : "") + "</span>" + (r.headline ? BVH.beatenHTML(r, { compact: true, note: true }) : "") + "</td>" +
          '<td data-l="Race type" class="rt">' + rt + (r.headline ? ' <span class="pill yes" title="Counted in the headline">counted</span>' : ' <span class="pill no" title="' + (r.race_type === "no-race" ? "Rejected: no bot beat or copied anyone here. Shown so the line is visible." : "Not counted in the headline: the bot did not beat a pending attack here.") + '">' + (r.race_type === "no-race" ? "not a race" : "not counted") + "</span>") + "</td>" +
          '<td data-l="Builder bid response (ms)" class="num">' + reactCell(r) + "</td>" +
          '<td data-l="Blocks ahead" class="num">' + aheadCell(r) + "</td>" +
          '<td data-l="Bid escalation" class="num">' + sparkSvg(r) + (r.n_bids ? '<span class="sub">' + r.n_bids + " bids" + BVH.bidsA({ raw: { bids: r.raw && r.raw.bids, bids_all: r.raw && r.raw.bids_all } }, "One relay's saved bids for this slot; the total adds up every relay file linked here.") + "</span>" : "") + "</td>" +
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
    $("#tblnote").innerHTML = '<b>Payment to the builder before refunds:</b> median ' + BVH.pct(bp.median_row_pct,1) + ' in ' + bp.rows + ' headline rows from the mature builder era (2024 to 2026; PBS, proposer-builder separation, is the system in which builders assemble blocks and proposers choose one); after refunds, ' + BVH.pct(bp.after_refunds.median_row_pct,1) + '. Neemo, Kelp and BiFi paid under 2%. Ronin’s block paid 802.79 ETH before a 791.74 ETH refund (11.04 ETH after); Alkimiya 50.83 → 2.56 ETH; Paraswap 6.45 → 2.11 ETH; DeFi Plaza 66.32 → 61.56 ETH (<a href="paper.html#54-the-builder-round-trip">paper §5.4</a>). <b>Returns:</b> ' + BVH.pct(rr.pooled_pct,1) + ' across ' + rr.rows + ' priced headline rows, ' + rr.known_zero_rows + ' with known zero. <b>Sensitivity:</b> ' + sr.rows + ' rows / ' + sr.incidents + ' incidents excluding c0ffeebabe.eth rows. Our call-level comparison for these rows is withheld by publication policy; anyone can compare the public traces.<br><br>' + "Builder bid response (ms) runs from the trigger (attack, deploy or user withdrawal) first appearing in the public mempool archive to the first big step-up bid from the builder that went on to win the block. Bid contents are never visible, so this is an estimate with a stated upper bound; see the <a href=\"methods.html#delay\">methods page</a>. Rows marked as non-races are shown so the line between a race and a coincidence is visible. Payment to the builder before refunds is the coinbase transfer plus priority fee of the bot's main transaction divided by its gross take, where the take is known; a race page may add further bot transactions in the same block. Pre-Merge races have no relay and no bid stream; they are decided by gas price and position. Data: <a href=\"data/incidents.json\">incidents.json</a>.";
  }

  /* ---------- bot lineages + on-chain messages ---------- */
  function lineages(L) {
    var A = L.a57 || {}, y = L.yoink || {}, mm = L.messages || {}, seen = {}, yRaces = rows.filter(function (r) { return r.bot === "Yoink" && !seen[r.slug + "|" + r.sub] && (seen[r.slug + "|" + r.sub] = 1); }).map(function (r) { return '<a href="' + href(r) + '">' + BVH.esc(r.title) + "</a>"; }).join(", ");
    $("#linlist").innerHTML =
      '<div class="lin"><h3>Yoink, 2022 to 2026</h3><p>One deployer address has put up <b>' + y.contracts + ' contracts</b>' + BVH.rawA(y.raw, "raw", "Contract-creation transactions of Yoink\'s deployer address, cut from the saved Etherscan list") +
      ', the first in August 2022. Rows in this piece: ' + yRaces + '.</p></div>' +
      '<div class="lin"><h3>The 0xa57 family, 2019 to 2022</h3><p>The searcher that replayed the DODO attack in 2021 (&ldquo;Cheetah&rdquo;) and the one behind the Earning.Farm copy in 2022 look like <b>one operator</b>, not two. The same capital wallet (0x56178a0d) received the DODO take&nbsp;' + BVH.rawAs(A.dodo_take, "raw", "Receipt of Cheetah\'s DODO transaction: 1,139,456.204396 USDT end up at 0x56178a0d") + '&nbsp;and supplied the Earning.Farm capital&nbsp;' + BVH.rawAs(A.ef_capital, "raw", "Call trace of the Earning.Farm copy: 0x56178a0d is the source and the destination of the WETH it moves") + ', and the same deployer wallet (0x8641df2d) put up both generations of the bot&rsquo;s contracts&nbsp;' + BVH.rawAs(A.deployer, "raw", "Etherscan rows of the two deployer transactions, and the creation record of 0xa69babef") + '. Confidence is high, based on an inference from public Etherscan histories. The infrastructure goes back to 2019 and kept running after our two races. Races: <a href="incident.html?slug=dodo-v2-2021">DODO 2021</a> and <a href="incident.html?slug=earningfarm-2022">Earning.Farm 2022</a>.</p></div>';
    $("#msglist").innerHTML = (mm.groups || []).map(function (g) {
      var msgs = g.messages.map(function (m) {
        var mine = m.dir === "from_yoink";
        return '<figure class="msg ' + (mine ? "out" : "in") + '"><blockquote>' + BVH.esc(m.text) + '</blockquote><figcaption>' + (mine ? "Yoink wrote" : "Sent to Yoink") + ', ' + m.time_utc.replace("T", " ").replace("Z", " UTC") + ' &middot; <a class="raw" href="https://etherscan.io/tx/' + m.tx + '" target="_blank" rel="noopener" title="Open on Etherscan (external)">' + BVH.short(m.tx, 10, 6) + '</a>' + BVH.rawA(mm.raw, "raw", "Verbatim Etherscan row for this message transaction") + (m.failed ? ' <span class="pill no" title="The transaction reverted, so the value it names did not move here">reverted</span>' : "") + '</figcaption></figure>';
      }).join("");
      var ex = g.extra ? '<p class="small muted mono">' + BVH.esc(g.extra.label) + ', ' + BVH.esc(g.extra.time_utc) + ': <a class="raw" href="https://etherscan.io/tx/' + g.extra.tx + '" target="_blank" rel="noopener" title="Open on Etherscan (external)">' + BVH.short(g.extra.tx, 10, 6) + '</a>' + BVH.rawA(mm.raw, "raw", "Verbatim Etherscan row") + '</p>' : "";
      return '<div class="msgg"><h3>' + BVH.esc(g.heading) + '</h3><p class="muted">' + BVH.esc(g.context) + (g.incident ? ' <a href="incident.html?slug=' + g.incident + '">Race page</a>' : "") + '</p>' + msgs + ex + '</div>';
    }).join("");
    $("#msgnote").innerHTML = "Messages are the transaction input data of Yoink&rsquo;s address and of transactions sent to it, decoded as text. These are a selection of " + (mm.groups || []).length + " exchanges. Off-chain Blockscan Chat messages are not on chain and are not included. Who wrote the incoming messages is as claimed in the message itself.";
  }

})();
