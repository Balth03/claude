// Opus 5.5 — procedural motion piece.
// Every frame is a pure function of time t: renderFrame(t) is deterministic, so frames can be
// rendered in any order, on any number of workers, and always match the sound track.

const TL = await (await fetch('timeline.json')).json();
await document.fonts.load('900 100px "Inter Tight"');
await document.fonts.load('800 100px "Inter Tight"');
await document.fonts.load('600 100px "Inter Tight"');
await document.fonts.load('400 100px "Inter Tight"');
await document.fonts.load('400 100px "JetBrains Mono"');
await document.fonts.load('700 100px "JetBrains Mono"');
await document.fonts.ready;
if (!document.fonts.check('900 100px "Inter Tight"') || !document.fonts.check('400 100px "JetBrains Mono"')) throw new Error('fonts failed to load');
const W = TL.width, H = TL.height, CX = W / 2, CY = H / 2;

// ------------------------------------------------------------------ palette
const C = {
  bg: '#08070b', ink: '#0b0a0e', cream: '#f3ede3', clay: '#e2714a', clay2: '#ff8a5c',
  blue: '#8fb5ff', green: '#5be39a', grey: '#6b6570',
};
const col = (k) => C[k] || k;

// ------------------------------------------------------------------ math
function mulberry32(a) {
  return function () {
    a |= 0; a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
const lerp = (a, b, t) => a + (b - a) * t;
const inv = (a, b, x) => clamp((x - a) / (b - a));
const eOutExpo = (x) => (x >= 1 ? 1 : 1 - Math.pow(2, -10 * x));
const eInExpo = (x) => (x <= 0 ? 0 : Math.pow(2, 10 * x - 10));
const eOutCubic = (x) => 1 - Math.pow(1 - x, 3);
const eInCubic = (x) => x * x * x;
const eInOutCubic = (x) => (x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2);
const eOutBack = (x) => { const c1 = 1.70158, c3 = c1 + 1; return 1 + c3 * Math.pow(x - 1, 3) + c1 * Math.pow(x - 1, 2); };
const hash1 = (n) => { const s = Math.sin(n * 127.1 + 311.7) * 43758.5453; return s - Math.floor(s); };
const vnoise = (x) => { const i = Math.floor(x), f = x - i, u = f * f * (3 - 2 * f); return lerp(hash1(i), hash1(i + 1), u) * 2 - 1; };
const TAU = Math.PI * 2;

// ------------------------------------------------------------------ canvases
const sc = document.createElement('canvas'); sc.width = W; sc.height = H;
const g = sc.getContext('2d');
const tmp = document.createElement('canvas'); tmp.width = W; tmp.height = H;
const tg = tmp.getContext('2d');

function sprite(color, size = 64, hard = 0.0) {
  const c = document.createElement('canvas'); c.width = c.height = size;
  const x = c.getContext('2d');
  const gr = x.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, size / 2);
  gr.addColorStop(0, color); gr.addColorStop(0.12 + hard, color);
  gr.addColorStop(0.35, color.replace(/,\s*[\d.]+\)$/, ',0.35)'));
  gr.addColorStop(1, color.replace(/,\s*[\d.]+\)$/, ',0)'));
  x.fillStyle = gr; x.fillRect(0, 0, size, size);
  return c;
}
const SPR = {
  cream: sprite('rgba(255,244,228,1)'),
  clay: sprite('rgba(255,128,84,1)'),
  white: sprite('rgba(255,255,255,1)'),
  blue: sprite('rgba(150,190,255,1)'),
  green: sprite('rgba(110,240,165,1)'),
};

// ------------------------------------------------------------------ post-processing (WebGL2)
const out = document.getElementById('out');
const gl = out.getContext('webgl2', { preserveDrawingBuffer: true, antialias: false, alpha: false });
const VS = `#version 300 es
in vec2 p; out vec2 uv;
void main(){ uv = p * 0.5 + 0.5; gl_Position = vec4(p, 0.0, 1.0); }`;
const FS = `#version 300 es
precision highp float;
uniform sampler2D tex; uniform float time, ca, zoom, flash, glitch, bloom, vig, grain, invert, barrel;
uniform vec3 flashCol; uniform vec2 zc;
in vec2 uv; out vec4 o;
float h(vec2 p){ return fract(sin(dot(p, vec2(12.9898, 78.233))) * 43758.5453); }
vec3 tap(vec2 u, vec2 off){
  return vec3(texture(tex, u + off).r, texture(tex, u).g, texture(tex, u - off).b);
}
void main(){
  vec2 u = uv;
  float fr = floor(time * 60.0);
  if (glitch > 0.001) {
    float row = floor(u.y * 27.0);
    float bk = floor(fr / 2.0);
    if (h(vec2(row, bk)) < glitch * 0.55) u.x += (h(vec2(row + 3.1, bk)) - 0.5) * 0.18 * glitch;
    float row2 = floor(u.y * 7.0);
    if (h(vec2(row2 + 9.0, bk)) < glitch * 0.3) u.x += (h(vec2(row2, bk + 1.0)) - 0.5) * 0.06;
  }
  vec2 c = u - 0.5;
  u = 0.5 + c * (1.0 + barrel * dot(c, c));
  vec2 d = u - zc;
  vec2 off = d * ca * 0.012 + vec2(ca * 0.0012, 0.0);
  vec3 colr;
  if (zoom > 0.002) {
    colr = vec3(0.0);
    float tot = 0.0;
    for (int i = 0; i < 18; i++) {
      float f = float(i) / 17.0;
      float s = 1.0 - zoom * 0.22 * f;
      float w = 1.0 - f * 0.55;
      colr += tap(zc + d * s, off * (1.0 + f)) * w;
      tot += w;
    }
    colr /= tot;
  } else {
    colr = tap(u, off);
  }
  vec3 b = textureLod(tex, u, 3.0).rgb * 0.25 + textureLod(tex, u, 4.5).rgb * 0.35 + textureLod(tex, u, 6.0).rgb * 0.4;
  colr += pow(b, vec3(1.35)) * bloom;
  colr = mix(colr, flashCol, clamp(flash, 0.0, 1.0));
  colr = mix(colr, 1.0 - colr, invert);
  float v = smoothstep(0.35, 1.05, length(c * vec2(1.0, 0.82)) * 1.35);
  colr *= 1.0 - vig * v;
  colr += (h(gl_FragCoord.xy + fract(time * 7.13) * 431.0) - 0.5) * grain;
  o = vec4(colr, 1.0);
}`;
function shader(type, src) {
  const s = gl.createShader(type); gl.shaderSource(s, src); gl.compileShader(s);
  if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(s));
  return s;
}
const prog = gl.createProgram();
gl.attachShader(prog, shader(gl.VERTEX_SHADER, VS));
gl.attachShader(prog, shader(gl.FRAGMENT_SHADER, FS));
gl.linkProgram(prog);
if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(prog));
gl.useProgram(prog);
const vb = gl.createBuffer();
gl.bindBuffer(gl.ARRAY_BUFFER, vb);
gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);
const ploc = gl.getAttribLocation(prog, 'p');
gl.enableVertexAttribArray(ploc);
gl.vertexAttribPointer(ploc, 2, gl.FLOAT, false, 0, 0);
const texo = gl.createTexture();
gl.bindTexture(gl.TEXTURE_2D, texo);
gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR_MIPMAP_LINEAR);
gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
const U = {};
for (const n of ['time', 'ca', 'zoom', 'flash', 'glitch', 'bloom', 'vig', 'grain', 'invert', 'barrel', 'flashCol', 'zc', 'tex']) U[n] = gl.getUniformLocation(prog, n);
gl.uniform1i(U.tex, 0);
gl.viewport(0, 0, W, H);

// ------------------------------------------------------------------ per-frame fx state
let fx;
function resetFx() {
  fx = { ca: 0.12, zoom: 0, flash: 0, flashCol: [1, 0.97, 0.93], glitch: 0, bloom: 0.55, vig: 0.42, grain: 0.035, invert: 0, barrel: 0.04, zc: [0.5, 0.5], shake: 0 };
}
const IMPACT = {
  bigbang: [34, 1.6, 0.45], word: [8, 0.55, 0.11], stamp: [26, 1.1, 0.28], boom: [58, 2.4, 0.75],
  morph: [5, 0.45, 0.25], soft: [4, 0.3, 0.2], flashHit: [16, 0.9, 0.22], ring: [7, 0.5, 0.12], pop: [3, 0.25, 0.1],
};
const impactCues = TL.cues.filter((c) => IMPACT[c.type]);
function impacts(t) {
  let sh = 0, ca = 0;
  for (const c of impactCues) {
    const dt = t - c.t;
    if (dt < 0 || dt > 4) continue;
    const [s, a, d] = IMPACT[c.type];
    const e = Math.exp(-dt / d);
    sh += s * e; ca += a * e;
  }
  return { sh, ca };
}

