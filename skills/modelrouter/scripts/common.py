"""Bounded JSON and catalog helpers. Records are not authenticated by this module."""
from __future__ import annotations
import hashlib
import json
import os
import stat
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MAX_JSON = 8 * 1024 * 1024

def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)

def nonempty(value: Any, field: str) -> str:
    require(isinstance(value, str) and bool(value.strip()), f'{field}: nonempty string required')
    return value

def string_list(value: Any, field: str, allow_empty: bool = True) -> list[str]:
    require(isinstance(value, list), f'{field}: list required')
    require(allow_empty or bool(value), f'{field}: nonempty list required')
    result = [nonempty(v, field) for v in value]
    require(len(result) == len(set(result)), f'{field}: duplicate values')
    return result

def boolean(value: Any, field: str) -> bool:
    require(type(value) is bool, f'{field}: boolean required')
    return value

def integer(value: Any, field: str, minimum: int = 0) -> int:
    require(type(value) is int and value >= minimum, f'{field}: integer >= {minimum} required')
    return value

def utcnow() -> datetime:
    return datetime.now(timezone.utc)

def timestamp(value: Any) -> datetime:
    text = nonempty(value, 'timestamp')
    result = datetime.fromisoformat(text.replace('Z', '+00:00'))
    require(result.tzinfo is not None, 'timestamp requires timezone')
    return result.astimezone(timezone.utc)

def fresh(value: Any, now: datetime, seconds: float) -> bool:
    age = (now - timestamp(value)).total_seconds()
    return -300 <= age <= seconds

def _unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        require(key not in out, f'duplicate JSON key: {key}')
        out[key] = value
    return out

def _invalid_constant(value: str) -> None:
    raise ValueError(f'non-finite JSON number: {value}')

def load_json(path: Path) -> dict[str, Any]:
    with path.open('rb') as handle:
        data = handle.read(MAX_JSON + 1)
    require(len(data) <= MAX_JSON, 'JSON size limit exceeded')
    obj = json.loads(data.decode('utf-8-sig'), object_pairs_hook=_unique,
                     parse_constant=_invalid_constant)
    require(isinstance(obj, dict), 'top-level JSON object required')
    return obj

def regular_path(path: Path) -> Path:
    """Reject existing linked components. Not a lock against same-user races."""
    require('..' not in path.parts, 'parent traversal is not accepted')
    path = path.absolute()
    for component in reversed((path, *path.parents)):
        try:
            info = component.lstat()
        except FileNotFoundError:
            continue
        require(not stat.S_ISLNK(info.st_mode) and not (
            getattr(info, 'st_file_attributes', 0) & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0x400)),
            f'refusing symlink or reparse path: {component}')
        require(component == path or stat.S_ISDIR(info.st_mode),
                f'existing ancestor must be a directory: {component}')
    return path


def output_path(path: Path, *, root: Path | None = None, replace: bool = False) -> Path:
    path = regular_path(path)
    if root is not None:
        root = regular_path(root)
        require(root.is_dir(), 'output root must be an existing trusted directory')
        require(path.is_relative_to(root) and path != root, 'output must be beneath output root')
    require(path.suffix.lower() == '.json', 'output must be a .json file')
    if path.exists():
        info = path.lstat()
        require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1, 'output must be a regular unlinked file')
        require(replace, 'output already exists; use explicit replacement only after inspection')
    return path


def atomic_json(path: Path, data: dict[str, Any], *, root: Path | None = None,
                replace: bool = False) -> None:
    path = output_path(path, root=root, replace=replace)
    path.parent.mkdir(parents=True, exist_ok=True)
    output_path(path, root=root, replace=replace)
    fd, tmp = tempfile.mkstemp(prefix='.router-', suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2, allow_nan=False)
            handle.write('\n')
        output_path(path, root=root, replace=replace)
        if replace:
            os.replace(tmp, path)
        else:
            # Atomic no-clobber publication; fail closed if hard links are unsupported.
            os.link(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)

def entry_digest(model: dict[str, Any]) -> str:
    fields = ('id', 'display_name', 'description', 'efforts', 'default_effort',
              'input_modalities', 'hidden')
    data = {key: model.get(key) for key in fields}
    raw = json.dumps(data, sort_keys=True, ensure_ascii=False,
                     separators=(',', ':'), allow_nan=False).encode('utf-8')
    return hashlib.sha256(raw).hexdigest()

def normalize_model(raw: dict[str, Any]) -> dict[str, Any]:
    require(isinstance(raw, dict), 'model entry must be an object')
    # `model` is the callable selector; do not turn a display name into an ID.
    model_id = nonempty(raw.get('model'), 'model.model')
    efforts = raw.get('supportedReasoningEfforts', [])
    require(isinstance(efforts, list), 'supportedReasoningEfforts must be a list')
    normalized: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in efforts:
        require(isinstance(item, dict), 'effort entry must be an object')
        value = nonempty(item.get('reasoningEffort'), 'reasoningEffort')
        require(value not in seen, 'duplicate effort value')
        description = item.get('description', '')
        require(isinstance(description, str), 'effort description must be a string')
        normalized.append({'value': value, 'description': description})
        seen.add(value)
    default = raw.get('defaultReasoningEffort')
    require(default is None or isinstance(default, str), 'default effort must be string/null')
    if default is not None:
        require(default in seen, 'default effort missing from advertised supported efforts')
    modalities = raw.get('inputModalities')
    # Conservative text-only fallback; never infer image support from missing metadata.
    modality_list = string_list(modalities, 'inputModalities') if modalities is not None else ['text']
    hidden = boolean(raw.get('hidden', False), 'hidden')
    desc, display = raw.get('description', ''), raw.get('displayName', model_id)
    require(isinstance(desc, str) and isinstance(display, str), 'display/description must be strings')
    model = {'id': model_id, 'display_name': display, 'description': desc,
             'efforts': sorted(normalized, key=lambda v: v['value']),
             'default_effort': default, 'input_modalities': sorted(modality_list),
             'modalities_observed': modalities is not None, 'hidden': hidden}
    model['catalog_entry_sha256'] = entry_digest(model)
    return model
