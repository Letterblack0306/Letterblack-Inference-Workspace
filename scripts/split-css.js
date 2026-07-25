'use strict';
/* ------------------------------------------------------------------
 * split-css.js
 * Splits the minified app.css / ux.css into readable component files
 * and rewrites app.css / ux.css as @import aggregators.
 *
 * NOT hardcoded: the keyword -> file mapping is an editable config
 * (ROUTES) below. To add a new component file or handle new selectors
 * later, just add an entry. Output is pretty-printed (one declaration
 * per line) so future edits never get "mixed" into a minified blob.
 * ------------------------------------------------------------------ */
const fs = require('fs');
const path = require('path');

const CSS_DIR = path.join(__dirname, '..', 'web', 'css');

/* ---------------- EDITABLE ROUTING CONFIG ---------------- */
const APP_ROUTES = [
  { out: 'base/reset.css',       match: ['*', 'html,body', 'body', 'button,input,select,textarea'] },
  { out: 'layout/nav.css',       match: ['.navigation', '.nav-', '.version-card'] },
  { out: 'layout/header.css',    match: ['.app-bar', '.brand-', '.eyebrow', '.product-name', '.workspace-switcher', '.global-health', '.health-pill', '.status-dot', '.app-actions'] },
  { out: 'layout/shell.css',     match: ['.app-shell', '.main-content'] },
  { out: 'layout/inspector.css', match: ['.inspector', '.drawer', '.widget-catalog', '.catalog-'] },
  { out: 'components/button.css', match: ['.button', '.icon-button', '.mobile-nav-toggle', '.text-button', '.danger-text'] },
  { out: 'components/badge.css', match: ['.status-badge'] },
  { out: 'components/widget.css', match: ['.widget', '.workspace-grid', '.customizing', '.customize-banner', '.banner-actions'] },
  { out: 'pages/page.css',       match: ['.page', '.page-header', '.page-description', '.empty-state', '.section-head', '.content-grid', '.toolbar-row'] },
  { out: 'pages/runtime.css',    match: ['.runtime-', '.model-identity', '.model-avatar', '.tag-row', '.metric', '.allocation', '.legend', '.action-grid', '.action-tile', '.warning-text'] },
  { out: 'pages/machines.css',   match: ['.machine-', '.topology-', '.node-', '.mini-meter', '.add-machine-card', '.endpoint-card', '.endpoint-grid'] },
  { out: 'pages/telemetry.css',  match: ['.telemetry-', 'chart'] },
  { out: 'pages/models.css',     match: ['.models-table', '.model-list', '.model-row'] },
  { out: 'components/table.css', match: ['.data-table'] },
  { out: 'components/form.css',  match: ['.form-grid', '.search-input', 'input:focus', 'select:focus', 'textarea:focus', '.prompt-area', '.composer-actions', '.span-2'] },
  { out: 'pages/logs.css',       match: ['.log-', '.event-'] },
  { out: 'pages/settings.css',   match: ['.settings-', '.profile-'] },
  { out: 'components/modal.css', match: ['.modal', '.command-', '.small-modal', '.step-indicator', '.connection-test', '.shutdown-plan'] },
  { out: 'components/toast.css', match: ['.toast'] },
  { out: 'pages/extensions-surfaces.css', match: ['.stack-list', '.manifest-row', '.asset-row', '.manifest-meta', '.compact-empty'] },
  { out: 'components/card.css',  match: ['.split-workbench', '.response-empty', 'card'] },
];

/* Bare element selectors (exact match, checked before substring routes). */
const EXACT_ROUTES = {
  'button': 'base/reset.css',
};

const UX_ROUTES = [
  { out: 'ux/progress.css',   match: ['.ux-progress'] },
  { out: 'ux/job-drawer.css', match: ['.job-', '.dirty-dot'] },
  { out: 'ux/onboarding.css', match: ['.coachmark', '.onboarding', '.choice-', '.launch-summary', '.summary-card', '.machine-step', '.step-indicator', '.validation-', '.request-blocker', '.inline-notice'] },
  { out: 'ux/misc.css',       match: ['.kbd', '.save-state', '.button'] },
];

/* ---------------- tokenizer ---------------- */
function tokenize(src) {
  const chunks = [];
  let i = 0, n = src.length, depth = 0, start = 0, buf = '';
  let state = 'normal', quote = '';
  while (i < n) {
    const c = src[i];
    if (state === 'blockComment') { if (c === '*' && src[i + 1] === '/') { i += 2; state = 'normal'; continue; } i++; continue; }
    if (state === 'lineComment') { if (c === '\n') state = 'normal'; i++; continue; }
    if (state === 'string') { if (c === '\\') { i += 2; continue; } if (c === quote) state = 'normal'; i++; continue; }
    if (c === '/' && src[i + 1] === '*') { state = 'blockComment'; i += 2; continue; }
    if (c === '/' && src[i + 1] === '/') { state = 'lineComment'; i += 2; continue; }
    if (c === '"' || c === "'") { state = 'string'; quote = c; i++; continue; }
    if (c === '{') depth++;
    else if (c === '}') {
      depth--;
      if (depth === 0) { buf += src.slice(start, i + 1); chunks.push(buf); buf = ''; start = i + 1; i++; continue; }
    } else if (c === ';' && depth === 0) { buf += src.slice(start, i + 1); chunks.push(buf); buf = ''; start = i + 1; i++; continue; }
    i++;
  }
  if (start < n) { const t = src.slice(start).trim(); if (t) chunks.push(t); }
  return chunks;
}

