import {api, ApiError} from './api.js';

const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const esc = value => String(value ?? '').replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
const state = {system:null, capabilities:null, machines:[], models:[], profiles:[], jobs:[], telemetry:null, logs:[], requests:null, gateway:null, workspaces:null, timer:null};

function errorText(error) {
  return error instanceof ApiError ? `${error.code}: ${error.message}` : (error?.message || String(error));
}

function notify(title, message = '', level = 'neutral') {
  const region = $('#toastRegion');
  if (!region) return;
  const item = document.createElement('div');
  item.className = `toast ${level}`;
  item.innerHTML = `<strong>${esc(title)}</strong><span>${esc(message)}</span>`;
  region.append(item);
  setTimeout(() => item.remove(), 4500);
}

function badge(text, level = 'neutral') {
  return `<span class="status-badge ${level}">${esc(text)}</span>`;
}

function list(value, keys = []) {
  if (Array.isArray(value)) return value;
  for (const key of keys) if (Array.isArray(value?.[key])) return value[key];
  return [];
}

function bytes(value) {
  let n = Number(value);
  if (!Number.isFinite(n) || n < 0) return 'Unknown';
  const units = ['B','KB','MB','GB','TB'];
  let i = 0;
  while (n >= 1024 && i < units.length - 1) { n /= 1024; i += 1; }
  return `${i === 0 || n >= 10 ? n.toFixed(0) : n.toFixed(1)} ${units[i]}`;
}

function terminal(value) {
  return ['completed','failed','cancelled','done'].includes(String(value || '').toLowerCase());
}

function renderHeader() {
  const runtime = state.system?.runtime || {};
  const process = runtime.process || {};
  const ready = process.running === true || ['ready','running'].includes(runtime.state);
  $('#healthHost').className = `health-pill ${ready ? 'good' : 'neutral'}`;
  $('#healthHost').innerHTML = `<span></span> Host ${esc(ready ? 'ready' : (runtime.state || 'unknown'))}`;

  const online = state.machines.filter(m => ['reachable','online'].includes(m.status)).length;
  $('#healthMachines').className = `health-pill ${state.machines.length && online === state.machines.length ? 'good' : 'neutral'}`;
  $('#healthMachines').innerHTML = `<span></span> ${online}/${state.machines.length} tested reachable`;

  const openai = state.capabilities?.openai || state.capabilities?.gateway?.openai || state.capabilities?.compatibility?.openai;
  const ollama = state.capabilities?.ollama || state.capabilities?.gateway?.ollama || state.capabilities?.compatibility?.ollama;
  $('#healthOpenAI').textContent = `OpenAI ${openai ? 'declared' : 'unknown'}`;
  $('#healthOllama').textContent = `Ollama ${ollama ? 'declared' : 'unknown'}`;

  $('#machineCount').textContent = state.machines.length;
  $('#modelCount').textContent = state.models.length;
  $('#controlPlaneDot').className = 'status-dot good';
  $('#controlPlaneLabel').textContent = 'Control plane online';
  $('#saveState').innerHTML = '<span class="status-dot good"></span> API connected';
}

function renderRuntime() {
  const runtime = state.system?.runtime || {};
  const process = runtime.process || {};
  const model = state.models.find(m => m.id === runtime.activeModelId);
  const runtimeState = runtime.state || (process.running ? 'running' : 'stopped');
  $('#runtimeTitle').textContent = model?.name || model?.filename || (runtime.activeModelId || 'No active model');
  $('#runtimeBadge').textContent = runtimeState;
  $('#runtimeBadge').className = `status-badge ${['ready','running'].includes(runtimeState) ? 'good' : runtimeState === 'starting' ? 'warning' : 'neutral'}`;
  $('#runtimeBody').innerHTML = `
    <div class="runtime-stats">
      <div class="metric"><span>State</span><strong>${esc(runtimeState)}</strong><small>Backend evidence</small></div>
      <div class="metric"><span>Process</span><strong>${process.running ? 'Running' : 'Stopped'}</strong><small>${process.pid ? `PID ${esc(process.pid)}` : 'No PID'}</small></div>
      <div class="metric"><span>Model</span><strong>${esc(model?.name || model?.filename || 'None')}</strong><small>${esc(runtime.activeModelId || 'Not selected')}</small></div>
      <div class="metric"><span>Jobs</span><strong>${state.jobs.length}</strong><small>Backend job store</small></div>
    </div>
    <div class="runtime-actions"><button class="button primary" type="button" id="launchModelBtn">Launch model</button><button class="button danger-soft" type="button" id="stopRuntimeBtn">Stop runtime</button></div>`;
  $('#launchModelBtn').addEventListener('click', openLaunch);
  $('#stopRuntimeBtn').addEventListener('click', stopRuntime);
}