// ------------------------------------------------------------------ drawing helpers
function bg(c) { g.fillStyle = col(c); g.fillRect(-300, -300, W + 600, H + 600); }
function font(weight, size, fam = 'Inter Tight') { g.font = `${weight} ${size}px "${fam}"`; }
// Draws text optically centred on (x, y) using real glyph bounds; honours letterSpacing.
function textC(s, x, y, ls = 0, ctx = g) {
  ctx.letterSpacing = ls + 'px';
  ctx.textAlign = 'left'; ctx.textBaseline = 'alphabetic';
  const m = ctx.measureText(s);
  const w = m.width - ls;
  ctx.fillText(s, x - w / 2, y + (m.actualBoundingBoxAscent - m.actualBoundingBoxDescent) / 2);
  ctx.letterSpacing = '0px';
  return w;
}
// Clean outlined text: dilate the glyph silhouette and cut the fill out of it, so overlapping
// contours inside the font never show up (strokeText would reveal them).
const OUT_DIRS = Array.from({ length: 16 }, (_, k) => [Math.cos((k * TAU) / 16), Math.sin((k * TAU) / 16)]);
function outlineLayer(draw, lw, color, alpha = 1) {
  const m = g.getTransform();
  tg.setTransform(1, 0, 0, 1, 0, 0);
  tg.globalCompositeOperation = 'source-over';
  tg.clearRect(0, 0, W, H);
  tg.font = g.font; tg.fillStyle = color;
  for (const [dx, dy] of OUT_DIRS) { tg.setTransform(m.a, m.b, m.c, m.d, m.e + dx * lw, m.f + dy * lw); draw(tg); }
  tg.globalCompositeOperation = 'destination-out';
  tg.setTransform(m); draw(tg);
  tg.globalCompositeOperation = 'source-over';
  tg.setTransform(1, 0, 0, 1, 0, 0);
  g.save(); g.setTransform(1, 0, 0, 1, 0, 0); g.globalAlpha = alpha; g.drawImage(tmp, 0, 0); g.restore();
}
function strokeC(s, x, y, ls = 0, lw = 2.5, alpha = 1) {
  const color = g.fillStyle;
  outlineLayer((ctx) => {
    ctx.letterSpacing = ls + 'px';
    ctx.textAlign = 'left'; ctx.textBaseline = 'alphabetic';
    const m = ctx.measureText(s);
    ctx.fillText(s, x - (m.width - ls) / 2, y + (m.actualBoundingBoxAscent - m.actualBoundingBoxDescent) / 2);
    ctx.letterSpacing = '0px';
  }, lw, color, alpha);
}
function fit(s, weight, maxW, maxSize, fam = 'Inter Tight', ls = 0) {
  font(weight, 100, fam);
  g.letterSpacing = ls * 0.01 * 100 + 'px';
  const w = g.measureText(s).width;
  g.letterSpacing = '0px';
  return Math.min(maxSize, (100 * maxW) / w);
}
function glowDot(spr, x, y, r, a = 1) {
  g.globalAlpha = a;
  g.drawImage(spr, x - r, y - r, r * 2, r * 2);
  g.globalAlpha = 1;
}
function roundRect(x, y, w, h, r) {
  g.beginPath(); g.roundRect(x, y, w, h, r);
}
function hud(t, color = 'rgba(243,237,227,0.55)', label = '') {
  g.save();
  g.setTransform(1, 0, 0, 1, 0, 0);
  g.strokeStyle = color; g.lineWidth = 2;
  const m = 48, l = 26;
  for (const [x, y, sx, sy] of [[m, m, 1, 1], [W - m, m, -1, 1], [m, H - m, 1, -1], [W - m, H - m, -1, -1]]) {
    g.beginPath(); g.moveTo(x, y + sy * l); g.lineTo(x, y); g.lineTo(x + sx * l, y); g.stroke();
  }
  g.fillStyle = color;
  g.font = '400 17px "JetBrains Mono"'; g.textBaseline = 'middle';
  g.textAlign = 'left'; g.letterSpacing = '2px';
  g.fillText('CLAUDE / OPUS 5.5', m + 40, m + 1);
  if (label) g.fillText(label, m + 40, H - m - 1);
  g.textAlign = 'right';
  const f = Math.floor(t * 60);
  const tc = `${String(Math.floor(t)).padStart(2, '0')}:${String(f % 60).padStart(2, '0')}`;
  g.fillText(`T+${tc}`, W - m - 40, m + 1);
  g.fillText(`FRAME ${String(f).padStart(4, '0')}`, W - m - 40, H - m - 1);
  g.letterSpacing = '0px';
  g.restore();
}

// ------------------------------------------------------------------ S0 : prompt + collapse
function S0(t) {
  const S = TL.s0;
  bg('bg');
  const fs = 46;
  g.font = `400 ${fs}px "JetBrains Mono"`;
  g.textBaseline = 'middle'; g.textAlign = 'left';
  const cw = g.measureText('M').width;
  const x0 = CX - (cw * S.text.length) / 2;
  let n = 0;
  while (n < S.typed.length && S.typed[n] <= t) n++;
  const cp = eInExpo(inv(S.collapse, TL.bang - 0.02, t));
  const cpS = eInCubic(inv(S.collapse, TL.bang - 0.02, t));
  const fadeIn = inv(0, 0.3, t);
  // glow gathering at the centre during the collapse
  if (cpS > 0) {
    g.globalCompositeOperation = 'lighter';
    glowDot(SPR.clay, CX, CY, 60 + 500 * cpS, 0.25 + 0.6 * cpS);
    glowDot(SPR.white, CX, CY, 10 + 120 * cp, cp);
    g.globalCompositeOperation = 'source-over';
  }
  for (let i = 0; i < n; i++) {
    const ch = S.text[i];
    const hx = x0 + i * cw, hy = CY;
    // each glyph is pulled into the centre with a small per-glyph delay and a spiral
    const k = clamp(cp * (1 + (Math.abs(i - S.text.length / 2) / S.text.length) * 0.6));
    const ang = k * 2.2 * (i % 2 ? 1 : -1);
    const dx = hx + cw / 2 - CX, dy = hy - CY;
    const r = 1 - k;
    const x = CX + (dx * Math.cos(ang) - dy * Math.sin(ang)) * r - cw / 2;
    const y = CY + (dx * Math.sin(ang) + dy * Math.cos(ang)) * r;
    const age = t - S.typed[i];
    g.globalAlpha = fadeIn * (1 - k * k) * clamp(age * 25);
    g.fillStyle = i < 2 ? C.clay : C.cream;
    g.save();
    g.translate(x + cw / 2, y);
    g.scale(r * 0.8 + 0.2 + 0.35 * Math.exp(-age * 30), r * 0.8 + 0.2 + 0.35 * Math.exp(-age * 30));
    g.fillText(ch, -cw / 2, 0);
    g.restore();
  }
  g.globalAlpha = 1;
  // cursor
  const typing = t >= S.typeStart - 0.05 && t < S.typeEnd + 0.05;
  const blinkOn = typing || Math.floor(t * 2.4) % 2 === 0;
  let cx = x0 + n * cw, cy = CY;
  let cwid = cw * 0.62, ch = fs * 1.12;
  if (cp > 0) {
    cx = lerp(cx, CX - cwid / 2, eOutCubic(clamp(cp * 3)));
    const s = 1 - cp;
    cwid *= s; ch *= s;
  }
  if (blinkOn || cp > 0) {
    g.fillStyle = C.clay2;
    g.globalAlpha = fadeIn;
    g.fillRect(cx + (cw * 0.62 - cwid) / 2 * (cp > 0 ? 0 : 1), cy - ch / 2, Math.max(cwid, 2), Math.max(ch, 2));
    g.globalAlpha = 1;
    g.globalCompositeOperation = 'lighter';
    glowDot(SPR.clay, cx + cwid / 2, cy, 70, 0.18 * fadeIn);
    g.globalCompositeOperation = 'source-over';
  }
  fx.zoom = cp * 0.9;
  fx.ca += cp * 1.2;
  fx.shake += cpS * 6;
  fx.vig = 0.55;
}

// ------------------------------------------------------------------ S1 : big bang
const BANG_P = (() => {
  const r = mulberry32(11), a = [];
  for (let i = 0; i < 1500; i++) {
    const ang = r() * TAU, sp = 300 + Math.pow(r(), 2.2) * 3200;
    a.push({ ang, sp, w: 0.8 + r() * 2.6, c: r() < 0.35 ? 1 : r() < 0.5 ? 2 : 0, life: 0.6 + r() * 0.9, z: r() });
  }
  return a;
})();
function burstPos(p, dt, k = 2.6) { return p.sp * (1 - Math.exp(-k * dt)) / k; }
function S1(t) {
  const dt = t - TL.bang;
  bg('bg');
  // warm core glow
  g.globalCompositeOperation = 'lighter';
  glowDot(SPR.clay, CX, CY, 900 * (0.4 + dt), 0.55 * Math.exp(-dt * 2.2));
  glowDot(SPR.white, CX, CY, 300 * Math.exp(-dt * 3), Math.exp(-dt * 4));
  // shock rings
  for (const [delay, max, c] of [[0, 1500, 'rgba(255,240,225,'], [0.07, 1150, 'rgba(255,128,84,'], [0.16, 800, 'rgba(255,240,225,']]) {
    const u = dt - delay;
    if (u <= 0) continue;
    const r = eOutExpo(clamp(u / 0.9)) * max;
    const a = Math.exp(-u * 3);
    g.strokeStyle = c + a + ')';
    g.lineWidth = 2 + 40 * Math.exp(-u * 6);
    g.beginPath(); g.arc(CX, CY, r, 0, TAU); g.stroke();
  }
  // streaking particles
  g.lineCap = 'round';
  for (const p of BANG_P) {
    const a = 1 - dt / p.life;
    if (a <= 0) continue;
    const r1 = burstPos(p, dt), r0 = burstPos(p, Math.max(0, dt - 0.045));
    const cs = Math.cos(p.ang), sn = Math.sin(p.ang);
    g.strokeStyle = p.c === 1 ? `rgba(255,128,84,${a})` : p.c === 2 ? `rgba(255,255,255,${a})` : `rgba(255,236,214,${a})`;
    g.lineWidth = p.w;
    g.beginPath(); g.moveTo(CX + cs * r0, CY + sn * r0); g.lineTo(CX + cs * r1 + cs * 2, CY + sn * r1 + sn * 2); g.stroke();
  }
  g.globalCompositeOperation = 'source-over';
  fx.flash = Math.exp(-dt * 7.5) * 0.95;
  fx.zoom = 1.0 * Math.exp(-dt * 2.6);
  fx.bloom = 0.9;
  // tail: pull into the word barrage
  fx.zoom += eInExpo(inv(3.3, 3.6, t)) * 0.6;
}

