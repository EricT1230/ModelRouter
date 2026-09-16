# Optional gate input format (schema_version 1)

Load this reference only when integrating `scripts/evidence_gate.py`. The host/CI owns these records; the implementing model must not fill a receipt by guessing. The matching release repository (not the installed skill) contains the synthetic factory in `tests/test_evidence_gate.py`. Those records deliberately do not claim to be real runs.

Invoke from the skill directory:

```sh
python scripts/evidence_gate.py --manifest /trusted/manifest.json --receipt /runner/receipt.json --artifacts /runner/artifacts
```

The tool reads files only. It does not run the tests, call models, install permissions, or contact any network service. Python 3.10 or newer is required. Exit 0 means internally consistent evidence; exit 1 means rejected evidence; exit 2 means input/IO failure. Do not use exit 0 as sole deployment authorization.

## Manifest (frozen by trusted orchestration)

Required keys:

- `schema_version`: integer 1.
- `task_id`: nonempty task identifier.
- `candidate_snapshot`: identity of the exact final candidate, supplied after freezing it.
- `protected_baseline`: identity of the separately approved acceptance tests/configuration.
- `author_ids`: nonempty list of actual author thread/actor IDs, including the designer if the design itself is being reviewed.
- `acceptance_ids`: nonempty list of criterion IDs.
- `minimum_isolation`: `procedural_only` or `runtime_enforced`. Enforced isolation requires external confirmation; the tool can only compare declared metadata.
- `checks`: nonempty array of check specifications.

Each check specification includes `id`, `kind` (`command` or `junit`), exact `argv` array, `cwd`, `data_kind`, and `acceptance_ids`. The union of its acceptance IDs must cover the manifest. Specify `junit` for a test check; `command` is for non-test gates such as a build or type check. Do not downgrade a test check to `command` to evade test-count validation.

For `junit`, also specify `minimum_executed` (positive integer, default 1), `required_cases` (list), and `allowed_skipped_cases` (list, default empty). Test identities are `classname::name`. A required case may not be skipped. Preapproved optional/platform skips are permitted only outside required cases and with enough executed tests. Duplicate testcase IDs or unsupported XML/report conventions require an explicit trusted adapter; do not silently discard records.

The frozen manifest is an acceptance boundary. Changes require independent approval, a new revision, and appropriate revalidation. Candidate and baseline identities are opaque to this tool; trustworthy binding is the host's responsibility.

## Receipt (generated from actual execution and review)

Required top-level keys: `schema_version`, `task_id`, `run_id`, `runner_id`, `snapshot_before`, `snapshot_after`, `protected_before`, `protected_after`, `checks`, and `review`.

The snapshot fields must match the manifest candidate; protected fields must match its baseline. Actual `checks` must have exactly the manifest's check IDs; keep prior attempts/history separately without erasing them.

Each check repeats `id`, `kind`, `argv`, `cwd`, and `data_kind`; adds `candidate_snapshot`, `status` (`passed` to be eligible), integer `exit_code`, `stdout` and `stderr`; and includes `report` for JUnit checks.

Each artifact reference has a relative `path` beneath the artifact directory and the lowercase 64-character `sha256` of the original bytes. Both stdout and stderr files are required, including an empty stderr file when appropriate. Preserve full logs securely; do not expose secrets in public summaries. JUnit must enumerate actual testcases and maintain consistent suite counts. Zero tests, failures/errors, unapproved skips, or missing required cases fail the gate.

The review object contains `reviewer_id`, `candidate_snapshot`, `verdict`, `blocking_findings`, `acceptance_ids`, `isolation`, and a `report` artifact reference. Acceptance requires a reviewer ID distinct from all authors, verdict `accept`, an explicit empty blockers list, and complete criterion coverage. These identity/verdict declarations need independent provenance; string comparisons do not authenticate them.

The host's full execution receipt should retain timestamps, environment/runtime/dependency versions, source/data provenance and original CI links too. The small gate does not independently verify those details.

## Scope of the result

Every result includes `authenticity: NOT_AUTHENTICATED_BY_THIS_TOOL` and `semantic_correctness: NOT_ESTABLISHED_BY_THIS_TOOL`. Even mutually consistent fabricated records can satisfy a consistency checker. Use external runner identity, immutable evidence storage, protected manifests, and independent substantive review before granting acceptance.
