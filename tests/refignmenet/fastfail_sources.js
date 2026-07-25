const fs = require('fs');
const path = require('path');

const files = {
  app: path.join(__dirname, '..', '..', 'web', 'js', 'app.js'),
  api: path.join(__dirname, '..', '..', 'web', 'js', 'api.js'),
  extensions: path.join(__dirname, '..', '..', 'web', 'js', 'extensions.js'),
  menuLedger: path.join(__dirname, '..', '..', 'web', 'js', 'menu-ledger.js'),
  persistentState: path.join(__dirname, '..', '..', 'web', 'js', 'persistent-state.js'),
  configLoader: path.join(__dirname, '..', '..', 'web', 'js', 'config-loader.js'),
  index: path.join(__dirname, '..', '..', 'web', 'index.html'),
  cssApp: path.join(__dirname, '..', '..', 'web', 'css', 'app.css'),
  cssPages: path.join(__dirname, '..', '..', 'web', 'css', 'pages', 'page.css'),
  cssExtensions: path.join(__dirname, '..', '..', 'web', 'css', 'pages', 'extensions-surfaces.css'),
};

const src = {};
for (const [k, v] of Object.entries(files)) {
  try { src[k] = fs.readFileSync(v, 'utf8').split(/\r?\n/); }
  catch (e) { src[k] = []; }
}

let fail = false;
function check(file, label, ok, detail) {
  const status = ok ? 'PASS' : 'FAIL';
  if (!ok) fail = true;
  console.log(`${status} ${file}: ${label}${detail ? ' - ' + detail : ''}`);
}

function is(chunk, needle) { return chunk.join('\n').includes(needle); }

check('app', 'const PAGES', is(src.app, 'const PAGES = ['));
check('app', 'const PAGE_CONTENT', is(src.app, 'const PAGE_CONTENT = {'));
check('app', 'renderNavigation', is(src.app, 'function renderNavigation()'));
check('app', 'renderPage', is(src.app, 'function renderPage(pageId)'));
check('app', 'navigate', is(src.app, 'function navigate(page)'));
check('app', 'rebindNav', is(src.app, 'function rebindNav()'));
check('app', 'boot renderNavigation', is(src.app, 'renderNavigation();'));
check('app', 'boot rebindNav', is(src.app, 'rebindNav();'));
check('app', 'boot navigate', is(src.app, 'navigate(validStartPage());'));
check('app', 'navigate renderPage', is(src.app, 'renderPage(page);'));
check('app', 'validStartPage', is(src.app, 'function validStartPage()'));
check('app', 'esc helper', is(src.app, 'const esc ='));
check('app', 'state object', is(src.app, 'const state = {'));
check('app', 'settingsValue helper', is(src.app, 'function settingsValue()'));
check('app', 'chat panel markup present in html', is(src.index, 'id="chatMessages"'));
check('app', 'request inspector markup present in html', is(src.index, 'id="chatStatus"') && is(src.index, 'id="chatRaw"'));
check('app', 'settingsRoot markup present in html', is(src.index, 'id="settingsRoot"'));
check('app', 'setupGrid markup present in html', is(src.index, 'id="setupGrid"'));
check('app', 'modelsTableBody markup present in html', is(src.index, 'id="modelsTableBody"'));
check('app', 'runtimePanel markup present in html', is(src.index, 'id="runtimePanel"'));
check('app', 'machineGrid markup present in html', is(src.index, 'id="machineGrid"'));
check('app', 'gatewayGrid markup present in html', is(src.index, 'id="gatewayGrid"'));
check('app', 'profileGrid markup present in html', is(src.index, 'id="profileGrid"'));
check('app', 'logOutput and filter inputs in html', is(src.index, 'id="logOutput"') && is(src.index, 'id="logLevelFilter"') && is(src.index, 'id="logSearch"'));
check('app', 'toast region present', is(src.index, 'id="toastRegion"'));
check('app', 'jobs drawer present', is(src.index, 'id="jobDrawer"'));
check('app', 'boot startup failure notify', is(src.app, 'UI startup failed'));
