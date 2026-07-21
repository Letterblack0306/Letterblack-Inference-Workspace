import { defaultMachines, modelRows, widgetCatalog, commandItems } from './state.js';

const $ = (s, root=document) => root.querySelector(s);
const $$ = (s, root=document) => [...root.querySelectorAll(s)];
const appShell = $('#appShell');
const workspaceGrid = $('#workspaceGrid');
let machines = JSON.parse(localStorage.getItem('lb-machines') || 'null') || defaultMachines;
let customizing = false;

function toast(title, message='') {
  const el = document.createElement('div');
  el.className = 'toast';
  el.innerHTML = `<strong>${title}</strong><span>${message}</span>`;
  $('#toastRegion').append(el);
  setTimeout(() => el.remove(), 3600);
}

function switchPage(page) {
  $$('.nav-item[data-page]').forEach(b => b.classList.toggle('active', b.dataset.page === page));
  $$('.page').forEach(p => p.classList.toggle('active', p.dataset.pageView === page));
  $('#navigation').classList.remove('open');
  localStorage.setItem('lb-last-page', page);
}

function openDrawer(drawer) {
  $('#drawerBackdrop').hidden = false;
  drawer.classList.add('open');
  drawer.setAttribute('aria-hidden','false');
}
function closeDrawers() {
  $('#drawerBackdrop').hidden = true;
  $$('.drawer').forEach(d => { d.classList.remove('open'); d.setAttribute('aria-hidden','true'); });
}

function setCustomize(value) {
  customizing = value;
  workspaceGrid.classList.toggle('customizing', value);
  $('#customizeBanner').hidden = !value;
  $('#customizeBtn').textContent = value ? 'Editing workspace' : 'Customize workspace';
  $$('.widget').forEach(w => w.draggable = value);
  toast(value ? 'Customize mode enabled' : 'Workspace saved', value ? 'Drag, resize, add, or remove widgets.' : 'Layout is stored locally in this prototype.');
}

function renderModels() {
  $('#modelsTableBody').innerHTML = modelRows.map(r => `<tr>${r.map((v,i) => `<td>${i===7 ? `<span class="status-badge ${v==='Safe'?'good':v==='Caution'?'warning':'neutral'}">${v}</span>` : i===8 ? `<span class="status-badge ${v==='Active'?'good':'neutral'}">${v}</span>` : v}</td>`).join('')}</tr>`).join('');
}

function renderMachines() {
  $('#machineGrid').innerHTML = machines.map(m => `<article class="content-card machine-card" data-machine-id="${m.id}"><div class="machine-card-header"><div><span class="status-badge good">${m.state}</span><h3>${m.name}</h3><code>${m.address}:${m.controllerPort}</code></div><button class="icon-button">•••</button></div><div class="node-grid"><span>Role</span><b>${m.role}</b><span>GPU</span><b>${m.gpu}</b><span>CPU</span><b>${m.cpu}</b><span>RAM</span><b>${m.ram}</b><span>Latency</span><b>${m.latency}</b><span>RPC</span><b>:${m.rpcPort}</b></div><div class="machine-card-actions"><button class="button secondary compact test-machine">Test</button><button class="button secondary compact">Logs</button><button class="button secondary compact inspect-machine">Inspect</button></div></article>`).join('') + `<button class="content-card machine-card add-card add-machine-trigger"><span style="font-size:26px;color:var(--accent)">＋</span><h3>Add machine</h3><p style="color:var(--text-3)">Register another host, RPC worker, or CPU worker.</p></button>`;
  $$('.add-machine-trigger').forEach(b => b.onclick = () => $('#machineDialog').showModal());
  $$('.test-machine').forEach(b => b.onclick = () => toast('Connection verified','Controller reachable and capability contract matched.'));
  $$('.inspect-machine').forEach(b => b.onclick = (e) => openInspector('Machine', e.target.closest('.machine-card').dataset.machineId));
}

function renderWidgetCatalog(filter='') {
  const list = widgetCatalog.filter(w => (w.name+w.desc).toLowerCase().includes(filter.toLowerCase()));
  $('#widgetCatalog').innerHTML = list.map(w => `<button class="catalog-item" data-widget="${w.id}"><span class="catalog-icon">${w.icon}</span><span><strong>${w.name}</strong><small>${w.desc}</small></span><span>＋</span></button>`).join('');
  $$('.catalog-item').forEach(item => item.onclick = () => { toast('Widget added', item.querySelector('strong').textContent); closeDrawers(); });
}

function openInspector(type='Workspace', id='') {
  appShell.classList.add('inspector-open');
  $('#inspectorTitle').textContent = type;
  const content = $('#inspectorContent');
  if (type === 'Machine') {
    const m = machines.find(x => x.id === id);
    content.innerHTML = `<div class="inspector-section"><h3>${m?.name || 'Machine'}</h3><label>Name<input value="${m?.name || ''}"></label><label>Address<input value="${m?.address || ''}"></label><label>Controller port<input value="${m?.controllerPort || ''}"></label><label>RPC port<input value="${m?.rpcPort || ''}"></label></div><div class="inspector-section"><h3>Capabilities</h3><button class="button secondary full">Run diagnostics</button><button class="button secondary full">Restart RPC</button></div>`;
  } else {
    content.innerHTML = `<div class="inspector-section"><h3>Canvas</h3><label>Grid size<select><option>12 columns</option><option>8 columns</option></select></label><label>Density<select><option>Comfortable</option><option>Compact</option></select></label></div><div class="inspector-section"><h3>Current layout</h3><button class="button secondary full">Export workspace JSON</button><button class="button secondary full">Import workspace JSON</button></div>`;
  }
}

