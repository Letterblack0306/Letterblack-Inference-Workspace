/* Map config "icon" glyph values to SVG gallery icon names. */
const fs = require('fs');
const path = require('path');
const CONFIG = 'C:/Proxy _server/ControlUI/web/config';

const MAP = new Map([
  [String.fromCodePoint(0x25EB), 'chat'],
  [String.fromCodePoint(0x2713), 'setup'],
  [String.fromCodePoint(0x25C7), 'models'],
  [String.fromCodePoint(0x25B6), 'runtime'],
  [String.fromCodePoint(0x2318), 'machines'],
  [String.fromCodePoint(0x2194), 'gateways'],
  [String.fromCodePoint(0x223F), 'telemetry'],
  [String.fromCodePoint(0x25A4), 'profiles'],
  [String.fromCodePoint(0x2B21), 'extensions'],
  [String.fromCodePoint(0x2261), 'logs'],
  [String.fromCodePoint(0x2699), 'settings'],
]);

function fix(list) {
  let changed = 0;
  for (const item of list || []) {
    if (item && typeof item === 'object' && MAP.has(item.icon)) {
      item.icon = MAP.get(item.icon);
      changed++;
    }
  }
  return changed;
}

let total = 0;
for (const sub of ['navigation', 'menu-ledger']) {
  const dir = path.join(CONFIG, sub);
  for (const f of fs.readdirSync(dir)) {
    if (!f.endsWith('.json')) continue;
    const p = path.join(dir, f);
    const data = JSON.parse(fs.readFileSync(p, 'utf8'));
    let n = 0;
    if (Array.isArray(data.items)) n += fix(data.items);
    if (Array.isArray(data.menus)) n += fix(data.menus);
    if (n) {
      fs.writeFileSync(p, JSON.stringify(data, null, 2) + '\n', 'utf8');
      total += n;
      console.log(sub + '/' + f + ': ' + n + ' icon(s)');
    }
  }
}
console.log('total icons mapped:', total);
