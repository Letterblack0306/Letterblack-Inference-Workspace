// Smoke test: verify the config loaders merge the split per-section files.
// Stubs fetch to read from disk, then exercises config-loader + menu-ledger.
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const CONFIG_DIR = path.join(ROOT, 'web', 'config');

globalThis.fetch = async (url) => {
  const rel = String(url).replace(/^\/config\//, '');
  const file = path.join(CONFIG_DIR, rel);
  const text = fs.readFileSync(file, 'utf8');
  return { ok: true, status: 200, json: async () => JSON.parse(text) };
};

const { configLoader } = await import('../web/js/config-loader.js');
const { menuLedger } = await import('../web/js/menu-ledger.js');

await configLoader.load();
await menuLedger.load();

const sections = configLoader.getNavigationSections();
const items = configLoader.getNavigationItems();
const menus = menuLedger.getAllMenus();
const workflows = menuLedger.getAllWorkflows();

console.log('navigation sections:', sections.map(s => s.id).join(', '));
console.log('navigation items:', items.length, '->', items.map(i => i.id).join(', '));
console.log('ledger menus:', menus.length, '->', menus.map(m => m.id).join(', '));
console.log('ledger workflows:', workflows.length, '->', workflows.map(w => w.id).join(', '));

// sanity checks
const assert = (cond, msg) => { if (!cond) { console.error('FAIL:', msg); process.exitCode = 1; } };
assert(sections.length === 5, 'expected 5 nav sections');
assert(items.length === 11, 'expected 11 nav items, got ' + items.length);
assert(items.every(i => i.section), 'every nav item should carry its section');
assert(items.find(i => i.id === 'models')?.badgeId === 'modelCount', 'models badgeId preserved');
assert(menus.length === 11, 'expected 11 ledger menus, got ' + menus.length);
assert(workflows.length === 2, 'expected 2 workflows, got ' + workflows.length);
assert(menuLedger.getGuidance('chat')?.length > 0, 'chat guidance present');
assert(menuLedger.workflowStatus('first-time-setup', () => true)?.steps.length === 6, 'workflow steps resolved');

console.log(process.exitCode ? 'SMOKE FAIL' : 'SMOKE PASS');