function renderMachines() {
  const grid = $('#machineGrid');
  const topology = $('#topologyCanvas');
  const online = state.machines.filter(m => ['reachable','online'].includes(m.status)).length;
  $('#topologySummary').innerHTML = badge(`${online}/${state.machines.length} tested reachable`, state.machines.length && online === state.machines.length ? 'good' : 'neutral');

  grid.innerHTML = state.machines.length ? state.machines.map(m => `
    <article class="content-card machine-card">
      <div class="section-head"><div><h3>${esc(m.name || m.id)}</h3><code>${esc(m.addresses?.[0] || 'Unknown')}</code></div>${badge(m.status || 'unknown', ['reachable','online'].includes(m.status) ? 'good' : 'neutral')}</div>
      <p>Controller :${esc(m.controller?.port || 'unknown')} · RPC :${esc(m.rpc?.port || 'unknown')}</p>
      <div class="runtime-actions">
        <button class="button compact secondary test-machine" type="button" data-id="${esc(m.id)}">Test</button>
        <button class="button compact secondary start-rpc" type="button" data-id="${esc(m.id)}">Start RPC</button>
        <button class="button compact secondary stop-rpc" type="button" data-id="${esc(m.id)}">Stop RPC</button>
      </div>
    </article>`).join('') : '<div class="empty-state"><p>No machines registered.</p></div>';

  topology.innerHTML = state.machines.length ? state.machines.map(m => `
    <div class="machine-node">
      <div class="node-head"><span class="status-dot ${['reachable','online'].includes(m.status) ? 'good' : 'neutral'}"></span><strong>${esc(m.name || m.id)}</strong><small>${esc(m.addresses?.[0] || 'Unknown')}</small></div>
      <div class="node-grid"><span>Status</span><b>${esc(m.status || 'unknown')}</b><span>RPC</span><b>:${esc(m.rpc?.port || 'unknown')}</b></div>
    </div>`).join('') : '<div class="empty-state"><p>No topology available.</p></div>';

  $$('.test-machine').forEach(b => b.addEventListener('click', () => testMachine(b.dataset.id)));
  $$('.start-rpc').forEach(b => b.addEventListener('click', () => rpc(b.dataset.id, 'start')));
  $$('.stop-rpc').forEach(b => b.addEventListener('click', () => rpc(b.dataset.id, 'stop')));
}

function renderModels() {
  $('#modelsTableBody').innerHTML = state.models.length ? state.models.map(m => {
    const meta = m.metadata || m.gguf || {};
    return `<tr>
      <td><strong>${esc(m.name || m.filename || m.id)}</strong><small>${esc(m.path || '')}</small></td>
      <td>${esc(m.architecture || meta.architecture || 'Unknown')}</td>
      <td>${esc(m.quantization || meta.fileType || 'Unknown')}</td>
      <td>${bytes(m.sizeBytes ?? m.size)}</td>
      <td>${esc(m.contextLength || meta.contextLength || 'Unknown')}</td>
      <td>${esc(m.profileId || 'None')}</td>
      <td>${badge(m.parseError ? 'Unknown' : 'Unverified', m.parseError ? 'warning' : 'neutral')}</td>
      <td>${badge(m.state || 'registered')}</td>
    </tr>`;
  }).join('') : '<tr><td colspan="8">No models registered. Run a model scan.</td></tr>';
}

