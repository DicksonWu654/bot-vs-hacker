/* The Bot Beat the Hacker: code-made art (v3). window.BVHArt.
   Every piece is drawn on a <canvas> at devicePixelRatio from real data in site/data or site/raw, in the Night
   forest palette, and redrawn when its box changes size, so it stays crisp at any width. Nothing animates: the
   picture is complete on first paint and identical under prefers-reduced-motion. API: launch/v3/shared-api.txt.
     <div class="art art-canvas" data-art="gate" data-art-opts='{"id":"makina-2026"}' role="img" aria-label="..."></div>
     BVHArt.draw(el, kind, opts) -> { redraw() }        BVHArt.mountAll(root?) */
(function () {
  "use strict";
  var A = (window.BVHArt = {});
  var C = {
    bg: "#050b08", bg2: "#0a130f", deep: "#071510", moss: "#0f2219",
    trail: "#5fe3a1", streak: "#ff9238", ember: "#e4505c", gold: "#ffe27a", mist: "#a9c2b4", moon: "#8fb0ec", ink: "#e9f1eb"
  };
  A.COLORS = C;

  /* ---------- helpers ---------- */
  function rng(seed) { var s = seed >>> 0 || 1; return function () { s |= 0; s = (s + 0x6D2B79F5) | 0; var t = Math.imul(s ^ (s >>> 15), 1 | s); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }; }
  function hash(str) { var h = 2166136261; str = String(str); for (var i = 0; i < str.length; i++) { h ^= str.charCodeAt(i); h = Math.imul(h, 16777619); } return h >>> 0; }
  function rgba(hex, a) { var n = parseInt(hex.slice(1), 16); return "rgba(" + (n >> 16 & 255) + "," + (n >> 8 & 255) + "," + (n & 255) + "," + a + ")"; }
  var cache = {};
  function getJSON(p) {
    if (!cache[p]) cache[p] = fetch(p, { cache: "force-cache" }).then(function (r) { if (!r.ok) throw new Error(p + " " + r.status); return r.json(); });
    return cache[p];
  }
  A.getJSON = getJSON;

  /* the night sky + floor every piece sits on */
  function ground(g, W, H, horizon, tone) {
    var sky = g.createLinearGradient(0, 0, 0, H);
    sky.addColorStop(0, "#030806"); sky.addColorStop(horizon / H * 0.7, "#06120c"); sky.addColorStop(horizon / H, "#0a1b13"); sky.addColorStop(Math.min(1, horizon / H + 0.02), "#040a07"); sky.addColorStop(1, "#020504");
    g.fillStyle = sky; g.fillRect(0, 0, W, H);
    /* a low band of light on the horizon */
    var hz = g.createLinearGradient(0, horizon - H * 0.22, 0, horizon + H * 0.04);
    hz.addColorStop(0, "rgba(95,227,161,0)"); hz.addColorStop(0.8, tone === "amber" ? "rgba(255,146,56,.07)" : "rgba(95,227,161,.07)"); hz.addColorStop(1, "rgba(95,227,161,0)");
    g.fillStyle = hz; g.fillRect(0, horizon - H * 0.22, W, H * 0.26);
  }
  /* distant trunks: the dark forest, in two depths */
  function trunks(g, W, H, horizon, seed, opts) {
    var r = rng(seed), layers = [[0.5, 0.05, 2.2, 0.55], [0.85, 0.09, 3.6, 0.95]];
    opts = opts || {};
    layers.forEach(function (L, li) {
      var n = Math.round(W / (li ? 34 : 18) * (opts.density == null ? 1 : opts.density));
      for (var i = 0; i < n; i++) {
        var x = r() * W, w = L[2] * (0.5 + r()), top = horizon - H * L[0] * (0.55 + r() * 0.6), a = L[1] * (0.6 + r() * 0.8);
        if (opts.clear && x > opts.clear[0] && x < opts.clear[1]) continue;
        var gr = g.createLinearGradient(0, top, 0, horizon);
        gr.addColorStop(0, rgba("#1d3a2b", 0)); gr.addColorStop(0.35, rgba("#1d3a2b", a * L[3])); gr.addColorStop(1, rgba("#2a4e3b", a));
        g.fillStyle = gr; g.fillRect(x, top, w, horizon - top);
      }
    });
  }
  /* wet floor: faint horizontal sheen lines below the horizon */
  function floorSheen(g, W, H, horizon, seed) {
    var r = rng(seed + 7);
    for (var i = 0; i < 70; i++) {
      var y = horizon + Math.pow(r(), 1.8) * (H - horizon), x = r() * W, w = 20 + r() * 220 * (1 + (y - horizon) / (H - horizon));
      g.fillStyle = "rgba(169,194,180," + (0.015 + r() * 0.035).toFixed(3) + ")";
      g.fillRect(x, y, w, 1);
    }
  }
  function fade(g, W, H, side) {
    if (!side || side === "none") return;
    var gr;
    if (side === "left") { gr = g.createLinearGradient(0, 0, W * 0.62, 0); gr.addColorStop(0, "rgba(5,11,8,.97)"); gr.addColorStop(0.55, "rgba(5,11,8,.8)"); gr.addColorStop(1, "rgba(5,11,8,0)"); g.fillStyle = gr; g.fillRect(0, 0, W * 0.62, H); }
    if (side === "bottom" || side === "left") { gr = g.createLinearGradient(0, H * 0.72, 0, H); gr.addColorStop(0, "rgba(5,11,8,0)"); gr.addColorStop(1, "rgba(5,11,8,1)"); g.fillStyle = gr; g.fillRect(0, H * 0.72, W, H * 0.28); }
  }
  function glowLine(g, pts, color, width, blur, alpha) {
    g.save(); g.globalCompositeOperation = "lighter"; g.lineCap = "round"; g.lineJoin = "round";
    [[blur * 2.2, width * 3.2, alpha * 0.22], [blur, width * 1.6, alpha * 0.45], [0, width, alpha]].forEach(function (p) {
      g.shadowColor = color; g.shadowBlur = p[0]; g.strokeStyle = rgba(color, p[2]); g.lineWidth = p[1];
      g.beginPath(); g.moveTo(pts[0][0], pts[0][1]); for (var i = 1; i < pts.length; i++) g.lineTo(pts[i][0], pts[i][1]); g.stroke();
    });
    g.restore();
  }
  function bezierPts(p0, p1, p2, p3, n) { var o = []; for (var i = 0; i <= n; i++) { var t = i / n, u = 1 - t; o.push([u * u * u * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t * t * t * p3[0], u * u * u * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t * t * t * p3[1]]); } return o; }
  /* a trail whose light grows toward its head */
  function streak(g, pts, color, w0, w1) {
    g.save(); g.globalCompositeOperation = "lighter"; g.lineCap = "round";
    for (var i = 1; i < pts.length; i++) {
      var f = i / (pts.length - 1), w = w0 + (w1 - w0) * f;
      g.shadowColor = color; g.shadowBlur = 6 + 18 * f;
      g.strokeStyle = rgba(color, 0.08 + 0.75 * f * f); g.lineWidth = w;
      g.beginPath(); g.moveTo(pts[i - 1][0], pts[i - 1][1]); g.lineTo(pts[i][0], pts[i][1]); g.stroke();
    }
    var h = pts[pts.length - 1];
    var rg = g.createRadialGradient(h[0], h[1], 0, h[0], h[1], w1 * 6);
    rg.addColorStop(0, "rgba(255,255,255,.95)"); rg.addColorStop(0.18, rgba(color, 0.85)); rg.addColorStop(1, rgba(color, 0));
    g.shadowBlur = 0; g.fillStyle = rg; g.beginPath(); g.arc(h[0], h[1], w1 * 6, 0, Math.PI * 2); g.fill();
    g.restore();
  }
  function bloom(g, x, y, r, color, a) {
    g.save(); g.globalCompositeOperation = "lighter";
    var rg = g.createRadialGradient(x, y, 0, x, y, r); rg.addColorStop(0, rgba(color, a)); rg.addColorStop(1, rgba(color, 0));
    g.fillStyle = rg; g.fillRect(x - r, y - r, 2 * r, 2 * r); g.restore();
  }

  /* ================================================================ kinds */
  var K = {};

  /* the block as a lit gate made of its transaction slivers (block order: up the left pillar, across, down the right) */
  K.gate = {
    data: function (o) { return getJSON("data/incident/" + (o.id || "makina-2026") + ".json"); },
    draw: function (g, W, H, D, o) {
      var strip = (D && D.strip) || [], n = strip.length || 105, seed = hash(o.id || "gate");
      var horizon = H * (W < 700 ? 0.74 : 0.7);
      ground(g, W, H, horizon);
      var cx = o.side === "center" || W < 700 ? W * 0.5 : W * (o.x || 0.69);
      var gh = Math.min(H * 0.64, W * (W < 700 ? 0.9 : 0.46)), gw = gh * 0.6, th = gw * 0.17;
      var x0 = cx - gw / 2, x1 = cx + gw / 2, top = horizon - gh;
      trunks(g, W, H, horizon, seed, { clear: [x0 - th, x1 + th], density: o.density });
      /* light through the doorway */
      var door = g.createLinearGradient(0, top, 0, horizon);
      door.addColorStop(0, "rgba(95,227,161,.05)"); door.addColorStop(0.55, "rgba(169,233,200,.16)"); door.addColorStop(1, "rgba(233,241,235,.32)");
      g.fillStyle = door; g.fillRect(x0 + th, top + th, gw - 2 * th, gh - th);
      bloom(g, cx, horizon - gh * 0.12, gh * 0.75, C.trail, 0.13);
      bloom(g, cx, horizon, gw * 0.9, C.ink, 0.12);
      /* slivers: up the left pillar, across the lintel, down the right pillar */
      var nL = Math.round(n * 0.38), nT = Math.round(n * 0.24), nR = n - nL - nT;
      var r = rng(seed + 3), rects = [];
      function role(i) { var s = strip[i]; return s ? s[2] : ""; }
      var gap = Math.max(1, gh / (nL * 7));
      for (var i = 0; i < nL; i++) { var hh = (gh - th) / nL; rects.push([x0, horizon - (i + 1) * hh + gap / 2, th, hh - gap, i]); }
      for (i = 0; i < nT; i++) { var ww = gw / nT; rects.push([x0 + i * ww + gap / 2, top, ww - gap, th, nL + i]); }
      for (i = 0; i < nR; i++) { var h2 = (gh - th) / nR; rects.push([x1 - th, top + th + i * h2 + gap / 2, th, h2 - gap, nL + nT + i]); }
      /* each sliver is dark glass with a line of light inside it; a few burn brighter (the green trail) */
      g.save();
      rects.forEach(function (q) {
        var rl = role(q[4]), a = 0.22 + r() * 0.5, hot = r() < 0.14, vert = q[3] > q[2];
        if (rl === "bot") return;
        g.shadowBlur = 0; g.fillStyle = rl === "builder" ? "rgba(70,58,12,.95)" : "rgba(13,31,23,.96)"; g.fillRect(q[0], q[1], q[2], q[3]);
        g.globalCompositeOperation = "lighter";
        var col = rl === "builder" ? C.gold : hot ? C.trail : C.mist, al = rl === "builder" ? 1 : hot ? Math.min(1, a + 0.35) : a * 0.75;
        g.shadowColor = col; g.shadowBlur = rl === "builder" || hot ? 12 : 4; g.fillStyle = rgba(col, al);
        if (vert) g.fillRect(q[0] + q[2] / 2 - 0.9, q[1] + 1, 1.8, q[3] - 2); else g.fillRect(q[0] + 2, q[1] + q[3] / 2 - 0.9, q[2] - 4, 1.8);
        g.globalCompositeOperation = "source-over";
      });
      /* the inner edge of the frame catches the doorway light */
      g.shadowBlur = 0; g.fillStyle = "rgba(169,233,200,.18)";
      g.fillRect(x0 + th - 1, top + th, 1, gh - th); g.fillRect(x1 - th, top + th, 1, gh - th); g.fillRect(x0 + th, top + th - 1, gw - 2 * th, 1);
      g.restore();
      /* position 0: the amber streak's light, the brightest thing in the scene */
      var p0 = rects.filter(function (q) { return role(q[4]) === "bot"; })[0] || rects[0];
      bloom(g, p0[0] + p0[2] / 2, p0[1] + p0[3] / 2, th * 4.2, C.streak, 0.55);
      g.save(); g.shadowColor = C.streak; g.shadowBlur = 26; g.fillStyle = "#ffb26b"; g.fillRect(p0[0] - 1, p0[1] - 1, p0[2] + 2, p0[3] + 2); g.fillStyle = "#fff1dc"; g.fillRect(p0[0] + 2, p0[1] + p0[3] * 0.3, p0[2] - 4, p0[3] * 0.4); g.restore();
      /* reflection of the gate on the wet floor */
      g.save(); g.globalAlpha = 0.22; g.translate(0, horizon * 2); g.scale(1, -1);
      rects.forEach(function (q) { var rl = role(q[4]); if (q[1] + q[3] < horizon - gh * 0.45) return; g.fillStyle = rl === "bot" ? C.streak : rl === "builder" ? C.gold : rgba(C.mist, 0.35); g.fillRect(q[0], q[1], q[2], q[3]); });
      g.restore();
      var rf = g.createLinearGradient(0, horizon, 0, horizon + gh * 0.5); rf.addColorStop(0, "rgba(4,10,7,0)"); rf.addColorStop(1, "rgba(4,10,7,.96)");
      g.fillStyle = rf; g.fillRect(0, horizon, W, gh * 0.5 + 2);
      floorSheen(g, W, H, horizon, seed);
      /* the two lights racing to the gate: the attacker's trail (ember) behind, the bot's amber streak arriving first */
      if (o.trails !== false) {
        var doorX = cx, doorY = horizon - 2, sx = W < 700 ? -W * 0.1 : cx - gw * 2.6;
        var amber = bezierPts([sx + gw * 0.2, H * 1.04], [cx - gw * 0.9, H * 0.98], [doorX - gw * 0.35, horizon + gh * 0.08], [doorX - th * 0.2, doorY], 60);
        var green = bezierPts([sx - gw * 0.4, H * 1.02], [cx - gw * 1.5, H * 0.95], [doorX - gw * 0.95, horizon + gh * 0.18], [doorX - gw * 0.52, horizon + gh * 0.075], 60);
        streak(g, green, C.trail, 0.6, W < 700 ? 2.4 : 3.2);
        streak(g, amber, C.streak, 0.8, W < 700 ? 3 : 4.2);
      }
      fade(g, W, H, o.fade);
    }
  };

  /* bids as rising light columns on a wet floor, from a race's real relay bids */
  K.columns = {
    data: function (o) { return getJSON("data/incident/" + (o.id || "makina-2026") + ".json"); },
    draw: function (g, W, H, D, o) {
      var Au = (D && D.auction) || {}, B = Au.bids || {}, ser = B.series || [], Wn = Au.winner || {}, seed = hash(o.id || "cols");
      var winIdx = Wn.builder && B.builders ? B.builders.indexOf(Wn.builder) : -1;
      var horizon = H * 0.66;
      ground(g, W, H, horizon, "amber");
      trunks(g, W, H, horizon, seed, { density: 0.7 });
      if (!ser.length) return;
      var t0 = ser[0][0], t1 = ser[ser.length - 1][0], mx = 0;
      ser.forEach(function (p) { if (p[1] > mx) mx = p[1]; });
      var full = o.side === "full" || W < 700, xa = full ? W * 0.04 : W * 0.4, xb = W * 0.97;
      var lanes = Math.max(4, (B.builders || []).length), r = rng(seed + 11);
      /* each builder gets a depth lane: far lanes are smaller and dimmer */
      var cols = ser.map(function (p) {
        var lane = ((p[2] * 7919) % lanes) / lanes, z = 0.35 + 0.65 * lane, isW = p[2] === winIdx;
        if (isW) z = 1;
        var f = (p[0] - t0) / Math.max(1, t1 - t0);
        /* time runs left to right, squeezed toward the right where the war happens */
        var x = xa + (xb - xa) * Math.pow(f, 2.2) + (r() - 0.5) * 6;
        var base = horizon + (H - horizon) * 0.55 * z, h = (base - H * 0.07) * (p[1] / mx) * z;
        return { x: x, base: base, h: h, z: z, w: isW, eth: p[1] };
      }).sort(function (a, b) { return a.z - b.z; });
      g.save(); g.globalCompositeOperation = "lighter";
      cols.forEach(function (c) {
        var col = c.w ? C.streak : C.mist, wd = (c.w ? 2.4 : 1.4) * (0.6 + c.z * 0.7), a = (c.w ? 0.75 : 0.32) * (0.45 + c.z * 0.55);
        if (c.h > 1.5) {
          var gr = g.createLinearGradient(0, c.base - c.h, 0, c.base);
          gr.addColorStop(0, rgba(col, a)); gr.addColorStop(0.25, rgba(col, a * 0.45)); gr.addColorStop(1, rgba(col, a * 0.08));
          g.fillStyle = gr; g.fillRect(c.x - wd / 2, c.base - c.h, wd, c.h);
          /* reflection */
          var rf = g.createLinearGradient(0, c.base, 0, c.base + Math.min(c.h * 0.35, 120));
          rf.addColorStop(0, rgba(col, a * 0.35)); rf.addColorStop(1, rgba(col, 0));
          g.fillStyle = rf; g.fillRect(c.x - wd / 2, c.base + 2, wd, Math.min(c.h * 0.35, 120));
        }
        /* the point of light at the top of each bid */
        g.shadowColor = col; g.shadowBlur = c.w ? 14 : 6;
        g.fillStyle = c.w ? "#ffd2a8" : rgba(C.ink, 0.55 * (0.4 + c.z * 0.6));
        g.beginPath(); g.arc(c.x, c.base - c.h, (c.w ? 1.9 : 1.1) * (0.6 + c.z * 0.6), 0, Math.PI * 2); g.fill();
        g.shadowBlur = 0;
      });
      g.restore();
      /* the winning bid: a lamp */
      if (Wn.eth != null && Wn.t_ms != null) {
        var wf = (Wn.t_ms - t0) / Math.max(1, t1 - t0), wx = xa + (xb - xa) * Math.pow(Math.max(0, Math.min(1, wf)), 2.2), wbase = horizon + (H - horizon) * 0.55, wy = wbase - (wbase - H * 0.07) * (Wn.eth / mx);
        bloom(g, wx, wy, H * 0.12, C.gold, 0.35); bloom(g, wx, wy, 10, "#ffffff", 0.9);
      }
      floorSheen(g, W, H, horizon, seed);
      fade(g, W, H, o.fade);
    }
  };

  /* a forest of blocks: one tree per race, its bot's transaction glowing at its place up the trunk */
  K.forest = {
    data: function () { return getJSON("data/incidents.json"); },
    draw: function (g, W, H, rows, o) {
      rows = (rows || []).filter(function (r) { return (o.all || r.headline) && r.date; }).sort(function (a, b) { return a.date < b.date ? -1 : 1; });
      var seed = hash("forest"), horizon = H * 0.8;
      ground(g, W, H, horizon);
      trunks(g, W, H, horizon, seed, { density: 0.8 });
      if (!rows.length) return;
      var full = o.side === "full" || W < 700, xa = full ? W * 0.06 : W * 0.42, xb = W * 0.96, r = rng(seed + 5);
      var mx = 0; rows.forEach(function (q) { if (q.gross_eth > mx) mx = q.gross_eth; });
      var step = (xb - xa) / rows.length;
      rows.forEach(function (q, i) {
        var x = xa + step * (i + 0.5) + (r() - 0.5) * step * 0.3, near = 0.7 + r() * 0.3;
        var h = (horizon - H * 0.1) * (0.38 + 0.62 * Math.sqrt((q.gross_eth || mx * 0.05) / mx)) * near, w = Math.max(5, Math.min(16, step * 0.32)) * near;
        var ns = Math.max(10, Math.round(h / 9)), sh = h / ns, botAt = Math.min(ns - 1, q.bot_idx || 0);
        for (var k = 0; k < ns; k++) {
          var y = horizon - (k + 1) * sh;
          g.fillStyle = k === botAt ? C.streak : rgba(k % 5 === 0 ? C.trail : C.mist, (0.1 + r() * 0.2) * (1 - k / ns * 0.6));
          if (k === botAt) { g.save(); g.shadowColor = C.streak; g.shadowBlur = 22; g.fillRect(x - w / 2, y + 1, w, sh - 2); g.restore(); bloom(g, x, y + sh / 2, w * 3.2, C.streak, 0.4); }
          else g.fillRect(x - w / 2, y + 1, w, sh - 2);
        }
        /* reflection */
        var rf = g.createLinearGradient(0, horizon, 0, horizon + h * 0.3); rf.addColorStop(0, rgba(C.streak, 0.32)); rf.addColorStop(1, rgba(C.streak, 0));
        g.fillStyle = rf; g.fillRect(x - w / 2, horizon + 2, w, h * 0.3);
      });
      floorSheen(g, W, H, horizon, seed);
      fade(g, W, H, o.fade);
    }
  };

  /* calldata code rain: a real transaction's input, one falling column per 32-byte word; differing words glow amber */
  K.rain = {
    data: function (o) { return getJSON(o.tx || "raw/rpc/tx_0xbce5b8548db486c561948e8a177c8ccaa72810f972cee3909ea50af015a60ad8.json"); },
    draw: function (g, W, H, T, o) {
      var input = (T && T.result && T.result.input) || (T && T.input) || "", hex = input.replace(/^0x/, "");
      var sel = hex.slice(0, 8), body = hex.slice(8), words = [];
      for (var i = 0; i + 64 <= body.length; i += 64) words.push(body.slice(i, i + 64));
      var diff = {}; (o.diff || [2, 5, 9]).forEach(function (d) { diff[d] = 1; });
      var seed = hash(sel || "rain"), r = rng(seed);
      g.fillStyle = C.bg; g.fillRect(0, 0, W, H);
      var bgG = g.createRadialGradient(W * 0.7, H * 0.4, 0, W * 0.7, H * 0.4, Math.max(W, H) * 0.7); bgG.addColorStop(0, "rgba(95,227,161,.06)"); bgG.addColorStop(1, "rgba(95,227,161,0)");
      g.fillStyle = bgG; g.fillRect(0, 0, W, H);
      if (!words.length) return;
      var full = o.side === "full" || W < 700, xa = full ? W * 0.03 : W * 0.4, xb = W * 0.98;
      var n = words.length, cw = (xb - xa) / n, fs = Math.max(9, Math.min(17, cw * 0.62)), lh = fs * 1.12;
      g.font = "500 " + fs.toFixed(1) + "px 'Spline Sans Mono', ui-monospace, Menlo, monospace"; g.textAlign = "center"; g.textBaseline = "middle";
      words.forEach(function (wd, k) {
        var x = xa + cw * (k + 0.5), d = !!diff[k], head = H * (0.2 + r() * 0.75) + (d ? H * 0.05 : 0), len = Math.min(wd.length, Math.round((head / lh)));
        /* the word reads downward to its head; the head is brightest, the tail fades into the dark */
        for (var j = 0; j < len; j++) {
          var ch = wd.charAt(wd.length - 1 - j), y = head - j * lh, f = 1 - j / len;
          if (y < -lh) break;
          var a = d ? 0.15 + 0.85 * Math.pow(f, 1.4) : (ch === "0" ? 0.05 : 0.1) + 0.42 * Math.pow(f, 2.2);
          g.fillStyle = d ? rgba(j === 0 ? "#ffe2c4" : C.streak, a) : rgba(j === 0 ? C.ink : C.trail, a);
          if (j === 0) { g.save(); g.shadowColor = d ? C.streak : C.trail; g.shadowBlur = d ? 16 : 8; g.fillText(ch, x, y); g.restore(); }
          else g.fillText(ch, x, y);
        }
        if (d) bloom(g, x, head, cw * 2.2, C.streak, 0.32);
      });
      fade(g, W, H, o.fade);
    }
  };

  /* the public mempool as fog: M attacker transactions as points in the fog, N of them lit (seen in public) */
  K.fog = {
    data: function (o) { return o.total ? Promise.resolve(null) : getJSON("data/evolution.json"); },
    draw: function (g, W, H, E, o) {
      var m = (E && E.measured) || {}, total = o.total || ((m.n || 203) - (m.unknown || 0)), lit = o.lit != null ? o.lit : (m.public != null ? m.public : 9);
      var seed = hash("fog" + total + "/" + lit), r = rng(seed), horizon = H * 0.78;
      ground(g, W, H, horizon);
      trunks(g, W, H, horizon, seed, { density: 0.9 });
      /* fog banks */
      g.save(); g.globalCompositeOperation = "lighter";
      for (var i = 0; i < 26; i++) { var fx = r() * W, fy = H * (0.25 + r() * 0.6), fr = Math.max(W, H) * (0.12 + r() * 0.22); var rg = g.createRadialGradient(fx, fy, 0, fx, fy, fr); rg.addColorStop(0, "rgba(169,194,180," + (0.008 + r() * 0.016).toFixed(3) + ")"); rg.addColorStop(1, "rgba(169,194,180,0)"); g.fillStyle = rg; g.fillRect(fx - fr, fy - fr, 2 * fr, 2 * fr); }
      g.restore();
      var full = o.side === "full" || W < 700, xa = full ? W * 0.04 : W * 0.4, xb = W * 0.97, ya = H * 0.12, yb = H * 0.86;
      var litSet = {}, pts = [];
      for (i = 0; i < total; i++) pts.push([xa + r() * (xb - xa), ya + Math.pow(r(), 0.8) * (yb - ya)]);
      while (Object.keys(litSet).length < Math.min(lit, total)) litSet[Math.floor(r() * total)] = 1;
      pts.forEach(function (p, k) {
        if (litSet[k]) return;
        g.fillStyle = "rgba(169,194,180," + (0.14 + r() * 0.14).toFixed(3) + ")"; g.beginPath(); g.arc(p[0], p[1], 1.6, 0, Math.PI * 2); g.fill();
      });
      Object.keys(litSet).forEach(function (k) {
        var p = pts[k]; bloom(g, p[0], p[1], 26, C.ember, 0.4); bloom(g, p[0], p[1], 7, "#ffd9d0", 0.9);
        g.fillStyle = "#fff4f0"; g.beginPath(); g.arc(p[0], p[1], 2.1, 0, Math.PI * 2); g.fill();
      });
      floorSheen(g, W, H, horizon, seed);
      fade(g, W, H, o.fade);
    }
  };

  /* a quiet forest-floor strip: decorative */
  K.floor = {
    data: function () { return Promise.resolve(null); },
    draw: function (g, W, H, _, o) {
      var horizon = H * 0.72, seed = hash("floor" + (o.tone || ""));
      ground(g, W, H, horizon, o.tone);
      trunks(g, W, H, horizon, seed, { density: 1.1 });
      var r = rng(seed + 2);
      g.save(); g.globalCompositeOperation = "lighter";
      for (var i = 0; i < Math.round(W / 28); i++) {
        var x = r() * W, h = (horizon * 0.15) + Math.pow(r(), 3) * horizon * 0.6, col = r() < 0.18 ? C.streak : C.trail, a = 0.05 + r() * 0.16;
        var gr = g.createLinearGradient(0, horizon - h, 0, horizon); gr.addColorStop(0, rgba(col, a)); gr.addColorStop(1, rgba(col, a * 0.1));
        g.fillStyle = gr; g.fillRect(x, horizon - h, 1.2, h);
      }
      g.restore();
      floorSheen(g, W, H, horizon, seed);
      fade(g, W, H, o.fade);
    }
  };
  A.KINDS = Object.keys(K);

  /* ---------- mounting ---------- */
  A.draw = function (el, kind, opts) {
    var k = K[kind]; if (!k) throw new Error("BVHArt: unknown kind " + kind);
    opts = opts || {};
    var cv = el.querySelector("canvas.art-cv");
    if (!cv) { cv = document.createElement("canvas"); cv.className = "art-cv"; cv.setAttribute("aria-hidden", "true"); el.appendChild(cv); }
    el.classList.add("art-canvas"); el.setAttribute("data-art-kind", kind);
    var data = null, lastW = 0, lastH = 0, ready = false;
    function paint() {
      var w = Math.round(el.clientWidth), h = Math.round(el.clientHeight);
      if (!w || !h) return;
      if (ready && w === lastW && Math.abs(h - lastH) < 2) return;
      lastW = w; lastH = h;
      var dpr = Math.min(window.devicePixelRatio || 1, 3);
      var s = Math.min(dpr, 4096 / w, 4096 / h);
      cv.width = Math.round(w * s); cv.height = Math.round(h * s);
      cv.style.width = w + "px"; cv.style.height = h + "px";
      var g = cv.getContext("2d"); g.setTransform(s, 0, 0, s, 0, 0);
      try { k.draw(g, w, h, data, opts); el.setAttribute("data-art-drawn", "1"); } catch (e) { if (window.console) console.warn("BVHArt", kind, e); }
      ready = true;
    }
    k.data(opts).then(function (d) { data = d; }, function () { data = null; }).then(function () { ready = false; paint(); });
    /* paint the ground immediately so there is never an empty box */
    paint();
    if ("ResizeObserver" in window) { var to; new ResizeObserver(function () { clearTimeout(to); to = setTimeout(paint, 60); }).observe(el); }
    else window.addEventListener("resize", paint);
    if (kind === "rain" && document.fonts && document.fonts.ready) document.fonts.ready.then(function () { lastW = 0; paint(); });
    return { redraw: function () { lastW = 0; paint(); } };
  };
  A.mountAll = function (root) {
    Array.prototype.forEach.call((root || document).querySelectorAll("[data-art]:not([data-art-kind])"), function (el) {
      var o = {}; try { o = JSON.parse(el.getAttribute("data-art-opts") || "{}"); } catch (e) { /* keep defaults */ }
      A.draw(el, el.getAttribute("data-art"), o);
    });
  };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", function () { A.mountAll(); });
  else A.mountAll();
})();
