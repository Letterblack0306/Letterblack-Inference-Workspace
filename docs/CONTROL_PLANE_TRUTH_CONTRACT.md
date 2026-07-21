# Control-Plane Truth Contract

## Status

This contract is normative for the operator UI and backend. It prevents saved configuration from being presented as applied runtime state.

## Configurable areas

The control plane separates these areas:

1. Nodes and network links
2. Model libraries and local model replicas
3. Provider and model endpoints
4. Routing policy: `primary`, `fallback`, `parallel-request`, and `benchmark-only`
5. Runtime launch profiles
6. Gateway and listener settings
7. UI workspace and layout preferences

Cross-machine GPU sharding is not an available routing policy unless a runtime explicitly reports distributed tensor execution. Parallel requests, failover, and benchmark routing must never be labeled as pooled VRAM or combined GPU inference.

## Three-state rule

Every configurable value must expose:

- `saved`: persisted desired configuration
- `applied`: value currently used by a running process or verified listener
- `requiredAction`: one of `none`, `apply`, `restart`, or `test`

A saved value is not proof that it is applied.

## Listener truthfulness

A URL may be shown as `available` only when:

1. the relevant listener has reported its applied host and port;
2. a health or compatibility test has passed against that exact address;
3. the result has a timestamp and expires after a defined freshness interval.

Until then the UI must display `Not verified` or `Unavailable`. Copy controls must be disabled for unverified addresses.

The current startup command launches one control-plane server. Separate dashboard, OpenAI, and Ollama ports must not be presented as independently applied unless separate listeners are actually started and verified.

## Validation areas

Each validation run has an explicit area and test type:

- `network.direct-link`: latency, reachability, and bandwidth
- `provider.health`: provider health and authenticated model listing
- `model.replica`: path, size, and hash verification per node
- `runtime.smoke`: preflight, launch, and inference smoke test
- `gateway.openai`: OpenAI-compatible request test
- `gateway.ollama`: Ollama-compatible request test
- `routing.primary`: primary route test
- `routing.fallback`: failover test
- `routing.parallel-request`: concurrent independent request test
- `routing.benchmark-only`: comparative benchmark test

## Durable audit runs

Validation runs are append-only records stored outside mutable runtime state. Each record contains:

- immutable run ID
- schema version
- area and test type
- redacted configuration snapshot
- target
- command or request summary
- start and finish timestamps
- duration
- response status
- latency and tokens per second when returned
- evidence
- result: `pass`, `fail`, or `unknown`
- retest relationship

Secrets, authorization headers, API keys, tokens, cookies, passwords, and credential-bearing URLs must be redacted before persistence or export.

## Profile lifecycle

A complete profile lifecycle requires backend contracts for:

- create
- edit
- duplicate
- validate
- benchmark
- activate
- delete
- command preview

Profile IDs are immutable. The UI must not expose lifecycle actions whose backend contracts do not exist. A command preview must be shown before launch.

## Release boundary

Static tests can validate route presence, schema behavior, redaction, and truthful labels. They cannot prove two-machine networking, provider authentication, model loading, inference, routing, or parallel execution. Those require live acceptance against the actual laptop and desktop endpoints.
