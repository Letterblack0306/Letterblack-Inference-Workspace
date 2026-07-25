const fs = require('fs');
const svg = fs.readFileSync('C:/Proxy _server/ControlUI/web/assets/icons.svg', 'utf8');
const html = fs.readFileSync('C:/Proxy _server/ControlUI/web/index.html', 'utf8');
const appjs = fs.readFileSync('C:/Proxy _server/ControlUI/web/js/app.js', 'utf8');

const ids = new Set([...svg.matchAll(/symbol id="(icon-[a-z0-9-]+)"/g)].map(m => m[1]));
console.log('sprite symbols:', ids.size);

// well-formedness sanity: balanced symbol/svg tags
const openSym = (svg.match(/<symbol/g) || []).length;
const closeSym = (svg.match(/<\/symbol>/g) || []).length;
console.log('symbol open/close:', openSym, '/', closeSym, openSym === closeSym ? 'OK' : 'MISMATCH');

// collect refs from html + app.js (icon('name') calls)
const refs = new Set([...html.matchAll(/#(icon-[a-z0-9-]+)/g)].map(m => m[1]));
for (const m of appjs.matchAll(/icon\('([a-z0-9-]+)'/g)) refs.add('icon-' + m[1]);
const missing = [...refs].filter(r => !ids.has(r));
console.log('unique icon refs:', refs.size);
console.log(missing.length ? ('MISSING SYMBOLS: ' + missing.join(', ')) : 'all referenced icons exist in the sprite');
