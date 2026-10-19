"""Build index.html (the standalone Tarot Log site) from src/template7.html + src/cards.json.
Usage: python3 src/build_site.py   (from the repo root). Images and icons already live in the repo root."""
import re, os
from pathlib import Path
SRC = Path(__file__).resolve().parent; ROOT = SRC.parent
t = (SRC / 'template7.html').read_text()
def rep(a, b, n=1):
    global t
    assert t.count(a) == n, (t.count(a), a[:60])
    t = t.replace(a, b)

# images: plain files
rep("const IMG = __IMGS__;\nconst src = k => IMG[k] || ('cards/' + k + '.jpg');", "const src = k => 'cards/' + k + '.jpg';")
# head: real icon files + manifest
t = re.sub(r'<link rel="apple-touch-icon"[^\n]*\n', '<link rel="apple-touch-icon" href="icon.png">\n<link rel="manifest" href="manifest.webmanifest">\n', t)
t = re.sub(r'<link rel="icon"[^\n]*\n', '<link rel="icon" type="image/png" href="icon-192.png">\n', t)
rep('<meta name="apple-mobile-web-app-capable" content="yes">', '<meta name="apple-mobile-web-app-capable" content="yes">\n<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">')

# connect panel in history sheet
rep('<p class="mode" id="hmode"></p>', '''<p class="mode" id="hmode"></p>
    <div class="ha"><button type="button" id="hs">Sync now</button></div>
    <details class="conn" id="conn"><summary>Google Sheet connection</summary>
      <div class="cbody">
        <input class="q2" id="cu" type="text" placeholder="Paste the setup link, or the web app URL" aria-label="Setup link or web app URL" autocomplete="off" autocapitalize="off" autocorrect="off">
        <input class="q2" id="ct" type="text" placeholder="Passcode (not needed if you pasted the setup link)" aria-label="Passcode" autocomplete="off" autocapitalize="off" autocorrect="off">
        <div class="ha"><button type="button" id="cs">Connect</button><button type="button" id="cc">Copy setup link</button><button type="button" id="cd">Disconnect</button></div>
        <p class="mode" id="cmsg"></p>
      </div></details>''')
rep("</style>", """.conn { background: var(--surface); border: 1px solid var(--line); border-radius: 10px; padding: 10px 14px; }
.conn summary { cursor: pointer; font-weight: 700; min-height: 28px; }
.cbody { display: grid; gap: 10px; margin-top: 10px; }
.more2 { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; justify-content: center; }
.more2 button { height: 40px; padding-inline: 16px; border-radius: 8px; border: 1px solid var(--line); background: var(--surface); font-weight: 700; }
.more2 span { color: var(--muted); font-size: .78rem; width: 100%; text-align: center; }
</style>""")

