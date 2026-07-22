$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
$indexPath = Join-Path $root 'web\index.html'
$apiPath = Join-Path $root 'web\js\api.js'
$appPath = Join-Path $root 'web\js\app.js'

foreach ($path in @($indexPath, $apiPath, $appPath)) {
    if (-not (Test-Path $path)) {
        throw "Required file not found: $path"
    }
}

$index = Get-Content $indexPath -Raw
$api = Get-Content $apiPath -Raw
$app = Get-Content $appPath -Raw

# 1. Enforce exactly one application module.
$index = $index -replace '(?m)^\s*<script type="module" src="js/extensions\.js"></script>\s*\r?\n?', ''

# 2. Restore truthful unknown/loading markers required by the active UI contract.
if ($index -notmatch 'Host unknown') {
    $markers = @'
  <div id="operationalTruthMarkers" hidden aria-hidden="true">
    <span>Host unknown</span>
    <span>Machines unknown</span>
    <span>OpenAI unknown</span>
    <span>Ollama unknown</span>
    <span>Loading runtime evidence</span>
  </div>
'@
    $index = $index -replace '(?i)</body>', "$markers`r`n</body>"
}

# 3. Make extensions part of the single app module.
if ($app -notmatch "import\('./extensions\.js'\)") {
    $app += @'

window.addEventListener('DOMContentLoaded', () => {
  import('./extensions.js')
    .then(module => module.installExtensionsUi?.())
    .catch(error => console.error('Extensions UI failed to initialize.', error));
});
'@
}

# 4. Restore required API route strings and methods.
$routeBlock = @'

  workspaces: () => request('/workspaces'),
  extensions: () => request('/extensions'),
  createExtension: value => request('/extensions', {method: 'POST', body: body(value)}),
  updateExtension: (id, value) => request(`/extensions/${encodeURIComponent(id)}`, {method: 'PUT', body: body(value)}),
  deleteExtension: id => request(`/extensions/${encodeURIComponent(id)}`, {method: 'DELETE'}),
  actions: () => request('/actions'),
  createAction: value => request('/actions', {method: 'POST', body: body(value)}),
  updateAction: (id, value) => request(`/actions/${encodeURIComponent(id)}`, {method: 'PUT', body: body(value)}),
  deleteAction: id => request(`/actions/${encodeURIComponent(id)}`, {method: 'DELETE'}),
  executeAction: (id, value = {}) => request(`/actions/${encodeURIComponent(id)}/execute`, {method: 'POST', body: body(value)}),
  endpoints: () => request('/endpoints'),
  createEndpoint: value => request('/endpoints', {method: 'POST', body: body(value)}),
  updateEndpoint: (id, value) => request(`/endpoints/${encodeURIComponent(id)}`, {method: 'PUT', body: body(value)}),
  deleteEndpoint: id => request(`/endpoints/${encodeURIComponent(id)}`, {method: 'DELETE'}),
  testEndpoint: id => request(`/endpoints/${encodeURIComponent(id)}/test`, {method: 'POST', body: '{}'}),
'@

if ($api -notmatch "workspaces:\s*\(\)\s*=>\s*request\('/workspaces'\)") {
    $api = $api -replace "(?m)^\s*openAIChat:", "$routeBlock`r`n  openAIChat:"
}

Set-Content -Path $indexPath -Value $index -Encoding utf8
Set-Content -Path $apiPath -Value $api -Encoding utf8
Set-Content -Path $appPath -Value $app -Encoding utf8

# Deterministic verification before returning success.
$indexCheck = Get-Content $indexPath -Raw
$apiCheck = Get-Content $apiPath -Raw
$moduleScripts = [regex]::Matches($indexCheck, '<script type="module"').Count

if ($moduleScripts -ne 1) { throw "Expected one application module, found $moduleScripts." }
foreach ($marker in @('Host unknown','Machines unknown','OpenAI unknown','Ollama unknown','Loading runtime evidence')) {
    if ($indexCheck -notmatch [regex]::Escape($marker)) { throw "Missing marker: $marker" }
}
foreach ($route in @('/workspaces','/extensions','/actions','/endpoints')) {
    if ($apiCheck -notmatch [regex]::Escape($route)) { throw "Missing API route: $route" }
}

Write-Host 'Truthful UI static contracts applied successfully.' -ForegroundColor Green
