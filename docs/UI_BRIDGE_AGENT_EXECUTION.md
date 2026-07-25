# UI Bridge Agent Execution Contract

This file is operational instruction, not a design proposal.

## Inputs

- Repository branch: `agent/ui-backend-contract-bridge`
- Visual source artifact: `letterblack_inference_workspace.html`
- Required source SHA-256: `ebf939a291ae0a2852db96d78fbaec68ac25c5b2ab9134bfa13437bfdb024352`
- DOM/function authority: `contracts/ui-prototype-dom.json`
- Handler/backend authority: `contracts/ui-prototype-binding.json`
- Route/payload authority: `contracts/ui-backend-bridge-map.json`
- Detailed backend contract: `docs/UI_BACKEND_BRIDGE_CONTRACT.md`
- Existing frontend API authority: `web/js/api.js`

## Mandatory first gate

Before editing any repository file, run:

```powershell
python scripts/verify-ui-prototype.py "<absolute-path>\letterblack_inference_workspace.html"
```

Required output:

```text
PASS exact UI prototype verified sha256=ebf939a291ae0a2852db96d78fbaec68ac25c5b2ab9134bfa13437bfdb024352 ids=78 handlers=60 functions=75
```

If this gate fails, stop. Do not bridge a visually similar file and do not regenerate the prototype.

## Implementation boundary

1. Preserve the prototype's visual composition, density, four top-level hubs, diagnostics drawer, inspector, runtime deck, cards, dialogs, and control placement.
2. Integrate that visual system into the active repository files under `web/`. Do not ship the standalone monolithic script as a second application.
3. Keep `web/js/api.js` as the backend adapter authority. Extend it only when a verified backend route exists but lacks an adapter method.
4. Do not add backend aliases for prototype-only routes.
5. Do not change Python backend behavior merely to make the prototype's old JavaScript work.
6. Backend-owned state must come from API responses. Demo values may exist only as disabled skeleton text before hydration.

## Exact handler rule

For every backend-affecting prototype function, use the corresponding entry in `contracts/ui-prototype-binding.json`.

- Preserve the listed selector's visible purpose.
- Use only the listed `repositoryCalls` unless the contract is updated with repository evidence.
- Apply the listed transformation or composition exactly.
- Implement every `requiredUiChange` visibly. Do not fabricate missing values.
- Remove every route in `forbiddenActiveRoutes` from active frontend code.

The local agent must not infer a machine ID from a display name, a model ID from a hardcoded label, or a profile ID from modal title text.

## Required UI structural corrections

### Machine dialog

The prototype's node dialog is insufficient for the backend machine validator. The integrated UI must expose:

- machine ID
- machine name
- address/hostname
- controller protocol
- controller port
- RPC port
- RPC enabled
- runtime path
- models path
- enabled state
- action selections where supported

Do not silently reuse one port for controller and RPC.

### Profile dialog

The integrated UI must expose:

- profile ID
- profile name
- description
- context size
- GPU layers
- batch size
- threads
- parallel count
- Flash Attention

Create and update must be distinct based on a backend-known profile ID.

### Settings page

The following values are backend-fixed and must be shown read-only:

- control plane: `http://127.0.0.1:8088`
- OpenAI base: `http://127.0.0.1:8088/v1`
- application root returned by the backend
- remote dashboard: unsupported

Save the complete object returned by `GET /api/v1/settings`, modifying only supported fields. Preserve all unedited sections and port values.

### Model cards

Render model cards from `api.models()` results. Button values must carry `model.id`. Static names in the prototype are visual examples, not valid runtime identifiers.

### Runtime actions

- Launch: preflight, explicit unsafe acknowledgement when required, launch, poll job, refresh system.
- Stop: submit stop, poll job, refresh system.
- Restart: capture active IDs, stop to success, preflight, launch to success, refresh system.
- Swap: selected registered `model.id`, stop to success, preflight, launch to success, refresh system.
- Shutdown: call stop with `shutdownControlServer:true`; do not call a workspace-shutdown route.

No runtime badge, PID, model, port, readiness, or success state may be updated optimistically.

## File scope

Expected active implementation scope:

```text
web/index.html
web/css/*.css
web/js/app.js
web/js/api.js
web/js/extensions.js
web/js/settings.js
```

New focused frontend modules are allowed. Avoid unrelated backend, state-data, release, or documentation changes.

## Validation gates

Run in this order:

```powershell
python -m unittest tests.test_ui_bridge_contract
npm run validate
```

Then run the real workspace:

```powershell
.\run.bat
```

Live acceptance must separately report:

1. model folder save and scan job terminal result
2. model registry refresh
3. preflight result
4. runtime launch job terminal result
5. `/api/v1/system/status` runtime evidence
6. OpenAI streaming chat
7. OpenAI non-streaming chat
8. Ollama `/api/chat`
9. runtime stop job terminal result
10. settings persistence after restart
11. machine test using a registered machine ID
12. RPC start/stop where a compatible controller exists

Do not describe live acceptance as passed when only static validation passed.

## Required final report

Return:

- exact files changed
- prototype verification output
- bridge contract test output
- `npm run validate` output
- list of prototype-only routes removed
- list of required UI fields added
- live acceptance results with evidence
- unresolved backend capability gaps

Do not report completion if any backend-affecting prototype handler remains local-only or simulated.