// ------------------------------------------------------------------ S2 : word barrage
function S2(t) {
  const S = TL.s2;
  const i = Math.min(S.words.length - 1, Math.floor((t - S.start) / S.step));
  const wd = S.words[i];
  const dt = t - wd.t;
  bg(wd.bg);
  const fg = col(wd.fg);
  const punch = 1 + 0.28 * Math.exp(-dt * 20) + 0.05 * dt;
  g.save();
  g.translate(CX, CY);
  g.rotate(wd.rot * Math.exp(-dt * 10));
  g.scale(punch, punch);
  g.fillStyle = fg; g.strokeStyle = fg;
  const st = wd.style;
  if (st === 'giant' || st === 'outline') {
    const fs = fit(wd.w, 900, W * 0.84, 520, 'Inter Tight', -3);
    font(900, fs);
    if (st === 'outline') {
      for (let k = -2; k <= 2; k++) {
        if (k === 0) continue;
        strokeC(wd.w, 0, k * fs * 0.84 + Math.sign(k) * fs * 0.25 * Math.exp(-dt * 16), -fs * 0.03, 3, 0.55 - Math.abs(k) * 0.15);
      }
    }
    textC(wd.w, 0, 0, -fs * 0.03);
  } else if (st === 'echo') {
    const fs = fit(wd.w, 900, W * 0.62, 400);
    font(900, fs);
    const lh = fs * 0.86;
    const scroll = (dt * 1200) % lh;
    for (let k = -4; k <= 4; k++) {
      if (k === 0) continue;
      strokeC(wd.w, 0, k * lh + (k < 0 ? -scroll : scroll) * 0.3, 0, 2.5, 0.85 - Math.abs(k) * 0.17);
    }
    textC(wd.w, 0, 0);
  } else if (st === 'wide') {
    const ls = lerp(90, 4, eOutExpo(clamp(dt / 0.22)));
    const fs = fit(wd.w, 800, W * 0.86 - ls * wd.w.length * 0.6, 260, 'Inter Tight');
    font(800, fs);
    textC(wd.w, 0, 0, ls);
    g.fillRect(-W * 0.3 * eOutExpo(clamp(dt / 0.2)), fs * 0.62, W * 0.6 * eOutExpo(clamp(dt / 0.2)), 6);
  } else if (st === 'split') {
    const fs = fit(wd.w, 900, W * 0.8, 560);
    font(900, fs);
    const off = W * 0.7 * Math.exp(-dt * 19);
    for (const [y0, sgn] of [[-H, -1], [0, 1]]) {
      g.save();
      g.beginPath(); g.rect(-W, y0, W * 2, H); g.clip();
      g.translate(off * sgn, 0);
      textC(wd.w, 0, 0);
      g.restore();
    }
  } else if (st === 'stripes') {
    const fs = fit(wd.w, 900, W * 0.84, 360);
    font(900, fs);
    const n = 9, bh = (fs * 1.1) / n;
    for (let k = 0; k < n; k++) {
      g.save();
      const y0 = -fs * 0.55 + k * bh;
      g.beginPath(); g.rect(-W, y0, W * 2, bh + 0.5); g.clip();
      g.translate((k % 2 ? 1 : -1) * W * Math.exp(-dt * (26 + k * 2)), 0);
      textC(wd.w, 0, 0);
      g.restore();
    }
  } else if (st === 'mono') {
    const fs = fit('{ ' + wd.w + ' }', 700, W * 0.8, 200, 'JetBrains Mono');
    font(700, fs, 'JetBrains Mono');
    g.textBaseline = 'alphabetic';
    const full = '{ ' + wd.w + ' }';
    const m = g.measureText(full);
    let x = -m.width / 2;
    const y = (m.actualBoundingBoxAscent - m.actualBoundingBoxDescent) / 2;
    g.textAlign = 'left';
    const shown = Math.floor(clamp(dt / 0.12) * full.length);
    for (let k = 0; k < full.length; k++) {
      const ch = full[k];
      const w = g.measureText(ch).width;
      if (k < shown) { g.fillStyle = ch === '{' || ch === '}' ? C.clay : fg; g.fillText(ch, x, y); }
      x += w;
    }
    if (Math.floor(t * 8) % 2 === 0 || shown < full.length) {
      g.fillStyle = C.clay;
      g.fillRect(-m.width / 2 + g.measureText(full.slice(0, shown)).width + 6, y - fs * 0.78, fs * 0.5, fs * 0.9);
    }
  } else if (st === 'glitchy') {
    const fs = fit(wd.w, 900, W * 0.86, 300);
    font(900, fs);
    textC(wd.w, 0, 0);
    fx.glitch = 0.55 * Math.exp(-dt * 6) + 0.15;
    fx.ca += 1.2 * Math.exp(-dt * 8);
  } else if (st === 'grid') {
    const last = i === S.words.length - 1;
    const fs = 150;
    font(900, fs);
    g.letterSpacing = '-4px';
    const unit = wd.w + '  ·  ';
    const uw = g.measureText(unit).width;
    const lh = fs * 0.9;
    const rows = Math.ceil(H / lh) + 3;
    const speed = last ? 2600 : 1700;
    g.textBaseline = 'middle'; g.textAlign = 'left';
    const rowX = (r) => { const dir = r % 2 ? 1 : -1; return (((dt * speed * dir + r * 173) % uw) + uw) % uw; };
    for (let r = 0; r < rows; r++) {
      if (!((r + (last ? 1 : 0)) % 2)) continue;
      const y = (r - rows / 2) * lh;
      for (let x = -W - rowX(r); x < W; x += uw) g.fillText(unit, x, y);
    }
    outlineLayer((ctx) => {
      ctx.letterSpacing = '-4px'; ctx.textBaseline = 'middle'; ctx.textAlign = 'left';
      for (let r = 0; r < rows; r++) {
        if ((r + (last ? 1 : 0)) % 2) continue;
        const y = (r - rows / 2) * lh;
        for (let x = -W - rowX(r); x < W; x += uw) ctx.fillText(unit, x, y);
      }
      ctx.letterSpacing = '0px';
    }, 2.5, fg);
    g.letterSpacing = '0px';
    if (last) {
      const z = eInExpo(inv(0.08, 0.3, dt));
      fx.zoom = z * 1.2;
      fx.flash = z * 0.3;
    }
  }
  g.restore();
  // occasional single-frame inversion stabs on hard cuts
  if ((i === 3 || i === 8 || i === 12) && dt < 1 / 60) fx.invert = 1;
  fx.bloom = 0.35;
  if (wd.bg !== 'bg') fx.vig = 0.22;
  hud(t, wd.bg === 'bg' ? 'rgba(243,237,227,0.5)' : 'rgba(11,10,14,0.55)', `${String(i + 1).padStart(2, '0')} / ${S.words.length}`);
}

