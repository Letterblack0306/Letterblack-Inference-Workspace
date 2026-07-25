const STORAGE = {
  inspectorWidth: 'letterblack.workspace.v2.inspectorWidth',
  inspectorCollapsed: 'letterblack.workspace.v2.inspectorCollapsed',
  sidebarCollapsed: 'letterblack.workspace.v2.sidebarCollapsed',
};

const q = (selector, root = document) => root.querySelector(selector);
const qa = (selector, root = document) => [...root.querySelectorAll(selector)];

function readBoolean(key, fallback = false) {
  const value = localStorage.getItem(key);
  return value == null ? fallback : value === 'true';
}

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

function setInspectorWidth(value) {
  const layout = q('.chat-layout');
  if (!layout) return;
  const width = clamp(Number(value) || 320, 220, Math.max(220, Math.floor(window.innerWidth * 0.48)));
  layout.style.setProperty('--chat-inspector-width', `${width}px`);
  localStorage.setItem(STORAGE.inspectorWidth, String(width));
}

function installInspectorControls() {
  const layout = q('.chat-layout');
  const inspector = q('.request-inspector', layout || document);
  if (!layout || !inspector || q('.workspace-v2-resizer', layout)) return;

  const resizer = document.createElement('div');
  resizer.className = 'workspace-v2-resizer';
  resizer.setAttribute('role', 'separator');
  resizer.setAttribute('aria-orientation', 'vertical');
  resizer.setAttribute('aria-label', 'Resize request inspector');
  resizer.tabIndex = 0;
  layout.append(resizer);

  const savedWidth = Number(localStorage.getItem(STORAGE.inspectorWidth));
  if (Number.isFinite(savedWidth)) setInspectorWidth(savedWidth);

  const collapsed = readBoolean(STORAGE.inspectorCollapsed);
  document.body.classList.toggle('v2-inspector-collapsed', collapsed);

  const toggle = document.createElement('button');
  toggle.type = 'button';
  toggle.className = 'workspace-v2-inspector-toggle';
  toggle.textContent = collapsed ? 'Show inspector' : 'Hide inspector';
  toggle.setAttribute('aria-pressed', String(!collapsed));
  q('.composer-actions')?.prepend(toggle);

  toggle.addEventListener('click', () => {
    const next = !document.body.classList.contains('v2-inspector-collapsed');
    document.body.classList.toggle('v2-inspector-collapsed', next);
    localStorage.setItem(STORAGE.inspectorCollapsed, String(next));
    toggle.textContent = next ? 'Show inspector' : 'Hide inspector';
    toggle.setAttribute('aria-pressed', String(!next));
  });

  let startX = 0;
  let startWidth = 0;
  const stopResize = () => {
    document.body.classList.remove('v2-resizing');
    window.removeEventListener('pointermove', moveResize);
    window.removeEventListener('pointerup', stopResize);
    window.removeEventListener('pointercancel', stopResize);
  };
  const moveResize = event => {
    const next = startWidth + (startX - event.clientX);
    setInspectorWidth(next);
  };
  resizer.addEventListener('pointerdown', event => {
    if (window.matchMedia('(max-width: 860px)').matches) return;
    startX = event.clientX;
    startWidth = inspector.getBoundingClientRect().width;
    resizer.setPointerCapture?.(event.pointerId);
    document.body.classList.add('v2-resizing');
    window.addEventListener('pointermove', moveResize);
    window.addEventListener('pointerup', stopResize);
    window.addEventListener('pointercancel', stopResize);
  });
  resizer.addEventListener('keydown', event => {
    if (!['ArrowLeft', 'ArrowRight'].includes(event.key)) return;
    event.preventDefault();
    const current = inspector.getBoundingClientRect().width;
    setInspectorWidth(current + (event.key === 'ArrowLeft' ? 16 : -16));
  });
}

