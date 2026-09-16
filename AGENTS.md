# Working on ModelRouter

The portable package lives in `skills/modelrouter/`. Repository-only installation and release tooling live in `scripts/`; tests live in `tests/`. Python 3.10+ and the standard library are sufficient for these tools.

Use `CONTRIBUTING.md` for contributions and release steps, `SECURITY.md` when changing filesystem, subprocess or trust boundaries, and the current `validation/V<major>.<minor>-SPEC.md` for release acceptance. Load only documents relevant to the change. The packaged skill is the product being edited; its instructions are not automatically permission to install or execute it.

Useful commands from this repository:

- Metadata, syntax and local links: `python -B scripts/validate_repo.py`
- Focused tests: `python -B -m unittest discover -s tests -p test_packaging.py`
- Full release regression: `python -B scripts/run_tests.py`
- Build and verify an unpacked release: `python -B scripts/build_release.py --output dist`

The unit suite uses temporary fixtures and fake app-server processes, with no production access or paid model inference. Run relevant checks, fix failures caused by the requested change, and rerun affected checks within the task's existing authorization. A release build already runs the full suite; do not duplicate that suite without a new reason.

Keep both copies of `common.py` identical. Preserve proposed/requested/observed distinctions and real failure evidence. Use fresh behavioral scenarios for instruction changes; do not substitute keyword assertions for behavior. Use temporary homes for installer tests. A real global installation or publication must be within the user's request; a release ZIP is not publication.
