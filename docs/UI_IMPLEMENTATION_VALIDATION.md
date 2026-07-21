# UI Implementation Validation

## Scope

This validation compares the committed operator UI, frontend API client, repository documentation, and verification script on branch `fix/validated-ui-contract`.

The goal is to distinguish implemented behavior from planned or historical behavior. This document does not claim real runtime acceptance unless the relevant command or hardware workflow has been executed successfully from a clean checkout.

## Authoritative frontend

The active page is `web/index.html` and the active application entrypoint is:

```text
web/js/app.js
```

The page loads:

```html
<script type="module" src="js/app.js"></script>
```

The current operator navigation is:

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

There is no dedicated Extensions page in the committed HTML.

## Verified implementation map

| Surface | Verified UI behavior | Current limitation |
|---|---|---|
| Chat | Model/profile/gateway selection, endpoint copy, real request submission, streaming and cancellation controls, request metadata | Requires real gateway/runtime acceptance |
| Setup | Readiness steps for sources, models, profiles, runtime, and chat | Successful test-chat completion is not persisted as a completed setup state |
| Models | Add/remove source paths, source scan, global scan, model listing, Chat and Launch actions | Source data is stored through general settings rather than a dedicated registry |
| Runtime | Status, active model, PID, endpoint, preflight, launch, stop | Advanced launch editor and command preview are incomplete |
| Machines | Create, edit, delete, test, RPC start, RPC stop | Bulk actions and richer role/state controls are absent |
| Gateways | Address display, copy, test, port editing | Auth, CORS, trusted hosts, enablement, and drain-policy editing are absent |
| Telemetry | CPU, system memory, request count, GPU VRAM, utilization, temperature, power, driver | No historical charts or TTFT/throughput time series |
| Profiles | List, create, select for Chat | Update, duplicate, delete, validation, fit estimate, and command preview are absent |
| Logs | Displays returned control-plane log records | Search/filter/export behavior is not complete |
| Settings | Loaded through the settings module and persisted through the settings API | Initialization is indirectly triggered from `api.js`, which should later be moved to `app.js` |

## API wiring confirmed by static inspection

The frontend API client exposes:

```text
GET/PUT settings
GET/POST/PUT/DELETE machines
machine test
RPC start/stop
GET models
model scan
GET/POST profiles
runtime preflight/launch/stop
jobs
telemetry
logs
requests and cancellation
gateway status
OpenAI-compatible chat
Ollama-compatible chat
```

## Verification correction

The previous `test.bat` referenced:

```text
web/js/phase6.js
```

That file is not the current frontend entrypoint and is absent from the active repository state. The script now validates every JavaScript file under `web/js/`:

```bat
for /R web\js %%F in (*.js) do @node --check "%%F" || exit /b 1
```

This prevents the verification command from silently drifting away from the committed frontend structure.

## Documentation correction

The previous README described a complete Extensions UI. The active HTML does not provide that page. The README now separates:

- Backend extension/action/endpoint contracts that may still exist
- Operator UI capabilities that are actually committed
- Remaining work that requires implementation or runtime acceptance

## UI consistency assessment

### Strengths

- Shared dark design tokens and state colors
- Consistent page headers, cards, buttons, badges, dialogs, and navigation
- Chat-first operator sequence
- Clear separation between ordinary operation and troubleshooting pages
- Truthful empty/loading states in the active HTML

### Debt

- Legacy CSS remains for obsolete dashboard widgets and topology layouts
- Some pages use cards while others use dense tables without a fully standardized action hierarchy
- Settings initialization is coupled to the API module
- Gateway behavior is still configured through generic settings rather than a dedicated contract
- Profiles do not yet match the depth of the runtime configuration domain

## Acceptance required before release-ready status

Run from a clean Windows checkout:

1. `test.bat`
2. Start the control plane with `run.bat`
3. Add a real GGUF source and complete a scan
4. Confirm GGUF metadata renders correctly
5. Run runtime preflight
6. Launch the configured llama-server executable
7. Complete a non-streaming OpenAI-compatible chat request
8. Complete a streaming OpenAI-compatible chat request
9. Cancel an active request
10. Complete an Ollama-compatible chat request
11. Stop and restart the runtime
12. Create, edit, test, start RPC, stop RPC, and delete a machine
13. Persist settings and verify them after restart
14. Validate responsive behavior at desktop, tablet, and narrow viewport widths
15. Validate keyboard navigation, dialog focus, labels, and contrast
16. Complete real two-machine Windows RPC acceptance

## Current verdict

The current UI is a real, partially complete operator console. It is no longer a static showcase, but it is not yet fully release-ready.

The repository documentation and verification script now describe the committed implementation truthfully. Runtime, hardware, responsive, and accessibility acceptance remain required before a final release claim.
