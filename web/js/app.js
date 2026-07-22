import {api, ApiError} from './api.js';
import {configLoader} from './config-loader.js';
import {persistentState} from './persistent-state.js';
import {menuLedger} from './menu-ledger.js';
import {icon} from './icons.js';

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
const $$$ = $$; // backward compatibility alias
const esc = value => String(value ?? '').replace(/[&<>'"]/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','\'':'&#39;','"':'&quot;'}[char]));
const state = {system:null, settings:null, capabilities:null, machines:[], machineActions:[], models:[], profiles:[], jobs:[], telemetry:null, logs:[], logLevel:'all', logSearch:'', gateway:null, gatewayHealth:{openai:null,ollama:null}, timer:null, chatAbort:null};

const PAGES = [
  {id:'chat', label:'Chat', icon:'icon-chat', showCount:false},
  {id:'setup', label:'Setup', icon:'icon-setup', showCount:false},
  {id:'models', label:'Models', icon:'icon-models', showCount:true, countId:'modelCount'},
  {id:'runtime', label:'Runtime', icon:'icon-runtime', showCount:false},
  {id:'machines', label:'Machines', icon:'icon-machines', showCount:true, countId:'machineCount'},
  {id:'gateways', label:'Gateways', icon:'icon-gateways', showCount:false},
  {id:'telemetry', label:'Telemetry', icon:'icon-telemetry', showCount:false},
  {id:'profiles', label:'Profiles', icon:'icon-profiles', showCount:false},
  {id:'extensions', label:'Extensions', icon:'icon-extensions', showCount:true, countId:'extensionCount'},
  {id:'logs', label:'Logs', icon:'icon-logs', showCount:false},
    {id:'settings', label:'Settings', icon:'icon-settings', showCount:false},
];

const PAGE_CONTENT = {
  chat: { title: 'Playground', subtitle: 'Test your model', description: 'Select a model, start the runtime, and send a real inference request.', render: renderChatAvailability },
  setup: { title: 'Get Started', subtitle: 'Setup', description: 'Complete the steps required to run your first model.', render: renderSetup },
  models: { title: 'Library', subtitle: 'Models', description: 'Manage model folders and discovered GGUF files.', render: renderModels },
  runtime: { title: 'Process', subtitle: 'Runtime', description: 'Launch, stop, and inspect the active llama.cpp server.', render: renderRuntime },
  machines: { title: 'Cluster', subtitle: 'Machines', description: 'Edit host and worker connectivity.', render: renderMachines },
  gateways: { title: 'Endpoints', subtitle: 'Gateways', description: 'Copy, test, and configure client endpoints.', render: renderGateways },
  telemetry: { title: 'Performance', subtitle: 'Telemetry', description: 'GPU, memory, runtime, and request metrics.', render: renderTelemetry },
  profiles: { title: 'Configuration', subtitle: 'Profiles', description: 'Reusable llama.cpp launch configurations.', render: renderProfiles },
  extensions: { title: 'Declarative Control', subtitle: 'Extensions', description: 'Manage permission-bound manifests, operational actions, and registered HTTP endpoints.', render: () => {} },
  logs: { title: 'Troubleshooting', subtitle: 'Logs', description: 'Detailed runtime and control-plane activity.', render: renderLogs },
  settings: { title: 'System', subtitle: 'Settings', description: 'Configure paths, ports, binding, polling, and safety controls.', render: () => {} },
};

function renderPage(pageId) {
  const content = PAGE_CONTENT[pageId];
  if (!content) { console.warn('Page content not configured:', pageId); return; }
  if (typeof content.render === 'function') { content.render(); }
}
function errorText(error) {
  return error instanceof ApiError ? `${error.code}: ${error.message}` : (error?.message || String(error));
}
function notify(title, message = '', level = 'neutral') {
  const item = document.createElement('div');
  item.className = `toast ${level}`;
  item.innerHTML = `<strong>${esc(title)}</strong><span>${esc(message)}</span>`;
  $('#toastRegion')?.append(item);
  setTimeout(() => item.remove(), 4500);
}
function badge(text, level = 'neutral') { return `<span class="status-badge ${level}">${esc(text)}</span>`; }
function bytes(value) {
  let number = Number(value);
  if (!Number.isFinite(number) || number < 0) return 'Unknown';
  const units = ['B','KB','MB','GB','TB']; let index = 0;
  while (number >= 1024 && index < units.length - 1) { number /= 1024; index += 1; }
  return `${index === 0 || number >= 10 ? number.toFixed(0) : number.toFixed(1)} ${units[index]}`;
}
function settingsValue() { return state.settings?.settings || state.settings || {}; }
function runtime() { return state.system?.runtime || {}; }
function processState() { return runtime().process || {}; }
function isRunning() { return processState().running === true || ['ready','running'].includes(String(runtime().state || '').toLowerCase()); }
function activeModel() { return state.models.find(model => model.id === runtime().activeModelId); }
function formatTime(value) {
  const date = new Date(Number(value));
  return Number.isNaN(date.getTime()) ? 'Unknown' : date.toLocaleString();
}
function renderNavigation() {
  const nav = $('#navigation nav');
  if (!nav) return;
  nav.innerHTML = PAGES.map(page => `<button class="nav-item${page.id === (persistentState.get('activePage') || 'chat') ? ' active' : ''}" data-page="${page.id}" type="button"><svg class="nav-glyph icon" aria-hidden="true"><use href="assets/icons.svg#${page.icon}"/></svg><span>${esc(page.label)}</span>${page.showCount ? `<span class="nav-count" id="${page.countId}">0</span>` : ''}</button>`).join('');
}
function gatewayUrls() {
  const controlPlane = state.gateway?.controlPlane || {host:'127.0.0.1',port:8088};
  const host = controlPlane.host || '127.0.0.1';
  const port = controlPlane.port || 8088;
  const base = `http://${host}:${port}`;
  return {
    dashboard: base,
    openai: `${base}/v1`,
    ollama: base,
  };
}
function navigate(page) {
  $$(".nav-item[data-page]").forEach(item => item.classList.toggle('active', item.dataset.page === page));
  $$(".page[data-page-view]").forEach(view => view.classList.toggle('active', view.dataset.pageView === page));
  $('#navigation')?.classList.remove('open');
  persistentState.set('activePage', page);
  renderPage(page);
}

