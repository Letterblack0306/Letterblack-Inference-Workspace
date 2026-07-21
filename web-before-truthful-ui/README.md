# Letterblack Local Inference Workspace — UX Prototype v2

Static HTML/CSS/JavaScript prototype. No npm dependencies.

## Added UX flows

- First-run guided onboarding
- Safe model launch wizard with validation and evidence phases
- Background job center with progress
- Safe unload flow with request drain/cancel policy
- Persisted first-run state and workspace save state
- Keyboard shortcuts: Ctrl/Cmd+K command palette, Ctrl/Cmd+S save
- Unsaved layout protection
- Guided actions that execute as verifiable jobs
- Existing multi-machine, widget, profile, API, telemetry and extension UI retained

## Run

```powershell
cd letterblack-inference-ux
python -m http.server 8088
```

Open http://localhost:8088

Reset onboarding in the browser console:

```js
localStorage.removeItem('lb-onboarded'); location.reload();
```
