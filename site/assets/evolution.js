(function () {
  "use strict";
  var $ = function (s) { return document.querySelector(s); };
  var esc = BVH.esc;
  var timingSummary = "builder bid response: see methods for the measured range";
  BVH.chrome("evolution.html");
  var E, META;
  var COL = { atk: "var(--atk)", bld: "var(--bld)", ink: "var(--ink)", mut: "var(--muted)", gold: "var(--gold)", line: "var(--line2)" };

  /* ---------- helpers ---------- */
  function S(tag, a, p, t) { return BVH.svg(tag, a, p, t); }
  function txt(p, x, y, s, o) {
    o = o || {};
    return S("text", { x: x, y: y, "text-anchor": o.a || "start", style: "font:" + (o.w || 400) + " " + (o.s || 11) + "px var(--mono);fill:" + (COL[o.c] || o.c || "var(--muted)") + (o.op ? ";opacity:" + o.op : "") }, p, s);
  }
  function hash(s) { var h = 2166136261; s = String(s); for (var i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619); } return ((h >>> 0) % 10000) / 10000; }
  function median(a) { a = a.filter(function (x) { return x != null && !isNaN(x); }).sort(function (x, y) { return x - y; }); if (!a.length) return null; var m = a.length >> 1; return a.length % 2 ? a[m] : (a[m - 1] + a[m]) / 2; }
  function fnum(x, d) { return x == null ? "n/a" : Number(x).toLocaleString("en-US", { maximumFractionDigits: d == null ? 1 : d }); }
  function fgwei(x) { return x == null ? "n/a" : x >= 10 ? fnum(x, 0) : x >= 1 ? fnum(x, 1) : x >= .1 ? fnum(x, 2) : fnum(x, 3); }
  function mount(sel, h, label, draw) {
    var el = $(sel), last = 0, timer;
    function go() {
      var w = Math.max(300, Math.floor(el.clientWidth || 600));
      if (w === last) return; last = w;
      el.innerHTML = "";
      var svg = S("svg", { viewBox: "0 0 " + w + " " + h, width: w, height: h, role: "img", "aria-label": label }, el);
      draw(svg, w, h);
    }
    go();
    if (window.ResizeObserver) new ResizeObserver(function () { clearTimeout(timer); timer = setTimeout(go, 80); }).observe(el);
    else window.addEventListener("resize", function () { clearTimeout(timer); timer = setTimeout(go, 80); });
    BVH.onTheme.push(function () { last = 0; go(); });
  }
  function table(sel, head, rows) {
    $(sel).innerHTML = '<table class="ops"><thead><tr>' + head.map(function (h) { return "<th>" + h + "</th>"; }).join("") + "</tr></thead><tbody>" +
      rows.map(function (r) { return "<tr>" + r.map(function (c) { return "<td>" + (c == null ? "n/a" : c) + "</td>"; }).join("") + "</tr>"; }).join("") + "</tbody></table>";
  }
  function axisY(svg, y, x0, x1, ticks, fmt) {
    var g = S("g", { "class": "ax" }, svg);
    ticks.forEach(function (t) {
      S("line", { x1: x0, x2: x1, y1: y(t), y2: y(t), style: "stroke:var(--line);stroke-width:1" }, g);
      txt(g, x0 - 6, y(t) + 4, fmt(t), { a: "end" });
    });
  }
  function qLabel(q) { return q.slice(0, 4) + " Q" + q.slice(5); }
  function yearFilter(y) { return y.n >= 1; }

  /* ---------- load ---------- */
  Promise.all([BVH.json("data/evolution.json"), BVH.json("data/meta.json"), BVH.json("data/headline_stats.json")]).then(function (r) { E = r[0]; META = r[1]; var d=r[2].detection_delay; timingSummary = d.n_measured + " measured races show " + BVH.dur(d.min_ms) + " to " + BVH.dur(d.max_ms) + ", from the trigger first appearing in the archive to the winning builder’s first qualifying bid"; build(); }).catch(function (e) { BVH.loadError($("#lede"), e); });

  function build() {
    var m = E.measured || {}, yrs = E.years, Y = {}; yrs.forEach(function (y) { Y[y.year] = y; });
    var res = (m.public || 0) + (m.private || 0);
    var eras = E.eras || [], e1 = eras[0] || {}, e4 = eras[3] || {};

    /* lede and banner */
    $("#lede").innerHTML = "The measured changes leave bots less to see. Since August 2023 only " + BVH.pct(m.attacker_seen_pct, 1) + " of exploit transactions were found in the public mempool archive, against " + BVH.pct(m.control_seen_pct, 1) + " of ordinary transactions in the same blocks. More attacks now happen in one transaction, and the gap between deploying an attack and running it has shortened from about half an hour in 2021–22 (n=11 fresh deployments) to about two minutes in 2024–26; the era table gives sample sizes and exact medians.";
    var b = $("#banner"); b.hidden = false;
    b.innerHTML = E.provisional
      ? "<b>Provisional numbers.</b> These come from the first analysis (v1), which treated every transaction listed in the reproduction repository as the attacker's. A correction pass was still running when this page was built, so treat them as approximate."
      : "<b>Corrected analysis (v2).</b> The first pass treated every listed transaction as the attacker's. Some were MEV bots, a whitehat or non-attack transactions. v2 classifies the sender of each, measures attackers only, and keeps the first-pass files unchanged. " + (E.v1_vs_v2 && E.v1_vs_v2.n_with_mainnet_tx_and_trace ? "The attacker sample is " + E.v1_vs_v2.n_with_mainnet_tx_and_trace.v2 + " exploits, down from " + E.v1_vs_v2.n_with_mainnet_tx_and_trace.v1 + ". " : "") + '<a href="#h-e">What changed</a>.';

    /* stat strip */
    var y25 = Y[2025] || {};
    var items = [
      [BVH.pct(m.attacker_seen_pct, 1), "of exploit transactions were visible in the public mempool since August 2023 (" + (m.public || 0) + " of " + res + "). Ordinary transactions: " + BVH.pct(m.control_seen_pct, 1) + "."],
      [m.relative_visibility ? "~" + Math.round(1 / m.relative_visibility) + "× less likely" : "n/a", "attacker transactions were seen in the archive, compared with other transactions in the same block."],
      [BVH.pct(y25.constructor_pct, 0), "of 2025 exploits ran entirely inside a constructor (" + (y25.constructor_k || "?") + " of " + (y25.constructor_n || "?") + "); none did before 2022."],
      [BVH.pct(y25.no_window_pct, 0), "of 2025 exploits gave a watching bot no window at all: one transaction, or deployed in the same block."]
    ];
    $("#stats").innerHTML = items.map(function (it) { return '<div class="stat" role="listitem"><b>' + it[0] + "</b><span>" + it[1] + "</span></div>"; }).join("");

    meas(); chartA(m); chartB(yrs, Y); chartC(yrs, Y, eras); chartD(yrs); changes(); downloads();
  }

  /* ---------- timeline: what can be measured ---------- */
  function meas() {
    var d = E.dots || [], cut = "2023-08-07";
    var before = d.filter(function (x) { return x.d < cut; }).length, after = d.length - before;
    var t0 = Date.UTC(2017, 0, 1), t1 = Date.UTC(2026, 10, 1), tc = Date.parse(cut + "T00:00:00Z");
    mount("#c-meas", 116, "Timeline from 2017 to 2026 showing that mempool data exists only from 7 August 2023", function (svg, w, h) {
      var l = 4, r = 4, x = BVH.lin(t0, t1, l, w - r), bar = 30, by = 34;
      S("rect", { x: x(t0), y: by, width: x(tc) - x(t0), height: bar, style: "fill:var(--bg3);stroke:var(--line2);stroke-dasharray:4 3" }, svg);
      S("rect", { x: x(tc), y: by, width: x(t1) - x(tc), height: bar, style: "fill:var(--bld-soft);stroke:var(--bld);stroke-width:1.3" }, svg);
      [[Date.UTC(2020, 11, 1), "Flashbots bundles", "end"], [Date.UTC(2022, 8, 15), "the Merge", "end"]].forEach(function (e) {
        S("line", { x1: x(e[0]), x2: x(e[0]), y1: by - 8, y2: by + bar, style: "stroke:var(--muted);stroke-width:1" }, svg);
        txt(svg, x(e[0]) - 4, by - 12, e[1], { a: e[2], s: 11 });
      });
      S("line", { x1: x(tc), x2: x(tc), y1: by - 8, y2: by + bar + 8, style: "stroke:var(--bld);stroke-width:2" }, svg);
      txt(svg, x(tc) - 4, by - 12, "7 Aug 2023", { a: "start", c: "bld", w: 600 });
      for (var yr = 2017; yr <= 2026; yr += (w < 520 ? 3 : 1)) { var xx = x(Date.UTC(yr, 0, 1)); S("line", { x1: xx, x2: xx, y1: by + bar, y2: by + bar + 4, style: "stroke:var(--line2)" }, svg); txt(svg, xx, by + bar + 16, String(yr), { a: yr === 2017 ? "start" : "middle", s: 10.5 }); }
      txt(svg, x(t0) + 2, by + bar + 34, "in-block evidence only: " + before + " exploits", { c: "ink", s: 12 });
      if (w < 560) txt(svg, x(t0) + 2, by + bar + 52, "archive covers: " + after + " exploits", { a: "start", c: "bld", s: 12, w: 600 }); else txt(svg, w - r, by + bar + 34, "archive covers: " + after + " exploits", { a: "end", c: "bld", s: 12, w: 600 });
    });
  }

  /* ---------- A: public vs neighbours ---------- */
  function chartA(m) {
    var Q = E.quarters || [];
    if (!Q.length) return;
    var last = Q[Q.length - 1], first = Q[0], res = (m.public || 0) + (m.private || 0);
    $("#a-text").innerHTML = "Of " + res + " exploit transactions we could classify since August 2023, " + (m.public || 0) + " were in the archive before their block (" + BVH.pct(m.attacker_seen_pct, 1) + "). In the same blocks, " + BVH.pct(m.control_seen_pct, 1) + " of ordinary transactions were. The archive's coverage of ordinary traffic has itself fallen, from " + BVH.pct(first.control_pct, 0) + " in " + qLabel(first.q) + " to " + BVH.pct(last.control_pct, 0) + " in " + qLabel(last.q) + " (a quarter still in progress), so the gap is the finding and the raw percentage is not." + (m.lead_time_n ? " Where a public sighting does exist, the median lead is " + BVH.dur(m.lead_time_s_median * 1000) + " (only " + m.lead_time_n + " cases, so treat it as an anecdote)." : "") + " An independent count (BACKRUNNER, January 2023 to May 2024, a different method) found 17 of 158 attack transactions visible.";
    mount("#c-a", 300, "Line chart by quarter: share of exploit transactions seen in the public mempool versus share of other transactions in the same blocks", function (svg, w, h) {
      var l = 42, r = 14, t = 34, bt = 30, x = BVH.lin(0, Math.max(1, Q.length - 1), l + 6, w - r - 6), y = BVH.lin(0, 100, h - bt, t);
      axisY(svg, y, l, w - r, [0, 25, 50, 75, 100], function (v) { return v + "%"; });
      var gx = S("g", { "class": "ax" }, svg);
      Q.forEach(function (q, i) { if (q.q.slice(4) === "Q1" || i === 0) { S("line", { x1: x(i), x2: x(i), y1: h - bt, y2: h - bt + 4, style: "stroke:var(--line2)" }, gx); txt(gx, x(i), h - bt + 17, q.q.slice(0, 4), { a: "middle" }); } });
      // legend
      S("line", { x1: l, x2: l + 22, y1: 12, y2: 12, style: "stroke:var(--bld);stroke-width:2.2" }, svg); S("rect", { x: l + 8, y: 8, width: 8, height: 8, style: "fill:var(--bld)" }, svg);
      txt(svg, l + 30, 16, "other transactions in the same blocks", { c: "ink", s: 12 });
      S("line", { x1: l, x2: l + 22, y1: 28, y2: 28, style: "stroke:var(--atk);stroke-width:2.2" }, svg); S("circle", { cx: l + 11, cy: 28, r: 4.2, style: "fill:var(--atk)" }, svg);
      txt(svg, l + 30, 32, "exploit transactions (band: 95% interval)", { c: "ink", s: 12 });
      // CI band
      var up = [], dn = [];
      Q.forEach(function (q, i) { if (q.attacker_ci) { up.push(x(i) + "," + y(q.attacker_ci[1])); dn.unshift(x(i) + "," + y(q.attacker_ci[0])); } });
      S("polygon", { points: up.concat(dn).join(" "), style: "fill:var(--atk-soft);stroke:none" }, svg);
      var pa = Q.map(function (q, i) { return x(i) + "," + y(q.attacker_pct || 0); }).join(" "), pc = Q.map(function (q, i) { return x(i) + "," + y(q.control_pct || 0); }).join(" ");
      S("polyline", { points: pc, style: "fill:none;stroke:var(--bld);stroke-width:2.2;stroke-linejoin:round" }, svg);
      S("polyline", { points: pa, style: "fill:none;stroke:var(--atk);stroke-width:2.2;stroke-linejoin:round" }, svg);
      var cw = (w - l - r) / Q.length;
      Q.forEach(function (q, i) {
        S("rect", { x: x(i) - 4.5, y: y(q.control_pct || 0) - 4.5, width: 9, height: 9, style: "fill:var(--bld);stroke:var(--bg);stroke-width:2" }, svg);
        S("circle", { cx: x(i), cy: y(q.attacker_pct || 0), r: 4.8, style: "fill:var(--atk);stroke:var(--bg);stroke-width:2" }, svg);
        var hit = S("rect", { x: x(i) - cw / 2, y: t, width: cw, height: h - bt - t, tabindex: 0, role: "img", "aria-label": qLabel(q.q) + ": " + (q.public || 0) + " of " + ((q.public || 0) + (q.private || 0)) + " exploit transactions public", style: "fill:transparent;outline-offset:-2px" }, svg);
        BVH.tipFor(hit, function () { return "<b>" + qLabel(q.q) + "</b><br>exploits classified: " + ((q.public || 0) + (q.private || 0)) + "<br>seen in public mempool: " + (q.public || 0) + " (" + BVH.pct(q.attacker_pct, 1) + (q.attacker_ci ? ", 95% " + q.attacker_ci[0] + " to " + q.attacker_ci[1] + "%" : "") + ")<br>other transactions seen: " + BVH.pct(q.control_pct, 0); });
      });
    });
    table("#t-a", ["quarter", "exploits", "seen public", "unknown", "exploit % seen", "95% interval", "others % seen"], Q.map(function (q) {
      return [qLabel(q.q), (q.public || 0) + (q.private || 0) + (q.unknown || 0), q.public, q.unknown, fnum(q.attacker_pct), q.attacker_ci ? q.attacker_ci[0] + " to " + q.attacker_ci[1] : null, fnum(q.control_pct)];
    }));
  }

  /* ---------- B: constructor share ---------- */
  function chartB(yrs, Y) {
    var y22 = Y[2022] || {}, y25 = Y[2025] || {}, y26 = Y[2026] || {}, y24 = Y[2024] || {};
    $("#b-text").innerHTML = "Before 2022 no exploit in the sample ran entirely inside a constructor. In 2024 it was " + BVH.pct(y24.constructor_pct, 0) + ", in 2025 " + BVH.pct(y25.constructor_pct, 0) + " (" + y25.constructor_k + " of " + y25.constructor_n + ") and in 2026 so far " + (y26.constructor_k != null ? Math.round(100 * y26.constructor_k / y26.n) + "% (" + y26.constructor_k + " of " + y26.n + ")" : BVH.pct(y26.constructor_pct, 0)) + ". Add exploits that create a contract from inside another call and the 2025 figure is " + BVH.pct(y25.constructor_or_internal_pct, 0) + ". It is a one-way door for bot builders: the later the attacker's contract exists, the less there is to see.";
    mount("#c-b", 290, "Bar chart by year: share of exploits that ran entirely inside a constructor", function (svg, w, h) {
      var l = 42, r = 10, t = 22, bt = 46, y = BVH.lin(0, 100, h - bt, t), n = yrs.length, bw = (w - l - r) / n;
      axisY(svg, y, l, w - r, [0, 25, 50, 75, 100], function (v) { return v + "%"; });
      yrs.forEach(function (d, i) {
        var cx = l + bw * (i + .5), small = (d.n || 0) < 10, bwid = Math.min(46, bw * .62), v = d.constructor_pct || 0;
        var g = S("g", { tabindex: 0, role: "img", "aria-label": d.year + ": " + v + "% of " + d.n + " exploits ran inside a constructor" }, svg);
        if (v > 0) S("rect", { x: cx - bwid / 2, y: y(v), width: bwid, height: y(0) - y(v), rx: 3, style: "fill:var(--atk);opacity:" + (small ? .35 : 1) }, g);
        else S("rect", { x: cx - bwid / 2, y: y(0) - 2, width: bwid, height: 2, style: "fill:var(--atk);opacity:" + (small ? .35 : 1) }, g);
        var top = y(v);
        if (d.constructor_ci && !small) { S("line", { x1: cx, x2: cx, y1: y(d.constructor_ci[0]), y2: y(d.constructor_ci[1]), style: "stroke:var(--ink);stroke-width:1.3" }, g); [0, 1].forEach(function (k) { S("line", { x1: cx - 4, x2: cx + 4, y1: y(d.constructor_ci[k]), y2: y(d.constructor_ci[k]), style: "stroke:var(--ink);stroke-width:1.3" }, g); }); top = Math.min(top, y(d.constructor_ci[1])); }
        txt(g, cx, top - 6, v ? (d.constructor_k != null && d.n ? Math.round(100 * d.constructor_k / d.n) : Math.round(v)) + "%" : "0%", { a: "middle", c: "ink", s: 12, w: 600 });
        txt(svg, cx, h - bt + 16, String(d.year), { a: "middle", s: 11.5, c: "ink" });
        txt(svg, cx, h - bt + 31, "n=" + d.n, { a: "middle", s: 10.5 });
        BVH.tipFor(g, function () { return "<b>" + d.year + "</b><br>" + (d.constructor_k != null ? d.constructor_k + " of " + d.constructor_n : "") + " ran in a constructor (" + BVH.pct(d.constructor_pct, 1) + ")" + (d.constructor_ci ? "<br>95% interval " + d.constructor_ci[0] + " to " + d.constructor_ci[1] + "%" : "") + "<br>in one transaction (deploy and attack): " + BVH.pct(d.same_tx_pct, 0); });
      });
    });
    table("#t-b", ["year", "exploits", "constructor-only", "95% interval", "deploy+attack in one tx %", "no watchable window %"], yrs.map(function (d) {
      return [d.year, d.n, d.constructor_k != null ? d.constructor_k + " (" + fnum(d.constructor_pct) + "%)" : fnum(d.constructor_pct) + "%", d.constructor_ci ? d.constructor_ci[0] + " to " + d.constructor_ci[1] : null, fnum(d.same_tx_pct), fnum(d.no_window_pct)];
    }));
  }

  /* ---------- C: deploy -> attack gap ---------- */
  function chartC(yrs, Y, eras) {
    var d = (E.dots || []).filter(function (x) { return x.fresh && x.gap != null; });
    var ys = yrs.map(function (x) { return x.year; }).filter(function (yr) { return d.some(function (x) { return x.y === yr; }); });
    var e = {}; eras.forEach(function (x) { e[x.era.slice(0, 2)] = x; });
    $("#c-text").innerHTML = "The median fresh attack contract waited " + BVH.dur((e.E1 && e.E1.gap_s || 0) * 1000) + " (before 2021), " + BVH.dur((e.E2 && e.E2.gap_s || 0) * 1000) + " (2021 to September 2022), " + BVH.dur((e.E3 && e.E3.gap_s || 0) * 1000) + " (to 2023) and " + BVH.dur((e.E4 && e.E4.gap_s || 0) * 1000) + " (2024 to 2026) between deployment and attack. A bot reacting in seconds (" + timingSummary + ") has more to work with than that, but a rising share has no window to work with: " + BVH.pct((Y[2025] || {}).no_window_pct, 0) + " of 2025 exploits were constructor attacks, internal creates, or deployed in the attack's own block.";
    mount("#c-c", 330, "Strip chart by year of the seconds between deploying an attack contract and attacking, log scale", function (svg, w, h) {
      var l = 56, r = 10, t = 14, bt = 50, zeroH = 34, y = BVH.log(6, 700000, h - bt - zeroH, t), n = ys.length, bw = (w - l - r) / n;
      var ticks = [[10, "10 s"], [60, "1 min"], [600, "10 min"], [3600, "1 hour"], [86400, "1 day"], [604800, "7 days"]];
      var g = S("g", { "class": "ax" }, svg);
      ticks.forEach(function (tk) { S("line", { x1: l, x2: w - r, y1: y(tk[0]), y2: y(tk[0]), style: "stroke:var(--line);stroke-width:1" }, g); txt(g, l - 6, y(tk[0]) + 4, tk[1], { a: "end" }); });
      var zy = h - bt - zeroH / 2 + 2;
      S("rect", { x: l, y: h - bt - zeroH + 6, width: w - l - r, height: zeroH - 6, style: "fill:var(--bg3);opacity:.7" }, svg);
      txt(g, l - 6, zy + 4, "0 s", { a: "end" });
      ys.forEach(function (yr, i) {
        var cx = l + bw * (i + .5), dd = d.filter(function (x) { return x.y === yr; }), zero = dd.filter(function (x) { return x.gap === 0; }).length;
        dd.forEach(function (x) {
          var jx = (hash(x.n + x.d) - .5) * Math.min(bw * .8, 70), cy = x.gap === 0 ? zy + (hash(x.d + x.n) - .5) * (zeroH - 16) : y(x.gap);
          var el = x.ctor ? S("polygon", { points: [cx + jx, cy - 4.6, cx + jx + 4.2, cy + 3.4, cx + jx - 4.2, cy + 3.4].join(","), style: "fill:var(--atk);opacity:.8;stroke:var(--bg);stroke-width:1" }, svg)
            : S("circle", { cx: cx + jx, cy: cy, r: 3.6, style: "fill:var(--atk);opacity:.62;stroke:var(--bg);stroke-width:1" }, svg);
          BVH.tipFor(el, function () { return "<b>" + esc(x.n) + "</b> (" + x.d + ")<br>" + (x.gap === 0 ? "deployed in the same block or transaction" : "deployed " + BVH.dur(x.gap * 1000) + " before") + (x.ctor ? "<br>constructor or internal create" : ""); });
        });
        var med = (Y[yr] || {}).gap_s_median, mn = (Y[yr] || {}).gap_n || 0;
        if (med) { S("line", { x1: cx - Math.min(bw * .42, 38), x2: cx + Math.min(bw * .42, 38), y1: y(med), y2: y(med), style: "stroke:var(--ink);stroke-width:2.4;opacity:" + (mn >= 8 ? 1 : .4) }, svg); }
        txt(svg, cx, h - bt + 16, String(yr), { a: "middle", s: 11.5, c: "ink" });
        if (bw > 70) txt(svg, cx, h - bt + 31, Math.round(100 * zero / dd.length) + "% at 0 s", { a: "middle", s: 10 });
      });
      txt(svg, l, 10, "bar = median where at least 8 gaps; triangle = constructor or internal create", { s: 10.5 });
    });
    table("#t-c", ["year", "exploits", "fresh contracts with a gap", "median gap (s)", "same block %", "no watchable window %"], ys.map(function (yr) {
      var Yd = Y[yr] || {}; return [yr, Yd.n, Yd.gap_n, Yd.gap_s_median, fnum(Yd.same_block_deploy_pct), fnum(Yd.no_window_pct)];
    }));
  }

  /* ---------- D: priority fee ---------- */
  function chartD(yrs) {
    var d = E.dots || [], rows = yrs.map(function (yd) {
      var meds = d.filter(function (x) { return x.y === yd.year; }).map(function (x) { return x.med; });
      return { year: yd.year, n: yd.n, atk: yd.tip_gwei_median, blk: median(meds), zero: yd.tip_zero_pct };
    }).filter(function (x) { return x.atk != null; });
    var a21 = rows.filter(function (x) { return x.year === 2021; })[0] || {}, a26 = rows[rows.length - 1] || {};
    $("#d-text").innerHTML = "In 2021 the median exploit paid a " + fgwei(a21.atk) + " gwei tip when the block's median was " + fgwei(a21.blk) + ", an attacker bidding 3 to 4 times the block. In " + a26.year + " it paid " + fgwei(a26.atk) + " when the block's median was " + fgwei(a26.blk) + ": the same. Exploits no longer bid in the gas auction, because the real auction moved to builders. Coinbase payments, the other way to bid, appear in only " + BVH.pct((E.overall || {}).bribe_pct, 1) + " of attacker transactions overall. Bots, by contrast, paid builders directly in " + (E.bot_side ? BVH.pct(E.bot_side.overall.bribe_paid_pct_of_measured, 0) : "most") + " of the bot transactions we could measure (" + (E.bot_side ? E.bot_side.overall.bribe_paid_n + " of " + E.bot_side.overall.n_measured : "most") + "), a mix of races and non-races.";
    mount("#c-d", 310, "Line chart by year of the median priority fee of exploit transactions against the median of their blocks, log scale", function (svg, w, h) {
      var l = 50, r = 12, t = 40, bt = 30, y = BVH.log(0.05, 400, h - bt, t), n = rows.length, bw = (w - l - r) / n;
      axisY(svg, y, l, w - r, [0.1, 1, 10, 100], function (v) { return String(v); });
            var X = function (i) { return l + bw * (i + .5); };
      rows.forEach(function (rw, i) {
        d.filter(function (x) { return x.y === rw.year && x.tip >= 0.05; }).forEach(function (x) {
          S("circle", { cx: X(i) + (hash(x.n + x.d) - .5) * Math.min(bw * .8, 60), cy: y(x.tip), r: 2.4, style: "fill:var(--atk);opacity:.22" }, svg);
        });
        txt(svg, X(i), h - bt + 17, String(rw.year), { a: "middle", s: 11.5, c: "ink" });
      });
      S("polyline", { points: rows.map(function (rw, i) { return rw.blk ? X(i) + "," + y(rw.blk) : null; }).filter(Boolean).join(" "), style: "fill:none;stroke:var(--bld);stroke-width:2.2" }, svg);
      S("polyline", { points: rows.map(function (rw, i) { return X(i) + "," + y(rw.atk); }).join(" "), style: "fill:none;stroke:var(--atk);stroke-width:2.2" }, svg);
      rows.forEach(function (rw, i) {
        if (rw.blk) S("rect", { x: X(i) - 4.5, y: y(rw.blk) - 4.5, width: 9, height: 9, style: "fill:var(--bld);stroke:var(--bg);stroke-width:2" }, svg);
        var c = S("circle", { cx: X(i), cy: y(rw.atk), r: 4.8, tabindex: 0, style: "fill:var(--atk);stroke:var(--bg);stroke-width:2" }, svg);
        BVH.tipFor(c, function () { return "<b>" + rw.year + "</b> (" + rw.n + " exploits)<br>median exploit tip: " + fgwei(rw.atk) + " gwei<br>median of the blocks: " + fgwei(rw.blk) + " gwei<br>exploits with a zero tip: " + BVH.pct(rw.zero, 1); });
      });
      var narrow = w < 560, lx = narrow ? l + 6 : w - 360, ly = 10, ly2 = narrow ? 26 : 10, lx2 = narrow ? lx : lx + 168;
      S("line", { x1: lx, x2: lx + 20, y1: ly, y2: ly, style: "stroke:var(--atk);stroke-width:2.2" }, svg); S("circle", { cx: lx + 10, cy: ly, r: 4, style: "fill:var(--atk)" }, svg);
      txt(svg, lx + 26, ly + 4, "exploit transactions", { c: "ink", s: 11.5 });
      S("line", { x1: lx2, x2: lx2 + 20, y1: ly2, y2: ly2, style: "stroke:var(--bld);stroke-width:2.2" }, svg); S("rect", { x: lx2 + 6, y: ly2 - 4, width: 8, height: 8, style: "fill:var(--bld)" }, svg);
      txt(svg, lx2 + 26, ly2 + 4, "median of their blocks (gwei, log scale)", { c: "ink", s: 11.5 });
    });
    table("#t-d", ["year", "exploits", "median exploit tip (gwei)", "median block tip (gwei)", "zero-tip exploits %"], rows.map(function (rw) { return [rw.year, rw.n, fgwei(rw.atk), fgwei(rw.blk), fnum(rw.zero)]; }));
  }

  /* ---------- what the correction changed ---------- */
  function changes() {
    var v = E.v1_vs_v2;
    if (!v) { $("#e-text").innerHTML = "<p>No comparison with the first pass is available in this build.</p>"; return; }
    $("#e-text").innerHTML = "<p>The first pass analysed 315 exploit rows. 34 had no attacker-sent transaction and were excluded: 28 bot-only, one whitehat and five unknown-sender or non-attack rows. In 35 rows the first listed transaction was non-attacker-sent; one mixed row remains and is measured using its attacker transaction. Visibility and the deploy-window findings barely moved. The first pass appeared to show attackers paying builders more over time. That was a bot signature: the large coinbase payments (Makina 1,299 ETH, DeFi Plaza 66, Alkimiya 51, Kelp 19) were MEV bots paying builders. Attackers who bribe do so in about 7 to 8 percent of cases, with no rise from 2023 to 2024.</p>";
    var names = [["n_with_mainnet_tx_and_trace", "exploits in the attacker sample"], ["dumpster_attacker_seen_pct", "seen in the public mempool (%)"], ["dumpster_control_seen_pct", "other transactions seen (%)"], ["constructor_exploit_pct", "constructor-only (%)"], ["no_watchable_window_pct", "no watchable window (%)"], ["deploy_gap_s_median_fresh_le7d", "median deploy-to-attack gap (s)"], ["coinbase_bribe_pct", "paid a coinbase bribe (%)"], ["tx_index_0_pct", "at the top of the block (%)"], ["tip_zero_pct", "zero tip (%)"], ["tx_index_median", "median position in the block"]];
    var rows = names.filter(function (n) { return v[n[0]]; }).map(function (n) {
      var q = v[n[0]], dl = q.delta, cls = Math.abs(dl) >= 2 && n[0] !== "n_with_mainnet_tx_and_trace" ? ' style="color:var(--gold);font-weight:600"' : "";
      return [n[1], fnum(q.v1), fnum(q.v2), "<span" + cls + ">" + (dl > 0 ? "+" : "") + fnum(dl) + "</span>"];
    });
    table("#t-e", ["measure", "first pass", "corrected", "change"], rows);
    var b = E.bot_side && E.bot_side.overall;
    if (b) $("#e-text").insertAdjacentHTML("beforeend", "<p>The bot-sent transactions form their own table: " + b.n_rows + " rows, of which " + b.n_measured + " could be measured. " + b.tx_index_0_n + " of the " + b.n_rows + " sat at position 0 of their block, and " + BVH.pct(b.bribe_paid_pct_of_measured, 0) + " of the " + b.n_measured + " measured paid a coinbase bribe (" + fnum(b.bribe_eth_total, 0) + " ETH in total). Nine rows involve one bot whose transactions we deliberately did not trace.</p>");
  }

  /* ---------- downloads ---------- */
  function downloads() {
    var list = (META.downloads || []).filter(function (x) { return /^downloads\/(evolution|bibliography)/.test(x.path); });
    list = list.concat([{ path: "data/incidents.json", bytes: null, desc: "One row per race, as shown on the home page" }]);
    $("#t-dl").innerHTML = '<thead><tr><th>file</th><th>what is in it</th><th>size</th></tr></thead><tbody>' + list.map(function (x) {
      var kb = x.bytes == null ? "" : x.bytes > 1e6 ? (x.bytes / 1e6).toFixed(1) + " MB" : Math.round(x.bytes / 1e3) + " kB";
      return '<tr><td><a href="' + esc(x.path) + '">' + esc(x.path.split("/").pop()) + "</a></td><td>" + esc(x.desc) + "</td><td>" + kb + "</td></tr>";
    }).join("") + "</tbody>";
  }
})();
