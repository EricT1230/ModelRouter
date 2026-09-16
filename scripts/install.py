#!/usr/bin/env python3
"""Install this local skill and managed AGENTS guidance. Dry-run unless --apply.

Backs up changed files, preserves unrelated guidance and never edits model/billing config.
"""
from __future__ import annotations
import argparse
import json
import os
import shutil
import stat
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Any
from common import require, utcnow

SKILL_SLUG = 'modelrouter'
LEGACY_SKILL_SLUG = 'model-auto-router'
BEGIN = '<!-- modelrouter:begin -->'
END = '<!-- modelrouter:end -->'
LEGACY_BEGIN = '<!-- model-auto-router:begin -->'
LEGACY_END = '<!-- model-auto-router:end -->'


def managed_span(original: str, begin: str, end: str) -> tuple[int, int] | None:
    require(original.count(begin) == original.count(end), 'unbalanced router markers; merge manually')
    require(original.count(begin) <= 1, 'duplicate router blocks; merge manually')
    if begin not in original:
        return None
    start, finish = original.index(begin), original.index(end) + len(end)
    require(finish - len(end) > start, 'reversed router markers')
    return start, finish


def merge_guidance(original: str, snippet: str) -> str:
    current = managed_span(original, BEGIN, END)
    legacy = managed_span(original, LEGACY_BEGIN, LEGACY_END)
    require(not (current and legacy), 'current and legacy router blocks both exist; merge manually')
    newline = '\r\n' if '\r\n' in original else '\n'
    block = snippet.strip().replace('\r\n', '\n').replace('\n', newline)
    span = current or legacy
    if span:
        start, finish = span
        return original[:start] + block + original[finish:]
    separator = '' if not original else (newline if original.endswith(('\n', '\r')) else newline * 2)
    return original + separator + block + newline


def safe_path(path: Path) -> None:
    for component in reversed((path, *path.parents)):
        try:
            reject_link(component)
        except FileNotFoundError:
            continue


