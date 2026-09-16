#!/usr/bin/env python3
"""Validate the public repository shape without third-party dependencies."""
from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SKILL = REPO / "skills" / "modelrouter"
SKILL_FILE = SKILL / "SKILL.md"
NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def fail(message: str) -> "NoReturn":
    raise SystemExit(f"validation failed: {message}")


def frontmatter(path: Path) -> dict[str, str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        fail("SKILL.md must begin with YAML frontmatter")
    try:
        end = lines.index("---", 1)
    except ValueError:
        fail("SKILL.md frontmatter is not closed")
    fields: dict[str, str] = {}
    for line in lines[1:end]:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line.startswith((" ", "\t")) or ":" not in line:
            continue
        key, value = line.split(":", 1)
        if key.strip() in fields:
            fail(f"duplicate frontmatter field: {key.strip()}")
        fields[key.strip()] = value.strip().strip('"').strip("'")
    return fields


def check_markdown_links() -> int:
    checked = 0
    pattern = re.compile(r"\]\(([^)]+)\)")
    for path in REPO.rglob("*.md"):
        if any(part in {".git", "__pycache__"} for part in path.parts):
            continue
        for target in pattern.findall(path.read_text(encoding="utf-8")):
            if "://" in target or target.startswith("#"):
                continue
            local = target.split("#", 1)[0]
            if local and not (path.parent / local).exists():
                fail(f"missing Markdown target: {path.relative_to(REPO)} -> {target}")
            checked += 1
    return checked


def main() -> int:
    if not SKILL_FILE.is_file():
        fail("skills/modelrouter/SKILL.md is missing")
    metadata = frontmatter(SKILL_FILE)
    if set(metadata) - {'name', 'description', 'license', 'allowed-tools', 'metadata'}:
        fail("frontmatter contains fields unsupported by this Codex package")
    name = metadata.get("name", "")
    description = metadata.get("description", "")
    if name != SKILL.name or not NAME_RE.fullmatch(name):
        fail("skill name must match its kebab-case directory")
    if not 1 <= len(description) <= 1024:
        fail("skill description must be 1-1024 characters")
    if any(char in description for char in "<>"):
        fail("skill description must not contain angle brackets")
    if len(SKILL_FILE.read_text(encoding="utf-8").splitlines()) > 500:
        fail("SKILL.md must stay under 500 lines")
    yaml_path = SKILL / "agents" / "openai.yaml"
    if not yaml_path.is_file():
        fail("Codex metadata file is missing")
    if (REPO / 'scripts/common.py').read_bytes() != (SKILL / 'scripts/common.py').read_bytes():
        fail("repository and portable common.py copies differ")
    if not list((REPO / 'tests').glob('test_*.py')):
        fail("repository regression tests are missing")
    for path in REPO.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path), feature_version=(3, 10))
    for path in REPO.rglob("*.json"):
        if "__pycache__" not in path.parts:
            json.loads(path.read_text(encoding="utf-8-sig"))
    links = check_markdown_links()
    print(json.dumps({
        "status": "PASS",
        "skill": name,
        "skill_lines": len(SKILL_FILE.read_text(encoding="utf-8").splitlines()),
        "python_files_checked": len([p for p in REPO.rglob("*.py") if "__pycache__" not in p.parts]),
        "json_files_checked": len([p for p in REPO.rglob("*.json") if "__pycache__" not in p.parts]),
        "markdown_links_checked": links,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