function renderTelemetry() {
  const data = state.telemetry || {};
  const local = data.local || {};
  const gpus = list(local.gpus || local.nvidia);
  const memory = local.memory || {};
  const markup = `
    <div class="telemetry-metrics">
      <div><span>State</span><strong>${esc(data.state || 'unavailable')}</strong><small>${esc(data.timestamp || 'No timestamp')}</small></div>
      <div><span>Memory used</span><strong>${bytes(memory.usedBytes ?? memory.used)}</strong><small>${bytes(memory.totalBytes ?? memory.total)} total</small></div>
      <div><span>GPUs</span><strong>${gpus.length}</strong><small>Backend reported</small></div>
    </div>
    <div class="stack-list">${gpus.length ? gpus.map(g => `<article class="asset-row"><div><strong>${esc(g.name || 'GPU')}</strong><code>${bytes(g.memoryUsedBytes ?? g.memoryUsed)} / ${bytes(g.memoryTotalBytes ?? g.memoryTotal)}</code></div><span>${esc(g.utilizationGpu ?? g.utilization ?? 'Unknown')}%</span></article>`).join('') : '<p>No GPU telemetry reported.</p>'}</div>`;
  $('#telemetryWidget').innerHTML = markup;
  $('#telemetryPage').innerHTML = markup;
}

function requestRows() {
  return list(state.requests, ['requests','active','items']);
}

function renderRequests() {
  const rows = requestRows();
  $('#overviewRequestsBody').innerHTML = rows.length ? rows.map(r => {
    const id = r.id || r.requestId;
    return `<tr><td><code>${esc(id || 'Unknown')}</code></td><td>${esc(r.route || r.path || 'Unknown')}</td><td>${badge(r.state || r.status || 'unknown')}</td><td>${esc(r.startedAt || r.createdAt || 'Unknown')}</td><td>${id ? `<button class="text-button danger-text cancel-request" type="button" data-id="${esc(id)}">Cancel</button>` : ''}</td></tr>`;
  }).join('') : '<tr><td colspan="5">No requests reported.</td></tr>';
  $$('.cancel-request').forEach(b => b.addEventListener('click', () => cancelRequest(b.dataset.id)));
}

function renderLogs() {
  const logs = list(state.logs, ['items','logs']);
  $('#logOutput').textContent = logs.length ? logs.map(x => `[${x.timestamp || x.at || ''}] ${String(x.level || 'info').toUpperCase()} ${x.source || x.category || 'system'} ${x.message || ''}`).join('\n') : 'No backend log evidence recorded.';
  $('#overviewEvidence').innerHTML = logs.length ? logs.slice(0, 5).map(x => `<div class="event-item"><span class="event-icon ${x.level === 'error' ? 'warning' : 'good'}">${x.level === 'error' ? '!' : '•'}</span><div><strong>${esc(x.message || 'Event')}</strong><p>${esc(x.source || x.category || 'system')}</p><small>${esc(x.timestamp || x.at || '')}</small></div></div>`).join('') : '<div class="empty-state"><p>No backend evidence recorded.</p></div>';
}

function renderProfiles() {
  $('#profileGrid').innerHTML = state.profiles.length ? state.profiles.map(p => `<div class="content-card profile-card">${badge(p.validationState || 'unknown')}<h3>${esc(p.name || p.id)}</h3><p>${esc(p.description || 'No description')}</p><div class="profile-meta"><span>${esc(p.id)}</span></div></div>`).join('') : '<div class="content-card"><p>No profiles registered.</p></div>';
}