function addMachineFromForm(form) {
  const data = Object.fromEntries(new FormData(form));
  machines.push({ id:`machine-${Date.now()}`, name:data.name, role:data.role, address:data.address, controllerPort:Number(data.controllerPort), rpcPort:Number(data.rpcPort), gpu:'Detect after verification', cpu:'Detect after verification', ram:'Detect after verification', latency:'Not measured', state:'Pending verification' });
  localStorage.setItem('lb-machines', JSON.stringify(machines));
  renderMachines();
  toast('Machine added', `${data.name} is registered and ready for verification.`);
}

function setupDrag() {
  let dragged = null;
  workspaceGrid.addEventListener('dragstart', e => { if (!customizing) return; dragged = e.target.closest('.widget'); if (dragged) dragged.style.opacity = '.45'; });
  workspaceGrid.addEventListener('dragend', () => { if (dragged) dragged.style.opacity = ''; dragged = null; });
  workspaceGrid.addEventListener('dragover', e => { if (customizing) e.preventDefault(); });
  workspaceGrid.addEventListener('drop', e => { if (!customizing || !dragged) return; e.preventDefault(); const target = e.target.closest('.widget'); if (target && target !== dragged) workspaceGrid.insertBefore(dragged, target); });
}

function setupCommandPalette() {
  const dlg = $('#commandDialog');
  const render = (q='') => {
    const items = commandItems.filter(i => i.label.toLowerCase().includes(q.toLowerCase()));
    $('#commandResults').innerHTML = items.map((i,idx) => `<button type="button" class="command-result" data-index="${idx}"><strong>${i.label}</strong><small>${i.hint}</small></button>`).join('');
    $$('.command-result').forEach((el,idx) => el.onclick = () => { const item=items[idx]; dlg.close(); if(item.page) switchPage(item.page); if(item.action==='add-machine') $('#machineDialog').showModal(); if(item.action==='add-widget') openDrawer($('#widgetDrawer')); if(item.action==='add-action') $('#actionDialog').showModal(); if(item.action==='scan') toast('Model scan started','Registered sources are being scanned recursively.'); });
  };
  $('#commandPaletteBtn').onclick = () => { render(); dlg.showModal(); setTimeout(()=>$('#commandSearch').focus(),50); };
  $('#commandSearch').oninput = e => render(e.target.value);
}

$$('.nav-item[data-page]').forEach(b => b.onclick = () => switchPage(b.dataset.page));
$('#mobileNavToggle').onclick = () => $('#navigation').classList.toggle('open');
$('#customizeBtn').onclick = () => setCustomize(!customizing);
$('#doneCustomizeBtn').onclick = () => setCustomize(false);
$('#resetLayoutBtn').onclick = () => toast('Layout reset','Default workspace layout restored.');
$('#addWidgetBtn').onclick = () => openDrawer($('#widgetDrawer'));
$('#drawerBackdrop').onclick = closeDrawers;
$$('[data-close-drawer]').forEach(b => b.onclick = closeDrawers);
$('#widgetSearch').oninput = e => renderWidgetCatalog(e.target.value);
$('#addMachineBtn').onclick = () => $('#machineDialog').showModal();
$('#topologyAddMachine').onclick = () => $('#machineDialog').showModal();
$('#addActionBtn').onclick = () => $('#actionDialog').showModal();
$('#addQuickActionBtn').onclick = () => $('#actionDialog').showModal();
$('#editActionsBtn').onclick = () => $('#actionDialog').showModal();
$('#stopAllBtn').onclick = () => $('#stopDialog').showModal();
$('#closeInspectorBtn').onclick = () => appShell.classList.remove('inspector-open');
$('#testConnectionBtn').onclick = () => { const r=$('#connectionResult'); r.innerHTML='<span class="status-dot good"></span> Controller reachable · protocol compatible'; };
$('#machineForm').addEventListener('submit', e => { e.preventDefault(); addMachineFromForm(e.currentTarget); $('#machineDialog').close(); e.currentTarget.reset(); });
// Phase 6 owns the action form and persists actions through the control-plane API.
$('#scanModelsBtn').onclick = () => toast('Model scan started','Scanning registered sources recursively.');
$('#registerModelBtn').onclick = () => toast('Registration flow','This prototype would open a server-side file browser.');
$('#layoutPresetBtn').onclick = () => toast('Layout presets','Operations, Performance Lab, and Minimal Monitor are available.');
$('#workspaceSelect').onchange = e => toast('Workspace switched', e.target.selectedOptions[0].textContent);

renderModels();
renderMachines();
renderWidgetCatalog();
setupDrag();
setupCommandPalette();
switchPage(localStorage.getItem('lb-last-page') || 'overview');
