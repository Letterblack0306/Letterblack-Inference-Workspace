const BASE = '/api/v1';

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
const esc = value => String(value ?? '').replace(/[&<>'"]/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[char]));

const state = {extensions:[], actions:[], endpoints:[], loading:false};

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
    headers:{'Content-Type':'application/json', ...(options.headers || {})},
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
  for (const key of keys) if (Array.isArray(value?.[key])) return value[key];
  return [];
}

function badge(text, level = 'neutral') {
  return `<span class="status-badge ${level}">${esc(text)}</span>`;
}

function permissions(items = []) {
  return items.length
    ? `<div class="permission-list">${items.map(item => `<code>${esc(item)}</code>`).join('')}</div>`
    : '<span class="muted">No permissions declared</span>';
}

function renderSummary() {
  $('#extensionCount').textContent = state.extensions.length;
  $('#extensionSummary').innerHTML = [
    ['Extensions', state.extensions.length],
    ['Enabled', state.extensions.filter(item => item.enabled !== false).length],
    ['Actions', state.actions.length],
    ['Endpoints', state.endpoints.length],
  ].map(([label, value]) => `<article class="content-card extension-stat"><span>${esc(label)}</span><strong>${esc(value)}</strong></article>`).join('');
}

function renderExtensions() {
  const root = $('#extensionList');
  if (!state.extensions.length) {
    root.innerHTML = '<div class="empty-state"><h3>No extensions installed</h3><p>Import a declarative JSON manifest. Executable code is not accepted.</p></div>';
    return;
  }
  root.innerHTML = state.extensions.map(item => {
    const assets = `${item.widgets?.length || 0} widgets · ${item.actions?.length || 0} actions · ${item.endpoints?.length || 0} endpoints`;
    return `<article class="registry-item"><div class="registry-main"><div class="registry-title"><div><h3>${esc(item.name || item.id)}</h3><code>${esc(item.id)} · v${esc(item.version || 'unknown')}</code></div>${badge(item.enabled === false ? 'Disabled' : 'Enabled', item.enabled === false ? 'neutral' : 'good')}</div><p>${esc(item.description || 'No description')}</p>${permissions(item.permissions || [])}<small>${esc(assets)}</small></div><div class="registry-actions"><button class="button compact secondary extension-toggle" data-id="${esc(item.id)}" type="button">${item.enabled === false ? 'Enable' : 'Disable'}</button><button class="button compact danger-soft extension-delete" data-id="${esc(item.id)}" type="button">Uninstall</button></div></article>`;
  }).join('');
  $$('.extension-toggle', root).forEach(button => button.addEventListener('click', () => toggleExtension(button.dataset.id)));
  $$('.extension-delete', root).forEach(button => button.addEventListener('click', () => deleteExtension(button.dataset.id)));
}

function renderActions() {
  const root = $('#actionList');
  if (!state.actions.length) {
    root.innerHTML = '<div class="empty-state"><p>No custom actions registered.</p></div>';
    return;
  }
  root.innerHTML = state.actions.map(item => `<article class="registry-item compact-item"><div class="registry-main"><div class="registry-title"><div><h3>${esc(item.name || item.id)}</h3><code>${esc(item.type || 'unknown')} · ${esc(item.id)}</code></div>${badge(item.enabled === false ? 'Disabled' : 'Enabled', item.enabled === false ? 'neutral' : 'good')}</div><p>${esc(item.description || 'No description')}</p>${permissions(item.permissions || [])}</div><div class="registry-actions"><button class="button compact primary action-run" data-id="${esc(item.id)}" type="button" ${item.enabled === false ? 'disabled' : ''}>Run</button><button class="button compact secondary action-edit" data-id="${esc(item.id)}" type="button">Edit</button><button class="button compact secondary action-toggle" data-id="${esc(item.id)}" type="button">${item.enabled === false ? 'Enable' : 'Disable'}</button><button class="button compact danger-soft action-delete" data-id="${esc(item.id)}" type="button">Delete</button></div></article>`).join('');
  $$('.action-run', root).forEach(button => button.addEventListener('click', () => runAction(button.dataset.id)));
  $$('.action-edit', root).forEach(button => button.addEventListener('click', () => openActionDialog(button.dataset.id)));
  $$('.action-toggle', root).forEach(button => button.addEventListener('click', () => toggleAction(button.dataset.id)));
  $$('.action-delete', root).forEach(button => button.addEventListener('click', () => deleteAction(button.dataset.id)));
}

function renderEndpoints() {
  const root = $('#endpointList');
  if (!state.endpoints.length) {
    root.innerHTML = '<div class="empty-state"><p>No custom endpoints registered.</p></div>';
    return;
  }
  root.innerHTML = state.endpoints.map(item => `<article class="registry-item compact-item"><div class="registry-main"><div class="registry-title"><div><h3>${esc(item.name || item.id)}</h3><code>${esc(item.baseUrl || 'No URL')}</code></div>${badge(item.enabled === false ? 'Disabled' : 'Enabled', item.enabled === false ? 'neutral' : 'good')}</div><small>${esc(item.id)}${item.healthCheck?.path ? ` · health ${esc(item.healthCheck.path)}` : ''}</small></div><div class="registry-actions"><button class="button compact secondary endpoint-test" data-id="${esc(item.id)}" type="button" ${item.enabled === false ? 'disabled' : ''}>Test</button><button class="button compact secondary endpoint-edit" data-id="${esc(item.id)}" type="button">Edit</button><button class="button compact secondary endpoint-toggle" data-id="${esc(item.id)}" type="button">${item.enabled === false ? 'Enable' : 'Disable'}</button><button class="button compact danger-soft endpoint-delete" data-id="${esc(item.id)}" type="button">Delete</button></div></article>`).join('');
  $$('.endpoint-test', root).forEach(button => button.addEventListener('click', () => testEndpoint(button.dataset.id)));
  $$('.endpoint-edit', root).forEach(button => button.addEventListener('click', () => openEndpointDialog(button.dataset.id)));
  $$('.endpoint-toggle', root).forEach(button => button.addEventListener('click', () => toggleEndpoint(button.dataset.id)));
  $$('.endpoint-delete', root).forEach(button => button.addEventListener('click', () => deleteEndpoint(button.dataset.id)));
}

function render() {
  renderSummary();
  renderExtensions();
  renderActions();
  renderEndpoints();
}

async function refresh() {
  if (state.loading) return;
  state.loading = true;
  try {
    const results = await Promise.allSettled([request('/extensions'), request('/actions'), request('/endpoints')]);
    if (results[0].status === 'fulfilled') state.extensions = normalizeList(results[0].value, ['extensions','items']);
    if (results[1].status === 'fulfilled') state.actions = normalizeList(results[1].value, ['actions','items']);
    if (results[2].status === 'fulfilled') state.endpoints = normalizeList(results[2].value, ['endpoints','items']);
    results.forEach((result, index) => { if (result.status === 'rejected') console.warn(['extensions','actions','endpoints'][index], result.reason); });
    render();
  } finally {
    state.loading = false;
  }
}

async function importExtension(event) {
  event.preventDefault();
  let manifest;
  try { manifest = JSON.parse($('#extensionManifestJson').value); }
  catch (error) { return toast('Invalid JSON', error.message, 'warning'); }
  try {
    await request('/extensions', {method:'POST', body:JSON.stringify(manifest)});
    $('#extensionImportDialog').close();
    event.currentTarget.reset();
    toast('Extension installed', manifest.name || manifest.id, 'good');
    await refresh();
  } catch (error) { toast('Extension import failed', error.message, 'warning'); }
}

async function toggleExtension(id) {
  const current = state.extensions.find(item => item.id === id);
  if (!current) return;
  try {
    await request(`/extensions/${encodeURIComponent(id)}`, {method:'PUT', body:JSON.stringify({...current, enabled:current.enabled === false})});
    await refresh();
  } catch (error) { toast('Extension update failed', error.message, 'warning'); }
}

async function deleteExtension(id) {
  if (!confirm(`Uninstall extension ${id}? Registered assets from this extension may be removed.`)) return;
  try {
    await request(`/extensions/${encodeURIComponent(id)}`, {method:'DELETE'});
    toast('Extension uninstalled', id, 'good');
    await refresh();
  } catch (error) { toast('Extension uninstall failed', error.message, 'warning'); }
}

function resetActionForm() {
  const form = $('#actionForm');
  form.reset();
  form.dataset.mode = 'create';
  form.dataset.originalId = '';
  form.elements.id.disabled = false;
  form.elements.config.value = '{}';
  form.elements.enabled.checked = true;
  $('#actionDialog h2').textContent = 'Create action';
  $('#actionDialog button[type="submit"]').textContent = 'Create action';
}

function openActionDialog(id = '') {
  resetActionForm();
  if (id) {
    const item = state.actions.find(action => action.id === id);
    if (!item) return;
    const form = $('#actionForm');
    form.dataset.mode = 'edit';
    form.dataset.originalId = item.id;
    form.elements.id.value = item.id;
    form.elements.id.disabled = true;
    form.elements.name.value = item.name || '';
    form.elements.type.value = item.type || 'models-scan';
    form.elements.confirmation.value = item.confirmation || 'dangerous-only';
    form.elements.permissions.value = (item.permissions || []).join(', ');
    form.elements.description.value = item.description || '';
    form.elements.config.value = JSON.stringify(item.config || {}, null, 2);
    form.elements.enabled.checked = item.enabled !== false;
    $('#actionDialog h2').textContent = 'Edit action';
    $('#actionDialog button[type="submit"]').textContent = 'Save action';
  }
  $('#actionDialog').showModal();
}

async function saveAction(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const data = Object.fromEntries(new FormData(form));
  let config;
  try { config = JSON.parse(data.config || '{}'); }
  catch (error) { return toast('Invalid config JSON', error.message, 'warning'); }
  const id = form.dataset.originalId || data.id;
  const payload = {id,name:data.name,description:data.description || '',type:data.type,confirmation:data.confirmation,permissions:String(data.permissions || '').split(',').map(item => item.trim()).filter(Boolean),config,enabled:form.elements.enabled.checked};
  const editing = form.dataset.mode === 'edit';
  try {
    await request(editing ? `/actions/${encodeURIComponent(id)}` : '/actions', {method:editing ? 'PUT' : 'POST', body:JSON.stringify(payload)});
    $('#actionDialog').close();
    resetActionForm();
    toast(editing ? 'Action updated' : 'Action created', payload.name, 'good');
    await refresh();
  } catch (error) { toast(editing ? 'Action update failed' : 'Action creation failed', error.message, 'warning'); }
}

async function toggleAction(id) {
  const item = state.actions.find(action => action.id === id);
  if (!item) return;
  try {
    await request(`/actions/${encodeURIComponent(id)}`, {method:'PUT', body:JSON.stringify({...item, enabled:item.enabled === false})});
    await refresh();
  } catch (error) { toast('Action update failed', error.message, 'warning'); }
}

async function runAction(id) {
  const action = state.actions.find(item => item.id === id);
  if (!action) return;
  if (action.confirmation === 'always' && !confirm(`Run action ${action.name || id}?`)) return;
  try {
    const result = await request(`/actions/${encodeURIComponent(id)}/execute`, {method:'POST', body:'{}'});
    toast('Action started', result?.id || result?.jobId || id, 'good');
  } catch (error) { toast('Action execution failed', error.message, 'warning'); }
}

async function deleteAction(id) {
  if (!confirm(`Delete action ${id}?`)) return;
  try { await request(`/actions/${encodeURIComponent(id)}`, {method:'DELETE'}); await refresh(); }
  catch (error) { toast('Action deletion failed', error.message, 'warning'); }
}

function resetEndpointForm() {
  const form = $('#endpointForm');
  form.reset();
  form.dataset.mode = 'create';
  form.dataset.originalId = '';
  form.elements.id.disabled = false;
  form.elements.enabled.checked = true;
  $('#endpointDialog h2').textContent = 'Create endpoint';
  $('#endpointDialog button[type="submit"]').textContent = 'Create endpoint';
}

function openEndpointDialog(id = '') {
  resetEndpointForm();
  if (id) {
    const item = state.endpoints.find(endpoint => endpoint.id === id);
    if (!item) return;
    const form = $('#endpointForm');
    form.dataset.mode = 'edit';
    form.dataset.originalId = item.id;
    form.elements.id.value = item.id;
    form.elements.id.disabled = true;
    form.elements.name.value = item.name || '';
    form.elements.baseUrl.value = item.baseUrl || '';
    form.elements.healthPath.value = item.healthCheck?.path || '';
    form.elements.enabled.checked = item.enabled !== false;
    $('#endpointDialog h2').textContent = 'Edit endpoint';
    $('#endpointDialog button[type="submit"]').textContent = 'Save endpoint';
  }
  $('#endpointDialog').showModal();
}

async function saveEndpoint(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const data = Object.fromEntries(new FormData(form));
  const id = form.dataset.originalId || data.id;
  const payload = {id,name:data.name,baseUrl:data.baseUrl,enabled:form.elements.enabled.checked,...(data.healthPath ? {healthCheck:{path:data.healthPath,method:'GET'}} : {})};
  const editing = form.dataset.mode === 'edit';
  try {
    await request(editing ? `/endpoints/${encodeURIComponent(id)}` : '/endpoints', {method:editing ? 'PUT' : 'POST', body:JSON.stringify(payload)});
    $('#endpointDialog').close();
    resetEndpointForm();
    toast(editing ? 'Endpoint updated' : 'Endpoint registered', payload.name, 'good');
    await refresh();
  } catch (error) { toast(editing ? 'Endpoint update failed' : 'Endpoint creation failed', error.message, 'warning'); }
}

async function toggleEndpoint(id) {
  const item = state.endpoints.find(endpoint => endpoint.id === id);
  if (!item) return;
  try {
    await request(`/endpoints/${encodeURIComponent(id)}`, {method:'PUT', body:JSON.stringify({...item, enabled:item.enabled === false})});
    await refresh();
  } catch (error) { toast('Endpoint update failed', error.message, 'warning'); }
}

async function testEndpoint(id) {
  try {
    const result = await request(`/endpoints/${encodeURIComponent(id)}/test`, {method:'POST', body:'{}'});
    const ok = result?.reachable ?? result?.ok ?? result?.healthy;
    toast(ok === false ? 'Endpoint test failed' : 'Endpoint reachable', result?.status ? String(result.status) : id, ok === false ? 'warning' : 'good');
    await refresh();
  } catch (error) { toast('Endpoint test failed', error.message, 'warning'); }
}

async function deleteEndpoint(id) {
  if (!confirm(`Delete endpoint ${id}? Actions referencing it may stop working.`)) return;
  try { await request(`/endpoints/${encodeURIComponent(id)}`, {method:'DELETE'}); await refresh(); }
  catch (error) { toast('Endpoint deletion failed', error.message, 'warning'); }
}

function wire() {
  $('#importExtensionBtn')?.addEventListener('click', () => $('#extensionImportDialog').showModal());
  $('#createActionBtn')?.addEventListener('click', () => openActionDialog());
  $('#createEndpointBtn')?.addEventListener('click', () => openEndpointDialog());
  $('#extensionImportForm')?.addEventListener('submit', importExtension);
  $('#actionForm')?.addEventListener('submit', saveAction);
  $('#endpointForm')?.addEventListener('submit', saveEndpoint);
  $$('.extension-dialog-close').forEach(button => button.addEventListener('click', () => button.closest('dialog').close()));
  document.querySelector('[data-page="extensions"]')?.addEventListener('click', () => refresh().catch(error => toast('Extension refresh failed', error.message, 'warning')));
}

function boot() {
  wire();
  resetActionForm();
  resetEndpointForm();
  refresh().catch(error => toast('Extensions unavailable', error.message, 'warning'));
  setInterval(() => {
    if (document.querySelector('[data-page-view="extensions"]')?.classList.contains('active')) refresh().catch(error => console.warn('Extension refresh failed', error));
  }, 10000);
}

if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot, {once:true});
else boot();