function renderGateway() {
  const caps = state.capabilities || {};
  const openai = caps.openai || caps.gateway?.openai || caps.compatibility?.openai;
  const ollama = caps.ollama || caps.gateway?.ollama || caps.compatibility?.ollama;
  $('#gatewayGrid').innerHTML = `
    <div class="content-card endpoint-card"><span class="status-dot ${openai ? 'good' : 'neutral'}"></span><div><h3>OpenAI compatibility</h3><p>${openai ? esc(JSON.stringify(openai)) : 'Not declared'}</p></div></div>
    <div class="content-card endpoint-card"><span class="status-dot ${ollama ? 'good' : 'neutral'}"></span><div><h3>Ollama compatibility</h3><p>${ollama ? esc(JSON.stringify(ollama)) : 'Not declared'}</p></div></div>
    <div class="content-card endpoint-card"><div><h3>Gateway state</h3><p>${esc(state.gateway?.state || 'unknown')}</p></div></div>`;
}

function renderJobs() {
  const active = state.jobs.filter(j => !terminal(j.state));
  $('#jobCount').textContent = active.length;
  $('#jobList').innerHTML = state.jobs.length ? state.jobs.slice(0, 20).map(j => `<div class="job-item"><strong>${esc(j.type || j.title || j.id)}</strong><small>${esc(j.phase || j.state || 'unknown')}</small><div class="ux-progress"><span style="width:${Math.max(0, Math.min(100, Number(j.progress || 0)))}%"></span></div></div>`).join('') : '<div class="empty-state"><p>No backend jobs</p></div>';
}

async function pollJob(id, timeout = 120000) {
  const start = Date.now();
  while (Date.now() - start < timeout) {
    const job = await api.job(id);
    state.jobs = await api.jobs();
    renderJobs();
    if (terminal(job.state)) {
      if (['failed','cancelled'].includes(String(job.state).toLowerCase())) throw new Error(job.error?.message || `Job ${job.state}`);
      notify('Job completed', job.type || job.id, 'good');
      return job;
    }
    await new Promise(r => setTimeout(r, 800));
  }
  throw new Error(`Timed out waiting for ${id}`);
}

async function testMachine(id) {
  try { const result = await api.testMachine(id); notify(result.reachable ? 'Machine reachable' : 'Machine offline', result.diagnostic || `${result.latencyMs ?? 'Unknown'} ms`, result.reachable ? 'good' : 'warning'); await refreshAll(); }
  catch (e) { notify('Machine test failed', errorText(e), 'warning'); }
}

async function rpc(id, action) {
  try { const job = action === 'start' ? await api.startRpc(id) : await api.stopRpc(id); notify(`RPC ${action} accepted`, job.id); await pollJob(job.id); await refreshAll(); }
  catch (e) { notify(`RPC ${action} failed`, errorText(e), 'warning'); }
}

async function scanModels() {
  try { const job = await api.scanModels({}); notify('Model scan accepted', job.id); await pollJob(job.id); await refreshAll(); }
  catch (e) { notify('Model scan failed', errorText(e), 'warning'); }
}

async function cancelRequest(id) {
  try { await api.cancelRequest(id); notify('Request cancelled', id, 'good'); await refreshAll(); }
  catch (e) { notify('Cancellation unavailable', errorText(e), 'warning'); }
}

function openLaunch() {
  if (!state.models.length) return notify('No models available', 'Run a model scan first.', 'warning');
  $('#launchPanel').innerHTML = `<div class="form-grid"><label>Model<select id="launchModelSelect">${state.models.map(m => `<option value="${esc(m.id)}">${esc(m.name || m.filename || m.id)}</option>`).join('')}</select></label><label>Profile<select id="launchProfileSelect"><option value="">No profile</option>${state.profiles.map(p => `<option value="${esc(p.id)}">${esc(p.name || p.id)}</option>`).join('')}</select></label><div id="preflightResult">Preflight not run.</div></div>`;
  $('#launchDialog').showModal();
}

