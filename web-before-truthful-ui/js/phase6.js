const $ = (selector, root=document) => root.querySelector(selector);

async function api(path, options={}) {
  const response = await fetch(`/api/v1${path}`, {
    headers: {'Content-Type':'application/json', ...(options.headers || {})},
    ...options,
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok || payload.ok === false) {
    const err = payload.error || {};
    throw new Error(`${err.code || response.status}: ${err.message || response.statusText}`);
  }
  return payload.data;
}

function notify(title, message='') {
  const region = $('#toastRegion');
  if (!region) return;
  const item = document.createElement('div');
  item.className = 'toast';
  item.innerHTML = `<strong>${escapeHtml(title)}</strong><span>${escapeHtml(message)}</span>`;
  region.append(item);
  setTimeout(() => item.remove(), 4200);
}

function escapeHtml(value='') {
  return String(value).replace(/[&<>'"]/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[ch]));
}

function permissionFor(type) {
  return {
    'models-scan':'models.scan',
    'controller-status':'machine.status',
    'rpc-start':'machine.rpc.start',
    'rpc-stop':'machine.rpc.stop',
    'http-request':'network.http',
    'profile-select':'profile.read',
  }[type];
}

function configFor(data) {
  if (data.type === 'http-request') return {endpointId:data.targetId, method:data.method, path:data.path || '/', timeoutSec:10};
  if (['controller-status','rpc-start','rpc-stop'].includes(data.type)) return {machineId:data.targetId};
  if (data.type === 'profile-select') return {profileId:data.targetId};
  return {};
}

async function loadExtensibility() {
  const extensionList = $('#extensionList');
  const actionList = $('#actionEndpointList');
  if (!extensionList || !actionList) return;
  try {
    const [extensions, actions, endpoints] = await Promise.all([
      api('/extensions'), api('/actions'), api('/endpoints')
    ]);
    extensionList.innerHTML = extensions.length ? extensions.map(ext => `
      <article class="manifest-row">
        <div><span class="status-badge ${ext.enabled === false ? 'warning' : 'good'}">${ext.enabled === false ? 'Disabled' : 'Enabled'}</span><h3>${escapeHtml(ext.name)}</h3><code>${escapeHtml(ext.id)} · v${escapeHtml(ext.version)}</code><p>${escapeHtml(ext.description || 'No description')}</p></div>
        <div class="manifest-meta"><small>${(ext.widgets || []).length} widgets</small><small>${(ext.actions || []).length} actions</small><small>${(ext.endpoints || []).length} endpoints</small><button class="button compact secondary extension-toggle" data-id="${escapeHtml(ext.id)}" data-enabled="${ext.enabled !== false}">${ext.enabled === false ? 'Enable' : 'Disable'}</button><button class="button compact danger-soft extension-remove" data-id="${escapeHtml(ext.id)}">Uninstall</button></div>
      </article>`).join('') : `<div class="empty-state compact-empty"><span>＋</span><h3>No extension manifests installed</h3><p>Import the sample manifest or another declarative JSON extension.</p></div>`;
    const actionRows = actions.map(action => `<article class="asset-row"><div><strong>${escapeHtml(action.name)}</strong><code>${escapeHtml(action.type)} · ${escapeHtml(action.id)}</code></div><button class="button compact primary execute-action" data-id="${escapeHtml(action.id)}">Run</button></article>`);
    const endpointRows = endpoints.map(endpoint => `<article class="asset-row"><div><strong>${escapeHtml(endpoint.name)}</strong><code>${escapeHtml(endpoint.baseUrl)}</code></div><button class="button compact secondary test-endpoint" data-id="${escapeHtml(endpoint.id)}">Test</button></article>`);
    actionList.innerHTML = [...actionRows, ...endpointRows].join('') || `<div class="empty-state compact-empty"><p>No actions or endpoints registered.</p></div>`;
    bindDynamic();
  } catch (error) {
    extensionList.innerHTML = `<div class="empty-state compact-empty"><h3>Control-plane API unavailable</h3><p>${escapeHtml(error.message)}</p></div>`;
    actionList.innerHTML = '';
  }
}

function bindDynamic() {
  document.querySelectorAll('.extension-toggle').forEach(button => button.onclick = async () => {
    try {
      await api(`/extensions/${button.dataset.id}`, {method:'PUT', body:JSON.stringify({enabled:button.dataset.enabled !== 'true'})});
      notify('Extension state updated', button.dataset.id); await loadExtensibility();
    } catch (error) { notify('Extension update failed', error.message); }
  });
  document.querySelectorAll('.extension-remove').forEach(button => button.onclick = async () => {
    if (!confirm(`Uninstall ${button.dataset.id}? Its widgets, actions, and endpoints will be removed from the registry.`)) return;
    try { await api(`/extensions/${button.dataset.id}`, {method:'DELETE'}); notify('Extension uninstalled', button.dataset.id); await loadExtensibility(); }
    catch (error) { notify('Uninstall failed', error.message); }
  });
  document.querySelectorAll('.execute-action').forEach(button => button.onclick = async () => {
    try { const job = await api(`/actions/${button.dataset.id}/execute`, {method:'POST', body:'{}'}); notify('Action accepted', `Job ${job.id}`); }
    catch (error) { notify('Action rejected', error.message); }
  });
  document.querySelectorAll('.test-endpoint').forEach(button => button.onclick = async () => {
    try { const result = await api(`/endpoints/${button.dataset.id}/test`, {method:'POST', body:'{}'}); notify(result.reachable ? 'Endpoint reachable' : 'Endpoint unavailable', `${button.dataset.id} · ${result.latencyMs} ms`); }
    catch (error) { notify('Endpoint test failed', error.message); }
  });
}

const actionForm = $('#actionForm');
if (actionForm) actionForm.addEventListener('submit', async event => {
  event.preventDefault();
  const data = Object.fromEntries(new FormData(actionForm));
  const payload = {
    id:data.id, name:data.name, description:data.description || '', type:data.type,
    permissions:[permissionFor(data.type)], config:configFor(data),
    confirmation:data.confirmation, enabled:true
  };
  try {
    await api('/actions', {method:'POST', body:JSON.stringify(payload)});
    $('#actionDialog')?.close(); actionForm.reset(); notify('Custom action created', payload.name); await loadExtensibility();
  } catch (error) { notify('Action validation failed', error.message); }
});

const endpointForm = $('#endpointForm');
if (endpointForm) endpointForm.addEventListener('submit', async event => {
  event.preventDefault(); const data = Object.fromEntries(new FormData(endpointForm));
  try {
    await api('/endpoints', {method:'POST', body:JSON.stringify({id:data.id,name:data.name,baseUrl:data.baseUrl,healthCheck:{path:data.healthPath || '/',method:'GET'},enabled:true})});
    $('#endpointDialog')?.close(); endpointForm.reset(); notify('Endpoint registered', data.name); await loadExtensibility();
  } catch (error) { notify('Endpoint validation failed', error.message); }
});

$('#addEndpointBtn')?.addEventListener('click', () => $('#endpointDialog')?.showModal());
$('#refreshExtensionsBtn')?.addEventListener('click', loadExtensibility);
$('#importExtensionBtn')?.addEventListener('click', () => $('#extensionFileInput')?.click());
$('#extensionFileInput')?.addEventListener('change', async event => {
  const file = event.target.files?.[0]; if (!file) return;
  try {
    const manifest = JSON.parse(await file.text());
    await api('/extensions', {method:'POST', body:JSON.stringify(manifest)});
    notify('Extension installed', manifest.name || manifest.id); await loadExtensibility();
  } catch (error) { notify('Extension rejected', error.message); }
  event.target.value = '';
});

document.querySelectorAll('[data-page="extensions"]').forEach(button => button.addEventListener('click', loadExtensibility));
loadExtensibility();
