<<<<<<< HEAD
# Letterblack Inference Workspace — Truthful UI v1

This folder is a complete replacement for `web/`.

## Properties

- No `state.js`, prototype `app.js`, prototype `ux.js`, or timer-simulated jobs.
- One active frontend controller: `js/app.js`.
- Operational values are loaded from `/api/v1/*`.
- Missing evidence renders as unknown, unavailable, empty, or stopped.
- Machine tests, RPC operations, model scan, runtime preflight/launch/stop, requests, logs, telemetry, profiles, gateway, workspaces, extensions, actions, and endpoints use backend APIs.
- No fabricated model counts, machine counts, latency, throughput, VRAM, request IDs, or readiness states.

## Install

Stop the server. Back up the current `web` folder, then replace it with this folder.

```powershell
Rename-Item "Z:\LLM_Proxy\ControlUI\web" "web-before-truthful-ui"
Copy-Item ".\Letterblack-Inference-Workspace-UI-Truthful-v1" "Z:\LLM_Proxy\ControlUI\web" -Recurse
```

Then:

```powershell
node --check "Z:\LLM_Proxy\ControlUI\web\js\api.js"
node --check "Z:\LLM_Proxy\ControlUI\web\js\app.js"
cd "Z:\LLM_Proxy\ControlUI"
.\test.bat
.\run.bat
```

Hard refresh with `Ctrl+F5`.

## Validation boundary

This UI is structurally API-driven. It does not prove that the Windows worker controller, GPUs, llama-server launch, or inference gateway have passed real hardware acceptance.
=======
# Web

Browser-based control interface.

Operational values must come from `/api/v1` evidence. Loading, unknown, unavailable, and offline states must never be replaced by fabricated success data.
>>>>>>> f59e44d6618350b661a43d817fc082e29a63ef02