async function preflightAndLaunch() {
  const modelId = $('#launchModelSelect')?.value;
  const profileId = $('#launchProfileSelect')?.value || undefined;
  try {
    const result = await api.preflight({modelId, profileId});
    $('#preflightResult').textContent = `Risk: ${result.allocation?.risk || 'unknown'} · launchAllowed: ${Boolean(result.launchAllowed)}`;
    if (!result.launchAllowed) return notify('Launch blocked', 'Backend preflight did not allow this allocation.', 'warning');
    if (!confirm('Backend preflight allows launch. Start the real runtime process?')) return;
    const job = await api.launch({modelId, profileId});
    $('#launchDialog').close();
    notify('Runtime launch accepted', job.id);
    await pollJob(job.id);
    await refreshAll();
  } catch (e) { notify('Runtime launch failed', errorText(e), 'warning'); }
}

async function stopRuntime() {
  if (!confirm('Drain requests and stop the runtime and configured workers?')) return;
  try { const job = await api.stop({force:false}); notify('Stop accepted', job.id); await pollJob(job.id); await refreshAll(); }
  catch (e) { notify('Stop failed', errorText(e), 'warning'); }
}

async function createMachine(event) {
  event.preventDefault();
  const f = event.currentTarget;
  const data = Object.fromEntries(new FormData(f));
  const payload = {
    id: `machine-${String(data.name || data.address).toLowerCase().replace(/[^a-z0-9]+/g,'-')}-${Date.now().toString().slice(-5)}`,
    name: data.name,
    addresses: [data.address],
    controller: {scheme:data.controllerProtocol, port:Number(data.controllerPort)},
    rpc: {port:Number(data.rpcPort), enabled:true},
    paths: {runtime:data.runtimePath || '', models:data.modelsPath || ''},
    tags: [data.role],
    enabled: true,
  };
  try { await api.createMachine(payload); $('#machineDialog').close(); f.reset(); notify('Machine registered', payload.name, 'good'); await refreshAll(); }
  catch (e) { notify('Machine registration failed', errorText(e), 'warning'); }
}

function permissionFor(type) {
  return {'models-scan':'models.scan','controller-status':'machine.status','rpc-start':'machine.rpc.start','rpc-stop':'machine.rpc.stop','http-request':'network.http','profile-select':'profile.read'}[type];
}
function configFor(data) {
  if (data.type === 'http-request') return {endpointId:data.targetId, method:data.method, path:data.path || '/', timeoutSec:10};
  if (['controller-status','rpc-start','rpc-stop'].includes(data.type)) return {machineId:data.targetId};
  if (data.type === 'profile-select') return {profileId:data.targetId};
  return {};
}
async function loadExtensions() {
  try {
    const [extensions, actions, endpoints] = await Promise.all([api.extensions(), api.actions(), api.endpoints()]);
    $('#extensionList').innerHTML = extensions.length ? extensions.map(x => `<article class="manifest-row"><div>${badge(x.enabled === false ? 'Disabled' : 'Enabled', x.enabled === false ? 'warning' : 'good')}<h3>${esc(x.name || x.id)}</h3><code>${esc(x.id)} · v${esc(x.version || 'unknown')}</code><p>${esc(x.description || 'No description')}</p></div><div class="manifest-meta"><button class="button compact secondary toggle-extension" type="button" data-id="${esc(x.id)}" data-enabled="${x.enabled !== false}">${x.enabled === false ? 'Enable' : 'Disable'}</button><button class="button compact danger-soft remove-extension" type="button" data-id="${esc(x.id)}">Uninstall</button></div></article>`).join('') : '<div class="empty-state"><p>No extensions installed.</p></div>';
    $('#actionEndpointList').innerHTML = [...actions.map(x => `<article class="asset-row"><div><strong>${esc(x.name)}</strong><code>${esc(x.type)} · ${esc(x.id)}</code></div><button class="button compact primary run-action" type="button" data-id="${esc(x.id)}">Run</button></article>`), ...endpoints.map(x => `<article class="asset-row"><div><strong>${esc(x.name)}</strong><code>${esc(x.baseUrl)}</code></div><button class="button compact secondary test-endpoint" type="button" data-id="${esc(x.id)}">Test</button></article>`)].join('') || '<div class="empty-state"><p>No actions or endpoints registered.</p></div>';
    $$('.toggle-extension').forEach(b => b.addEventListener('click', async () => { await api.updateExtension(b.dataset.id, {enabled:b.dataset.enabled !== 'true'}); await loadExtensions(); }));
    $$('.remove-extension').forEach(b => b.addEventListener('click', async () => { if (confirm(`Uninstall ${b.dataset.id}?`)) { await api.deleteExtension(b.dataset.id); await loadExtensions(); } }));
    $$('.run-action').forEach(b => b.addEventListener('click', async () => { const job = await api.executeAction(b.dataset.id); notify('Action accepted', job.id); }));
    $$('.test-endpoint').forEach(b => b.addEventListener('click', async () => { const r = await api.testEndpoint(b.dataset.id); notify(r.reachable ? 'Endpoint reachable' : 'Endpoint unavailable', `${r.latencyMs ?? 'Unknown'} ms`); }));
  } catch (e) { $('#extensionList').innerHTML = `<div class="empty-state"><p>${esc(errorText(e))}</p></div>`; }
}

