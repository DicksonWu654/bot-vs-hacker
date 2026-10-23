/* Part 2: How the bot works. Every figure is computed in the browser from site/data and the saved raw
   responses in site/raw; the Yoink calldata is decoded here from the raw transactions, using the grammar
   in the paper (section 5.2). Nothing animates on its own: the walk-through only moves when asked. */
(function () {
  "use strict";
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var esc = BVH.esc, rawA = BVH.rawA;
  BVH.chrome("explainer.html");

  /* ---------- small helpers ---------- */
  var FN = 0;
  function fn(url, title) { FN++; return '<sup class="fn">' + rawA(url, String(FN), title || "Saved source for this number") + "</sup>"; }
  function num(x, d) { return Number(x).toLocaleString("en-US", { maximumFractionDigits: d == null ? 2 : d, minimumFractionDigits: 0 }); }
  function fix(x, d) { return Number(x).toLocaleString("en-US", { maximumFractionDigits: d, minimumFractionDigits: d }); }
  function eth(x, d) { return fix(x, d == null ? 2 : d) + " ETH"; }
  function short(a) { a = String(a || ""); if (a.slice(0, 2) !== "0x") a = "0x" + a; return a.slice(0, 6) + "…" + a.slice(-4); }
  function settle(p) { return p.then(function (v) { return v; }, function () { return null; }); }
  function fail(el, e) { if (window.console) console.error(e); BVH.loadError(el, e); }
  function txOf(d, hash) {
    var r = (d && d.result) || d;
    if (r && r.transactions) { for (var i = 0; i < r.transactions.length; i++) if (r.transactions[i].hash === hash) return r.transactions[i]; return null; }
    return r;
  }
  function hexBytes(h) { h = h.replace(/^0x/, ""); var b = new Uint8Array(h.length / 2); for (var i = 0; i < b.length; i++) b[i] = parseInt(h.substr(i * 2, 2), 16); return b; }
  function hx(b, s, e) { var o = ""; for (var i = s; i < e; i++) o += (b[i] < 16 ? "0" : "") + b[i].toString(16); return o; }
  function big(b, s, e) { var h = hx(b, s, e); return h ? BigInt("0x" + h) : BigInt(0); }
  var WEI = BigInt("1000000000000000000");
  function weiStr(w, dp) { /* exact decimal string, dp decimals, truncated */
    var neg = w < 0; if (neg) w = -w;
    var i = w / WEI, f = (w % WEI).toString().padStart(18, "0").slice(0, dp);
    return (neg ? "-" : "") + Number(i).toLocaleString("en-US") + (dp ? "." + f : "");
  }

  /* ---------- names for public contracts and functions that appear on the tapes ---------- */
  var AB = {
    "64192819ac13ef72bf6b5ae239ac672b43a9af08": "Ronin bridge",
    "88e6a0c2ddd26feeb64f039a2c41296fcb3f5640": "Uniswap v3 USDC/WETH pool",
    "c02aaa39b223fe8d0a0e5c4f27ead9083c756cc2": "WETH",
    "10605ee48ff962952c966277a5d2dac0a0705cb1": "the attacker's executor",
    "ba12222222228d8ba445958a75a0704d566bf2c8": "Balancer vault",
    "a1290d69c65a6fe4df752f95823fae25cb99e5a7": "rsETH",
    "a0b86991c6218b36c1d19d4a2e9eb0ce3606eb48": "USDC", "dac17f958d2ee523a2206206994597c13d831ec7": "USDT",
    "6b175474e89094c44da98b954eedeac495271d0f": "DAI", "2260fac5e5542a773aa44fbcfedf7c193bc2c599": "WBTC",
    "514910771af9ca656af840dff83e8264ecf986ca": "LINK", "6b3595068778dd592e39a122f4f5a5cf09c90fe2": "SUSHI",
    "c00e94cb662c3520282e6f5717214004a7f26888": "COMP", "d533a949740bb3306d119cc777fa900ba034cd52": "CRV",
    "7fc66500c84a76ad7e9c93437bfc5ac33e2ddae9": "AAVE", "9f8f72aa9304c8b593d555f12ef6589cc3a579a2": "MKR",
    "7d1afa7b718fb893db30a3abc0cfc608aacfebb0": "MATIC", "0bc529c00c6401aef6d220be8c6ea1667f6ad93e": "YFI",
    "4e3fbd56cd56c3e72c1403e103b45db9da5b9d2b": "CVX", "090185f2135308bad17527004364ebcc2d37e5f6": "SPELL",
    "6980a47bee930a4584b09ee79ebe46484fbdbdd0": "Yoink's contract (gen 2)", "80bf7db69556d9521c03461978b8fc731dbbd4e4": "Yoink's contract (gen 3)"
  };
  var SEL = { "4d0d6673": "submitWithdrawal", "128acb08": "swap", "2e1a7d4d": "withdraw", "095ea7b3": "approve", "5c38449e": "flashLoan", "a9059cbb": "transfer", "882d6bfa": "function 0x882d6bfa" };
  function nameOf(a) { return AB[a] || short(a); }

  /* ---------- the executor grammar (paper 5.2) ---------- */
  var OPN = { 0: "CALL", 1: "CALL+VALUE", 2: "SWAP", 3: "SWAP", 4: "SWAP", 5: "SWAP", 6: "PAY_CB", 7: "NEXT_CB", 8: "SWEEP", 9: "UNWRAP", 10: "V4_SWAP", 11: "V4_SWAP" };
  var OPK = { 0: "call", 1: "call", 2: "swap", 3: "swap", 4: "swap", 5: "swap", 6: "cb", 7: "cb", 8: "sweep", 9: "unwrap", 10: "swap", 11: "swap" };
  function decode(b) {
    var p = 4, out = { sel: hx(b, 0, 4), stores: [], ops: [], size: b.length };
    out.x = big(b, p, p + 16); p += 16; out.f = b[p]; p += 1; if (out.f) p += 36; out.n = b[p]; p += 1; out.hdr = p;
    for (var s = 0; s < out.n; s++) {
      var key = hx(b, p, p + 4), st = p; p += 4; var tot = 4;
      for (;;) { var flag = b[p], ls = Number(big(b, p + 1, p + 5)), lr = Number(big(b, p + 5, p + 9)); p += 9 + ls + lr; tot += 9 + ls + lr; if (flag === 0xff) break; }
      out.stores.push({ key: key, start: st, len: tot });
    }
    while (p < b.length) {
      var op = b[p], st2 = p, o = { op: op, start: p, name: OPN[op], kind: OPK[op] }; p += 1;
      if (op === 0 || op === 1) {
        var L = Number(big(b, p, p + 3)); p += 3; o.to = hx(b, p, p + 20); p += 20;
        if (op === 1) { o.value = big(b, p, p + 16); p += 16; }
        o.dstart = p; o.dlen = L; o.sel = hx(b, p, p + 4); p += L;
      } else if (op >= 2 && op <= 5) { o.pool = hx(b, p, p + 20); o.token = hx(b, p + 20, p + 40); p += 72; }
      else if (op === 6) { o.token = hx(b, p, p + 20); p += 20; }
      else if (op === 7) { o.key = hx(b, p, p + 4); p += 4; }
      else if (op === 8) { o.token = hx(b, p, p + 20); p += 36; }
      else if (op === 9) { /* no operands */ }
      else if (op === 10 || op === 11) { p += 59; }
      else { o.name = "?"; o.kind = "cb"; p = b.length; }
      o.len = p - st2; out.ops.push(o);
    }
    return out;
  }
  function opWhat(o, b) {
    if (o.kind === "call") {
      var s = SEL[o.sel] || ("0x" + o.sel);
      if (o.sel === "2e1a7d4d") return "unwrap " + weiStr(big(b, o.dstart + 4, o.dstart + 36), 4) + " WETH into ETH at the WETH contract";
      if (o.sel === "095ea7b3") return "approve " + nameOf(o.to) + " for spending";
      if (o.sel === "128acb08") return "swap at the " + nameOf(o.to) + "; the pool's callback pays it";
      if (o.sel === "5c38449e") return "borrow a flash loan from the " + nameOf(o.to) + "; the stored scripts run inside its callback";
      return nameOf(o.to) + ": " + s;
    }
    if (o.op >= 2 && o.op <= 5) return "swap " + nameOf(o.token) + " in pool " + short(o.pool) + " (op " + o.op + ")";
    if (o.op === 8) return "sweep all " + nameOf(o.token) + " to the bot's vault";
    if (o.op === 9) return "turn the contract's WETH into ETH";
    if (o.op === 10 || o.op === 11) return "Uniswap v4 swap (gen 3 only)";
    if (o.op === 6) return "pay the pending callback in " + nameOf(o.token);
    if (o.op === 7) return "move on to the stored script for callback " + o.key;
    return "unknown operation";
  }

  /* ---------- load everything once ---------- */
  var D = {
    X: settle(BVH.json("data/explainer.json")),
    ronin: settle(BVH.json("data/incident/ronin-2024--yoink.json")),
    kelp: settle(BVH.json("data/incident/kelp-rseth-2026.json")),
    makina: settle(BVH.json("data/incident/makina-2026.json")),
    dfp: settle(BVH.json("data/incident/defiplaza-2024.json")),
    rows: settle(BVH.json("data/incidents.json")),
    fork: settle(BVH.json("downloads/yoink/fork_replay_results.json"))
  };
  var FORK_URL = "downloads/yoink/fork_replay_results.json";
  D.userTx = D.X.then(function (X) { return X ? settle(BVH.json(X.raw.user_tx)) : null; });
  D.yoinkTx = D.X.then(function (X) { return X ? settle(BVH.json(X.raw.yoink_tx)) : null; });
  var DFP_TX = "raw/rpc/eth_getTransactionByHash_0xa245deda8553c6e4c575baff9b50ef35abf4c8f990f8f36897696f896f240e3a.json";
  var KELP_HASH = "0x0e7680b06cb8a6f86c149d9ba90d98e3d334e7b072dde03909d43fcfd98a8705";
  D.kelpBlock = D.kelp.then(function (K) { return K ? settle(BVH.json(K.block.raw.block)) : null; });
  D.dfpTx = settle(BVH.json(DFP_TX));
  /* Ronin profit = the WETH amount Yoink's tape unwraps (exact, in wei) */
  D.ronProfit = D.yoinkTx.then(function (t) {
    var Y = txOf(t); if (!Y) return null;
    var yb = hexBytes(Y.input), w = decode(yb).ops.filter(function (o) { return o.sel === "2e1a7d4d"; })[0];
    return w ? big(yb, w.dstart + 4, w.dstart + 36) : null;
  });
  D.words = Promise.all([D.X, D.userTx, D.yoinkTx]).then(function (r) {
    var X = r[0], U = txOf(r[1]), Y = txOf(r[2]);
    if (!X || !U || !Y) return null;
    var ub = hexBytes(U.input), yb = hexBytes(Y.input), dec = decode(yb), first = dec.ops[0];
    var cb = yb.slice(first.dstart, first.dstart + first.dlen);
    var nW = Math.floor((ub.length - 4) / 32), uw = [], yw = [], diff = [];
    for (var i = 0; i < nW; i++) { uw.push(hx(ub, 4 + 32 * i, 36 + 32 * i)); yw.push(hx(cb, 4 + 32 * i, 36 + 32 * i)); if (uw[i] !== yw[i]) diff.push(i); }
    return { X: X, uw: uw, yw: yw, diff: diff, nW: nW };
  });
  function all(keys) { return Promise.all(keys.map(function (k) { return D[k]; })); }
  function ev(I, kind, utcPrefix) { var e = (I.events || []).filter(function (x) { return x.kind === kind && String(x.utc || "").indexOf(utcPrefix) === 0; }); return e[0] || null; }
  function mem(I, role) { var e = ((I.mempool || {}).entries || []).filter(function (x) { return x.role === role; }); return e; }

  /* shared derived numbers for the machine and the hero */
  var M = {};

  /* ---------- hero dek ---------- */
  all(["X", "ronin"]).then(function (r) {
    var X = r[0], R = r[1]; if (!X || !R) return;
    var seen = mem(R, "attacker")[0];
    var gap = seen ? (R.t0_ms - seen.t_ms) / 1000 : null;
    $("#dek").innerHTML = "On 6 August 2024 a user asked the Ronin bridge to pay out <span class=\"q\">" + num(X.attacker_quantity_usdc, 2) + " USDC</span>" + fn(X.raw.user_tx, "The user's withdrawal transaction") +
      ". " + (gap != null ? fix(gap, 1) + " seconds" : "Seconds") + " after that request first showed up in public" + (seen ? fn(seen.raw.sourcelog, "Mempool archive: first-seen times for the user's request") : "") +
      ", a bot called Yoink had copied it, changed <b>" + X.words_different + " of its " + X.words_total + " words</b>, and collected <span class=\"q\">" + num(X.yoink_quantity_usdc, 3) + " USDC</span>" + fn(X.raw.yoink_trace, "Trace of Yoink's copy") + " instead. This page takes that bot apart, one step at a time.";
  });

  /* ---------- hero figure: both requests as 61 word-bars ---------- */
  D.words.then(function (Wd) {
    var f = $("#hero-words"); if (!Wd) throw new Error("raw transactions missing");
    var X = Wd.X;
    function row(cls) { var o = '<div class="hw-row ' + cls + '" aria-hidden="true">'; for (var i = 0; i < Wd.nW; i++) o += '<i class="' + (Wd.diff.indexOf(i) >= 0 ? "d" : "") + '"></i>'; return o + "</div>"; }
    var mids = Wd.diff.map(function (w) { return '<span style="left:' + (100 * (w + 0.5) / Wd.nW) + '%">' + w + "</span>"; }).join("");
    f.innerHTML = '<div class="hw-l"><b>the user\'s request</b><span>' + num(X.attacker_quantity_usdc, 2) + " USDC" + rawA(X.raw.user_tx, "tx") + "</span></div>" + row("u") +
      '<div class="hw-mid" aria-hidden="true">' + mids + "</div>" + row("y") +
      '<div class="hw-l"><b>Yoink\'s copy</b><span>' + num(X.yoink_quantity_usdc, 3) + " USDC" + rawA(X.raw.yoink_tx, "tx") + "</span></div>" +
      "<figcaption>Each bar is one 32-byte word of the withdrawal request. " + (Wd.nW - Wd.diff.length) + " of " + Wd.nW + " are identical; words " + Wd.diff.join(", ").replace(/, (\d+)$/, " and $1") + ' were changed: the recipient, twice, and the amount. <a href="#copy">See every word</a></figcaption>';
  }).catch(function (e) { fail($("#hero-words"), e); });

  /* ======================================================================
     The machine: ten stations, a caption, play / step / show all.
     Default state is complete (every station filled in). Play is user-started.
     ====================================================================== */
  var ST = [
    { id: "watch", verb: "Watch" }, { id: "simulate", verb: "Simulate" }, { id: "copy", verb: "Copy and swap" }, { id: "wrap", verb: "Wrap in a program" },
    { id: "check", verb: "Check the profit" }, { id: "bribe", verb: "Set the bribe" }, { id: "bid", verb: "Bid for the block" }, { id: "first", verb: "Get in first" },
    { id: "payout", verb: "Pay out" }, { id: "return", verb: "Give it back" }
  ];
  var mach = $("#mach"), cap = $("#mach-cap"), cur = -1, timer = null;
  mach.innerHTML = ST.map(function (s, i) {
    return '<li id="st-' + s.id + '"><button type="button" data-i="' + i + '" aria-label="Step ' + (i + 1) + ": " + esc(s.verb) + '"><span class="dot"><i></i><b>' + (i + 1) + '</b></span><span class="verb">' + esc(s.verb) + '</span><span class="val" id="sv-' + s.id + '">…</span><span class="tm" id="st-t-' + s.id + '"></span></button></li>';
  }).join("");
  function setVal(id, v, t) { var e = $("#sv-" + id); if (e) e.textContent = v; if (t != null) { var f = $("#st-t-" + id); if (f) f.textContent = t; } }
  function capFor(i) {
    var s = ST[i]; if (!s) return "";
    return '<span class="k">Step ' + (i + 1) + " of 10: " + esc(s.verb) + "</span>" + (s.cap || "") + ' <a class="jump" href="#' + s.id + '">Read step ' + (i + 1) + "</a>";
  }
  function capAll() { return '<span class="k">All ten steps</span>' + (M.allCap || "Pick a step, or press play to walk through them in order.") ; }
  function render() {
    Array.prototype.forEach.call(mach.children, function (li, i) {
      li.className = cur < 0 ? "" : i < cur ? "" : i === cur ? "on" : "todo";
      li.querySelector("button").setAttribute("aria-current", i === cur ? "step" : "false");
    });
    cap.innerHTML = cur < 0 ? capAll() : capFor(cur);
    $("#m-prog").style.width = (cur < 0 ? 100 : (cur + 1) * 10) + "%";
    $("#m-prev").disabled = cur === 0; $("#m-next").disabled = cur === ST.length - 1;
  }
  function stop() { if (timer) { clearInterval(timer); timer = null; } $("#m-play").textContent = "Play"; $("#m-play").setAttribute("aria-pressed", "false"); }
  function go(i) { cur = Math.max(0, Math.min(ST.length - 1, i)); render(); }
  $("#m-play").addEventListener("click", function () {
    if (timer) { stop(); return; }
    if (cur < 0 || cur >= ST.length - 1) cur = -1;
    go(cur + 1);
    this.textContent = "Pause"; this.setAttribute("aria-pressed", "true");
    timer = setInterval(function () { if (cur >= ST.length - 1) { stop(); return; } go(cur + 1); }, 2600);
  });
  $("#m-prev").addEventListener("click", function () { stop(); go(cur < 0 ? ST.length - 1 : cur - 1); });
  $("#m-next").addEventListener("click", function () { stop(); go(cur < 0 ? 0 : cur + 1); });
  $("#m-all").addEventListener("click", function () { stop(); cur = -1; render(); });
  mach.addEventListener("click", function (e) { var b = e.target.closest("button[data-i]"); if (!b) return; stop(); go(+b.getAttribute("data-i")); });
  render();
  function capSet(id, html) { ST.forEach(function (s) { if (s.id === id) s.cap = html; }); render(); }

  /* ======================================================================
     Step 1: three things to watch
     ====================================================================== */
  all(["ronin", "kelp", "makina"]).then(function (r) {
    var R = r[0], K = r[1], Mk = r[2], box = $("#v-watch");
    if (!R || !K || !Mk) throw new Error("incident files missing");
    var seen = mem(R, "attacker")[0];
    var kAtk = mem(K, "attacker"), kBot = mem(K, "bot")[0];
    var mDeploy = (Mk.events || []).filter(function (e) { return e.kind === "deploy" && /attack contract/.test(e.detail); })[0];
    var mIdx = mDeploy && /idx (\d+)/.exec(mDeploy.detail || "");
    var mGap = mDeploy ? (Mk.block.ts_ms - Date.parse(mDeploy.utc)) / 1000 : null;
    function cell(cls, bn, txt) { return '<div class="wb ' + cls + '"><span class="bn">' + bn + '</span><span class="ev">' + txt + "</span></div>"; }
    var h = '<div class="vf"><div class="watch">';
    h += '<div class="wl"><div class="wl-h">Ronin bridge<span>Aug 2024, Yoink. The user\'s request was public before the copy landed.</span></div>' +
      cell("pend", "public mempool", "user's request first seen <b>" + (seen ? BVH.clock(seen.t_ms) : "n/a") + "</b>" + (seen ? BVH.memA(seen.raw) : "")) +
      cell("bot", "block " + R.block.number, "Yoink's copy, position " + R.bot_idx + rawA(R.block.raw.block, "block")) +
      cell("atk fail", "block " + R.atk_block, "the user's request, position " + R.atk_idx + ': <span class="x">fails</span>' + rawA(R.next_block.raw.receipts, "receipts")) + "</div>";
    h += '<div class="wl"><div class="wl-h">Kelp rsETH<span>Sep 2026, Yoink. The attacker\'s setup landed, then the copy, one block later.</span></div>' +
      cell("atk", "block " + (kAtk[0] ? kAtk[0].block : "?"), "attacker deploys its executor, position " + (kAtk[0] ? kAtk[0].idx : "?") + rawA("raw/rpc/block_" + (kAtk[0] && kAtk[0].block) + ".json", "block")) +
      cell("atk", "block " + (kAtk[1] ? kAtk[1].block : "?"), "attacker calls <code>prepare()</code>, position " + (kAtk[1] ? kAtk[1].idx : "?") + rawA("raw/rpc/block_" + (kAtk[1] && kAtk[1].block) + ".json", "block")) +
      cell("bot", "block " + (kBot ? kBot.block : K.block.number), "Yoink calls the attacker's executor first, position " + K.bot_idx + rawA(K.block.raw.block, "block")) + "</div>";
    h += '<div class="wl"><div class="wl-h">Makina<span>Jan 2026, a different searcher. The attack contract landed, then the copy, one block later.</span></div>' +
      cell("atk", "block " + (mDeploy ? mDeploy.block : "?"), "attacker deploys its attack contract" + (mIdx ? ", position " + mIdx[1] : "") + (mDeploy ? rawA(mDeploy.raw, "trace") : "")) +
      cell("bot", "block " + Mk.block.number + (mGap != null ? ", " + Math.round(mGap) + " s later" : ""), "a searcher runs the same plan, position " + Mk.bot_idx + rawA(Mk.block.raw.block, "block")) +
      cell("pend", "afterwards", "the attacker never calls its own contract" + rawA((Mk.incident_raw && Mk.incident_raw.attack_contract_txlist) || null)) + "</div>";
    var mkIr = Mk.incident_raw || {};
    h += "</div><p class=\"cap\">Amber is the bot, red the attacker or the user it copied. The archive covers both days, but none of these Kelp or Makina transactions appear in it before their blocks (Makina" + rawA(mkIr.mempool_dumpster_day, "day rows", "Rows cut from the 20 Jan 2026 archive file for the cited transactions: none matched") + rawA(mkIr.mempool_dumpster_index || (Mk.mempool && Mk.mempool.coverage_raw), "index", "The archive's January 2026 index, listing that day's file") +
      "; Kelp" + rawA("data/incident/kelp-rseth-2026.json", "our lookup", "Our lookup: each cited Kelp transaction marked not seen") + rawA(K.mempool.coverage_raw || (kAtk[0] && kAtk[0].raw.index), "index", "The archive's September 2026 index, listing that day's file") +
      "). So those bots probably acted on what had landed on chain, unless every archive source missed the transactions. Makina is the race in <a href=\"race.html\">Part 1</a>.</p></div>";
    box.innerHTML = h;
    setVal("watch", "request seen in public", seen ? BVH.clock(seen.t_ms) + " UTC" : "");
    capSet("watch", "The user's withdrawal request reached the public mempool, where any node can read it. The archive's sources first saw it at " + (seen ? BVH.clock(seen.t_ms) : "n/a") + " UTC.");
  }).catch(function (e) { fail($("#v-watch"), e); });

  /* ======================================================================
     Step 2: simulate (our own local replays, published in downloads/yoink)
     ====================================================================== */
  all(["fork", "X"]).then(function (r) {
    var F = r[0], X = r[1], box = $("#v-simulate");
    if (!F) throw new Error("fork_replay_results.json missing");
    var B = F.B_substituted_user_calldata || {}, C = F.C_quantity_probe || {};
    var h = '<div class="vf"><h3>Test 1: change the recipient. Does the request still pay?</h3>';
    h += '<div class="forkrow"><div class="fk"><span class="who">the user\'s request, ' + (B.address_words_substituted || 2) + ' recipient words swapped</span>withdraw <b>' + num(B.user_original_qty_usdc, 6) + ' USDC</b> to a <b>new recipient</b></div><div class="arrow" aria-hidden="true">→</div><div class="fk ok"><span class="who">result</span>still pays: <b>' + num(B.recipient_usdc_received, 6) + " USDC</b> to the new recipient" + rawA(FORK_URL, "replay") + "</div></div>";
    h += '<p class="cap">Fork of block ' + F.fork_block + ", run on our machine, nothing broadcast. Any bot must learn the same thing in its own simulation before it copies.</p></div>";
    var probe = Object.keys(C).map(function (k) {
      var m = /([\d,]+(?:\.\d+)?)/.exec(k.replace(/^(user|yoink)_qty_/, ""));
      var ask = /^user/.test(k) && B.user_original_qty_usdc != null ? B.user_original_qty_usdc : (m ? parseFloat(m[1].replace(/,/g, "")) : NaN);
      return { k: k, ask: ask, got: C[k].recipient_usdc_received, who: /^user/.test(k) ? "the user's amount" : /^yoink/.test(k) ? "Yoink's amount" : "" };
    }).filter(function (p) { return !isNaN(p.ask); }).sort(function (a, b) { return a.ask - b.ask; });
    var mx = Math.max.apply(null, probe.map(function (p) { return Math.max(p.ask, p.got); }).filter(function (v) { return v <= 2.5e6; }).concat([2e6]));
    h += '<div class="vf"><h3>Test 2: how much will it pay? Asked for, then paid out, in USDC</h3><div class="probe">';
    probe.forEach(function (p) {
      var big2 = p.ask > 2.5e6, z = p.got === 0;
      h += '<div class="pr' + (z ? " zero" : "") + '"><span class="lab">ask ' + num(p.ask, 6) + (p.who ? "<span>" + p.who + "</span>" : "") + '</span><span class="trk" role="img" aria-label="paid ' + num(p.got, 6) + ' USDC"><i class="' + (z ? "zero" : "") + '" style="width:' + (z ? 0 : Math.max(0.3, Math.min(100, 100 * p.got / mx))) + '%"></i></span><span class="val">' + (z ? "paid 0" : "paid " + num(p.got, 6)) + "" + "</span></div>";
    });
    h += '</div><p class="cap">The tested amounts below 2,000,000 USDC paid in full; tested amounts at or above it succeeded but paid nothing. Yoink asked for 1,998,046.875, which is 2,000,000 x (1 - 2<sup>-10</sup>): it looks like the result of a search for the largest amount that pays <span class="note-inf">inferred</span>' + rawA(FORK_URL, "replays") + "</p></div>";
    box.innerHTML = h;
    setVal("simulate", "copy still pays");
    capSet("simulate", "Run on a private copy of the chain with the recipient changed, the request pays the new recipient. Swap in another recipient and it still pays, and every tested amount below 2,000,000 USDC paid in full.");
  }).catch(function (e) { fail($("#v-simulate"), e); });

  /* ======================================================================
     Step 3: the word-level calldata diff, read from both raw transactions
     ====================================================================== */
  var PLAIN = { 0: "withdrawal number", 1: "kind (1 = withdrawal)", 2: "recipient on Ethereum", 3: "token on Ethereum (USDC)", 4: "Ethereum chain id", 5: "recipient address on Ronin", 6: "token on Ronin", 7: "Ronin chain id", 8: "token standard", 9: "token id", 10: "amount", 11: "where the signature list starts", 12: "number of signatures" };
  function wordName(i) { if (PLAIN[i]) return PLAIN[i]; var k = i - 13; return "signature " + (Math.floor(k / 3) + 1) + ", part " + ["v", "r", "s"][k % 3]; }
  all(["words", "makina"]).then(function (r) {
    var Wd = r[0], Mk = r[1], box = $("#v-copy");
    if (!Wd) throw new Error("raw transactions missing");
    var X = Wd.X, uw = Wd.uw, yw = Wd.yw, diff = Wd.diff, nW = Wd.nW;
    var same = nW - diff.length;
    M.diff = diff; M.nW = nW;
    function cellsFor(a, b) { var s = ""; for (var j = a; j <= b; j++) s += '<button type="button" class="wcell' + (diff.indexOf(j) >= 0 ? " d" : "") + '" data-w="' + j + '" aria-label="word ' + j + ": " + esc(wordName(j)) + (diff.indexOf(j) >= 0 ? ", changed" : ", identical") + '">' + j + "</button>"; return s; }
    var h = '<div class="vf"><div class="wd-top"><div class="big">' + same + " of " + nW + "<small>32-byte words identical" + rawA(X.raw.user_tx, "user tx") + rawA(X.raw.yoink_tx, "Yoink tx") + "</small></div></div>";
    h += '<div class="wd-groups"><div class="wdg"><div class="wdg-l">the receipt, words 0 to 10</div><div class="wdg-c">' + cellsFor(0, 10) + '</div></div><div class="wdg"><div class="wdg-l">list, 11 and 12</div><div class="wdg-c">' + cellsFor(11, 12) + '</div></div><div class="wdg sig"><div class="wdg-l">16 validator signatures, words 13 to ' + (nW - 1) + '</div><div class="wdg-c">' + cellsFor(13, nW - 1) + "</div></div></div>";
    h += '<div class="wd-key"><span><i></i>identical in both</span><span><i class="d"></i>changed by Yoink</span><span class="muted">select any word to compare it</span></div>';
    h += '<div class="opdetail" id="wd-detail" aria-live="polite" style="margin-top:14px"></div>';
    h += '<div class="dcards">';
    function marks(a, b, cls) { var o = ""; for (var k = 0; k < a.length; k++) o += a[k] !== b[k] ? '<mark class="' + cls + '">' + a[k] + "</mark>" : a[k]; return o.replace(/<\/mark><mark class="[^"]*">/g, ""); }
    diff.forEach(function (w) {
      var isAmt = w === 10, ua = "0x" + uw[w].slice(24), ya = "0x" + yw[w].slice(24);
      var hu = isAmt ? num(X.attacker_quantity_usdc, 6) + " USDC" : short(ua) + " (the user)";
      var hy = isAmt ? num(X.yoink_quantity_usdc, 3) + " USDC" : short(ya) + " (Yoink's contract)";
      h += '<div class="dc"><div class="dc-h">Word ' + w + ": " + esc(wordName(w)) + "<span>" + esc((X.diff_words.filter(function (d) { return d.word === w; })[0] || {}).field || "") + '</span></div><div class="dc-row"><span class="who">user</span><span><span class="hm">' + hu + '</span><br><span class="hx">' + marks(uw[w], yw[w], "") + '</span></span><span class="who">Yoink</span><span><span class="hm b">' + hy + '</span><br><span class="hx">' + marks(yw[w], uw[w], "b") + "</span></span></div></div>";
    });
    h += "</div>";
    var mk = Mk && /(\d[\d,]*) of (\d[\d,]*) non-zero bytes \((\d+)%\)/.exec((Mk.narrative || []).join(" "));
    var mTx = Mk && (Mk.events || []).filter(function (e) { return e.kind === "tx" && /position 0/.test(e.detail); })[0];
    h += '<p class="cap">The amount went from ' + num(X.attacker_quantity_usdc, 2) + " to " + num(X.yoink_quantity_usdc, 3) + " USDC, and the request is " + num(X.calldata_bytes[0]) + " bytes in both. " +
      (mk ? "Copies are not always this literal: at Makina, " + mk[3] + "% of the searcher's non-zero calldata bytes (" + mk[1] + " of " + mk[2] + ") appear in the attacker's contract code" + rawA(Mk.incident_raw && Mk.incident_raw.copy_tx, "bot tx", "The searcher's transaction, with its calldata") + rawA(Mk.incident_raw && Mk.incident_raw.attack_contract_code, "attacker code", "The attacker contract's runtime code") + rawA("data/incident/makina-2026.json", "count", "Derived: our byte-overlap count, in the race's narrative") + ", and it wrapped its own flash loans around them" + (mTx ? rawA(mTx.raw, "trace") : "") + "." : "") + "</p></div>";
    box.innerHTML = h;
    var det = $("#wd-detail");
    function show(w) {
      Array.prototype.forEach.call(box.querySelectorAll(".wcell"), function (c) { c.classList.toggle("sel", +c.getAttribute("data-w") === w); });
      var d = diff.indexOf(w) >= 0;
      det.innerHTML = "<b>Word " + w + ": " + esc(wordName(w)) + "</b> " + (d ? '<span style="color:var(--bot)">changed</span>' : "identical") + "<br>user&nbsp; " + uw[w] + "<br>Yoink " + yw[w];
    }
    box.querySelector(".wd-groups").addEventListener("click", function (e) { var c = e.target.closest(".wcell"); if (c) show(+c.getAttribute("data-w")); });
    box.querySelector(".wd-groups").addEventListener("focusin", function (e) { var c = e.target.closest(".wcell"); if (c) show(+c.getAttribute("data-w")); });
    show(diff[0] != null ? diff[0] : 0);
    setVal("copy", diff.length + " of " + nW + " words changed");
    capSet("copy", "Yoink copied the request and changed " + diff.length + " of its " + nW + " words: both recipient addresses became its own contract and the amount rose from " + num(X.attacker_quantity_usdc, 2) + " to " + num(X.yoink_quantity_usdc, 3) + " USDC.");
  }).catch(function (e) { fail($("#v-copy"), e); });

  /* ======================================================================
     Step 4: the instruction tape (Ronin / Kelp / DeFi Plaza)
     ====================================================================== */
  var TAPES = [
    { id: "ronin", label: "Ronin, Aug 2024", load: function () { return all(["yoinkTx", "X"]).then(function (r) { return { tx: txOf(r[0]), raw: r[1].raw.yoink_tx, copied: 0, after: "copied request", note: "The first operation is the user's request with three words changed. The other two sell the USDC for WETH and unwrap it." }; }); } },
    { id: "kelp", label: "Kelp rsETH, Sep 2026", load: function () { return all(["kelpBlock", "kelp"]).then(function (r) { return { tx: txOf(r[0], KELP_HASH), raw: r[1].block.raw.block, copied: 0, after: "call into the attacker's prepared executor", note: "Nothing is copied word for word here: the first operation calls the attacker's own prepared executor. Part of the rsETH is sold for ETH on Uniswap v4 and the rest is swept to the vault." }; }); } },
    { id: "dfp", label: "DeFi Plaza, Jul 2024", load: function () { return D.dfpTx.then(function (t) { return { tx: txOf(t), raw: DFP_TX, copied: -1, note: "A long one: approvals, then a Balancer flash loan whose callback runs the two stored scripts, then swaps of everything taken, an unwrap, and six sweeps to the vault." }; }); } }
  ];
  var tapeCache = {};
  function tapeSegs(dec) {
    var segs = [{ kind: "hdr", oc: "hdr", name: "header", what: "header: minimum profit x = " + dec.x.toString() + " wei, " + dec.n + " stored script" + (dec.n === 1 ? "" : "s"), len: dec.hdr, start: 0 }];
    dec.stores.forEach(function (s) { segs.push({ kind: "store", oc: "store", name: "stored script", what: "a script stored for callback " + s.key + ", run when that callback re-enters the contract (" + num(s.len) + " bytes)", len: s.len, start: s.start }); });
    var i = 0;
    while (i < dec.ops.length) {
      var o = dec.ops[i], j = i + 1;
      while (j < dec.ops.length && dec.ops[j].op === o.op && dec.ops[j].sel === o.sel && (o.kind !== "call" || o.sel === "095ea7b3") && dec.ops[j].kind === o.kind) j++;
      var n = j - i, len = 0; for (var k = i; k < j; k++) len += dec.ops[k].len;
      segs.push({ kind: o.kind, oc: (o.op < 16 ? "0" : "") + o.op.toString(16), name: o.name, n: n, ops: dec.ops.slice(i, j), len: len, start: o.start, idx: i });
      i = j;
    }
    return segs;
  }
  function renderTape(cfg, data) {
    var host = $("#tape-host"), tx = data.tx; if (!tx) { host.innerHTML = '<div class="callout bad">This transaction is missing from the saved block.</div>'; return; }
    var b = hexBytes(tx.input), dec = decode(b), segs = tapeSegs(dec), v = BigInt(tx.value);
    var opsN = dec.ops.length, kinds = {};
    dec.ops.forEach(function (o) { kinds[o.kind] = (kinds[o.kind] || 0) + 1; });
    var h = '<p class="grammar" aria-label="Input layout"><span>selector ' + dec.sel + "</span><em>+</em><span>header</span><em>+</em>" + (dec.n ? "<span>" + dec.n + " stored script" + (dec.n > 1 ? "s" : "") + "</span><em>+</em>" : "") + "<span>" + opsN + " operations</span><em>=</em><span>" + num(dec.size) + " bytes</span>" + rawA(data.raw, "raw tx") + "</p>";
    if (data.note) h += '<p class="tape-note">' + esc(data.note) + "</p>";
    h += '<div class="tape" role="list" aria-label="Decoded operations, in order">';
    segs.forEach(function (s, si) {
      var w = Math.round(Math.min(340, 46 + 7 * Math.sqrt(s.len)));
      var label = s.ops ? (s.n > 1 ? opWhat(s.ops[0], b).replace(/^approve .*/, "make " + s.n + " approval calls") : opWhat(s.ops[0], b)) : s.what;
      var short1 = s.ops ? (s.ops[0].kind === "call" ? (SEL[s.ops[0].sel] || "0x" + s.ops[0].sel) + (s.n > 1 ? "" : " · " + nameOf(s.ops[0].to)) : s.ops[0].kind === "sweep" ? nameOf(s.ops[0].token) : s.ops[0].op >= 2 && s.ops[0].op <= 5 ? nameOf(s.ops[0].token) : "") : (s.kind === "store" ? "callback " + (dec.stores[si - 1] || {}).key : "x = " + dec.x.toString());
      var copied = s.ops && s.idx === data.copied && s.n === 1;
      h += '<button type="button" role="listitem" class="seg k-' + s.kind + (copied ? " copied" : "") + (s.n > 1 ? " grp" : "") + '" data-s="' + si + '" style="--w:' + w + 'px"' + (s.n > 1 ? ' data-n="×' + s.n + '"' : "") + ' aria-label="' + esc((s.n > 1 ? s.n + " × " : "") + (s.name || "") + ": " + label) + '">' +
        '<span class="oc">' + (s.kind === "hdr" || s.kind === "store" ? s.oc : "op " + s.oc) + '</span><span class="on">' + esc(s.name) + '</span><span class="ot">' + esc(short1.replace(" · ", " ")) + '</span><span class="hb" aria-hidden="true">' + hx(b, s.start, Math.min(s.start + s.len, s.start + 10)).replace(/(..)/g, "$1 ") + '</span><span class="ob">' + num(s.len) + " B</span></button>";
    });
    var vv = Number(v);
    h += '<div class="tape-end" role="listitem">then the contract itself: profit check, and a bribe to the block\'s builder set by the call\'s value, <b>' + num(vv) + "</b> (" + (vv < 1000 ? vv + " thousandths of the profit" : "fixed: " + weiStr(v * BigInt(1e11), 7) + " ETH") + ")</div></div>";
    h += '<div class="opdetail" id="op-detail" aria-live="polite"></div>';
    h += '<ol class="oplist">';
    segs.forEach(function (s, si) {
      if (!s.ops) return;
      var copied = s.idx === data.copied && s.n === 1;
      h += '<li class="' + (copied ? "copied" : "") + '"><span class="i">' + (s.idx + 1) + (s.n > 1 ? "–" + (s.idx + s.n) : "") + '</span><span class="n">' + esc(s.name) + (s.n > 1 ? " ×" + s.n : "") + '</span><span class="w">' + esc(s.n > 1 && s.ops[0].sel === "095ea7b3" ? "make " + s.n + " approval calls for the swaps that follow" : s.n > 1 ? s.ops.map(function (o) { return opWhat(o, b).replace(/^sweep all (\S+) to the bot's vault$/, "$1"); }).join(", ").replace(/^(.*)$/, s.ops[0].op === 8 ? "sweep $1 to the vault" : "$1") : opWhat(s.ops[0], b)) + (copied ? " <b>(" + esc(data.after) + ")</b>" : "") + '</span><span class="b">' + num(s.len) + " B</span></li>";
    });
    h += "</ol>";
    host.innerHTML = h;
    var det = $("#op-detail");
    function show(si) {
      var s = segs[si]; Array.prototype.forEach.call(host.querySelectorAll(".seg"), function (e) { e.classList.toggle("sel", +e.getAttribute("data-s") === si); });
      var bytes = hx(b, s.start, Math.min(s.start + s.len, s.start + 40)).replace(/(..)/g, "$1 ").trim();
      var desc = s.ops ? (s.n > 1 ? s.n + " operations: " + s.ops.map(function (o) { return opWhat(o, b); }).slice(0, 4).join("; ") + (s.n > 4 ? "; …" : "") : opWhat(s.ops[0], b)) : s.what;
      det.innerHTML = "<b>" + esc((s.n > 1 ? s.n + " × " : "") + s.name) + "</b>, bytes " + num(s.start) + " to " + num(s.start + s.len - 1) + ": " + esc(desc) + '<br><span class="muted">' + bytes + (s.len > 40 ? " …" : "") + "</span>";
    }
    host.querySelector(".tape").addEventListener("click", function (e) { var s = e.target.closest(".seg"); if (s) show(+s.getAttribute("data-s")); });
    host.querySelector(".tape").addEventListener("focusin", function (e) { var s = e.target.closest(".seg"); if (s) show(+s.getAttribute("data-s")); });
    show(Math.max(0, segs.findIndex(function (s) { return s.ops && s.idx === (data.copied < 0 ? 0 : data.copied); })));
    return dec;
  }
  (function () {
    var box = $("#v-wrap");
    var h = '<div class="vf"><div class="tabs" role="tablist" aria-label="Pick a race">' + TAPES.map(function (t, i) { return '<button type="button" role="tab" id="tt-' + t.id + '" aria-selected="' + (i === 0) + '" aria-controls="tape-host" data-t="' + t.id + '">' + esc(t.label) + "</button>"; }).join("") + "</div>";
    h += '<div id="tape-host" role="tabpanel"><p class="loading">Decoding…</p></div>';
    h += '<p class="cap">Decoded in your browser from the saved raw transaction with the grammar in the paper (section 5.2): one byte names the operation, then its operands. Red is the copied call, blue the swaps, gold the unwrap, amber the sweeps to the vault. All 17,783 gen 2 and gen 3 inputs we checked parse this way to the exact byte (8,148 and 9,635 main-entry inputs' + rawA("downloads/yoink/corpus_stats.json", "counts", "Parser coverage per contract generation: txs_main and parse_exact") + ', <a href="paper.html#5-anatomy-of-a-front-runner-yoink">paper section 5</a>); the three tapes here are examples. The names of swap ops 2 to 5 are ours <span class="note-inf">inferred</span>.</p></div>';
    box.innerHTML = h;
    function pick(id) {
      Array.prototype.forEach.call(box.querySelectorAll("[role=tab]"), function (b) { b.setAttribute("aria-selected", b.getAttribute("data-t") === id ? "true" : "false"); });
      var cfg = TAPES.filter(function (t) { return t.id === id; })[0];
      (tapeCache[id] || (tapeCache[id] = cfg.load())).then(function (d) {
        var dec = renderTape(cfg, d);
        if (id === "ronin" && dec) {
          setVal("wrap", dec.ops.length + " calls, " + num(dec.size) + " bytes");
          capSet("wrap", "The copied request became the first of " + dec.ops.length + " operations on a " + num(dec.size) + "-byte tape: the bridge withdrawal, a swap of the USDC for WETH at Uniswap, then unwrapping the WETH into ETH.");
        }
      }).catch(function (e) { fail($("#tape-host"), e); });
    }
    box.querySelector(".tabs").addEventListener("click", function (e) { var b = e.target.closest("[data-t]"); if (b) pick(b.getAttribute("data-t")); });
    box.querySelector(".tabs").addEventListener("keydown", function (e) {
      if (e.key !== "ArrowRight" && e.key !== "ArrowLeft") return;
      var tabs = Array.prototype.slice.call(box.querySelectorAll("[role=tab]")), i = tabs.indexOf(document.activeElement);
      var n = tabs[(i + (e.key === "ArrowRight" ? 1 : tabs.length - 1)) % tabs.length]; n.focus(); pick(n.getAttribute("data-t"));
    });
    pick("ronin");
  })();

  /* ======================================================================
     Step 5: profit check, from the decoded header (x) and the real profit
     ====================================================================== */
  all(["yoinkTx", "kelpBlock", "kelp", "X"]).then(function (r) {
    var Y = txOf(r[0]), KT = txOf(r[1], KELP_HASH), K = r[2], X = r[3], box = $("#v-check");
    if (!Y) throw new Error("Yoink transaction missing");
    var yb = hexBytes(Y.input), dec = decode(yb), w = dec.ops.filter(function (o) { return o.sel === "2e1a7d4d"; })[0];
    var profit = w ? big(yb, w.dstart + 4, w.dstart + 36) : null;
    M.profitWei = profit;
    var pe = profit != null ? Number(weiStr(profit, 6).replace(/,/g, "")) : null;
    var kdec = KT ? decode(hexBytes(KT.input)) : null;
    var h = '<div class="vf"><h3>Ronin: balance of Yoink\'s contract during the transaction</h3><div class="gauge">';
    h += '<div class="gr"><span class="l">before (S0)</span><span class="gtrk"><i style="width:4%"></i></span></div>';
    h += '<div class="gr"><span class="l">after (S1)</span><span class="gtrk"><i style="width:4%"></i><i class="gain" style="left:4%;width:94%"></i><span class="t">+' + (pe != null ? eth(pe, 2) : "?") + '</span><span class="x" style="left:4%"><span>x = ' + dec.x.toString() + "</span></span></span></div></div>";
    h += '<div class="verdict"><div class="vd ok"><b>Profit at least x: carry on</b>profit = S1 - S0 = ' + (profit != null ? weiStr(profit, 6) : "?") + " ETH, from unwrapping the WETH" + rawA(X.raw.yoink_tx, "tx") + '</div><div class="vd bad"><b>Below x: revert "poor"</b>everything the transaction did is undone; if it was included, only its gas is spent</div></div>';
    h += '<div class="hdrx"><div><b>x = ' + dec.x.toString() + " wei</b>Ronin's minimum profit, read from its header" + rawA(X.raw.yoink_tx, "tx") + "</div>" + (kdec ? "<div><b>x = " + kdec.x.toString() + " wei</b>Kelp's minimum profit" + rawA(K.block.raw.block, "block") + "</div>" : "") + '<div><b>S0, S1</b>are the contract\'s own ETH balance; the snapshot is taken by the contract itself</div></div>';
    h += '<p class="cap">Schematic bar lengths; the gain is real. The rule, recovered from the contract code and tested on a local copy: <code>require(S1 &gt;= S0 + x) else revert "poor"</code>' + rawA("downloads/yoink/blackbox_results.json", "tests") + "</p></div>";
    box.innerHTML = h;
    if (pe != null) { setVal("check", "+" + eth(pe, 2) + " ≥ x = " + dec.x.toString()); capSet("check", "The contract measured its gain, " + eth(pe, 2) + ", against the minimum in the header, x = " + dec.x.toString() + " wei. Had it been smaller, everything the transaction did would have been undone, at the cost of its gas."); }
  }).catch(function (e) { fail($("#v-check"), e); });

  /* ======================================================================
     Step 6: the bribe calculator (documented per-mille rule, BigInt exact)
     ====================================================================== */
  all(["yoinkTx", "ronin", "kelp", "dfp", "rows", "dfpTx", "X"]).then(function (r) {
    var Y = txOf(r[0]), R = r[1], K = r[2], DP = r[3], rows = r[4] || [], DT = txOf(r[5]), X = r[6], box = $("#v-bribe");
    var time = rows.filter(function (x) { return x.id === "time-2023"; })[0], dfr = rows.filter(function (x) { return x.id === "defiplaza-2024"; })[0];
    var yb = Y && hexBytes(Y.input), w = Y && decode(yb).ops.filter(function (o) { return o.sel === "2e1a7d4d"; })[0];
    var rProfit = w ? big(yb, w.dstart + 4, w.dstart + 36) : null;
    var kProfit = K && /funded by the ([\d.]+) ETH swap proceeds/.exec(K.dataset_money.note || "");
    function toWei(x) { var s = String(x).split("."), f = (s[1] || "").padEnd(18, "0").slice(0, 18); return BigInt(s[0]) * WEI + BigInt(f); }
    var P = [
      rProfit && { id: "ronin", label: "Ronin", v: Number(BigInt(Y.value)), x: BigInt(0), profit: rProfit, shown: R.dataset_money.coinbase_eth, raw: R.block.raw.trace, dp: 9, note: "profit = the WETH it unwrapped" },
      kProfit && { id: "kelp", label: "Kelp rsETH", v: 999, x: BigInt(1), profit: toWei(kProfit[1]), shown: K.dataset_money.coinbase_eth, raw: K.block.raw.trace, dp: 5, note: "profit = the ETH from selling part of the rsETH, as rounded in our data" },
      DT && dfr && { id: "dfp", label: "DeFi Plaza", v: Number(BigInt(DT.value)), x: BigInt(0), profit: toWei(dfr.gross_eth), shown: DP.dataset_money.coinbase_eth, raw: DP.block.raw.trace, dp: 7, note: "a fixed amount, so the profit does not matter" },
      time && { id: "time", label: "TIME", v: 55, x: BigInt(0), profit: toWei(time.gross_eth), shown: time.coinbase_eth, raw: time.raw.trace, dp: 9, note: "profit = the take" }
    ].filter(Boolean);
    var st = { profit: P[0] ? P[0].profit : toWei("1"), v: P[0] ? P[0].v : 999, x: BigInt(0), preset: P[0] && P[0].id };
    function bribe(profit, v, x) {
      if (profit < x) return { revert: true };
      if (v === 0) return { b: BigInt(0), line: 1 };
      if (v < 1000) { var b = profit * BigInt(v) / BigInt(1000); if (b > profit - x) return { b: (profit - x) / BigInt(2), line: 3 }; return { b: b, line: 2 }; }
      return { b: BigInt(v) * BigInt(1e11), line: 4 };
    }
    var h = '<div class="vf"><div class="calc"><div class="ctl">';
    h += '<div class="fld"><span>Real transactions</span><div class="presets" id="pre">' + P.map(function (p) { return '<button type="button" class="xbtn" data-p="' + p.id + '" aria-pressed="false">' + esc(p.label) + "</button>"; }).join("") + "</div></div>";
    h += '<label class="fld"><span class="row">profit (ETH)<output id="o-p"></output></span><input type="range" id="i-p" min="0" max="1000" step="1" aria-label="Profit in ETH, slider"><input type="number" id="n-p" min="0" step="any" aria-label="Profit in ETH"></label>';
    h += '<label class="fld"><span class="row">value of the call, v<output id="o-v"></output></span><input type="range" id="i-v" min="0" max="1000" step="1" aria-label="Value v, 0 to 999 per mille, 1,000 means fixed"><input type="number" id="n-v" min="0" step="1" aria-label="Value v"></label>';
    h += '<label class="fld"><span class="row">minimum profit x (ETH)<output id="o-x"></output></span><input type="number" id="n-x" min="0" step="any" value="0" aria-label="Minimum profit x in ETH"></label>';
    h += '</div><div class="res"><div class="nums"><div><span class="sw" style="background:var(--bld)"></span>to the block builder<b id="r-b"></b></div><div><span class="sw" style="background:var(--bot)"></span>left for the bot<b id="r-k"></b></div></div><div class="split" id="r-bar" role="img"><i class="bb"></i><i class="kk"></i></div>';
    h += '</div><div class="rule" id="rule" aria-label="The rule"><div><span>if profit &lt; x</span><span>revert "poor"</span></div><div><span>if v = 0</span><span>no payment</span></div><div><span>if v &lt; 1,000</span><span>bribe = profit × v / 1,000</span></div><div class="sub"><span>and if bribe &gt; profit − x</span><span>bribe = (profit − x) / 2 instead</span></div><div><span>if v ≥ 1,000</span><span>bribe = v × 0.0000001 ETH, fixed</span></div></div>';
    h += '<div class="match" id="r-m" aria-live="polite"></div></div>';
    h += '<p class="cap">The rule was recovered from the contract code and checked with local tests' + rawA("downloads/yoink/blackbox_results.json", "tests") + '; on the real transactions it reproduces the payment to the builder exactly. "Left for the bot" is before any builder refund, which comes in step 9.</p></div>';
    box.innerHTML = h;
    var ip = $("#i-p"), np = $("#n-p"), iv = $("#i-v"), nv = $("#n-v"), nx = $("#n-x");
    function pEth() { return Number(weiStr(st.profit, 6).replace(/,/g, "")); }
    function upd(src) {
      var pe = pEth();
      if (src !== "ip") ip.value = Math.min(1000, Math.round(pe));
      if (src !== "np") np.value = weiStr(st.profit, 6).replace(/,/g, "");
      if (src !== "iv") iv.value = Math.min(1000, st.v);
      if (src !== "nv") nv.value = st.v;
      $("#o-p").textContent = weiStr(st.profit, 4) + " ETH";
      $("#o-v").textContent = st.v < 1000 ? num(st.v) + " = " + (st.v / 10).toFixed(1) + "%" : num(st.v) + " (fixed)";
      $("#o-x").textContent = weiStr(st.x, 4) + " ETH";
      var r2 = bribe(st.profit, st.v, st.x), rows2 = box.querySelectorAll("#rule div");
      Array.prototype.forEach.call(rows2, function (d, i) { d.className = (r2.revert ? i === 0 : i === r2.line) ? "hit" : ""; });
      var bar = $("#r-bar");
      if (r2.revert) {
        $("#r-b").textContent = "0 ETH"; $("#r-k").textContent = "reverts";
        bar.innerHTML = '<i class="rv" style="flex:1 1 100%"></i>'; bar.setAttribute("aria-label", "The transaction reverts with poor");
      } else {
        var kept = st.profit - r2.b, tot = Number(st.profit) || 1;
        $("#r-b").textContent = weiStr(r2.b, 4) + " ETH"; $("#r-k").textContent = weiStr(kept, 4) + " ETH";
        var fb = Math.max(0, Number(r2.b) / tot), fk = Math.max(0, Number(kept) / tot);
        bar.innerHTML = (fb > 0 ? '<i class="bb" style="flex:' + fb + ' 1 0"></i>' : "") + (fk > 0 ? '<i class="kk" style="flex:' + fk + ' 1 0"></i>' : "");
        bar.setAttribute("aria-label", "Builder gets " + weiStr(r2.b, 6) + " ETH, bot keeps " + weiStr(kept, 6) + " ETH");
      }
      var p = P.filter(function (q) { return q.id === st.preset; })[0];
      Array.prototype.forEach.call(box.querySelectorAll("#pre button"), function (b) { b.setAttribute("aria-pressed", b.getAttribute("data-p") === st.preset ? "true" : "false"); });
      $("#r-m").innerHTML = p ? "<b>" + esc(p.label) + "</b>: v = " + num(p.v) + ", " + esc(p.note) + ". The rule gives " + (r2.revert ? "a revert" : "<b>" + weiStr(r2.b, p.dp) + " ETH</b>") + "; the block shows <b>" + fix(p.shown, p.dp) + " ETH</b> paid to the builder" + rawA(p.raw, "trace") + " (to " + p.dp + " decimals)." : "Your own numbers. Pick a real transaction to compare with the chain.";
      if (p && p.id === "ronin" && !r2.revert) { setVal("bribe", "v = " + p.v + ": " + eth(Number(weiStr(r2.b, 6).replace(/,/g, "")), 2)); capSet("bribe", "The call's value was " + p.v + ", so " + (p.v / 10).toFixed(1) + "% of the profit, " + weiStr(r2.b, 6) + " ETH, went to the block's builder. The chain shows exactly that payment."); }
    }
    function preset(id) { var p = P.filter(function (q) { return q.id === id; })[0]; if (!p) return; st.profit = p.profit; st.v = p.v; st.x = p.x; nx.value = weiStr(p.x, 18).replace(/,/g, "").replace(/\.?0+$/, "") || "0"; st.preset = id; upd(); }
    box.querySelector("#pre").addEventListener("click", function (e) { var b = e.target.closest("[data-p]"); if (b) preset(b.getAttribute("data-p")); });
    ip.addEventListener("input", function () { st.profit = BigInt(ip.value) * WEI; st.preset = null; upd("ip"); });
    np.addEventListener("input", function () { var v = parseFloat(np.value); if (!isNaN(v) && v >= 0) { st.profit = toWei(np.value.indexOf("e") >= 0 ? v.toFixed(6) : np.value); st.preset = null; upd("np"); } });
    iv.addEventListener("input", function () { st.v = +iv.value; st.preset = null; upd("iv"); });
    nv.addEventListener("input", function () { var v = parseInt(nv.value, 10); if (!isNaN(v) && v >= 0) { st.v = v; st.preset = null; upd("nv"); } });
    nx.addEventListener("input", function () { var v = parseFloat(nx.value); if (!isNaN(v) && v >= 0) { st.x = toWei(nx.value.indexOf("e") >= 0 ? v.toFixed(18) : nx.value); st.preset = null; upd(); } });
    if (P[0]) preset(P[0].id); else upd();
  }).catch(function (e) { fail($("#v-bribe"), e); });

  /* ======================================================================
     Step 7: the bid chart (linear ETH axis, seconds from slot start)
     ====================================================================== */
  var bidState = null;
  function drawBids() {
    if (!bidState) return;
    var R = bidState.R, host = $("#bid-svg"); if (!host) return;
    var A = R.auction, S = A.bids.series, names = A.bids.builders, wname = A.winner.builder, wi = names.indexOf(wname);
    var seen = mem(R, "attacker")[0], seenT = seen ? seen.rel_ms : null;
    var W = Math.max(300, host.clientWidth || 600), narrow = W < 560;
    var padL = narrow ? 40 : 52, padR = narrow ? 12 : 120, top = 26, H1 = narrow ? 230 : 280, gap = 44, H2 = narrow ? 90 : 100, H = top + H1 + gap + H2 + 34;
    var t0 = Math.min(-7.2, (seenT || 0) / 1000 - 0.4), t1 = 0.6;
    var x = BVH.lin(t0, t1, padL, W - padR);
    var yMax = Math.ceil((A.winner.eth || 12) / 2) * 2 + (narrow ? 2 : 0), y = BVH.lin(0, yMax, top + H1, top);
    var zMax = 1.2, yz = BVH.lin(0, zMax, top + H1 + gap + H2, top + H1 + gap);
    host.innerHTML = "";
    var svg = BVH.svg("svg", { viewBox: "0 0 " + W + " " + H, role: "img", "aria-label": "Bids for block " + R.block.number + ": " + S.length + " bids. " + wname + " bid from " + (S.filter(function (s) { return s[2] === wi; })[0] || [0, 0])[1] + " ETH up to the winning " + A.winner.eth + " ETH; best rival bid " + A.runner_up.eth + " ETH." }, host);
    var g = BVH.svg("g", null, svg);
    // grid + axes, main
    for (var v = 0; v <= yMax; v += 2) { BVH.svg("line", { x1: padL, x2: W - padR, y1: y(v), y2: y(v), class: "gl" }, g); BVH.svg("text", { x: padL - 8, y: y(v) + 4, "text-anchor": "end", class: "ann2" }, g, v); }
    BVH.svg("text", { x: padL - 8, y: top - 12, "text-anchor": "end", class: "ann2" }, g, "ETH");
    // zoom band
    BVH.svg("rect", { x: padL, y: top + H1 + gap, width: W - padR - padL, height: H2, class: "band", rx: 3 }, g);
    [0, 0.5, 1].forEach(function (v2) { BVH.svg("line", { x1: padL, x2: W - padR, y1: yz(v2), y2: yz(v2), class: "gl" }, g); BVH.svg("text", { x: padL - 8, y: yz(v2) + 4, "text-anchor": "end", class: "ann2" }, g, v2); });
    BVH.svg("text", { x: padL, y: top + H1 + gap - 10, class: "ann2" }, g, "zoom: 0 to " + zMax + " ETH, the rival bids");
    // x ticks
    for (var s = Math.ceil(t0); s <= 0; s++) {
      if (narrow && s % 2) continue;
      BVH.svg("line", { x1: x(s), x2: x(s), y1: top + H1, y2: top + H1 + 4, stroke: "var(--line2)" }, g);
      BVH.svg("text", { x: x(s), y: top + H1 + gap + H2 + 18, "text-anchor": "middle", class: "ann2" }, g, (s > 0 ? "+" : s < 0 ? "−" : "") + Math.abs(s) + " s");
    }
    // event lines
    if (seenT != null) {
      BVH.svg("line", { x1: x(seenT / 1000), x2: x(seenT / 1000), y1: top - 6, y2: top + H1 + gap + H2, class: "seen" }, g);
      BVH.svg("text", { x: x(seenT / 1000) + 5, y: top + 6, class: "ann" }, g, "user's request");
      BVH.svg("text", { x: x(seenT / 1000) + 5, y: top + 20, class: "ann2" }, g, "first seen " + BVH.sec(seenT, true));
    }
    BVH.svg("line", { x1: x(0), x2: x(0), y1: top - 6, y2: top + H1 + gap + H2, class: "vl" }, g);
    BVH.svg("text", { x: x(0) - 5, y: top + H1 + gap + H2 + 18, "text-anchor": "end", class: "ann2" }, g, "");
    BVH.svg("text", { x: x(0) + (narrow ? -5 : 5), y: top + 6, "text-anchor": narrow ? "end" : "start", class: "ann" }, g, "slot starts");
    BVH.svg("text", { x: x(0) + (narrow ? -5 : 5), y: top + 20, "text-anchor": narrow ? "end" : "start", class: "ann2" }, g, BVH.clock(R.t0_ms, false) + " UTC");
    // dots
    var own = [], riv = [];
    S.forEach(function (b) { (b[2] === wi ? own : riv).push(b); });
    riv.forEach(function (b) {
      BVH.svg("circle", { cx: x(b[0] / 1000), cy: y(b[1]), r: 3, class: "riv" }, g);
      BVH.svg("circle", { cx: x(b[0] / 1000), cy: yz(Math.min(zMax, b[1])), r: 3.2, class: "riv" }, g);
    });
    // own steps as a staircase
    var steps = [], last = -1;
    own.forEach(function (b) { if (b[1] !== last) { steps.push(b); last = b[1]; } });
    var pth = "";
    steps.forEach(function (b, i) { var X1 = x(b[0] / 1000), Y1 = y(b[1]); pth += (i ? "H" + X1 + "V" + Y1 : "M" + X1 + "," + Y1); });
    /* light columns from zero up to each of the winning builder's bids (linear ETH), then its staircase as the amber streak */
    own.forEach(function (b) { var hh = y(0) - y(b[1]); if (hh > 1.5) BVH.svg("rect", { x: x(b[0] / 1000) - 0.75, y: y(b[1]), width: 1.5, height: hh, class: "col-a" }, g); });
    if (pth) BVH.svg("path", { d: pth + "H" + x(own[own.length - 1][0] / 1000), class: "streak glow", fill: "none" }, g);
    var gOwn = BVH.svg("g", { class: "glow-s" }, g);
    own.forEach(function (b) { BVH.svg("circle", { cx: x(b[0] / 1000), cy: y(b[1]), r: 4, class: "own" }, gOwn); });
    var win = own[own.length - 1];
    if (win) { BVH.svg("circle", { cx: x(win[0] / 1000), cy: y(win[1]), r: 12, class: "win-halo" }, g); BVH.svg("circle", { cx: x(win[0] / 1000), cy: y(win[1]), r: 7, class: "win glow-s" }, g); }
    // labels on the steps
    steps.forEach(function (b, i) {
      var isW = i === steps.length - 1, lx = x(b[0] / 1000);
      var txt = isW ? fix(b[1], 2) + " ETH wins" : fix(b[1], 2);
      if (narrow && !isW && i > 0) return;
      var t = BVH.svg("text", { x: isW && !narrow ? x(own[own.length - 1][0] / 1000) + 12 : lx - 8, y: y(b[1]) + (isW ? 4 : -8), "text-anchor": isW && !narrow ? "start" : "end", class: isW ? "ann" : "ann2" }, g, txt);
      if (isW) t.setAttribute("font-weight", "600");
    });
    // rival annotation
    var ru = A.runner_up;
    if (ru && ru.t_ms != null) {
      BVH.svg("text", { x: x(ru.t_ms / 1000), y: y(ru.eth) - 10, "text-anchor": "middle", class: "ann2" }, g, "best rival " + fix(ru.eth, 2));
    }
    // hit targets with tooltips
    S.forEach(function (b) {
      var c = BVH.svg("circle", { cx: x(b[0] / 1000), cy: b[1] > zMax ? y(b[1]) : yz(b[1]), r: 9, class: "hit", tabindex: -1 }, g);
      BVH.tipFor(c, function () { return "<b>" + esc(names[b[2]] || "unknown") + "</b><br>" + fix(b[1], 5) + " ETH at " + BVH.sec(b[0], true) + "<br>" + b[4] + " transactions in the block"; });
    });
  }
  D.ronin.then(function (R) {
    var box = $("#v-bid");
    if (!R || !R.auction || !R.auction.bids) throw new Error("bid data missing");
    var A = R.auction, rc = R.reaction || {};
    var h = '<div class="vf bidc"><h3>Bids for block ' + R.block.number + " (" + A.bids.n_total + " bids from " + A.n_builders + " builders in the saved relay data)" + BVH.bidsA(A) + "</h3>";
    h += '<div id="bid-svg"></div>';
    h += '<div class="bid-legend"><span><i style="background:var(--bot)"></i>' + esc(A.winner.builder) + ' (the builder our data ties to Yoink)</span><span><i style="background:var(--gold)"></i>winning bid</span><span><i style="background:var(--mist)"></i>other builders</span></div>';
    h += '<div class="bstats"><div><b>' + BVH.sec(rc.delay_ms) + "</b>from the user's request first seen" + BVH.memA((mem(R, "attacker")[0] || {}).raw) + " to Yoink's builder's first big bid" + BVH.bidsA(A, "Relay bid file: the builder's first big bid and its arrival time") + "</div><div><b>" + fix(A.winner.eth, 2) + " ETH</b>winning bid, paid to the proposer" + rawA(A.raw.delivered, "relay") + "</div><div><b>" + fix(A.runner_up.eth, 2) + " ETH</b>best rival bid, from " + esc(A.runner_up.builder) + BVH.bidsA(A) + "</div></div>";
    h += '<p class="cap">Linear scale. Seconds are relative to the start of the slot (the block\'s timestamp). The builder raised its bid in steps, ' + (function () { var l = -1, o = []; A.bids.series.forEach(function (b) { if (b[2] === A.bids.builders.indexOf(A.winner.builder) && b[1] !== l) { o.push(fix(b[1], 2)); l = b[1]; } }); return o.join(" → "); })() + " ETH, ending far above any rival. Who decides those steps is not visible on chain.</p></div>";
    box.innerHTML = h;
    bidState = { R: R }; drawBids();
    var rt; window.addEventListener("resize", function () { clearTimeout(rt); rt = setTimeout(drawBids, 120); });
    setVal("bid", fix(A.winner.eth, 2) + " ETH winning bid", rc.t_ms != null ? "first big bid " + BVH.clock(R.t0_ms + rc.t_ms) : "");
    capSet("bid", "Yoink's builder first bid big " + BVH.sec(rc.delay_ms) + " after the request was first seen, then raised its bid in steps to " + fix(A.winner.eth, 2) + " ETH. The best rival bid was " + fix(A.runner_up.eth, 2) + " ETH.");
  }).catch(function (e) { fail($("#v-bid"), e); });

  /* ======================================================================
     Step 8: positions in the two blocks
     ====================================================================== */
  all(["ronin", "rows"]).then(function (r) {
    var R = r[0], rows = r[1] || [], box = $("#v-first");
    var strip = R.strip || [], n = R.block.ntx, nb = R.next_block || {}, nn = nb.ntx || 0;
    var nbot = strip.filter(function (s) { return s[2] === "bot"; }).length;
    var h = '<div class="vf"><div class="blk"><div class="blk-h"><b>Block ' + R.block.number + "</b><span>" + n + " transactions, " + BVH.clock(R.t0_ms, false) + " UTC" + rawA(R.block.raw.block, "block") + "</span></div>";
    h += '<div class="cells n24" role="img" aria-label="Block ' + R.block.number + ": position " + R.bot_idx + " is Yoink's copy; " + nbot + " of " + n + ' transactions are Yoink\'s; the last two are the builder\'s payments">';
    for (var i = 0; i < n; i++) { var s = strip[i] || [], cls = s[2] === "bot" ? (i === R.bot_idx ? "copy" : "bot") : s[2] === "builder" ? "bld" : ""; h += '<i class="' + cls + '" title="position ' + i + '"></i>'; }
    h += '</div><div class="cellnote"><span>position 0</span><span>' + (n - 1) + "</span></div></div>";
    h += '<div class="blk"><div class="blk-h"><b>Block ' + nb.number + "</b><span>" + nn + " transactions, 12 s later" + rawA(nb.raw && nb.raw.block, "block") + rawA(nb.raw && nb.raw.receipts, "receipts") + "</span></div>";
    h += '<div class="cells dense" role="img" aria-label="Block ' + nb.number + ": the user\'s own request at position " + R.atk_idx + ' fails">';
    for (var j = 0; j < nn; j++) h += '<i class="' + (j === R.atk_idx ? "atk" : "") + '"></i>';
    h += '</div><div class="cellnote"><span>position 0</span><span>' + (nn - 1) + "</span></div></div>";
    h += '<div class="poskey"><span><i class="copy"></i>Yoink\'s copy, position ' + R.bot_idx + '</span><span><i class="bot"></i>Yoink\'s other ' + (nbot - 1) + ' transactions</span><span><i class="bld"></i>builder pays the refund, then the proposer</span><span><i class="atk"></i>the user\'s request, position ' + R.atk_idx + ", fails</span></div>";
    var yo = rows.filter(function (x) { return /Yoink/.test(x.bot || "") && x.headline && x.bot_idx != null; });
    if (yo.length) {
      h += '<h3 style="margin-top:20px">Where Yoink landed in its other headline races</h3><div class="pos-strip">' + yo.map(function (x) { return '<a href="incident.html?slug=' + encodeURIComponent(x.slug) + (x.sub ? "&amp;sub=" + encodeURIComponent(x.sub) : "") + '"><b>' + esc(x.title) + "</b>position " + x.bot_idx + ", block " + x.block + "</a>"; }).join("") + "</div>";
    }
    h += '<p class="cap">Position 0 of the block is the top of the line. The failed request reverted with error ' + "<code>0x4f13df61</code>, which we read as \"withdrawal already used\".</p></div>";
    box.innerHTML = h;
    setVal("first", "position " + R.bot_idx + ", block " + R.block.number, BVH.clock(R.t0_ms, false) + " UTC");
    capSet("first", "Yoink's copy ran at position " + R.bot_idx + " of block " + R.block.number + ". The user's own request landed 12 seconds later at position " + R.atk_idx + " of the next block, and failed.");
  }).catch(function (e) { fail($("#v-first"), e); });

  /* ======================================================================
     Step 9: where the money went inside the block
     ====================================================================== */
  all(["ronin", "kelp", "X", "fork", "ronProfit"]).then(function (r) {
    var R = r[0], K = r[1], X = r[2], F = r[3], box = $("#v-payout");
    var f = R.flows, dm = R.dataset_money, raw = R.block.raw;
    var gross = r[4] != null ? Number(weiStr(r[4], 6).replace(/,/g, "")) : null;
    var max = Math.max(f.bot_coinbase_eth, gross || 0);
    function hop(cls, ft, amt, v, url, lbl) { return '<div class="hop ' + cls + '"><div class="ft">' + ft + '</div><div class="am"><span class="bar">' + (amt != null ? '<i style="width:' + Math.max(0.4, 100 * amt / max) + '%"></i>' : "") + '</span><span class="v">' + v + (url ? rawA(url, lbl || "raw") : "") + "</span></div></div>"; }
    var ref = (f.payouts || [])[0] || {};
    var h = '<div class="vf"><div class="ledger"><div class="lg-sec">Inside Yoink\'s transaction (position ' + R.bot_idx + ")</div>";
    h += hop("k-usd", "<b>Ronin bridge</b><span class=\"ar\">→</span>Yoink's contract", null, num(X.yoink_quantity_usdc, 3) + " USDC", X.raw.yoink_trace, "trace");
    h += hop("", "<b>USDC → WETH → ETH</b> at the Uniswap pool, then unwrapped", gross, gross ? eth(gross, 2) : "n/a", X.raw.yoink_tx, "tx");
    h += hop("k-bld", "Yoink's contract<span class=\"ar\">→</span><b>block builder</b> (the bribe, 999 thousandths)", dm.coinbase_eth, eth(dm.coinbase_eth, 3), raw.trace, "trace");
    if (F && F.A_yoink_replay) h += hop("k-bot", "left in Yoink's contract", F.A_yoink_replay.bot_eth_delta, eth(F.A_yoink_replay.bot_eth_delta, 3), FORK_URL, "replay");
    h += '<div class="lg-sec">Later in the same block</div>';
    h += hop("k-bld", "all " + f.n_bot_txs + " of Yoink's transactions<span class=\"ar\">→</span><b>builder</b>", f.bot_coinbase_eth, eth(f.bot_coinbase_eth, 2), raw.trace, "trace");
    h += hop("k-bot", "builder<span class=\"ar\">→</span><b>Yoink's contract</b> (refund, position " + (ref.i != null ? ref.i : "?") + ")", f.refund_to_bot_eth, eth(f.refund_to_bot_eth, 2), raw.block, "block");
    h += hop("k-prop", "builder<span class=\"ar\">→</span><b>proposer</b> (the winning bid, position " + (R.txs.filter(function (t) { return t.h === f.proposer_payment_tx; }).map(function (t) { return t.i; })[0] != null ? R.txs.filter(function (t) { return t.h === f.proposer_payment_tx; })[0].i : (R.block.ntx - 1)) + ")", f.proposer_eth, eth(f.proposer_eth, 2), R.auction.raw.delivered, "relay");
    h += "</div>";
    var net = dm.coinbase_eth - dm.builder_refund_eth;
    h += '<div class="netbox"><div><b>' + eth(net, 2) + "</b>net cost of going first for this transaction: the bribe minus the refund. The refund covered all " + f.n_bot_txs + " of Yoink's transactions; our data credits it to this one" + rawA(raw.trace, "bribe", "Block trace: the coinbase transfer from Yoink's transaction") + rawA(raw.block, "refund", "The block: the builder's refund transaction and its value") + "</div><div><b>" + eth(f.proposer_eth, 2) + "</b>what the proposer received for the whole block, equal to the relay's delivered value" + rawA(R.auction.raw.delivered, "relay") + "</div></div>";
    if (K && K.flows) { var kf = K.flows; h += '<p class="cap"><b>Kelp, for contrast:</b> no refund. Yoink\'s ' + kf.n_bot_txs + " transactions in that block paid the builder " + eth(kf.bot_coinbase_eth, 2) + ", " + eth(kf.primary_coinbase_eth, 2) + " of it from the copy" + rawA(K.block.raw.trace, "trace") + ". For the whole block, the builder paid the proposer " + eth(kf.proposer_eth, 2) + rawA(K.auction.raw.delivered, "relay") + (kf.payout_other_eth > 0 ? ", sent " + fix(kf.payout_other_eth, 6) + " ETH to another address" : "") + " and kept " + eth(kf.builder_kept_eth, 2) + ".</p>"; }
    h += "</div>";
    box.innerHTML = h;
    setVal("payout", eth(dm.coinbase_eth, 2) + " to builder");
    capSet("payout", "Yoink paid the builder " + eth(dm.coinbase_eth, 2) + ". Later in the block the builder refunded " + eth(f.refund_to_bot_eth, 2) + " to Yoink's contract and paid the proposer " + eth(f.proposer_eth, 2) + ".");
  }).catch(function (e) { fail($("#v-payout"), e); });

  /* ======================================================================
     Step 10: the return, the full split, and Yoink's record
     ====================================================================== */
  /* the whole split from the shared money fields (BVH.moneySplit), not rebuilt from rounded percentages */
  function split(row) {
    var s = BVH.moneySplit(row);
    if (!s.priced) return null;
    if (s.mixed) return { g: s.gross, take: s.gross, ret: s.known && s.known.returned != null ? s.known.returned : null, bld: null, kept: null, unk: null, oth: 0, ok: false, s: s };
    var v = {}; s.parts.forEach(function (p) { v[p.k] = (v[p.k] || 0) + p.eth; });
    return { g: s.total, take: s.gross, ret: v.ret != null ? v.ret : null, bld: v.bld || 0, kept: v.bot != null ? v.bot : null, unk: v.unk || 0, oth: v.oth || 0, ok: true, s: s };
  }
  function splitBar(sp) {
    if (!sp.ok) return '<span class="ms-bar"><i class="c-unk" style="flex:1 1 0"></i></span>';
    var parts = [["c-ret", sp.ret], ["c-bld", sp.bld], ["c-kept", sp.kept], ["c-unk", sp.unk], ["c-oth", sp.oth]];
    return '<span class="ms-bar" role="img" aria-label="' + parts.filter(function (p) { return p[1]; }).map(function (p) { return { "c-ret": "returned", "c-bld": "to builder and proposer", "c-kept": "kept by the bot", "c-unk": "unknown", "c-oth": "gas and other costs" }[p[0]] + " " + BVH.eth(p[1]); }).join(", ") + '">' + parts.map(function (p) { return p[1] ? '<i class="' + p[0] + '" style="flex:' + (p[1] / sp.g) + ' 1 0"></i>' : ""; }).join("") + "</span>";
  }
  all(["ronin", "rows", "kelp"]).then(function (r) {
    var R = r[0], rows = r[1] || [], K = r[2], box = $("#v-return");
    var kBack = K && ev(K, "return", "2026-09-16T10:38");
    var kHours = K && /about ([\d.]+) hours/.exec((K.fate && K.fate.text) || "");
    var land = ev(R, "block", "2024-08-06T10:11:47"), out = ev(R, "return", "2024-08-06T10:29"), msg = ev(R, "message", "2024-08-06T10:53"), back = ev(R, "return", "2024-08-06T17:05");
    var outAmt = out && /\(([\d,.]+) ETH\)/.exec(out.detail), backAmt = back && /([\d,.]+) ETH to Safe/.exec(back.detail), quote = msg && /'([^']+)'/.exec(msg.detail);
    var h = '<div class="vf"><h3>Ronin, 6 August 2024 (UTC)</h3><ol class="rt">';
    h += '<li class="bot"><span class="tt">' + (land ? land.utc.slice(11, 19) : "10:11:47") + "</span>Yoink's copy lands and takes the USDC" + (land ? rawA(land.raw, "block") : "") + "</li>";
    if (out) h += '<li class="bot"><span class="tt">' + out.utc.slice(11, 19) + "</span>Yoink moves " + (outAmt ? outAmt[1] : "800") + " ETH out of its contract to a new address, before any contact from Ronin" + rawA(out.raw, "txs") + "</li>";
    if (msg) h += '<li class="msg"><span class="tt">' + msg.utc.slice(11, 19) + "</span>Ronin's first on-chain message to Yoink" + rawA(msg.raw, "txs") + (quote ? "<q>" + esc(quote[1]) + "</q>" : "") + "</li>";
    if (back) h += '<li class="ret"><span class="tt">' + back.utc.slice(11, 19) + "</span><b>" + (backAmt ? backAmt[1] : "?") + " ETH</b> reaches a Ronin Safe" + rawA(back.raw, "txs") + "</li>";
    h += "</ol></div>";
    // full split for Ronin and Kelp
    var rr = rows.filter(function (x) { return x.id === "ronin-2024--yoink"; })[0], kk = rows.filter(function (x) { return x.id === "kelp-rseth-2026"; })[0];
    function msRow(row, title, one) {
      var sp = split(row); if (!sp) return "";
      var o = '<div class="ms-row"><div class="ms-h">' + esc(title) + "<span>take " + BVH.eth(sp.take) + rawA(row.raw && row.raw.trace, "trace") + "</span></div>" + splitBar(sp) + '<div class="ms-key">';
      o += '<div><i class="c-ret"></i><span>returned to the victim</span><span class="v">' + BVH.eth(sp.ret) + " (" + BVH.pct(100 * sp.ret / sp.g) + ")</span></div>";
      o += '<div><i class="c-bld"></i><span>paid for position: to builder and proposer, after refunds</span><span class="v">' + BVH.eth(sp.bld) + "</span></div>";
      o += '<div><i class="c-kept"></i><span>kept by the bot</span><span class="v">' + (sp.kept != null ? BVH.eth(sp.kept) : "unknown") + "</span></div>";
      if (sp.oth > 0) o += '<div><i class="c-oth"></i><span>gas and other costs</span><span class="v">' + BVH.eth(sp.oth) + "</span></div>";
      o += "</div>" + (sp.s && sp.s.note ? '<p class="ms-one">' + esc(sp.s.note) + "</p>" : "");
      return o + '<p class="ms-one">' + one + "</p></div>";
    }
    h += '<div class="vf msplit"><h3>Where the whole take went</h3>';
    if (rr) h += msRow(rr, "Ronin, Yoink's copy", "Almost everything came back. The rest was the bot's net payment to the block builder for going first, and a sliver it kept.");
    if (kk) h += msRow(kk, "Kelp rsETH", "Yoink sold part of the rsETH to pay the builder, then sent everything its vault received on to an address our race data lists as a signer of the drained Safe" + (kHours ? ", about " + kHours[1] + " hours later" : "") + (kBack ? rawA(kBack.raw, "transfers") : "") + ".");
    h += '<p class="cap">Values in ETH; Kelp is rsETH valued at the in-transaction swap rate. Returned share and refunds from the race files' + rawA("data/incidents.json", "incidents.json") + ".</p></div>";
    // Yoink's record
    var yo = rows.filter(function (x) { return /Yoink/.test(x.bot || "") && x.fate_kind !== "n-a" && x.loot_scope === "bot-tx" && x.gross_eth != null; }).sort(function (a, b) { return a.date < b.date ? -1 : 1; });
    var skipped = rows.filter(function (x) { return /Yoink/.test(x.bot || "") && x.fate_kind !== "n-a" && x.loot_scope !== "bot-tx"; }).length;
    var nRet = 0, nKept = 0;
    h += '<div class="vf rec"><h3>Yoink\'s record: ' + yo.length + " single-transaction races in our data</h3>";
    h += '<div class="rec-key"><span><i class="c-ret"></i>returned</span><span><i class="c-bld"></i>to builder and proposer</span><span><i class="c-kept"></i>kept by the bot</span><span><i class="c-unk"></i>unknown</span><span><i class="c-oth"></i>gas and other costs</span></div>';
    yo.forEach(function (x) {
      var sp = split(x), o;
      if (x.fate_kind === "kept") { nKept++; o = '<span class="o kept">no return found</span>'; }
      else if (sp && sp.ret == null) o = '<span class="o">return not split by race</span>';
      else if (sp && !sp.ok) { nRet++; o = '<span class="o">mixed assets; see race</span>'; }
      else { nRet++; o = '<span class="o">' + BVH.pct(x.returned_pct) + " returned</span>"; }
      h += '<div class="rec-row"><span><a href="incident.html?slug=' + encodeURIComponent(x.slug) + (x.sub ? "&amp;sub=" + encodeURIComponent(x.sub) : "") + '">' + esc(x.title) + '</a><span class="d">' + esc(x.date) + ", take " + BVH.eth(x.gross_eth) + "</span></span>" + (sp ? splitBar(sp) : "<span></span>") + o + "</div>";
    });
    h += '<p class="cap">Bars are each race\'s whole take. ' + (skipped ? skipped + " campaign-level rows that cover several transactions are left out here. " : "") + "Where the return is shared across races or measured in other tokens, the bar is hatched and the race page has the detail.</p></div>";
    box.innerHTML = h;
    var spR = rr && split(rr);
    setVal("return", backAmt ? backAmt[1] + " ETH back" : "returned", back ? back.utc.slice(11, 19) + " UTC" : "");
    capSet("return", "Yoink moved the money out " + (out ? Math.round((Date.parse(out.utc) - R.t0_ms) / 60000) + " minutes after the take" : "soon after") + ", before Ronin got in touch. " + (backAmt ? backAmt[1] + " ETH" : "Most of it") + " reached a Ronin Safe that afternoon" + (spR ? ": " + BVH.pct(100 * spR.ret / spR.g, 1) + " of the take" : "") + ".");
    M.allCap = "A user's withdrawal request, copied with " + (M.diff ? M.diff.length : 3) + " words changed, wrapped in a program, paid for with a bribe to the builder, placed ahead of the original, and mostly handed back the same day. Pick a step, or press play.";
    render();
    void nRet; void nKept;
  }).catch(function (e) { fail($("#v-return"), e); });
})();
