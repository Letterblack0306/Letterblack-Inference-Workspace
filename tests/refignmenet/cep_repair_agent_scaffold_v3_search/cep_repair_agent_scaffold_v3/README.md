# CEP Repair Agent

A constrained, local CEP code-repair service for one workspace.

## What it does

- Starts in read-only trace mode.
- Scans one configured CEP workspace.
- Reads governance rules from `governance.json`.
- Blocks access outside the configured workspace.
- Blocks edits outside allowed paths.
- Blocks forbidden file patterns and commands.
- Runs only explicitly allowed validation commands.
- Stores only verified repair records in `memory/verified_repairs.jsonl`.
- Exposes a small local HTTP API and CLI.

## Important boundary

This is an application-level constraint layer, not a hostile-code security sandbox.
Run it under a dedicated OS user or container if untrusted code may execute.

## Requirements

- Python 3.11+
- A CEP project workspace
- Optional OpenAI-compatible local model endpoint such as LM Studio

No third-party Python packages are required.

## Setup

1. Copy `config.example.json` to `config.json`.
2. Set `workspace_root` to the current trusted CEP project.
3. Update `governance.json`.
4. Run the read-only trace:

```powershell
python agent.py trace
```

5. Review `state/workspace_trace.json`.
6. Start the local API:

```powershell
python server.py
```

The API binds to `127.0.0.1` only.

## CLI

```powershell
python agent.py trace
python agent.py inspect path/to/file.js
python agent.py validate
python agent.py propose --issue "Panel button does not call JSX"
python agent.py apply state/latest_proposal.json
```

`apply` is blocked unless:

- `write_enabled` is true;
- the patch only touches allowed paths;
- no forbidden pattern is matched;
- the proposal includes a base SHA-256 for each edited file;
- all required validation commands pass.

## API

- `GET /health`
- `POST /trace`
- `POST /inspect`
- `POST /propose`
- `POST /apply`
- `POST /validate`

Example:

```json
{
  "issue": "evalScript callback returns malformed JSON"
}
```

## Expected CEP repair cycle

```text
trace workspace
→ retrieve relevant files and verified repairs
→ inspect governance
→ produce bounded proposal
→ review proposal
→ apply guarded patch
→ run required checks
→ store verified result
```


## Version 2 changes

The tracer now reads arbitrary nested historical folders inside the configured dump root.

- `allowed_read_paths` defaults to `["."]`.
- `.git`, `node_modules`, and `_FILTER` remain excluded.
- Write permissions remain restricted by `allowed_write_paths`.
- Trace output includes `file_count` and `top_level_groups`.

This version performs read-only inventory and hashing. It does not yet infer version lineage or classify failed/passed snapshots.


## Version 3: read-only historical retrieval

Search the dump without enabling the model or writes:

```powershell
python .\agent.py search "evalScript callback"
python .\agent.py search "manifest host version" --max-results 25
python .\agent.py search "CSInterface" --extensions js,jsx,md,json
```

Search output is also written to:

```text
state/last_search.json
```

Local API endpoint:

```text
POST /search
```

Example body:

```json
{
  "query": "evalScript callback",
  "max_results": 25,
  "extensions": [".js", ".jsx", ".md"]
}
```

This is the intended minimal next step: retrieve relevant historical evidence on demand. It does not build lineage, train a model, classify every snapshot, or edit the dump.
