# Helper formats and commands

All helpers require Python 3.10+ and only the standard library. They never install dependencies or create API keys. Run from the installed skill directory, or use absolute script paths. In Windows PowerShell, `py -3` may replace `python` when Python Launcher is installed.

## 1. Catalog (optional actual local CLI probe)
`python scripts/probe_models.py --codex ABSOLUTE_NATIVE_EXECUTABLE --codex-sha256 TRUSTED_SHA256 --output-root EXISTING_TRUSTED_DIRECTORY --output EXISTING_TRUSTED_DIRECTORY/catalog.json --host-scope DESCRIPTIVE_HOST_SCOPE`

V5.4 removes PATH lookup and the separate version subprocess. Select a reviewed native executable (on Windows, the actual .exe, not an npm .cmd shim), with an expected hash from a trusted installation. A hash supplied by the same untrusted source is not authentication. All linked/reparse ancestors are refused. The output must be JSON beneath an existing trusted root; replacement requires `--replace`. Use a private directory not writable by untrusted workers. Filesystems without hard-link support fail closed for new-file publication. Same-user filesystem races are not a guaranteed security boundary.

A successful file has schema_version=1, source {kind, source_ref, host_scope, observed_at, complete, session_bound}, and models. Each model has exact id, display_name, description, efforts [{value,description}], default_effort, input_modalities, hidden, and catalog_entry_sha256. Missing modality metadata conservatively yields text only. The default probe leaves session_bound=false: compare the active host/account/environment before binding. Preserve actual native effort values, including unknown future values.

If the existing host exposes equivalent metadata, normalize it to this schema. Use `common.normalize_model` for App Server shaped entries and `common.entry_digest` for the fingerprint. These functions are importable helpers; they do not authenticate a source. A complete catalog with no models is valid discovery but cannot authorize a route.

## 2. Role profiles (coordinator-created, evidence-backed)
`templates/profiles.EMPTY.json` starts intentionally empty. A profile is:

```json
{
  "id": "ACTUAL_OBSERVED_MODEL_ID",
  "catalog_entry_sha256": "ACTUAL_ENTRY_FINGERPRINT",
  "checked_at": "ACTUAL_CHECK_TIME_WITH_TIMEZONE",
  "basis": "documented",
  "source_refs": ["ACTUAL_OFFICIAL_DESCRIPTION_OR_EVALUATION_REFERENCE"],
  "capability_class": "generalist",
  "roles": ["implement"],
  "cost_band": "unknown",
  "effort_bindings": {"medium": "ACTUAL_SUPPORTED_NATIVE_VALUE"}
}
```

This is a structural illustration and must not be copied as a live profile. Classes: worker/generalist/reasoner/frontier. Roles: inspect/implement/architect/diagnose/review/research/answer. Basis: provisional/documented/evaluated. Cost: low/standard/premium/unknown. Known semantic effort keys: low/medium/high/xhigh/max/ultra. Native values can evolve; classify them using current evidence. A future native value can bind to a stable semantic slot without a code change. Brand-new semantics outside these slots require explicit policy review.

## 3. Task and route
Copy `templates/task.json`, fill real evidence and classification, then run:

`python scripts/route.py --task PATH/task.json --catalog PATH/catalog.json --profiles PATH/profiles.json --host PATH/host.json --ledger PATH/ledger.json`

Host and ledger arguments are optional for ordinary plans. Max/Ultra requires a task-bound exceptional-stage ledger; Ultra also requires actual host semantics/control evidence. The host file is descriptive input, not a tool connector or a permission grant. Planner exit 0 means PLAN_READY; any other route state/input error exits 2. No model call occurs. It outputs at most two alternative pairs to keep routine output bounded.

The task card remains a semantic judgment made by the coordinator, so task understanding still requires inspection and evidence. The script offers deterministic policy application, not an independently intelligent classifier. Profiles and card values cannot bypass actual host capability/permissions or verification.

## 4. Local routing outcomes

Read [metrics.md](metrics.md). `routing_metrics.py init` creates an explicit host-scoped state marker; `record` atomically adds one bounded event; `summary` and `compare` are read-only unless the caller supplies an output file and trusted output root. Unknown usage remains null. No command calls a model, dispatches an agent, reads prompts, or updates profiles.

## 5. Evidence consistency
Read evidence-format.md. Run:
`python scripts/evidence_gate.py --manifest PATH/manifest.json --receipt PATH/receipt.json --artifacts PATH/artifacts`

Exit 0 means EVIDENCE_COMPLETE consistency only; exit 1 rejects evidence, exit 2 reports input errors. It runs no commands, models or tests. The frozen manifest, actual runner and trustworthy raw artifacts must exist independently. See verification.md for authenticity and semantic acceptance boundaries.

## 6. Installed integrity and repository tests
`python -B scripts/verify_install.py` runs from the installed skill directory. It checks the versioned manifest and reports missing, changed or extra payload files. It does not run the regression suite or authenticate the publisher. A skill manager may inject tracking metadata into SKILL.md; this will correctly report changed bytes and requires inspection against the pinned source, not silently accepting a new manifest.

Full regression tests and the optional bridge are deliberately repository-only. Obtain the release repository/archive matching the installed manifest version, then run `python -B scripts/run_tests.py` from its root. Zero discovered tests cannot pass. Do not run the repository test command from an installed skill directory.

Tests use synthetic model records and a clearly marked fake protocol subprocess, plus temporary installer directories. They do not prove live model availability, role fitness, actual independent review, OS isolation, token savings, or target-host triggering.

## 7. Lifecycle context for corrections and reviews

Attach `lifecycle` to the task, copying effective rules from the selected workflow:

```json
{
  "deliverable_id": "stable-deliverable",
  "attempt_id": "unique-attempt",
  "stage_kind": "correction",
  "correction_round": 4,
  "max_correction_rounds": 5,
  "escalate_after_round": 3,
  "baseline_capability_class": "generalist",
  "source_ref": "approved-workflow-rule-reference"
}
```

These numbers are illustrative, not new defaults or authorization. Allowed stages: initial (round zero), correction (phase implement, round >= 1), review (phase review, round matching the candidate being reviewed). The baseline class is the original implementer's evidenced class. Rounds above the sourced allowance stop; corrections above the escalation threshold require a strictly higher class and fresh context. If no higher class exists, report NO_SUPPORTED_ROUTE. A fresh-context capability explicitly false returns DISPATCH_LIMITED. Unknown host settings remain unknown.

Use phase=implement and obstacle=none for ordinary correction; findings belong in evidence_refs. Integrity remains reserved for actual evidence-integrity concerns. The planner cannot extract policy from free-text goals. Missing lifecycle returns lifecycle_check=not_supplied; supplied limits return supplied_limits_only. The coordinator protects records, counts attempts and keeps the deliverable identity across retries. Neither JSON IDs nor hashes authenticate the records or enforce runtime counters.

Proposal outputs include selected_cost_band, cost_evidence_status, ranking_order and tie_break. Unknown cost produces cost_basis=unknown; equal candidates may be chosen by model_id_tie_break, which is not evidence of superiority or savings.