# storage: Google Sheet through an Apps Script web app, with a device cache and an outbox for failed writes
a = t.index("/* ---------- history: saved")
b = t.index("function entryFrom()")
store = r'''/* ---------- history: kept in a Google Sheet through an Apps Script web app; this device keeps a cache and retries failed writes ---------- */
const newId = () => Date.now().toString(36) + randInt(46656).toString(36);
const CFG_KEY = 'tarotCfg', LOCAL_KEY = 'pocketTarotHistory', OUT_KEY = 'tarotOutbox', PAGE = 20;
const lsGet = (k, d) => { try { const v = JSON.parse(localStorage.getItem(k) || 'null'); return v === null ? d : v; } catch (e) { return d; } };
const lsSet = (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) {} };
/* a setup link carries the web app address and passcode in its #fragment, so it is never sent to any server */
(function () {
  try {
    const h = new URLSearchParams(location.hash.slice(1)), u = h.get('u'), t = h.get('t');
    if (u && t) { lsSet(CFG_KEY, { u, t }); window.history.replaceState(null, '', location.pathname + location.search); }
  } catch (e) {}
})();
const store = {
  cfg: lsGet(CFG_KEY, null), items: [], total: 0, shown: PAGE, ready: false, err: '', flushing: null,
  get mode() { return this.cfg ? 'sheet' : 'local'; },
  saveLocal() { lsSet(LOCAL_KEY, this.items.slice(0, 200)); },
  async api(q, body) {
    const u = new URL(this.cfg.u); let res;
    if (body) res = await fetch(u.toString(), { method: 'POST', body: JSON.stringify(Object.assign({ token: this.cfg.t }, body)), redirect: 'follow' });
    else { u.searchParams.set('token', this.cfg.t); Object.keys(q).forEach(k => u.searchParams.set(k, q[k])); res = await fetch(u.toString(), { redirect: 'follow' }); }
    const j = await res.json();
    if (!j.ok) throw new Error(j.error || 'error');
    return j;
  },
  pending() { return lsGet(OUT_KEY, []).length; },
  flush() {
    if (!this.cfg) return Promise.resolve();
    if (this.flushing) return this.flushing;
    const p = (async () => {
      for (;;) {
        const ob = lsGet(OUT_KEY, []);
        if (!ob.length) break;
        await this.api(null, ob[0]);
        const cur = lsGet(OUT_KEY, []); cur.shift(); lsSet(OUT_KEY, cur);
      }
    })();
    this.flushing = p;
    const done = () => { if (this.flushing === p) this.flushing = null; };
    p.then(done, done);
    return p;
  },
  enqueue(op) {
    if (!this.cfg) return;
    const ob = lsGet(OUT_KEY, []); ob.push(op); lsSet(OUT_KEY, ob);
    this.flush().then(() => { this.err = ''; renderHist(); }, () => { this.err = 'Could not reach the Sheet yet. Saved on this device and will retry.'; renderHist(); });
  },
  async init() {
    this.items = lsGet(LOCAL_KEY, []); this.total = this.items.length; this.ready = true; renderHist();
    if (this.cfg) await this.sync();
  },
  async sync() {
    try {
      await this.flush();
      const j = await this.api({ action: 'list', offset: 0, limit: 40 });
      const have = new Set(j.items.map(x => x.id)), waiting = [];
      lsGet(OUT_KEY, []).forEach(op => { if (op.action === 'put' && !have.has(op.entry.id)) { const { text, ...en } = op.entry; waiting.push(en); } });
      this.items = j.items.concat(waiting).sort((a, b) => b.ts - a.ts); this.total = j.total + waiting.length; this.err = ''; this.saveLocal();
    } catch (e) { this.err = 'Could not reach the Sheet. Showing what is saved on this device.'; }
    this.ready = true; renderHist();
  },
  async more(all) {
    this.shown = all ? Math.max(this.total, this.shown) : this.shown + PAGE;
    const target = Math.min(this.shown, this.total);
    if (this.cfg && this.items.length < target) {
      try {
        const j = await this.api({ action: 'list', offset: this.items.length, limit: target - this.items.length });
        const have = new Set(this.items.map(x => x.id));
        this.items = this.items.concat(j.items.filter(x => !have.has(x.id))); this.total = j.total; this.err = '';
      } catch (e) { this.err = 'Could not load more from the Sheet.'; }
    }
    renderHist();
  },
  async connect(u, t) {
    const old = this.cfg; this.cfg = { u, t };
    try { await this.api({ action: 'list', offset: 0, limit: 1 }); }
    catch (e) { this.cfg = old; throw e; }
    lsSet(CFG_KEY, this.cfg);
    /* history already on this device goes up to the Sheet (a repeat just overwrites the same row) */
    this.items.forEach(x => this.enqueue({ action: 'put', entry: Object.assign({}, x, { text: entryText(x) }) }));
    await this.sync();
  },
  disconnect() { this.cfg = null; try { localStorage.removeItem(CFG_KEY); } catch (e) {} this.err = ''; renderHist(); },
  async put(id, obj) {
    const e = Object.assign({ id }, obj), existed = this.items.some(x => x.id === id);
    this.items = [e].concat(this.items.filter(x => x.id !== id)).sort((a, b) => b.ts - a.ts);
    if (!existed) this.total += 1;
    this.saveLocal(); renderHist();
    this.enqueue({ action: 'put', entry: Object.assign({}, e, { text: entryText(e) }) });
  },
  async patch(id, p, quiet) {
    let merged = null;
    this.items = this.items.map(x => { if (x.id !== id) return x; merged = Object.assign({}, x, p); return merged; });
    this.saveLocal(); if (!quiet) renderHist();
    if (merged) this.enqueue({ action: 'patch', id, p: Object.assign({}, p, { text: entryText(merged) }) });
  },
  async del(id) {
    this.items = this.items.filter(x => x.id !== id); this.total = Math.max(0, this.total - 1);
    this.saveLocal(); renderHist();
    this.enqueue({ action: 'del', id });
  },
};

'''
t = t[:a] + store + t[b:]

