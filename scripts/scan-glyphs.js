const fs = require('fs');
const file = process.argv[2];
const t = fs.readFileSync(file, 'utf8');
const re = /[☰×✓◫◇▶⌘↔∿▤⬡≡⚙⌁＋•›◦●▲●]|event-icon|empty-state|step-number|nav-glyph|class="icon/;
t.split('\n').forEach((l, i) => {
  if (re.test(l)) console.log((i + 1) + ': ' + l.trim().slice(0, 200));
});
