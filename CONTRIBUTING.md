# Contributing

## Development setup

Python 3.10 or newer is required for the helper scripts. The project uses only the Python standard library.

```bash
python -B scripts/run_tests.py
python scripts/install.py --scope user --dry-run
```

Do not run the installer against a real home directory while developing. Use a temporary project and explicit `--codex-home` paths for installation tests.

## Pull requests

- Keep the portable skill under `skills/modelrouter/`.
- Keep `SKILL.md` focused on activation and decision boundaries; move detailed material into `references/`.
- Preserve the distinction between proposed, requested and observed runtime settings.
- Add a regression test for behavior changes and update the changelog.
- Do not claim live model dispatch, cost savings or automatic activation without host evidence.
- Run the same validation that GitHub Actions runs before opening a pull request.

## Changes to the skill

The root `README.md` is for people. `skills/modelrouter/SKILL.md` is for the agent. Keep Codex UI metadata in `skills/modelrouter/agents/openai.yaml` and keep paths relative to the skill root.

Build a release with `python -B scripts/build_release.py --output dist`. This generates the portable manifest, validates source, tests an unpacked copy and creates ZIP/hash/verification records. It refuses an existing versioned output. Keep the repository and portable common.py copies identical; validation checks this.