function renderHeader() {
  const urls = gatewayUrls();
  const online = state.machines.filter(machine => ['online','reachable'].includes(machine.status)).length;
  $('#runtimeHealth').className = `health-pill ${isRunning() ? 'good' : 'neutral'}`;
  $('#runtimeHealth').textContent = isRunning() ? `Runtime: ${activeModel()?.name || activeModel()?.filename || runtime().activeModelId || 'running'}` : 'Runtime stopped';
  const openaiHealthy = state.gatewayHealth.openai === true;
  $('#gatewayHealth').className = `health-pill ${openaiHealthy ? 'good' : 'neutral'}`;
  $('#gatewayHealth').textContent = openaiHealthy ? `API healthy: ${urls.openai}` : 'API health unverified';
  $('#machineHealth').className = `health-pill ${online ? 'good' : 'neutral'}`;
  $('#machineHealth').textContent = `${online}/${state.machines.length} machines online`;
  $('#modelCount').textContent = state.models.length;
  $('#machineCount').textContent = state.machines.length;
  $('#systemDot').className = 'status-dot good';
  $('#systemLabel').textContent = isRunning() ? 'Ready for inference' : (state.models.length ? 'Model ready to start' : 'Setup required');
  $('#dashboardAddress').textContent = urls.dashboard;
}

function fillSelectors() {
  const modelOptions = state.models.length ? state.models.map(model => `<option value="${esc(model.id)}">${esc(model.name || model.filename || model.id)}</option>`).join('') : '<option value="">No models registered</option>';
  const profileOptions = `<option value="">No profile</option>${state.profiles.map(profile => `<option value="${esc(profile.id)}">${esc(profile.name || profile.id)}</option>`).join('')}`;
  const previousModel = $('#chatModel').value;
  $('#chatModel').innerHTML = modelOptions;
  if (previousModel && state.models.some(model => model.id === previousModel)) $('#chatModel').value = previousModel;
  else if (runtime().activeModelId) $('#chatModel').value = runtime().activeModelId;
  $('#chatProfile').innerHTML = profileOptions;
  updateChatEndpoint();
}
function updateChatEndpoint() {
  const urls = gatewayUrls();
  const type = $('#chatGateway').value;
  $('#chatEndpoint').textContent = type === 'ollama' ? urls.ollama : urls.openai;
}
function renderChatAvailability() {
  const missing = [];
  if (!state.models.length) missing.push('Add a model folder or GGUF file.');
  if (!state.profiles.length) missing.push('A profile is optional, but recommended for repeatable launch settings.');
  if (!isRunning()) missing.push('Start the selected model before sending a prompt.');
  const notice = $('#chatSetupNotice');
  notice.hidden = missing.length === 0;
  notice.innerHTML = missing.length ? `<strong>${state.models.length ? 'Runtime not ready' : 'No model configured'}</strong><p>${missing.join(' ')}</p><div><button class="button primary" data-open-page="${state.models.length ? 'runtime' : 'models'}" type="button">${state.models.length ? 'Open runtime controls' : 'Add model source'}</button></div>` : '';
  notice.querySelector('[data-open-page]')?.addEventListener('click', event => navigate(event.currentTarget.dataset.openPage));
  $('#sendChat').disabled = !isRunning();
}

function renderSetup() {
  const settings = settingsValue();
  const sources = settings.paths?.modelSources || settings.modelSources || [];
  const steps = [
    {done:sources.length > 0, title:'Add model source', detail:sources.length ? sources.join(', ') : 'Choose a folder containing GGUF files.', action:'models', label:'Manage sources'},
    {done:state.models.length > 0, title:'Scan and select model', detail:state.models.length ? `${state.models.length} model(s) registered.` : 'Run a scan after adding a folder.', action:'models', label:'Open models'},
    {done:state.profiles.length > 0, optional:true, title:'Create launch profile', detail:state.profiles.length ? `${state.profiles.length} profile(s) available.` : 'Store context, GPU, batch, and thread settings.', action:'profiles', label:'Open profiles'},
    {done:isRunning(), title:'Start runtime', detail:isRunning() ? `${activeModel()?.name || runtime().activeModelId} is running.` : 'Run preflight and launch llama-server.', action:'runtime', label:'Open runtime'},
    {done:false, optional:true, title:'Send test prompt', detail:'Use Chat to verify a real response and inspect latency.', action:'chat', label:'Open chat'},
  ];
  $('#setupGrid').innerHTML = steps.map((step, index) => `<article class="content-card setup-step ${step.done ? 'complete' : ''}"><span class="step-number">${step.done ? icon('check') : index + 1}</span><div><h2>${esc(step.title)}${step.optional ? ' <small>Optional</small>' : ''}</h2><p>${esc(step.detail)}</p></div><button class="button secondary" data-open-page="${step.action}" type="button">${esc(step.label)}</button></article>`).join('');
  $$('#setupGrid [data-open-page]').forEach(button => button.addEventListener('click', () => navigate(button.dataset.openPage)));
}

