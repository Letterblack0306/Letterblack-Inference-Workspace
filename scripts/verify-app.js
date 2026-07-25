const fs = require('fs');
const t = fs.readFileSync('C:/Proxy _server/ControlUI/web/js/app.js', 'utf8');
const i = t.indexOf('function navigate');
console.log(t.slice(i, i + 160));
console.log('--- icon import present:', t.includes("import {icon} from './icons.js';"));
console.log('--- icon(check) used:', t.includes("icon('check')"));
console.log('--- navigate uses $$ :', t.slice(i, i + 200).includes('$$('));
