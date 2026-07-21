export function installSettingsUi(api, notify) {
  const page = document.querySelector('[data-page-view="settings"]');
  if (!page) return;

  page.innerHTML = `
    <div class="page-header">
      <div><p class="eyebrow">SYSTEM</p><h1>Settings</h1><p class="page-description">Validated control-plane settings. Restart requirements are reported after save.</p></div>
      <button class="button primary" type="button" id="saveSettingsBtn">Save changes</button>
    </div>
    <div class="settings-layout">
      <div class="content-card settings-section">
        <h3>Paths</h3>
        <label>Application root<input id="settingApplicationRoot" autocomplete="off"></label>
        <label>Model sources<textarea id="settingModelSources" rows="4" placeholder="One absolute path per line"></textarea></label>
        <label>llama-server executable<input id="settingLlamaServerPath" autocomplete="off" placeholder="Optional absolute path"></label>
      </div>
      <div class="content-card settings-section">
        <h3>Ports</h3>
        <label>Dashboard<input id="settingDashboardPort" type="number" min="1" max="65535"></label>
        <label>OpenAI gateway<input id="settingOpenAiPort" type="number" min="1" max="65535"></label>
        <label>Ollama gateway<input id="settingOllamaPort" type="number" min="1" max="65535"></label>
        <label>Worker controller<input id="settingControllerPort" type="number" min="1" max="65535"></label>
        <label>RPC<input id="settingRpcPort" type="number" min="1" max="65535"></label>
      </div>
      <div class="content-card settings-section">
        <h3>Runtime</h3>
        <label>Bind address<input id="settingBindAddress" autocomplete="off"></label>
        <label>UI polling interval (ms)<input id="settingPollInterval" type="number" min="1000" max="60000"></label>
        <label>Request drain timeout (sec)<input id="settingDrainTimeout" type="number" min="1" max="600"></label>
      </div>
      <div class="content-card settings-section">
        <h3>Safety</h3>
        <label><input id="settingBlockUnsafe" type="checkbox"> Block high-risk launches</label>
        <label><input id="settingAllowRemote" type="checkbox"> Allow remote dashboard binding</label>
        <div id="settingsStatus" class="inline-notice">Loading settings…</div>
      </div>
    </div>`;

  const byId = id => document.getElementById(id);
  const status = byId('settingsStatus');

  function setStatus(message, kind = 'neutral') {
    status.textContent = message;
    status.className = `inline-notice ${kind}`;
  }

  function fill(settings) {
    byId('settingApplicationRoot').value = settings.paths.applicationRoot || '';
    byId('settingModelSources').value = (settings.paths.modelSources || []).join('\n');
    byId('settingLlamaServerPath').value = settings.paths.llamaServerPath || '';
    byId('settingDashboardPort').value = settings.ports.dashboard;
    byId('settingOpenAiPort').value = settings.ports.openaiGateway;
    byId('settingOllamaPort').value = settings.ports.ollamaGateway;
    byId('settingControllerPort').value = settings.ports.workerController;
    byId('settingRpcPort').value = settings.ports.rpc;
    byId('settingBindAddress').value = settings.runtime.bindAddress || '127.0.0.1';
    byId('settingPollInterval').value = settings.runtime.pollIntervalMs;
    byId('settingDrainTimeout').value = settings.runtime.requestDrainTimeoutSec;
    byId('settingBlockUnsafe').checked = settings.safety.blockUnsafeLaunch === true;
    byId('settingAllowRemote').checked = settings.safety.allowRemoteDashboard === true;
  }

  function collect() {
    return {
      paths: {
        applicationRoot: byId('settingApplicationRoot').value.trim(),
        modelSources: byId('settingModelSources').value.split(/\r?\n/).map(x => x.trim()).filter(Boolean),
        llamaServerPath: byId('settingLlamaServerPath').value.trim(),
      },
      ports: {
        dashboard: Number(byId('settingDashboardPort').value),
        openaiGateway: Number(byId('settingOpenAiPort').value),
        ollamaGateway: Number(byId('settingOllamaPort').value),
        workerController: Number(byId('settingControllerPort').value),
        rpc: Number(byId('settingRpcPort').value),
      },
      runtime: {
        bindAddress: byId('settingBindAddress').value.trim(),
        pollIntervalMs: Number(byId('settingPollInterval').value),
        requestDrainTimeoutSec: Number(byId('settingDrainTimeout').value),
      },
      safety: {
        blockUnsafeLaunch: byId('settingBlockUnsafe').checked,
        allowRemoteDashboard: byId('settingAllowRemote').checked,
      },
    };
  }

  async function load() {
    try {
      const result = await api.settings();
      fill(result.settings);
      setStatus('Settings loaded from the backend.', 'good');
    } catch (error) {
      setStatus(`${error.code || 'SETTINGS_UNAVAILABLE'}: ${error.message || error}`, 'warning');
    }
  }

  byId('saveSettingsBtn').addEventListener('click', async () => {
    try {
      setStatus('Validating and saving…');
      const result = await api.updateSettings(collect());
      fill(result.settings);
      const restart = result.restartRequired || [];
      const message = restart.length ? `Saved. Restart required for: ${restart.join(', ')}` : 'Saved. No restart required.';
      setStatus(message, restart.length ? 'warning' : 'good');
      notify('Settings saved', message, restart.length ? 'warning' : 'good');
    } catch (error) {
      const details = Array.isArray(error.details) ? error.details.map(x => `${x.path}: ${x.message}`).join(' | ') : '';
      const message = `${error.code || 'SETTINGS_SAVE_FAILED'}: ${error.message || error}${details ? ` — ${details}` : ''}`;
      setStatus(message, 'warning');
      notify('Settings rejected', message, 'warning');
    }
  });

  load();
}