// ------------------------------------------------------------------ S3 : the mind (3D graph)
const MIND = (() => {
  const r = mulberry32(3);
  const nodes = [];
  const N = 720;
  for (let i = 0; i < N; i++) {
    const y = 1 - (i / (N - 1)) * 2, rad = Math.sqrt(1 - y * y), th = i * 2.399963;
    const k = 0.72 + r() * 0.5;
    nodes.push([Math.cos(th) * rad * k, y * k, Math.sin(th) * rad * k]);
  }
  for (let i = 0; i < 160; i++) {
    const a = r() * TAU, b = Math.acos(2 * r() - 1), k = Math.cbrt(r()) * 0.6;
    nodes.push([Math.sin(b) * Math.cos(a) * k, Math.cos(b) * k, Math.sin(b) * Math.sin(a) * k]);
  }
  const edges = [], seen = new Set();
  for (let i = 0; i < nodes.length; i++) {
    const d = [];
    for (let j = 0; j < nodes.length; j++) {
      if (i === j) continue;
      const dx = nodes[i][0] - nodes[j][0], dy = nodes[i][1] - nodes[j][1], dz = nodes[i][2] - nodes[j][2];
      d.push([dx * dx + dy * dy + dz * dz, j]);
    }
    d.sort((a, b) => a[0] - b[0]);
    for (let k = 0; k < 3; k++) {
      const j = d[k][1], key = i < j ? i * 10000 + j : j * 10000 + i;
      if (!seen.has(key)) { seen.add(key); edges.push([i, j]); }
    }
  }
  return { nodes, edges, big: nodes.map(() => r()) };
})();
function S3(t) {
  const S = TL.s3;
  const lt = t - S.start;
  bg('bg');
  g.globalCompositeOperation = 'lighter';
  glowDot(SPR.clay, CX, CY, 800, 0.16);
  g.globalCompositeOperation = 'source-over';
  const ry = 0.9 + lt * 0.32 + 1.2 * Math.exp(-lt * 2.5) * -1;
  const rx = 0.35 + Math.sin(lt * 0.6) * 0.15;
  let dist = lerp(1.25, 2.45, eOutCubic(clamp(lt / 2.2)));
  const dive = eInExpo(inv(S.dive, S.end, t));
  dist = lerp(dist, 0.02, dive);
  const f = 820 * (1 + dive * 0.6);
  const cy_ = Math.cos(ry), sy = Math.sin(ry), cx_ = Math.cos(rx), sx = Math.sin(rx);
  const P = MIND.nodes.map(([x, y, z]) => {
    const x1 = x * cy_ + z * sy, z1 = -x * sy + z * cy_;
    const y2 = y * cx_ - z1 * sx, z2 = y * sx + z1 * cx_;
    const zz = z2 + dist;
    return zz > 0.03 ? [CX + (x1 * f) / zz, CY + (y2 * f) / zz, zz] : null;
  });
  // edges, bucketed by depth for speed
  const buckets = [[], [], [], []];
  for (const [a, b] of MIND.edges) {
    const p = P[a], q = P[b];
    if (!p || !q) continue;
    const z = (p[2] + q[2]) / 2;
    const k = clamp(Math.floor(((z - dist + 1.2) / 2.4) * 4), 0, 3);
    buckets[k].push(p, q);
  }
  g.lineWidth = 1.1;
  buckets.forEach((arr, k) => {
    g.strokeStyle = `rgba(243,237,227,${0.34 - k * 0.07})`;
    g.beginPath();
    for (let i = 0; i < arr.length; i += 2) { g.moveTo(arr[i][0], arr[i][1]); g.lineTo(arr[i + 1][0], arr[i + 1][1]); }
    g.stroke();
  });
  // node flashes when pulses arrive
  const heat = new Float32Array(MIND.nodes.length);
  const pulses = [];
  for (const p of S.pulses) {
    const u = (t - p.t) / p.d;
    if (u < 0 || u > 1.8) continue;
    const e = MIND.edges[Math.floor(p.e * MIND.edges.length) % MIND.edges.length];
    if (u >= 1) heat[e[1]] = Math.max(heat[e[1]], 1 - (u - 1) / 0.8);
    else pulses.push([e, u]);
  }
  g.globalCompositeOperation = 'lighter';
  P.forEach((p, i) => {
    if (!p) return;
    const s = clamp(1.8 / p[2], 0.2, 30);
    const big = MIND.big[i] > 0.93;
    glowDot(big ? SPR.clay : SPR.cream, p[0], p[1], (big ? 9 : 5) * s + heat[i] * 26 * s, clamp(0.35 + heat[i] + (big ? 0.4 : 0)));
  });
  for (const [e, u] of pulses) {
    const p = P[e[0]], q = P[e[1]];
    if (!p || !q) continue;
    const s = clamp(1.8 / lerp(p[2], q[2], u), 0.2, 30);
    for (let k = 0; k < 5; k++) {
      const uu = Math.max(0, u - k * 0.05);
      glowDot(SPR.clay, lerp(p[0], q[0], uu), lerp(p[1], q[1], uu), (16 - k * 2.5) * s, 1 - k * 0.18);
    }
    glowDot(SPR.white, lerp(p[0], q[0], u), lerp(p[1], q[1], u), 6 * s, 1);
  }
  g.globalCompositeOperation = 'source-over';
  // title words
  const out = eInCubic(inv(S.wordsOut, S.wordsOut + 0.3, t));
  font(900, 124);
  g.letterSpacing = '-3px';
  const ws = S.words.map((w) => w.w);
  const gap = 36;
  const widths = ws.map((w) => g.measureText(w).width + 3);
  const total = widths.reduce((a, b) => a + b, 0) + gap * (ws.length - 1);
  let x = CX - total / 2;
  g.textBaseline = 'middle'; g.textAlign = 'left';
  S.words.forEach((w, k) => {
    const dt = t - w.t;
    if (dt >= 0 && out < 1) {
      const a = clamp(dt / 0.12) * (1 - out);
      g.save();
      g.translate(x, CY + 10 * Math.exp(-dt * 12) - out * 40);
      g.shadowColor = 'rgba(0,0,0,0.85)'; g.shadowBlur = 40;
      g.globalAlpha = a;
      g.fillStyle = k === S.words.length - 1 ? C.clay2 : C.cream;
      g.filter = dt < 0.15 ? `blur(${(1 - dt / 0.15) * 14}px)` : 'none';
      g.fillText(w.w, 0, 0);
      g.restore();
    }
    x += widths[k] + gap;
  });
  g.letterSpacing = '0px';
  // HUD readouts
  g.fillStyle = 'rgba(243,237,227,0.7)';
  g.font = '400 20px "JetBrains Mono"'; g.textAlign = 'left'; g.textBaseline = 'middle';
  const dots = '.'.repeat(1 + (Math.floor(t * 6) % 3));
  g.fillText('reasoning' + dots, 110, 150);
  const count = Math.floor(Math.pow(clamp(lt / 3.9), 2.2) * 8388608);
  g.textAlign = 'right';
  g.fillText('paths explored', W - 110, H - 190);
  g.font = '700 44px "JetBrains Mono"';
  g.fillStyle = C.clay2;
  g.fillText(count.toLocaleString('en-US'), W - 110, H - 145);
  fx.zoom = dive * 1.4;
  fx.flash = Math.pow(inv(S.end - 0.25, S.end, t), 2) * 1.0;
  fx.ca += dive * 1.5;
  fx.bloom = 0.8;
  fx.shake += dive * 10;
  hud(t, 'rgba(243,237,227,0.45)', '02 — CONTEXT');
}

