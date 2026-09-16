# Install ModelRouter

The standard Agent Skills installers are the preferred path. They copy the portable skill and leave the host's global instructions untouched.

## Standard install

Replace `OWNER/REPO` with the GitHub repository that contains this project.

```bash
npx skills@latest add OWNER/REPO --skill modelrouter --agent codex --global --yes
```

Or use GitHub CLI:

```bash
gh skill install OWNER/REPO modelrouter --agent codex --scope user
```

Pin a GitHub CLI install to a reviewed tag or commit when reproducibility matters:

```bash
gh skill install OWNER/REPO modelrouter --agent codex --scope user --pin v5.7.0
```

Install from a local checkout:

```bash
npx skills@latest add . --from-local --skill modelrouter --agent codex --global --yes
```

Restart the target agent after installation. In Codex, `$modelrouter` is the explicit smoke test.

When upgrading from V5.6 or older with a standard installer, install and verify `modelrouter` first, then remove the legacy ID:

```bash
npx skills@latest remove model-auto-router -g -y
```

The optional Codex guidance bridge performs this legacy backup and cleanup itself.

## Optional Codex guidance bridge

Use the repository installer only when you also want a managed routing block in the effective `AGENTS.md`. It requires Python 3.10+ and defaults to dry-run.

```powershell
.\install.ps1 -DryRun
.\install.ps1 -Apply
```

```sh
./install.sh --dry-run
./install.sh --apply
```

Project scope keeps the change inside one existing repository:

```powershell
.\install.ps1 -Scope project -Project C:\path\to\project -DryRun
.\install.ps1 -Scope project -Project C:\path\to\project -Apply
```

The bridge copies the skill from `skills/modelrouter/`, backs up changed files, migrates a legacy `model-auto-router` install, preserves unrelated instructions, and rejects symlink or reparse-point paths. It does not modify `config.toml`, model selection, billing, account state or permissions.

## Update and remove

```bash
npx skills@latest update modelrouter -g -y
npx skills@latest remove modelrouter -g -y
```

If the optional bridge was used, restore the backup path printed by the installer to remove its managed `AGENTS.md` block. Review the backup before restoring it.

## Troubleshooting

### The skill is not listed

Confirm that the command targeted `codex` and the intended scope, then restart the agent. For a local checkout, run `npx skills@latest add . --from-local --list` to confirm discovery.

### The optional installer refuses a path

The installer intentionally refuses symlinks, Windows junctions and other reparse points. Resolve the real directory, inspect it, and rerun with a regular path.

### The skill installed but did not automatically activate

Installation proves file placement only. Start a fresh session and invoke `$modelrouter`. Host model availability, effort support, context inheritance and real dispatch remain separate runtime checks.

### I want to inspect before executing

Read `skills/modelrouter/SKILL.md`, run the standard install with `--list` or the optional bridge with `-DryRun`, and pin a reviewed ref for repeatable installs.

## Verify installation bytes

From the installed skill directory run `python -B scripts/verify_install.py`. Compare against a trusted release manifest; this is not a signature or a regression test. If a manager injects tracking metadata, inspect the reported SKILL.md change against the pinned source. Full tests are repository-only: `python -B scripts/run_tests.py`.

## Optional probe (advanced)

The probe requires `--codex ABSOLUTE_NATIVE_EXECUTABLE --codex-sha256 TRUSTED_HASH --output-root EXISTING_PRIVATE_DIRECTORY --output EXISTING_PRIVATE_DIRECTORY/catalog.json`. Use the native executable, not an npm shim; inspect an update before accepting a new hash. Existing output is preserved unless `--replace` is explicit. Prefer current host metadata when available.
