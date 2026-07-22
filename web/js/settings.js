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
        <label>Application root<input id="settingApplicationRoot" autocomplete="off" readonly></label>
        <p>Applied location of the running control plane. Move or start the workspace from the required location instead of editing this value.</p>
        <label>Model sources<textarea id="settingModelSources" rows="4" placeholder="One absolute path per line"></textarea></label>
        <label>llama-server executable<input id="settingLlamaServerPath" autocomplete="off" placeholder="Optional absolute path"></label>
      </div>
      <div class="content-card settings-section">
        <h3>Control-plane listener</h3>
        <p><code>http://127.0.0.1:8088</code></p>
        <p>Applied listener. Remote control is unsupported until authentication exists.</p>
        <p>Saved OpenAI and Ollama port values are not applied; both compatibility routes share this listener.</p>
        <label>Worker controller<input id="settingControllerPort" type="number" min="1" max="65535"></label>
        <label>RPC<input id="settingRpcPort" type="number" min="1" max="65535"></label>
      </div>
      <div class="content-card settings-section">
        <h3>Runtime</h3>
        <p>Control-plane bind address: <code>127.0.0.1</code></p>
        <label>UI polling interval (ms)<input id="settingPollInterval" type="number" min="1000" max="60000"></label>
        <label>Request drain timeout (sec)<input id="settingDrainTimeout" type="number" min="1" max="600"></label>
      </div>
      <div class="content-card settings-section">
        <h3>Safety</h3>
        <label><input id="settingBlockUnsafe" type="checkbox"> Block high-risk launches</label>
        <div id="settingsStatus" class="inline-notice">Loading settings…</div>
      </div>
    </div>`;

  const byId = id => document.getElementById(id);
  const status = byId('settingsStatus');
  let loadedSettings = null;

  function setStatus(message, kind = 'neutral') {
    status.textContent = message;
    status.className = `inline-notice ${kind}`;
  }

  function fill(settings) {
    byId('settingApplicationRoot').value = settings.paths.applicationRoot || '';
    byId('settingModelSources').value = (settings.paths.modelSources || []).join('\n');
    byId('settingLlamaServerPath').value = settings.paths.llamaServerPath || '';
    byId('settingControllerPort').value = settings.ports.workerController;
    byId('settingRpcPort').value = settings.ports.rpc;
    byId('settingPollInterval').value = settings.runtime.pollIntervalMs;
    byId('settingDrainTimeout').value = settings.runtime.requestDrainTimeoutSec;
    byId('settingBlockUnsafe').checked = settings.safety.blockUnsafeLaunch === true;
    loadedSettings = settings;
  }

  function collect() {
    return {
      paths: {
        applicationRoot: byId('settingApplicationRoot').value.trim(),
        modelSources: byId('settingModelSources').value.split(/\r?\n/).map(x => x.trim()).filter(Boolean),
        llamaServerPath: byId('settingLlamaServerPath').value.trim(),
      },
      ports: {
        dashboard: 8088,
        openaiGateway: Number(loadedSettings.ports.openaiGateway),
        ollamaGateway: Number(loadedSettings.ports.ollamaGateway),
        workerController: Number(byId('settingControllerPort').value),
        rpc: Number(byId('settingRpcPort').value),
      },
      runtime: {
        bindAddress: '127.0.0.1',
        pollIntervalMs: Number(byId('settingPollInterval').value),
        requestDrainTimeoutSec: Number(byId('settingDrainTimeout').value),
      },
      safety: {
        blockUnsafeLaunch: byId('settingBlockUnsafe').checked,
        allowRemoteDashboard: false,
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