# history list with paging + connection panel
a = t.index("let hist = $('hist');")
b = t.index("function openHist()")
hist = r'''function renderHist() {
  const sheet = $('hist');
  const on = store.mode === 'sheet';
  $('hmode').textContent = (on ? 'Saved to your Google Sheet, so every device sees the same list.' : 'Saved on this device only. Open “Google Sheet connection” below to sync across devices.') + (on && store.pending() ? ' ' + store.pending() + ' change(s) still waiting to upload.' : '') + (store.err ? ' ' + store.err : '');
  if (sheet.hidden) return;
  $('hs').hidden = !on;
  const ae = document.activeElement;
  if (ae && ae.tagName === 'TEXTAREA' && $('hlist').contains(ae)) return;
  $('cd').hidden = !on; $('cc').hidden = !on;
  const list = $('hlist'); list.textContent = '';
  if (!store.items.length) {
    const n = document.createElement('div'); n.className = 'none'; n.textContent = store.ready ? 'No draws saved yet. Each finished draw is added here automatically.' : 'Loading…';
    list.append(n); return;
  }
  const wrap = document.createElement('div'); wrap.style.display = 'grid'; wrap.style.gap = '12px';
  const total = Math.max(store.total, store.items.length);
  store.items.slice(0, store.shown).forEach(e => {
    const art = document.createElement('article'); art.className = 'hi';
    const hh = document.createElement('div'); hh.className = 'hh';
    const sp = SPREADS[e.spread] ? e.spread : 'compare';
    const b = document.createElement('b'); b.textContent = sp === 'compare' ? 'Compare options' : spreadTitle(sp);
    const tm = document.createElement('time'); tm.textContent = (e.manual ? 'By hand · ' : '') + fmtTime(e.ts);
    hh.append(b, tm); art.append(hh);
    if (e.q) { const q = document.createElement('div'); q.className = 'hq'; q.textContent = e.q; art.append(q); }
    entryGroups(e).forEach((g, gi) => {
      const box = document.createElement('div'); box.className = 'hg';
      if (sp === 'compare') { const gl = document.createElement('div'); gl.className = 'gl'; gl.textContent = (g.name && g.name.trim()) || 'Option ' + String.fromCharCode(65 + gi); box.append(gl); }
      const row = document.createElement('div'); row.className = 'hc';
      g.cards.forEach(c => {
        const im = document.createElement('img'); im.src = src(CARDS[c.i].k); im.alt = CARDS[c.i].n + ' (' + oriWord(c) + ')'; im.loading = 'lazy';
        im.className = (c.rev ? 'rv ' : '') + (c.jp ? 'jp ' : '') + (c.x ? 'xt' : ''); row.append(im);
      });
      box.append(row); art.append(box);
    });
    const ta = document.createElement('textarea'); ta.className = 'hn'; ta.id = 'note-' + e.id; ta.value = e.note || '';
    ta.placeholder = 'What happened? Outcome or notes'; ta.setAttribute('aria-label', 'Outcome or notes for this draw');
    let tmr;
    ta.addEventListener('input', () => { if (e.id === curId) curNote = ta.value; clearTimeout(tmr); tmr = setTimeout(() => store.patch(e.id, { note: ta.value }, true), 700); });
    ta.addEventListener('change', () => { clearTimeout(tmr); if (e.id === curId) curNote = ta.value; store.patch(e.id, { note: ta.value }, true); });
    art.append(ta);
    const ha = document.createElement('div'); ha.className = 'ha';
    const open = document.createElement('button'); open.type = 'button'; open.textContent = 'Open'; open.addEventListener('click', () => loadEntry(e));
    const cp = document.createElement('button'); cp.type = 'button'; cp.textContent = 'Copy'; cp.addEventListener('click', () => copyText(entryText(e) + (ta.value.trim() ? '\nOutcome: ' + ta.value.trim() : '')));
    const dl = document.createElement('button'); dl.type = 'button'; dl.className = 'del'; dl.textContent = 'Delete';
    let armed = 0;
    dl.addEventListener('click', () => {
      if (!armed) { armed = 1; dl.textContent = 'Tap again to delete'; setTimeout(() => { armed = 0; dl.textContent = 'Delete'; }, 3000); return; }
      store.del(e.id);
    });
    ha.append(open, cp, dl); art.append(ha);
    wrap.append(art);
  });
  list.append(wrap);
  const shownN = Math.min(store.shown, store.items.length);
  if (total > shownN || store.shown > store.items.length) {
    const m = document.createElement('div'); m.className = 'more2';
    m.append(mk('span', '', 'Showing ' + shownN + ' of ' + total));
    if (total > shownN) {
      const b1 = mk('button', '', 'Show ' + Math.min(PAGE, total - shownN) + ' more'); b1.type = 'button'; b1.addEventListener('click', () => store.more(false));
      const b2 = mk('button', '', 'Show all'); b2.type = 'button'; b2.addEventListener('click', () => store.more(true));
      m.append(b1, b2);
    }
    list.append(m);
  } else list.append(Object.assign(mk('p', 'mode', 'Showing all ' + total), { style: 'text-align:center' }));
}
$('cs').onclick = async () => {
  let u = $('cu').value.trim(), t = $('ct').value.trim(), msg = $('cmsg');
  const m = u.indexOf('#');
  if (m >= 0) { try { const h = new URLSearchParams(u.slice(m + 1)); u = h.get('u') || ''; t = h.get('t') || t; } catch (e) { u = ''; } }
  if (!/^https:\/\/script\.google\.com\//.test(u) || !t) { msg.textContent = 'Paste the full setup link, or the web app URL (starts with https://script.google.com/) plus the passcode.'; return; }
  msg.textContent = 'Connecting…';
  try { await store.connect(u, t); msg.textContent = 'Connected.'; $('cu').value = ''; $('ct').value = ''; }
  catch (e) { msg.textContent = 'Could not connect: ' + (e.message === 'auth' ? 'wrong passcode.' : 'check the URL and that the web app is deployed for “Anyone”.'); }
  renderHist();
};
$('cc').onclick = () => {
  if (!store.cfg) return;
  copyText(location.origin + location.pathname + '#u=' + encodeURIComponent(store.cfg.u) + '&t=' + encodeURIComponent(store.cfg.t));
  $('cmsg').textContent = 'Setup link copied. Paste it into the same box on another device or in the home-screen app. Keep it private, it contains your passcode.';
};
$('cd').onclick = () => { store.disconnect(); $('cmsg').textContent = 'Disconnected. History on this device stays, the Sheet is untouched.'; };
$('hs').onclick = async () => { const b = $('hs'); b.textContent = 'Syncing…'; await store.sync(); b.textContent = 'Sync now'; };
window.addEventListener('online', () => { if (store.cfg) store.sync(); });
document.addEventListener('visibilitychange', () => { if (!document.hidden && store.cfg) store.sync(); });
window.addEventListener('pagehide', () => { if (store.cfg) store.flush().catch(() => {}); });
'''
t = t[:a] + hist + t[b:]