function renderModelSources() {
  const settings = settingsValue();
  const sources = settings.paths?.modelSources || settings.modelSources || [];
  $('#modelSources').innerHTML = sources.length ? sources.map((source, index) => `<div class="source-row"><code>${esc(typeof source === 'string' ? source : source.path)}</code><button class="button compact secondary scan-source" data-index="${index}" type="button">Scan</button><button class="button compact danger-soft remove-source" data-index="${index}" type="button">Remove</button></div>`).join('') : '<div class="empty-state"><p>No model folders configured.</p></div>';
  $$('.scan-source').forEach(button => button.addEventListener('click', () => scanModels({sources:[sources[Number(button.dataset.index)]]})));
  $$('.remove-source').forEach(button => button.addEventListener('click', () => removeModelSource(Number(button.dataset.index))));
}
function renderModels() {
  $('#modelsTableBody').innerHTML = state.models.length ? state.models.map(model => {
    const meta = model.metadata || model.gguf || {};
    return `<tr><td><strong>${esc(model.name || model.filename || model.id)}</strong><small>${esc(model.path || '')}</small></td><td>${esc(model.architecture || meta.architecture || 'Unknown')}</td><td>${esc(model.quantization || meta.fileType || 'Unknown')}</td><td>${bytes(model.sizeBytes ?? model.size)}</td><td>${esc(model.contextLength || meta.contextLength || 'Unknown')}</td><td><button class="button compact primary use-model" data-id="${esc(model.id)}" type="button">Chat</button><button class="button compact secondary launch-model" data-id="${esc(model.id)}" type="button">Launch</button></td></tr>`;
  }).join('') : '<tr><td colspan="6"><div class="empty-state"><h3>No models registered</h3><p>Add a model folder above, then scan for GGUF files.</p></div></td></tr>';
                  $('.use-model').forEach(button => button.addEventListener('click', () => { $('#chatModel').value = button.dataset.id; navigate('chat'); }));
  $('.launch-model').forEach(button => button.addEventListener('click', () => quickLaunch(button.dataset.id)));
}

function renderRuntime() {
  const current = runtime(); const process = processState(); const model = activeModel(); const urls = gatewayUrls();
  $('#runtimePanel').innerHTML = `<div class="runtime-summary"><div><span>Status</span><strong>${esc(current.state || (process.running ? 'running' : 'stopped'))}</strong></div><div><span>Model</span><strong>${esc(model?.name || model?.filename || current.activeModelId || 'None')}</strong></div><div><span>PID</span><strong>${esc(process.pid || 'Not running')}</strong></div><div><span>OpenAI endpoint</span><code>${esc(urls.openai)}</code></div></div><div class="runtime-actions"><button class="button primary" id="runtimeLaunchBtn" type="button">Launch model</button><button class="button danger-soft" id="runtimeStopBtn" type="button">Stop runtime</button></div>`;
          $('#runtimeLaunchBtn').addEventListener('click', () => quickLaunch());
  $('#runtimeStopBtn').addEventListener('click', stopRuntime);
}

function renderMachines() {
  const visibleActions = machine => state.machineActions.filter(action => (machine.actions || []).includes(action.id) && (action.when === 'always' || (action.when === 'enabled' && machine.enabled !== false) || (action.when === 'disabled' && machine.enabled === false) || (action.when === 'rpc-enabled' && machine.enabled !== false && machine.rpc?.enabled === true)));
  $('#machineGrid').innerHTML = state.machines.length ? state.machines.map(machine => {
    const machineStatus = machine.enabled === false ? 'disconnected' : (machine.status || 'unknown');
    const isOnline = ['online','reachable'].includes(machineStatus);
    const actionButtons = visibleActions(machine).map(action => `<button class="button compact ${esc(action.style || 'secondary')} machine-action" data-id="${esc(machine.id)}" data-operation="${esc(action.operation)}" data-enabled="${esc(action.enabled)}" type="button">${esc(action.label)}</button>`).join('');
    const machineId = esc(machine.id);
    return `<article class="content-card machine-card"><div class="section-head"><div><h3>${esc(machine.name || machine.id)}</h3><code>${esc(machine.addresses?.[0] || 'Unknown')}</code></div>${badge(machineStatus, isOnline ? 'good' : 'neutral')}</div><dl class="machine-details"><div><dt>Controller</dt><dd>${esc(machine.controller?.scheme || 'http')} :${esc(machine.controller?.port || 'unknown')}</dd></div><div><dt>RPC</dt><dd>:${esc(machine.rpc?.port || 'unknown')}</dd></div><div><dt>Role</dt><dd>${esc((machine.tags || []).join(', ') || 'Unassigned')}</dd></div></dl><div class="runtime-actions"><button class="button compact ${isOnline ? 'danger-soft' : 'secondary'} machine-stop" data-id="${machineId}" type="button" ${isOnline ? '' : 'disabled'}>Stop</button><button class="button compact ${isOnline ? 'secondary' : 'primary'} machine-start" data-id="${machineId}" type="button" ${isOnline ? 'disabled' : ''}>Start</button>${actionButtons}</div></article>`;
  }).join('') : '<div class="empty-state"><h3>No machines registered</h3><p>Add a host or RPC worker.</p></div>';
            $('.machine-action').forEach(button => button.addEventListener('click', () => runMachineAction(button.dataset.id, button.dataset.operation, button.dataset.enabled)));
  $('.machine-start').forEach(button => button.addEventListener('click', () => startMachine(button.dataset.id)));
  $('.machine-stop').forEach(button => button.addEventListener('click', () => stopMachine(button.dataset.id)));
}

async function startMachine(machineId) {
  try {
    const job = await api.startRpc(machineId);
    notify('Machine RPC start requested', job.id, 'neutral');
    await pollJob(job.id);
    await refreshAll();
  } catch (error) { notify('Machine start failed', errorText(error), 'warning'); }
}

async function stopMachine(machineId) {
  if (!confirm('Stop this machine?')) return;
  try {
    const job = await api.stopRpc(machineId);
    notify('Machine RPC stop requested', job.id, 'neutral');
    await pollJob(job.id);
    await refreshAll();
  } catch (error) { notify('Machine stop failed', errorText(error), 'warning'); }
}

