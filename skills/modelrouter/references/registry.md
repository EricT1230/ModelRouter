# Model discovery and evolving role profiles

## Two different kinds of data
`catalog.json` records observed IDs, exact supported effort values/descriptions, modalities, default status, full-page completion, observation time, and host scope. It does not rank intelligence or cost. `profiles.json` contains the coordinator's evidence-backed role suitability judgments, bound to a catalog-entry fingerprint. A profile is not a new API capability.

The portable capability classes are worker (1), generalist (2), reasoner (3), frontier (4). They express minimum role suitability under this policy, not physical model size or universal benchmarks. The policy requires reasoner-or-better for independent code/architecture review. More routine review usually uses medium effort; difficult review usually uses high. Model names have no role in these rules.

## Bootstrap without asking the user to assign every model
1. Obtain a session-bound complete catalog from available host discovery or an authorized compatible local probe. Unknown available IDs stay in the catalog.
2. Use current official descriptions for the exact IDs/variants to assign conservative classes and roles. Do not assume that a display alias is an API ID, that the newest version wins, or that all variants share prices/modalities/efforts. If the correct variant cannot be identified, leave it provisional.
3. Record `source_refs`, `checked_at`, the entry fingerprint, and `basis: documented`. Assign only supported semantic-to-native effort bindings. Basic exact names low/medium/high/xhigh/max can be recorded when current docs give their meanings; new native names require reading their descriptions. Ultra needs explicit host-specific interpretation.
4. A documented profile can seed routing. Disclose its uncalibrated status. Successful independently verified usage can support `basis: evaluated`; a model's assertion cannot promote itself.
5. If no supported documented/evaluated route exists, use the current parent for safe bounded work when sufficient, and report any missing strong-review capability. Do not fabricate a roster to avoid a blocker.

This bootstrap is performed by the coordinator following the skill. The catalog probe and route planner do not scrape documentation, understand tasks, or automatically generate trustworthy profiles. Once established, cached profiles avoid repeated lookup.

## New model lifecycle
Discovered → provisional → documented or independently evaluated → eligible for matching roles.

A new model with no reliable role evidence can only receive an explicitly permitted low-risk canary; automatic paid benchmark jobs are disabled. A canary uses a sandbox or already-authorized low-risk real task, protected acceptance, a known reviewer, and the normal shared budget. It must not replace production or security acceptance reviewers. Do not invent canary results.

Official evidence can move a provisional model to documented suitability without a paid benchmark, with uncertainty recorded. Prefer evaluated routes for consequential work when comparable evidence exists. High-risk/architect/reviewer work never uses an unclassified provisional route.

## Change detection and stability
`catalog_entry_sha256` fingerprints normalized dispatch-relevant metadata. An ID, supported-effort/default, visible description, or modality change invalidates that profile. A catalog disappearance removes eligibility; an `upgrade` suggestion is an input to reassessment, not an automatic migration order.

Recheck profile evidence at least every 30 days, after failures, or when a user requests a refresh. Silent model changes may not change IDs/metadata; rolling accepted-task performance is needed to detect behavioral drift. No skill can guarantee detection of undocumented changes. Pin candidate inputs, dependency versions and model snapshots when the host exposes them.

Keep a known route until there is relevant evidence to switch. Avoid flapping after a single favorable run. Compare quality, correction burden, total charged cost and latency in matched task buckets. Documented price bands are initial heuristics; independent outcome evidence has priority over generation labels.

## What adapts automatically
When catalog-based routing is needed, reuse current observations and refresh only stale, missing or invalidated catalog data and affected profiles, then resolve roles. Skill invocation alone does not trigger discovery. A newly documented or evaluated model can replace an older role binding without rewriting SKILL.md or route.py. A future effort named `deliberate` can map to the existing high semantic slot if evidence establishes that meaning. Unknown labels are preserved but remain unused until classified.

No daemon, schedule, account migration, external provider subscription, API key creation, global parent-model change, or automatic paid benchmark is installed.

## Minimal profile shape
See templates/profiles.EMPTY.json and tests for synthetic examples. Each model profile needs:
- id, catalog_entry_sha256, checked_at, basis (provisional/documented/evaluated), source_refs;
- capability_class, roles, effort_bindings, cost_band (low/standard/premium/unknown).

`cost_band` is only a source-backed initial ordering. Do not call it measured credits, a fixed multiplier, or a savings estimate. Documented/evaluated eligibility is a claim in this file; external trust and actual evidence review remain required.

Optional `incumbent_roles` records roles already accepted under this route. It breaks ties so a new alphabetical ID does not displace an equally evidenced incumbent. For ordinary low/medium-risk work, qualified cost/capability fit precedes evaluation history; an evaluated frontier must not monopolize simple work. Architecture, diagnosis, review and high-risk work prefer evaluated evidence among otherwise eligible routes.

When host metadata omits input modalities, record a conservative text fallback with modalities_observed=false. Do not promote an inferred default, class or cost band into host-observed telemetry. Capture the actual host event reference for capacity claims; active slots, total retained threads and descendant depth are different limits.
