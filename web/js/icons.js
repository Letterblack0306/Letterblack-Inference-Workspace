/* icons.js
 * Central SVG icon gallery. All icons live in web/assets/icons.svg as
 * <symbol id="icon-NAME"> and are referenced here by name. No emoji or
 * unicode glyphs - the UI renders crisp vector icons via this module.
 *
 * Add a new icon: add a <symbol id="icon-NAME"> to assets/icons.svg and
 * add "NAME" to ICONS below.
 */

const SPRITE_URL = 'assets/icons.svg';

// The gallery of available icon names (for discoverability / pickers).
export const ICONS = [
  // navigation
  'chat', 'setup', 'models', 'runtime', 'machines', 'gateways',
  'telemetry', 'profiles', 'extensions', 'logs', 'settings',
  // ui chrome
  'menu', 'close', 'check',
  // actions & status
  'plus', 'search', 'refresh', 'copy', 'folder', 'download',
  'trash', 'edit', 'stop', 'warning', 'info', 'cpu', 'external',
];

export function iconUrl(name) {
  return SPRITE_URL + '#icon-' + name;
}

export function hasIcon(name) {
  return ICONS.includes(name);
}

// Returns SVG markup for an icon. `cls` is appended to the class list.
export function icon(name, cls = '') {
  const classes = ('icon' + (cls ? ' ' + cls : '')).trim();
  const label = hasIcon(name) ? name : 'info';
  return '<svg class="' + classes + '" aria-hidden="true" focusable="false">' +
    '<use href="' + iconUrl(label) + '"></use></svg>';
}

export default icon;
