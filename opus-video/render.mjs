// Renders every frame of src/index.html with headless Chromium.
//   node render.mjs                      -> all frames into frames/
//   node render.mjs --stills 1.2,5,30    -> single PNGs into stills/ (for checking)
//   node render.mjs --workers 3 --from 0 --to 600
import fs from 'node:fs';
import http from 'node:http';
import path from 'node:path';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';

const require = createRequire(import.meta.url);
let playwright;
try { playwright = require('playwright'); } catch { playwright = require('/opt/node22/lib/node_modules/playwright'); }

const ROOT = path.dirname(fileURLToPath(import.meta.url));
const args = process.argv.slice(2);
const opt = (k, d) => { const i = args.indexOf('--' + k); return i >= 0 ? args[i + 1] : d; };
const TL = JSON.parse(fs.readFileSync(path.join(ROOT, 'src/timeline.json'), 'utf8'));
const FPS = TL.fps;
const TOTAL = Math.round(TL.duration * FPS);

const MIME = { '.html': 'text/html', '.js': 'text/javascript', '.json': 'application/json', '.woff2': 'font/woff2' };
const server = http.createServer((req, res) => {
  const p = path.join(ROOT, decodeURIComponent(new URL(req.url, 'http://x').pathname));
  if (!p.startsWith(ROOT) || !fs.existsSync(p) || fs.statSync(p).isDirectory()) { res.writeHead(404); return res.end(); }
  res.writeHead(200, { 'Content-Type': MIME[path.extname(p)] || 'application/octet-stream' });
  fs.createReadStream(p).pipe(res);
});
await new Promise((r) => server.listen(0, '127.0.0.1', r));
const URL_ = `http://127.0.0.1:${server.address().port}/src/index.html`;

const browser = await playwright.chromium.launch({
  args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist', '--font-render-hinting=none'],
});

async function openPage() {
  const page = await browser.newPage({ viewport: { width: TL.width, height: TL.height }, deviceScaleFactor: 1 });
  const errors = [];
  page.on('pageerror', (e) => errors.push(e.message));
  page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
  await page.goto(URL_);
  await page.waitForFunction(() => window.__ready === true || false, null, { timeout: 60000 }).catch(() => {});
  if (errors.length || !(await page.evaluate(() => window.__ready === true))) throw new Error('page failed: ' + errors.join(' | '));
  page.__errors = errors;
  return page;
}
async function shot(page, t, file) {
  await page.evaluate((t) => window.renderFrame(t), t);
  const buf = await page.screenshot({ type: 'png', clip: { x: 0, y: 0, width: TL.width, height: TL.height } });
  fs.writeFileSync(file, buf);
  if (page.__errors.length) throw new Error(`error at t=${t}: ${page.__errors.join(' | ')}`);
}

const stills = opt('stills');
if (stills) {
  const dir = path.join(ROOT, opt('out', 'stills'));
  fs.mkdirSync(dir, { recursive: true });
  const page = await openPage();
  for (const s of stills.split(',')) {
    const t = parseFloat(s);
    await shot(page, t, path.join(dir, `t_${t.toFixed(3)}.png`));
    console.log('still', t);
  }
} else {
  const dir = path.join(ROOT, 'frames');
  fs.mkdirSync(dir, { recursive: true });
  const from = +opt('from', 0), to = +opt('to', TOTAL);
  const workers = +opt('workers', 3);
  const todo = [];
  for (let f = from; f < to; f++) {
    const file = path.join(dir, `f_${String(f).padStart(5, '0')}.png`);
    if (!fs.existsSync(file)) todo.push([f, file]);
  }
  console.log(`${todo.length} frames to render (${from}..${to - 1}) with ${workers} workers`);
  let done = 0; const start = Date.now();
  await Promise.all(Array.from({ length: workers }, async (_, w) => {
    const page = await openPage();
    for (let k = w; k < todo.length; k += workers) {
      const [f, file] = todo[k];
      const tmp = file + '.tmp';
      await shot(page, f / FPS, tmp);
      fs.renameSync(tmp, file);
      if (++done % 60 === 0) {
        const el = (Date.now() - start) / 1000;
        console.log(`${done}/${todo.length}  ${(done / el).toFixed(2)} fps  eta ${((todo.length - done) / (done / el) / 60).toFixed(1)} min`);
      }
    }
  }));
}
await browser.close();
server.close();
