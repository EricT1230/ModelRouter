#!/usr/bin/env python3
"""Compare installed bytes to the release manifest. Not publisher authentication."""
import hashlib
import json
import re
from pathlib import Path
import sys
from common import load_json, regular_path, require


def verify(root):
    root = regular_path(root)
    manifest_path = regular_path(root / 'manifest.json')
    manifest = load_json(manifest_path)
    version = manifest.get('version')
    require(isinstance(version, str) and re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+', version),
            'manifest version must be numeric semver')
    expected = manifest.get('sha256')
    require(isinstance(expected, dict) and bool(expected), 'nonempty manifest.sha256 required')
    for name, digest in expected.items():
        require(isinstance(name, str) and bool(name) and '\\' not in name and ':' not in name,
                'manifest keys must be relative forward-slash paths')
        require(all(part not in {'', '.', '..'} for part in name.split('/')) and name != 'manifest.json',
                'manifest paths must be normalized payload paths')
        require(isinstance(digest, str) and re.fullmatch(r'[0-9a-f]{64}', digest),
                'manifest hashes must be lowercase SHA-256 strings')
    actual = {}
    pending = [root]
    while pending:
        for path in pending.pop().iterdir():
            regular_path(path)
            if path.name == '__pycache__' or path.suffix == '.pyc':
                continue
            if path.is_dir():
                pending.append(path)
            elif path.is_file() and path != manifest_path:
                require(path.stat().st_size <= 50 * 1024 * 1024, 'payload file size exceeded')
                actual[path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    require(bool(actual), 'installed payload is empty')
    differences = sorted(k for k in set(actual) | set(expected) if actual.get(k) != expected.get(k))
    return {'status': 'PASS' if not differences else 'MISMATCH', 'version': manifest.get('version'),
            'files_checked': len(actual), 'differences': differences, 'publisher_authenticated': False}


def main():
    try:
        result = verify(Path(__file__).absolute().parents[1])
    except (OSError, ValueError, TypeError) as exc:
        result = {'status': 'INVALID', 'reason': str(exc), 'publisher_authenticated': False}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result['status'] == 'PASS' else 2


if __name__ == '__main__':
    sys.exit(main())