# save a draw the moment it is dealt; save question and names while typing
rep("  curId = newId(); curTs = Date.now(); curNote = ''; saved = false;\n  window.scrollTo(0, 0);", "  curId = newId(); curTs = Date.now(); curNote = ''; saved = false;\n  persistCurrent();\n  window.scrollTo(0, 0);")
rep("  $('pile').classList.remove('on'); lock(false);\n  persistCurrent();\n}", "  $('pile').classList.remove('on'); lock(false);\n}")
rep("      inp.addEventListener('change', () => { if (draw && curId && saved) persistCurrent(); });", "      inp.addEventListener('input', persistSoon);\n      inp.addEventListener('change', () => { if (draw && curId && saved) persistCurrent(); });")
rep("$('q').addEventListener('change', () => { if (draw && curId && saved) persistCurrent(); });", "$('q').addEventListener('input', () => { if (S.mode === 'enter') persistSoon(); });\n$('q').addEventListener('change', () => { if (S.mode === 'enter' && draw && curId && saved) persistCurrent(); });")
rep("async function persistCurrent() {", "let pst;\nfunction persistSoon() { clearTimeout(pst); pst = setTimeout(() => { if (draw && curId && saved) persistCurrent(); }, 800); }\nasync function persistCurrent() {")

# page shell
i = t.index('<main class="wrap">')
head, body = t[:i], t[i:]
head = head.replace('<style>', '<style>\n[hidden] { display: none !important; }', 1)
doc = '<!doctype html>\n<html lang="vi">\n<head>\n<meta charset="utf-8">\n<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n' + head + '</head>\n<body>\n' + body + '\n</body>\n</html>\n'
doc = doc.replace('__CARDS__', (SRC / 'cards.json').read_text().strip())
assert '__CARDS__' not in doc and '__IMGS__' not in doc
(ROOT / 'index.html').write_text(doc)
print('wrote', ROOT / 'index.html', len(doc), 'bytes')
