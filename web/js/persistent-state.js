/* persistent-state.js
 * UI state manager. Loads default UI state from web/config/persistent-state.json,
 * then merges anything saved in localStorage (letterblack_state) on top, so a
 * returning user's session is restored. Call save() to persist changes.
 * Pure state access - no DOM side effects.
 */

import { readJSON, writeJSON, storageKeys } from './persistent-config.js';

const DEFAULTS_URL = '/config/persistent-state.json';

function isPlainObject(value) {
  return value != null && typeof value === 'object' && !Array.isArray(value);
}

function deepMerge(base, override) {
  const out = { ...base };
  for (const key of Object.keys(override || {})) {
    const a = out[key];
    const b = override[key];
    out[key] = isPlainObject(a) && isPlainObject(b) ? deepMerge(a, b) : b;
  }
  return out;
}

class PersistentState {
  constructor() {
    this.state = this.fallbackDefaults();
    this.loaded = false;
  }

  fallbackDefaults() {
    return {
      activePage: 'chat',
      lastUsed: { model: null, profile: null, gateway: 'openai' },
      preferences: { theme: 'dark', pollInterval: 5000, streamResponses: true },
    };
  }

  async load(url = DEFAULTS_URL) {
    let defaults = this.fallbackDefaults();
    try {
      const response = await fetch(url, { cache: 'no-cache' });
      if (response.ok) defaults = deepMerge(defaults, await response.json());
    } catch (error) {
      console.warn('[state] Using built-in defaults:', error?.message || error);
    }
    const saved = readJSON(storageKeys.state, null);
    this.state = deepMerge(defaults, saved || {});
    this.loaded = true;
    return this.state;
  }

  get(path, fallbackValue = undefined) {
    let node = this.state;
    for (const key of String(path).split('.')) {
      if (node == null || typeof node !== 'object' || !(key in node)) return fallbackValue;
      node = node[key];
    }
    return node === undefined ? fallbackValue : node;
  }

  set(path, value) {
    const keys = String(path).split('.');
    let node = this.state;
    for (let i = 0; i < keys.length - 1; i++) {
      if (!isPlainObject(node[keys[i]])) node[keys[i]] = {};
      node = node[keys[i]];
    }
    node[keys[keys.length - 1]] = value;
    this.save();
  }

  save() {
    writeJSON(storageKeys.state, this.state);
  }
}

export const persistentState = new PersistentState();
export default persistentState;
