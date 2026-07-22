/* menu-ledger.js
 * Menu registry + agent guidance. Loads web/config/menu-ledger.json, which
 * references per-section menu files (web/config/menu-ledger/*.json) and
 * per-workflow files (web/config/workflows/*.json); this loader fetches and
 * merges them. State evaluation is injected by the caller as checkFn(key) ->
 * boolean, so this module never evaluates arbitrary code. No DOM side effects.
 */

const LEDGER_URL = '/config/menu-ledger.json';

async function fetchJSON(url, fallback = null) {
  try {
    const response = await fetch(url, { cache: 'no-cache' });
    if (!response.ok) throw new Error('HTTP ' + response.status);
    return await response.json();
  } catch (error) {
    console.warn('[menu-ledger] Failed to load ' + url + ':', error?.message || error);
    return fallback;
  }
}

function baseOf(url) {
  return url.slice(0, url.lastIndexOf('/') + 1);
}

class MenuLedger {
  constructor() {
    this.ledger = { menus: [], workflows: [], stateRequirements: {} };
    this.menuMap = new Map();
    this.workflowMap = new Map();
    this.loaded = false;
  }

  async load(url = LEDGER_URL) {
    const root = await fetchJSON(url, null);
    const base = baseOf(url);
    if (root) {
      root.menus = await this.resolveMenus(root.menus, base);
      root.workflows = await this.resolveWorkflows(root.workflows, base);
      this.ledger = root;
    } else {
      this.ledger = { menus: [], workflows: [], stateRequirements: {} };
    }
    this.buildMaps();
    this.loaded = true;
    return this.ledger;
  }

  // Menus may be section file paths or inline objects/arrays; resolve all.
  async resolveMenus(refs, base) {
    if (!Array.isArray(refs)) return [];
    const resolved = await Promise.all(refs.map(ref => (
      typeof ref === 'string' ? fetchJSON(base + ref, null) : Promise.resolve(ref)
    )));
    const out = [];
    for (const part of resolved.filter(Boolean)) {
      if (Array.isArray(part)) out.push(...part);
      else if (Array.isArray(part.menus)) out.push(...part.menus);
      else if (part.id) out.push(part);
    }
    return out;
  }

  async resolveWorkflows(refs, base) {
    if (!Array.isArray(refs)) return [];
    const resolved = await Promise.all(refs.map(ref => (
      typeof ref === 'string' ? fetchJSON(base + ref, null) : Promise.resolve(ref)
    )));
    return resolved.filter(wf => wf && wf.id);
  }

  buildMaps() {
    this.menuMap = new Map((this.ledger.menus || []).map(menu => [menu.id, menu]));
    this.workflowMap = new Map((this.ledger.workflows || []).map(wf => [wf.id, wf]));
  }

  getMenu(id) { return this.menuMap.get(id) || null; }
  getAllMenus() { return [...this.menuMap.values()]; }
  getMenusBySection(section) { return this.getAllMenus().filter(m => m.section === section); }
  getWorkflow(id) { return this.workflowMap.get(id) || null; }
  getAllWorkflows() { return [...this.workflowMap.values()]; }

  getGuidance(id) { return this.getMenu(id)?.guidance || null; }

  requirementsFor(id) {
    const menu = this.getMenu(id);
    return {
      requires: menu?.state?.requires || [],
      recommends: menu?.state?.recommends || [],
    };
  }

  getStateGuidance(key) {
    return this.ledger.stateRequirements?.[key]?.guidance || null;
  }

  menuStatus(id, checkFn) {
    const { requires, recommends } = this.requirementsFor(id);
    const reqMet = requires.every(key => safeCheck(checkFn, key));
    const recMet = recommends.every(key => safeCheck(checkFn, key));
    if (reqMet && recMet) return 'ready';
    if (reqMet) return 'partial';
    return 'blocked';
  }

  unmetGuidance(id, checkFn) {
    const { requires, recommends } = this.requirementsFor(id);
    return [...requires, ...recommends]
      .filter(key => !safeCheck(checkFn, key))
      .map(key => ({ requirement: key, guidance: this.getStateGuidance(key) }))
      .filter(item => item.guidance);
  }

  workflowStatus(id, checkFn) {
    const wf = this.getWorkflow(id);
    if (!wf) return null;
    return {
      id: wf.id,
      label: wf.label,
      description: wf.description,
      steps: (wf.steps || []).map((step, i) => ({
        step: i + 1,
        page: step.page,
        action: step.action,
        label: step.label,
        guidance: step.guidance,
        status: this.menuStatus(step.page, checkFn),
      })),
    };
  }
}

function safeCheck(checkFn, key) {
  try {
    return typeof checkFn === 'function' ? Boolean(checkFn(key)) : false;
  } catch {
    return false;
  }
}

export const menuLedger = new MenuLedger();
export default menuLedger;
