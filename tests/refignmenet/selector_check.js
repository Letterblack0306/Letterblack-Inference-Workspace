const fs = require('fs');
const path = require('path');

const appPath = path.join(__dirname, '..', '..', 'web', 'js', 'app.js');
const htmlPath = path.join(__dirname, '..', '..', 'web', 'index.html');

const app = fs.readFileSync(appPath, 'utf8');
const html = fs.readFileSync(htmlPath, 'utf8');

// Extract only simple #id selectors, not compound selectors like #id .foo or #id [attr]
const ids = [...app.matchAll(/\$\('#([^']+)'\)/g)]
  .map(m => m[1])
  .filter(id => /^[A-Za-z_][\w-]*$/.test(id));

// IDs that are known to be created dynamically by render functions
const dynamicIds = new Set([
  'runtimeLaunchBtn',
  'runtimeStopBtn',
  'launchModelSelect',
  'launchProfileSelect',
  'preflightResult',
]);

const staticMissing = ids.filter(id => !html.includes('id="' + id + '"') && !dynamicIds.has(id));
const dynamicIdCount = ids.filter(id => dynamicIds.has(id)).length;

if (staticMissing.length) {
  console.log('FAIL missing static ids in index.html:');
  staticMissing.forEach(x => console.log(' - #' + x));
  process.exit(1);
} else {
  console.log('PASS index.html contains all static app.js IDs (' + ids.length + ' total, ' + dynamicIdCount + ' dynamic excluded)');
}