function renderGateways() {
  const urls = gatewayUrls();
  const settings = settingsValue();
  const cards = [
    {name:'Control plane', url:urls.dashboard, type:'dashboard', healthy:state.gateway !== null, detail:'Applied listener: 127.0.0.1:8088. Remote control is unsupported.'},
    {name:'OpenAI compatible', url:urls.openai, type:'openai', healthy:state.gatewayHealth.openai, detail:`Saved port ${settings.ports?.openaiGateway || 1234} is not applied. This route shares the control-plane listener.`},
    {name:'Ollama compatible', url:urls.ollama, type:'ollama', healthy:state.gatewayHealth.ollama, detail:`Saved port ${settings.ports?.ollamaGateway || 11434} is not applied. This route shares the control-plane listener.`},
  ];
  $('#gatewayGrid').innerHTML = cards.map(card => { const status = card.healthy === true ? 'Available' : card.healthy === false ? 'Unavailable' : 'Health unverified'; return `<article class="content-card endpoint-card"><div class="section-head"><div><h2>${esc(card.name)}</h2><code>${esc(card.url)}</code></div>${badge(status, card.healthy === true ? 'good' : 'neutral')}</div><div class="runtime-actions"><button class="button compact secondary copy-endpoint" data-url="${esc(card.url)}" type="button" ${card.healthy === true ? '' : 'disabled'}>Copy URL</button><button class="button compact secondary test-gateway" data-type="${card.type}" type="button">Test health</button></div><p>${esc(card.detail)}</p></article>`; }).join('');
  $$('.copy-endpoint').forEach(button => button.addEventListener('click', () => copyText(button.dataset.url)));
  $$('.test-gateway').forEach(button => button.addEventListener('click', () => testGateway(button.dataset.type)));
}

function renderTelemetry() {
  const telemetry = state.telemetry || {}; const local = telemetry.local || {}; const memory = local.memory || {}; const gpus = Array.isArray(local.gpus) ? local.gpus : (Array.isArray(local.nvidia) ? local.nvidia : []);
  const gpuCards = gpus.map(gpu => {
    const used = gpu.memoryUsedBytes ?? gpu.memoryUsed; const total = gpu.memoryTotalBytes ?? gpu.memoryTotal; const utilization = gpu.utilizationPercent ?? gpu.utilizationGpu ?? gpu.utilization;
    const percent = Number(total) > 0 ? Math.round(Number(used || 0) / Number(total) * 100) : null;
    return `<article class="content-card gpu-card"><div class="section-head"><div><h2>${esc(gpu.name || `GPU ${gpu.index ?? ''}`)}</h2><code>${esc(gpu.uuid || gpu.driverVersion || '')}</code></div>${badge(utilization == null ? 'No utilization data' : `${utilization}% load`, utilization > 80 ? 'warning' : 'good')}</div><div class="telemetry-grid"><div><span>VRAM</span><strong>${bytes(used)} / ${bytes(total)}</strong><meter min="0" max="100" value="${percent ?? 0}"></meter></div><div><span>Free VRAM</span><strong>${bytes(gpu.memoryFreeBytes ?? gpu.memoryFree)}</strong></div><div><span>Temperature</span><strong>${gpu.temperatureC == null ? 'Unknown' : `${gpu.temperatureC} °C`}</strong></div><div><span>Power</span><strong>${gpu.powerWatts == null ? 'Unknown' : `${gpu.powerWatts} W`}</strong></div><div><span>Driver</span><strong>${esc(gpu.driverVersion || 'Unknown')}</strong></div><div><span>Utilization</span><strong>${utilization == null ? 'Unknown' : `${utilization}%`}</strong></div></div></article>`;
  }).join('');
  $('#telemetryPage').innerHTML = `<div class="telemetry-summary"><div class="content-card"><span>Updated</span><strong>${formatTime(telemetry.timestamp)}</strong></div><div class="content-card"><span>System memory</span><strong>${bytes(memory.usedBytes ?? memory.used)} / ${bytes(memory.totalBytes ?? memory.total)}</strong></div><div class="content-card"><span>CPU threads</span><strong>${esc(local.cpuCount ?? local.logicalCpuCount ?? 'Unknown')}</strong></div><div class="content-card"><span>Active requests</span><strong>${esc(state.gateway?.requests?.active?.length ?? state.gateway?.requests?.activeCount ?? 0)}</strong></div></div><div class="gpu-grid">${gpuCards || '<div class="empty-state"><p>No GPU telemetry returned.</p></div>'}</div>`;
}

function renderProfiles() {
  $('#profileGrid').innerHTML = state.profiles.length ? state.profiles.map(profile => { const values = profile.values || profile.config || {}; return `<article class="content-card profile-card"><div class="section-head"><div><h2>${esc(profile.name || profile.id)}</h2><code>${esc(profile.id)}</code></div>${badge(profile.validationState || 'saved')}</div><p>${esc(profile.description || 'No description')}</p><div class="profile-values"><span>Context <b>${esc(values.contextSize || 'default')}</b></span><span>GPU layers <b>${esc(values.gpuLayers ?? 'default')}</b></span><span>Batch <b>${esc(values.batchSize || 'default')}</b></span><span>Threads <b>${esc(values.threads || 'default')}</b></span></div><div class="runtime-actions"><button class="button compact primary profile-chat" data-id="${esc(profile.id)}" type="button">Use in chat</button><button class="button compact secondary profile-edit" data-id="${esc(profile.id)}" type="button">Edit</button><button class="button compact secondary profile-duplicate" data-id="${esc(profile.id)}" type="button">Duplicate</button><button class="button compact danger-soft profile-delete" data-id="${esc(profile.id)}" type="button">Delete</button></div></article>`; }).join('') : '<div class="empty-state"><h3>No profiles registered</h3><p>Create a reusable launch configuration.</p></div>';
  $$('.profile-chat').forEach(button => button.addEventListener('click', () => { $('#chatProfile').value = button.dataset.id; navigate('chat'); }));
  $$('.profile-edit').forEach(button => button.addEventListener('click', () => openProfile(state.profiles.find(profile => profile.id === button.dataset.id))));
  $$('.profile-duplicate').forEach(button => button.addEventListener('click', () => openProfile(state.profiles.find(profile => profile.id === button.dataset.id), true)));
  $$('.profile-delete').forEach(button => button.addEventListener('click', () => deleteProfile(button.dataset.id)));
}
function renderLogs() {
  const logs = Array.isArray(state.logs) ? state.logs : (state.logs?.items || state.logs?.logs || []);
  const visible = filteredLogs(logs);
  $('#logResultCount').textContent = `${visible.length} of ${logs.length} records`;
  $('#logLevelFilter').value = state.logLevel;
  $('#logSearch').value = state.logSearch;
  $('#logOutput').textContent = visible.length ? visible.map(log => `[${formatTime(log.timestamp || log.at)}] ${String(log.severity || log.level || 'info').toUpperCase()} ${log.source || log.category || 'system'} ${log.message || ''}`).join('\n') : 'No matching logs.';
}
function filteredLogs(logs) {
  const search = state.logSearch.trim().toLowerCase();
  return logs.filter(log => {
    const level = String(log.severity || log.level || 'info').toLowerCase();
    return (state.logLevel === 'all' || level === state.logLevel) && (!search || JSON.stringify(log).toLowerCase().includes(search));
  });
}
function exportLogs() {
  const logs = Array.isArray(state.logs) ? state.logs : (state.logs?.items || state.logs?.logs || []);
  const blob = new Blob([JSON.stringify(filteredLogs(logs), null, 2)], {type:'application/json'});
  const url = URL.createObjectURL(blob); const link = document.createElement('a');
  link.href = url; link.download = 'letterblack-visible-logs.json'; link.click(); URL.revokeObjectURL(url);
}
function renderJobs() {
  const active = state.jobs.filter(job => !['completed','succeeded','failed','cancelled','done'].includes(String(job.state || '').toLowerCase()));
  $('#jobCount').textContent = active.length;
  $('#jobList').innerHTML = state.jobs.length ? state.jobs.slice(0, 30).map(job => `<div class="job-item"><strong>${esc(job.type || job.id)}</strong><small>${esc(job.phase || job.state || 'unknown')}</small><div class="ux-progress"><span style="width:${Math.max(0, Math.min(100, Number(job.progress || 0)))}%"></span></div></div>`).join('') : '<div class="empty-state"><p>No jobs.</p></div>';
}
function renderAll() { renderHeader(); fillSelectors(); renderChatAvailability(); renderSetup(); renderModelSources(); renderModels(); renderRuntime(); renderMachines(); renderGateways(); renderTelemetry(); renderProfiles(); renderLogs(); renderJobs(); }

