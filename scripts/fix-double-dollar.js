const fs = require('fs');
const p = 'C:/Proxy _server/ControlUI/web/js/app.js';
let t = fs.readFileSync(p, 'utf8');

// Fix wireNavigationHandlers: replace $('.nav-item[data-page]') with $$('.nav-item[data-page]')
const target = "$('.nav-item[data-page]')";
const replacement = "$" + target;  // prepend one $ to make $$
t = t.split(target).join(replacement);

fs.writeFileSync(p, t, 'utf8');
console.log('fixed');
// verify
const c = fs.readFileSync(p, 'utf8');
const i = c.indexOf('wireNavigationHandlers');
console.log(c.slice(i, i + 120));
