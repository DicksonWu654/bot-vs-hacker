(function () {
  "use strict";
  /* The landing page: the decided headline and who-lost strip, a playable Makina race, the headline numbers, the
     three parts, the 19-race scoreboard (who lost, full money split), the bot's messages as a chat, and the data &
     evidence drawers (race table, race types, lineages). */
  var $ = function (s) { return document.querySelector(s); };
  var RV = window.RaceViz, esc = BVH.esc;
  BVH.chrome("index.html");

  var headlineStats = null;
  var rows = [], filter = "head", sortKey = "date", sortDir = 1;

  Promise.all([BVH.json("data/incidents.json"), BVH.json("data/incident/makina-2026.json").catch(function () { return null; }), BVH.json("data/evolution.json").catch(function () { return null; }), BVH.json("data/lineages.json").catch(function () { return null; }), BVH.json("data/headline_stats.json"), BVH.json("data/explainer.json").catch(function () { return null; })])
    .then(function (r) {
      headlineStats = r[4]; rows = r[0];
      hero(r[1], rows); stats(); parts(r[1], r[5], r[2]); board(); types(); table();
      if (r[3]) lineages(r[3]); else { $("#lineages").hidden = true; $("#said").hidden = true; }
      /* deep links (index.html#data, #sb-makina-2026 ...) open the drawer they point into */
      BVH.openHash(null, true);
    })
    .catch(function (e) { BVH.loadError($("#hx-sum"), e); });

  /* ---------- hero: the decided headline, the 19 who-lost dots, then the Makina race ---------- */
  function hero(D, rows) {
    var nRaces = rows.filter(function (x) { return x.headline; }).length;
    $("#hx-dek").innerHTML = esc(BVH.headline(rows)) + '<sup class="fn">' + BVH.rawA("data/beaten_party.json", "data", "Who lost each headline race: verdict, note and evidence per race") + "</sup>";
    $("#hx-strip").innerHTML = BVH.lostStrip(rows);
    Array.prototype.forEach.call(document.querySelectorAll('a[href="#races"]'), function (a) { a.textContent = "All " + nRaces + " races"; });
    $("#races-h").textContent = "All " + nRaces + " races, and who lost each one";
    var row = rows.filter(function (x) { return x.id === "makina-2026"; })[0];
    if (!D || !row) { $("#hx-sum").textContent = "The race could not be loaded."; return; }
    var E = RV.E, ev = RV.events(D), dep = ev.filter(function (e) { return e.id === "deploy"; })[0];
    var bot = D.txs.filter(function (t) { return t.role === "bot"; })[0];
    var fn = RV.footnotes();
    $("#hx-date").textContent = BVH.dateLong(D.date);
    var IR = D.incident_raw || {};
    $("#hx-sum").innerHTML = "An attacker deployed Makina's drain contract. The next block, timestamped " + Math.round(-dep.t / 1000) + " seconds later" + timesA(D) +
      ", held a bot's copy and its " + E(bot.cb_eth) + " payment to the " + BVH.term("builder", "builder") + fn(IR.copy_tx_trace, "Trace of the copy, with the payment to the builder") + ".";
    var chart = RV.auction($("#hx-chart"), D, { compact: true, inset: false });
    RV.warp($("#hx-ctrl"), chart, { t0: D.t0_ms, label: "Time in the Makina race", autoplay: "inview", observe: $("#hx-chart"), compact: true });
    $("#hx-src").innerHTML = "Saved bids for block " + D.block.number.toLocaleString("en-US") + " on a linear scale" + BVH.bidsA(D.auction) + '. <a href="race.html#auction">The whole race, second by second, in Part 1 <span aria-hidden="true">&rarr;</span></a>';
  }

  /* ---------- headline numbers: one big figure, one plain sentence, a source marker ---------- */
  /* the 12 seconds is the gap between two block timestamps: the attacker's deploy (account history) and the copy's block */
  function timesA(D) {
    var IR = D.incident_raw || {}, br = D.block && D.block.raw || {};
    return '<sup class="fn">' + BVH.rawA(IR.attacker_txlist, "deploy", "Attacker account history: the deploy transaction and its block timestamp") + "</sup>" +
      '<sup class="fn">' + BVH.rawA(br.block, "block", "The copy's block, with its timestamp") + "</sup>";
  }

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
    /* v4 tiles: the same numbers, each with a label of eight words or fewer; the full sentences above sit in the drawer */
    tiles: {
      races: "races where a bot got there first",
      taken: "taken first by the bots, in {priced} priced races",
      returned: "of the take went back, in {retRows} known-outcome races",
      paid: "of the take paid to builders, before refunds"
    },
    lostWhy: "We checked who sent each losing transaction or setup.",
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
    var src = BVH.rawA("data/headline_stats.json", "data", "Computed in data/headline_stats.json from the race rows; method on the methods page");
    var T = HEADLINE.tiles;
    $("#stats").innerHTML = BVH.tiles([
      { big: fill("{races}", v), label: T.races, cls: "t-bot", src: src },
      { big: fill("<small class=\"pre\">about</small>{takenRound}<small> ETH</small>", v), label: fill(T.taken, v), src: src },
      { big: fill("{retPct}%", v), label: fill(T.returned, v), cls: "t-ret", src: src },
      { big: fill("{paidPct}%", v), label: T.paid, src: src }
    ], { cls: "tiles-4", label: "The headline numbers" });
    var items = [HEADLINE.taken, HEADLINE.returned, HEADLINE.paid];
    $("#stat-drawer").innerHTML = BVH.drawer("What each number counts", '<ul class="statfull"><li>' + BVH.esc(BVH.headline(rows)) + "</li>" + items.map(function (it) { return "<li><b>" + fill(it[0], v).replace(/<small[^>]*>|<\/small>/g, "") + "</b> " + fill(it[1], v) + "</li>"; }).join("") + "</ul>" +
      '<p class="statnote">' + fill(HEADLINE.exact, v) + '</p><p class="statnote"><a href="methods.html#headline-numbers">How we count these numbers</a>. Each one is broken down race by race in <a href="#data">the race table</a>, with a link to the saved source behind every value.</p>', { meta: "exact values and scope", id: "stat-notes" });
  }

  /* ---------- the three parts ---------- */
  function parts(D, X, Ev) {
    var tz = {};
    if (D) { var dep = RV.events(D)[0]; tz[1] = ['<span class="pt-big">' + Math.round(-dep.t / 1000) + " s" + timesA(D) + "</span>", "between block timestamps"]; }
    if (X && X.words_total) tz[2] = ['<span class="pt-big">' + (X.words_total - X.words_different) + " of " + X.words_total + '<sup class="fn">' + BVH.rawA(X.raw && X.raw.user_tx, "user", "The Ronin withdrawal transaction") + '</sup><sup class="fn">' + BVH.rawA(X.raw && X.raw.yoink_tx, "bot", "The bot's transaction") + "</sup></span>", "32-byte words match"];
    if (Ev && Ev.measured) tz[3] = ['<span class="pt-big">' + Ev.measured.attacker_seen_pct + '%<sup class="fn">' + BVH.rawA("data/evolution.json", "data", "Part 3's measured shares and their sample") + "</sup></span>", "of sampled attacks seen in public; other transactions in their blocks " + Ev.measured.control_seen_pct + "%"];
    $("#parts").innerHTML = BVH.SERIES.map(function (s) {
      var t = tz[s.part];
      return '<div class="part"><span class="pt-art night" data-pt-art="' + s.part + '" aria-hidden="true"></span><span class="pt-main"><span class="pt-n">Part ' + s.part + '</span><h3><a class="pt-link" href="' + s.href + '">' + s.title + "</a></h3>" + (t ? '<span class="pt-tz">' + t[0] + "<span>" + t[1] + "</span></span>" : "") + "</span></div>";
    }).join("");
    /* each card carries a small piece of its part's code-made art (same data as the part's opener) */
    var ART = { 1: ["gate", { id: "makina-2026", x: 0.7, trails: false, fade: "none" }], 2: ["rain", { fade: "none" }], 3: ["fog", { fade: "none" }] };
    if (window.BVHArt) Array.prototype.forEach.call(document.querySelectorAll("[data-pt-art]"), function (el) {
      var a = ART[el.getAttribute("data-pt-art")]; if (a) BVHArt.draw(el, a[0], a[1]);
    });
  }

  /* ---------- the scoreboard: 19 rows, grouped by who lost, the whole split on every row ---------- */
  function board() {
    BVH.scoreboard($("#board"), rows, { victims: { "makina-2026": "Makina", "kelp-rseth-2026": "the Safe's owner" } });
    $("#lost-drawer").innerHTML = BVH.drawer("How we judged who lost", "<p>" + HEADLINE.lostWhy + " " + HEADLINE.lostFoot + "</p>" +
      '<p class="sb-src">' + BVH.rawA("data/beaten_party.json", "data", "Who lost each headline race: verdict, note and evidence per race") + " every verdict, with its note and evidence</p>", { meta: "confirmed, likely, later" });
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
      var dm = $("#data-meta"); if (dm) dm.textContent = COLS.length + " fields per race";
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
    /* the bot's messages: one exchange as a chat thread, the rest in a drawer; tx details behind a toggle on each bubble */
    function when(m) { var d = m.time_utc; return BVH.dateLong(d.slice(0, 10)) + ", " + d.slice(11, 16) + " UTC"; }
    function thread(g) {
      return BVH.chat(g.messages.map(function (m) {
        var mine = m.dir === "from_yoink";
        return { side: mine ? "out" : "in", who: mine ? "Yoink wrote" : "Sent to Yoink", when: when(m), text: esc(m.text),
          tx: '<a class="raw" href="https://etherscan.io/tx/' + m.tx + '" target="_blank" rel="noopener" title="Open on Etherscan (external)">' + BVH.short(m.tx, 10, 6) + "</a>" + BVH.rawA(mm.raw, "raw", "Verbatim Etherscan row for this message transaction") + " block " + m.block.toLocaleString("en-US") + (m.failed ? ' <span class="pill no" title="The transaction reverted, so the value it names did not move here">reverted</span>' : "") };
      }), { label: g.heading });
    }
    function group(g, lead) {
      var ex = g.extra ? '<p class="cb-extra">' + esc(g.extra.label) + ", " + esc(g.extra.time_utc) + ': <a class="raw" href="https://etherscan.io/tx/' + g.extra.tx + '" target="_blank" rel="noopener" title="Open on Etherscan (external)">' + BVH.short(g.extra.tx, 10, 6) + "</a>" + BVH.rawA(mm.raw, "raw", "Verbatim Etherscan row") + "</p>" : "";
      return '<div class="msgg' + (lead ? " msgg-lead" : "") + '"><h3>' + esc(g.heading) + '</h3><p class="msgg-ctx">' + esc(g.context) + (g.incident ? ' <a href="incident.html?slug=' + g.incident + '">Race page</a>' : "") + "</p>" + thread(g) + ex + "</div>";
    }
    var G = mm.groups || [], lead = G.filter(function (g) { return g.key === "botbot"; })[0] || G[0], rest = G.filter(function (g) { return g !== lead; });
    if (lead) { $("#said-one").innerHTML = group(lead, true); BVH.buildIn($("#said-one"), "rise"); }
    $("#said-more").innerHTML = BVH.drawer("Read all " + G.length + " exchanges", rest.map(function (g) { return group(g); }).join("") +
      '<p class="tblnote">Messages are the transaction input data of Yoink&rsquo;s address and of transactions sent to it, decoded as text. These are a selection of ' + G.length + " exchanges. Off-chain Blockscan Chat messages are not on chain and are not included. Who wrote the incoming messages is as claimed in the message itself.</p>", { meta: rest.length + " more threads", id: "said-all" });
  }

})();