def reject_link(path: Path) -> None:
    info = path.lstat()
    linked = stat.S_ISLNK(info.st_mode) or bool(
        getattr(info, 'st_file_attributes', 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT)
    require(not linked, f'refusing symlink or reparse path: {path}; install manually after inspection')


def safe_tree(root: Path) -> None:
    pending = [root]
    while pending:
        for path in pending.pop().iterdir():
            reject_link(path)
            if path.is_dir():
                pending.append(path)


def require_skill_name(root: Path, expected: str) -> None:
    skill_file = root / 'SKILL.md'
    require(skill_file.is_file(), f'{root} is not an identified {expected} Skill: SKILL.md is missing')
    data = skill_file.read_bytes()
    require(len(data) <= 1_048_576, f'{skill_file} is too large to identify safely')
    text = data.decode('utf-8')
    lines = text.splitlines()
    require(lines and lines[0].strip() == '---', f'{skill_file} has no Skill frontmatter')
    try:
        finish = lines.index('---', 1)
    except ValueError as exc:
        raise ValueError(f'{skill_file} has unclosed Skill frontmatter') from exc
    names = [line.split(':', 1)[1].strip().strip('"').strip("'")
             for line in lines[1:finish]
             if not line.startswith((' ', '\t')) and line.split(':', 1)[0].strip() == 'name'
             and ':' in line]
    require(names == [expected], f'{root} does not identify as the legacy {expected} Skill')


def install(source: Path, *, scope: str, user_home: Path, codex_home: Path,
            project: Path | None = None, apply: bool = False) -> dict[str, Any]:
    safe_path(source.absolute())
    source = source.resolve(strict=True)
    require((source / 'SKILL.md').is_file(), 'source SKILL.md is missing')
    require(scope in {'user', 'project'}, 'scope must be user/project')
    if scope == 'project':
        require(project is not None and project.is_dir(), 'existing project directory required')
        base = project.absolute()
        skills_base = base / '.agents' / 'skills'
        dest = skills_base / SKILL_SLUG
        legacy_dest = skills_base / LEGACY_SKILL_SLUG
        retirement_base = base / '.agents' / 'modelrouter-retired'
        guidance_base, backup_base = base, base / '.codex' / 'modelrouter-backups'
    else:
        skills_base = user_home.absolute() / '.agents' / 'skills'
        dest = skills_base / SKILL_SLUG
        legacy_dest = skills_base / LEGACY_SKILL_SLUG
        retirement_base = user_home.absolute() / '.agents' / 'modelrouter-retired'
        guidance_base, backup_base = codex_home.absolute(), codex_home.absolute() / 'modelrouter-backups'
    override = guidance_base / 'AGENTS.override.md'
    base_guidance = guidance_base / 'AGENTS.md'
    for path in (dest, legacy_dest, retirement_base, base_guidance, override, backup_base):
        safe_path(path)
    guidance_texts: dict[Path, str] = {}
    managed_locations: list[tuple[Path, str]] = []
    for candidate in (base_guidance, override):
        require(not candidate.exists() or candidate.is_file(),
                f'guidance target must be a file: {candidate}')
        text = candidate.read_bytes().decode('utf-8') if candidate.exists() else ''
        guidance_texts[candidate] = text
        current = managed_span(text, BEGIN, END)
        legacy = managed_span(text, LEGACY_BEGIN, LEGACY_END)
        require(not (current and legacy),
                f'current and legacy router blocks both exist in {candidate}; merge manually')
        if current:
            managed_locations.append((candidate, 'current'))
        if legacy:
            managed_locations.append((candidate, 'legacy'))
    require(len(managed_locations) <= 1,
            'managed router blocks appear in multiple guidance files; merge manually')
    guidance = override if override.is_file() and override.read_bytes().strip() else base_guidance
    if managed_locations:
        require(managed_locations[0][0] == guidance,
                'managed router block exists in an inactive guidance file; reconcile AGENTS files manually')
    require(not dest.exists() or dest.is_dir(), 'skill destination must be a directory')
    require(not legacy_dest.exists() or legacy_dest.is_dir(), 'legacy skill destination must be a directory')
    require(not (dest.exists() and legacy_dest.exists()),
            'current and legacy skill directories both exist; remove the unwanted copy after inspection')
    safe_tree(source)
    if dest.exists():
        safe_tree(dest)
    if legacy_dest.exists():
        safe_tree(legacy_dest)
        require_skill_name(legacy_dest, LEGACY_SKILL_SLUG)
    source_is_dest = source == dest.resolve()
    require(source_is_dest or not dest.resolve().is_relative_to(source), 'destination inside package source')
    require(source_is_dest or not source.is_relative_to(dest.resolve()), 'source inside destination')
    original = guidance.read_bytes() if guidance.exists() else None
    original_text = guidance_texts[guidance]
    snippet = (source / 'templates' / 'AGENTS.md.snippet').read_text(encoding='utf-8')
    merged = merge_guidance(original_text, snippet).encode('utf-8')
    warnings: list[str] = []
    unmanaged_text = original_text
    span = managed_span(original_text, BEGIN, END) or managed_span(
        original_text, LEGACY_BEGIN, LEGACY_END)
    if span:
        unmanaged_text = original_text[:span[0]] + original_text[span[1]:]
    if any(name in unmanaged_text.lower() for name in (SKILL_SLUG, LEGACY_SKILL_SLUG)):
        warnings.append('Existing unmarked router guidance preserved; inspect for old/conflicting rules.')
    if guidance == override:
        warnings.append('Merged into effective AGENTS.override.md; it takes precedence over AGENTS.md.')
    stamp = utcnow().strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:8]
    backup = backup_base / stamp
    retired_legacy = retirement_base / stamp / 'legacy-skill'
    safe_path(retired_legacy)
    had_legacy = legacy_dest.exists()
    out: dict[str, Any] = {'status': 'DRY_RUN', 'skill_path': str(dest),
                          'legacy_skill_path': str(legacy_dest),
                          'legacy_skill_detected': had_legacy,
                          'legacy_skill_removed': False,
                          'legacy_retired_path': str(retired_legacy) if had_legacy else None,
                          'guidance_path': str(guidance), 'backup_path': str(backup),
                          'warnings': warnings, 'models_config_changed': False,
                          'live_activation_verified': False}
    if not apply:
        return out
    backup.mkdir(parents=True, exist_ok=False)
    if had_legacy:
        retired_legacy.parent.mkdir(parents=True, exist_ok=False)
    had_dest = dest.exists()
    previous = dest if had_dest else legacy_dest if had_legacy else None
    if previous is not None and not source_is_dest:
        shutil.copytree(previous, backup / 'previous-skill')
    if original is not None:
        (backup / guidance.name).write_bytes(original)
    stage: Path | None = None
    replaced = False
    legacy_retired = False
    try:
        if not source_is_dest:
            dest.parent.mkdir(parents=True, exist_ok=True)
            stage = Path(tempfile.mkdtemp(prefix='.router-incoming-', dir=dest.parent))
            shutil.copytree(source, stage, dirs_exist_ok=True,
                            ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
            replaced = True
            if had_dest:
                shutil.rmtree(dest)
            os.replace(stage, dest)
            stage = None
        guidance.parent.mkdir(parents=True, exist_ok=True)
        fd, temp = tempfile.mkstemp(prefix='.router-guidance-', dir=guidance.parent)
        try:
            with os.fdopen(fd, 'wb') as handle:
                handle.write(merged)
            os.replace(temp, guidance)
        finally:
            if os.path.exists(temp):
                os.unlink(temp)
        if had_legacy:
            os.replace(legacy_dest, retired_legacy)
            legacy_retired = True
    except Exception:
        if legacy_retired:
            os.replace(retired_legacy, legacy_dest)
        if replaced:
            if dest.exists():
                shutil.rmtree(dest)
            if had_dest:
                shutil.copytree(backup / 'previous-skill', dest)
        if original is None:
            if guidance.exists():
                guidance.unlink()
        else:
            guidance.write_bytes(original)
        raise
    finally:
        if stage is not None and stage.exists():
            shutil.rmtree(stage)
    if had_legacy:
        out['legacy_skill_removed'] = True
    out['status'] = 'INSTALLED_FILES_ONLY'
    out['next'] = 'Start a fresh Codex session; check trigger, host capabilities and independent dispatch.'
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scope', choices=['user', 'project'], default='user')
    parser.add_argument('--project', type=Path)
    parser.add_argument('--user-home', type=Path,
                        help='Explicit home root for isolated testing; defaults to the current user home.')
    parser.add_argument('--codex-home', type=Path)
    flags = parser.add_mutually_exclusive_group()
    flags.add_argument('--apply', action='store_true')
    flags.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    try:
        home = args.user_home or Path.home()
        codex_home = args.codex_home or Path(os.environ.get('CODEX_HOME', str(home / '.codex')))
        script_path = Path(__file__).absolute()
        safe_path(script_path)
        skill_source = script_path.parents[1] / 'skills' / SKILL_SLUG
        out = install(skill_source, scope=args.scope, user_home=home,
                      codex_home=codex_home, project=args.project, apply=args.apply)
        code = 0
    except (OSError, ValueError) as exc:
        out = {'status': 'INSTALLATION_FAILED', 'reason': str(exc)}
        code = 2
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return code

if __name__ == '__main__':
    sys.exit(main())
