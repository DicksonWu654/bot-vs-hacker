/* Part 3: Has the dark forest changed? Every number is read from site/data at render time. */
(function () {
  "use strict";
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
  function wilson(k, n) {
    if (!n) return [0, 0];
    var z = 1.96, p = k / n, den = 1 + z * z / n, c = (p + z * z / (2 * n)) / den, h = z * Math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den;
    return [Math.max(0, 100 * (c - h)), Math.min(100, 100 * (c + h))];
  }
  function gapTxt(s) {
    if (s == null) return "n/a";
    if (s < 120) return Math.round(s) + "\u00a0s";
    if (s < 7200) return (s / 60).toFixed(1) + "\u00a0min";
    return (s / 3600).toFixed(1) + "\u00a0h";
  }
  function month(iso) { var d = new Date(iso + "T00:00:00Z"); return d.toLocaleDateString("en-GB", { month: "short", year: "numeric", timeZone: "UTC" }); }
  function tms(iso) { return Date.parse(iso + "T00:00:00Z"); }
  function utcTime(s) { return s ? s.slice(11, 19) : "n/a"; }
  function short(r) { return (r.title || r.id).split(":")[0].trim(); }
  function incA(r, text) { return '<a href="incident.html?slug=' + encodeURIComponent(r.id) + '">' + esc(text || short(r)) + "</a>"; }

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
    attrs["class"] = "hit"; attrs.tabindex = 0; attrs.role = "img"; attrs["aria-label"] = html.replace(/<[^>]+>/g, "");
    var r = S(attrs.r != null ? "circle" : "rect", attrs, parent);
    BVH.tipFor(r, function () { return html; });
    return r;
  }
  function gridY(svg, y, x0, x1, ticks, fmt) {
    ticks.forEach(function (t) {
      S("line", { x1: x0, x2: x1, y1: y(t), y2: y(t), "class": t === 0 ? "g-base" : "g-grid" }, svg);
      T(svg, x0 - 8, y(t) + 4, fmt(t), "t-ax", "end");
    });
  }

  var E, HS, INC, MK, META;
  Promise.all([BVH.json(F.evo), BVH.json(F.hs), BVH.json(F.inc), BVH.json("data/incident/makina-2026.json"), BVH.json("data/meta.json")])
    .then(function (r) { E = r[0]; HS = r[1]; INC = r[2]; MK = r[3]; META = r[4]; build(); })
    .catch(function (e) { var d = document.createElement("div"); d.className = "wrap"; $("#main").insertBefore(d, $("#ch1")); BVH.loadError(d, e); });

  function build() {
    var Y = {}; E.years.forEach(function (y) { Y[y.year] = y; });
    var m = E.measured, ov = E.overall, eras = E.eras, bot = E.bot_side.overall, vv = E.v1_vs_v2;
    var resolved = m.public + m.private;
    var head = INC.filter(function (r) { return r.headline; });
    var dw = head.filter(function (r) { return r.race_type === "deploy-window-copy"; }).sort(function (a, b) { return a.date < b.date ? -1 : 1; });
    var dwYears = dw.map(function (r) { return +r.date.slice(0, 4); });
    var dwMin = Math.min.apply(null, dwYears), dwMax = Math.max.apply(null, dwYears);
    var y25 = Y[2025], y26 = Y[2026];
    var archive = E.dots.filter(function (d) { return d.d >= m.since && (d.exp === "public" || d.exp === "private-bundle"); })
      .sort(function (a, b) { return a.d < b.d ? -1 : a.d > b.d ? 1 : 0; });
    var seen = archive.filter(function (d) { return d.exp === "public"; });
    var lastSeen = seen[seen.length - 1];
    var timesLess = Math.round(1 / m.relative_visibility);
    var x0Years = E.years.filter(function (y) { return y.year < 2020; });
    var e1 = eras[0], e4 = eras[3];

    /* ---------- hero ---------- */
    $(".ev-dek").innerHTML = "Ethereum used to be a place where a hacker's transaction sat in public for a few seconds, and any bot could copy it. That world is mostly gone. Here is what changed, measured on " + num(ov.n) + " exploits from " + E.years[0].year + " to " + E.years[E.years.length - 1].year + "." + SE();
    var toc = [
      ["#ch1", pct(m.attacker_seen_pct), "atk", "of attacker transactions showed up in the public mempool, against " + pct(m.control_seen_pct) + " of ordinary ones."],
      ["#ch2", pctS(y25.constructor_pct), "atk", "of " + y25.year + " exploits ran the whole attack inside the attack contract's constructor, leaving nothing pending to copy."],
      ["#ch3", gapTxt(y25.gap_s_median), "gold", "median wait between deploying an attack contract and using it in " + y25.year + ". Before 2021 it was " + gapTxt(e1.gap_s) + "."],
      ["#ch4", pctS(bot.bribe_paid_pct_of_measured), "bot", "of bot transactions paid the block builder directly. Attackers did so " + pct(ov.bribe_pct) + " of the time."],
      ["#ch5", dw.length + " of " + head.length, "gold", "races a bot won by copying the attacker's on-chain setup. All " + dw.length + " came in " + (dwMin === dwMax ? dwMin : dwMin + " and " + dwMax) + "."]
    ];
    $("#toc").innerHTML = toc.map(function (t, i) {
      return '<li><a href="' + t[0] + '"><span class="i">' + (i + 1) + '</span><span class="v ' + t[2] + '">' + esc(t[1]) + '</span><span class="d">' + esc(t[3]) + "</span></a></li>";
    }).join("");

    ch1(m, resolved, archive, seen, lastSeen, timesLess);
    ch2(Y, y25, y26, x0Years);
    ch3(Y, y25, y26, eras, dw);
    ch4(Y, ov, bot, head);
    ch5(head, bot, vv, dw);
    ending(m, seen, lastSeen, y25, dw);
    tables(head);
    downloads();
  }

  /* ================= 1. visibility ================= */
  function ch1(m, resolved, archive, seen, lastSeen, timesLess) {
    var since = BVH.dateLong(m.since);
    $("#ch1-lede").innerHTML = "Since a public archive of the mempool began on " + since + ", only <b>" + m.public + " of " + resolved + "</b> attacker transactions were seen there before they landed. In the very same blocks, the archive saw <b>" + pct(m.control_seen_pct) + "</b> of everyone else's." + SF() + " Attacker transactions now almost never show up in the public pool before they land; most likely they go privately to block builders. A bot watching the public pool then has nothing to copy.";

    var rows = [
      ["ctl", "Ordinary transactions", "in the same blocks", m.control_seen_pct, pct(m.control_seen_pct)],
      ["atk", "Attacker transactions", m.public + " of " + resolved, m.attacker_seen_pct, pct(m.attacker_seen_pct)]
    ];
    $("#c1-vs").innerHTML = rows.map(function (r) {
      return '<div class="ev-vsrow ' + r[0] + '"><div class="l"><b>' + r[1] + "</b>" + esc(r[2]) + '</div><div class="track" role="img" aria-label="' + r[1] + ": " + r[4] + ' seen in the public mempool"><div class="fill" style="width:' + r[3] + '%"></div></div><div class="v">' + r[4] + "</div></div>";
    }).join("") + '<div class="ev-vsaxis" aria-hidden="true"><div></div><div><span style="left:0">0%</span><span style="left:25%">25%</span><span style="left:50%">50%</span><span style="left:75%">75%</span><span style="left:100%">100%</span></div><div></div></div>';
    $("#f1cap").innerHTML = "Share seen in the public mempool archive before the block was proposed, " + since + " to October 2026. Attackers were about " + timesLess + " times less visible than the transactions around them." + SF();

    /* lights */
    $("#c1-gridt").textContent = archive.length + " resolved attacker transactions since the archive began, one square each" + (m.unknown ? "; " + m.unknown + (m.unknown === 1 ? " more could not be resolved and is not drawn" : " more could not be resolved and are not drawn") : "") + ". Lit: the archive saw it in public.";
    var g = $("#c1-grid");
    g.setAttribute("aria-label", archive.length + " squares, one per attacker transaction since " + since + "; " + seen.length + " are lit because the archive saw them");
    archive.forEach(function (d) {
      var i = document.createElement("i");
      if (d.exp === "public") {
        i.className = "on"; i.tabIndex = 0;
        BVH.tipFor(i, function () { return "<b>" + esc(d.n) + "</b>, " + BVH.dateLong(d.d) + "<br>seen in the public mempool before its block"; });
      }
      g.appendChild(i);
    });
    var key = '<ul class="ev-lightkey"><li><i></i>seen in the public mempool (' + seen.length + ')</li><li><i class="off"></i>never seen in public (' + (archive.length - seen.length) + ")</li></ul>";
    $("#c1-key").innerHTML = key;
    $("#f1bcap").innerHTML = "In date order, " + month(archive[0].d) + " at the top left to " + month(archive[archive.length - 1].d) + " at the bottom right. The " + seen.length + " that were seen:" +
      '<ul class="ev-seen">' + seen.map(function (d) { return "<li>" + esc(d.n) + " <span>" + month(d.d) + "</span></li>"; }).join("") + "</ul>" + src(F.per, "per_exploit_v2.json: one row per exploit, with its mempool label");

    var early = seen.filter(function (d) { return d.d < "2024-05-01"; }).length;
    var Q = E.quarters;
    $("#ch1-side").innerHTML =
      "<p>The lights went out early. " + early + " of the " + seen.length + " sightings came before May 2024. Since then the archive has caught one attacker in public: " + esc(lastSeen.n) + ", in " + month(lastSeen.d) + ". Every attacker transaction after that went unseen." + SE() + "</p>" +
      "<p>Even the ones that were seen gave little warning: a median of " + m.lead_time_s_median.toFixed(1) + " seconds before their block." + SF() + "</p>" +
      "<p>The archive itself caught less over time, " + pct(Y_(2023).control_pct) + " of ordinary transactions in 2023 and " + pct(Y_(2026).control_pct) + " in 2026. That is why every comparison here is against the other transactions in the same blocks.</p>";

    mount($("#c1-q"), "Quarterly share seen in the public mempool: ordinary transactions stay between " + Math.round(Math.min.apply(null, Q.map(function (q) { return q.control_pct; }))) + " and " + Math.round(Math.max.apply(null, Q.map(function (q) { return q.control_pct; }))) + " percent, attacker transactions between 0 and " + Math.round(Math.max.apply(null, Q.map(function (q) { return q.attacker_pct; }))) + " percent.", function (svg, w) {
      var wide = w >= 640, l = 44, r = wide ? 16 : 8, t = 18, ph = wide ? 260 : 220, b = wide ? 74 : 44;
      var n = Q.length, bw = (w - l - r) / n;
      var x = function (i) { return l + (i + .5) * bw; }, y = BVH.lin(0, 100, t + ph, t);
      gridY(svg, y, l, w - r, [0, 25, 50, 75, 100], function (v) { return v + "%"; });
      /* control */
      S("polyline", { points: Q.map(function (q, i) { return x(i) + "," + y(q.control_pct); }).join(" "), fill: "none", stroke: "var(--muted)", "stroke-width": 2 }, svg);
      Q.forEach(function (q, i) { S("circle", { cx: x(i), cy: y(q.control_pct), r: 3.5, fill: "var(--muted)" }, svg); });
      /* attacker: interval + dot */
      S("polyline", { points: Q.map(function (q, i) { return x(i) + "," + y(q.attacker_pct); }).join(" "), fill: "none", stroke: "var(--atk)", "stroke-width": 2 }, svg);
      Q.forEach(function (q, i) { S("circle", { cx: x(i), cy: y(q.attacker_pct), r: 5, fill: "var(--atk)", stroke: "var(--bg)", "stroke-width": 2 }, svg); });
      /* direct labels */
      var c0 = Q[0];
      T(svg, x(0) - 4, y(c0.control_pct) - 12, "ordinary transactions", "t-labb", "start");
      var qn = Q.length - 1;
      T(svg, x(qn) + 4, y(Q[qn].attacker_pct) - (wide ? 14 : 22), "attacker transactions", "t-labb", "end", { fill: "var(--atk)" });
      /* x axis */
      Q.forEach(function (q, i) {
        var yr = q.q.slice(0, 4), qq = q.q.slice(4);
        T(svg, x(i), t + ph + 16, wide ? qq : qq.slice(1), "t-ax", "middle");
        if (i === 0 || qq === "Q1") T(svg, x(i) - bw / 2 + 2, t + ph + 32, yr, "t-lab", "start");
        if (wide) {
          T(svg, x(i), t + ph + 52, q.public + "/" + (q.public + q.private), "t-ax", "middle");
        }
        hit(svg, { x: x(i) - bw / 2, y: t, width: bw, height: ph }, "<b>" + yr + " " + qq + "</b><br>attacker transactions seen: " + q.public + " of " + (q.public + q.private) + " (" + pct(q.attacker_pct) + ")<br>ordinary transactions seen: " + pct(q.control_pct));
      });
      if (wide) T(svg, l - 8, t + ph + 52, "seen", "t-ax", "end");
      return t + ph + b;
    });
    $("#f1ccap").innerHTML = "Share seen in the public mempool archive, by quarter. Grey: the other transactions in the same blocks. Red: attacker transactions. Some quarters hold only a handful of exploits, so the row under the axis gives seen / total for each." + SE();

    var bc = HS.backrunner_comparison, bp = bc.backrunner_paper, ow = bc.ours_w6_v2_same_window_attacker_only;
    $("#ch1-how").innerHTML = "<b>How we know.</b> The Mempool Dumpster archive starts on " + since + "; we have no mempool archive for earlier exploits, so they have in-block evidence only. A transaction counts as private when the archive covered that day, saw many other transactions in the same block, and never saw this one. That is strong evidence, not proof. An independent study (BACKRUNNER) found " + bp.visible_in_public_mempool + " of " + bp.attack_txs + " attack transactions public from January 2023 to May 2024 (" + pct(bp.public_pct) + "); over the overlapping window we find " + ow.public + " of " + ow.resolved + " (" + pct(ow.public_pct) + ")." + SH();
  }
  var _Y = null;
  function Y_(yr) { if (!_Y) { _Y = {}; E.years.forEach(function (y) { _Y[y.year] = y; }); } return _Y[yr]; }

  /* ================= 2. constructor-only ================= */
  function ch2(Y, y25, y26, x0Years) {
    var pre = E.years.filter(function (y) { return y.year >= 2020 && y.year < 2025; });
    var lo = Math.min.apply(null, pre.map(function (y) { return y.constructor_pct; })), hi = Math.max.apply(null, pre.map(function (y) { return y.constructor_pct; }));
    $("#ch2-lede").innerHTML = "In a two-step attack the contract sits on chain before it is used, and a bot can read it. In " + y25.year + ", <b>" + pctS(y25.constructor_pct) + " of exploits (" + y25.constructor_k + " of " + y25.constructor_n + ")</b> skipped that step: the whole attack ran inside the transaction that created the contract. Through 2024 the share had been between " + pctS(lo) + " and " + pctS(hi) + "." + SE();

    $("#c2-shapes").innerHTML =
      '<div class="ev-shape"><h4>Two steps</h4><p>Deploy a contract, wait, then call it.</p>' +
      '<div class="ev-track"><div class="ev-tx">1. Deploy the attack contract<small>lands in a block, readable by anyone</small></div><div class="ev-wait">the contract waits on chain <em>seconds to minutes</em></div><div class="ev-tx">2. Call attack()<small>usually never seen in the public pool</small></div></div>' +
      '<p class="ev-copy yes"><i></i><span>A copier can read the deployed contract and run the same plan first. That is how the Makina race was won.</span></p></div>' +
      '<div class="ev-shape"><h4>One step, constructor-only</h4><p>The attack runs while the contract is being created.</p>' +
      '<div class="ev-track one"><div class="ev-tx">1. Create the contract; its constructor runs the whole attack<small>one transaction</small></div><div class="ev-wait none">no wait <em>nothing sits on chain</em></div><div class="ev-tx ghost">no second step<small>the attack is already over</small></div></div>' +
      '<p class="ev-copy no"><i></i><span>Nothing exists on chain until the attack has landed. If the transaction also skipped the public pool, nothing is available in the public mempool or in prior on-chain state for an outside copier.</span></p></div>';

    var yrs = E.years.filter(function (y) { return y.year >= 2020; });
    mount($("#c2-bars"), "Bar chart by year of the share of exploits with no watchable window, split into constructor-only and other. " + yrs.map(function (y) { return y.year + ": " + pctS(y.constructor_pct) + " constructor-only, " + pctS(y.no_window_pct) + " no window"; }).join("; "), function (svg, w) {
      var wide = w >= 640, l = 44, r = 8, t = 26, ph = wide ? 280 : 230, b = 46;
      var n = yrs.length, bw = (w - l - r) / n, barW = Math.min(64, bw * .62);
      var y = BVH.lin(0, 100, t + ph, t);
      gridY(svg, y, l, w - r, [0, 25, 50, 75, 100], function (v) { return v + "%"; });
      yrs.forEach(function (d, i) {
        var cx = l + (i + .5) * bw, x0 = cx - barW / 2, faint = d.n < 10;
        var g = S("g", faint ? { opacity: .5 } : {}, svg);
        var yc = y(d.constructor_pct), yn = y(d.no_window_pct), y0 = y(0);
        if (d.constructor_pct > 0) S("rect", { x: x0, y: yc, width: barW, height: Math.max(0, y0 - yc), rx: 3, fill: "var(--atk)" }, g);
        if (d.no_window_pct - d.constructor_pct > 0.05) S("rect", { x: x0, y: yn, width: barW, height: Math.max(0, yc - yn - 2), rx: 3, fill: "var(--atk)", opacity: .38 }, g);
        /* interval for the constructor share */
        var ci = d.constructor_ci;
        if (ci && d.n >= 10 && wide) {
          var wx = x0 + barW + 6;
          S("line", { x1: wx, x2: wx, y1: y(ci[0]), y2: y(ci[1]), "class": "g-ann" }, g);
          S("line", { x1: wx - 3, x2: wx + 3, y1: y(ci[0]), y2: y(ci[0]), "class": "g-ann" }, g);
          S("line", { x1: wx - 3, x2: wx + 3, y1: y(ci[1]), y2: y(ci[1]), "class": "g-ann" }, g);
        }
        T(g, cx, yn - 8, pctS(d.no_window_pct), d.year === y25.year ? "t-big" : "t-labb", "middle", wide ? null : { style: "font-size:11px" });
        if (y0 - yc > 22 && wide) T(g, cx, y0 - 8, pctS(d.constructor_pct), "t-labb", "middle", { fill: "var(--bg)" });
        T(g, cx, t + ph + 17, String(d.year), "t-lab", "middle");
        T(g, cx, t + ph + 33, "n=" + d.n, "t-ax", "middle");
        hit(svg, { x: cx - bw / 2, y: t, width: bw, height: ph }, "<b>" + d.year + "</b> (" + d.n + " exploits)<br>constructor-only: " + pct(d.constructor_pct) + " (" + d.constructor_k + " of " + d.constructor_n + ", 95% interval " + d.constructor_ci[0].toFixed(1) + " to " + d.constructor_ci[1].toFixed(1) + "%)<br>no watchable window at all: " + pct(d.no_window_pct));
      });
      return t + ph + b;
    });
    var preN = x0Years.reduce(function (s, y) { return s + y.n; }, 0), preK = x0Years.reduce(function (s, y) { return s + y.constructor_k; }, 0);
    $("#f2bcap").innerHTML = "The number on top is the total with no window. Faded segment: an attack contract created inside the attack transaction, or deployed in the same block as the attack. On wide screens, ticks beside each bar give the 95% interval for the constructor-only share (also in the tables at the end). 2020 has only " + Y[2020].n + " exploits and is drawn faint; " + x0Years.map(function (y) { return y.year; }).join(" and ") + " (" + preN + " exploits, " + preK + " constructor-only) are left off. " + y26.year + " runs to October." + SE();
    $("#ch2-how").innerHTML = "<b>How we know.</b> We traced the first attacker transaction of each exploit. Constructor-only means the attack calls happen inside the creation of the attack contract; the detection is a lower bound. The jump from 2024 (" + pct(Y[2024].constructor_pct) + ", interval " + Y[2024].constructor_ci[0] + " to " + Y[2024].constructor_ci[1] + "%) to 2025 (" + pct(y25.constructor_pct) + ", " + y25.constructor_ci[0] + " to " + y25.constructor_ci[1] + "%) is larger than the uncertainty. In " + y26.year + " so far the share is " + pct(y26.constructor_pct) + " (" + y26.constructor_k + " of " + y26.constructor_n + ")." + SF();
  }

  /* ================= 3. the window ================= */
  function ch3(Y, y25, y26, eras, dw) {
    $("#ch3-lede").innerHTML = "When attackers did deploy first, they waited less. The median gap between deploying an attack contract and using it fell from <b>" + gapTxt(eras[0].gap_s) + "</b> before 2021 to <b>" + gapTxt(y25.gap_s_median) + "</b> in " + y25.year + " and " + gapTxt(y26.gap_s_median) + " in " + y26.year + ". In " + y25.year + ", of the " + y25.gap_n + " attacks whose fresh contract was deployed before the attack transaction (within seven days), " + pctS(y25.same_block_deploy_pct) + " deployed it in the very block of the attack." + SE();

    var yrs = E.years.filter(function (y) { return y.year >= 2020 && y.gap_s_median != null; });
    mount($("#c3-gap"), "Median deploy-to-attack gap by year: " + yrs.map(function (y) { return y.year + " " + gapTxt(y.gap_s_median); }).join(", "), function (svg, w) {
      var wide = w >= 640, l = wide ? 92 : 56, r = wide ? 120 : 56, t = 34, rh = wide ? 40 : 38, n = yrs.length, ph = n * rh;
      var maxMin = 16, x = BVH.lin(0, maxMin, l, w - r);
      [0, 4, 8, 12, 16].forEach(function (v) {
        S("line", { x1: x(v), x2: x(v), y1: t - 6, y2: t + ph, "class": v === 0 ? "g-base" : "g-grid" }, svg);
        T(svg, x(v), t + ph + 16, v + (v === 16 ? " min" : ""), "t-ax", "middle");
      });
      /* one-block reference */
      var xb = x(12 / 60);
      S("line", { x1: xb, x2: xb, y1: t - 14, y2: t + ph, stroke: "var(--gold)", "stroke-width": 1.5 }, svg);
      T(svg, xb + 5, t - 16, "one block, 12 s", "t-ann", "start", { fill: "var(--gold)" });
      yrs.forEach(function (d, i) {
        var cy = t + i * rh + rh / 2, mins = d.gap_s_median / 60, faint = d.gap_n < 10, g = S("g", faint ? { opacity: .5 } : {}, svg);
        var hl = d.year >= 2025;
        T(g, l - 14, cy + 1, String(d.year), hl ? "t-big" : "t-lab", "end");
        T(g, l - 14, cy + 14, "n=" + d.gap_n, "t-ax", "end");
        var bh = 16, off = mins > maxMin;
        var xe = off ? x(maxMin) - 18 : x(mins);
        S("rect", { x: l, y: cy - bh / 2, width: Math.max(3, xe - l), height: bh, rx: 3, fill: hl ? "var(--gold)" : "var(--ink2)" }, g);
        if (off) {
          /* broken bar: the value runs off the scale */
          S("path", { d: "M" + (xe + 4) + " " + (cy - bh / 2 - 3) + "l6 " + (bh + 6) + "M" + (xe + 10) + " " + (cy - bh / 2 - 3) + "l6 " + (bh + 6), stroke: "var(--ink2)", "stroke-width": 1.5, fill: "none" }, g);
          S("rect", { x: xe + 16, y: cy - bh / 2, width: x(maxMin) - xe - 16, height: bh, rx: 3, fill: "var(--ink2)" }, g);
          T(g, x(maxMin) + 8, cy + 4, gapTxt(d.gap_s_median) + (wide ? ", off scale" : ""), "t-labb", "start");
        } else {
          T(g, xe + 8, cy + 4, gapTxt(d.gap_s_median), hl ? "t-big" : "t-labb", "start");
        }
        hit(svg, { x: 0, y: cy - rh / 2, width: w, height: rh }, "<b>" + d.year + "</b><br>median fresh deploy-to-attack gap: " + gapTxt(d.gap_s_median) + " (" + d.gap_s_median + " s)<br>from " + d.gap_n + " attacker-owned contracts deployed at most 7 days before<br>deployed in the attack's own block: " + pct(d.same_block_deploy_pct));
      });
      return t + ph + 26;
    });
    $("#f3acap").innerHTML = "Median over attacker-owned contracts created at most seven days before the attack; n is how many such contracts that year. Years with fewer than ten are drawn faint. The scale is linear; 2021's median runs off it and is drawn broken. By era: " + eras.map(function (e) { return e.era.replace(/^E\d /, "").replace(/ \(.*$/, "") + " " + gapTxt(e.gap_s); }).join(", ") + "." + SE();

    /* Makina */
    var evs = MK.events || [];
    var dep = evs.filter(function (e) { return e.kind === "deploy" && /attack contract/.test(e.detail); })[0];
    var helper = evs.filter(function (e) { return e.kind === "deploy" && /helper/.test(e.detail); })[0];
    var btx = evs.filter(function (e) { return e.kind === "tx" && e.block === MK.block.number && /searcher/i.test(e.actor); })[0];
    var payout = (MK.txs || []).filter(function (x) { return x.role === "builder"; })[0];
    var botTx = (MK.txs || []).filter(function (x) { return x.role === "bot"; })[0];
    var gapS = dep && btx ? Math.round((Date.parse(btx.utc) - Date.parse(dep.utc)) / 1000) : null;
    var cb = MK.dataset_money.coinbase_eth;
    $("#ch3-mk").innerHTML = "Makina's attacker prepared for about " + (helper && dep ? Math.round((Date.parse(dep.utc) - Date.parse(helper.utc)) / 60000) : "n/a") + " minutes, then deployed the attack contract at " + utcTime(dep && dep.utc) + " UTC" + (dep ? src(dep.raw, "Trace of the deploy transaction") : "") + ". It never got to call it. In the next block, " + gapS + " seconds later, a searcher ran the same plan at position " + MK.bot_idx + " and paid <b>" + BVH.eth(cb) + "</b> to the block builder for that spot." + (btx ? src(btx.raw, "Trace of the searcher's transaction") : "");

    mount($("#c3-mk"), "Two blocks, " + gapS + " seconds apart. Block " + (dep && dep.block) + ": the attacker deploys its attack contract. Block " + MK.block.number + ": a searcher's copy runs at position 0 of " + MK.block.ntx + " transactions and pays " + BVH.eth(cb) + " to the builder. The attacker's own call never lands.", function (svg, w) {
      var wide = w >= 700, labW = wide ? 210 : 0, x0 = labW, x1 = w - 2, strip = MK.strip || [], nt = MK.block.ntx || strip.length, bh = 40;
      var fs = wide ? 12.5 : 11.5, y = 6;
      function head(lines, yy) {
        lines.forEach(function (L, j) { T(svg, 0, yy + 14 + j * 17, L[0], L[1], "start", L[2]); });
      }
      /* row 1: the attacker's deploy */
      var h1 = [["block " + num(dep ? dep.block : null), "t-labb"], [(dep ? utcTime(dep.utc) : "") + " UTC", "t-ax"]];
      if (wide) head(h1, y); else { T(svg, 0, y + 14, "block " + num(dep ? dep.block : null), "t-labb", "start"); T(svg, x1, y + 14, (dep ? utcTime(dep.utc) : "") + " UTC", "t-ax", "end"); }
      var by = wide ? y : y + 24;
      S("rect", { x: x0, y: by, width: x1 - x0, height: bh, rx: 4, fill: "none", stroke: "var(--line2)" }, svg);
      S("rect", { x: x0 + 6, y: by + 6, width: x1 - x0 - 12, height: bh - 12, rx: 3, fill: "var(--atk-soft)", stroke: "var(--atk)", "stroke-width": 1.5 }, svg);
      T(svg, x0 + 16, by + 25, wide ? "the attacker deploys its attack contract and waits" : "attacker deploys its attack contract", "t-lab", "start", { style: "font-size:" + fs + "px" });
      y = by + bh + 8;
      /* the 12 s gap */
      S("line", { x1: x0 + 12, x2: x0 + 12, y1: y, y2: y + 26, stroke: "var(--gold)", "stroke-width": 2 }, svg);
      T(svg, x0 + 22, y + 18, "+" + gapS + " s, the next block", "t-ann", "start", { fill: "var(--gold)" });
      y += 34;
      /* row 2: the next block, one sliver per transaction */
      if (wide) head([["block " + num(MK.block.number), "t-labb"], [utcTime(btx && btx.utc) + " UTC", "t-ax"]], y);
      else { T(svg, 0, y + 14, "block " + num(MK.block.number), "t-labb", "start"); T(svg, x1, y + 14, utcTime(btx && btx.utc) + " UTC", "t-ax", "end"); }
      by = wide ? y : y + 24;
      var cw = (x1 - x0) / nt;
      for (var k = 0; k < nt; k++) {
        var st = strip[k] || [], role = st[2];
        var fill = role === "bot" ? "var(--bot)" : (k === nt - 1 && payout ? "var(--bld)" : "var(--ev-dim2)");
        S("rect", { x: x0 + k * cw + .5, y: by, width: Math.max(1, cw - 1), height: bh, rx: 1, fill: fill }, svg);
      }
      var bx = x0 + cw / 2;
      S("line", { x1: bx, x2: bx, y1: by + bh, y2: by + bh + 10, "class": "g-ann" }, svg);
      T(svg, x0, by + bh + 24, "position 0: the searcher's copy", "t-labb", "start", { style: "font-size:" + fs + "px" });
      T(svg, x0, by + bh + 41, "paid " + BVH.eth(cb) + " to the builder", "t-lab", "start", { style: "font-size:" + fs + "px" });
      if (payout) T(svg, x1, by + bh + (wide ? 24 : 58), wide ? "last: the builder pays the proposer " + BVH.eth(payout.value_eth) : "last: builder pays proposer " + BVH.eth(payout.value_eth), "t-ax", "end");
      y = by + bh + (wide ? 58 : 74);
      /* row 3: the call that never came */
      T(svg, 0, y + (wide ? 23 : 14), "attacker's own call", "t-labb", "start", { fill: "var(--atk)" });
      by = wide ? y : y + 24;
      S("rect", { x: x0, y: by + 4, width: Math.min(320, x1 - x0), height: bh - 8, rx: 4, fill: "none", stroke: "var(--atk)", "stroke-dasharray": "4 4" }, svg);
      T(svg, x0 + 14, by + 25, "never sent", "t-lab", "start", { fill: "var(--atk)" });
      return by + bh + 4;
    });
    $("#f3bcap").innerHTML = "Block " + num(MK.block.number) + " held " + MK.block.ntx + " transactions; each sliver is one. The copy sits first" + (payout ? "; the last transaction is the builder paying the proposer " + BVH.eth(payout.value_eth) : "") + "." + BVH.rawA(MK.block.raw.block, "block") + BVH.rawA(MK.block.raw.trace, "trace") + ' <a href="incident.html?slug=makina-2026">The full Makina race</a>.';

    var y0 = +dw[0].date.slice(0, 4), y1 = +dw[dw.length - 1].date.slice(0, 4);
    $("#ch3-mk2").innerHTML = "That is the deploy-window copy: the bot copies the attacker's setup instead of the attack. Of the " + INC.filter(function (r) { return r.headline; }).length + " races a bot won, " + dw.length + " worked this way, all in " + (y0 === y1 ? y0 : y0 + " and " + y1) + ". In each one the bot moved in the very next block." + SH();
    $("#c3-dw").innerHTML = dw.map(function (r) {
      return '<li><div class="blk" aria-hidden="true"><i class="a"></i><i class="b' + (r.bot_idx > 0 ? " p1" : "") + '"></i></div><div><h4>' + incA(r) + '</h4><div class="meta">' + BVH.dateLong(r.date) + ", " + esc(r.bot) + ", position " + r.bot_idx + "</div><p>" + esc(r.one_liner) + BVH.rawA(r.raw.trace, "trace") + "</p></div></li>";
    }).join("");
    $("#ch3-how").innerHTML = "<b>How we know.</b> Times are block timestamps, so they move in 12-second steps. Gaps count only contracts the attacker owned and created within seven days; an attack contract created inside the attack transaction counts as zero. How the Makina searcher learned the plan is not visible on chain; its calldata matches the deployed contract, so the contract alone was enough.";
  }

  /* ================= 4. paying the builder ================= */
  function ch4(Y, ov, bot, head) {
    var bci = wilson(bot.bribe_paid_n, bot.n_measured);
    $("#ch4-lede").innerHTML = "A transaction can buy its place in a block by paying the builder directly. Attackers rarely do: <b>" + pct(ov.bribe_pct) + "</b> of attacker transactions, with no clear rise over the years. The bots that copy them mostly do: <b>" + bot.bribe_paid_n + " of " + bot.n_measured + "</b> traced bot transactions (" + pct(bot.bribe_paid_pct_of_measured) + "), " + num(bot.bribe_eth_total, 2) + " ETH in all." + SE();

    var yrs = E.years.filter(function (y) { return y.year >= 2020; });
    mount($("#c4-att"), "Bars by year of the share of attacker transactions that paid the builder, between 0 and " + Math.round(Math.max.apply(null, yrs.map(function (y) { return y.bribe_pct; }))) + " percent, and one bar for bots at " + pct(bot.bribe_paid_pct_of_measured), function (svg, w) {
      var wide = w >= 640, l = 44, r = 8, t = 26, ph = wide ? 240 : 200, b = 46;
      var slots = yrs.length + 1.6, bw = (w - l - r) / slots, barW = Math.min(52, bw * .6);
      var y = BVH.lin(0, 100, t + ph, t);
      gridY(svg, y, l, w - r, [0, 25, 50, 75, 100], function (v) { return v + "%"; });
      function bar(cx, v, k, n, fill, lab, sub, tip, faint) {
        var g = S("g", faint ? { opacity: .5 } : {}, svg), ci = wilson(k, n);
        if (v > 0) S("rect", { x: cx - barW / 2, y: y(v), width: barW, height: y(0) - y(v), rx: 3, fill: fill }, g);
        else S("line", { x1: cx - barW / 2, x2: cx + barW / 2, y1: y(0) - 1, y2: y(0) - 1, stroke: fill, "stroke-width": 2 }, g);
        if (!faint) {
          S("line", { x1: cx, x2: cx, y1: y(ci[0]), y2: y(ci[1]), "class": "g-ann" }, g);
          S("line", { x1: cx - 4, x2: cx + 4, y1: y(ci[1]), y2: y(ci[1]), "class": "g-ann" }, g);
          S("line", { x1: cx - 4, x2: cx + 4, y1: y(ci[0]), y2: y(ci[0]), "class": "g-ann" }, g);
        }
        T(g, cx, Math.min(y(v), y(faint ? v : ci[1])) - 8, pctS(v), "t-labb", "middle");
        T(g, cx, t + ph + 17, lab, "t-lab", "middle");
        T(g, cx, t + ph + 33, sub, "t-ax", "middle");
        hit(svg, { x: cx - bw / 2, y: t, width: bw, height: ph }, tip);
      }
      yrs.forEach(function (d, i) {
        var k = Math.round(d.bribe_pct * d.n / 100);
        bar(l + (i + .5) * bw, d.bribe_pct, k, d.n, "var(--atk)", String(d.year), "n=" + d.n, "<b>" + d.year + "</b>, attackers<br>paid the builder: " + pct(d.bribe_pct) + " of " + d.n + " exploits", d.n < 10);
      });
      var bx = l + (yrs.length + 1.1) * bw;
      S("line", { x1: bx - bw * .8, x2: bx - bw * .8, y1: t, y2: t + ph + 36, "class": "g-grid" }, svg);
      bar(bx, bot.bribe_paid_pct_of_measured, bot.bribe_paid_n, bot.n_measured, "var(--bot)", "bots", "n=" + bot.n_measured, "<b>Bot transactions</b> in the same exploit listings<br>paid the builder: " + bot.bribe_paid_n + " of " + bot.n_measured + " (" + pct(bot.bribe_paid_pct_of_measured) + ")<br>" + num(bot.bribe_eth_total, 2) + " ETH in total");
      return t + ph + b;
    });
    $("#f4acap").innerHTML = "Red: attacker transactions, by year of the exploit. Amber: every bot transaction we traced in the same exploit listings (Sept 2022 to 2026). Ticks: 95% intervals. 2020 and 2021 have few exploits and are drawn faint." + SE() + " The bot bar comes from " + bot.n_measured + " transactions found in exploit records, so it says nothing about how common bots are." + SF();

    /* races: share of take to builder */
    var BE = HS.block_producer_share.by_era_headline;
    var MERGE = "2022-09-15", PBS2 = "2024-01-01";
    var eraOf = function (d) { return d < MERGE ? "mev-geth-2021-22" : d < PBS2 ? "early-pbs-2022-23" : "mature-pbs-2024-26"; };
    var pts = head.filter(function (r) { return r.pct_to_builder != null; }).map(function (r) {
      var after = r.builder_refund_eth > 0 && r.gross_eth ? 100 * (r.paid_to_builder_eth - r.builder_refund_eth) / r.gross_eth : null;
      return { r: r, t: tms(r.date), v: r.pct_to_builder, after: after };
    });
    var bandsDef = [
      ["2021-01-01", MERGE, "mev-geth-2021-22", "Before the Merge", "Pre-Merge"],
      [MERGE, PBS2, "early-pbs-2022-23", "Early builder era", "Early PBS"],
      [PBS2, "2026-12-31", "mature-pbs-2024-26", "Mature builder era", "Mature PBS"]
    ];
    mount($("#c4-races"), "Dot plot of the share of each winning bot's take paid to the block builder, by date. Before 2024 every race paid under " + Math.ceil(Math.max.apply(null, pts.filter(function (p) { return p.r.date < PBS2; }).map(function (p) { return p.v; }))) + " percent; from 2024 the median race paid " + pct(BE["mature-pbs-2024-26"].median_row_pct) + ".", function (svg, w) {
      var wide = w >= 700, l = 44, r = wide ? 16 : 10, t = wide ? 58 : 22, ph = wide ? 300 : 260, b = wide ? 34 : 52;
      var x = BVH.lin(tms("2021-01-01"), tms("2026-12-31"), l, w - r), y = BVH.lin(0, 100, t + ph, t);
      bandsDef.forEach(function (bd, i) {
        var xa = x(tms(bd[0])), xb = x(tms(bd[1])), e = BE[bd[2]];
        if (i % 2 === 1) S("rect", { x: xa, y: wide ? t - 50 : t - 14, width: xb - xa, height: ph + (wide ? 50 : 14) + (wide ? 0 : 50), fill: "var(--bg2)" }, svg);
        if (wide) {
          T(svg, xa + 6, t - 34, bd[3], "t-labb", "start");
          T(svg, xa + 6, t - 18, e.rows + " race" + (e.rows === 1 ? "" : "s"), "t-ax", "start");
        } else {
          T(svg, (xa + xb) / 2, t + ph + 40, bd[4], "t-ann", "middle");
        }
      });
      gridY(svg, y, l, w - r, [0, 25, 50, 75, 100], function (v) { return v + "%"; });
      for (var yr = 2021; yr <= 2026; yr++) {
        var xx = x(tms(yr + "-07-01"));
        T(svg, xx, t + ph + 18, wide ? String(yr) : "'" + String(yr).slice(2), "t-ax", "middle");
      }
      /* the Merge */
      var xm = x(tms(MERGE));
      S("line", { x1: xm, x2: xm, y1: t, y2: t + ph, stroke: "var(--ink2)", "stroke-width": 1 }, svg);
      if (wide) T(svg, xm + 6, y(50), "The Merge, Sep 2022:", "t-ann", "start");
      if (wide) T(svg, xm + 6, y(50) + 15, "builders and relays start", "t-ann", "start");
      if (wide) T(svg, xm + 6, y(50) + 30, "building blocks", "t-ann", "start");
      pts.forEach(function (p) {
        var cx = x(p.t), cy = y(p.v);
        if (p.after != null) {
          S("line", { x1: cx, x2: cx, y1: cy + 6, y2: y(p.after) - 6, stroke: "var(--bld)", "stroke-width": 1.5, opacity: .7 }, svg);
          S("circle", { cx: cx, cy: y(p.after), r: 5, fill: "var(--bg)", stroke: "var(--bld)", "stroke-width": 2 }, svg);
        }
        S("circle", { cx: cx, cy: cy, r: 6, fill: "var(--bld)", stroke: "var(--bg)", "stroke-width": 2 }, svg);
      });
      var labels = wide ? { "earningfarm-2022": [8, -12, "start"], "blueberry-2024": [-12, 4, "end"], "defiplaza-2024": [12, 4, "start"], "alkimiya-2025": [-12, 4, "end", "after"], "makina-2026": [0, -14, "middle"], "kelp-rseth-2026": [-12, -10, "end"], "punk-2021": [0, -14, "middle"] }
        : { "makina-2026": [0, -12, "middle"] };
      pts.forEach(function (p) {
        var L = labels[p.r.id]; if (!L) return;
        var vy = L[3] === "after" ? p.after : p.v;
        var txt = short(p.r).replace(/ (Protocol|SilicaPools|rsETH holder Safe)$/, "") + (L[3] === "after" ? " after refund " : " ") + pctT(vy);
        T(svg, x(p.t) + L[0], y(vy) + L[1], txt, "t-labb", L[2]);
      });
      pts.forEach(function (p) {
        hit(svg, { cx: x(p.t), cy: y(p.v), r: 13 }, "<b>" + esc(short(p.r)) + "</b>, " + BVH.dateLong(p.r.date) + "<br>" + esc(p.r.bot) + "<br>paid to the builder: " + BVH.eth(p.r.paid_to_builder_eth) + " of " + BVH.eth(p.r.gross_eth) + " (" + pct(p.v) + ")" + (p.after != null ? "<br>after the builder's refund: " + pct(p.after) : ""));
      });
      return t + ph + b;
    });
    var eraRow = document.getElementById("c4-eras") || (function () { var d = document.createElement("ul"); d.id = "c4-eras"; d.className = "ev-eras"; $("#c4-races").insertAdjacentElement("afterend", d); return d; })();
    eraRow.innerHTML = bandsDef.map(function (bd) { var e = BE[bd[2]]; return "<li><b>" + pctT(e.median_row_pct) + "</b><span>" + bd[3] + ": the median race paid the builder this share of its take (" + e.rows + " race" + (e.rows === 1 ? "" : "s") + ")</span></li>"; }).join("");
    $("#f4bcap").innerHTML = "Each filled dot is one race a bot won: what its transaction paid the builder, including the priority fee, as a share of what it took. " + pts.length + " of " + head.length + " races are priced; " + head.filter(function (r) { return r.pct_to_builder == null; }).map(short).join(", ") + "'s take is not priced in ETH. Open ring: after the builder refunded part of the payment to the bot, where it did. The era medians are of these races." + SH() + " Builder eras follow the paper; the Merge is block 15,537,394.";

    /* where the bribe went */
    var mb = BE["mature-pbs-2024-26"], paid = mb.sum_paid_eth, refund = paid - mb.after_refunds.sum_paid_minus_refund_eth;
    var pass = HS.loot.returns.headline_rows_returned_by_builder_or_proposer, toVictim = pass.sum_eth, kept = paid - refund - toVictim;
    var passNames = Object.keys(pass.rows).map(function (k) { var r = INC.filter(function (x) { return x.id === k; })[0]; return r ? short(r) : k; });
    $("#c4-split-t").textContent = "Where the " + num(paid, 2) + " ETH the winning bots paid builders since 2024 ended up (" + mb.rows + " races)";
    var segs = [[toVictim, "var(--ret)", "back to the victims", "the builder passed it on (" + passNames.join(" and ") + ")"], [kept, "var(--bld)", "stayed with builders and proposers", "the price of going first"], [refund, "var(--bot)", "refunded to the bots", "by the same builder, in the same block"]];
    $("#c4-split").innerHTML = '<div class="ev-sbar" role="img" aria-label="' + segs.map(function (s) { return s[2] + " " + num(s[0], 2) + " ETH"; }).join(", ") + '">' + segs.map(function (s) { return '<div style="flex-grow:' + s[0].toFixed(3) + ';background:' + s[1] + '"></div>'; }).join("") + '</div><div class="k">' +
      segs.map(function (s) { return '<div style="border-color:' + s[1] + '"><b>' + pct(100 * s[0] / paid) + "</b><span>" + s[2] + "</span><small>" + num(s[0], 2) + " ETH, " + s[3] + "</small></div>"; }).join("") + "</div>";
    $("#f4ccap").innerHTML = "Payment before refunds, followed to where it landed. Blueberry's builder sent most of the bot's payment to the protocol's multisig in the same block; Makina's builder forwarded 1,023 ETH to an address that returned 920.7 ETH after a 10% bounty. The rest is what remains with builders and proposers under the flows we traced." + SH();
    $("#ch4-how").innerHTML = "<b>How we know.</b> A payment to the builder is a direct ETH transfer to the block's fee recipient inside the transaction, read from the trace. An earlier pass of this study counted bot transactions as attackers and showed attackers paying builders more and more; with each sender classified, that trend disappears (" + pct(E.v1_vs_v2.coinbase_bribe_pct.v1) + " before the correction, " + pct(E.v1_vs_v2.coinbase_bribe_pct.v2) + " after). Two large attacker payments remain, Hopelend (263.9 ETH) and Ambient (33.9 ETH); both look like searcher transactions but nothing identifies them as bots." + SF();
  }

  /* ================= 5. the winning bots ================= */
  function ch5(head, bot, vv, dw) {
    var oi = HS.backrunner_comparison.ours_incident_set;
    var name = function (id) { id = id.replace("/", "--"); var r = INC.filter(function (x) { return x.id === id; })[0]; return r ? short(r) : id; };
    var seenNames = oi.seen.map(name), uniq = seenNames.filter(function (s, i) { return seenNames.indexOf(s) === i; }).map(function (s) {
      var k = seenNames.filter(function (x) { return x === s; }).length; return k > 1 ? (k === 2 ? "two" : k) + " " + s + " races" : s; });
    $("#ch5-lede").innerHTML = "Bots that beat attackers no longer win by watching the public pool alone. Since the archive began, the attacker's transaction was visible in public in only <b>" + oi.attacker_trigger_tx_seen_public_before_inclusion + " of the " + oi.headline_races_in_dumpster_era + "</b> races a bot won." + SH() + " The winners sit at the top of the block, pay the builder for that spot, and lately copy what the attacker leaves on chain.";

    var atk0 = vv.tx_index_0_pct.v2;
    var rows = [
      ["At position 0, the top of the block", atk0, "attackers", bot.tx_index_0_pct, "bots", bot.tx_index_0_n + " of " + bot.n_rows],
      ["Paid the block builder directly", E.overall.bribe_pct, "attackers", bot.bribe_paid_pct_of_measured, "bots", bot.bribe_paid_n + " of " + bot.n_measured]
    ];
    function lab(v, cls, who, val, extra) {
      var right = v > 55;
      return '<span class="lab ' + cls + '" style="left:' + v + '%;' + (right ? "transform:translateX(-100%);text-align:right" : "") + '">' + who + " <b>" + val + "</b>" + (extra ? " (" + extra + ")" : "") + "</span>";
    }
    $("#c5-db").innerHTML = rows.map(function (r) {
      var lo = Math.min(r[1], r[3]), hi = Math.max(r[1], r[3]);
      return '<div class="ev-dbrow"><div class="l">' + r[0] + '</div><div class="ev-dbtrack" role="img" aria-label="' + r[0] + ": attackers " + pct(r[1]) + ", bots " + pct(r[3]) + '"><div class="base"></div><div class="span" style="left:' + lo + "%;width:" + (hi - lo) + '%"></div>' +
        '<div class="dot atk" style="left:' + r[1] + '%"></div><div class="dot bot" style="left:' + r[3] + '%"></div>' + lab(r[1], "up", "attackers", pct(r[1])) + lab(r[3], "dn", "bots", pct(r[3]), r[5]) + "</div></div>";
    }).join("") + '<div class="ev-dbaxis" aria-hidden="true"><div></div><div><span style="left:0">0%</span><span style="left:50%">50%</span><span style="left:100%">100%</span></div></div>';
    $("#f5acap").innerHTML = "Attackers: the first attacker transaction of each of " + E.overall.n + " exploits." + SE() + " Bots: the " + bot.n_rows + " bot transactions listed in the same records (" + bot.n_measured + " traced for payments; the other " + (bot.n_rows - bot.n_measured) + " are c0ffeebabe.eth rows we record by block and position only)." + SF();

    /* lanes */
    var years = []; for (var yv = +head.reduce(function (a, r) { return r.date < a ? r.date : a; }, "9999").slice(0, 4); yv <= 2026; yv++) years.push(yv);
    function chip(r) {
      var cbb = r.bot === "c0ffeebabe.eth";
      var botName = r.bot.replace(/\s*\(.*$/, "");
      return '<a class="ev-chip' + (r.race_type === "deploy-window-copy" ? " dw" : "") + (cbb ? " cb" : "") + '" href="incident.html?slug=' + encodeURIComponent(r.id) + '">' + esc(r.sub_label ? short(r) + ", " + r.sub_label : short(r)) + "<small>" + esc(botName) + ", " + month(r.date) + "</small></a>";
    }
    var html = '<div class="lrow lhd"><div class="yr"></div><div class="la"><i class="sw"></i>Copied a pending attack<small>' + head.filter(function (r) { return r.race_type === "beat-pending-attack"; }).length + ' races</small></div><div class="lb"><i class="sw dw"></i>Copied the attacker\'s setup<small>' + dw.length + " races</small></div></div>";
    years.forEach(function (yy) {
      var inY = head.filter(function (r) { return +r.date.slice(0, 4) === yy; }).sort(function (a, b) { return a.date < b.date ? -1 : 1; });
      var a = inY.filter(function (r) { return r.race_type === "beat-pending-attack"; }), b = inY.filter(function (r) { return r.race_type === "deploy-window-copy"; });
      html += '<div class="lrow"><div class="yr">' + yy + '</div><div class="la' + (a.length ? "" : " empty") + '">' + (a.map(chip).join("") || '<span class="ev-empty">none</span>') + '</div><div class="lb' + (b.length ? "" : " empty") + '">' + (b.map(chip).join("") || '<span class="ev-empty">none</span>') + "</div></div>";
    });
    $("#c5-lanes").innerHTML = html;
    $("#f5bcap").innerHTML = "Amber edge: the bot copied an attack transaction that was still pending, or landed ahead of it in the same block. Gold: the bot used the attacker's deployed contract, upgrade or prepare() call before the attacker's own attack. Each chip opens the race and its saved evidence." + SH();

    $("#ch5-side").innerHTML =
      "<p>Look at the amber chips. Through " + (+dw[0].date.slice(0, 4) - 1) + ", every one of these races was won against a pending attack transaction. Since then, " + dw.length + " wins came from the attacker's setup: a contract, an upgrade or a prepare() call that landed one block before the attack.</p>" +
      "<p>The data cannot say why. It fits the first three chapters: when the attack itself is private and runs in one step, what a copier can still see is the setup that lands on chain first, and only for a block or two.</p>" +
      "<p>Of the races since the archive began, the attacker's transaction was seen in public in " + uniq.join(", ").replace(/, ([^,]*)$/, " and $1") + ". In the other " + oi.not_seen.length + " the archive never saw the attacker's transaction before its block.</p>";

    /* c0ffeebabe public facts */
    var cbRows = head.filter(function (r) { return r.bot === "c0ffeebabe.eth"; }).sort(function (a, b) { return a.date < b.date ? -1 : 1; });
    function outcome(r) {
      if (r.fate_kind === "returned") return "Returned";
      if (r.fate_kind === "partial") return "Partly returned";
      if (r.fate_kind === "kept") return "No return found";
      return "Unknown";
    }
    function drawCb(DS) { $("#c5-cb").innerHTML = "<h3>Where c0ffeebabe.eth appears</h3><p>Public transaction facts only: which block, which position, and where the money went. " + cbRows.length + " of the " + head.length + " races. Its transactions in exploit listings are recorded by block and position only; we do not analyse its bot.</p><ol>" +
      cbRows.map(function (r, ri) {
        var sp = BVH.moneySplit ? BVH.splitHTML(BVH.moneySplit(r), { compact: false, sources: BVH.moneySrc(r, DS && DS[ri]) }) : "<p>" + outcome(r) + "</p>";
        return '<li><div class="cbh">' + incA(r, short(r) + (r.sub_label ? ", " + r.sub_label : "")) + "<span>" + esc(outcome(r)) + '</span></div><div class="cbm">' + BVH.dateLong(r.date) + ", block " + num(r.block) + ", position " + r.bot_idx + BVH.rawA(r.raw.block, "block") + BVH.rawA(r.raw.trace, "trace") + "</div>" + sp + "</li>";
      }).join("") + "</ol>"; }
    drawCb(null);
    Promise.all(cbRows.map(function (r) { return BVH.json("data/incident/" + r.id + ".json").catch(function () { return null; }); })).then(drawCb);

    $("#ch5-how").innerHTML = "<b>How we know.</b> The " + head.length + " races are those confirmed on chain where a bot beat a pending attack or used the attacker's setup. Euler (2023), an earlier setup copy, is left out because the copier's identity is unresolved. Positions and payments come from each block's trace. The bot-side counts come from bot transactions that happen to appear in exploit listings, not from a census of bots. For c0ffeebabe.eth we describe public transactions only." + SH();
  }

  /* ================= end ================= */
  function ending(m, seen, lastSeen, y25, dw) {
    var none = E.quarters.filter(function (q) { return q.q > "2025Q1"; }).every(function (q) { return q.public === 0; });
    var cards = [
      ["Attackers hid", pct(m.attacker_seen_pct) + " of attacker transactions were seen in the public mempool" + (none ? ", and none after " + month(lastSeen.d) : "") + ". Ordinary transactions in the same blocks: " + pct(m.control_seen_pct) + "."],
      ["The window closed", pctS(y25.constructor_pct) + " of " + y25.year + " exploits were constructor-only, and " + pctS(y25.same_tx_pct) + " deployed and attacked in the same transaction. Where a fresh contract went up first, the median wait was " + gapTxt(y25.gap_s_median) + " (" + y25.gap_n + " exploits)."],
      ["The bots adapted", "Winning bots sit at the top of the block, pay the builder for it, and since " + dw[0].date.slice(0, 4) + " have won by copying the attacker's setup instead of the attack."]
    ];
    $("#sum").innerHTML = cards.map(function (c) { return "<div><h3>" + c[0] + "</h3><p>" + c[1] + "</p></div>"; }).join("");
  }

  /* ================= tables ================= */
  function tbl(title, head, rows, note) {
    return "<section><h3>" + title + '</h3><div class="ev-tw"><table><thead><tr>' + head.map(function (h) { return "<th>" + h + "</th>"; }).join("") + "</tr></thead><tbody>" +
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
    var list = (META.downloads || []).filter(function (x) { return /^downloads\/evolution\/.*v2/.test(x.path); });
    list = list.concat([{ path: F.evo, desc: "Aggregates drawn on this page" }, { path: F.hs, desc: "Race-level totals: payments to builders, returns" }, { path: F.inc, desc: "One row per race" }]);
    $("#t-dl").innerHTML = "<thead><tr><th>download</th><th>what is in it</th></tr></thead><tbody>" + list.map(function (x) {
      return '<tr><td><a href="' + esc(x.path) + '">' + esc(x.path.split("/").pop()) + "</a></td><td>" + esc(x.desc) + "</td></tr>";
    }).join("") + "</tbody>";
  }
})();
