const BASE = '/api/v1';

export class ApiError extends Error {
  constructor(code, message, status = 0, details = null) {
    super(message || code || 'API request failed');
    this.name = 'ApiError';
    this.code = code || 'API_ERROR';
    this.status = status;
    this.details = details;
  }
}

async function request(path, options = {}) {
  const response = await fetch(`${BASE}${path}`, {
    ...options,
    headers: {'Content-Type': 'application/json', ...(options.headers || {})},
  });
  const payload = await response.json().catch(() => null);
  if (!response.ok || !payload || payload.ok === false) {
    const error = payload?.error || {};
    throw new ApiError(error.code || `HTTP_${response.status}`, error.message || response.statusText, response.status, error.details || null);
  }
  return payload.data;
}

const body = value => JSON.stringify(value ?? {});

export const api = {
  capabilities: () => request('/capabilities'),
  system: () => request('/system/status'),
  settings: () => request('/settings'),
  updateSettings: value => request('/settings', {method: 'PUT', body: body(value)}),
  machines: () => request('/machines'),
  createMachine: value => request('/machines', {method: 'POST', body: body(value)}),
  testMachine: id => request(`/machines/${encodeURIComponent(id)}/test`, {method: 'POST', body: '{}'}),
  startRpc: id => request(`/machines/${encodeURIComponent(id)}/rpc/start`, {method: 'POST', body: '{}'}),
  stopRpc: id => request(`/machines/${encodeURIComponent(id)}/rpc/stop`, {method: 'POST', body: '{}'}),
  models: () => request('/models'),
  scanModels: value => request('/models/scan', {method: 'POST', body: body(value)}),
  profiles: () => request('/profiles'),
  preflight: value => request('/runtime/preflight', {method: 'POST', body: body(value)}),
  launch: value => request('/runtime/launch', {method: 'POST', body: body(value)}),
  stop: value => request('/runtime/stop', {method: 'POST', body: body(value)}),
  jobs: () => request('/jobs'),
  job: id => request(`/jobs/${encodeURIComponent(id)}`),
  telemetry: () => request('/telemetry'),
  logs: () => request('/logs'),
  requests: () => request('/requests'),
  cancelRequest: id => request(`/requests/${encodeURIComponent(id)}/cancel`, {method: 'POST', body: '{}'}),
  gateway: () => request('/gateway/status'),
  workspaces: () => request('/workspaces'),
  updateWorkspace: (id, value) => request(`/workspaces/${encodeURIComponent(id)}`, {method: 'PUT', body: body(value)}),
  extensions: () => request('/extensions'),
  createExtension: value => request('/extensions', {method: 'POST', body: body(value)}),
  updateExtension: (id, value) => request(`/extensions/${encodeURIComponent(id)}`, {method: 'PUT', body: body(value)}),
  deleteExtension: id => request(`/extensions/${encodeURIComponent(id)}`, {method: 'DELETE'}),
  actions: () => request('/actions'),
  createAction: value => request('/actions', {method: 'POST', body: body(value)}),
  executeAction: id => request(`/actions/${encodeURIComponent(id)}/execute`, {method: 'POST', body: '{}'}),
  endpoints: () => request('/endpoints'),
  createEndpoint: value => request('/endpoints', {method: 'POST', body: body(value)}),
  testEndpoint: id => request(`/endpoints/${encodeURIComponent(id)}/test`, {method: 'POST', body: '{}'}),
};

function settingsNotice(title, message = '', level = 'neutral') {
  const region = document.querySelector('#toastRegion');
  if (!region) return;
  const item = document.createElement('div');
  item.className = `toast ${level}`;
  item.innerHTML = `<strong>${title}</strong><span>${message}</span>`;
  region.append(item);
  setTimeout(() => item.remove(), 4500);
}

window.addEventListener('DOMContentLoaded', () => {
  import('./settings.js')
    .then(({installSettingsUi}) => installSettingsUi(api, settingsNotice))
    .catch(error => console.error('Settings UI failed to initialize.', error));
});
