# Evidence-based, independent verification

Use this reference for required independent acceptance or disputed evidence. The task and selected workflow determine required checks and review; this reference does not create a new gate for every edit or routine answer. Keep records proportionate and reuse valid existing evidence.

## Freeze the meaning of success
Reuse original requirements, acceptance IDs and required checks from the selected lifecycle; add only what is missing. Before edits, bind them to protected tests/expectations, runner settings and relevant data kind. Inventory existing failures. Snapshot the complete candidate (including uncommitted/untracked relevant files), tests, dependencies, runner and environment identifiers; a Git HEAD alone does not identify a dirty worktree. Record independently approved contract changes explicitly; revalidate after changing the candidate.

Unit fixtures and mocks are useful when labeled and appropriate. They do not substitute for required real database/network/end-to-end integration. If a dependency is unavailable, report the relevant check BLOCKED and keep the failure evidence. In research, preserve actual source references, extraction and calculation inputs; distinguish estimates/inferences from observed facts. Do not manufacture quotations, dates, rows or sample observations.

## Roles and trust
The author may write meaningful unit tests and self-test. The author cannot grant independent final approval, edit protected acceptance to fit a wrong output, add skip/xfail/only filters to escape failure, relax thresholds, replace snapshots, suppress a nonzero exit code, or rewrite runner logs. Legitimate test errors can be corrected with a distinct approval and rerun; never silently freeze an incorrect test forever.

The reviewer gets fresh context with original requirements, candidate/diff, relevant surrounding code and raw artifact access. A full or partial fork carrying the author's rationale/history is not clean independence. Confirm the current dispatch API's no-history and override compatibility rules before sending the request; see [runtime.md](runtime.md). Otherwise disclose the weaker separation. The same model family in different fresh contexts provides procedural independence, but correlated errors remain. A different family is not automatically better and does not prove isolation.

A lifecycle reviewer can satisfy this gate when it did not author the candidate/design and meets the required context, capability and evidence conditions. Reuse that review for its bound candidate; do not order a second independent review just because routing was added. Revalidate only changed or invalidated evidence while retaining required checks.

Reviewers report findings and stay read-only. If they author a patch, obtain a new independent evaluator for that patch. The PM checks coverage and blockers rather than duplicating the review; if the PM authored code/design, it cannot supply the missing independent approval. A human or protected CI evaluator can satisfy a suitable independent gate when an agent cannot.

## Execution evidence
For each required check preserve actual command/arguments, cwd, candidate and protected baseline, data kind, exit code, stdout/stderr, structured report if available, and runner-supplied identifiers/time. Observe zero tests, missing required cases, unexpected skips, swallowed errors, stale reports, filtered suites, and test runner mutations. For a regression fix, reproduce on the faulty baseline when safe and feasible, then show the actual fixed result; label inability to reproduce honestly. A tiny smoke test does not prove full integration.

The evidence_gate helper checks consistency of supplied artifacts and JUnit details, not execution authenticity. A command-only receipt with exit 0 cannot establish arbitrary semantic correctness. Choose an appropriate structured test oracle and independently examine commands. An adversary able to forge every record and hash can satisfy a consistency checker; real protection requires a trusted runner and protected evidence outside the author's write permission.

## Levels to disclose
self-check: author verified their own work; no independent acceptance.
procedural separation: distinct fresh reviewer, permissions not enforced or not independently established.
enforced isolation: actual host/OS/CI controls protect candidate/acceptance/evidence and attest the relevant execution boundary.

Never infer enforcement from a requested read-only setting. Parent live overrides can change child permissions. Tests may need writable build/temp directories; protect inputs while allowing those outputs in a separate runner. If integrity is suspect, stop acceptance, preserve artifacts, restore a trusted baseline with authorization and rerun required checks under a trusted boundary. Additional model debate alone cannot repair forged provenance.

## Final states
VERIFIED_IN_SCOPE: all required real checks and the required independent review completed for the bound candidate, no unresolved blockers, with exact scope/protection limits stated.
FAILED: a required executed check/criterion failed.
BLOCKED: missing environment/data/access prevents required work.
INCOMPLETE: remaining required review/execution, budget exhaustion or missing adequate independence.
INTEGRITY_FAILURE: acceptance/runner/evidence tampering or credible authenticity failure.

EVIDENCE_COMPLETE is only the helper's consistency result. It must never be substituted for VERIFIED_IN_SCOPE. Verified scope is not a bug-free guarantee. Missing verification or an unauthorized waiver cannot become a pass.

## Skill delivery itself
The package's own author-run unit tests are self-tests. A separate function named reviewer, a second reasoning pass, or a prose statement does not establish independent review. Do not certify installation or live dispatch before observing it in the target host.
