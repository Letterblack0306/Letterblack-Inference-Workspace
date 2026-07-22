#!/usr/bin/env node

const fs = require('fs');
const path = require('path');

const root = path.resolve(__dirname, '..');
const sourceRoots = ['backend', 'web', 'scripts'];
const sourceExtensions = new Set(['.py', '.js']);
const declaredPattern = /^(?:export\s+)?([A-Z][A-Z0-9_]*)\s*=/;
const environmentPatterns = [
  /os\.environ\.get\(\s*["']([A-Z][A-Z0-9_]*)["']/g,
  /os\.getenv\(\s*["']([A-Z][A-Z0-9_]*)["']/g,
  /process\.env\.([A-Z][A-Z0-9_]*)/g,
];

function filesIn(directory) {
  return fs.readdirSync(directory, {withFileTypes: true}).flatMap(entry => {
    const fullPath = path.join(directory, entry.name);
    if (entry.isDirectory()) return entry.name === '__pycache__' ? [] : filesIn(fullPath);
    return sourceExtensions.has(path.extname(entry.name)) ? [fullPath] : [];
  });
}

function declaredVariables() {
  const example = fs.readFileSync(path.join(root, 'env.example'), 'utf8');
  return new Set(example.split(/\r?\n/).flatMap(line => {
    const match = line.match(declaredPattern);
    return match ? [match[1]] : [];
  }));
}

function referencedVariables() {
  const variables = new Set();
  for (const sourceRoot of sourceRoots) {
    const directory = path.join(root, sourceRoot);
    if (!fs.existsSync(directory)) continue;
    for (const file of filesIn(directory)) {
      const content = fs.readFileSync(file, 'utf8');
      for (const pattern of environmentPatterns) {
        pattern.lastIndex = 0;
        for (const match of content.matchAll(pattern)) variables.add(match[1]);
      }
    }
  }
  return variables;
}

const declared = declaredVariables();
const missing = [...referencedVariables()].filter(variable => !declared.has(variable)).sort();

if (missing.length) {
  console.error(`Environment contract failed. Missing from env.example: ${missing.join(', ')}`);
  process.exitCode = 1;
} else {
  console.log(`Environment contract passed: ${[...declared].sort().join(', ') || 'no variables declared'}.`);
}
