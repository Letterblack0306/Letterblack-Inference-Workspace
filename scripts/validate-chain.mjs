/* validate-chain.mjs
 * Fail-fast validation chain. Runs every check in order (fastest first) and
 * STOPS at the first failure so you get immediate, actionable feedback.
 *
 * Usage:  node scripts/validate-chain.mjs
 * Exit:   0 = all green, 1 = a step failed (chain halted).
 *
 * Add a new check by pushing a step onto `steps`. Keep fast checks early.
 */
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const WEB = path.join(ROOT, 'web');
const CONFIG = path.join(WEB, 'config');

const rel = p => path.relative(ROOT, p);
const read = p => fs.readFileSync(p, 'utf8');
const isDir = p => fs.statSync(p).isDirectory();

function walk(dir, out = []) {
  for (const name of fs.readdirSync(dir)) {
    const p = path.join(dir, name);
    if (isDir(p)) walk(p, out); else out.push(p);
  }
  return out;
}

function run(cmd, args, opts = {}) {
  const r = spawnSync(cmd, args, { cwd: ROOT, encoding: 'utf8', ...opts });
  if (r.error) throw r.error;
  if (r.status !== 0) {
    const e = new Error((r.stderr || r.stdout || ('exit ' + r.status)).trim());
    e.stderr = r.stderr; e.stdout = r.stdout;
    throw e;
  }
  return { stdout: (r.stdout || '').trim(), stderr: (r.stderr || '').trim() };
}

const steps = [];
const step = (name, fn) => steps.push({ name, fn });

/* ---- 1. environment contract guard ---- */
step('env contract guard', () => {
  const { stdout } = run('node', ['scripts/env-contract-guard.js']);
  return stdout.split('\n').filter(Boolean);
});

/* ---- 2. config JSON validity ---- */
step('config JSON valid', () => {
  const files = walk(CONFIG).filter(p => p.endsWith('.json'));
  const bad = [];
  for (const f of files) {
    try { JSON.parse(read(f)); } catch (e) { bad.push(`${rel(f)}: ${e.message}`); }
  }
  if (bad.length) throw new Error(bad.join('\n'));
  return `${files.length} JSON files valid: ` + files.map(f => path.relative(CONFIG, f)).join(', ');
});

