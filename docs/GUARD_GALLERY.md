# Guard Gallery

## Environment Contract Guard

Command:

```powershell
npm run guard:env
```

Authority: `scripts/env-contract-guard.js` scans production Python and JavaScript for environment-variable reads and requires each declared name to appear in `env.example`.

Current contract:

| Variable | Required | Purpose |
| --- | --- | --- |
| `LB_LLAMA_SERVER` | No | Optional absolute `llama-server` executable path. |

This guard prevents undocumented configuration. It does not require optional values to be set, provide authentication, enable remote control, or change listener ports. The control plane remains fixed to `127.0.0.1:8088`.

## Validation Entry Point

```powershell
npm run validate
```

This runs the environment contract guard followed by the existing Python and JavaScript validation suite.
