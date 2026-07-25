/* persistent-config.js
 * Safe, namespaced localStorage manager. All keys are prefixed with
 * "letterblack_" so the app never collides with other storage users.
 * Every access is wrapped in try/catch so a disabled or full storage
 * never breaks the UI. Pure data access - no DOM side effects.
 */

const PREFIX = 'letterblack_';

export const storageKeys = {
  config: 'config',
  state: 'state',
  workspace: 'workspace',
};

function fullKey(name) {
  return PREFIX + name;
}

function storageAvailable() {
  try {
    return typeof localStorage !== 'undefined' && localStorage !== null;
  } catch {
    return false;
  }
}

export function readJSON(name, fallback = null) {
  if (!storageAvailable()) return fallback;
  try {
    const raw = localStorage.getItem(fullKey(name));
    return raw == null ? fallback : JSON.parse(raw);
  } catch {
    return fallback;
  }
}

export function writeJSON(name, value) {
  if (!storageAvailable()) return false;
  try {
    localStorage.setItem(fullKey(name), JSON.stringify(value));
    return true;
  } catch {
    return false;
  }
}

export function removeKey(name) {
  if (!storageAvailable()) return false;
  try {
    localStorage.removeItem(fullKey(name));
    return true;
  } catch {
    return false;
  }
}