/* ---------------- helpers ---------------- */
function splitPrelude(chunk) {
  let s = chunk.trim();
  const comments = [];
  while (s.startsWith('/*')) {
    const end = s.indexOf('*/');
    comments.push(s.slice(0, end + 2));
    s = s.slice(end + 2).trim();
  }
  let i = 0, depth = 0, state = 'normal', quote = '', open = -1;
  for (; i < s.length; i++) {
    const c = s[i];
    if (state === 'string') { if (c === '\\') { i++; continue; } if (c === quote) state = 'normal'; continue; }
    if (c === '"' || c === "'") { state = 'string'; quote = c; continue; }
    if (c === '(' || c === '[') depth++;
    else if (c === ')' || c === ']') depth--;
    else if (c === '{' && depth === 0) { open = i; break; }
  }
  if (open === -1) return { comments, prelude: s, body: null, isAtRule: s.startsWith('@') };
  const prelude = s.slice(0, open).trim();
  let d = 0, close = -1; state = 'normal'; quote = '';
  for (let j = open; j < s.length; j++) {
    const c = s[j];
    if (state === 'string') { if (c === '\\') { j++; continue; } if (c === quote) state = 'normal'; continue; }
    if (c === '"' || c === "'") { state = 'string'; quote = c; continue; }
    if (c === '{') d++;
    else if (c === '}') { d--; if (d === 0) { close = j; break; } }
  }
  const body = s.slice(open + 1, close === -1 ? s.length : close);
  return { comments, prelude, body, isAtRule: prelude.startsWith('@') };
}

function splitDeclarations(body) {
  const out = [];
  let depth = 0, state = 'normal', quote = '', cur = '';
  for (let i = 0; i < body.length; i++) {
    const c = body[i];
    if (state === 'string') { cur += c; if (c === '\\') { cur += body[i + 1] || ''; i++; continue; } if (c === quote) state = 'normal'; continue; }
    if (c === '"' || c === "'") { state = 'string'; quote = c; cur += c; continue; }
    if (c === '(' || c === '[') depth++;
    else if (c === ')' || c === ']') depth--;
    if (c === ';' && depth === 0) { out.push(cur); cur = ''; continue; }
    cur += c;
  }
  if (cur.trim()) out.push(cur);
  return out.map(x => x.trim()).filter(Boolean);
}

function formatChunk(chunk, indent) {
  const pad = '  '.repeat(indent);
  const { comments, prelude, body, isAtRule } = splitPrelude(chunk);
  const lines = [];
  for (const c of comments) lines.push(pad + c);
  if (body === null) { lines.push(pad + prelude + ';'); return lines.join('\n'); }
  lines.push(pad + prelude + ' {');
  if (isAtRule) {
    for (const r of tokenize(body)) lines.push(formatChunk(r, indent + 1));
  } else {
    for (const d of splitDeclarations(body)) lines.push(pad + '  ' + d + ';');
  }
  lines.push(pad + '}');
  return lines.join('\n');
}

function classify(prelude, routes, responsiveOut) {
  const sel = prelude.toLowerCase();
  if (sel.startsWith('@media')) return responsiveOut;
  if (Object.prototype.hasOwnProperty.call(EXACT_ROUTES, sel)) return EXACT_ROUTES[sel];
  for (const r of routes) {
    for (const m of r.match) {
      if (m === '*' ? sel === '*' : sel.includes(m)) return r.out;
    }
  }
  return 'misc.css';
}

/* ---------------- main ---------------- */
function process(file, routes, responsiveOut, label) {
  const abs = path.join(CSS_DIR, file);
  const src = fs.readFileSync(abs, 'utf8');
  const chunks = tokenize(src);
  const files = new Map();
  const firstIndex = new Map();
  chunks.forEach((c, idx) => {
    const { prelude } = splitPrelude(c);
    const out = classify(prelude, routes, responsiveOut);
    if (!files.has(out)) { files.set(out, []); firstIndex.set(out, idx); }
    files.get(out).push(formatChunk(c, 0));
  });

  for (const [out, rules] of files) {
    const target = path.join(CSS_DIR, out);
    fs.mkdirSync(path.dirname(target), { recursive: true });
    fs.writeFileSync(target, rules.join('\n\n') + '\n', 'utf8');
  }

  const ordered = [...files.keys()].sort((a, b) => firstIndex.get(a) - firstIndex.get(b));
  const imports = ordered.map(o => `@import url("${o}");`).join('\n');
  const aggregator = `/* ${label}\n * Auto-generated aggregator. Do not add rules here.\n * Add new component files via scripts/split-css.js (ROUTES config).\n */\n${imports}\n`;
  fs.writeFileSync(abs, aggregator, 'utf8');

  const norm = s => s.replace(/\s+/g, '').replace(/;/g, '');
  const originalSet = chunks.map(norm).sort();
  const rebuilt = [];
  for (const o of ordered) {
    const t = fs.readFileSync(path.join(CSS_DIR, o), 'utf8');
    rebuilt.push(...tokenize(t).map(norm));
  }
  rebuilt.sort();
  const pass = JSON.stringify(originalSet) === JSON.stringify(rebuilt);
  return { file, chunkCount: chunks.length, files: ordered, pass };
}

const results = [
  process('app.css', APP_ROUTES, 'base/responsive.css', 'app.css'),
  process('ux.css', UX_ROUTES, 'ux/responsive.css', 'ux.css'),
];
for (const r of results) {
  console.log(`\n${r.file}: ${r.chunkCount} chunks -> ${r.files.length} files | verify ${r.pass ? 'PASS' : 'FAIL'}`);
  r.files.forEach(f => console.log('   - ' + f));
}

