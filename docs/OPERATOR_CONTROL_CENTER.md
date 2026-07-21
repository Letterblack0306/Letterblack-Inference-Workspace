# Operator Control Center

This change replaces the passive Overview dashboard with a task-oriented control surface.

## Primary workflow

1. Add a model source directory.
2. Scan for GGUF models.
3. Select a discovered model.
4. Optionally create and select a launch profile.
5. Run backend preflight and launch the runtime.
6. Send a real OpenAI- or Ollama-compatible chat request.
7. Inspect request state, latency, route, request ID, and raw response.

## Included controls

- Chat-first default page with model, profile, gateway, endpoint, start, send, and stop controls.
- Guided setup page.
- Editable model source list backed by the settings API.
- Model actions for Chat and Launch.
- Runtime status, PID, endpoint, launch, and stop controls.
- Machine create, edit, delete, test, RPC start, and RPC stop controls.
- Gateway endpoint cards with full URLs, copy, test, and editable ports.
- Richer GPU telemetry including utilization, VRAM, temperature, power, driver, and timestamp.
- Profile creation for reusable llama.cpp launch parameters.
- Logs moved to a dedicated troubleshooting page.

## Validation boundary

The UI does not simulate model discovery, runtime launch, machine state, chat responses, or telemetry. Controls call the existing backend and compatibility routes. Hardware acceptance still requires a real GGUF model, llama-server executable, reachable machines, and a successful inference request.

## Remaining follow-up

- Profile update, duplicate, delete, command preview, and fit estimation.
- Structured model-source CRUD API and native folder/file picker support.
- Explicit gateway enable/disable policy contract.
- Persistent telemetry history and charts.
- Exact token usage and TTFT from backend request metrics.
