# Local routing measurements

Use this mode only when the user wants routing outcomes recorded or compared.
The helper is explicit local state, not a hook or telemetry service. It makes no
model calls and does not read prompts, credentials, repositories, or provider
logs. The caller supplies already-observed aggregate values.

## State and data boundary

Choose a private host-scoped directory, normally beneath
`$CODEX_HOME/modelrouter-state/<host-scope>/`. Initialize it explicitly:

```text
python -B scripts/routing_metrics.py init --state-root PATH --host-scope HOST_SCOPE
```

Initialization creates only `state.json`. It refuses linked/reparse paths and a
non-empty directory that lacks the state marker. The path checks reduce mistakes;
they are not a security boundary against a process that can race or rewrite the
same user's files. Keep state outside implementer write access where evidence
integrity matters.

Copy `templates/metrics-event.json`, replace every placeholder, then record it:

```text
python -B scripts/routing_metrics.py record --state-root PATH --input EVENT.json
```

Each stable event ID maps to one atomically published file. Repeating identical
content is idempotent; different content with the same ID fails. Events reject
unknown fields and bounded strings reject newlines. Do not put prompts, source
code, credentials, personal data, or arbitrary notes in these records.

`total_tokens` is the host-observed aggregate for the complete parent-and-child
task outcome. Components are informational and are never added to derive the
total because providers differ on cached and reasoning-token inclusion. Unknown
values stay null. Any observed aggregate usage needs a `source_ref` to the host
receipt or retained evidence. Credits, currency cost, latency, and tokens remain
separate measures.

An accepted outcome requires an evidence reference. `verification_level` records
self-check, procedural separation, or enforced isolation; it does not upgrade the
underlying evidence. Use opaque host/evidence scopes rather than private project
names when the state could be reused across workspaces.

## Read-only reports

Summary writes nothing unless an explicit output is supplied:

```text
python -B scripts/routing_metrics.py summary --state-root PATH
```

Totals include failed, blocked, and incomplete task cost; the denominator is
accepted tasks. This prevents a route from looking cheap by discarding failed
attempts.

Compare matched routes with the same evidence scope, task bucket, risk, and
verification level:

```text
python -B scripts/routing_metrics.py compare --state-root PATH \
  --evidence-scope SCOPE --task-bucket BUCKET --risk low \
  --verification-level self-check --baseline-route BASELINE \
  --candidate-route CANDIDATE --min-accepted 3
```

The default three accepted tasks per route is an operational minimum, not
statistical proof. A comparison also requires complete `total_tokens` coverage.
The result is limited to the matched recorded sample; it cannot establish cause,
future savings, model quality outside the bucket, or universal superiority.
Profiles change only through the separately reviewed calibration process.