async function refreshAll() {
  const calls = [api.capabilities(), api.system(), api.settings(), api.machines(), api.machineActions(), api.models(), api.profiles(), api.jobs(), api.telemetry(), api.logs(), api.gateway()];
  const keys = ['capabilities','system','settings','machines','machineActions','models','profiles','jobs','telemetry','logs','gateway'];
  const results = await Promise.allSettled(calls);
  results.forEach((result, index) => { if (result.status === 'fulfilled') state[keys[index]] = result.value; else console.warn(`${keys[index]} unavailable`, result.reason); });
  if (!Array.isArray(state.machineActions)) state.machineActions = [];
  await refreshGatewayHealth();
  renderAll();
}
async function refreshGatewayHealth() {
  const urls = gatewayUrls();
  const checks = {openai:`${urls.openai}/models`,ollama:`${urls.ollama}/api/tags`};
  const results = await Promise.allSettled(Object.values(checks).map(url => fetch(url, {method:'GET',cache:'no-store'})));
  Object.keys(checks).forEach((type, index) => { state.gatewayHealth[type] = results[index].status === 'fulfilled' && results[index].value.ok; });
}
async function pollJob(id, timeout = 120000) {
  const started = Date.now();
  while (Date.now() - started < timeout) {
    const job = await api.job(id);
    state.jobs = await api.jobs(); renderJobs();
    if (['completed','succeeded','failed','cancelled','done'].includes(String(job.state || '').toLowerCase())) {
      if (['failed','cancelled'].includes(String(job.state).toLowerCase())) throw new Error(job.error?.message || `Job ${job.state}`);
      return job;
    }
    await new Promise(resolve => setTimeout(resolve, 800));
  }
  throw new Error(`Timed out waiting for ${id}`);
}
async function scanModels(payload = {}) {
  try { const job = await api.scanModels(payload); notify('Model scan started', job.id); await pollJob(job.id); await refreshAll(); }
  catch (error) { notify('Model scan failed', errorText(error), 'warning'); }
}
async function addModelSource(event) {
  event.preventDefault();
  const path = $('#modelSourcePath').value.trim(); if (!path) return;
  const current = settingsValue(); const existing = current.paths?.modelSources || current.modelSources || [];
  const next = [...existing, path].filter((item, index, all) => all.indexOf(item) === index);
  const payload = structuredClone(current); payload.paths = {...(payload.paths || {}), modelSources:next};
  try { await api.updateSettings(payload); $('#modelSourcePath').value = ''; notify('Model folder added', path, 'good'); await refreshAll(); await scanModels({modelSources:[path]}); }
  catch (error) { notify('Could not add model folder', errorText(error), 'warning'); }
}
async function removeModelSource(index) {
  const current = settingsValue(); const existing = current.paths?.modelSources || current.modelSources || [];
  const payload = structuredClone(current); payload.paths = {...(payload.paths || {}), modelSources:existing.filter((_, itemIndex) => itemIndex !== index)};
  try { await api.updateSettings(payload); await refreshAll(); }
  catch (error) { notify('Could not remove model folder', errorText(error), 'warning'); }
}
async function quickLaunch(modelId, profileId) {
  if (!modelId) return notify('No model selected', 'Choose a model first.', 'warning');
  try {
    notify('Launching model...', '', 'neutral');
    const preflight = await api.preflight({modelId, profileId});
    if (!preflight.launchAllowed) return notify('Launch blocked', 'Preflight did not approve this configuration.', 'warning');
    const job = await api.launch({modelId, profileId});
    notify('Runtime launch started', job.id, 'good');
    await pollJob(job.id);
    await refreshAll();
    navigate('chat');
  } catch (error) {
    notify('Runtime launch failed', errorText(error), 'warning');
  }
}
function openLaunch(modelId = '') {
  if (!state.models.length) { navigate('models'); return notify('No models registered', 'Add a model source first.', 'warning'); }
  $('#launchPanel').innerHTML = `<div class="form-grid"><label>Model<select id="launchModelSelect">${state.models.map(model => `<option value="${esc(model.id)}" ${model.id === modelId ? 'selected' : ''}>${esc(model.name || model.filename || model.id)}</option>`).join('')}</select></label><label>Profile<select id="launchProfileSelect"><option value="">No profile</option>${state.profiles.map(profile => `<option value="${esc(profile.id)}">${esc(profile.name || profile.id)}</option>`).join('')}</select></label><div id="preflightResult">Preflight has not run.</div></div>`;
  $('#launchDialog').showModal();
}
async function preflightAndLaunch() {
  const modelId = $('#launchModelSelect').value; const profileId = $('#launchProfileSelect').value || undefined;
  try {
    const preflight = await api.preflight({modelId, profileId});
    $('#preflightResult').textContent = `Allocation risk: ${preflight.allocation?.risk || 'unknown'} · Allowed: ${Boolean(preflight.launchAllowed)}`;
    if (!preflight.launchAllowed) return notify('Launch blocked', 'Preflight did not approve this configuration.', 'warning');
    const job = await api.launch({modelId, profileId}); $('#launchDialog').close(); notify('Runtime launch started', job.id); await pollJob(job.id); await refreshAll(); navigate('chat');
  } catch (error) { notify('Runtime launch failed', errorText(error), 'warning'); }
}
async function shutdownWorkspace() {
  if (!confirm('Stop the host runtime and every enabled worker? The dashboard will close after all stops are verified.')) return;
  try {
    const job = await api.stop({force:false, shutdownControlServer:true});
    await pollJob(job.id);
    if (state.timer) clearInterval(state.timer);
    notify('Workspace shutdown scheduled', 'All requested runtime targets stopped. The dashboard is closing.', 'warning');
  } catch (error) { notify('Workspace shutdown failed', errorText(error), 'warning'); }
}
async function stopRuntime() {
  if (!isRunning()) return notify('Runtime already stopped');
  if (!confirm('Stop the active runtime?')) return;
  try { const job = await api.stop({force:false}); await pollJob(job.id); await refreshAll(); }
  catch (error) { notify('Runtime stop failed', errorText(error), 'warning'); }
}

