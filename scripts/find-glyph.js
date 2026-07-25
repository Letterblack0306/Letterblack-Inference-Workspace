const fs = require('fs');
const file = process.argv[2];
const target = process.argv[3] || '＋';
const t = fs.readFileSync(file, 'utf8');
t.split('\n').forEach((l, i) => {
  if (l.includes(target)) console.log((i + 1) + ': ' + l.trim().slice(0, 200));
});
console.log('--- icon-close refs:', (t.match(/#icon-close/g) || []).length);
console.log('--- nav svg icons:', (t.match(/nav-glyph icon/g) || []).length);
