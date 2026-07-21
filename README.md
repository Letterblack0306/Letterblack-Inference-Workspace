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