function openMachine(machine = null) {
  const form = $('#machineForm'); form.reset(); form.elements.enabled.checked = machine?.enabled !== false; form.elements.rpcEnabled.checked = machine?.rpc?.enabled === true;
  $('#machineDialogTitle').textContent = machine ? 'Edit machine' : 'Add machine';
  const selectedActions = new Set(machine?.actions || state.machineActions.map(action => action.id));
  $('#machineActionOptions').innerHTML = state.machineActions.map(action => `<label><input type="checkbox" name="machineAction" value="${esc(action.id)}" ${selectedActions.has(action.id) ? 'checked' : ''}> ${esc(action.label)}</label>`).join('');
  if (machine) {
    form.elements.id.value = machine.id; form.elements.name.value = machine.name || ''; form.elements.address.value = machine.addresses?.[0] || ''; form.elements.controllerPort.value = machine.controller?.port ?? ''; form.elements.rpcPort.value = machine.rpc?.port ?? ''; form.elements.controllerProtocol.value = machine.controller?.scheme || 'http'; form.elements.role.value = (machine.tags || []).join(', '); form.elements.runtimePath.value = machine.paths?.runtime || ''; form.elements.modelsPath.value = machine.paths?.models || '';
  }
  $('#machineDialog').showModal();
}
async function saveMachine(event) {
  event.preventDefault(); const form = event.currentTarget; const data = Object.fromEntries(new FormData(form));
  const generatedId = crypto.randomUUID?.().replace(/-/g, '').slice(0, 12) || `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 8)}`;
  const id = data.id || `machine-${String(data.name || data.address).toLowerCase().replace(/[^a-z0-9]+/g,'-')}-${generatedId}`;
  const actions = $$('[name="machineAction"]', form).filter(input => input.checked).map(input => input.value);
  const tags = String(data.role || '').split(',').map(tag => tag.trim()).filter(Boolean);
  const payload = {id,name:data.name,addresses:[data.address],controller:{scheme:data.controllerProtocol,port:Number(data.controllerPort)},rpc:{port:Number(data.rpcPort),enabled:form.elements.rpcEnabled.checked},paths:{runtime:data.runtimePath || '',models:data.modelsPath || ''},tags,actions,enabled:form.elements.enabled.checked};
  try { data.id ? await api.updateMachine(id, payload) : await api.createMachine(payload); $('#machineDialog').close(); notify('Machine saved', payload.name, 'good'); await refreshAll(); }
  catch (error) { notify('Machine save failed', errorText(error), 'warning'); }
}
async function deleteMachine(id) { if (!confirm(`Delete machine ${id}?`)) return; try { await api.deleteMachine(id); await refreshAll(); } catch (error) { notify('Delete failed', errorText(error), 'warning'); } }
async function testMachine(id) { try { const result = await api.testMachine(id); notify(result.reachable ? 'Machine reachable' : 'Machine unavailable', result.reachable ? `${result.latencyMs ?? 'Unknown'} ms` : result.error?.message || id, result.reachable ? 'good' : 'warning'); await refreshAll(); } catch (error) { notify('Machine test failed', errorText(error), 'warning'); } }
async function rpc(id, action) { try { const job = action === 'start' ? await api.startRpc(id) : await api.stopRpc(id); await pollJob(job.id); await refreshAll(); } catch (error) { notify(`RPC ${action} failed`, errorText(error), 'warning'); } }
async function setMachineEnabled(id, enabled) {
  const machine = state.machines.find(item => item.id === id);
  if (!machine) return notify('Machine unavailable', id, 'warning');
  const payload = structuredClone(machine); payload.enabled = enabled; payload.status = enabled ? 'unknown' : 'disconnected';
  try { await api.updateMachine(id, payload); notify(enabled ? 'Machine connected' : 'Machine disconnected', machine.name || id, 'good'); await refreshAll(); }
  catch (error) { notify('Machine update failed', errorText(error), 'warning'); }
}
async function runMachineAction(id, operation, enabledValue) {
  if (operation === 'test') return testMachine(id);
  if (operation === 'edit') return openMachine(state.machines.find(machine => machine.id === id));
  if (operation === 'rpc-start') return rpc(id, 'start');
  if (operation === 'rpc-stop') return rpc(id, 'stop');
  if (operation === 'set-enabled') return setMachineEnabled(id, enabledValue === 'true');
  if (operation === 'delete') return deleteMachine(id);
  notify('Unsupported machine action', operation, 'warning');
}

