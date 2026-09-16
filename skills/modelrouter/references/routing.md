# Minimal workflow and routing decisions

Apply the activation and lifecycle precedence in [runtime.md](runtime.md) first. Start from role, clarity, uncertainty, consequence, reasoning depth and evidence. Small code changes may alter authorization, deletion, financial logic or concurrency. Length is not risk.

## Decision order
Integrity concern → preserve artifacts and suspend acceptance.
Environment/input blocker → remedy it within authorization or report BLOCKED.
Material ambiguity → inspect available context, then ask the smallest necessary question.
Unknown routing-critical evidence → bounded inspection; expand only for a named missing fact.
Unclear implementation → define its contract/design before giving it to a small worker.
Clear implementation → parent or suitable worker/generalist, retaining the current workflow's required review.
Deep causal/architecture issue → reasoner/frontier reasoning phase.

A task card describes an existing phase; do not create a second phase plan or duplicate acceptance criteria. Mapping, writing, reasoning, testing and review may legitimately get different routes inside one deliverable. The coordinator maintains shared budget counters across phases; replacing the task-card file does not reset the task. `route.py` checks the supplied exceptional-stage count only for Max/Ultra and does not persist any counter. With structured lifecycle data, correction allowances and escalation thresholds are checked against the supplied round; the coordinator still maintains and protects all counters.

## Minimize handoff overhead
Use the parent directly for a short answer or a tiny edit when capable. When independent code review is required, reuse the lifecycle's qualified reviewer. When routing that review to a model, select a fresh reasoner-or-better reviewer suited to its scope. Loading the router does not add a review requirement to every edit. The parent may be both coordinator and implementer; it cannot be the independent approver of its own edit. Do not spawn another coordinator or repeat a completed eligible review solely for routing.

Delegate execution when the work is substantial enough, needs a different capability, isolates large context, or requires fresh review. Before spawning, identify which of those benefits applies. Do not claim numerical savings without comparable actual data. Avoid a dedicated agent just to reformat ten lines or run one existing check.

Code implementation does not automatically need an architect. Existing design/acceptance may suffice. Consequential new architecture requires independent evaluation, which may be covered by the final reviewer if no separate earlier approval gate was required. When a design decision is costly to reverse, review that decision before broad implementation.

## Parallelism
Use serial work for dependencies. Parallelize only independent investigations or disjoint edits with a known integration plan. The package defaults are at most two simultaneous children and no descendant dispatch. These are procedural policy limits unless the host enforces them; a prompt is not a global concurrency lock. Use limits already established by the user, host or selected workflow; package numbers are fallbacks for routed work, not an extra lifecycle. Record the source of each effective limit. A strong reviewer may run a focused test tool; no separate "test agent" is needed unless tool/environment isolation justifies it.

## Planner use
`route.py --task ... --catalog ... --profiles ... --host ...` returns a proposed route from records supplied by the host/coordinator. It does not understand natural language, call models, persist counters, or enforce permissions. RISK/DEPTH/EVIDENCE fields must reflect observed facts. Never write "known" to obtain a cheaper plan when uncertainty remains.

The planner filters unavailable/hidden models, unsupported modalities/efforts, stale or mismatched profiles, insufficient capability, unauthorized canaries, and invalid catalog scope. It sorts qualified candidates using profile evidence and documented cost bands. This is a conservative heuristic, not a learned optimizer.

Supported output states include PLAN_READY, NEEDS_INSPECTION, NEEDS_CONTRACT, NEEDS_REASONING_GAP, BLOCKED_ENVIRONMENT, NEEDS_CLARIFICATION, INTEGRITY_FAILURE, BUDGET_BLOCKED, CAPABILITY_REFRESH_REQUIRED, PROFILE_UPDATE_REQUIRED, NO_SUPPORTED_ROUTE, and ULTRA_CONTROL_UNCONFIRMED. PLAN_READY explicitly has executed=false and observed_model/observed_effort=null.

For Max/Ultra, `route.py` requires a ledger object with matching task_id and a nonnegative integer exceptional_stages_used, then compares that count with policy.exceptional_stages. Exhaustion returns `BUDGET_BLOCKED`. Other efforts do not inspect the ledger. This does not stop external dispatches or prove that the supplied count includes every prior attempt. The coordinator preserves and checks the full ledger, records the source of limits, and obtains any required budget change before re-planning; never alter usage merely to get PLAN_READY.

If no exact effort is supported, propose a separate plan for an evidenced supported pair. Do not rename medium as high. If the actual host instead requires inheritance, assess the permitted inherited route and record its limits; an explicit planner pair must not be reported as executed through omitted arguments. An unavailable effort is a routing constraint; solve it directly rather than retrying identical requests.

## Completion receipt
Keep it short: host-observed model/effort (unknown if absent), task/candidate, genuine checks and results, independent reviewer context/protection level, measured usage if supplied, unresolved limitations, final state. Reasoning summaries are useful; private internal reasoning traces are unnecessary.