/* ---- 3. icon gallery integrity ---- */
step('icon gallery integrity', () => {
  const svg = read(path.join(WEB, 'assets', 'icons.svg'));
  const ids = new Set([...svg.matchAll(/symbol id="(icon-[a-z0-9-]+)"/g)].map(m => m[1]));
  const openSym = (svg.match(/<symbol/g) || []).length;
  const closeSym = (svg.match(/<\/symbol>/g) || []).length;
  if (openSym !== closeSym) throw new Error(`unbalanced <symbol> tags: ${openSym}/${closeSym}`);
  const html = read(path.join(WEB, 'index.html'));
  const refs = new Set([...html.matchAll(/#(icon-[a-z0-9-]+)/g)].map(m => m[1]));
  for (const js of walk(path.join(WEB, 'js')).filter(p => p.endsWith('.js'))) {
    for (const m of read(js).matchAll(/icon\('([a-z0-9-]+)'/g)) refs.add('icon-' + m[1]);
  }
  const missing = [...refs].filter(r => !ids.has(r));
  if (missing.length) throw new Error('referenced icons missing from sprite: ' + missing.join(', '));
  return `${ids.size} symbols; ${refs.size} referenced icons all resolve`;
});

/* ---- 4. CSS aggregator + tokens integrity ---- */
step('css aggregator + tokens', () => {
  const cssDir = path.join(WEB, 'css');
  const detail = [];
  for (const agg of ['app.css', 'ux.css']) {
    const src = read(path.join(cssDir, agg));
    const imports = [...src.matchAll(/@import url\("([^"]+)"\);/g)].map(m => m[1]);
    const missing = imports.filter(relPath => !fs.existsSync(path.join(cssDir, relPath)));
    if (missing.length) throw new Error(`${agg} imports missing: ${missing.join(', ')}`);
    if (!imports.length) throw new Error(`${agg} has no @import entries`);
    detail.push(`${agg} -> ${imports.length} imports`);
  }
  const tokens = read(path.join(cssDir, 'tokens.css'));
  for (const tok of ['--canvas', '--accent', '--text', '--border']) {
    if (!tokens.includes(tok + ':')) throw new Error(`tokens.css missing ${tok}`);
  }
  detail.push('tokens.css core tokens present');
  return detail;
});

/* ---- 5. web/js ES module syntax ---- */
step('web/js ESM syntax', () => {
  const files = walk(path.join(WEB, 'js')).filter(p => p.endsWith('.js'));
  for (const f of files) {
    try {
      run('node', ['--input-type=module', '--check'], { input: read(f) });
    } catch {
      throw new Error('ESM syntax error in ' + rel(f));
    }
  }
  return `${files.length} modules OK: ` + files.map(f => path.basename(f)).join(', ');
});

/* ---- 6. config loaders merge (smoke) ---- */
step('config loaders merge', () => {
  const { stdout } = run('node', ['scripts/smoke-config.mjs']);
  return stdout.split('\n').filter(Boolean);
});

/* ---- 7. backend python syntax (lock-free, no .pyc writes) ---- */
step('backend python syntax', () => {
  const code = 'import ast,glob,sys\n' +
    'files=glob.glob("backend/**/*.py", recursive=True)\n' +
    'bad=[]\n' +
    'for f in files:\n' +
    '    try: ast.parse(open(f, encoding="utf-8").read())\n' +
    '    except SyntaxError as e: bad.append(f"{f}: {e}")\n' +
    'print("parsed %d python files OK" % len(files) if not bad else "\\n".join(bad))\n' +
    'sys.exit(1 if bad else 0)\n';
  const { stdout } = run('python', ['-c', code]);
  return stdout.split('\n').filter(Boolean);
});

/* ---- 8. python unit tests ---- */
step('python unit tests', () => {
  const { stdout, stderr } = run('python', ['-m', 'unittest', 'discover', '-s', 'tests', '-p', 'test_*.py']);
  const lines = (stderr || stdout).split('\n').map(s => s.trim()).filter(Boolean);
  return lines.slice(-2);
});

/* ---------------- fail-fast runner ---------------- */
const args = process.argv.slice(2);
const logFlag = args.some(a => a === '--log' || a === '-l' || a.startsWith('--log='));
const customPath = args.find(a => a.startsWith('--log='))?.slice('--log='.length);
const LOGS_DIR = path.join(ROOT, 'logs');

const lines = [];
const out = (s = '') => { lines.push(s); console.log(s); };
const err = (s = '') => { lines.push(s); console.error(s); };
function flushLog(exitCode) {
  if (!logFlag) return;
  try {
    fs.mkdirSync(LOGS_DIR, { recursive: true });
    const target = customPath ? path.resolve(customPath) : path.join(LOGS_DIR, 'validate-chain.log');
    const header = '# validate-chain  ' + new Date().toISOString() + '  exit=' + exitCode;
    fs.writeFileSync(target, header + '\n' + lines.join('\n') + '\n', 'utf8');
    console.log('log written to ' + path.relative(ROOT, target));
  } catch (e) {
    console.error('could not write log: ' + (e?.message || e));
  }
}

const start = Date.now();
let passed = 0;
out('Fail-fast validation chain\n' + '='.repeat(40));
for (const s of steps) {
  const t = Date.now();
  try {
    const result = await s.fn();
    passed++;
    out(`[PASS] ${s.name} (${Date.now() - t}ms)`);
    const det = Array.isArray(result) ? result : (result == null || result === '' ? [] : [String(result)]);
    for (const line of det) out('    ' + line);
  } catch (error) {
    const detail = String(error.stderr || error.message || error).trim();
    err(`[FAIL] ${s.name} (${Date.now() - t}ms)`);
    if (detail) err('  ' + detail.split('\n').join('\n  '));
    err(`\nChain halted at "${s.name}" after ${passed}/${steps.length} passing step(s).`);
    err('Fix this first, then re-run: node scripts/validate-chain.mjs');
    flushLog(1);
    process.exit(1);
  }
}
out('='.repeat(40));
out(`ALL ${passed}/${steps.length} checks passed in ${Date.now() - start}ms.`);
flushLog(0);

