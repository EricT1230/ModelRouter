# Effort and budget policy

These policies apply to routed work. Reuse effective user, host and selected-workflow limits before applying package fallbacks; do not impose another approval cycle on ordinary local fixes. Supplied planner policies and lifecycle limits remain binding for that plan. Record the source of effective limits before dispatch; do not erase usage or loosen a limit merely to pass a check.

Here, routed work means a deliverable using child dispatch or an explicit structured planner policy. Merely loading the skill, discussing a route, or choosing to continue with the parent does not activate package iteration limits. Once a routed deliverable has effective limits, parent/child handoffs do not reset its counters. If a required routed recheck discovers a material new failure, preserve it and repair within the remaining effective allowance; when that allowance is exhausted, report incomplete and obtain the required extension. Do not treat a failed recheck as acceptance.

Model suitability, reasoning effort and orchestration are separate axes. Use current host-supported native values and current semantic descriptions. Do not assume that one model's high equals another model's medium, or that any effort has a fixed token multiplier.

These choices are subject to the actual host's dispatch schema and applicable instructions. Explicit overrides are useful only where permitted. Legal inheritance may be necessary; record it and any unknown effective settings instead of claiming that the semantic target changed the parent's or child's effort.

## Semantic effort selection
low: mechanical low-risk work with clear expectations.
medium: normal implementation, coordination, routine bounded review.
high: architectural/causal reasoning, meaningful edge cases or high-risk review.
xhigh: a concrete deep issue that warrants extended analysis.
max: a named exceptionally difficult reasoning bottleneck.
ultra: exceptional reasoning where that native option has been confirmed; its orchestration implications must be identified and bounded.

For exceptional tasks, the default is max. Ultra may be proposed when at least two difficult independent tracks are explicitly supported by evidence, or when the user expressly requests it and its reasoning/orchestration semantics are known. This is this package's conservative spending policy, not a claim that Ultra universally requires two subagents. A host that exposes ultra as reasoning-only may run it without parallelism. A host that lets it create descendants requires effective global descendant/depth controls and auditability; a prompt saying "only two" is not an enforced cap.

Unknown semantics or uncontrolled automatic spawning means ULTRA_CONTROL_UNCONFIRMED; offer a separately labeled max/controlled-parallel route. Explicit multi-agent work under medium/high is supported when the host exposes dispatch. Do not call that native Ultra.

max/ultra can be the initial choice for a justified exceptional phase. One executed exceptional stage is allowed by default across the entire deliverable; attempts count even when they fail. One autonomous capability escalation is allowed. A direct initial exceptional choice uses the exceptional allowance but is not itself a retry/escalation. Any larger allowance needs a recorded user-approved budget change.

## Avoid excessive review
Reuse the selected lifecycle's acceptance and eligible reviewer; freeze any missing acceptance before implementation. Review correctness, required behavior, security boundaries, changed dependencies and meaningful test sufficiency. No quota of findings. Style and speculative redesign are nonblocking unless originally required. A blocking finding needs a criterion/invariant, location, consequence, and either a reproduction or a concrete execution-path explanation. Credible severe uncertainty remains unresolved until examined.

Where the selected workflow supplies no review budget, plan one initial review, one consolidated repair, and one focused recheck for a routed deliverable. This fallback is not a requirement to add reviews or to stop ordinary parent-led work after its first implementation. Existing required integration gates remain. Preserve failures and earlier findings. Reopen a resolved issue only for new material evidence. A tool retry for a documented transient outage is not an excuse for a new full reasoning pass. Limit retries under the shared task ledger.

When checks fail, repair the cause or report failure. Do not expand into a full-repository audit without a concrete affected path or user-requested scope. Reusing evidence requires the same relevant candidate, test/runner version, dependencies, environment and data; an old green check alone is insufficient.

For the package fallback, one consolidated repair round spans the fixes and local checks after a consolidated review until the next independent recheck. Local edit/test cycles are not separate repair rounds. An applicable workflow's round definition takes precedence; separate execution-attempt or exceptional-stage limits still count attempts as specified, even inside a repair round.

## Honest budget accounting
Track parent and all descendants, including failed attempts, model reasoning and tool calls. Actual host metering wins. Record total, cached input and reasoning components without adding subcomponents twice. API tokens, subscription messages/limits, credits, currency, elapsed time and machine execution time are separate metrics.

Reserve capacity for mandatory validation before optional depth or parallelism. Do not measure remaining budget by token guesses when the host cannot report it. Use procedural limits and disclose that they are not hard enforcement. No fabricated actual cost, no unmeasured savings percentage.

Record the provenance of each limit: host-enforced constraint, user-approved budget, or package procedural default. Effective limits remain shared across the routed deliverable, including lifecycle work that fulfills a routed phase; package defaults fill only missing limits. For Max/Ultra, `route.py` checks the supplied ledger's task identity and exceptional_stages_used, returning `BUDGET_BLOCKED` when that allowance is exhausted. With optional structured lifecycle data it also checks correction-round allowances and capability escalation thresholds, requiring fresh context on escalated corrections. See [formats.md](formats.md). It does not persist counters or authenticate supplied records. The coordinator maintains the full history and checks review, repair, recheck, escalation and active-child counts. Only actual host controls justify a claim of enforced spending, concurrency, or descendant limits.

When the allowance is exhausted and necessary work remains, return INCOMPLETE/BLOCKED with a bounded request for extension. Do not silently omit checks, lower acceptance, or reset counters through a renamed phase or a new model.
