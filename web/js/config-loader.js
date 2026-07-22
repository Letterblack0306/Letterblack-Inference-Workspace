/* config-loader.js
 * Loads web/config/ui-config.json and exposes typed getters. The navigation
 * sections are split into per-section files (web/config/navigation/*.json) so
 * each section is easy to navigate and edit; this loader fetches and merges
 * them. Pure data access with no DOM side effects, so it is safe to import
 * from the single app.js module entrypoint.
 *
 * Extensible by design: add a new section file, reference it from
 * ui-config.json "navigation.sections". Do not hardcode values here.
 */

const DEFAULT_URL = '/config/ui-config.json';

async function fetchJSON(url, fallback = null) {
  try {
    const response = await fetch(url, { cache: 'no-cache' });
    if (!response.ok) throw new Error('HTTP ' + response.status);
    return await response.json();
  } catch (error) {
    console.warn('[config] Failed to load ' + url + ':', error?.message || error);
    return fallback;
  }
}

function baseOf(url) {
  return url.slice(0, url.lastIndexOf('/') + 1);
}

class ConfigLoader {
  constructor() {
    this.config = null;
    this.loaded = false;
  }

  async load(url = DEFAULT_URL) {
    const root = await fetchJSON(url, null);
    if (root) {
      root.navigation = await this.resolveNavigation(root.navigation, baseOf(url));
      this.config = root;
    } else {
      this.config = this.fallback();
    }
    this.loaded = true;
    return this.config;
  }

  // Sections may be file paths (strings) or inline objects; resolve both.
  async resolveNavigation(nav, base) {
    if (!nav) return { sections: [], items: [] };
    const refs = Array.isArray(nav.sections) ? nav.sections : [];
    const resolved = await Promise.all(refs.map(ref => (
      typeof ref === 'string' ? fetchJSON(base + ref, null) : Promise.resolve(ref)
    )));
    const sections = resolved.filter(s => s && Array.isArray(s.items));
    const items = sections.flatMap(sec => (sec.items || []).map(item => ({ ...item, section: item.section || sec.id })));
    return { sections, items };
  }

  fallback() {
    return {
      defaults: { pollInterval: 5000, modelSources: [] },
      navigation: { sections: [], items: [] },
    };
  }

  get(path, fallbackValue = undefined) {
    let node = this.config;
    for (const key of String(path).split('.')) {
      if (node == null || typeof node !== 'object' || !(key in node)) return fallbackValue;
      node = node[key];
    }
    return node === undefined ? fallbackValue : node;
  }

  getDefault(key, fallbackValue = undefined) {
    return this.get('defaults.' + key, fallbackValue);
  }

  getPollInterval(fallbackValue = 5000) {
    const value = Number(this.getDefault('pollInterval', fallbackValue));
    return Number.isFinite(value) && value > 0 ? value : fallbackValue;
  }

  getNavigationSections() {
    return this.get('navigation.sections', []);
  }

  getNavigationItems() {
    return this.get('navigation.items', []);
  }

  getNavigationItem(id) {
    return this.getNavigationItems().find(item => item.id === id) || null;
  }
}

export const configLoader = new ConfigLoader();
export default configLoader;
