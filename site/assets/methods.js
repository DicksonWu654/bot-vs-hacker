(function () {
  "use strict";
  var esc = BVH.esc;
  BVH.chrome("methods.html");
  BVH.json("data/headline_stats.json").then(function (H) {
    var d=H.detection_delay, s=H.sensitivity.excluding_c0ffeebabe_rows, r=H.loot.returns.gross.headline_rows;
    document.getElementById("timing-summary").textContent = d.n_measured + " races can be timed (" + d.headline_rows_measured.length + " headline), ranging from " + d.min_ms + " to " + d.max_ms + " ms. Median: " + d.median_ms + " ms. Bid contents and bot detection times remain unknown.";
    document.getElementById("sensitivity-summary").textContent = H.counts.headline_rows + " rows in " + H.counts.headline_incidents + " incidents; " + s.rows + " rows in " + s.incidents + " incidents excluding c0ffeebabe.eth rows with withheld comparisons.";
    document.getElementById("returns-summary").textContent = BVH.pct(r.pooled_pct,1) + " pooled across " + r.rows + " rows, " + r.known_zero_rows + " with known zero.";
    /* the home page shows one number and one sentence per card; the qualifiers live here */
    var c = H.counts, hb = c.headline_by_race_type || {}, o = H.ordering || {}, pd = H.block_producer_share.headline_rows, ar = pd.after_refunds || {}, n = function (x, k) { return Number(x).toLocaleString("en-US", { maximumFractionDigits: k == null ? 0 : k, minimumFractionDigits: k == null ? 0 : k }); };
    var hn = [
      [c.headline_rows + " races in " + c.headline_incidents + " incidents",
        "Out of " + c.rows + " races and sub-races investigated across " + c.incidents + " incidents. A race counts when the evidence is confirmed on chain and the bot either beat a pending attack (" + (hb["beat-pending-attack"] || 0) + " races) or used the attacker's own setup before the attacker's call (" + (hb["deploy-window-copy"] || 0) + "). " +
        (o["earlier-block"] || 0) + " landed a block or more ahead of the attacker, " + (o["same-block-earlier-index"] || 0) + " earlier in the same block, and in " + (o["before-attacker-call-landed"] || 0) + " the attacker's own call never landed. Copies of a user's withdrawal or a whitehat rescue (Ronin, for example), late copies and replays after a failure are in the table but not counted. The Euler copy is left out because its operator is unresolved. Before August 2023 there is no mempool archive, so those races rest on in-block evidence only."],
      [n(pd.sum_paid_eth) + " ETH",
        "The bots' direct payments to the block builder plus priority fees, summed over the " + pd.rows + " counted races with a priced take (" + n(pd.sum_paid_eth, 2) + " ETH, " + BVH.pct(pd.pooled_pct, 1) + " of the " + n(pd.sum_gross_eth) + " ETH they took). This is before refunds: some builders passed part of it back, and across the " + ar.rows + " rows where refunds are known the total after refunds is " + n(ar.sum_paid_minus_refund_eth, 2) + " ETH. A few large races carry most of the total. Pre-Merge races paid the miner through the gas price instead."],
      [Math.round(r.pooled_pct) + "%",
        n(r.sum_returned_eth) + " ETH of " + n(r.sum_denominator_eth) + " ETH (" + BVH.pct(r.pooled_pct, 1) + "), pooled over the " + r.rows + " counted races with a priced return figure, including " + r.known_zero_rows + " where nothing came back. It counts money that reached the victim side from the bot and from any builder pass-through, net of an agreed bounty. The median race returned " + BVH.pct(r.median_row_pct, 1) + ". The other " + (c.headline_rows - r.rows) + " counted races have no priced return figure and are left out, not counted as zero."],
      [H.detection_delay.median_ms + " ms",
        "Median of the only " + H.detection_delay.n_measured + " races that can be timed (" + H.detection_delay.headline_rows_measured.length + " of them counted in the headline, " + (H.detection_delay.n_measured - H.detection_delay.headline_rows_measured.length) + " not): from the first public-mempool sighting of the trigger (the attack, the attacker's deploy, or a user's withdrawal) to the first big step-up bid of the builder that won the block. Range " + H.detection_delay.min_ms + " ms to " + BVH.dur(H.detection_delay.max_ms) + "; median over the counted races alone " + H.detection_delay.median_ms_headline_rows + " ms; median upper bound " + BVH.dur(H.detection_delay.median_upper_bound_ms) + ". Bid contents are never visible, so this is an estimate. Most races cannot be timed: the attacker's transaction never showed up in the public archive, or the race predates it. Method: <a href=\"#delay\">builder bid response</a>."]
    ];
    document.getElementById("hn-list").innerHTML = hn.map(function (x) { return "<dt>" + x[0] + "</dt><dd>" + x[1] + "</dd>"; }).join("");
  });
  BVH.json("data/meta.json").then(function (M) {
    document.getElementById("built").textContent = "Built " + M.built.replace("T", " ").replace("Z", " UTC") + ". " + M.n_rows + " races, " + M.n_headline + " counted in the headline across " + M.n_headline_incidents + " incidents. " + M.raw_files.toLocaleString("en-US") + " saved responses (" + (M.raw_bytes / 1e6).toFixed(0) + " MB).";
    var list = [{ path: "data/incidents.json", bytes: M.file_sizes["data/incidents.json"], desc: "One row per race, as shown on the home page" }, { path: "data/evolution.json", bytes: M.file_sizes["data/evolution.json"], desc: "Numbers behind the evolution charts" }, { path: "raw/MANIFEST.json", bytes: M.file_sizes["raw/MANIFEST.json"], desc: "Every saved response: origin, checksum, source address, time fetched" }].concat(M.downloads || []);
    document.getElementById("t-dl").innerHTML = "<thead><tr><th>file</th><th>what is in it</th><th>size</th></tr></thead><tbody>" + list.map(function (x) {
      var kb = x.bytes == null ? "" : x.bytes > 1e6 ? (x.bytes / 1e6).toFixed(1) + " MB" : Math.max(1, Math.round(x.bytes / 1e3)) + " kB";
      return '<tr><td><a href="' + esc(x.path) + '">' + esc(x.path.replace(/^downloads\//, "")) + "</a></td><td>" + esc(x.desc) + "</td><td>" + kb + "</td></tr>";
    }).join("") + "</tbody>";
  }).catch(function (e) { BVH.loadError(document.getElementById("built"), e); });
})();
