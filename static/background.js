/* Animated background: a banknote flies in from the top right corner, smashes
   into pennies, dimes and quarters, and the coins keep bouncing. After a while
   the coins fade out and a new note drops in.

   The artwork is drawn in code and cached as images at start-up, so the
   animation itself is cheap. The note is a fictional "Expense Tracker Reserve
   Note" with a generic engraved bust: realistic in style, not a copy of any
   real currency.

   Pure canvas, no libraries. Respects prefers-reduced-motion (draws one still
   frame) and pauses automatically when the tab is hidden. */
(function () {
  "use strict";

  var canvas = document.getElementById("bg-canvas");
  if (!canvas || !canvas.getContext) return;
  var ctx = canvas.getContext("2d");
  var reduceMotion =
    window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  var TAU = Math.PI * 2;
  var DISPLAY_FONT = '"Bodoni Moda", "Bodoni 72", Didot, Georgia, serif';

  var GRAVITY = 1800;       // pixels per second squared
  var FLY_TIME = 1.6;       // seconds for the note to arrive
  var SMASH_TIME = 0.3;     // seconds the note takes to burst
  var BOUNCE_TIME = 16;     // seconds the coins bounce before fading
  var FADE_TIME = 1.3;      // seconds the coins take to fade out
  var PAUSE_TIME = 0.5;     // seconds of empty screen before the next note

  // Radii keep the real US proportions (quarter 1.0, penny 0.79, dime 0.74), drawn big and bold.
  var COIN_TYPES = [
    { name: "penny", words: ["ONE", "CENT"], r: 29, weight: 12, ticks: 0,
      light: "#f7bc8c", base: "#bf6824", dark: "#5a2a0b", hi: "#ffd9b6", lo: "#3e1a05",
      edgeA: "#8c4818", edgeB: "#d98a45" },
    { name: "dime", words: ["ONE", "DIME"], r: 27, weight: 9, ticks: 118,
      light: "#f8fafd", base: "#a9b2c4", dark: "#4a556d", hi: "#ffffff", lo: "#323b50",
      edgeA: "#8590a6", edgeB: "#eef2f8" },
    { name: "quarter", words: ["QUARTER", "DOLLAR"], r: 37, weight: 9, ticks: 119,
      light: "#ffffff", base: "#b3bccd", dark: "#515c75", hi: "#ffffff", lo: "#323b50",
      edgeA: "#8a95ab", edgeB: "#f2f5fb" }
  ];

  var SPRITE_SIZE = 256;    // coin face artwork is drawn at this many pixels across
  var BILL_W = 1200, BILL_H = 510;

  var W = 0, H = 0, scale = 1;
  var phase = "pause", phaseTime = 0;
  var bill = null, coins = [], shards = [];
  var flash = 0, shake = 0, impact = { x: 0, y: 0 };
  var lastTime = 0;
  var billSprite = null, coinSprites = [];        // full size artwork, built once
  var billScaled = null, coinScaled = [], edgeGrads = [];   // display size copies, rebuilt on resize
  var dprNow = 1;

  function rand(min, max) { return min + Math.random() * (max - min); }
  function clamp(v, lo, hi) { return Math.max(lo, Math.min(hi, v)); }
  function easeOut(p) { return 1 - Math.pow(1 - p, 3); }
  function makeRng(seed) {
    var s = seed >>> 0;
    return function () { s = (s * 1664525 + 1013904223) >>> 0; return s / 4294967296; };
  }
  function makeCanvas(w, h) {
    var c = document.createElement("canvas");
    c.width = w; c.height = h;
    return c;
  }

  /* ---------- artwork helpers ---------- */

  function roundRectPath(g, x, y, w, h, r) {
    g.beginPath();
    g.moveTo(x + r, y);
    g.arcTo(x + w, y, x + w, y + h, r);
    g.arcTo(x + w, y + h, x, y + h, r);
    g.arcTo(x, y + h, x, y, r);
    g.arcTo(x, y, x + w, y, r);
    g.closePath();
  }

  // Generic engraved bust in profile, unit sized around (0,0). Not a real person.
  function bustPath(g) {
    g.beginPath();
    g.moveTo(-0.32, 0.52);
    g.bezierCurveTo(-0.36, 0.32, -0.32, 0.18, -0.23, 0.10);
    g.bezierCurveTo(-0.36, 0.00, -0.38, -0.22, -0.27, -0.38);
    g.bezierCurveTo(-0.17, -0.53, 0.07, -0.55, 0.19, -0.42);
    g.bezierCurveTo(0.23, -0.34, 0.25, -0.28, 0.28, -0.24);
    g.lineTo(0.34, -0.12);
    g.bezierCurveTo(0.36, -0.08, 0.33, -0.05, 0.29, -0.04);
    g.bezierCurveTo(0.31, -0.02, 0.30, 0.01, 0.28, 0.03);
    g.bezierCurveTo(0.30, 0.07, 0.29, 0.11, 0.25, 0.14);
    g.bezierCurveTo(0.21, 0.19, 0.13, 0.19, 0.09, 0.18);
    g.bezierCurveTo(0.13, 0.26, 0.21, 0.34, 0.35, 0.40);
    g.lineTo(0.35, 0.52);
    g.closePath();
  }

  // Relief effect: dark offset, light offset, then the base colour on top.
  function embossed(g, base, hi, lo, depth, fn) {
    g.save(); g.translate(depth, depth * 1.2); g.fillStyle = lo; fn(); g.restore();
    g.save(); g.translate(-depth * 0.7, -depth * 0.9); g.fillStyle = hi; fn(); g.restore();
    g.fillStyle = base; fn();
  }

  // Text laid along a circle. bottom=false reads along the top, true along the bottom.
  function curvedText(g, text, radius, bottom) {
    var widths = [], total = 0, i;
    for (i = 0; i < text.length; i++) {
      widths.push(g.measureText(text[i]).width);
      total += widths[i];
    }
    var arc = total / radius, run = 0;
    g.textAlign = "center";
    g.textBaseline = "middle";
    for (i = 0; i < text.length; i++) {
      var mid = run + widths[i] / 2;
      var a = bottom ? Math.PI / 2 + arc / 2 - mid / radius : -Math.PI / 2 - arc / 2 + mid / radius;
      g.save();
      g.translate(Math.cos(a) * radius, Math.sin(a) * radius);
      g.rotate(bottom ? a - Math.PI / 2 : a + Math.PI / 2);
      g.fillText(text[i], 0, 0);
      g.restore();
      run += widths[i];
    }
  }

  function laurel(g, mirror, R) {
    for (var i = 0; i < 7; i++) {
      var a = Math.PI * (0.62 + i * 0.075);
      var x = Math.cos(a) * R * 0.72, y = Math.sin(a) * R * 0.72;
      g.save();
      g.translate(mirror ? -x : x, y);
      g.rotate((mirror ? -1 : 1) * (a + Math.PI / 2 + 0.5));
      g.beginPath();
      g.ellipse(0, 0, R * 0.075, R * 0.032, 0, 0, TAU);
      g.fill();
      g.restore();
    }
  }

  /* ---------- coin faces ---------- */

  function buildCoinFace(type, reverse) {
    var S = SPRITE_SIZE, R = S / 2 - 3;
    var cv = makeCanvas(S, S), g = cv.getContext("2d");
    g.translate(S / 2, S / 2);

    // metal body
    var body = g.createRadialGradient(-R * 0.38, -R * 0.42, R * 0.08, 0, 0, R);
    body.addColorStop(0, type.light);
    body.addColorStop(0.5, type.base);
    body.addColorStop(1, type.dark);
    g.beginPath(); g.arc(0, 0, R, 0, TAU); g.fillStyle = body; g.fill();

    // fine machine turned lines in the field
    g.lineWidth = 1;
    for (var k = 1; k < 9; k++) {
      g.beginPath(); g.arc(0, 0, R * 0.84 * k / 9, 0, TAU);
      g.strokeStyle = "rgba(0, 0, 0, 0.045)"; g.stroke();
    }

    // raised rim: lit top left, shaded bottom right
    var rim = g.createLinearGradient(-R, -R, R, R);
    rim.addColorStop(0, type.hi); rim.addColorStop(0.5, type.base); rim.addColorStop(1, type.lo);
    g.beginPath(); g.arc(0, 0, R * 0.935, 0, TAU);
    g.lineWidth = R * 0.13; g.strokeStyle = rim; g.stroke();
    g.beginPath(); g.arc(0, 0, R * 0.86, 0, TAU);
    g.lineWidth = 2.6; g.strokeStyle = "rgba(0, 0, 0, 0.45)"; g.stroke();
    g.beginPath(); g.arc(0, 0, R * 0.885, 0, TAU);
    g.lineWidth = 1.4; g.strokeStyle = "rgba(255, 255, 255, 0.45)"; g.stroke();

    // relief artwork
    g.font = "800 " + Math.round(R * 0.15) + "px " + DISPLAY_FONT;
    if (!reverse) {
      embossed(g, type.light, type.hi, type.lo, R * 0.014, function () { curvedText(g, "LIBERTY", R * 0.7, false); });
      embossed(g, type.light, type.hi, type.lo, R * 0.014, function () { curvedText(g, "2026", R * 0.7, true); });
      embossed(g, type.light, type.hi, type.lo, R * 0.02, function () {
        g.save(); g.translate(R * 0.02, R * 0.04); g.scale(R * 0.74, R * 0.74); bustPath(g); g.restore(); g.fill();
      });
    } else {
      g.font = "800 " + Math.round(R * 0.115) + "px " + DISPLAY_FONT;
      embossed(g, type.light, type.hi, type.lo, R * 0.014, function () { curvedText(g, "IN BUDGET WE TRUST", R * 0.74, false); });
      embossed(g, type.light, type.hi, type.lo, R * 0.016, function () { laurel(g, false, R); laurel(g, true, R); });
      var big = type.words[0] === "QUARTER" ? 0.2 : 0.3;
      g.font = "800 " + Math.round(R * big) + "px " + DISPLAY_FONT;
      embossed(g, type.light, type.hi, type.lo, R * 0.018, function () {
        g.textAlign = "center"; g.textBaseline = "middle";
        g.fillText(type.words[0], 0, -R * 0.17);
        g.fillText(type.words[1], 0, R * 0.17);
      });
    }

    // soft highlight and a bold dark outline
    var shine = g.createRadialGradient(-R * 0.45, -R * 0.5, 0, -R * 0.45, -R * 0.5, R * 0.9);
    shine.addColorStop(0, "rgba(255, 255, 255, 0.32)");
    shine.addColorStop(1, "rgba(255, 255, 255, 0)");
    g.beginPath(); g.arc(0, 0, R, 0, TAU); g.fillStyle = shine; g.fill();
    g.beginPath(); g.arc(0, 0, R - 1.2, 0, TAU);
    g.lineWidth = 2.6; g.strokeStyle = type.lo; g.stroke();
    return cv;
  }

  /* ---------- the banknote ---------- */

  function rosette(g, cx, cy, R, n, alpha) {
    g.save();
    g.lineWidth = 0.8;
    g.strokeStyle = "rgba(37, 98, 66, " + alpha + ")";
    for (var k = 0; k < n; k++) {
      var a = (k / n) * TAU;
      g.beginPath();
      g.arc(cx + Math.cos(a) * R * 0.42, cy + Math.sin(a) * R * 0.42, R * 0.58, 0, TAU);
      g.stroke();
    }
    g.restore();
  }

  function drawSeal(g, sx, sy, SR, topText, bottomText, glyph, glyphSize, deep) {
    g.beginPath(); g.arc(sx, sy, SR, 0, TAU);
    g.fillStyle = "rgba(236, 241, 224, 0.95)"; g.fill();
    rosette(g, sx, sy, SR, 64, 0.5);
    g.strokeStyle = deep;
    g.lineWidth = SR * 0.04; g.beginPath(); g.arc(sx, sy, SR, 0, TAU); g.stroke();
    g.lineWidth = 1.4; g.beginPath(); g.arc(sx, sy, SR * 0.895, 0, TAU); g.stroke();
    g.lineWidth = 2; g.beginPath(); g.arc(sx, sy, SR * 0.6, 0, TAU); g.stroke();
    g.save(); g.translate(sx, sy);
    g.font = "700 " + Math.round(SR * 0.145) + "px " + DISPLAY_FONT; g.fillStyle = deep;
    curvedText(g, topText, SR * 0.76, false);
    curvedText(g, bottomText, SR * 0.76, true);
    g.font = "700 " + glyphSize + "px " + DISPLAY_FONT;
    g.textAlign = "center"; g.textBaseline = "middle";
    g.fillStyle = "#1f5238"; g.fillText(glyph, 0, glyphSize * 0.06);
    g.restore();
  }

  function engravedText(g, text, x, y, size, align, fillStyle) {
    g.font = "700 " + size + "px " + DISPLAY_FONT;
    g.textAlign = align; g.textBaseline = "alphabetic";
    g.lineWidth = Math.max(1.5, size * 0.05);
    g.strokeStyle = "#1f5238"; g.lineJoin = "round";
    g.strokeText(text, x, y);
    g.fillStyle = fillStyle; g.fillText(text, x, y);
  }

  function buildBill() {
    var BW = BILL_W, BH = BILL_H;
    var cv = makeCanvas(BW, BH), g = cv.getContext("2d"), rnd = makeRng(20260917);
    var deep = "#256242", i, x, y;
    var spaced = "letterSpacing" in g;

    roundRectPath(g, 0, 0, BW, BH, 9); g.clip();

    // aged paper with a pale green and peach wash
    var paper = g.createLinearGradient(0, 0, BW, BH);
    paper.addColorStop(0, "#dbe6cf"); paper.addColorStop(0.5, "#eef0df"); paper.addColorStop(1, "#d6e3cb");
    g.fillStyle = paper; g.fillRect(0, 0, BW, BH);
    var washL = g.createLinearGradient(0, 0, BW * 0.4, 0);
    washL.addColorStop(0, "rgba(110, 180, 140, 0.40)"); washL.addColorStop(1, "rgba(110, 180, 140, 0)");
    g.fillStyle = washL; g.fillRect(0, 0, BW, BH);
    var washR = g.createLinearGradient(BW, 0, BW * 0.6, 0);
    washR.addColorStop(0, "rgba(238, 186, 140, 0.36)"); washR.addColorStop(1, "rgba(238, 186, 140, 0)");
    g.fillStyle = washR; g.fillRect(0, 0, BW, BH);

    // paper fibres
    var fibre = ["rgba(60, 120, 90, 0.12)", "rgba(200, 80, 80, 0.10)", "rgba(70, 110, 175, 0.12)"];
    g.lineWidth = 0.8;
    for (i = 0; i < 2600; i++) {
      x = rnd() * BW; y = rnd() * BH;
      var len = 6 + rnd() * 16, ang = rnd() * TAU;
      g.strokeStyle = fibre[i % 3];
      g.beginPath(); g.moveTo(x, y); g.lineTo(x + Math.cos(ang) * len, y + Math.sin(ang) * len); g.stroke();
    }

    // guilloche lacework in the border band
    g.save();
    g.beginPath(); g.rect(0, 0, BW, BH); g.rect(48, 48, BW - 96, BH - 96); g.clip("evenodd");
    g.lineWidth = 1; g.strokeStyle = "rgba(37, 98, 66, 0.6)";
    for (var k = 0; k < 9; k++) {
      var ph = k * 0.7;
      g.beginPath();
      for (x = 0; x <= BW; x += 4) { y = 24 + Math.sin(x * 0.05 + ph) * 12; if (x === 0) g.moveTo(x, y); else g.lineTo(x, y); }
      g.stroke();
      g.beginPath();
      for (x = 0; x <= BW; x += 4) { y = BH - 24 - Math.sin(x * 0.05 + ph) * 12; if (x === 0) g.moveTo(x, y); else g.lineTo(x, y); }
      g.stroke();
      g.beginPath();
      for (y = 0; y <= BH; y += 4) { x = 24 + Math.sin(y * 0.05 + ph) * 12; if (y === 0) g.moveTo(x, y); else g.lineTo(x, y); }
      g.stroke();
      g.beginPath();
      for (y = 0; y <= BH; y += 4) { x = BW - 24 - Math.sin(y * 0.05 + ph) * 12; if (y === 0) g.moveTo(x, y); else g.lineTo(x, y); }
      g.stroke();
    }
    g.restore();

    // frame lines
    g.strokeStyle = deep;
    g.lineWidth = 5; roundRectPath(g, 8, 8, BW - 16, BH - 16, 6); g.stroke();
    g.lineWidth = 2.5; g.strokeRect(48, 48, BW - 96, BH - 96);
    g.lineWidth = 1; g.strokeRect(55, 55, BW - 110, BH - 110);

    // corner rosettes with numerals
    var corners = [[92, 92], [BW - 92, 92], [92, BH - 92], [BW - 92, BH - 92]];
    for (i = 0; i < 4; i++) {
      g.beginPath(); g.arc(corners[i][0], corners[i][1], 66, 0, TAU);
      g.fillStyle = "rgba(236, 241, 224, 0.92)"; g.fill();
      rosette(g, corners[i][0], corners[i][1], 66, 56, 0.55);
      g.beginPath(); g.arc(corners[i][0], corners[i][1], 66, 0, TAU);
      g.lineWidth = 2; g.strokeStyle = deep; g.stroke();
    }
    engravedText(g, "100", 92, 108, 44, "center", "#f3f6ea");
    engravedText(g, "100", BW - 92, 108, 44, "center", "#f3f6ea");
    engravedText(g, "100", 92, BH - 76, 44, "center", "#f3f6ea");
    engravedText(g, "100", BW - 92, BH - 76, 44, "center", "#f3f6ea");

    // title and microprint
    if (spaced) g.letterSpacing = "4px";
    g.font = "700 31px " + DISPLAY_FONT;
    g.textAlign = "center"; g.textBaseline = "alphabetic";
    g.fillStyle = deep;
    g.fillText("EXPENSE TRACKER RESERVE NOTE", BW / 2, 104);
    if (spaced) g.letterSpacing = "2px";
    g.font = "600 9px " + DISPLAY_FONT;
    g.fillStyle = "rgba(37, 98, 66, 0.8)";
    g.fillText("ONE HUNDRED DOLLARS · ONE HUNDRED DOLLARS · ONE HUNDRED DOLLARS · ONE HUNDRED DOLLARS · ONE HUNDRED DOLLARS", BW / 2, 126);
    if (spaced) g.letterSpacing = "6px";
    g.font = "700 42px " + DISPLAY_FONT;
    g.fillStyle = deep;
    g.fillText("ONE HUNDRED DOLLARS", BW / 2, BH - 62);
    if (spaced) g.letterSpacing = "0px";

    // seals
    drawSeal(g, 250, 288, 104, "EXPENSE TRACKER RESERVE", "SERIES 2026", "$", 76, deep);
    drawSeal(g, 940, 228, 64, "RESERVE DISTRICT", "FOR SPENDING", "ET", 40, deep);

    // portrait oval with engraved hatching
    var px = 560, py = 276, rx = 122, ry = 140;
    g.save();
    g.beginPath(); g.ellipse(px, py, rx, ry, 0, 0, TAU); g.clip();
    g.fillStyle = "rgba(226, 235, 215, 1)"; g.fillRect(px - rx, py - ry, rx * 2, ry * 2);
    g.lineWidth = 1; g.strokeStyle = "rgba(37, 98, 66, 0.38)";
    g.beginPath();
    for (x = px - rx; x < px + rx; x += 3) { g.moveTo(x, py - ry); g.lineTo(x, py + ry); }
    g.stroke();
    g.save();
    g.translate(px + 6, py + 34); g.scale(235, 235); bustPath(g);
    g.setTransform(1, 0, 0, 1, 0, 0);
    g.clip();
    g.fillStyle = "rgba(226, 235, 215, 1)"; g.fillRect(px - rx, py - ry, rx * 2, ry * 2);
    g.lineWidth = 1.5; g.strokeStyle = "rgba(24, 78, 52, 0.9)";
    g.beginPath();
    for (x = px - rx; x < px + rx; x += 2.4) { g.moveTo(x, py - ry); g.lineTo(x, py + ry); }
    g.stroke();
    g.lineWidth = 1; g.strokeStyle = "rgba(24, 78, 52, 0.55)";
    g.beginPath();
    for (y = py - ry; y < py + ry; y += 4) { g.moveTo(px - rx, y); g.lineTo(px + rx, y + 40); }
    g.stroke();
    g.restore();
    g.save();
    g.translate(px + 6, py + 34); g.scale(235, 235); bustPath(g);
    g.restore();
    g.lineWidth = 2; g.strokeStyle = "rgba(24, 78, 52, 0.95)"; g.stroke();
    g.restore();
    g.beginPath(); g.ellipse(px, py, rx, ry, 0, 0, TAU);
    g.lineWidth = 7; g.strokeStyle = deep; g.stroke();
    g.beginPath(); g.ellipse(px, py, rx + 9, ry + 9, 0, 0, TAU);
    g.lineWidth = 1.5; g.stroke();

    // blue security ribbon with little coin marks
    var rx0 = 730, rw = 58;
    var rib = g.createLinearGradient(rx0, 0, rx0 + rw, 0);
    rib.addColorStop(0, "#5b97cf"); rib.addColorStop(0.5, "#b3d6f0"); rib.addColorStop(1, "#5b97cf");
    var ribTop = 142, ribH = 262;                  // sits between the title and the bottom line
    g.fillStyle = rib; g.fillRect(rx0, ribTop, rw, ribH);
    g.strokeStyle = "rgba(20, 60, 110, 0.7)"; g.lineWidth = 1.5;
    g.strokeRect(rx0, ribTop, rw, ribH);
    g.strokeStyle = "rgba(255, 255, 255, 0.55)"; g.lineWidth = 1;
    for (y = ribTop + 8; y < ribTop + ribH - 40; y += 46) {
      g.beginPath(); g.arc(rx0 + rw / 2, y + 18, 15, 0, TAU); g.stroke();
      g.font = "700 14px " + DISPLAY_FONT; g.fillStyle = "rgba(255, 255, 255, 0.85)";
      g.textAlign = "center"; g.textBaseline = "middle"; g.fillText("¢", rx0 + rw / 2, y + 19);
    }

    // serial numbers
    g.font = "700 25px 'Courier New', monospace";
    g.textAlign = "left"; g.textBaseline = "alphabetic"; g.fillStyle = "#1c3d68";
    g.fillText("EK 20260917 B", 120, 190);
    g.textAlign = "right";
    g.fillText("EK 20260917 B", BW - 170, 322);

    // colour shifting numeral
    g.font = "800 98px " + DISPLAY_FONT;
    g.textAlign = "right"; g.textBaseline = "alphabetic";
    var shift = g.createLinearGradient(BW - 400, 0, BW - 170, 0);
    shift.addColorStop(0, "#b9722c"); shift.addColorStop(0.5, "#8c8a3a"); shift.addColorStop(1, "#2f9a63");
    g.lineWidth = 4; g.strokeStyle = "#1f4a35"; g.lineJoin = "round";
    g.strokeText("100", BW - 170, BH - 98);
    g.fillStyle = shift; g.fillText("100", BW - 170, BH - 98);

    // age: darker edges, soft inner highlight
    var vig = g.createRadialGradient(BW / 2, BH / 2, BH * 0.35, BW / 2, BH / 2, BW * 0.62);
    vig.addColorStop(0, "rgba(60, 50, 25, 0)"); vig.addColorStop(1, "rgba(60, 50, 25, 0.28)");
    g.fillStyle = vig; g.fillRect(0, 0, BW, BH);
    g.lineWidth = 2; g.strokeStyle = "rgba(255, 255, 255, 0.35)";
    roundRectPath(g, 2, 2, BW - 4, BH - 4, 8); g.stroke();
    return cv;
  }

  function buildSprites() {
    billSprite = buildBill();
    coinSprites = [];
    for (var i = 0; i < COIN_TYPES.length; i++) {
      coinSprites.push({
        obv: buildCoinFace(COIN_TYPES[i], false),
        rev: buildCoinFace(COIN_TYPES[i], true)
      });
    }
  }

  /* ---------- drawing the moving parts ---------- */

  function drawReeding(type, r, x0, x1, roll) {
    ctx.save();
    ctx.beginPath(); ctx.rect(x0, -r, x1 - x0, r * 2); ctx.clip();
    ctx.lineWidth = 1;
    ctx.strokeStyle = "rgba(40, 50, 70, 0.6)";
    ctx.beginPath();
    for (var k = 0; k < type.ticks; k++) {
      var phi = roll + (k * TAU) / type.ticks;
      if (Math.cos(phi) <= 0) continue;
      var y = r * Math.sin(phi);
      ctx.moveTo(x0, y); ctx.lineTo(x1, y);
    }
    ctx.stroke();
    ctx.restore();
  }

  function drawCoin(c, alpha) {
    var type = COIN_TYPES[c.type], spr = coinScaled[c.type];
    var cos = Math.cos(c.theta), sin = Math.sin(c.theta);
    var fw = Math.max(0.02, Math.abs(cos));
    var r = c.r, half = r * 0.1;                       // coin thickness is 20% of its radius
    var obvX = half * sin, revX = -half * sin;
    var nearObv = cos >= 0;
    var nearX = nearObv ? obvX : revX, farX = nearObv ? revX : obvX;

    ctx.save();
    ctx.globalAlpha = alpha;
    ctx.translate(c.x, c.y);
    ctx.rotate(c.tilt);

    // the edge of the coin: far face, then the band that joins it to the near face
    ctx.fillStyle = edgeGrads[c.type];
    ctx.beginPath(); ctx.ellipse(farX, 0, r * fw, r, 0, 0, TAU); ctx.fill();
    var x0 = Math.min(nearX, farX), x1 = Math.max(nearX, farX);
    if (x1 - x0 > 0.3) {
      ctx.fillRect(x0, -r, x1 - x0, r * 2);
      if (type.ticks && x1 - x0 > 1.4) drawReeding(type, r, x0, x1, c.roll);
    }

    // the near face, darker as the coin turns edge on
    ctx.drawImage(nearObv ? spr.obv : spr.rev, nearX - r * fw, -r, r * fw * 2, r * 2);
    if (fw < 1) {
      ctx.fillStyle = "rgba(0, 0, 0, " + (0.4 * (1 - fw)).toFixed(3) + ")";
      ctx.beginPath(); ctx.ellipse(nearX, 0, r * fw, r, 0, 0, TAU); ctx.fill();
    }
    ctx.restore();
  }

  function drawCoinShadow(c, alpha) {
    var height = Math.max(0, H - c.y - c.r);
    var a = clamp(0.5 - height / 700, 0, 0.5) * alpha;
    if (a < 0.02) return;
    var w = c.r * (1.15 - Math.min(0.45, height / 800));
    ctx.fillStyle = "rgba(0, 0, 0, " + a.toFixed(3) + ")";
    ctx.beginPath(); ctx.ellipse(c.x, H - 3, w, c.r * 0.2, 0, 0, TAU); ctx.fill();
  }

  // The note drawn in vertical strips so it can ripple like paper in flight.
  function drawBillSprite(w, h, ripple, t, alpha, shadow) {
    var strips = 36, srcW = billScaled.width, srcH = billScaled.height;
    var sw = srcW / strips, dw = w / strips;
    ctx.save();
    ctx.globalAlpha = alpha;
    if (shadow) {
      ctx.shadowColor = "rgba(0, 0, 0, 0.55)";
      ctx.shadowBlur = 26;
      ctx.shadowOffsetY = 16;
    }
    for (var i = 0; i < strips; i++) {
      var dy = ripple ? Math.sin(i * 0.3 - t * 9) * ripple * h * 0.028 : 0;
      ctx.drawImage(billScaled, i * sw, 0, sw + 1, srcH, -w / 2 + i * dw, -h / 2 + dy, dw + 1, h);
    }
    ctx.restore();
  }

  function drawFlash() {
    if (flash <= 0) return;
    var radius = Math.max(1, 90 * scale + (1 - Math.min(1, flash)) * 260 * scale);
    var g = ctx.createRadialGradient(impact.x, impact.y, 0, impact.x, impact.y, radius);
    g.addColorStop(0, "rgba(255, 244, 214, " + (flash * 0.85).toFixed(3) + ")");
    g.addColorStop(1, "rgba(255, 244, 214, 0)");
    ctx.fillStyle = g;
    ctx.fillRect(impact.x - radius, impact.y - radius, radius * 2, radius * 2);
  }

  /* ---------- scene ---------- */

  // Copies of the artwork at the size they are drawn on screen, so each frame
  // is a cheap 1:1 copy instead of a big downscale.
  function shrink(src, w, h) {
    var c = makeCanvas(Math.max(8, Math.round(w)), Math.max(8, Math.round(h)));
    var g = c.getContext("2d");
    g.imageSmoothingEnabled = true;
    g.imageSmoothingQuality = "high";
    g.drawImage(src, 0, 0, c.width, c.height);
    return c;
  }

  function prepareScaled() {
    var i, bw = clamp(W * 0.5, 280, 580);
    billScaled = shrink(billSprite, bw * dprNow * 1.15, bw * (BILL_H / BILL_W) * dprNow * 1.15);
    coinScaled = [];
    edgeGrads = [];
    for (i = 0; i < COIN_TYPES.length; i++) {
      var r = COIN_TYPES[i].r * scale, d = r * 2 * dprNow * 1.15;
      coinScaled.push({ obv: shrink(coinSprites[i].obv, d, d), rev: shrink(coinSprites[i].rev, d, d) });
      var edge = ctx.createLinearGradient(0, -r, 0, r);
      edge.addColorStop(0, COIN_TYPES[i].edgeB);
      edge.addColorStop(0.5, COIN_TYPES[i].edgeA);
      edge.addColorStop(1, COIN_TYPES[i].lo);
      edgeGrads.push(edge);
    }
  }

  function resize() {
    var dpr = Math.min(window.devicePixelRatio || 1, 2);
    dprNow = dpr;
    W = window.innerWidth;
    H = window.innerHeight;
    canvas.width = Math.round(W * dpr);
    canvas.height = Math.round(H * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.imageSmoothingEnabled = true;
    ctx.imageSmoothingQuality = "medium";
    scale = clamp(W / 1100, 0.7, 1.3);
    prepareScaled();
    for (var i = 0; i < coins.length; i++) {
      coins[i].x = clamp(coins[i].x, coins[i].r, W - coins[i].r);
      coins[i].y = Math.min(coins[i].y, H - coins[i].r);
    }
    if (reduceMotion) drawStill();
  }

  function newBill() {
    var w = clamp(W * 0.5, 280, 580);
    var h = w * (BILL_H / BILL_W);
    return {
      w: w, h: h,
      x0: W + w * 0.55, y0: -h * 1.3,           // start beyond the top right corner
      tx: W * rand(0.38, 0.52), ty: H - h / 2 - 6,
      rot0: rand(0.5, 0.75)
    };
  }

  function pickType() {
    var total = 0, i;
    for (i = 0; i < COIN_TYPES.length; i++) total += COIN_TYPES[i].weight;
    var roll = Math.random() * total;
    for (i = 0; i < COIN_TYPES.length; i++) {
      roll -= COIN_TYPES[i].weight;
      if (roll <= 0) return i;
    }
    return 0;
  }

  function burst() {
    impact.x = bill.tx;
    impact.y = H - 12;
    flash = 1;
    shake = 16 * scale;
    coins = [];
    var count = clamp(Math.round(16 + W / 130), 18, 28);
    for (var i = 0; i < count; i++) {
      var type = pickType();
      var angle = -Math.PI * rand(0.08, 0.92);               // upward fan
      var speed = rand(650, 1500) * Math.sqrt(scale);
      var r = COIN_TYPES[type].r * scale;
      coins.push({
        type: type, r: r,
        x: impact.x + rand(-bill.w * 0.3, bill.w * 0.3),
        y: H - r - rand(4, 40),
        vx: Math.cos(angle) * speed, vy: Math.sin(angle) * speed,
        theta: rand(0, TAU), omega: rand(-22, 22),
        tilt: rand(-0.5, 0.5), tiltSpeed: rand(-1.6, 1.6), roll: rand(0, TAU)
      });
    }
    var paperColors = ["#e6eddb", "#4f9a72", "#a9cbe8", "#e9bf94"];
    shards = [];
    for (var s = 0; s < 22; s++) {
      var a = -Math.PI * rand(0.05, 0.95);
      var v = rand(300, 950);
      shards.push({
        x: impact.x + rand(-bill.w * 0.4, bill.w * 0.4), y: H - 20,
        vx: Math.cos(a) * v, vy: Math.sin(a) * v,
        rot: rand(0, TAU), spin: rand(-12, 12), life: 1.5,
        size: rand(8, 18) * scale, color: paperColors[s % paperColors.length]
      });
    }
  }

  function stepCoins(dt) {
    var i, j, c;
    for (i = 0; i < coins.length; i++) {
      c = coins[i];
      c.vy += GRAVITY * dt;
      c.x += c.vx * dt;
      c.y += c.vy * dt;
      c.theta += c.omega * dt;
      c.tilt += c.tiltSpeed * dt;
      c.roll += c.omega * 0.35 * dt;

      if (c.y + c.r > H) {
        c.y = H - c.r;
        if (c.vy > 0) c.vy = -c.vy * 0.72;
        c.vx *= 0.985;
        c.omega *= 0.97;
        c.tiltSpeed *= 0.97;
        if (Math.abs(c.vy) < 90) c.vy = 0;
      }
      if (c.y - c.r < 0 && c.vy < 0) { c.y = c.r; c.vy = -c.vy * 0.5; }
      if (c.x - c.r < 0) { c.x = c.r; c.vx = Math.abs(c.vx) * 0.9; }
      if (c.x + c.r > W) { c.x = W - c.r; c.vx = -Math.abs(c.vx) * 0.9; }

      // keep bouncing: a coin lying on the floor hops up every second or so
      if (phase === "bounce" && c.y + c.r >= H - 0.5 && Math.abs(c.vy) < 140 &&
          Math.random() < dt * 1.1) {
        c.vy = -rand(560, 1250);
        c.vx += rand(-260, 260);
        c.omega = rand(-20, 20);
        c.tiltSpeed = rand(-1.6, 1.6);
      }
    }

    // coins knock into each other
    for (i = 0; i < coins.length; i++) {
      for (j = i + 1; j < coins.length; j++) {
        var a = coins[i], b = coins[j];
        var dx = b.x - a.x, dy = b.y - a.y;
        var min = a.r + b.r, d2 = dx * dx + dy * dy;
        if (d2 >= min * min || d2 === 0) continue;
        var d = Math.sqrt(d2), nx = dx / d, ny = dy / d;
        var ma = a.r * a.r, mb = b.r * b.r, overlap = min - d;
        a.x -= nx * overlap * mb / (ma + mb);
        a.y -= ny * overlap * mb / (ma + mb);
        b.x += nx * overlap * ma / (ma + mb);
        b.y += ny * overlap * ma / (ma + mb);
        var rv = (b.vx - a.vx) * nx + (b.vy - a.vy) * ny;
        if (rv < 0) {
          var jimp = -(1 + 0.7) * rv / (1 / ma + 1 / mb);
          a.vx -= jimp * nx / ma; a.vy -= jimp * ny / ma;
          b.vx += jimp * nx / mb; b.vy += jimp * ny / mb;
        }
      }
    }
  }

  function stepShards(dt) {
    for (var i = shards.length - 1; i >= 0; i--) {
      var s = shards[i];
      s.vy += GRAVITY * 0.6 * dt;
      s.x += s.vx * dt; s.y += s.vy * dt; s.rot += s.spin * dt;
      s.life -= dt;
      if (s.life <= 0 || s.y > H + 40) shards.splice(i, 1);
    }
  }

  function setPhase(name) { phase = name; phaseTime = 0; }

  function update(dt) {
    phaseTime += dt;
    flash = Math.max(0, flash - dt * 3.2);
    shake = Math.max(0, shake - dt * 45);

    if (phase === "pause" && phaseTime >= PAUSE_TIME) {
      bill = newBill();
      coins = []; shards = [];
      setPhase("fly");
    } else if (phase === "fly" && phaseTime >= FLY_TIME) {
      burst();
      setPhase("smash");
    } else if (phase === "smash" && phaseTime >= SMASH_TIME) {
      setPhase("bounce");
    } else if (phase === "bounce" && phaseTime >= BOUNCE_TIME) {
      setPhase("fade");
    } else if (phase === "fade" && phaseTime >= FADE_TIME) {
      coins = [];
      setPhase("pause");
    }
    if (coins.length) stepCoins(dt);
    if (shards.length) stepShards(dt);
  }

  function render() {
    ctx.clearRect(0, 0, W, H);
    ctx.save();
    if (shake > 0) ctx.translate(rand(-shake, shake), rand(-shake, shake));

    var coinAlpha = phase === "fade" ? Math.max(0, 1 - phaseTime / FADE_TIME) : 1;
    var i;
    for (i = 0; i < coins.length; i++) drawCoinShadow(coins[i], coinAlpha);
    for (i = 0; i < coins.length; i++) drawCoin(coins[i], coinAlpha);

    if (bill && phase === "fly") {
      var p = Math.min(1, phaseTime / FLY_TIME);
      var e = Math.pow(p, 2.1);                                   // speeds up like a drop
      ctx.save();
      ctx.translate(bill.x0 + (bill.tx - bill.x0) * e, bill.y0 + (bill.ty - bill.y0) * e);
      ctx.rotate(bill.rot0 * (1 - e) + Math.sin(p * 9) * 0.06 * (1 - p));
      drawBillSprite(bill.w, bill.h, 1 - p * 0.8, phaseTime, 1, true);
      ctx.restore();
    } else if (bill && phase === "smash") {
      var q = Math.min(1, phaseTime / SMASH_TIME);
      var sy = 1 - 0.7 * easeOut(q), sx = 1 + 0.25 * easeOut(q);
      ctx.save();
      ctx.translate(bill.tx, H - (bill.h * sy) / 2 - 6);
      ctx.scale(sx, sy);
      drawBillSprite(bill.w, bill.h, 0, 0, 1 - q, false);
      ctx.restore();
    }

    for (var k = 0; k < shards.length; k++) {
      var s = shards[k];
      ctx.save();
      ctx.globalAlpha = clamp(s.life / 1.5, 0, 1);
      ctx.translate(s.x, s.y);
      ctx.rotate(s.rot);
      ctx.fillStyle = s.color;
      ctx.fillRect(-s.size / 2, -s.size / 3, s.size, s.size * 0.66);
      ctx.restore();
    }
    drawFlash();
    ctx.restore();
  }

  function frame(now) {
    var dt = lastTime ? clamp((now - lastTime) / 1000, 0, 0.05) : 0.016;
    lastTime = now;
    update(dt);
    render();
    window.requestAnimationFrame(frame);
  }

  // One still frame for people who ask for reduced motion.
  function drawStill() {
    ctx.clearRect(0, 0, W, H);
    var b = newBill();
    ctx.save();
    ctx.translate(W * 0.74, H * 0.24);
    ctx.rotate(-0.16);
    drawBillSprite(b.w * 0.8, b.h * 0.8, 0, 0, 0.95, true);
    ctx.restore();
    var x = W * 0.1;
    for (var i = 0; i < 9; i++) {
      var type = i % 3;
      var r = COIN_TYPES[type].r * scale;
      var coin = { type: type, r: r, x: x + r, y: H - r - (i % 2) * 6, theta: i % 2 ? 0.5 : 0, tilt: 0, roll: 0 };
      drawCoinShadow(coin, 1);
      drawCoin(coin, 1);
      x += r * 2.4;
    }
  }

  buildSprites();
  window.addEventListener("resize", resize);
  resize();
  // Web fonts load after the page starts, so redraw the artwork once they are ready.
  if (document.fonts && document.fonts.ready) {
    document.fonts.ready.then(function () {
      buildSprites();
      prepareScaled();
      if (reduceMotion) drawStill();
    });
  }
  if (!reduceMotion) window.requestAnimationFrame(frame);
})();
