'use strict';
/* Dependency-free CSS top-level chunk inspector.
 * Walks a CSS file and splits it into top-level rules/at-rules,
 * correctly ignoring braces inside comments and strings.
 */
const fs = require('fs');
const path = require('path');

function tokenize(src) {
  const chunks = [];
  let i = 0, n = src.length, depth = 0, start = 0, buf = '';
  let state = 'normal'; // normal | blockComment | lineComment | string
  let quote = '';
  while (i < n) {
    const c = src[i];
    if (state === 'blockComment') {
      if (c === '*' && src[i + 1] === '/') { i += 2; state = 'normal'; continue; }
      i++; continue;
    }
    if (state === 'lineComment') {
      if (c === '\n') { state = 'normal'; }
      i++; continue;
    }
    if (state === 'string') {
      if (c === '\\') { i += 2; continue; }
      if (c === quote) { state = 'normal'; }
      i++; continue;
    }
    if (c === '/' && src[i + 1] === '*') { state = 'blockComment'; i += 2; continue; }
    if (c === '/' && src[i + 1] === '/') { state = 'lineComment'; i += 2; continue; }
    if (c === '"' || c === "'") { state = 'string'; quote = c; i++; continue; }
    if (c === '{') { depth++; }
    else if (c === '}') {
      depth--;
      if (depth === 0) {
        buf += src.slice(start, i + 1);
        chunks.push(buf);
        buf = '';
        start = i + 1;
        i++;
        continue;
      }
    } else if (c === ';' && depth === 0) {
      // top-level statement without a block (e.g. @import, @charset)
      buf += src.slice(start, i + 1);
      chunks.push(buf);
      buf = '';
      start = i + 1;
      i++;
      continue;
    }
    i++;
  }
  if (start < n) {
    const tail = src.slice(start).trim();
    if (tail) chunks.push(tail);
  }
  return chunks;
}

function summary(chunk) {
  const head = chunk.trim();
  const selEnd = head.indexOf('{');
  let pre = selEnd === -1 ? head : head.slice(0, selEnd).trim();
  if (pre.length > 120) pre = pre.slice(0, 120) + '…';
  return pre.replace(/\s+/g, ' ');
}

const files = process.argv.slice(2);
for (const f of files) {
  const src = fs.readFileSync(f, 'utf8');
  const chunks = tokenize(src);
  console.log('\n===== ' + path.basename(f) + ' : ' + chunks.length + ' chunks =====');
  chunks.forEach((c, idx) => {
    console.log(String(idx).padStart(3, ' ') + ' | ' + summary(c));
  });
}
