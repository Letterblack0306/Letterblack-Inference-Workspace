# Standalone UI → Repository Backend Bridge Contract

**Branch:** `agent/ui-backend-contract-bridge`  
**Generated:** 2026-07-25  
**Purpose:** Provide a deterministic contract for linking the standalone `letterblack_inference_workspace.html` visual UI to the existing Letterblack Inference Workspace backend.

## Decision

Adapt the standalone UI to the existing repository API. Do **not** add duplicate backend aliases merely to preserve prototype route names. The backend remains authoritative for runtime, models, machines, profiles, settings, extensions, jobs, requests, logs, gateway state, and telemetry.

Only view preferences may remain in `localStorage`: active page/hub, inspector width/open state, and unsaved editor drafts.

## Verified source fingerprints

The bridge was derived from these repository files on `main`:

| File | Blob SHA |
|---|---|
| `web/js/api.js` | `a58a03ed0d12e8e796738577c69927cb221d6830` |
| `backend/server.py` | `2e89884e445228e8b62530b2848b72c586dd71f4` |
| `backend/contracts.py` | `b76c8be546b8027ff2febd4f2d72bfdde95d27fd` |
| `backend/server_settings.py` | `f9edb4f85eff425faa8c537ac17ba81fd75557c1` |
| `contracts/openapi.json` | `513a20a1e31817ee851ef0606c6dd8c7404bf573` |
| `data/state.json` | `9758409b09721905a4a049bdf9a256e0581cb3e3` |

Before implementation, compare these SHAs with the current branch. If any changed, re-read the changed contract before modifying the UI.

## Response authority

### Control-plane routes

All `/api/v1/*` success responses use:

```json
{
  "ok": true,
  "requestId": "req-*",
  "timestamp": 0,
  "data": {}
}
```

Failures use:

```json
{
  "ok": false,
  "requestId": "req-*",
  "timestamp": 0,
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable message",
    "details": null
  }
}
```

The frontend adapter must unwrap `payload.data` and preserve `requestId` for diagnostics. It must throw a typed error using `error.code`, `error.message`, HTTP status, and `error.details`.

### Compatibility routes

The following are raw OpenAI/Ollama-compatible routes and must **not** be unwrapped as control envelopes:

- `GET /v1/models`
- `POST /v1/chat/completions`
- `POST /v1/completions`
- `POST /v1/embeddings`
- `GET /api/tags`
- `POST /api/chat`
- `POST /api/generate`
- `POST /api/embeddings`

## Route and data diff

| UI feature | Standalone prototype | Repository authority | Required bridge |
|---|---|---|---|
| Control health | `GET /health` | `GET /api/v1/system/status` | Replace. Use `data.runtime` and `data.runtime.process`. |
| Gateway status | Inferred fixed URLs | `GET /api/v1/gateway/status` | Hydrate addresses from `data.controlPlane` and `data.routes`. |
| Registered models | `GET /models` | `GET /api/v1/models` | Replace and unwrap. Model identity is `model.id`, not a display alias. |
| OpenAI models | `GET /v1/models` | `GET /v1/models` | Compatible raw response. Do not unwrap. |
| Telemetry | `GET /api/telemetry` with flat fields | `GET /api/v1/telemetry` | Replace. Map `runtimeProcess`, `local`, and `machines[]`; do not expect flat `vram_used_gb`. |
| Scan models | `POST /api/models/rescan` body `{directories}` | `POST /api/v1/models/scan` body `{sources}` | Transform `directories → sources`; response is a job. Poll it, then refetch models. |
| Preflight | Missing | `POST /api/v1/runtime/preflight` | Required before launch. Send `{modelId, profileId?, overrides?, safetyMargin?}`. |
| Launch | `POST /api/runtime/launch` body `{model, profile}` | `POST /api/v1/runtime/launch` body `{modelId, profileId?, overrides?, readinessTimeoutSec?, allowUnsafe?}` | Transform identifiers and profile values. Poll returned job to terminal. |
| Stop | `POST /api/runtime/stop` | `POST /api/v1/runtime/stop` | Replace. Body supports `{drainTimeoutSec, timeoutSec, force, machineIds?, shutdownControlServer?}`. Poll job. |
| Restart | `POST /api/runtime/restart` | No route | Compose: capture IDs → stop and await success → preflight → launch and await success. |
| Model swap | `POST /api/runtime/swap` | No route | Compose stop → preflight selected `modelId` → launch. Do not update active badge optimistically. |
| Workspace shutdown | `POST /api/workspace/shutdown` | `POST /api/v1/runtime/stop` | Send `{shutdownControlServer:true}` after explicit confirmation. |
| Machine list | Local/static node state | `GET /api/v1/machines` | Backend replaces local node authority. |
| Add machine | Local-only | `POST /api/v1/machines` | Send the validated machine shape below. |
| Edit machine | Local-only | `PUT /api/v1/machines/{id}` | Send the complete machine object. |
| Delete machine | Local-only | `DELETE /api/v1/machines/{id}` | Remove only after backend success. |
| Node test | `POST /api/nodes/test` body host/port | `POST /api/v1/machines/{machineId}/test` body `{}` | Machine must be registered. Use its ID. |
| RPC start/stop | Missing | `POST /api/v1/machines/{id}/rpc/start|stop` | Both return jobs; poll to terminal. |
| OpenAI chat | `POST /v1/chat/completions` | Same | Keep JSON/SSE handling; use active registered model/runtime identity and capture `X-Request-ID`. |
| Ollama chat | UI displays `/api/generate` | `POST /api/chat` for message chat | Use `/api/chat` for role messages. Keep `/api/generate` only for prompt-only mode. |
| Settings | `localStorage` only | `GET/PUT /api/v1/settings` | Backend replaces local authority. Send the complete settings object. Surface `restartRequired`. |
| Profiles | Local profile object | CRUD under `/api/v1/profiles` | Backend replaces local authority. |
| Extensions | Local JSON parse/save | CRUD under `/api/v1/extensions` | Send manifests to backend validation. Never claim installed from local parse alone. |
| Logs | DOM-only simulated log stream | `GET /api/v1/logs` | Render backend records; local UI events may be visually separated. |
| Jobs | Missing | `GET /api/v1/jobs`, `GET /api/v1/jobs/{id}` | Required for every async scan/runtime/RPC/action result. |
| Browser stop | `AbortController` only | `POST /api/v1/requests/{requestId}/cancel` | Browser abort stops consumption. Backend cancellation may return `ACTIVE_CANCELLATION_UNSUPPORTED`; report separately. |