async function createAction(event) {
  event.preventDefault();
  const data = Object.fromEntries(new FormData(event.currentTarget));
  try { await api.createAction({id:data.id,name:data.name,description:data.description || '',type:data.type,permissions:[permissionFor(data.type)],config:configFor(data),confirmation:data.confirmation,enabled:true}); $('#actionDialog').close(); event.currentTarget.reset(); await loadExtensions(); }
  catch (e) { notify('Action validation failed', errorText(e), 'warning'); }
}
async function createEndpoint(event) {
  event.preventDefault();
  const data = Object.fromEntries(new FormData(event.currentTarget));
  try { await api.createEndpoint({id:data.id,name:data.name,baseUrl:data.baseUrl,healthCheck:{path:data.healthPath || '/',method:'GET'},enabled:true}); $('#endpointDialog').close(); event.currentTarget.reset(); await loadExtensions(); }
  catch (e) { notify('Endpoint validation failed', errorText(e), 'warning'); }
}

async function loadWorkspaces() {
  try {
    state.workspaces = await api.workspaces();
    const items = state.workspaces?.items || [];
    const select = $('#workspaceSelect');
    select.innerHTML = items.length ? items.map(w => `<option value="${esc(w.id)}">${esc(w.name)}</option>`).join('') : '<option>No workspace</option>';
    if (state.workspaces?.activeWorkspaceId) select.value = state.workspaces.activeWorkspaceId;
    applyWorkspace(items.find(w => w.id === select.value) || items[0]);
  } catch (e) {
    $('#workspaceSelect').innerHTML = '<option>Unavailable</option>';
    notify('Workspace API unavailable', errorText(e), 'warning');
  }
}
function applyWorkspace(workspace) {
  if (!workspace) return;
  const byType = new Map((workspace.widgets || []).map(w => [w.type, w]));
  $$('#workspaceGrid .widget').forEach(node => {
    const item = byType.get(node.dataset.widgetType);
    if (!item) return;
    node.hidden = item.visibility === false;
    node.style.gridColumn = `span ${Math.max(2, Math.min(12, Number(item.size?.w || 4)))}`;
  });
}
async function saveWorkspace() {
  const items = state.workspaces?.items || [];
  const current = items.find(w => w.id === $('#workspaceSelect').value);
  if (!current) return notify('Workspace unavailable', 'No active workspace.', 'warning');
  const widgets = $$('#workspaceGrid .widget').map((node, i) => ({id:node.dataset.widgetId,type:node.dataset.widgetType,position:{x:i%12,y:Math.floor(i/3)*3},size:{w:Number((node.style.gridColumn.match(/\d+/) || [4])[0]),h:3},settings:{},visibility:!node.hidden}));
  try { await api.updateWorkspace(current.id, {...current, widgets, updatedAt:Date.now()}); $('#customizeBanner').hidden = true; notify('Workspace saved', `${widgets.length} widget states persisted.`, 'good'); }
  catch (e) { notify('Workspace save failed', errorText(e), 'warning'); }
}

