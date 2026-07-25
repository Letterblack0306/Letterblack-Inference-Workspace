const fs = require('fs');
const path = require('path');

const appPath = path.join(__dirname, '..', '..', 'web', 'js', 'app.js');
const htmlPath = path.join(__dirname, '..', '..', 'web', 'index.html');

const app = fs.readFileSync(appPath, 'utf8');
const html = fs.readFileSync(htmlPath, 'utf8');

let fail = false;

function check(label, ok, detail) {
  const status = ok ? 'PASS' : 'FAIL';
  if (!ok) fail = true;
  console.log(`${status} ${label}${detail ? ' - ' + detail : ''}`);
}

// Required symbols in app.js
const checks = [
  ['const $', app.includes("const $ = (selector, root = document) => root.querySelector(selector);")],
  ['const $$', app.includes("const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];")],
  ['const $$$', app.includes("const $$$ = $$;")],
  ['const PAGES', app.includes("const PAGES = [")],
  ['const PAGE_CONTENT', app.includes("const PAGE_CONTENT = {")],
  ['function renderNavigation', app.includes("function renderNavigation()")],
  ['function renderPage(pageId)', app.includes("function renderPage(pageId)")],
  ['function navigate(page)', app.includes("function navigate(page)")],
  ['function rebindNav', app.includes("function rebindNav()")],
  ['renderPage(page) in navigate', app.includes("renderPage(page);")],
  ['boot calls renderNavigation', app.includes("renderNavigation();")],
  ['boot calls rebindNav', app.includes("rebindNav();")],
];

for (const [label, ok] of checks) check(label, ok);

// Ensure nav items schema referenced
check("renderNavigation generates data-page", app.includes('data-page="${page.id}"'));
check("renderNavigation uses esc(page.label)", app.includes("esc(page.label)"));
check("navigate binds .nav-item[data-page]", app.includes('.nav-item[data-page]'));
check("navigate binds .page[data-page-view]", app.includes('.page[data-page-view]'));
check("rebindNav listens for click", app.includes('addEventListener'));

// Ensure HTML contains matching page sections
const htmlPages = ['chat','setup','models','runtime','machines','gateways','telemetry','profiles','extensions','logs','settings'];
let matchedSections = 0;
for (const id of htmlPages) {
  const has = html.includes('data-page-view="' + id + '"');
  if (has) matchedSections++;
  else console.log('FAIL HTML section missing: ' + id);
  check('html section ' + id, has);
}
check('All HTML page sections present', matchedSections === htmlPages.length, matchedSections + '/' + htmlPages.length);

// Check sidebar nav placeholders in HTML
const htmlNavIds = ['modelCount','machineCount','extensionCount'];
for (const id of htmlNavIds) {
  check('html nav id ' + id, html.includes('id="' + id + '"'));
}

console.log('\nRESULT: ' + (fail ? 'FAIL' : 'PASS'));