function openProfile(profile = null, duplicate = false) {
  const form = $('#profileForm'); form.reset(); form.dataset.mode = profile && !duplicate ? 'edit' : 'create'; form.dataset.originalId = profile?.id || ''; form.dataset.additionalValues = '{}';
  if (profile) {
    const values = profile.values || {}; const known = new Set(['contextSize','gpuLayers','batchSize','threads','parallel','flashAttention']);
    form.elements.id.value = duplicate ? `${profile.id}-copy`.slice(0, 64) : profile.id; form.elements.name.value = duplicate ? `Copy of ${profile.name || profile.id}` : profile.name || ''; form.elements.description.value = profile.description || '';
    for (const field of ['contextSize','gpuLayers','batchSize','threads','parallel']) form.elements[field].value = values[field] ?? form.elements[field].value;
    form.elements.flashAttention.checked = values.flashAttention === true; form.dataset.additionalValues = JSON.stringify(Object.fromEntries(Object.entries(values).filter(([key]) => !known.has(key))));
  }
  form.elements.id.disabled = Boolean(profile && !duplicate); $('#profileDialog h2').textContent = profile && !duplicate ? 'Edit launch profile' : duplicate ? 'Duplicate launch profile' : 'Create launch profile'; $('#profileDialog button[type="submit"]').textContent = profile && !duplicate ? 'Save profile' : duplicate ? 'Create duplicate' : 'Create profile'; $('#profileDialog').showModal();
}
async function saveProfile(event) {
  event.preventDefault(); const form = event.currentTarget; const data = Object.fromEntries(new FormData(form)); const additionalValues = JSON.parse(form.dataset.additionalValues || '{}');
  const payload = {id:form.dataset.originalId || data.id,name:data.name,description:data.description || '',values:{...additionalValues,contextSize:Number(data.contextSize),gpuLayers:Number(data.gpuLayers),batchSize:Number(data.batchSize),threads:Number(data.threads),parallel:Number(data.parallel),flashAttention:form.elements.flashAttention.checked}};
  const editing = form.dataset.mode === 'edit';
  try { editing ? await api.updateProfile(payload.id, payload) : await api.createProfile(payload); $('#profileDialog').close(); notify(editing ? 'Profile updated' : 'Profile created', payload.name, 'good'); await refreshAll(); }
  catch (error) { notify(editing ? 'Profile update failed' : 'Profile creation failed', errorText(error), 'warning'); }
}
async function deleteProfile(id) { if (!confirm(`Delete profile ${id}?`)) return; try { await api.deleteProfile(id); notify('Profile deleted', id, 'good'); await refreshAll(); } catch (error) { notify('Profile deletion failed', errorText(error), 'warning'); } }
async function testGateway(type) { await refreshGatewayHealth(); renderAll(); const healthy = state.gatewayHealth[type]; notify(healthy ? 'Gateway route healthy' : 'Gateway route unavailable', healthy ? `${type} route passed its exact health request.` : `${type} route did not pass health validation.`, healthy ? 'good' : 'warning'); }
async function copyText(value) { try { await navigator.clipboard.writeText(value); notify('Copied', value, 'good'); } catch { notify('Copy failed', value, 'warning'); } }

function appendMessage(role, content, id = '') {
  const messages = $('#chatMessages'); if ($('.empty-state', messages)) messages.innerHTML = '';
  const article = document.createElement('article'); article.className = `chat-message ${role}`; if (id) article.id = id; article.innerHTML = `<strong>${role === 'user' ? 'You' : 'Model'}</strong><div>${esc(content).replace(/\n/g,'<br>')}</div>`; messages.append(article); messages.scrollTop = messages.scrollHeight; return article;
}
function updateAssistantMessage(article, content) { article.querySelector('div').innerHTML = esc(content).replace(/\n/g,'<br>'); $('#chatMessages').scrollTop = $('#chatMessages').scrollHeight; }
async function sendChat(event) {
  event.preventDefault(); const prompt = $('#chatPrompt').value.trim(); if (!prompt || !isRunning()) return;
  appendMessage('user', prompt); $('#chatPrompt').value = ''; const assistant = appendMessage('assistant', '');
  const gateway = $('#chatGateway').value; const model = $('#chatModel').value || runtime().activeModelId; const started = performance.now(); state.chatAbort = new AbortController(); $('#cancelChat').disabled = false; $('#sendChat').disabled = true; $('#chatStatus').textContent = 'Sending'; $('#chatRequestId').textContent = 'Pending'; $('#chatRoute').textContent = gateway === 'ollama' ? '/api/chat' : '/v1/chat/completions'; $('#chatRaw').textContent = '';
  try {
    const response = gateway === 'ollama' ? await api.ollamaChat({model,messages:[{role:'user',content:prompt}],stream:$('#streamChat').checked}, state.chatAbort.signal) : await api.openAIChat({model,messages:[{role:'user',content:prompt}],stream:$('#streamChat').checked}, state.chatAbort.signal);
    const requestId = response.headers.get('x-request-id') || response.headers.get('request-id') || 'Not returned'; $('#chatRequestId').textContent = requestId;
    let output = ''; let raw = '';
    if ($('#streamChat').checked && response.body) {
      const reader = response.body.getReader(); const decoder = new TextDecoder(); let buffer = '';
      while (true) {
        const {done, value} = await reader.read(); if (done) break; buffer += decoder.decode(value, {stream:true});
        const lines = buffer.split('\n'); buffer = lines.pop() || '';
        for (const line of lines) {
          const clean = line.trim(); if (!clean || clean === 'data: [DONE]') continue; const text = clean.startsWith('data:') ? clean.slice(5).trim() : clean; raw += `${text}\n`;
          try { const item = JSON.parse(text); const token = gateway === 'ollama' ? (item.message?.content || item.response || '') : (item.choices?.[0]?.delta?.content || item.choices?.[0]?.message?.content || ''); output += token; updateAssistantMessage(assistant, output); } catch { /* retain raw line */ }
        }
      }
    } else {
      const payload = await response.json(); raw = JSON.stringify(payload, null, 2); output = gateway === 'ollama' ? (payload.message?.content || payload.response || '') : (payload.choices?.[0]?.message?.content || payload.choices?.[0]?.text || ''); updateAssistantMessage(assistant, output);
    }
    const elapsed = performance.now() - started; $('#chatLatency').textContent = `${Math.round(elapsed)} ms`; $('#chatStatus').textContent = 'Completed'; $('#chatRaw').textContent = raw || output; const estimatedTokens = output ? output.trim().split(/\s+/).length * 1.3 : 0; $('#chatTokensPerSecond').textContent = elapsed > 0 && estimatedTokens ? `${(estimatedTokens / (elapsed / 1000)).toFixed(1)} estimated` : 'Not reported';
  } catch (error) { updateAssistantMessage(assistant, `Request failed: ${errorText(error)}`); $('#chatStatus').textContent = error.name === 'AbortError' ? 'Cancelled' : 'Failed'; $('#chatRaw').textContent = errorText(error); }
  finally { state.chatAbort = null; $('#cancelChat').disabled = true; $('#sendChat').disabled = !isRunning(); }
}

  $$('.nav-item[data-page]').forEach(button => button.addEventListener('click', () => navigate(button.dataset.page)));
  $('.nav-item[data-page]').forEach(button => button.addEventListener('click', () => navigate(button.dataset.page)));
  $('#mobileNavToggle').addEventListener('click', () => $('#navigation').classList.toggle('open'));
  $$('.dialog-close').forEach(button => button.addEventListener('click', () => button.closest('dialog').close()));
  $('#jobsBtn').addEventListener('click', () => $('#jobDrawer').hidden = !$('#jobDrawer').hidden);
  $('#closeJobsBtn').addEventListener('click', () => $('#jobDrawer').hidden = true);
}
function rebindNav() {
  $$('#navigation nav .nav-item[data-page]').forEach(button => button.addEventListener('click', () => navigate(button.dataset.page)));
}

