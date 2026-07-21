# Letterblack Inference Workspace

Letterblack Inference Workspace is a local inference control surface for GGUF model discovery, llama.cpp runtime launch, distributed machine control, OpenAI- and Ollama-compatible endpoints, telemetry, profiles, logs, and settings.

## Current operator workflow

The committed UI is organized around the actual operator sequence:

1. Add a model folder.
2. Scan for GGUF files.
3. Select a model and optional profile.
4. Run preflight and launch the runtime.
5. Send a real test prompt from Chat.
6. Copy or test the exposed gateway endpoints.
7. Inspect telemetry, jobs, and logs when needed.

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

The verification script performs:

- Python unit-test discovery under `tests/`
- Python compilation checks for every backend module
- JavaScript syntax checks for every file under `web/js/`

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
- Copy endpoint URLs
- Test endpoints
- Change gateway ports through settings

Authentication, CORS, trusted hosts, per-surface enablement, and drain-policy editing are not yet exposed in the current UI.

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

Profile update, duplicate, delete, validation, fit estimate, and command preview remain incomplete.

### Logs and jobs

- Display runtime and control-plane log records
- Display background jobs and progress

### Settings

- Edit paths, ports, runtime binding, polling, timeout, and safety-related values through the current settings contract

## Extensibility status

The backend contains Phase 6 action, endpoint, extension, and widget-registry contracts. The current committed operator UI does **not** expose a dedicated Extensions page or the full action/extension management workflow.

Those backend capabilities must not be described as current user-facing UI until the frontend is restored and validated against the active API contract.

## Validation status

Static repository validation confirms:

- The active frontend entrypoint is `web/js/app.js`.
- The current HTML loads the Chat-first operator interface.
- Machine update and delete actions are wired in the frontend API client.
- Runtime launch, stop, chat, gateway, telemetry, profile creation, logs, and settings are wired to backend routes.
- The previous verification command referenced the removed `web/js/phase6.js`; `test.bat` now checks every active JavaScript file instead.

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
- Settings persistence after restart
- Responsive and accessibility acceptance
- Real two-machine Windows validation

## Security boundary

The runtime does not intentionally permit:

- Arbitrary shell execution from the operator UI
- Free-form local script execution
- Hidden executable extension code
- Undeclared remote endpoints

Any future executable extension mechanism requires a separate trust, signing, permission, and acceptance contract.