async function refreshAll() {
  const calls = [api.capabilities(),api.system(),api.machines(),api.models(),api.profiles(),api.jobs(),api.telemetry(),api.logs(),api.requests(),api.gateway()];
  const keys = ['capabilities','system','machines','models','profiles','jobs','telemetry','logs','requests','gateway'];
  const results = await Promise.allSettled(calls);
  results.forEach((r, i) => { if (r.status === 'fulfilled') state[keys[i]] = r.value; else notify(`${keys[i]} unavailable`, errorText(r.reason), 'warning'); });
  renderHeader(); renderRuntime(); renderMachines(); renderModels(); renderTelemetry(); renderRequests(); renderLogs(); renderProfiles(); renderGateway(); renderJobs();
}

function wire() {
  $$('.nav-item[data-page]').forEach(b => b.addEventListener('click', () => {
    $$('.nav-item[data-page]').forEach(x => x.classList.toggle('active', x === b));
    $$('.page[data-page-view]').forEach(p => p.classList.toggle('active', p.dataset.pageView === b.dataset.page));
    if (b.dataset.page === 'extensions') loadExtensions();
  }));
  $('#mobileNavToggle').addEventListener('click', () => $('#navigation').classList.toggle('open'));
  $$('.add-machine-trigger').forEach(b => b.addEventListener('click', () => $('#machineDialog').showModal()));
  $$('.dialog-close').forEach(b => b.addEventListener('click', () => b.closest('dialog').close()));
  $('#machineForm').addEventListener('submit', createMachine);
  $('#scanModelsBtn').addEventListener('click', scanModels);
  $('#scanModelsQuick').addEventListener('click', scanModels);
  $('#stopAllBtn').addEventListener('click', stopRuntime);
  $('#launchPreflightBtn').addEventListener('click', preflightAndLaunch);
  $('#jobsBtn').addEventListener('click', () => $('#jobDrawer').hidden = !$('#jobDrawer').hidden);
  $('#closeJobsBtn').addEventListener('click', () => $('#jobDrawer').hidden = true);
  $('#addActionBtn').addEventListener('click', () => $('#actionDialog').showModal());
  $('#addQuickActionBtn').addEventListener('click', () => $('#actionDialog').showModal());
  $('#actionForm').addEventListener('submit', createAction);
  $('#addEndpointBtn').addEventListener('click', () => $('#endpointDialog').showModal());
  $('#endpointForm').addEventListener('submit', createEndpoint);
  $('#refreshExtensionsBtn').addEventListener('click', loadExtensions);
  $('#importExtensionBtn').addEventListener('click', () => $('#extensionFileInput').click());
  $('#extensionFileInput').addEventListener('change', async e => {
    const file = e.target.files?.[0]; if (!file) return;
    try { const manifest = JSON.parse(await file.text()); await api.createExtension(manifest); notify('Extension installed', manifest.name || manifest.id, 'good'); await loadExtensions(); }
    catch (err) { notify('Extension rejected', errorText(err), 'warning'); }
    e.target.value = '';
  });
  $('#customizeBtn').addEventListener('click', () => $('#customizeBanner').hidden = false);
  $('#doneCustomizeBtn').addEventListener('click', saveWorkspace);
  $('#workspaceSelect').addEventListener('change', () => {
    const item = state.workspaces?.items?.find(w => w.id === $('#workspaceSelect').value);
    applyWorkspace(item);
  });
  $('#addWidgetBtn').addEventListener('click', () => notify('Widget registry', 'Use workspace configuration after renderer support is added.', 'neutral'));
}

async function boot() {
  wire();
  await Promise.all([refreshAll(), loadWorkspaces(), loadExtensions()]);
  state.timer = setInterval(() => refreshAll().catch(e => notify('Refresh failed', errorText(e), 'warning')), 5000);
}
window.addEventListener('beforeunload', () => { if (state.timer) clearInterval(state.timer); });
boot().catch(e => notify('UI startup failed', errorText(e), 'warning'));
