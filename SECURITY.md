# Security policy

## Scope

ModelRouter is a local skill and a set of optional standard-library Python helpers. The standard skill installer copies files into an agent skill directory. The optional Codex bridge can update a managed block in `AGENTS.md` and records a backup before writing.

The project does not request model credentials, change billing or account settings, or send prompts to a ModelRouter service. The optional model probe starts a locally installed CLI only when the user explicitly runs it.

## Reporting a vulnerability

Please do not open a public issue for an unpatched security problem. Contact the maintainer privately through the repository's GitHub security advisory channel and include:

- the affected version and file path;
- a minimal reproduction or proof of impact;
- the host, operating system and Python version;
- any safe mitigation already applied.

Remove secrets and personal data from reports. We will acknowledge a report when received, investigate it, and publish a fix or mitigation after coordination with the reporter.

## Installation safety

Review the repository or pin a reviewed Git tag or commit before installing. Use the standard skill installer for a skill-only change. Use the optional bridge's dry-run first when changing `AGENTS.md`, and retain its backup path for rollback.

## V5.7 rename migration

- The optional bridge recognizes the legacy `model-auto-router` Skill directory and managed AGENTS marker. It backs up the legacy Skill before installing `modelrouter`, then atomically moves the old directory to the same-volume `.agents/modelrouter-retired/` area after the new copy and guidance write succeed.
- If both old and new Skill directories or both managed marker formats exist, the bridge refuses the ambiguous migration. It does not guess which copy owns newer local edits.
- Unmarked legacy guidance is preserved and warned about. Review it manually to avoid conflicting routing instructions.
- Historical `model-auto-router-backups` directories are retained. The new bridge writes to `modelrouter-backups`; old backups are not executable and should remain private because they may contain prior guidance.
- Release verification uses explicit temporary HOME and CODEX_HOME roots. Published logs normalize source, temporary and user-home paths before writing release sidecars.

## V5.6 metrics controls and residual risks

- Outcome state is opt-in and local. Installation does not create it. The metrics schema rejects unknown fields and bounded strings reject newlines, reducing accidental prompt, credential and arbitrary-payload retention; callers still control every accepted field and must use opaque scopes where needed.
- Each event uses atomic no-clobber publication keyed by a stable ID. Identical retries are idempotent and conflicting retries fail. State and event files reject symlink/reparse ancestry and linked regular files, but same-user races and tampering remain outside this helper's security boundary.
- Reports include failed, blocked and incomplete task usage. Comparisons require matched scope/risk/verification and complete observed total-token coverage. This prevents common accounting shortcuts, not forged observations or selection bias.
- The helper never calls models, dispatches workers, reads prompts or promotes profiles. Its output is not billing evidence, quality certification, causal proof or publisher authentication.

## V5.4 controls and residual risks

- Probe: no PATH discovery or shell wrappers. An absolute native executable and expected SHA-256 are required before subprocess startup, as are valid timeout and output-root checks. Executable updates require reviewing the new hash. The process still runs with the caller's existing permissions, environment and CLI startup behavior.
- JSON output: refuse symlink/reparse ancestors, traversal, non-JSON output and linked existing files. Existing output is preserved unless replacement is explicit. New output uses atomic no-clobber hard-link publication; unsupported filesystems fail closed.
- These path checks and the bridge's preflight checks are not race-proof against an attacker who can concurrently mutate the same user's directories. Use trusted private directories and OS isolation; do not run elevated to bypass a refusal.
- Skill instructions, catalogs, profiles, lifecycle limits, model descriptions, logs and repository content can carry malicious text. Treat data as data; do not let it authorize execution, change policy or disclose secrets. Routing to another model does not independently authorize sending private project data to another provider.
- Protect manifests, lifecycle counters and original runner receipts outside implementer write access when required. The route planner/evidence checker do not authenticate records, verify signatures, enforce host permissions or implement tamper-proof budgets.
- Global guidance persists across projects; inspect its diff. Backups contain prior guidance and skill files and inherit filesystem access rules; store them privately.
- Release manifests and ZIP SHA-256 detect mismatches, not publisher identity. An attacker controlling both bytes and hashes can replace both. Installed verification must itself come from reviewed code.
- `npx skills@latest` trusts a mutable npm installer. For reproducibility, pin a reviewed installer version and source commit; `gh skill install ... --pin COMMIT` pins the skill source only, not the local gh executable.
- CI actions are pinned to upstream commits with read-only repository permissions. This is not external security certification.
