const BASE = '/api/v1';

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
const esc = value => String(value ?? '').replace(/[&<>'"]/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[char]));

const extensionState = {
  extensions: [],
  actions: [],
  endpoints: [],
  loading: false,
};

function toast(title, message = '', level = 'neutral') {
  const region = $('#toastRegion');
  if (!region) return;
  const item = document.createElement('div');
  item.className = `toast ${level}`;
  item.innerHTML = `<strong>${esc(title)}</strong><span>${esc(message)}</span>`;
  region.append(item);
  setTimeout(() => item.remove(), 4500);
}

async function request(path, options = {}) {
  const response = await fetch(`${BASE}${path}`, {
    ...options,
    headers: {'Content-Type': 'application/json', ...(options.headers || {})},
  });
  const payload = await response.json().catch(() => null);
  if (!response.ok || !payload || payload.ok === false) {
    const error = payload?.error || {};
    throw new Error(`${error.code || `HTTP_${response.status}`}: ${error.message || response.statusText}`);
  }
  return payload.data;
}

function normalizeList(value, keys) {
  if (Array.isArray(value)) return value;
  for (const key of keys) {
    if (Array.isArray(value?.[key])) return value[key];
  }
  return [];
}

function badge(text, level = 'neutral') {
  return `<span class="status-badge ${level}">${esc(text)}</span>`;
}

function permissionList(items = []) {
  return items.length
    ? `<div class="permission-list">${items.map(item => `<code>${esc(item)}</code>`).join('')}</div>`
    : '<span class="muted">No permissions declared</span>';
}

function renderSummary() {
  $('#extensionCount').textContent = extensionState.extensions.length;
  $('#extensionSummary').innerHTML = [
    ['Extensions', extensionState.extensions.length],
    ['Enabled', extensionState.extensions.filter(item => item.enabled !== false).length],
    ['Actions', extensionState.actions.length],
    ['Endpoints', extensionState.endpoints.length],
  ].map(([label, value]) => `<article class="content-card extension-stat"><span>${esc(label)}</span><strong>${esc(value)}</strong></article>`).join('');
}

function renderExtensions() {
  const root = $('#extensionList');
  if (!extensionState.extensions.length) {
    root.innerHTML = '<div class="empty-state"><h3>No extensions installed</h3><p>Import a declarative JSON manifest. Executable code is not accepted.</p></div>';
    return;
  }
  root.innerHTML = extensionState.extensions.map(item => {
    const assets = [
      `${item.widgets?.length || 0} widgets`,
      `${item.actions?.length || 0} actions`,
      `${item.endpoints?.length || 0} endpoints`,
    ].join(' · ');
    return `<article class="registry-item">
      <div class="registry-main">
        <div class="registry-title"><div><h3>${esc(item.name || item.id)}</h3><code>${esc(item.id)} · v${esc(item.version || 'unknown')}</code></div>${badge(item.enabled === false ? 'Disabled' : 'Enabled', item.enabled === false ? 'neutral' : 'good')}</div>
        <p>${esc(item.description || 'No description')}</p>
        ${permissionList(item.permissions || [])}
        <small>${esc(assets)}</small>
      </div>
      <div class="registry-actions">
        <button class="button compact secondary extension-toggle" data-id="${esc(item.id)}" type="button">${item.enabled === false ? 'Enable' : 'Disable'}</button>
        <button class="button compact danger-soft extension-delete" data-id="${esc(item.id)}" type="button">Uninstall</button>
      </div>
    </article>`;
  }).join('');

  $$('.extension-toggle', root).forEach(button => button.addEventListener('click', () => toggleExtension(button.dataset.id)));
  $$('.extension-delete', root).forEach(button => button.addEventListener('click', () => deleteExtension(button.dataset.id)));
}

function renderActions() {
  const root = $('#actionList');
  if (!extensionState.actions.length) {
    root.innerHTML = '<div class="empty-state"><p>No custom actions registered.</p></div>';
    return;
  }
  root.innerHTML = extensionState.actions.map(item => `<article class="registry-item compact-item">
    <div class="registry-main">
      <div class="registry-title"><div><h3>${esc(item.name || item.id)}</h3><code>${esc(item.type || 'unknown')} · ${esc(item.id)}</code></div>${badge(item.enabled === false ? 'Disabled' : 'Enabled', item.enabled === false ? 'neutral' : 'good')}</div>
      <p>${esc(item.description || 'No description')}</p>
      ${permissionList(item.permissions || [])}
    </div>
    <div class="registry-actions">
      <button class="button compact primary action-run" data-id="${esc(item.id)}" type="button" ${item.enabled === false ? 'disabled' : ''}>Run</button>
      <button class="button compact danger-soft action-delete" data-id="${esc(item.id)}" type="button">Delete</button>
    </div>
  </article>`).join('');

  $$('.action-run', root).forEach(button => button.addEventListener('click', () => runAction(button.dataset.id)));
  $$('.action-delete', root).forEach(button => button.addEventListener('click', () => deleteAction(button.dataset.id)));
}

function renderEndpoints() {
  const root = $('#endpointList');
  if (!extensionState.endpoints.length) {
    root.innerHTML = '<div class="empty-state"><p>No custom endpoints registered.</p></div>';
    return;
  }
  root.innerHTML = extensionState.endpoints.map(item => `<article class="registry-item compact-item">
    <div class="registry-main">
      <div class="registry-title"><div><h3>${esc(item.name || item.id)}</h3><code>${esc(item.baseUrl || 'No URL')}</code></div>${badge(item.enabled === false ? 'Disabled' : 'Enabled', item.enabled === false ? 'neutral' : 'good')}</div>
      <small>${esc(item.id)}${item.healthCheck?.path ? ` · health ${esc(item.healthCheck.path)}` : ''}</small>
    </div>
    <div class="registry-actions">
      <button class="button compact secondary endpoint-test" data-id="${esc(item.id)}" type="button">Test</button>
      <button class="button compact danger-soft endpoint-delete" data-id="${esc(item.id)}" type="button">Delete</button>
    </div>
  </article>`).join('');

  $$('.endpoint-test', root).forEach(button => button.addEventListener('click', () => testEndpoint(button.dataset.id)));
  $$('.endpoint-delete', root).forEach(button => button.addEventListener('click', () => deleteEndpoint(button.dataset.id)));
}

function render() {
  renderSummary();
  renderExtensions();
  renderActions();
  renderEndpoints();
}

async function refreshExtensions() {
  if (extensionState.loading) return;
  extensionState.loading = true;
  try {
    const results = await Promise.allSettled([
      request('/extensions'),
      request('/actions'),
      request('/endpoints'),
    ]);
    if (results[0].status === 'fulfilled') extensionState.extensions = normalizeList(results[0].value, ['extensions', 'items']);
    if (results[1].status === 'fulfilled') extensionState.actions = normalizeList(results[1].value, ['actions', 'items']);
    if (results[2].status === 'fulfilled') extensionState.endpoints = normalizeList(results[2].value, ['endpoints', 'items']);
    results.forEach((result, index) => {
      if (result.status === 'rejected') console.warn(['extensions', 'actions', 'endpoints'][index], result.reason);
    });
    render();
  } finally {
    extensionState.loading = false;
  }
}

async function importExtension(event) {
  event.preventDefault();
  let manifest;
  try {
    manifest = JSON.parse($('#extensionManifestJson').value);
  } catch (error) {
    return toast('Invalid JSON', error.message, 'warning');
  }
  try {
    await request('/extensions', {method:'POST', body:JSON.stringify(manifest)});
    $('#extensionImportDialog').close();
    event.currentTarget.reset();
    toast('Extension installed', manifest.name || manifest.id, 'good');
    await refreshExtensions();
  } catch (error) {
    toast('Extension import failed', error.message, 'warning');
  }
}

async function toggleExtension(id) {
  const current = extensionState.extensions.find(item => item.id === id);
  if (!current) return;
  try {
    await request(`/extensions/${encodeURIComponent(id)}`, {
      method:'PUT',
      body:JSON.stringify({...current, enabled:current.enabled === false}),
    });
    await refreshExtensions();
  } catch (error) {
    toast('Extension update failed', error.message, 'warning');
  }
}

async function deleteExtension(id) {
  if (!confirm(`Uninstall extension ${id}? Registered assets from this extension may be removed.`)) return;
  try {
    await request(`/extensions/${encodeURIComponent(id)}`, {method:'DELETE'});
    toast('Extension uninstalled', id, 'good');
    await refreshExtensions();
  } catch (error) {
    toast('Extension uninstall failed', error.message, 'warning');
  }
}

async function createAction(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const data = Object.fromEntries(new FormData(form));
  let config;
  try {
    config = JSON.parse(data.config || '{}');
  } catch (error) {
    return toast('Invalid config JSON', error.message, 'warning');
  }
  const payload = {
    id:data.id,
    name:data.name,
    description:data.description || '',
    type:data.type,
    confirmation:data.confirmation,
    permissions:String(data.permissions || '').split(',').map(item => item.trim()).filter(Boolean),
    config,
    enabled:form.elements.enabled.checked,
  };
  try {
    await request('/actions', {method:'POST', body:JSON.stringify(payload)});
    $('#actionDialog').close();
    form.reset();
    form.elements.config.value = '{}';
    form.elements.enabled.checked = true;
    toast('Action created', payload.name, 'good');
    await refreshExtensions();
  } catch (error) {
    toast('Action creation failed', error.message, 'warning');
  }
}

async function runAction(id) {
  const action = extensionState.actions.find(item => item.id === id);
  if (!action) return;
  if (action.confirmation === 'always' && !confirm(`Run action ${action.name || id}?`)) return;
  try {
    const result = await request(`/actions/${encodeURIComponent(id)}/execute`, {method:'POST', body:'{}'});
    toast('Action started', result?.id || result?.jobId || id, 'good');
  } catch (error) {
    toast('Action execution failed', error.message, 'warning');
  }
}

async function deleteAction(id) {
  if (!confirm(`Delete action ${id}?`)) return;
  try {
    await request(`/actions/${encodeURIComponent(id)}`, {method:'DELETE'});
    await refreshExtensions();
  } catch (error) {
    toast('Action deletion failed', error.message, 'warning');
  }
}

async function createEndpoint(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const data = Object.fromEntries(new FormData(form));
  const payload = {
    id:data.id,
    name:data.name,
    baseUrl:data.baseUrl,
    enabled:form.elements.enabled.checked,
    ...(data.healthPath ? {healthCheck:{path:data.healthPath, method:'GET'}} : {}),
  };
  try {
    await request('/endpoints', {method:'POST', body:JSON.stringify(payload)});
    $('#endpointDialog').close();
    form.reset();
    form.elements.enabled.checked = true;
    toast('Endpoint registered', payload.name, 'good');
    await refreshExtensions();
  } catch (error) {
    toast('Endpoint creation failed', error.message, 'warning');
  }
}

async function testEndpoint(id) {
  try {
    const result = await request(`/endpoints/${encodeURIComponent(id)}/test`, {method:'POST', body:'{}'});
    const ok = result?.reachable ?? result?.ok ?? result?.healthy;
    toast(ok === false ? 'Endpoint test failed' : 'Endpoint reachable', result?.status ? String(result.status) : id, ok === false ? 'warning' : 'good');
    await refreshExtensions();
  } catch (error) {
    toast('Endpoint test failed', error.message, 'warning');
  }
}

async function deleteEndpoint(id) {
  if (!confirm(`Delete endpoint ${id}? Actions referencing it may stop working.`)) return;
  try {
    await request(`/endpoints/${encodeURIComponent(id)}`, {method:'DELETE'});
    await refreshExtensions();
  } catch (error) {
    toast('Endpoint deletion failed', error.message, 'warning');
  }
}

function wireExtensions() {
  $('#importExtensionBtn')?.addEventListener('click', () => $('#extensionImportDialog').showModal());
  $('#createActionBtn')?.addEventListener('click', () => $('#actionDialog').showModal());
  $('#createEndpointBtn')?.addEventListener('click', () => $('#endpointDialog').showModal());
  $('#extensionImportForm')?.addEventListener('submit', importExtension);
  $('#actionForm')?.addEventListener('submit', createAction);
  $('#endpointForm')?.addEventListener('submit', createEndpoint);
  $$('.extension-dialog-close').forEach(button => button.addEventListener('click', () => button.closest('dialog').close()));
  document.querySelector('[data-page="extensions"]')?.addEventListener('click', () => refreshExtensions().catch(error => toast('Extension refresh failed', error.message, 'warning')));
}

function bootExtensions() {
  wireExtensions();
  refreshExtensions().catch(error => toast('Extensions unavailable', error.message, 'warning'));
  setInterval(() => {
    if (document.querySelector('[data-page-view="extensions"]')?.classList.contains('active')) {
      refreshExtensions().catch(error => console.warn('Extension refresh failed', error));
    }
  }, 10000);
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', bootExtensions, {once:true});
} else {
  bootExtensions();
}
