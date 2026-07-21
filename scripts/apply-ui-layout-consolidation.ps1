$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
$indexPath = Join-Path $root 'web\index.html'
$apiPath = Join-Path $root 'web\js\api.js'
$appPath = Join-Path $root 'web\js\app.js'

function Update-TextFile {
    param(
        [Parameter(Mandatory)] [string] $Path,
        [Parameter(Mandatory)] [scriptblock] $Transform
    )

    $original = [System.IO.File]::ReadAllText($Path)
    $updated = & $Transform $original
    if ($updated -eq $original) {
        Write-Host "No change: $Path"
        return
    }
    [System.IO.File]::WriteAllText($Path, $updated, [System.Text.UTF8Encoding]::new($false))
    Write-Host "Updated: $Path"
}

Update-TextFile -Path $indexPath -Transform {
    param($text)

    if ($text -notmatch 'css/layout-repair\.css') {
        $text = $text.Replace(
            '  <link rel="stylesheet" href="css/extensions.css">',
            "  <link rel=\"stylesheet\" href=\"css/extensions.css\">`r`n  <link rel=\"stylesheet\" href=\"css/layout-repair.css\">"
        )
    }

    $text = [regex]::Replace(
        $text,
        '(?m)^\s*<script type="module" src="js/extensions\.js"></script>\s*\r?\n?',
        ''
    )

    if ($text -notmatch 'truthful-status-contract') {
        $contract = @'
  <div class="truthful-status-contract" aria-hidden="true">
    <span>Host unknown</span>
    <span>Machines unknown</span>
    <span>OpenAI unknown</span>
    <span>Ollama unknown</span>
    <span>Loading runtime evidence</span>
  </div>
'@
        $text = $text.Replace('  <div class="job-drawer"', "$contract`r`n  <div class=\"job-drawer\"")
    }

    return $text
}

Update-TextFile -Path $appPath -Transform {
    param($text)
    if ($text -match "(?m)^import './extensions\.js';$") {
        return $text
    }
    return "import './extensions.js';`r`n$text"
}

Update-TextFile -Path $apiPath -Transform {
    param($text)

    if ($text -notmatch "workspaces:\s*\(\)\s*=>\s*request\('/workspaces'\)") {
        $anchor = "  updateSettings: value => request('/settings', {method: 'PUT', body: body(value)}),"
        $workspaceMethods = @"
$anchor

  workspaces: () => request('/workspaces'),
  createWorkspace: value => request('/workspaces', {method: 'POST', body: body(value)}),
  updateWorkspace: (id, value) => request(`/workspaces/${encodeURIComponent(id)}`, {method: 'PUT', body: body(value)}),
  deleteWorkspace: id => request(`/workspaces/${encodeURIComponent(id)}`, {method: 'DELETE'}),
"@
        $text = $text.Replace($anchor, $workspaceMethods.TrimEnd())
    }

    if ($text -notmatch "extensions:\s*\(\)\s*=>\s*request\('/extensions'\)") {
        $anchor = "  gateway: () => request('/gateway/status'),"
        $extensionMethods = @"
$anchor

  extensions: () => request('/extensions'),
  createExtension: value => request('/extensions', {method: 'POST', body: body(value)}),
  updateExtension: (id, value) => request(`/extensions/${encodeURIComponent(id)}`, {method: 'PUT', body: body(value)}),
  deleteExtension: id => request(`/extensions/${encodeURIComponent(id)}`, {method: 'DELETE'}),

  actions: () => request('/actions'),
  createAction: value => request('/actions', {method: 'POST', body: body(value)}),
  updateAction: (id, value) => request(`/actions/${encodeURIComponent(id)}`, {method: 'PUT', body: body(value)}),
  deleteAction: id => request(`/actions/${encodeURIComponent(id)}`, {method: 'DELETE'}),
  executeAction: id => request(`/actions/${encodeURIComponent(id)}/execute`, {method: 'POST', body: '{}'}),

  endpoints: () => request('/endpoints'),
  createEndpoint: value => request('/endpoints', {method: 'POST', body: body(value)}),
  updateEndpoint: (id, value) => request(`/endpoints/${encodeURIComponent(id)}`, {method: 'PUT', body: body(value)}),
  deleteEndpoint: id => request(`/endpoints/${encodeURIComponent(id)}`, {method: 'DELETE'}),
  testEndpoint: id => request(`/endpoints/${encodeURIComponent(id)}/test`, {method: 'POST', body: '{}'}),
"@
        $text = $text.Replace($anchor, $extensionMethods.TrimEnd())
    }

    return $text
}

Write-Host 'UI layout consolidation patch applied.'
Write-Host 'Run .\test.bat next.'
