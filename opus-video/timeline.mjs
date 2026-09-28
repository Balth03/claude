// Single source of truth for picture AND sound.
// Every visual beat and every sound cue is derived from this file, so the two can never drift.
// Run: node timeline.mjs  ->  writes src/timeline.json
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

function mulberry32(a) {
  return function () {
    a |= 0; a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
const rng = mulberry32(55);
const r4 = (x) => Math.round(x * 10000) / 10000;

const cues = [];
const cue = (t, type, o = {}) => cues.push({ t: r4(t), type, ...o });

// ---------------------------------------------------------------- S0 : the prompt
const s0 = { text: '> build me something impossible.', typeStart: 0.55, typed: [] };
{
  let t = s0.typeStart;
  for (let i = 0; i < s0.text.length; i++) {
    s0.typed.push(r4(t));
    if (s0.text[i] !== ' ') cue(t, 'key', { v: r4(rng()) });
    t += 0.03 + rng() * 0.015 + (s0.text[i] === ' ' ? 0.028 : 0);
  }
  s0.typeEnd = r4(t);
}
s0.collapse = 1.98;
const BANG = 2.4;
cue(s0.collapse, 'suck', { d: r4(BANG - s0.collapse) });
cue(BANG, 'bigbang');

// ---------------------------------------------------------------- S2 : word barrage
const s2 = { start: 3.6, step: 0.3, words: [] };
const WORDS = [
  ['THINK', 'giant', 'bg', 'cream'],
  ['DEEPER', 'giant', 'clay', 'ink'],
  ['READ', 'echo', 'bg', 'cream'],
  ['EVERYTHING', 'wide', 'bg', 'clay'],
  ['PLAN', 'split', 'cream', 'ink'],
  ['EACH STEP', 'stripes', 'bg', 'cream'],
  ['WRITE', 'giant', 'clay', 'ink'],
  ['THE CODE', 'mono', 'bg', 'cream'],
  ['RUN', 'giant', 'cream', 'ink'],
  ['THE TESTS', 'wide', 'bg', 'cream'],
  ['FIX', 'split', 'clay', 'ink'],
  ['WHAT BREAKS', 'glitchy', 'bg', 'cream'],
  ['SHIP', 'outline', 'bg', 'cream'],
  ['IT.', 'giant', 'clay', 'ink'],
  ['AGAIN', 'grid', 'bg', 'cream'],
  ['AND AGAIN', 'grid', 'cream', 'ink'],
];
WORDS.forEach(([w, style, bg, fg], i) => {
  const t = s2.start + i * s2.step;
  s2.words.push({ t: r4(t), w, style, bg, fg, rot: r4((rng() - 0.5) * 0.08) });
  cue(t, 'word', { i, p: r4(rng()) });
});
s2.end = r4(s2.start + WORDS.length * s2.step); // 8.4
cue(s2.end - 0.22, 'whoosh', { d: 0.3, up: 1 });

// ---------------------------------------------------------------- S3 : the mind
const s3 = { start: s2.end, end: 13.2, dive: 12.35, pulses: [] };
s3.words = [
  { t: 9.3, w: 'SEE' }, { t: 9.72, w: 'THE' }, { t: 10.14, w: 'WHOLE' }, { t: 10.68, w: 'SYSTEM.' },
];
s3.wordsOut = 11.95;
cue(s3.start, 'swell', { d: r4(s3.end - s3.start) });
s3.words.forEach((w) => cue(w.t, 'soft'));
{
  const n = 110;
  for (let i = 0; i < n; i++) {
    const t = 8.55 + 3.75 * Math.pow(rng(), 0.62);
    s3.pulses.push({ t: r4(t), e: r4(rng()), d: r4(0.35 + rng() * 0.35) });
  }
  s3.pulses.sort((a, b) => a.t - b.t);
  s3.pulses.forEach((p, i) => { if (i % 3 === 0) cue(p.t, 'ping', { pan: r4(rng() * 2 - 1), p: r4(rng()) }); });
}
cue(s3.dive, 'whoosh', { d: r4(s3.end - s3.dive), up: 1, big: 1 });
cue(s3.end, 'flashHit');

// ---------------------------------------------------------------- S4 : the build
const s4 = { start: 13.2, end: 18.6, panels: [13.3, 13.45, 13.6, 13.75, 13.9], term: 14.85, testsStart: 15.15, testsEnd: 17.55, stamp: 17.8, glitch: 18.42, total: 1284 };
s4.panels.forEach((t) => cue(t, 'pop'));
{
  let t = 13.35;
  while (t < 14.8) { cue(t, 'tick', { v: r4(rng()) }); t += 0.028 + rng() * 0.03; }
}
cue(s4.term, 'whoosh', { d: 0.28, up: 1 });
{
  // one audible blip per visible test line
  s4.lines = [];
  let t = s4.testsStart;
  let i = 0;
  while (t < s4.testsEnd) {
    s4.lines.push(r4(t));
    cue(t, 'blip', { k: r4((t - s4.testsStart) / (s4.testsEnd - s4.testsStart)) });
    const u = (t - s4.testsStart) / (s4.testsEnd - s4.testsStart);
    t += 0.075 - 0.045 * u; // accelerates
    i++;
  }
}
cue(s4.testsStart, 'riser', { d: r4(s4.stamp - s4.testsStart), lo: 180, hi: 900, q: 0.5 });
cue(s4.stamp, 'stamp');
cue(s4.glitch, 'glitch', { d: r4(s4.end - s4.glitch) });

// ---------------------------------------------------------------- S5 : shape of thought
const s5 = { start: 18.6, end: 23.4, form: 18.6, morphs: [19.8, 21.0, 22.2], settle: 22.9, exit: 23.05 };
s5.captions = [
  { t: 19.0, e: 19.72, w: 'ONE MIND' },
  { t: 19.85, e: 20.92, w: 'ANY SHAPE' },
  { t: 21.05, e: 22.1, w: 'ANY SCALE' },
];
cue(s5.form, 'whoosh', { d: 0.6, up: 0 });
s5.morphs.forEach((t) => { cue(t - 0.35, 'rev', { d: 0.35 }); cue(t, 'morph'); });
cue(s5.settle, 'shimmer');
cue(s5.exit, 'whoosh', { d: 0.35, up: 1, big: 1 });

// ---------------------------------------------------------------- S6 : warp
const s6 = { start: 23.4, end: 28.2, collapse: 27.55, dark: 27.95, rings: [] };
{
  let t = 24.0, g = 0.62;
  while (t < 27.46) { s6.rings.push(r4(t)); t += g; g *= 0.86; }
}
s6.words = ['SHARPER', 'FASTER', 'DEEPER', 'BOLDER', 'FURTHER', 'BEYOND'];
cue(s6.start, 'warp');
cue(s6.start, 'riser', { d: r4(s6.collapse - s6.start), lo: 90, hi: 2400, q: 1 });
s6.rings.forEach((t, i) => cue(t, 'ring', { i }));
cue(s6.collapse, 'implode', { d: r4(s6.dark - s6.collapse) });
cue(s6.dark, 'inhale', { d: r4(s6.end - s6.dark) });

// ---------------------------------------------------------------- S7 : reveal
const BOOM = s6.end;
const s7 = { start: BOOM, end: 35, shine: 29.6, line: 29.05, typeStart: 30.8, text: '> ready when you are.', typed: [], fade: 33.3, black: 34.6 };
cue(BOOM, 'boom');
cue(s7.shine, 'shimmer', { soft: 1 });
{
  let t = s7.typeStart;
  for (let i = 0; i < s7.text.length; i++) {
    s7.typed.push(r4(t));
    if (s7.text[i] !== ' ') cue(t, 'key', { v: r4(rng()), soft: 1 });
    t += 0.045 + rng() * 0.02 + (s7.text[i] === ' ' ? 0.03 : 0);
  }
}

cues.sort((a, b) => a.t - b.t);
const timeline = { fps: 60, width: 1920, height: 1080, duration: 35, bang: BANG, s0, s2, s3, s4, s5, s6, s7, cues };
const out = path.join(path.dirname(fileURLToPath(import.meta.url)), 'src', 'timeline.json');
fs.writeFileSync(out, JSON.stringify(timeline, null, 1));
console.log(`timeline: ${cues.length} cues, typed prompt ends at ${s0.typeEnd}s, ${s6.rings.length} rings, ${s4.lines.length} test lines -> ${out}`);
