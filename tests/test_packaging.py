"""Public CLI checks for installed integrity and release test discovery."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]


class PackagingTests(unittest.TestCase):
    def test_release_refuses_existing_sidecar_hardlink_without_touching_source(self):
        version = json.loads((REPO / 'VERSION.json').read_text())['version']
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'release'; output.mkdir()
            keep = Path(tmp) / 'keep'; keep.write_bytes(b'preserve bytes')
            os.link(keep, output / ('modelrouter-v' + version + '-metadata.log'))
            manifest = REPO / 'skills/modelrouter/manifest.json'
            before = manifest.read_bytes() if manifest.exists() else None
            run = subprocess.run([sys.executable, '-B', str(REPO / 'scripts/build_release.py'),
                                  '--output', str(output)], capture_output=True, text=True, timeout=20)
            self.assertNotEqual(0, run.returncode)
            self.assertIn('refusing overwrite', run.stderr)
            self.assertEqual(b'preserve bytes', keep.read_bytes())
            self.assertEqual(before, manifest.read_bytes() if manifest.exists() else None)

    def test_missing_or_corrupt_policy_returns_structured_input_error(self):
        source = REPO / 'skills/modelrouter'
        with tempfile.TemporaryDirectory() as tmp:
            installed = Path(tmp) / 'skill'
            shutil.copytree(source, installed, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
            data = Path(tmp) / 'input.json'; data.write_text('{}')
            policy = installed / 'policy/defaults.json'
            for value in (None, '{', '{}'):
                with self.subTest(value=value):
                    if value is None:
                        policy.unlink()
                    else:
                        policy.write_text(value)
                    run = subprocess.run([sys.executable, '-B', str(installed / 'scripts/route.py'),
                                          '--task', str(data), '--catalog', str(data), '--profiles', str(data)],
                                         capture_output=True, text=True, timeout=20)
                    self.assertEqual(2, run.returncode)
                    self.assertEqual('INPUT_ERROR', json.loads(run.stdout)['status'])

    def test_zero_test_discovery_is_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = subprocess.run([sys.executable, '-B', str(REPO / 'scripts/run_tests.py'), '--start-dir', tmp],
                                 capture_output=True, text=True, timeout=20)
        self.assertEqual(2, run.returncode)
        self.assertIn('ZERO_TESTS', run.stdout + run.stderr)

    def test_installed_verifier_detects_changed_and_missing_payload(self):
        source = REPO / 'skills/modelrouter'
        with tempfile.TemporaryDirectory() as tmp:
            installed = Path(tmp) / 'skill'
            shutil.copytree(source, installed, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
            import hashlib
            manifest = {'version': '5.4.0', 'sha256': {
                p.relative_to(installed).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in installed.rglob('*') if p.is_file() and p.name != 'manifest.json'}}
            (installed / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
            def verify():
                return subprocess.run([sys.executable, '-B', str(installed / 'scripts/verify_install.py')],
                                      capture_output=True, text=True, timeout=20)
            self.assertEqual(0, verify().returncode)
            manifest['sha256']['missing.py'] = None
            (installed / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
            self.assertEqual(2, verify().returncode)
            del manifest['sha256']['missing.py']
            (installed / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
            (installed / 'policy/defaults.json').write_text('{}')
            self.assertEqual(2, verify().returncode)
            (installed / 'policy/defaults.json').unlink()
            result = verify()
            self.assertEqual(2, result.returncode)
            self.assertIn('policy/defaults.json', result.stdout)
