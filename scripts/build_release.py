#!/usr/bin/env python3
"""Build a clean release, verify an unpacked copy, and write hashes and local test logs."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import zipfile
from common import regular_path

REPO = Path(__file__).resolve().parents[1]
SKILL = REPO / 'skills/modelrouter'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def files_under(root):
    regular_path(root)
    paths = sorted(root.rglob('*'))
    for path in paths:
        regular_path(path)
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in paths
            if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc'}


def write_new(path, data):
    regular_path(path)
    with path.open('xb') as handle:
        handle.write(data)


def normalized_log(data, replacements):
    text = data.decode('utf-8', errors='replace')
    for value, label in sorted(replacements, key=lambda item: len(item[0]), reverse=True):
        variants = {value, value.replace('\\', '/'), json.dumps(value)[1:-1]}
        for variant in variants:
            if variant:
                text = text.replace(variant, label)
    return text.encode('utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=REPO / 'dist')
    args = parser.parse_args()
    version = json.loads(regular_path(REPO / 'VERSION.json').read_text(encoding='utf-8'))['version']
    if not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+', version):
        raise ValueError('release version must be numeric semver')
    stem = 'modelrouter-v' + version
    output = regular_path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    archive_path = output / (stem + '.zip')
    suffixes = ('.zip', '.sha256', '-verification.json', '-metadata.log',
                '-installed-manifest.log', '-tests.log', '-installer-dry-run.log')
    for suffix in suffixes:
        target = regular_path(output / (stem + suffix))
        if target.exists():
            raise ValueError('versioned output already exists; refusing overwrite: ' + target.name)
    skill_files = files_under(SKILL)
    skill_files.pop('manifest.json', None)
    (SKILL / 'manifest.json').write_text(json.dumps({
        'version': version, 'sha256': {name: sha(data) for name, data in skill_files.items()}
    }, indent=2) + '\n', encoding='utf-8')
    selected = {}
    for folder in ('skills', 'scripts', 'tests', '.github'):
        selected.update({folder + '/' + name: data for name, data in files_under(REPO / folder).items()})
    for p in REPO.iterdir():
        regular_path(p)
        if p.is_file() and (p.suffix in {'.md', '.txt', '.json', '.ps1', '.sh'} or p.name in {'LICENSE', '.gitignore'}):
            selected[p.name] = p.read_bytes()
    release_notes = 'V' + '.'.join(version.split('.')[:2])
    for name in (release_notes + '-SPEC.md', release_notes + '.zh-TW.md'):
        selected['validation/' + name] = regular_path(REPO / 'validation' / name).read_bytes()
    env = dict(os.environ, PYTHONUTF8='1', PYTHONDONTWRITEBYTECODE='1')
    with tempfile.TemporaryDirectory(prefix='router-release-') as tmp:
        isolated_home = Path(tmp) / 'isolated-home'
        isolated_codex = Path(tmp) / 'isolated-codex'
        isolated_home.mkdir()
        isolated_codex.mkdir()
        check_env = dict(env, HOME=str(isolated_home), USERPROFILE=str(isolated_home),
                         CODEX_HOME=str(isolated_codex))
        if os.name == 'nt':
            drive, tail = os.path.splitdrive(str(isolated_home))
            check_env['HOMEDRIVE'] = drive
            check_env['HOMEPATH'] = tail
        candidate = Path(tmp) / 'candidate.zip'
        with zipfile.ZipFile(candidate, 'w', zipfile.ZIP_DEFLATED) as z:
            for name, data in sorted(selected.items()):
                info = zipfile.ZipInfo('modelrouter/' + name, date_time=(2026, 9, 15, 0, 0, 0))
                info.create_system = 3
                mode = 0o100755 if name == 'install.sh' else 0o100644
                info.external_attr = mode << 16
                info.compress_type = zipfile.ZIP_DEFLATED
                z.writestr(info, data)
        with zipfile.ZipFile(candidate) as z:
            if z.testzip() is not None:
                raise ValueError('corrupt candidate ZIP')
            z.extractall(tmp)
        extracted = Path(tmp) / 'modelrouter'
        if files_under(extracted) != selected:
            raise ValueError('unpacked bytes differ')
        results = {}
        checks = {
            'metadata': ['scripts/validate_repo.py'],
            'installed-manifest': ['skills/modelrouter/scripts/verify_install.py'],
            'tests': ['scripts/run_tests.py'],
            'installer-dry-run': [
                'scripts/install.py', '--dry-run',
                '--user-home', str(isolated_home), '--codex-home', str(isolated_codex)],
        }
        replacements = [
            (str(REPO), '<SOURCE_REPO>'),
            (str(Path(tmp)), '<TEMP_ROOT>'),
            (str(Path(tempfile.gettempdir())), '<TEMP_DIR>'),
            (str(Path.home()), '<USER_HOME>'),
        ]
        test_counts = {}
        for label, command in checks.items():
            run = subprocess.run([sys.executable, '-B', '-X', 'utf8', *command], cwd=extracted,
                                 env=check_env, capture_output=True, timeout=120)
            log = normalized_log(run.stdout + run.stderr, replacements)
            write_new(output / (stem + '-' + label + '.log'), log)
            if run.returncode:
                raise RuntimeError(label + ' failed: ' + log.decode('utf-8', errors='replace'))
            results[label] = {'exit_code': 0, 'log_sha256': sha(log)}
            if label == 'tests':
                text = log.decode('utf-8')
                count = re.search(r'Ran (\d+) tests?', text)
                if not count or int(count[1]) == 0:
                    raise RuntimeError('zero or unknown test count')
                skipped = [line.split(' ... ')[0] for line in text.splitlines() if ' ... skipped ' in line]
                test_counts = {'run': int(count[1]), 'passed': int(count[1]) - len(skipped),
                               'skipped': skipped}
        if files_under(extracted) != selected:
            raise ValueError('verification changed unpacked payload')
        data = candidate.read_bytes()
    write_new(archive_path, data)
    receipt = {'version': version, 'zip': archive_path.name, 'sha256': sha(data),
               'files': len(selected), 'checks': results, 'tests': test_counts,
               'payload_sha256': {name: sha(content) for name, content in selected.items()},
               'live_dispatch_verified': False, 'publisher_authenticated': False}
    write_new(output / (stem + '.sha256'), (sha(data) + '  ' + archive_path.name + '\n').encode('ascii'))
    write_new(output / (stem + '-verification.json'), (json.dumps(receipt, indent=2) + '\n').encode('utf-8'))
    print(json.dumps({k: receipt[k] for k in ('version', 'zip', 'sha256', 'files', 'tests')}, indent=2))


if __name__ == '__main__':
    main()