// ------------------------------------------------------------------ S4 : the build
const CODE = [
  { file: 'planner.ts', src: `export async function plan(goal: Goal): Promise<Step[]> {
  const graph = await analyze(goal.context);
  const steps: Step[] = [];
  for (const node of graph.topoSort()) {
    if (node.blocked) continue;
    steps.push({ id: node.id, run: () => execute(node) });
  }
  return optimize(steps, { parallel: true });
}` },
  { file: 'render.rs', src: `fn render(scene: &Scene, frame: u32) -> Image {
    let mut img = Image::new(1920, 1080);
    for layer in scene.layers.iter().rev() {
        let t = frame as f32 / 60.0;
        img.composite(layer.sample(t), Blend::Add);
    }
    img
}` },
  { file: 'solver.py', src: `def solve(problem, depth=0):
    # split until every piece is obvious
    if problem.is_trivial():
        return problem.answer()
    parts = decompose(problem)
    results = [solve(p, depth + 1) for p in parts]
    return merge(results, strategy="verify")` },
  { file: 'server.go', src: `func (s *Server) Handle(w http.ResponseWriter, r *http.Request) {
	ctx, cancel := context.WithTimeout(r.Context(), 2*time.Second)
	defer cancel()
	res, err := s.core.Process(ctx, r.Body)
	if err != nil {
		http.Error(w, err.Error(), 500)
		return
	}
	json.NewEncoder(w).Encode(res)
}` },
  { file: 'glow.glsl', src: `vec3 glow(vec2 uv, float t) {
  float d = length(uv - 0.5);
  float ring = smoothstep(0.02, 0.0, abs(d - 0.25 * t));
  // warm core, cool falloff
  return mix(vec3(0.05), vec3(1.0, 0.45, 0.28), ring);
}` },
];
const KW = new Set('export async function const for of if continue return let mut fn in as def else func defer nil err vec3 vec2 float await new'.split(' '));
function tokenize(line) {
  const out = [];
  const re = /(\/\/.*|#.*)|("[^"]*")|(\b\d+(?:\.\d+)?\b)|([A-Za-z_][A-Za-z0-9_]*)|(\s+)|([^\sA-Za-z0-9_"]+)/g;
  let m;
  while ((m = re.exec(line))) {
    let c = '#d9d3ca';
    if (m[1]) c = '#6b6570';
    else if (m[2]) c = '#f2c98a';
    else if (m[3]) c = C.blue;
    else if (m[4]) c = KW.has(m[4]) ? C.clay2 : /^[A-Z]/.test(m[4]) ? '#f3ede3' : '#d9d3ca';
    else if (m[6]) c = '#8a8490';
    out.push([m[0], c]);
  }
  return out;
}
CODE.forEach((c) => { c.lines = c.src.split('\n').map((l) => l.replace(/\t/g, '    ')).map(tokenize); c.len = c.src.length; });
const PANELS = [
  { x: 150, y: 150, w: 760, s: 0.78, d: 0.6, code: 0, rot: -0.03 },
  { x: 1000, y: 110, w: 780, s: 0.7, d: 0.45, code: 1, rot: 0.025 },
  { x: 90, y: 600, w: 720, s: 0.74, d: 0.55, code: 2, rot: 0.02 },
  { x: 1120, y: 620, w: 820, s: 0.66, d: 0.4, code: 3, rot: -0.02 },
  { x: 640, y: 380, w: 700, s: 0.9, d: 0.8, code: 4, rot: 0.0 },
];
const TESTS = (() => {
  const subj = ['parser', 'scheduler', 'renderer', 'auth', 'cache', 'router', 'solver', 'encoder', 'queue', 'planner', 'index', 'shader'];
  const act = ['handles nested scopes', 'recovers from timeout', 'streams large payloads', 'merges partial results', 'rejects invalid input', 'retries with backoff', 'preserves ordering', 'survives concurrent writes', 'resolves cyclic deps', 'renders at 60fps', 'compresses without loss', 'keeps state consistent'];
  const r = mulberry32(21);
  return TL.s4.lines.map(() => [subj[Math.floor(r() * subj.length)] + ' ' + act[Math.floor(r() * act.length)], 2 + Math.floor(r() * 60)]);
})();
function panel(x, y, w, h, title) {
  g.fillStyle = 'rgba(18,16,22,0.94)';
  roundRect(x, y, w, h, 18); g.fill();
  g.strokeStyle = 'rgba(243,237,227,0.12)'; g.lineWidth = 2; g.stroke();
  g.fillStyle = 'rgba(243,237,227,0.05)';
  g.beginPath(); g.roundRect(x, y, w, 46, [18, 18, 0, 0]); g.fill();
  for (let k = 0; k < 3; k++) { g.fillStyle = k === 0 ? C.clay : 'rgba(243,237,227,0.22)'; g.beginPath(); g.arc(x + 26 + k * 22, y + 23, 6.5, 0, TAU); g.fill(); }
  g.fillStyle = 'rgba(243,237,227,0.55)'; g.font = '400 18px "JetBrains Mono"'; g.textAlign = 'left'; g.textBaseline = 'middle';
  g.fillText(title, x + 100, y + 24);
}
function checkmark(x, y, s, c) {
  g.strokeStyle = c; g.lineWidth = s * 0.22; g.lineCap = 'round'; g.lineJoin = 'round';
  g.beginPath(); g.moveTo(x - s * 0.4, y); g.lineTo(x - s * 0.1, y + s * 0.3); g.lineTo(x + s * 0.45, y - s * 0.35); g.stroke();
}
function S4(t) {
  const S = TL.s4;
  const lt = t - S.start;
  bg('bg');
  // perspective floor grid
  g.save();
  const hy = H * 0.5;
  g.strokeStyle = 'rgba(226,113,74,0.22)'; g.lineWidth = 1.5;
  g.beginPath();
  for (let k = -24; k <= 24; k++) { g.moveTo(CX + k * 40, hy); g.lineTo(CX + k * 420, H + 40); }
  const zoff = (lt * 1.6) % 1;
  for (let k = 0; k < 16; k++) {
    const z = k + 1 - zoff;
    const y = hy + 520 / z;
    if (y > H + 10) continue;
    g.moveTo(0, y); g.lineTo(W, y);
  }
  g.stroke();
  const fade = g.createLinearGradient(0, hy - 10, 0, hy + 240);
  fade.addColorStop(0, 'rgba(8,7,11,1)'); fade.addColorStop(1, 'rgba(8,7,11,0)');
  g.fillStyle = fade; g.fillRect(0, hy - 10, W, 250);
  g.fillStyle = C.bg; g.fillRect(0, 0, W, hy - 9);
  g.restore();
  g.globalCompositeOperation = 'lighter';
  glowDot(SPR.clay, CX, hy, 700, 0.2);
  g.globalCompositeOperation = 'source-over';
  // camera push
  const push = 1 + lt * 0.035;
  const termOn = eOutExpo(inv(S.term, S.term + 0.35, t));
  PANELS.forEach((p, k) => {
    const t0 = S.panels[k];
    const a = eOutBack(clamp((t - t0) / 0.35));
    if (t < t0) return;
    const code = CODE[p.code];
    const lineH = 30;
    const h = 60 + code.lines.length * lineH + 30;
    g.font = '400 20px "JetBrains Mono"';
    const maxLen = Math.max(...code.src.split('\n').map((l) => l.replace(/\t/g, '    ').length));
    const pw = Math.max(p.w, 28 + g.measureText('M').width * (3 + maxLen) + 36);
    g.save();
    const drift = (lt - 1) * 26 * (k % 2 ? 1 : -1) * p.d;
    g.translate(CX, CY); g.scale(push, push); g.translate(-CX, -CY);
    g.translate(p.x + p.w / 2 + drift, p.y + h / 2);
    const pwScale = Math.sqrt(p.w / pw);
    g.rotate(p.rot);
    const sc_ = p.s * pwScale * lerp(0.6, 1, a);
    g.scale(sc_, sc_);
    g.globalAlpha = clamp((t - t0) / 0.15) * (1 - termOn * 0.55);
    g.translate(-pw / 2, -h / 2);
    panel(0, 0, pw, h, code.file);
    // type code
    const chars = Math.floor((t - t0 - 0.05) * 330);
    let shown = 0;
    g.font = '400 20px "JetBrains Mono"'; g.textBaseline = 'middle'; g.textAlign = 'left';
    const cw = g.measureText('M').width;
    let cursor = null;
    code.lines.forEach((toks, li) => {
      let x = 28;
      const y = 76 + li * lineH;
      g.fillStyle = 'rgba(243,237,227,0.2)';
      g.fillText(String(li + 1).padStart(2, ' '), x - 6, y);
      x += cw * 3;
      for (const [s, c] of toks) {
        if (shown >= chars) break;
        const take = Math.min(s.length, chars - shown);
        g.fillStyle = c;
        g.fillText(s.slice(0, take), x, y);
        x += cw * take; shown += take;
        if (take < s.length) break;
      }
      if (shown < chars) shown += 1; // newline
      if (!cursor && shown >= chars) cursor = [x, y];
    });
    if (cursor && Math.floor(t * 5) % 2 === 0) { g.fillStyle = C.clay2; g.fillRect(cursor[0] + 2, cursor[1] - 12, 11, 24); }
    g.restore();
  });
  // terminal with tests
  if (t >= S.term) {
    const tw = 1040, th = 600;
    g.save();
    g.translate(CX, CY + lerp(700, 0, termOn));
    g.scale(lerp(0.85, 1, termOn), lerp(0.85, 1, termOn));
    g.translate(-tw / 2, -th / 2);
    g.shadowColor = 'rgba(0,0,0,0.8)'; g.shadowBlur = 80;
    panel(0, 0, tw, th, 'terminal');
    g.shadowBlur = 0;
    g.font = '400 24px "JetBrains Mono"';
    g.fillStyle = C.clay2; g.fillText('$', 32, 86);
    g.fillStyle = C.cream;
    const cmd = 'npm test -- --all';
    g.fillText(cmd.slice(0, Math.floor(clamp((t - S.term - 0.1) / 0.2) * cmd.length)), 58, 86);
    // test lines
    let n = 0;
    while (n < S.lines.length && S.lines[n] <= t) n++;
    const visible = 11;
    const first = Math.max(0, n - visible);
    g.font = '400 21px "JetBrains Mono"';
    for (let k = first; k < n; k++) {
      const y = 140 + (k - first) * 32;
      const age = t - S.lines[k];
      g.globalAlpha = clamp(age * 20);
      checkmark(46, y, 20, C.green);
      g.fillStyle = 'rgba(243,237,227,0.85)';
      g.fillText(TESTS[k][0], 76, y);
      g.fillStyle = 'rgba(243,237,227,0.35)'; g.textAlign = 'right';
      g.fillText(TESTS[k][1] + 'ms', tw - 36, y);
      g.textAlign = 'left';
    }
    g.globalAlpha = 1;
    // progress
    const pr = clamp((t - S.testsStart) / (S.testsEnd - S.testsStart));
    const passed = Math.round(Math.pow(pr, 1.3) * S.total);
    g.fillStyle = 'rgba(243,237,227,0.08)'; g.fillRect(32, th - 76, tw - 64, 12);
    g.fillStyle = C.green; g.fillRect(32, th - 76, (tw - 64) * Math.pow(pr, 1.3), 12);
    g.font = '700 22px "JetBrains Mono"'; g.fillStyle = C.green;
    g.fillText(`${passed.toLocaleString('en-US')} passed`, 32, th - 34);
    g.fillStyle = 'rgba(243,237,227,0.45)'; g.font = '400 22px "JetBrains Mono"';
    g.fillText('0 failed', 32 + 250, th - 34);
    g.textAlign = 'right';
    g.fillText(`${Math.round(Math.pow(pr, 1.3) * 100)}%`, tw - 32, th - 34);
    g.restore();
  }
  // stamp
  if (t >= S.stamp) {
    const dt = t - S.stamp;
    g.fillStyle = `rgba(4,3,6,${0.5 * clamp(dt / 0.06)})`;
    g.fillRect(-300, -300, W + 600, H + 600);
    const s = lerp(2.6, 1, eOutExpo(clamp(dt / 0.14)));
    g.save();
    g.translate(CX, CY);
    g.rotate(-0.08);
    g.scale(s, s);
    g.globalAlpha = clamp(dt / 0.05);
    font(900, 150);
    g.letterSpacing = '8px';
    const bw = g.measureText('SHIPPED').width - 8 + 150;
    g.letterSpacing = '0px';
    g.fillStyle = 'rgba(8,7,11,0.88)';
    roundRect(-bw / 2 - 22, -122, bw + 44, 244, 28); g.fill();
    g.strokeStyle = C.clay2; g.lineWidth = 12;
    roundRect(-bw / 2, -100, bw, 200, 20); g.stroke();
    g.fillStyle = C.clay2;
    textC('SHIPPED', 0, 0, 8);
    g.restore();
    fx.flash = Math.max(fx.flash, 0.35 * Math.exp(-dt * 14));
    fx.flashCol = [1, 0.55, 0.35];
  }
  fx.flash = Math.max(fx.flash, Math.exp(-lt * 15));
  const gt = inv(S.glitch, S.end, t);
  if (gt > 0) {
    fx.glitch = 0.4 + gt * 0.6;
    fx.ca += 2.5 * gt;
    fx.invert = Math.floor(t * 60) % 3 === 0 ? 1 : 0;
  }
  fx.bloom = 0.5;
  hud(t, 'rgba(243,237,227,0.45)', '03 — EXECUTION');
}

// ------------------------------------------------------------------ S5 : shape of thought (point-cloud morph)
const NP = 4200;
const SHAPES = (() => {
  const r = mulberry32(99);
  const sphere = [], cube = [], knot = [], scatter = [], text = [];
  for (let i = 0; i < NP; i++) {
    const y = 1 - (i / (NP - 1)) * 2, rad = Math.sqrt(1 - y * y), th = i * 2.399963;
    sphere.push([Math.cos(th) * rad * 1.25, y * 1.25, Math.sin(th) * rad * 1.25]);
    // cube surface with edges emphasised
    const face = Math.floor(r() * 6);
    let u = r() * 2 - 1, v = r() * 2 - 1;
    if (r() < 0.45) { if (r() < 0.5) u = Math.sign(u) || 1; else v = Math.sign(v) || 1; }
    const s = 0.82;
    const f = [[1, u, v], [-1, u, v], [u, 1, v], [u, -1, v], [u, v, 1], [u, v, -1]][face];
    cube.push(f.map((q) => q * s));
    // (2,3) torus knot tube
    const tt = r() * TAU, a = r() * TAU;
    const R = 0.75, rr = 0.34;
    const px = (R + rr * Math.cos(3 * tt)) * Math.cos(2 * tt), py = (R + rr * Math.cos(3 * tt)) * Math.sin(2 * tt), pz = rr * Math.sin(3 * tt) * 1.4;
    const tube = 0.11;
    knot.push([px + Math.cos(a) * tube, py + Math.sin(a) * tube, pz + Math.cos(a + 1) * tube]);
    const sa = r() * TAU, sb = Math.acos(2 * r() - 1), sr = 3 + r() * 5;
    scatter.push([Math.sin(sb) * Math.cos(sa) * sr, Math.cos(sb) * sr, Math.sin(sb) * Math.sin(sa) * sr]);
  }
  // "5.5" sampled from real glyph pixels
  const c = document.createElement('canvas'); c.width = 1200; c.height = 440;
  const x = c.getContext('2d');
  x.fillStyle = '#fff'; x.font = '900 400px "Inter Tight"'; x.textAlign = 'center'; x.textBaseline = 'middle';
  x.letterSpacing = '-8px';
  x.fillText('5.5', 600, 230);
  const d = x.getImageData(0, 0, 1200, 440).data;
  const pts = [];
  for (let yy = 0; yy < 440; yy += 3) for (let xx = 0; xx < 1200; xx += 3) if (d[(yy * 1200 + xx) * 4 + 3] > 128) pts.push([xx, yy]);
  let minX = 1e9, maxX = -1e9, minY = 1e9, maxY = -1e9;
  for (const [a, b] of pts) { minX = Math.min(minX, a); maxX = Math.max(maxX, a); minY = Math.min(minY, b); maxY = Math.max(maxY, b); }
  const sc2 = 3.3 / (maxX - minX);
  for (let i = 0; i < NP; i++) {
    const p = pts[Math.floor(r() * pts.length)];
    text.push([(p[0] - (minX + maxX) / 2 + (r() - 0.5) * 3) * sc2, (p[1] - (minY + maxY) / 2 + (r() - 0.5) * 3) * sc2, (r() - 0.5) * 0.12]);
  }
  const delay = [], hue = [], jit = [];
  for (let i = 0; i < NP; i++) { delay.push(r()); hue.push(r()); jit.push([r() - 0.5, r() - 0.5, r() - 0.5]); }
  return { list: [scatter, sphere, cube, knot, text], delay, hue, jit };
})();
function S5(t) {
  const S = TL.s5;
  const lt = t - S.start;
  bg('bg');
  g.globalCompositeOperation = 'lighter';
  glowDot(SPR.clay, CX, CY, 900, 0.18);
  // which transition are we in?
  const times = [S.form, ...S.morphs];
  const durs = [0.75, 0.6, 0.6, 0.65];
  let from = 0, to = 0, prog = 1;
  for (let k = 0; k < times.length; k++) {
    if (t >= times[k]) { from = k; to = k + 1; prog = (t - times[k]) / durs[k]; }
  }
  const A = SHAPES.list[from], B = SHAPES.list[to];
  // rotation that lands exactly front-facing when the text forms
  const spin = (x) => 0.85 * x + 0.4 * Math.sin(x * 0.7);
  const tText = S.morphs[2];
  let ry;
  if (t < tText) ry = spin(t - S.start);
  else {
    const r0 = spin(tText - S.start), target = Math.ceil(r0 / TAU) * TAU;
    ry = lerp(r0, target, eOutCubic(clamp((t - tText) / 0.75)));
  }
  const settle = t < tText ? 0 : eOutCubic(clamp((t - tText) / 0.75));
  const rx = (0.38 + 0.15 * Math.sin(lt * 0.8)) * (1 - settle);
  const exitK = eInExpo(inv(S.exit, S.end, t));
  const dist = lerp(4.3, 0.2, exitK);
  const f = 1080;
  const cy_ = Math.cos(ry), sy = Math.sin(ry), cx_ = Math.cos(rx), sx = Math.sin(rx);
  const breathe = 1 + 0.02 * Math.sin(lt * 3);
  for (let i = 0; i < NP; i++) {
    const d = SHAPES.delay[i] * 0.35;
    const u = eInOutCubic(clamp((prog - d) / (1 - 0.35)));
    const a = A[i], b = B[i], j = SHAPES.jit[i];
    const sw = Math.sin(u * Math.PI) * 0.9;
    let x = lerp(a[0], b[0], u) + j[0] * sw, y = lerp(a[1], b[1], u) + j[1] * sw, z = lerp(a[2], b[2], u) + j[2] * sw;
    x *= breathe; y *= breathe; z *= breathe;
    const x1 = x * cy_ + z * sy, z1 = -x * sy + z * cy_;
    const y2 = y * cx_ - z1 * sx, z2 = y * sx + z1 * cx_;
    const zz = z2 + dist;
    if (zz < 0.05) continue;
    const px = CX + (x1 * f) / zz, py = CY + (y2 * f) / zz;
    const s = clamp(4.3 / zz, 0.3, 40);
    const depth = clamp((z2 + 1.3) / 2.6);
    const hot = SHAPES.hue[i] < 0.42;
    glowDot(hot ? SPR.clay : SPR.cream, px, py, (hot ? 7 : 5.5) * s * (1 + exitK * 3), (1 - depth * 0.65) * 0.9);
  }
  g.globalCompositeOperation = 'source-over';
  // captions
  for (const c of S.captions) {
    if (t < c.t || t > c.e) continue;
    const a = clamp((t - c.t) / 0.12) * clamp((c.e - t) / 0.12);
    g.globalAlpha = a;
    g.fillStyle = C.cream;
    font(800, 46);
    g.shadowColor = 'rgba(0,0,0,0.9)'; g.shadowBlur = 24;
    textC(c.w, CX, H - 104 + 12 * Math.exp(-(t - c.t) * 14), lerp(40, 18, eOutExpo(clamp((t - c.t) / 0.4))));
    g.shadowBlur = 0;
    g.globalAlpha = 1;
  }
  fx.flash = Math.max(fx.flash, Math.exp(-lt * 10) * 0.6);
  fx.flashCol = [1, 0.97, 0.93];
  fx.glitch = Math.exp(-lt * 12) * 0.8;
  fx.zoom = exitK * 1.4 + Math.exp(-lt * 6) * 0.5;
  fx.ca += exitK * 1.5;
  fx.bloom = 0.95;
  hud(t, 'rgba(243,237,227,0.45)', '04 — FORM');
}

// ------------------------------------------------------------------ S6 : warp
const STARS = (() => {
  const r = mulberry32(5), a = [];
  for (let i = 0; i < 1700; i++) {
    const ang = r() * TAU, rad = 0.25 + Math.pow(r(), 0.7) * 3.2;
    a.push({ x: Math.cos(ang) * rad, y: Math.sin(ang) * rad, z: r() * 24, c: r() < 0.22 ? 1 : r() < 0.12 ? 2 : 0 });
  }
  return a;
})();
function warpDist(u) { return 3 * u + 2.1 * Math.pow(u, 3.1); } // integral of speed
function warpSpeed(u) { return 3 + 2.1 * 3.1 * Math.pow(u, 2.1); }
function S6(t) {
  const S = TL.s6;
  const u = Math.min(t, S.collapse) - S.start;
  bg('bg');
  if (t >= S.dark) {
    // the held breath: one point of light
    const k = (t - S.dark) / (S.end - S.dark);
    g.globalCompositeOperation = 'lighter';
    glowDot(SPR.white, CX, CY, 14 + 30 * k * k, 0.6 + 0.4 * Math.abs(Math.sin(k * 9)));
    glowDot(SPR.clay, CX, CY, 60 + 140 * k * k, 0.3 + 0.5 * k);
    g.globalCompositeOperation = 'source-over';
    fx.vig = 0.9; fx.bloom = 1.2; fx.grain = 0.05;
    return;
  }
  const col_ = eInCubic(inv(S.collapse, S.dark, t));
  g.save();
  g.translate(CX, CY);
  g.scale(1 - col_ * 0.97, 1 - col_ * 0.97);
  g.rotate(col_ * 0.9);
  g.translate(-CX, -CY);
  const dist = warpDist(u), sp = warpSpeed(u);
  const f = 760;
  g.globalCompositeOperation = 'lighter';
  glowDot(SPR.clay, CX, CY, 400 + Math.min(sp, 30) * 10, 0.22 + clamp(u / 4) * 0.12);
  g.lineCap = 'round';
  const trail = Math.min(0.02 + sp * 0.012, 1.6);
  for (const s of STARS) {
    const z = ((((s.z - dist) % 24) + 24) % 24) + 0.15;
    const z2 = z + trail;
    const x1 = CX + (s.x * f) / z, y1 = CY + (s.y * f) / z;
    const x2 = CX + (s.x * f) / z2, y2 = CY + (s.y * f) / z2;
    const a = clamp((24 - z) / 10) * clamp(z * 2);
    g.strokeStyle = s.c === 1 ? `rgba(255,128,84,${a})` : s.c === 2 ? `rgba(150,190,255,${a})` : `rgba(255,244,230,${a})`;
    g.lineWidth = clamp(3.2 / z, 0.6, 6);
    g.beginPath(); g.moveTo(x2, y2); g.lineTo(x1, y1); g.stroke();
  }
  // portals
  S.rings.forEach((tp, i) => {
    const d = (tp - t) * 5.5 + 0.02;
    if (d <= 0.02 || d > 14) return;
    const r = (2.3 * f) / d;
    const a = clamp((14 - d) / 6) * clamp(d / 0.35);
    const rot = t * (i % 2 ? 1.4 : -1.4) + i;
    g.strokeStyle = `rgba(255,128,84,${a * 0.35})`;
    g.lineWidth = clamp(90 / d, 2, 160);
    g.beginPath(); g.arc(CX, CY, r, 0, TAU); g.stroke();
    g.strokeStyle = `rgba(255,240,225,${a})`;
    g.lineWidth = clamp(14 / d, 1, 40);
    for (let k = 0; k < 6; k++) {
      g.beginPath(); g.arc(CX, CY, r, rot + (k * TAU) / 6, rot + (k * TAU) / 6 + TAU / 6 - 0.18); g.stroke();
    }
    // tick marks
    g.lineWidth = clamp(6 / d, 1, 16);
    g.beginPath();
    for (let k = 0; k < 48; k++) {
      const an = -rot * 0.5 + (k * TAU) / 48;
      g.moveTo(CX + Math.cos(an) * r * 1.06, CY + Math.sin(an) * r * 1.06);
      g.lineTo(CX + Math.cos(an) * r * (k % 4 ? 1.09 : 1.14), CY + Math.sin(an) * r * (k % 4 ? 1.09 : 1.14));
    }
    g.stroke();
  });
  g.globalCompositeOperation = 'source-over';
  // words riding the portals
  S.rings.forEach((tp, i) => {
    if (i >= S.words.length) return;
    if (i > 0 && t < S.rings[i - 1]) return; // one word at a time: only the next portal speaks
    const d = (tp - t) * 5.5 + 0.02;
    if (d < 0.25 || d > 9) return;
    const size = clamp((1.0 * f) / d, 10, 700) * 0.42;
    const a = clamp((9 - d) / 3) * clamp((d - 0.25) / 0.5);
    g.globalAlpha = a;
    g.fillStyle = i === S.words.length - 1 ? C.clay2 : C.cream;
    font(900, size);
    textC(S.words[i], CX, CY, -size * 0.02);
    g.globalAlpha = 1;
  });
  g.globalCompositeOperation = 'lighter';
  glowDot(SPR.white, CX, CY, 30 + col_ * 200, 0.4 + col_);
  g.globalCompositeOperation = 'source-over';
  g.restore();
  const ramp = clamp(u / (S.collapse - S.start));
  fx.zoom = 0.15 + ramp * ramp * 0.9 + col_ * 1.5;
  fx.ca += ramp * ramp * 2.2 + col_ * 3;
  fx.shake += ramp * ramp * 14 + col_ * 30;
  fx.bloom = 0.6 + ramp * 0.25;
  fx.flash = Math.max(fx.flash, Math.exp(-(t - S.start) * 9) * 0.7);
  fx.barrel = 0.04 + ramp * 0.25;
  // strobing on the last, fastest portals
  if (t > S.rings[6] && t < S.collapse && Math.floor(t * 60) % 4 === 0) fx.flash = Math.max(fx.flash, 0.18);
  hud(t, 'rgba(243,237,227,0.45)', '05 — ACCELERATE');
}

// ------------------------------------------------------------------ S7 : reveal
const BOOM_P = (() => {
  const r = mulberry32(77), a = [];
  for (let i = 0; i < 1900; i++) {
    const ang = r() * TAU, sp = 200 + Math.pow(r(), 2.4) * 4200;
    a.push({ ang, sp, w: 0.8 + r() * 2.8, c: r() < 0.4 ? 1 : r() < 0.3 ? 2 : 0, life: 0.7 + r() * 1.2, ph: r() * TAU });
  }
  return a;
})();
const EMBERS = (() => {
  const r = mulberry32(8), a = [];
  for (let i = 0; i < 240; i++) a.push({ x: r() * W, y: r() * H, sp: 12 + r() * 40, s: 1 + r() * 3.5, ph: r() * TAU, c: r() < 0.5 });
  return a;
})();
const titleC = document.createElement('canvas'); titleC.width = 1700; titleC.height = 420;
const tc = titleC.getContext('2d');
function S7(t) {
  const S = TL.s7;
  const dt = t - S.start;
  bg('bg');
  g.globalCompositeOperation = 'lighter';
  // god rays
  const rayA = 0.085 * clamp(dt / 0.2) * (1 - 0.55 * clamp((dt - 1) / 3));
  g.save(); g.translate(CX, CY); g.rotate(dt * 0.07);
  for (let k = 0; k < 22; k++) {
    const an = (k * TAU) / 22 + hash1(k + 40) * 0.2, wdt = 0.015 + 0.03 * hash1(k);
    const gr = g.createRadialGradient(0, 0, 60, 0, 0, 1300);
    gr.addColorStop(0, `rgba(255,150,100,${rayA * (0.6 + hash1(k + 9))})`);
    gr.addColorStop(1, 'rgba(255,150,100,0)');
    g.fillStyle = gr;
    g.beginPath(); g.moveTo(0, 0); g.arc(0, 0, 1400, an - wdt, an + wdt); g.closePath(); g.fill();
  }
  g.restore();
  glowDot(SPR.clay, CX, CY, 1100, 0.3 + 0.5 * Math.exp(-dt * 1.5));
  glowDot(SPR.white, CX, CY, 500 * Math.exp(-dt * 2), Math.exp(-dt * 3));
  // shock rings
  for (const [delay, max, c, w] of [[0, 2100, 'rgba(255,245,235,', 60], [0.06, 1700, 'rgba(255,128,84,', 44], [0.15, 1300, 'rgba(255,245,235,', 30], [0.3, 900, 'rgba(150,190,255,', 16]]) {
    const u = dt - delay;
    if (u <= 0) continue;
    const r = eOutExpo(clamp(u / 1.1)) * max;
    g.strokeStyle = c + Math.exp(-u * 2.4) + ')';
    g.lineWidth = 2 + w * Math.exp(-u * 5);
    g.beginPath(); g.arc(CX, CY, r, 0, TAU); g.stroke();
  }
  // debris -> embers
  g.lineCap = 'round';
  for (const p of BOOM_P) {
    const a = 1 - dt / p.life;
    if (a <= 0) continue;
    const r1 = burstPos(p, dt, 2.2), r0 = burstPos(p, Math.max(0, dt - 0.05), 2.2);
    const cs = Math.cos(p.ang), sn = Math.sin(p.ang);
    g.strokeStyle = p.c === 1 ? `rgba(255,128,84,${a})` : p.c === 2 ? `rgba(150,190,255,${a})` : `rgba(255,240,222,${a})`;
    g.lineWidth = p.w;
    g.beginPath(); g.moveTo(CX + cs * r0, CY + sn * r0); g.lineTo(CX + cs * r1 + cs * 2, CY + sn * r1 + sn * 2); g.stroke();
  }
  const emA = clamp((dt - 0.4) / 1.2);
  for (const e of EMBERS) {
    const y = (((e.y - dt * e.sp) % H) + H) % H;
    const x = e.x + Math.sin(dt * 0.8 + e.ph) * 30;
    glowDot(e.c ? SPR.clay : SPR.cream, x, y, e.s * 5, emA * (0.25 + 0.35 * Math.sin(dt * 2 + e.ph) ** 2));
  }
  g.globalCompositeOperation = 'source-over';
  // ---- title layer (rendered separately so the shine can be clipped to the glyphs)
  tc.clearRect(0, 0, titleC.width, titleC.height);
  tc.font = '900 250px "Inter Tight"';
  tc.fillStyle = C.cream;
  {
    // two words laid out explicitly so the gap between OPUS and 5.5 is generous and exact
    tc.letterSpacing = '-5px';
    const wa = tc.measureText('OPUS').width - 5, wb = tc.measureText('5.5').width - 5, gap = 78;
    const x0 = titleC.width / 2 - (wa + gap + wb) / 2;
    tc.letterSpacing = '0px';
    textC('OPUS', x0 + wa / 2, titleC.height / 2, -5, tc);
    textC('5.5', x0 + wa + gap + wb / 2, titleC.height / 2, -5, tc);
  }
  const sh = inv(S.shine, S.shine + 0.75, t);
  if (sh > 0 && sh < 1) {
    tc.globalCompositeOperation = 'source-atop';
    const sx = lerp(-400, titleC.width + 400, eInOutCubic(sh));
    const gr = tc.createLinearGradient(sx - 160, 0, sx + 160, 0);
    gr.addColorStop(0, 'rgba(255,255,255,0)'); gr.addColorStop(0.5, 'rgba(255,190,150,1)'); gr.addColorStop(1, 'rgba(255,255,255,0)');
    tc.fillStyle = gr;
    tc.save(); tc.translate(sx, titleC.height / 2); tc.transform(1, 0, -0.35, 1, 0, 0); tc.translate(-sx, -titleC.height / 2);
    tc.fillRect(0, 0, titleC.width, titleC.height); tc.restore();
    tc.globalCompositeOperation = 'source-over';
  }
  const s = 1 + 2.3 * Math.exp(-dt * 11) + 0.02 * Math.exp(-dt * 0.4);
  const flick = dt < 0.22 ? (hash1(Math.floor(t * 60)) > 0.3 ? 1 : 0.35) : 1;
  const ta = clamp(dt * 14) * flick;
  const ty = CY - 10;
  g.save();
  g.translate(CX, ty); g.scale(s, s);
  g.globalAlpha = ta * (0.22 + 0.4 * Math.exp(-dt * 3));
  g.filter = 'blur(34px)';
  g.globalCompositeOperation = 'lighter';
  g.drawImage(titleC, -titleC.width / 2, -titleC.height / 2);
  g.filter = 'none';
  g.globalCompositeOperation = 'source-over';
  g.globalAlpha = ta;
  g.drawImage(titleC, -titleC.width / 2, -titleC.height / 2);
  g.restore();
  // CLAUDE wordmark
  const ca = eOutExpo(inv(S.start + 0.35, S.start + 1.2, t));
  g.globalAlpha = ca * 0.85;
  g.fillStyle = C.cream;
  font(600, 40);
  textC('CLAUDE', CX, ty - 190, lerp(60, 26, ca));
  g.globalAlpha = 1;
  // rule
  const lw = eOutExpo(inv(S.line, S.line + 0.6, t)) * 560;
  g.fillStyle = C.clay2;
  g.fillRect(CX - lw / 2, ty + 150, lw, 4);
  // closing prompt
  let n = 0;
  while (n < S.typed.length && S.typed[n] <= t) n++;
  g.font = '400 34px "JetBrains Mono"'; g.textAlign = 'left'; g.textBaseline = 'middle';
  const cw = g.measureText('M').width;
  const x0 = CX - (cw * S.text.length) / 2;
  const yy = ty + 228;
  for (let i = 0; i < n; i++) { g.fillStyle = i < 2 ? C.clay2 : C.cream; g.fillText(S.text[i], x0 + i * cw, yy); }
  const typing = t >= S.typeStart - 0.05 && n < S.typed.length;
  if (t > S.typeStart - 0.9 && t < S.black && (typing || Math.floor((t - S.typeStart) * 2.4) % 2 === 0)) {
    g.globalAlpha = clamp((t - (S.typeStart - 0.9)) / 0.2);
    g.fillStyle = C.clay2; g.fillRect(x0 + n * cw + 2, yy - 18, cw * 0.62, 36);
    g.globalAlpha = 1;
  }
  // fade out (everything but the cursor fades first)
  const fo = eInOutCubic(inv(S.fade, S.black, t));
  if (fo > 0) {
    g.fillStyle = `rgba(8,7,11,${fo})`;
    g.fillRect(-300, -300, W + 600, H + 600);
    if (t < S.black && Math.floor((t - S.typeStart) * 2.4) % 2 === 0) { g.fillStyle = C.clay2; g.fillRect(x0 + n * cw + 2, yy - 18, cw * 0.62, 36); }
  }
  if (t >= S.black) bg('bg');
  // post
  fx.flash = Math.exp(-dt * 5.5);
  fx.flashCol = [1, 0.98, 0.95];
  fx.invert = dt < 2 / 60 ? 1 : 0;
  fx.zoom = 1.3 * Math.exp(-dt * 3.2);
  fx.bloom = 0.45 + 0.6 * Math.exp(-dt * 2);
  fx.grain = 0.045;
  fx.ca += 0.1;
  fx.vig = 0.5;
}

// ------------------------------------------------------------------ master
const SCENES = [
  [0, TL.bang, S0],
  [TL.bang, TL.s2.start, S1],
  [TL.s2.start, TL.s2.end, S2],
  [TL.s3.start, TL.s3.end, S3],
  [TL.s4.start, TL.s4.end, S4],
  [TL.s5.start, TL.s5.end, S5],
  [TL.s6.start, TL.s6.end, S6],
  [TL.s7.start, Infinity, S7],
];
function renderFrame(t) {
  resetFx();
  const im = impacts(t);
  // scenes add their own shake/ca to fx; we need shake before drawing, so run the scene
  // into the canvas with a provisional transform and apply shake from cues + scene ramp.
  const sceneShake = sceneShakeAt(t);
  const sh = im.sh + sceneShake;
  const ox = sh * vnoise(t * 37 + 3.3), oy = sh * vnoise(t * 41 + 17.1), rot = sh * 0.0007 * vnoise(t * 29 + 9);
  g.setTransform(1, 0, 0, 1, 0, 0);
  g.globalAlpha = 1; g.globalCompositeOperation = 'source-over'; g.filter = 'none'; g.shadowBlur = 0;
  g.translate(CX + ox, CY + oy); g.rotate(rot); g.translate(-CX, -CY);
  const sc_ = SCENES.find(([a, b]) => t >= a && t < b) || SCENES[SCENES.length - 1];
  sc_[2](t);
  g.setTransform(1, 0, 0, 1, 0, 0);
  fx.ca += im.ca;
  // upload + post
  gl.bindTexture(gl.TEXTURE_2D, texo);
  gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, true);
  gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, sc);
  gl.generateMipmap(gl.TEXTURE_2D);
  gl.uniform1f(U.time, t);
  gl.uniform1f(U.ca, fx.ca);
  gl.uniform1f(U.zoom, clamp(fx.zoom, 0, 2));
  gl.uniform1f(U.flash, fx.flash);
  gl.uniform1f(U.glitch, fx.glitch);
  gl.uniform1f(U.bloom, fx.bloom);
  gl.uniform1f(U.vig, fx.vig);
  gl.uniform1f(U.grain, fx.grain);
  gl.uniform1f(U.invert, fx.invert);
  gl.uniform1f(U.barrel, fx.barrel);
  gl.uniform3fv(U.flashCol, fx.flashCol);
  gl.uniform2fv(U.zc, fx.zc);
  gl.drawArrays(gl.TRIANGLES, 0, 3);
  gl.finish();
}
// scene-driven camera shake (the scenes' own fx.shake is computed while drawing, so the
// ramps that need to shake the camera are mirrored here as pure functions of t)
function sceneShakeAt(t) {
  const s0 = TL.s0, s3 = TL.s3, s6 = TL.s6;
  let s = 0;
  s += eInCubic(inv(s0.collapse, TL.bang, t)) * 6 * (t < TL.bang ? 1 : 0);
  if (t >= s3.start && t < s3.end) s += eInExpo(inv(s3.dive, s3.end, t)) * 10;
  if (t >= s6.start && t < s6.dark) {
    const r = clamp((Math.min(t, s6.collapse) - s6.start) / (s6.collapse - s6.start));
    s += r * r * 14 + eInCubic(inv(s6.collapse, s6.dark, t)) * 30;
  }
  return s;
}


window.TL = TL;
window.renderFrame = renderFrame;
window.__ready = true;

// realtime preview: open /src/index.html?play in a browser
if (new URLSearchParams(location.search).has('play')) {
  const t0 = performance.now();
  const loop = () => { renderFrame(((performance.now() - t0) / 1000) % TL.duration); requestAnimationFrame(loop); };
  loop();
}