## Authoritative request shapes

### Machine

```json
{
  "id": "machine-worker-01",
  "name": "Worker 01",
  "addresses": ["192.168.1.155"],
  "controller": {"scheme": "http", "port": 50053},
  "rpc": {"port": 50052, "enabled": true},
  "paths": {"runtime": "", "models": ""},
  "enabled": true,
  "tags": ["rpc-worker"],
  "actions": ["test", "edit", "start-rpc", "stop-rpc"]
}
```

`id` must match `^[a-z0-9][a-z0-9._-]{1,63}$`. Both controller and RPC ports are required and must be from 1 to 65535.

### Profile

```json
{
  "id": "profile-production",
  "name": "Production",
  "description": "",
  "values": {
    "contextSize": 16384,
    "gpuLayers": 99,
    "batchSize": 512,
    "threads": 8,
    "parallel": 1,
    "flashAttention": true
  }
}
```

The numeric fields above must be non-negative integers. `flashAttention` must be boolean.

### Runtime preflight

```json
{
  "modelId": "model-*",
  "profileId": "profile-production",
  "overrides": {},
  "safetyMargin": 0.1
}
```

Do not launch when `launchAllowed` is false unless the operator explicitly acknowledges the returned allocation risk and the request sets `allowUnsafe:true`.

### Runtime launch

```json
{
  "modelId": "model-*",
  "profileId": "profile-production",
  "overrides": {},
  "readinessTimeoutSec": 45,
  "allowUnsafe": false
}
```

### Runtime stop / shutdown

```json
{
  "drainTimeoutSec": 30,
  "timeoutSec": 10,
  "force": false,
  "shutdownControlServer": false
}
```

### Settings

The complete object is required:

```json
{
  "paths": {
    "applicationRoot": "<value returned by GET /api/v1/settings>",
    "modelSources": ["C:\\Models"],
    "llamaServerPath": "C:\\llama.cpp\\llama-server.exe"
  },
  "ports": {
    "dashboard": 8088,
    "openaiGateway": 1234,
    "ollamaGateway": 11434,
    "workerController": 50053,
    "rpc": 50052
  },
  "runtime": {
    "bindAddress": "127.0.0.1",
    "pollIntervalMs": 5000,
    "requestDrainTimeoutSec": 30
  },
  "safety": {
    "blockUnsafeLaunch": true,
    "allowRemoteDashboard": false
  }
}
```

The control plane is fixed to `127.0.0.1:8088`. Do not present dashboard host/port or remote-control settings as applied when the backend rejects them.

## Job handling contract

Scan, runtime launch, runtime stop, RPC lifecycle, and action execution return HTTP `202` with a job object:

```json
{
  "id": "job-*",
  "type": "runtime.launch",
  "state": "queued",
  "phase": "validate",
  "progress": 0,
  "phases": [],
  "evidence": [],
  "error": null,
  "createdAt": 0,
  "updatedAt": 0,
  "simulation": false
}
```

Poll `GET /api/v1/jobs/{id}` until `state` is `succeeded` or `failed`. A `202` response means accepted/queued, **not completed**. Use `phase`, `progress`, `evidence`, `result`, and `error` in the UI.

## Local agent execution task

1. Inspect the current branch and verify the source fingerprints above.
2. Preserve the standalone visual design, but integrate it into the repository-authoritative frontend (`web/index.html`, `web/js/*`, `web/css/*`). Do not replace the backend.
3. Create one API adapter module. Route all control-plane calls through it; keep raw compatibility fetch handling separate.
4. Remove prototype route constants and scattered direct control-plane `fetch()` calls.
5. Hydrate runtime, gateway, models, machines, profiles, settings, telemetry, jobs, logs, and extensions on startup.
6. Keep only view preferences and unsaved drafts in local storage.
7. Implement shared job polling with abort, timeout, terminal-state handling, and evidence display.
8. Implement restart and swap as proven compositions; do not invent routes.
9. Convert local profile, settings, machine, and extension mutations into backend CRUD.
10. Preserve truthful UI states: queued, running, succeeded, failed, unverified, and unsupported must remain distinct.

## Acceptance gates

- `npm run validate` passes.
- No prototype-only route remains in active UI code.
- No backend-owned state is initialized from hardcoded demo values after hydration.
- Runtime active model, PID, port, and readiness are shown only from `/api/v1/system/status`.
- Every async action remains pending until its job reaches a terminal state.
- Model results are refetched only after a scan job succeeds.
- Machine tests use registered machine IDs.
- Settings persist across control-plane restart.
- OpenAI streaming and non-streaming chat both work.
- Ollama role-message chat works through `/api/chat`.
- Browser stream abort and backend cancellation are reported separately.
- Restart and swap contain no fake endpoint or optimistic success claim.
- Real Windows acceptance is run with `run.bat`, `test.bat`, a real GGUF scan, real preflight/launch, chat, stop, and two-machine controls where available.