function installSidebarControl() {
  const brand = q('.brand-block');
  if (!brand || q('.workspace-v2-sidebar-toggle')) return;
  const button = document.createElement('button');
  button.type = 'button';
  button.className = 'workspace-v2-sidebar-toggle';
  button.setAttribute('aria-label', 'Toggle compact navigation');
  button.title = 'Toggle compact navigation';
  button.textContent = '≡';
  brand.append(button);

  const collapsed = readBoolean(STORAGE.sidebarCollapsed);
  document.body.classList.toggle('v2-sidebar-collapsed', collapsed);
  button.setAttribute('aria-pressed', String(collapsed));

  button.addEventListener('click', () => {
    const next = !document.body.classList.contains('v2-sidebar-collapsed');
    document.body.classList.toggle('v2-sidebar-collapsed', next);
    localStorage.setItem(STORAGE.sidebarCollapsed, String(next));
    button.setAttribute('aria-pressed', String(next));
  });
}

function dispatchClick(selector) {
  const target = q(selector);
  if (!target || target.disabled) return false;
  target.click();
  return true;
}

function pageCommands() {
  return qa('.nav-item[data-page]').map((button, index) => ({
    id: `page-${button.dataset.page}`,
    icon: String(index + 1),
    label: button.textContent.trim().replace(/\s+\d+$/, ''),
    hint: 'Open page',
    keywords: `navigate ${button.dataset.page}`,
    run: () => button.click(),
  }));
}

function utilityCommands() {
  return [
    {id: 'focus-chat', icon: '↵', label: 'Focus prompt', hint: 'Chat', keywords: 'compose prompt message', run: () => { dispatchClick('.nav-item[data-page="chat"]'); setTimeout(() => q('#chatPrompt')?.focus(), 0); }},
    {id: 'rescan-models', icon: '↻', label: 'Rescan models', hint: 'Models', keywords: 'scan refresh gguf', run: () => dispatchClick('#scanModelsBtn')},
    {id: 'start-model', icon: '▶', label: 'Start selected model', hint: 'Runtime', keywords: 'launch inference runtime', run: () => dispatchClick('#startSelectedModel')},
    {id: 'open-jobs', icon: 'J', label: 'Open background jobs', hint: 'Jobs', keywords: 'tasks progress', run: () => dispatchClick('#jobsBtn')},
    {id: 'toggle-inspector', icon: 'I', label: 'Toggle request inspector', hint: 'Chat', keywords: 'request raw response metrics', run: () => dispatchClick('.workspace-v2-inspector-toggle')},
  ];
}

function installCommandPalette() {
  if (q('#workspaceV2CommandOverlay')) return;
  const overlay = document.createElement('div');
  overlay.id = 'workspaceV2CommandOverlay';
  overlay.className = 'workspace-v2-command-overlay';
  overlay.hidden = true;
  overlay.innerHTML = `
    <section class="workspace-v2-command" role="dialog" aria-modal="true" aria-label="Workspace command palette">
      <input id="workspaceV2CommandInput" type="search" autocomplete="off" placeholder="Navigate or run a safe UI action…">
      <div class="workspace-v2-command-list" id="workspaceV2CommandList"></div>
    </section>`;
  document.body.append(overlay);

  const button = document.createElement('button');
  button.type = 'button';
  button.className = 'workspace-v2-command-button';
  button.textContent = 'Commands';
  button.title = 'Command palette (Ctrl/Cmd+K)';
  q('.app-actions')?.prepend(button);

  const input = q('#workspaceV2CommandInput');
  const list = q('#workspaceV2CommandList');
  let activeIndex = 0;
  let visible = [];

  const close = () => {
    overlay.hidden = true;
    input.value = '';
  };
  const execute = command => {
    close();
    command.run();
  };
  const render = () => {
    const term = input.value.trim().toLowerCase();
    const commands = [...pageCommands(), ...utilityCommands()];
    visible = commands.filter(item => !term || `${item.label} ${item.hint} ${item.keywords}`.toLowerCase().includes(term));
    activeIndex = clamp(activeIndex, 0, Math.max(0, visible.length - 1));
    list.innerHTML = visible.length
      ? visible.map((item, index) => `<button class="workspace-v2-command-item${index === activeIndex ? ' active' : ''}" type="button" data-command-index="${index}"><span>${item.icon}</span><strong>${item.label}</strong><small>${item.hint}</small></button>`).join('')
      : '<div class="workspace-v2-command-empty">No matching command.</div>';
    qa('[data-command-index]', list).forEach(item => item.addEventListener('click', () => execute(visible[Number(item.dataset.commandIndex)])));
  };
  const open = () => {
    overlay.hidden = false;
    activeIndex = 0;
    render();
    requestAnimationFrame(() => input.focus());
  };

  button.addEventListener('click', open);
  overlay.addEventListener('mousedown', event => { if (event.target === overlay) close(); });
  input.addEventListener('input', () => { activeIndex = 0; render(); });
  input.addEventListener('keydown', event => {
    if (event.key === 'Escape') { event.preventDefault(); close(); return; }
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault();
      activeIndex = clamp(activeIndex + (event.key === 'ArrowDown' ? 1 : -1), 0, Math.max(0, visible.length - 1));
      render();
      q('.workspace-v2-command-item.active', list)?.scrollIntoView({block: 'nearest'});
      return;
    }
    if (event.key === 'Enter' && visible[activeIndex]) { event.preventDefault(); execute(visible[activeIndex]); }
  });

  document.addEventListener('keydown', event => {
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
      event.preventDefault();
      overlay.hidden ? open() : close();
    }
  });
}