function wireWorkspaceHandlers() {
  $('#stopAllBtn').addEventListener('click', shutdownWorkspace);
}

function wireModelAndRuntimeHandlers() {
  $('#scanModelsBtn').addEventListener('click', () => scanModels({}));
  $('#modelSourceForm').addEventListener('submit', addModelSource);
  $('#startSelectedModel').addEventListener('click', () => quickLaunch($('#chatModel').value, $('#chatProfile').value || undefined));
  $('#launchPreflightBtn').addEventListener('click', preflightAndLaunch);
}

function wireMachineAndProfileHandlers() {
  $('#addMachineBtn').addEventListener('click', () => openMachine());
  $('#machineForm').addEventListener('submit', saveMachine);
  $('#createProfileBtn').addEventListener('click', () => openProfile());
  $('#profileForm').addEventListener('submit', saveProfile);
}

function wireChatHandlers() {
  $('#chatGateway').addEventListener('change', updateChatEndpoint);
  $('#copyChatEndpoint').addEventListener('click', () => copyText($('#chatEndpoint').textContent));
  $('#chatForm').addEventListener('submit', sendChat);
  $('#cancelChat').addEventListener('click', () => state.chatAbort?.abort());
}

function wireLogHandlers() {
  $('#logLevelFilter').addEventListener('change', event => { state.logLevel = event.currentTarget.value; renderLogs(); });
  $('#logSearch').addEventListener('input', event => { state.logSearch = event.currentTarget.value; renderLogs(); });
  $('#exportLogsBtn').addEventListener('click', exportLogs);
}

function wire() {
  wireNavigationHandlers();
  wireWorkspaceHandlers();
  wireModelAndRuntimeHandlers();
  wireMachineAndProfileHandlers();
  wireChatHandlers();
  wireLogHandlers();
}

function validStartPage() {
  const saved = persistentState.get('activePage', 'chat');
  return document.querySelector('.page[data-page-view="' + saved + '"]') ? saved : 'chat';
}
function ledgerCheck(key) {
  switch (key) {
    case 'runtime.running': return isRunning();
    case 'models.exists': return state.models.length > 0;
    case 'models.selected': return Boolean(runtime().activeModelId || $('#chatModel')?.value);
    case 'modelSources.exists': return (settingsValue().paths?.modelSources || settingsValue().modelSources || []).length > 0;
    case 'profile.selected': return Boolean($('#chatProfile')?.value);
    case 'machines.exists': return state.machines.length > 0;
    default: return false;
  }
}
function exposeAgentApi() {
  window.letterblack = Object.assign(window.letterblack || {}, {
    config: configLoader,
    uiState: persistentState,
    menuLedger,
    menuStatus: id => menuLedger.menuStatus(id, ledgerCheck),
    guidance: id => menuLedger.unmetGuidance(id, ledgerCheck),
    workflows: () => menuLedger.getAllWorkflows().map(wf => menuLedger.workflowStatus(wf.id, ledgerCheck)),
  });
}
async function boot() {
  await Promise.all([configLoader.load(), persistentState.load(), menuLedger.load()]);
  renderNavigation();
  rebindNav();
  wire();
  navigate(validStartPage());
  await refreshAll();
  exposeAgentApi();
  const poll = Number(persistentState.get('preferences.pollInterval')) || configLoader.getPollInterval(5000);
  state.timer = setInterval(() => refreshAll().catch(error => console.warn('Refresh failed', error)), poll);
}
window.addEventListener('beforeunload', () => { if (state.timer) clearInterval(state.timer); state.chatAbort?.abort(); persistentState.save(); });
boot().catch(error => notify('UI startup failed', errorText(error), 'warning'));

window.addEventListener('DOMContentLoaded', () => {
  import('./extensions.js')
    .then(module => module.installExtensionsUi?.())
    .catch(error => console.error('Extensions UI failed to initialize.', error));
});
