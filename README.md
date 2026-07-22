# Letterblack Inference Workspace

Letterblack Inference Workspace is a local inference control surface for GGUF model discovery, llama.cpp runtime launch, distributed machine control, OpenAI- and Ollama-compatible endpoints, telemetry, profiles, declarative extensions, logs, and settings.

## Current operator workflow

The committed UI is organized around the actual operator sequence:

1. Add a model folder.
2. Scan for GGUF files.
3. Select a model and optional profile.
4. Run preflight and launch the runtime.
5. Send a real test prompt from Chat.
6. Copy or test the exposed gateway endpoints.
7. Manage declarative extensions, safe actions, and registered endpoints.
8. Inspect telemetry, jobs, and logs when needed.

The active navigation is:

```text
Chat
Setup
Models
Runtime
Machines
Gateways
Telemetry
Profiles
Extensions
Logs
Settings
```

## Run

```powershell
.\run.bat
```

Open:

```text
http://127.0.0.1:8088
```

## Verify

```powershell
.\test.bat
```

Or use the npm validation entry point:

```powershell
npm run validate
```

The verification script performs:

- Python unit-test discovery under `tests/`
- Environment-variable contract validation against `env.example`
- Python compilation checks for every backend module
- JavaScript syntax checks for every file under `web/js/`
- Static UI-contract coverage for the Extensions surface

A successful command ends with:

```text
Letterblack Inference Workspace validation passed.
```

## Implemented UI capabilities

### Chat

- Select a registered model
- Select an optional launch profile
- Choose OpenAI-compatible or Ollama-compatible routing
- Copy the active endpoint
- Send a real inference request
- Stream or cancel a response
- Inspect request state, latency, route, request ID, and raw response

### Setup

- Guided first-run progression
- Model-source, model, profile, runtime, and chat readiness states
- Direct navigation to the required control surface

### Models

- Add model folders
- Remove model folders
- Scan all sources or one source
- Inspect discovered GGUF metadata
- Open a model in Chat
- Open the launch flow for a model

Model sources are currently stored through the settings contract. A dedicated model-source registry is not yet implemented.

### Runtime

- Inspect active runtime state, model, PID, and endpoint
- Run preflight before launch
- Launch a selected model with an optional profile
- Stop the active runtime

### Machines

- Create machines
- Edit machines
- Delete machines
- Test connectivity
- Start RPC workers
- Stop RPC workers

### Gateways

- Display dashboard, OpenAI-compatible, and Ollama-compatible addresses
- Display the applied loopback listener at `127.0.0.1:8088`
- Label saved compatibility-port values as not applied
- Enable endpoint copying only after an exact health request passes

Authentication is not implemented. Remote control is unsupported and the control plane is fixed to `127.0.0.1:8088`.

### Telemetry

- System memory
- CPU count
- Active request count
- Per-GPU VRAM usage
- Free VRAM
- GPU utilization
- Temperature
- Power
- Driver information

Historical request charts and TTFT/throughput time series are not yet implemented.

### Profiles

- List saved launch profiles
- Create a launch profile
- Select a profile for Chat or launch

Profile update, duplicate, delete, validation, fit estimate, and command preview remain incomplete because matching profile mutation contracts are not present in the active frontend API surface.

### Extensions

The Extensions page is backed by the Phase 6 declarative API contracts and provides:

- Import of JSON extension manifests
- Backend validation of manifest compatibility and permissions
- Extension enable/disable
- Extension uninstall
- Registered widget/action/endpoint counts
- Creation of permission-bound operational actions
- Action execution as backend jobs
- Action deletion
- Registration of explicit HTTP endpoints
- Endpoint health testing
- Endpoint deletion

The UI does not execute extension-provided JavaScript, Python, PowerShell, shell commands, or binaries. Extension manifests remain declarative and are validated by the backend.

### Logs and jobs

- Display runtime and control-plane log records
- Filter records by level or search across returned record data
- Export the visible filtered records as JSON
- Display background jobs and progress

### Settings

- Edit paths, ports, runtime binding, polling, timeout, and safety-related values through the current settings contract

## API and UI authority

The operator UI uses:

```text
web/index.html
web/js/app.js
web/js/extensions.js
web/js/settings.js
web/css/operator.css
web/css/extensions.css
```

The declarative Extensions surface maps to:

```text
GET/POST   /api/v1/extensions
GET/PUT/DELETE /api/v1/extensions/{extensionId}
GET/POST   /api/v1/actions
GET/PUT/DELETE /api/v1/actions/{actionId}
POST       /api/v1/actions/{actionId}/execute
GET/POST   /api/v1/endpoints
PUT/DELETE /api/v1/endpoints/{endpointId}
POST       /api/v1/endpoints/{endpointId}/test
```

## Validation status

Static repository validation confirms:

- The primary runtime frontend entrypoint is `web/js/app.js`.
- The Extensions feature is isolated in `web/js/extensions.js` and loaded explicitly by the active HTML.
- The current HTML loads the Chat-first operator interface.
- Machine update and delete actions are wired in the frontend API client.
- Runtime launch, stop, chat, gateway, telemetry, profile creation, logs, settings, extensions, actions, and endpoints are wired to backend routes.
- `test.bat` checks every active JavaScript file instead of referencing removed phase-specific files.
- `tests/test_extensions_ui_contract.py` protects the active Extensions navigation, controls, route mapping, and security wording.

See `docs/UI_IMPLEMENTATION_VALIDATION.md` for the detailed implementation audit and remaining acceptance requirements.

## Release boundary

This repository should not be described as fully release-ready until all of the following pass from a clean Windows checkout:

- `test.bat`
- Fresh model-folder scan
- Real llama-server preflight and launch
- OpenAI-compatible chat request
- Ollama-compatible chat request
- Runtime cancellation
- Machine edit/delete/test/RPC controls
- Extension import, enable/disable, and uninstall
- Action creation and execution
- Endpoint registration and test
- Settings persistence after restart
- Responsive and accessibility acceptance
- Real two-machine Windows validation

## Security boundary

The runtime does not intentionally permit:

- Arbitrary shell execution from the operator UI
- Free-form local script execution
- Extension-provided executable code
- Undeclared remote endpoints
- HTTP actions against raw unregistered target URLs

Any future executable extension mechanism requires a separate trust, signing, permission, and acceptance contract.
