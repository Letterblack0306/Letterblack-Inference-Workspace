<<<<<<< HEAD
# Letterblack Local Inference Workspace — Phase 6

Phase 6 adds **declarative extensibility and user-defined operational actions** to the Phase 5 hardware-safe runtime. It keeps the approved HTML/UX, real runtime integration, gateway, request lifecycle, GGUF inspection, and telemetry layers.

## Run

```powershell
.\run.bat
```

Open `http://127.0.0.1:8088`.

## Verify

```powershell
.\test.bat
```

The package was validated with 24 unit tests, Python compilation, JavaScript syntax checks, API installation smoke tests, registry merge checks, and a real background action-job smoke test.

## Phase 6 capabilities

### Declarative extension manifests

Extensions can register:

- Workspace widget definitions
- Permission-bound custom actions
- Controlled HTTP endpoint definitions
- Settings schemas and sizing metadata

Extensions **cannot** load Python, JavaScript, PowerShell, executables, arbitrary commands, or remote shell entrypoints. Phase 6 rejects executable-code fields in extension manifests.

Use `examples/sample-extension.json` as the reference manifest.

### User-defined actions

Supported action types:

- `models-scan`
- `controller-status`
- `rpc-start`
- `rpc-stop`
- `http-request`
- `profile-select`

Every action declares its required permission. Execution creates a structured background job containing validation, execution, verification, evidence, result, and error state.

### Controlled custom endpoints

HTTP actions cannot call an arbitrary URL directly. They must reference a registered endpoint. Endpoints have explicit base URLs, health checks, enabled state, and structured test results.

### Extension lifecycle

- Install a JSON manifest
- Validate API compatibility and permissions
- Detect widget, action, and endpoint ID conflicts
- Enable or disable an extension
- Uninstall cleanly
- Dynamically merge enabled extension assets into registries

## New routes

```text
GET    /api/v1/actions
POST   /api/v1/actions
GET    /api/v1/actions/{actionId}
PUT    /api/v1/actions/{actionId}
DELETE /api/v1/actions/{actionId}
POST   /api/v1/actions/{actionId}/execute

GET    /api/v1/extensions
POST   /api/v1/extensions
GET    /api/v1/extensions/{extensionId}
PUT    /api/v1/extensions/{extensionId}
DELETE /api/v1/extensions/{extensionId}

GET    /api/v1/endpoints
POST   /api/v1/endpoints
PUT    /api/v1/endpoints/{endpointId}
DELETE /api/v1/endpoints/{endpointId}
POST   /api/v1/endpoints/{endpointId}/test
```

`GET /api/v1/widgets/registry` now merges enabled extension widget declarations with core widgets.

## UI additions

The Extensions page now supports:

- Importing extension JSON manifests
- Reviewing declared permissions and registered assets
- Enabling, disabling, and uninstalling extensions
- Creating safe custom actions
- Registering and testing custom endpoints
- Running actions as visible background jobs

## Contracts

```text
contracts/action.schema.json
contracts/endpoint.schema.json
contracts/extension.schema.json
contracts/openapi.json
```

State schema is upgraded to version 6 and preserves Phase 5 data during migration.

## Security boundary

Phase 6 does not permit:

- Arbitrary shell commands
- Free-form local script execution
- Extension-provided executable code
- HTTP actions with raw unregistered target URLs
- Undeclared permissions
- Hidden endpoint or widget registration

The earlier UI wording “approved local script” has been removed from the working action builder because no signed script registry exists yet. Such a registry would require a separate security contract and acceptance phase.

## Remaining work

Phase 6 is not the final public release. The major remaining items are:

- Real two-machine Windows acceptance testing
- Installer and Windows service packaging
- Extension signature/trust model if executable extensions are ever introduced
- Remote model acquisition
- GBNF studio
- Backup/recovery and schema migration UI
- Full accessibility and multi-breakpoint acceptance
=======
# Letterblack Inference Workspace

Local and distributed AI runtime control for GGUF inference.

## Repository status

This repository currently contains the clean project scaffold. Runtime code should be imported from the validated local source only after fake/demo handlers are removed and the truthful UI audit passes.

## Structure

```text
backend/     Python control-plane and runtime services
web/         Browser UI and API-driven frontend
contracts/   JSON schemas and API contracts
tests/       Automated tests
examples/    Declarative extension and profile examples
docs/        Architecture, operations, and acceptance records
scripts/     Validation, packaging, and maintenance tools
```

## Validation policy

A feature is not considered operationally validated until the relevant unit, API, browser, host, worker, llama-server, and gateway checks have actually been executed. Missing validation must be reported explicitly.
>>>>>>> f59e44d6618350b661a43d817fc082e29a63ef02
