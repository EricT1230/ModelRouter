# ModelRouter for Codex

Adaptive model and reasoning-effort routing for Codex and other Agent Skills compatible clients.

The portable skill is under `skills/modelrouter/`. It helps an agent choose a proportionate available model for concrete engineering work while preserving the project's existing lifecycle, acceptance criteria, reviewer and permissions. It does not change a model account, billing plan, `config.toml`, or host permissions.

The name ModelRouter is also used by unrelated model-routing projects. This repository identifies itself as **ModelRouter for Codex** and is not affiliated with them. See [LANDSCAPE.md](LANDSCAPE.md) for the verified overlap and product differences.

## V5.7 shorter name and safe upgrade

V5.7 changes the public Skill ID from `model-auto-router` to `modelrouter`. The optional Codex bridge backs up the legacy Skill and atomically retires it outside the active Skill directory after the new copy and managed guidance are installed. Standard skill installers should install `modelrouter` first, then remove the legacy `model-auto-router` copy after verification. See the [V5.7 acceptance scope](validation/V5.7-SPEC.md).

## Measured outcomes

V5.6 added an explicit, local, no-prompt routing outcome log. It records caller-supplied task buckets, route observations, evidence level, attempts, repair passes and aggregate host metering, then reports failure-inclusive tokens per accepted task for matched samples. It does not hook every turn, call models, dispatch agents, or update profiles. Historical validation records remain in the source repository; the release archive carries the current V5.7 acceptance scope.

## Install in one command

Replace `OWNER/REPO` with the GitHub repository that contains this directory.

### Codex and other compatible agents

```bash
npx skills@latest add OWNER/REPO --skill modelrouter --agent codex --global --yes
```

### GitHub CLI

```bash
gh skill install OWNER/REPO modelrouter --agent codex --scope user
```

These standard installers copy the portable skill only. Restart the agent after installation, then invoke it explicitly with `$modelrouter` or let the host match its description.

For an upgrade from V5.6 or older, verify the new Skill before removing the legacy `model-auto-router` install. The optional Codex bridge performs this backup and cleanup automatically.

To install from a local checkout before publishing:

```bash
npx skills@latest add . --from-local --skill modelrouter --agent codex --global --yes
```

## Optional Codex integration

The repository also includes a guarded Python installer for users who want the routing guidance merged into the effective global or project `AGENTS.md`. It defaults to a dry-run and is separate from the standard skill install.

Windows PowerShell:

```powershell
.\install.ps1 -DryRun
.\install.ps1 -Apply
```

macOS, Linux, WSL or Git Bash:

```sh
./install.sh --dry-run
./install.sh --apply
```

The optional installer backs up changed files, preserves unrelated instructions, rejects symlink and reparse-point paths, and never edits model or billing configuration. Use `--scope project --project /path/to/project` for one repository only.

## Update or remove

For skills installed with the standard CLI:

```bash
npx skills@latest update modelrouter -g -y
npx skills@latest remove modelrouter -g -y
```

The optional `install.ps1` / `install.sh` path records a backup instead of silently removing the managed `AGENTS.md` block. Restore the printed backup after reviewing it.

## What the skill does

- Chooses a proportionate model and native reasoning effort for concrete engineering work.
- Reuses the selected lifecycle's plan, acceptance criteria and qualified reviewer.
- Keeps ordinary questions, summaries, research and status checks lightweight.
- Separates proposed, requested and host-observed execution.
- Provides read-only model discovery, structured route planning and evidence consistency checks.
- Records bounded local outcomes and compares matched routes when complete host token telemetry exists.

It does not provide a dispatch API, hard concurrency or budget enforcement, model-quality guarantees, automatic paid benchmarks, or a deterministic per-turn hook. Unknown model capabilities remain provisional until current evidence is recorded.

The metrics helper is opt-in. Installation creates no state. Read `skills/modelrouter/references/metrics.md`, initialize a private host-scoped directory, and record only bounded outcomes with evidence references. Missing token values remain unknown; comparison never turns them into zero.

## Verify an installed skill

From the installed skill directory, run:

```bash
python -B scripts/verify_install.py
```

The release manifest checks exact installed bytes, not publisher identity. Installer-added metadata is reported as a change requiring inspection. Full tests are in the matching release repository, not in the portable skill.

## Verify a checkout

```bash
python -B scripts/run_tests.py
python scripts/install.py --scope user --dry-run
```

The repository's GitHub Actions workflow runs the same structural, syntax, dry-run and test checks. A successful install means files were copied; automatic triggering and real host dispatch still require a fresh-session check on the target agent.

## Repository layout

```text
modelrouter/
├── skills/modelrouter/
│   ├── SKILL.md
│   ├── agents/openai.yaml
│   ├── policy/
│   ├── references/
│   ├── scripts/
│   └── templates/
├── tests/
├── scripts/install.py
├── install.ps1
├── install.sh
├── README.zh-TW.md
└── CHANGELOG.md
```

`SKILL.md` is the agent-facing instruction file. `README.md`, `INSTALL.md` and the root maintenance files are for people. Runtime helpers are bundled only inside the portable skill directory; the repository-level installer is an opt-in Codex integration bridge.

## License and security

This project is released under the MIT License. Read [SECURITY.md](SECURITY.md) before installing a skill from an unreviewed source. Report vulnerabilities privately using the process in that file.