function installKeyboardControls() {
  const prompt = q('#chatPrompt');
  if (prompt && !prompt.dataset.v2Keyboard) {
    prompt.dataset.v2Keyboard = 'true';
    prompt.addEventListener('keydown', event => {
      if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') {
        event.preventDefault();
        dispatchClick('#sendChat');
      }
    });
  }

  document.addEventListener('keydown', event => {
    if (event.key !== 'Escape') return;
    const openDialog = qa('dialog[open]').at(-1);
    if (openDialog) { openDialog.close(); return; }
    const cancel = q('#cancelChat');
    if (cancel && !cancel.disabled) cancel.click();
  });
}

function syncTruthState() {
  const runtimeText = q('#runtimeHealth')?.textContent?.toLowerCase() || '';
  const gatewayText = q('#gatewayHealth')?.textContent?.toLowerCase() || '';
  const machineText = q('#machineHealth')?.textContent?.toLowerCase() || '';
  document.body.dataset.runtimeState = runtimeText.includes('stopped') ? 'stopped' : (runtimeText.includes('running') || runtimeText.includes('runtime:') ? 'running' : 'unknown');
  document.body.dataset.gatewayState = gatewayText.includes('healthy') ? 'healthy' : (gatewayText.includes('unverified') || gatewayText.includes('unavailable') ? 'unverified' : 'unknown');
  document.body.dataset.machineState = /[1-9]\d*\/\d+ machines online/.test(machineText) ? 'online' : 'unverified';
}

function installTruthObserver() {
  syncTruthState();
  const targets = ['#runtimeHealth', '#gatewayHealth', '#machineHealth'].map(q).filter(Boolean);
  const observer = new MutationObserver(syncTruthState);
  targets.forEach(target => observer.observe(target, {subtree: true, childList: true, characterData: true, attributes: true}));
}

function installAutoGrow() {
  const prompt = q('#chatPrompt');
  if (!prompt || prompt.dataset.v2AutoGrow) return;
  prompt.dataset.v2AutoGrow = 'true';
  const resize = () => {
    prompt.style.height = 'auto';
    prompt.style.height = `${clamp(prompt.scrollHeight, 88, 260)}px`;
  };
  prompt.addEventListener('input', resize);
  resize();
}

function initialize() {
  document.documentElement.dataset.workspaceUi = 'v2';
  installSidebarControl();
  installInspectorControls();
  installCommandPalette();
  installKeyboardControls();
  installTruthObserver();
  installAutoGrow();
}

if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', initialize, {once: true});
else initialize();
