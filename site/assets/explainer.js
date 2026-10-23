(function () {
  "use strict";
  var $ = function (s) { return document.querySelector(s); };
  var esc = BVH.esc;
  BVH.chrome("explainer.html");

  /* ---------- tiny SVG toolkit (colours come from CSS tokens so light/dark just work) ---------- */
  var COL = { bot: "var(--bot)", atk: "var(--atk)", bld: "var(--bld)", gold: "var(--gold)", ink: "var(--ink)", mut: "var(--muted)", line: "var(--line2)" };
  var SOFT = { bot: "var(--bot-soft)", atk: "var(--atk-soft)", bld: "var(--bld-soft)", gold: "var(--gold-soft)", ink: "var(--bg3)", mut: "var(--bg3)" };
  function fig(id) { return document.getElementById(id); }
  function T(g, x, y, s, o) {
    o = o || {};
    var t = BVH.svg("text", { x: x, y: y, "text-anchor": o.a || "start", style: "font:" + (o.w || 400) + " " + (o.s || 13) + "px var(--mono);fill:" + (COL[o.c] || o.c || "var(--ink2)") + (o.strike ? ";text-decoration:line-through" : "") }, g, null);
    String(s).split("\n").forEach(function (ln, i) { BVH.svg("tspan", { x: x, dy: i ? (o.lh || 16) : 0 }, t, ln); });
    return t;
  }
  function R(g, x, y, w, h, c, o) {
    o = o || {};
    return BVH.svg("rect", { x: x, y: y, width: w, height: h, rx: o.rx == null ? 5 : o.rx, style: "fill:" + (o.fill || SOFT[c] || "var(--bg3)") + ";stroke:" + (COL[c] || c) + ";stroke-width:" + (o.sw || 1.3) + (o.dash ? ";stroke-dasharray:4 3" : "") }, g);
  }
  function L(g, x1, y1, x2, y2, c, o) {
    o = o || {};
    BVH.svg("line", { x1: x1, y1: y1, x2: x2, y2: y2, style: "stroke:" + (COL[c] || c) + ";stroke-width:" + (o.sw || 1.4) + (o.dash ? ";stroke-dasharray:4 3" : "") }, g);
    if (o.arrow) {
      var a = Math.atan2(y2 - y1, x2 - x1), s = 7;
      BVH.svg("polygon", { points: [x2, y2, x2 - s * Math.cos(a - .45), y2 - s * Math.sin(a - .45), x2 - s * Math.cos(a + .45), y2 - s * Math.sin(a + .45)].join(","), style: "fill:" + (COL[c] || c) }, g);
    }
  }
  function C(g, x, y, r, c, o) {
    return BVH.svg("circle", { cx: x, cy: y, r: r, style: "fill:" + (o && o.hollow ? "none" : (COL[c] || c)) + ";stroke:" + (COL[c] || c) + ";stroke-width:1.4" }, g);
  }
  function D(g, x, y, r, c) { // diamond = the bot
    return BVH.svg("polygon", { points: [x, y - r, x + r, y, x, y + r, x - r, y].join(","), style: "fill:" + COL[c] }, g);
  }
  function label(svg, f) { var g = BVH.svg("g", null, svg); f(g); }

  /* ---------- the eight small figures ---------- */
  function f1() {
    var s = fig("f1"); label(s, function (g) {
      L(g, 20, 118, 500, 118, "mut", { arrow: true }); T(g, 500, 140, "time", { a: "end", c: "mut", s: 12 });
      R(g, 36, 56, 150, 38, "atk"); T(g, 111, 79, "deploy the contract", { a: "middle", c: "ink" });
      R(g, 334, 56, 150, 38, "atk"); T(g, 409, 79, "call the exploit", { a: "middle", c: "ink" });
      L(g, 111, 94, 111, 118, "atk"); L(g, 409, 94, 409, 118, "atk");
      T(g, 111, 136, "block N", { a: "middle", s: 12, c: "mut" }); T(g, 409, 136, "block N + k", { a: "middle", s: 12, c: "mut" });
      L(g, 112, 40, 408, 40, "bot", { sw: 2 }); L(g, 112, 33, 112, 47, "bot", { sw: 2 }); L(g, 408, 33, 408, 47, "bot", { sw: 2 });
      T(g, 260, 29, "the bot's window", { a: "middle", c: "bot", w: 600 });
      D(g, 190, 118, 7, "bot"); T(g, 200, 106, "bot copies", { c: "bot", s: 12 });
      T(g, 20, 176, "k = 0, or no separate call at all: no window to use", { c: "mut", s: 12 });
    });
  }
  function f2() {
    var s = fig("f2"); label(s, function (g) {
      C(g, 44, 95, 16, "atk"); T(g, 44, 130, "the hacker's\ntransaction", { a: "middle", s: 12, c: "ink" });
      R(g, 190, 22, 170, 62, "bld"); T(g, 275, 42, "public mempool", { a: "middle", c: "ink", w: 600 }); T(g, 275, 62, "every node sees it", { a: "middle", s: 12 });
      for (var i = 0; i < 9; i++) C(g, 204 + i * 18, 74, 2.6, "bld");
      R(g, 190, 108, 170, 62, "mut", { dash: true }); T(g, 275, 128, "sent to a builder", { a: "middle", c: "ink", w: 600 }); T(g, 275, 148, "nobody else sees it", { a: "middle", s: 12 });
      L(g, 62, 88, 188, 56, "atk", { arrow: true }); L(g, 62, 102, 188, 136, "atk", { arrow: true });
      R(g, 410, 66, 96, 60, "gold"); T(g, 458, 92, "the block", { a: "middle", c: "ink", w: 600 }); T(g, 458, 110, "slot, 12 s", { a: "middle", s: 12 });
      L(g, 362, 56, 408, 86, "bld", { arrow: true }); L(g, 362, 138, 408, 108, "mut", { arrow: true });
      D(g, 22, 178, 5, "bot"); T(g, 34, 182, "a bot can only copy what it can see: the top path", { s: 11.5, c: "bot" });
    });
  }
  function f3() {
    var s = fig("f3"); label(s, function (g) {
      BVH.svg("polygon", { points: "70,16 450,16 290,150 230,150", style: "fill:var(--bg3);stroke:var(--line2);stroke-width:1.3" }, g);
      var seed = 7; function rnd() { seed = (seed * 9301 + 49297) % 233280; return seed / 233280; }
      for (var i = 0; i < 70; i++) { var y = 24 + rnd() * 54, half = 190 - (y - 16) * 1.2; C(g, 260 + (rnd() * 2 - 1) * (half - 8), y, 2.4, "mut"); }
      L(g, 150, 84, 370, 84, "bld", { dash: true }); T(g, 376, 88, "cheap filter", { c: "bld", s: 12 });
      for (var j = 0; j < 4; j++) C(g, 244 + j * 11, 118, 3, "mut");
      C(g, 249, 138, 4, "bot"); C(g, 271, 138, 4, "bot");
      T(g, 462, 30, "thousands in", { s: 12, c: "ink" });
      T(g, 306, 122, "simulate", { s: 12, c: "ink" }); T(g, 300, 150, "a handful", { s: 12, c: "bot" });
    });
  }
  function f4() {
    var s = fig("f4"); label(s, function (g) {
      var xs = [8, 138, 268, 398], names = [["pending", "transaction"], ["run it on a", "fork + trace"], ["who gained?", "read balances"], ["build a copy", "for the bot"]], cols = ["atk", "bld", "bld", "bot"];
      xs.forEach(function (x, i) { R(g, x, 40, 112, 58, cols[i]); T(g, x + 56, 65, names[i].join("\n"), { a: "middle", c: "ink", s: 12.5 }); });
      for (var i = 0; i < 3; i++) L(g, xs[i] + 114, 69, xs[i + 1] - 2, 69, "mut", { arrow: true });
      T(g, 391, 62, "yes", { a: "end", s: 11, c: "bot" });
      L(g, 194, 100, 194, 142, "mut", { arrow: true }); T(g, 194, 160, "reverts: give up", { a: "middle", s: 12, c: "mut" });
      L(g, 324, 100, 324, 142, "mut", { arrow: true }); T(g, 324, 160, "no one gained: give up", { a: "middle", s: 12, c: "mut" });
      T(g, 20, 20, "the Dark Forest recipe, in four boxes", { s: 12, c: "mut" });
    });
  }
  function f5() {
    var s = fig("f5"); label(s, function (g) {
      R(g, 10, 14, 500, 56, "atk"); T(g, 22, 34, "the hacker's calldata", { s: 12, c: "atk", w: 600 });
      T(g, 22, 56, "recipient = 0x5f49…4a30   amount = 2,640.82 USDC", { s: 13, c: "ink" });
      L(g, 260, 72, 260, 100, "mut", { arrow: true }); T(g, 272, 91, "swap in the bot's address", { s: 12, c: "mut" });
      R(g, 10, 106, 500, 56, "bot"); T(g, 22, 126, "the bot's copy", { s: 12, c: "bot", w: 600 });
      T(g, 22, 148, "recipient = 0x6980…bdd0   amount = 1,998,046.875 USDC", { s: 13, c: "ink" });
      T(g, 10, 186, "if the contract checks  CALLER == 0x5f49…", { s: 12.5, c: "ink", strike: true });
      T(g, 10, 204, "a capable bot patches that comparison and redeploys", { s: 12, c: "mut" });
    });
  }
  function f6() {
    var s = fig("f6"); label(s, function (g) {
      var xs = [8, 178, 348], hd = ["before 2021", "Dec 2020 on", "since the Merge"], sub = [["outbid the", "gas price", "in public"], ["a bundle with a", "coinbase payment", "to the miner"], ["a bid to a", "builder for the", "whole block"]];
      xs.forEach(function (x, i) {
        R(g, x, 18, 164, 142, ["mut", "gold", "bld"][i]); T(g, x + 82, 42, hd[i], { a: "middle", c: "ink", w: 600 });
        T(g, x + 82, 72, sub[i].join("\n"), { a: "middle", s: 12.5, c: "ink" });
      });
      // small marks for each era
      var mk = BVH.svg("g", { transform: "translate(0,12)" }, g);
      for (var k = 0; k < 4; k++) BVH.svg("rect", { x: 30 + k * 26, y: 142 - 6 - k * 5, width: 14, height: 6 + k * 5, style: "fill:" + COL.mut }, mk);
      D(mk, 260, 128, 7, "bot"); C(mk, 250, 128, 3, "gold"); C(mk, 270, 128, 3, "gold");
      C(mk, 400, 130, 3, "bld"); C(mk, 416, 124, 3, "bld"); C(mk, 432, 116, 3, "bld"); C(mk, 448, 108, 4.5, "gold");
      T(g, 8, 188, "in every era the winner is whoever pays the block's producer most", { s: 12, c: "mut" });
    });
  }
  function f7() {
    var s = fig("f7"); label(s, function (g) {
      var x0 = 100, x1 = 500, t = function (sec) { return x0 + (sec + 4) / 8 * (x1 - x0); };
      var rows = ["searcher", "builders", "relay", "proposer"], ys = [48, 92, 132, 172];
      rows.forEach(function (r, i) { T(g, 6, ys[i] + 4, r, { s: 12.5, c: "ink" }); L(g, x0, ys[i], x1, ys[i], "line"); });
      for (var k = -4; k <= 4; k += 2) { L(g, t(k), 190, t(k), 194, "mut"); T(g, t(k), 208, (k > 0 ? "+" : "") + k + " s", { a: "middle", s: 11, c: "mut" }); }
      L(g, t(0), 26, t(0), 190, "mut", { dash: true }); T(g, t(0) + 4, 22, "slot starts", { s: 11, c: "mut" });
      L(g, t(4), 26, t(4), 190, "mut", { dash: true }); T(g, t(4) - 4, 22, "attest.", { a: "end", s: 11, c: "mut" });
      D(g, t(-1.5), ys[0], 6, "bot"); T(g, t(-1.5) + 9, ys[0] - 8, "bundle", { s: 11, c: "bot" });
      for (var j = 0; j < 12; j++) { var sec = -3.8 + j * .55; C(g, t(sec), ys[1], 2.2 + j * .35, "bld"); }
      C(g, t(2.0), ys[1], 6.2, "gold");
      C(g, t(1.0), ys[2], 4, "bld"); T(g, t(1.0), ys[2] + 17, "best bid forwarded", { a: "middle", s: 11, c: "mut" });
      C(g, t(2.2), ys[3], 4, "gold", { hollow: true }); T(g, t(2.2), ys[3] - 9, "header signed", { a: "middle", s: 11, c: "ink" });
      T(g, t(2.2), ys[3] + 17, "block published", { a: "middle", s: 11, c: "mut" });
    });
  }
  function f8() {
    var s = fig("f8"); label(s, function (g) {
      R(g, 170, 8, 180, 36, "gold"); T(g, 260, 30, "the bot holds the funds", { a: "middle", c: "ink", s: 12 });
      var xs = [6, 134, 262, 390], names = [["returned", "in full"], ["returned,", "bounty kept"], ["kept"], ["disputed", "or unknown"]], cols = ["bot", "bot", "atk", "mut"];
      xs.forEach(function (x, i) {
        R(g, x, 126, 122, 50, cols[i]); T(g, x + 61, names[i].length > 1 ? 147 : 156, names[i].join("\n"), { a: "middle", c: "ink", s: 12.5 });
        L(g, 260, 44, x + 61, 124, "mut", { arrow: true });
      });
      T(g, 6, 22, "negotiated, not decided\nby the protocol", { s: 12, c: "mut" });
      T(g, 6, 206, "bounties on offer are around 10%; often nothing is written down", { s: 12, c: "mut" });
    });
  }
  [f1, f2, f3, f4, f5, f6, f7, f8].forEach(function (f) { try { f(); } catch (e) { if (window.console) console.error(e); } });

  /* ---------- live bits: evolution, fates ---------- */
  BVH.json("data/evolution.json").then(function (E) {
    var m = E.measured; if (!m) return;
    var res = m.public + m.private;
    if (!res) return;
    $("#ev-vis").innerHTML = "of " + res + " exploit transactions we could classify since August 2023, " + m.private + " (" + Math.round(100 * m.private / res) + "%) were absent from the mempool archive even though most other transactions in their blocks were in it. <a class=\"raw\" href=\"evolution.html\">evolution</a>";
  }).catch(function () { /* default text stays */ });

  BVH.json("data/incidents.json").then(function (rows) {
    var heads = rows.filter(function (r) { return r.headline; });
    var k = { returned: 0, partial: 0, kept: 0, other: 0 };
    heads.forEach(function (r) { var f = r.fate_kind; if (k[f] != null) k[f]++; else k.other++; });
    $("#fates").innerHTML = "In the " + heads.length + " races counted as the bot beating the hacker: funds returned in " + k.returned + ", partly returned in " + k.partial + ", no return found in " + k.kept + ", unknown or not applicable in " + k.other + ". <a href=\"index.html#table\">See each row</a>.";
  }).catch(function () { $("#fates").textContent = ""; });

  /* ---------- Ronin: 61 words, 58 identical ---------- */
  BVH.json("data/explainer.json").then(function (X) {
    var box = $("#ronin");
    if (!X || !X.words_total) { box.textContent = "The calldata comparison file is missing."; return; }
    var diff = {}; X.diff_words.forEach(function (d) { diff[d.word] = d; });
    var known = {}; (X.first_11_words || []).forEach(function (d) { known[d.word] = d; });
    var h = '<div class="worddiff" role="img" aria-label="' + X.words_total + ' calldata words, ' + (X.words_total - X.words_different) + ' identical and ' + X.words_different + ' different">';
    for (var i = 0; i < X.words_total; i++) {
      var cls = diff[i] ? "w d" : "w", tt = diff[i] ? "word " + i + ": " + diff[i].field + " (changed)" : known[i] ? "word " + i + ": " + known[i].field + " (identical)" : "word " + i + " (identical)";
      h += '<div class="' + cls + '" title="' + esc(tt) + '">' + i + "</div>";
    }
    h += "</div>";
    h += '<p class="small mono muted"><b style="color:var(--ink)">' + (X.words_total - X.words_different) + " of " + X.words_total + "</b> 32-byte words are identical, including the whole array of 16 signatures. Calldata is " + X.calldata_bytes[0].toLocaleString("en-US") + " bytes in both transactions.</p>";
    h += '<div class="swap">';
    var left = "<b>the user's pending withdrawal</b><br>", right = "<b>Yoink's copy</b><br>";
    X.diff_words.forEach(function (d) {
      var qty = /quantity/i.test(d.field);
      var av = qty ? (X.attacker_quantity_usdc != null ? Number(X.attacker_quantity_usdc).toLocaleString("en-US", { maximumFractionDigits: 6 }) + " USDC" : d.attacker) : d.attacker;
      var yv = qty ? (X.yoink_quantity_usdc != null ? Number(X.yoink_quantity_usdc).toLocaleString("en-US", { maximumFractionDigits: 6 }) + " USDC" : d.yoink) : d.yoink;
      left += "word " + d.word + " " + esc(d.field) + "<br><em>" + esc(av) + "</em><br>";
      right += "word " + d.word + " " + esc(d.field) + "<br><em class=\"b\">" + esc(yv) + "</em><br>";
    });
    h += "<div>" + left + "</div><div>" + right + "</div></div>";
    var r = X.raw || {};
    h += '<p class="small muted mono">Sources: user transaction ' + BVH.short(X.attacker_tx, 10, 6) + BVH.rawA(r.user_tx, "tx") + BVH.rawA(r.user_receipt, "receipt") + BVH.rawA(r.user_trace, "trace") +
      " and Yoink transaction " + BVH.short(X.yoink_tx, 10, 6) + BVH.rawA(r.yoink_tx, "tx") + BVH.rawA(r.yoink_receipt, "receipt") + BVH.rawA(r.yoink_trace, "trace") +
      ' &nbsp; <a class="raw" href="downloads/yoink/ronin_calldata_diff.json">word-by-word diff</a> &nbsp; <a href="incident.html?slug=ronin-2024&amp;sub=Yoink">Ronin replay</a></p>';
    h += '<p class="small muted">Why 1,998,046.875 USDC? A local fork shows amounts up to 1,999,999.999999 USDC pay in full and 2,000,000 or more pay nothing. 1,998,046.875 is 2,000,000 x (1 - 2<sup>-10</sup>), which looks like a bisection result. That reading is an inference.</p>';
    box.innerHTML = h;
  }).catch(function (e) { BVH.loadError($("#ronin"), e); });

  /* ---------- bribe formula vs real blocks, and the refund round trip ---------- */
  var CASES = [
    { id: "ronin-2024--yoink", label: "Ronin bridge", v: "999", rule: "per-mille", input: "796.4115 ETH from WETH.withdraw", pred: 796.4114523868589 * 0.999 },
    { id: "kelp-rseth-2026", label: "Kelp rsETH", v: "999", rule: "per-mille", input: "18.95017 ETH", pred: 18.95017 * 0.999 },
    { id: "defiplaza-2024", label: "DeFi Plaza", v: "663,180,915", rule: "fixed: v x 1e11 wei", input: "n/a (fixed amount)", pred: 663180915e11 / 1e18 }
  ];
  Promise.all(CASES.map(function (c) { return BVH.json("data/incident/" + c.id + ".json").catch(function () { return null; }); })).then(function (ds) {
    var h = '<div style="overflow-x:auto"><table class="ops"><thead><tr><th>block</th><th>msg.value v</th><th>rule</th><th>profit input</th><th>formula gives</th><th>block shows</th></tr></thead><tbody>';
    var h2 = '<div style="overflow-x:auto"><table class="ops"><thead><tr><th>block</th><th>coinbase payments</th><th>refund to the bot</th><th>to the proposer</th><th>not accounted</th></tr></thead><tbody>';
    var any2 = false;
    CASES.forEach(function (c, i) {
      var D = ds[i]; if (!D) return;
      var f = D.flows || {}, raw = (D.block && D.block.raw) || {}, dl = D.auction && D.auction.raw && D.auction.raw.delivered;
      var shown = f.primary_coinbase_eth;
      h += "<tr><td><a href=\"incident.html?slug=" + encodeURIComponent(D.slug) + (D.sub ? "&amp;sub=" + encodeURIComponent(D.sub) : "") + '">' + esc(c.label) + "</a></td><td>" + c.v + "</td><td>" + esc(c.rule) + "</td><td>" + esc(c.input) + "</td><td>" + BVH.eth(c.pred) + "</td><td>" + (shown != null ? BVH.eth(shown) : "n/a") + BVH.rawA(raw.trace, "trace", "Block trace holding the coinbase transfer") + "</td></tr>";
      if (f.bot_coinbase_eth != null && f.proposer_eth != null) {
        any2 = true;
        var rest = f.bot_coinbase_eth - (f.refund_to_bot_eth || 0) - f.proposer_eth;
        h2 += "<tr><td><a href=\"incident.html?slug=" + encodeURIComponent(D.slug) + (D.sub ? "&amp;sub=" + encodeURIComponent(D.sub) : "") + '">' + esc(c.label) + "</a></td><td>" + BVH.eth(f.bot_coinbase_eth) + BVH.rawA(raw.trace, "trace") + "</td><td>" + (f.refund_to_bot_eth ? BVH.eth(f.refund_to_bot_eth) + BVH.rawA(raw.receipts, "receipts") : "none") + "</td><td>" + BVH.eth(f.proposer_eth) + BVH.rawA(dl, "relay") + "</td><td>" + (Math.abs(rest) < 0.0005 ? "0" : BVH.eth(rest)) + "</td></tr>";
      }
    });
    h += "</tbody></table></div><p class=\"small muted\">For Kelp the \"formula gives\" figure uses the 18.95017 ETH quoted in our analysis of the transaction; Ronin uses its WETH.withdraw amount. DeFi Plaza's v is at or above 1,000, so the amount is fixed rather than proportional.</p>";
    $("#bribes").innerHTML = h;
    h2 += "</tbody></table></div>";
    $("#refunds").innerHTML = any2 ? h2 + '<p class="small muted">A non-zero remainder is money the builder kept or paid elsewhere (Kelp), or a small excess because the proposer payment also carries fees from other transactions in the block (DeFi Plaza).</p>' : "";
  });
})();
