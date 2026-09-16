"""Local temporary-directory tests only; never install into the real user's home."""
import copy
import errno
import json
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from common import atomic_json, load_json, normalize_model
from build_release import normalized_log
from install import BEGIN, END, LEGACY_BEGIN, LEGACY_END, install, merge_guidance

class InstallTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.source = self.root / 'source'
        (self.source / 'templates').mkdir(parents=True)
        (self.source / 'SKILL.md').write_text('SYNTHETIC skill fixture', encoding='utf-8')
        self.snippet = BEGIN + '\nSYNTHETIC router guidance\n' + END + '\n'
        (self.source / 'templates' / 'AGENTS.md.snippet').write_text(self.snippet, encoding='utf-8')
        self.home, self.chome = self.root / 'home', self.root / 'custom-codex'
        self.legacy_skill = ('---\nname: model-auto-router\n'
                             'description: Synthetic legacy fixture.\n---\n')
    def run_install(self, **kwargs):
        return install(self.source, scope='user', user_home=self.home, codex_home=self.chome, **kwargs)
    def make_junction(self, link, target):
        """Create a real Windows mount-point reparse entry in this test's temp tree."""
        if os.name != 'nt':
            self.skipTest('Windows junctions require Windows')
        import ctypes
        from ctypes import wintypes
        # Hosted Windows runners can spell the temporary root with an 8.3 alias
        # while resolve() returns its long form. Compare canonical paths so this
        # safety assertion checks location instead of path spelling.
        resolved_root = self.root.resolve(strict=True)
        self.assertTrue(link.absolute().is_relative_to(self.root.absolute()))
        self.assertTrue(target.resolve(strict=True).is_relative_to(resolved_root))
        link.parent.mkdir(parents=True, exist_ok=True)
        link.mkdir()
        self.addCleanup(lambda: link.rmdir() if link.exists() else None)
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                      wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
        kernel.CreateFileW.restype = wintypes.HANDLE
        kernel.DeviceIoControl.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPVOID,
                                          wintypes.DWORD, wintypes.LPVOID, wintypes.DWORD,
                                          ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID]
        kernel.DeviceIoControl.restype = wintypes.BOOL
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel.CloseHandle.restype = wintypes.BOOL
        handle = kernel.CreateFileW(str(link), 0x40000000, 0, None, 3, 0x02200000, None)
        if handle == ctypes.c_void_p(-1).value:
            raise ctypes.WinError(ctypes.get_last_error())
        substitute = ('\\??\\' + str(target.resolve())).encode('utf-16-le')
        display = str(target.resolve()).encode('utf-16-le')
        paths = substitute + b'\0\0' + display + b'\0\0'
        data = struct.pack('<IHHHHHH', 0xA0000003, 8 + len(paths), 0,
                           0, len(substitute), len(substitute) + 2, len(display)) + paths
        returned = wintypes.DWORD()
        try:
            if not kernel.DeviceIoControl(handle, 0x900A4, data, len(data), None,
                                          0, ctypes.byref(returned), None):
                code = ctypes.get_last_error()
                if code in {1, 50, 1314}:
                    self.skipTest(f'Windows junction capability unavailable: {ctypes.WinError(code)}')
                raise ctypes.WinError(code)
        finally:
            kernel.CloseHandle(handle)

    def test_source_junction_rejected_without_writes(self):
        outside = self.root / 'outside'; outside.mkdir()
        (outside / 'keep.txt').write_text('preserve linked target', encoding='utf-8')
        self.make_junction(self.source / 'linked', outside)
        with self.assertRaises(ValueError):
            self.run_install(apply=True)
        self.assertFalse(self.home.exists())
        self.assertFalse(self.chome.exists())
        self.assertEqual('preserve linked target', (outside / 'keep.txt').read_text())

    def test_destination_ancestor_junction_rejected_without_writes(self):
        outside = self.root / 'outside'; outside.mkdir()
        (outside / 'keep.txt').write_text('preserve linked target', encoding='utf-8')
        self.make_junction(self.home / '.agents', outside)
        with self.assertRaises(ValueError):
            self.run_install(apply=True)
        self.assertFalse(self.chome.exists())
        self.assertEqual(['keep.txt'], [entry.name for entry in outside.iterdir()])
        self.assertEqual('preserve linked target', (outside / 'keep.txt').read_text())

    def test_catalog_output_rejects_parent_junction_before_writing(self):
        outside = self.root / 'outside'; outside.mkdir()
        keep = outside / 'catalog.json'
        keep.write_bytes(b'preserve original')
        alias = self.root / 'alias'
        self.make_junction(alias, outside)
        with self.assertRaises(ValueError):
            atomic_json(alias / 'catalog.json', {'unexpected': True}, replace=True)
        with self.assertRaises(ValueError):
            atomic_json(alias / 'new.json', {'unexpected': True})
        self.assertEqual(b'preserve original', keep.read_bytes())
        self.assertEqual(['catalog.json'], sorted(p.name for p in outside.iterdir()))

    def test_source_root_junction_rejected_without_writes(self):
        alias = self.root / 'source-alias'
        self.make_junction(alias, self.source)
        with self.assertRaises(ValueError):
            install(alias, scope='user', user_home=self.home, codex_home=self.chome, apply=True)
        self.assertFalse(self.home.exists())
        self.assertFalse(self.chome.exists())

    def test_cli_source_junction_rejected_without_writes(self):
        script_dir = self.source / 'scripts'; script_dir.mkdir()
        real_scripts = Path(__file__).resolve().parents[1] / 'scripts'
        for name in ('install.py', 'common.py'):
            shutil.copy2(real_scripts / name, script_dir / name)
        alias = self.root / 'source-alias'
        self.make_junction(alias, self.source)
        project = self.root / 'project'; project.mkdir()
        result = subprocess.run(
            [sys.executable, str(alias / 'scripts' / 'install.py'), '--scope', 'project',
             '--project', str(project), '--apply'],
            capture_output=True, text=True, encoding='utf-8', timeout=10)
        self.assertEqual(2, result.returncode, result.stdout + result.stderr)
        self.assertEqual('INSTALLATION_FAILED', json.loads(result.stdout)['status'])
        self.assertEqual([], list(project.iterdir()))
        self.assertFalse(self.home.exists())
        self.assertFalse(self.chome.exists())

    def test_existing_skill_junction_rejected_before_backup_or_replacement(self):
        first = self.run_install(apply=True)
        dest = Path(first['skill_path'])
        guidance = Path(first['guidance_path']).read_bytes()
        backup_base = Path(first['backup_path']).parent
        backups = set(backup_base.iterdir())
        outside = self.root / 'outside'; outside.mkdir()
        (outside / 'keep.txt').write_text('preserve linked target', encoding='utf-8')
        self.make_junction(dest / 'linked', outside)
        (self.source / 'SKILL.md').write_text('CHANGED candidate', encoding='utf-8')
        with self.assertRaises(ValueError):
            self.run_install(apply=True)
        self.assertEqual(backups, set(backup_base.iterdir()))
        self.assertEqual(guidance, Path(first['guidance_path']).read_bytes())
        self.assertEqual('SYNTHETIC skill fixture', (dest / 'SKILL.md').read_text())
        self.assertEqual('preserve linked target', (outside / 'keep.txt').read_text())

    def test_guidance_and_backup_ancestor_junctions_rejected_without_writes(self):
        for location in ('guidance', 'backup'):
            with self.subTest(location=location):
                self.chome = self.root / location / 'codex'
                outside = self.root / location / 'outside'; outside.mkdir(parents=True)
                (outside / 'keep.txt').write_text('preserve linked target', encoding='utf-8')
                link = self.chome if location == 'guidance' else self.chome / 'modelrouter-backups'
                self.make_junction(link, outside)
                with self.assertRaises(ValueError):
                    self.run_install(apply=True)
                self.assertFalse(self.home.exists())
                self.assertFalse((self.chome / 'AGENTS.md').exists())
                self.assertEqual(['keep.txt'], [entry.name for entry in outside.iterdir()])
                self.assertEqual('preserve linked target', (outside / 'keep.txt').read_text())
    def test_dry_run_no_writes(self):
        self.assertEqual('DRY_RUN', self.run_install()['status'])
        self.assertFalse(self.home.exists())
        self.assertFalse(self.chome.exists())

    def test_cli_explicit_homes_keep_dry_run_out_of_real_home(self):
        script = Path(__file__).resolve().parents[1] / 'scripts' / 'install.py'
        run = subprocess.run(
            [sys.executable, '-B', str(script), '--dry-run',
             '--user-home', str(self.home), '--codex-home', str(self.chome)],
            capture_output=True, text=True, encoding='utf-8', timeout=20)
        self.assertEqual(0, run.returncode, run.stdout + run.stderr)
        out = json.loads(run.stdout)
        self.assertTrue(Path(out['skill_path']).is_relative_to(self.home))
        self.assertTrue(Path(out['guidance_path']).is_relative_to(self.chome))
        self.assertFalse(self.home.exists())
        self.assertFalse(self.chome.exists())
    def test_installs_files_does_not_claim_activation(self):
        out = self.run_install(apply=True)
        self.assertEqual('INSTALLED_FILES_ONLY', out['status'])
        self.assertTrue(Path(out['skill_path'], 'SKILL.md').exists())
        self.assertFalse(out['live_activation_verified'])
        self.assertFalse((self.chome / 'config.toml').exists())
    def test_preserves_original_guidance_and_backup(self):
        self.chome.mkdir()
        original = b'Existing rule: preserve real tests.\r\n'
        (self.chome / 'AGENTS.md').write_bytes(original)
        out = self.run_install(apply=True)
        self.assertTrue((self.chome / 'AGENTS.md').read_bytes().startswith(original))
        self.assertEqual(original, (Path(out['backup_path']) / 'AGENTS.md').read_bytes())
    def test_second_install_idempotent_guidance(self):
        one = self.run_install(apply=True)
        before = Path(one['guidance_path']).read_bytes()
        two = self.run_install(apply=True)
        self.assertEqual(before, Path(two['guidance_path']).read_bytes())
        self.assertEqual(1, before.decode().count(BEGIN))
        self.assertTrue((Path(two['backup_path']) / 'previous-skill' / 'SKILL.md').exists())

    def test_upgrade_migrates_legacy_skill_and_managed_guidance(self):
        legacy = self.home / '.agents' / 'skills' / 'model-auto-router'
        legacy.mkdir(parents=True)
        (legacy / 'SKILL.md').write_text(self.legacy_skill, encoding='utf-8')
        self.chome.mkdir()
        (self.chome / 'AGENTS.md').write_text(
            LEGACY_BEGIN + '\nLegacy managed guidance\n' + LEGACY_END + '\n',
            encoding='utf-8')
        out = self.run_install(apply=True)
        guidance = Path(out['guidance_path']).read_text(encoding='utf-8')
        self.assertTrue(out['legacy_skill_detected'])
        self.assertTrue(out['legacy_skill_removed'])
        self.assertFalse(legacy.exists())
        retired = Path(out['legacy_retired_path'])
        self.assertTrue(retired.is_relative_to(self.home / '.agents' / 'modelrouter-retired'))
        self.assertEqual(self.legacy_skill, (retired / 'SKILL.md').read_text())
        self.assertTrue(Path(out['skill_path'], 'SKILL.md').exists())
        self.assertIn(BEGIN, guidance)
        self.assertNotIn(LEGACY_BEGIN, guidance)
        self.assertEqual(
            self.legacy_skill,
            (Path(out['backup_path']) / 'previous-skill' / 'SKILL.md').read_text())

    def test_legacy_upgrade_dry_run_writes_nothing(self):
        legacy = self.home / '.agents' / 'skills' / 'model-auto-router'
        legacy.mkdir(parents=True)
        (legacy / 'SKILL.md').write_text(self.legacy_skill, encoding='utf-8')
        self.chome.mkdir()
        guidance = self.chome / 'AGENTS.md'
        original = LEGACY_BEGIN + '\nLegacy managed guidance\n' + LEGACY_END + '\n'
        guidance.write_text(original, encoding='utf-8')
        out = self.run_install()
        self.assertTrue(out['legacy_skill_detected'])
        self.assertFalse(out['legacy_skill_removed'])
        self.assertTrue(legacy.exists())
        self.assertFalse(Path(out['skill_path']).exists())
        self.assertEqual(original, guidance.read_text(encoding='utf-8'))
        self.assertFalse(Path(out['backup_path']).exists())

    def test_current_and_legacy_skill_directories_refuse_ambiguous_upgrade(self):
        current = self.home / '.agents' / 'skills' / 'modelrouter'
        legacy = self.home / '.agents' / 'skills' / 'model-auto-router'
        for path in (current, legacy):
            path.mkdir(parents=True, exist_ok=True)
            (path / 'SKILL.md').write_text('synthetic', encoding='utf-8')
        with self.assertRaises(ValueError):
            self.run_install(apply=True)
        self.assertFalse(self.chome.exists())

    def test_unidentified_legacy_named_directory_is_preserved_and_refused(self):
        legacy = self.home / '.agents' / 'skills' / 'model-auto-router'
        legacy.mkdir(parents=True)
        keep = legacy / 'keep.txt'
        keep.write_text('unrelated data', encoding='utf-8')
        with self.assertRaises(ValueError):
            self.run_install(apply=True)
        self.assertEqual('unrelated data', keep.read_text(encoding='utf-8'))
        self.assertFalse((self.home / '.agents' / 'skills' / 'modelrouter').exists())
        self.assertFalse(self.chome.exists())
    def test_effective_override_merged(self):
        self.chome.mkdir()
        (self.chome / 'AGENTS.override.md').write_text('Temporary existing override', encoding='utf-8')
        (self.chome / 'AGENTS.md').write_text('Preserve base', encoding='utf-8')
        out = self.run_install(apply=True)
        self.assertEqual('AGENTS.override.md', Path(out['guidance_path']).name)
        self.assertEqual('Preserve base', (self.chome / 'AGENTS.md').read_text())
    def test_empty_override_does_not_shadow(self):
        self.chome.mkdir()
        (self.chome / 'AGENTS.override.md').write_text('  \n', encoding='utf-8')
        self.assertEqual('AGENTS.md', Path(self.run_install()['guidance_path']).name)
    def test_project_install(self):
        project = self.root / 'project'; project.mkdir()
        out = install(self.source, scope='project', user_home=self.home, codex_home=self.chome, project=project, apply=True)
        self.assertTrue(Path(out['skill_path']).is_relative_to(project))
        self.assertEqual(project / 'AGENTS.md', Path(out['guidance_path']))
    def test_broken_markers_no_writes(self):
        self.chome.mkdir()
        (self.chome / 'AGENTS.md').write_text(BEGIN, encoding='utf-8')
        with self.assertRaises(ValueError): self.run_install(apply=True)
        self.assertFalse(self.home.exists())
    def test_duplicate_managed_blocks_rejected(self):
        with self.assertRaises(ValueError): merge_guidance(self.snippet * 2, self.snippet)

    def test_current_and_legacy_managed_blocks_are_rejected_together(self):
        legacy = LEGACY_BEGIN + '\nlegacy\n' + LEGACY_END + '\n'
        with self.assertRaises(ValueError):
            merge_guidance(self.snippet + legacy, self.snippet)

    def test_current_override_and_legacy_base_blocks_are_rejected_before_writes(self):
        self.chome.mkdir()
        base = self.chome / 'AGENTS.md'
        override = self.chome / 'AGENTS.override.md'
        legacy = LEGACY_BEGIN + '\nlegacy base\n' + LEGACY_END + '\n'
        base.write_text(legacy, encoding='utf-8')
        override.write_text(self.snippet, encoding='utf-8')
        with self.assertRaises(ValueError):
            self.run_install(apply=True)
        self.assertEqual(legacy, base.read_text(encoding='utf-8'))
        self.assertEqual(self.snippet, override.read_text(encoding='utf-8'))
        self.assertFalse(self.home.exists())
        self.assertFalse((self.chome / 'modelrouter-backups').exists())

    def test_duplicate_current_blocks_across_guidance_files_are_rejected(self):
        self.chome.mkdir()
        base = self.chome / 'AGENTS.md'
        override = self.chome / 'AGENTS.override.md'
        base.write_text(self.snippet, encoding='utf-8')
        override.write_text(self.snippet, encoding='utf-8')
        with self.assertRaises(ValueError):
            self.run_install(apply=True)
        self.assertEqual(self.snippet, base.read_text(encoding='utf-8'))
        self.assertEqual(self.snippet, override.read_text(encoding='utf-8'))
        self.assertFalse(self.home.exists())

    def test_inactive_base_managed_block_with_unmarked_override_is_rejected(self):
        for label, block in (
                ('current', self.snippet),
                ('legacy', LEGACY_BEGIN + '\nlegacy base\n' + LEGACY_END + '\n')):
            with self.subTest(label=label):
                self.chome = self.root / ('codex-' + label)
                self.chome.mkdir()
                base = self.chome / 'AGENTS.md'
                override = self.chome / 'AGENTS.override.md'
                base.write_text(block, encoding='utf-8')
                override.write_text('Unrelated active override\n', encoding='utf-8')
                with self.assertRaises(ValueError):
                    self.run_install(apply=True)
                self.assertEqual(block, base.read_text(encoding='utf-8'))
                self.assertEqual('Unrelated active override\n', override.read_text(encoding='utf-8'))
                self.assertFalse(self.home.exists())
    def test_legacy_router_guidance_warned_preserved(self):
        self.chome.mkdir()
        (self.chome / 'AGENTS.md').write_text('Old model-auto-router instruction', encoding='utf-8')
        out = self.run_install(apply=True)
        self.assertTrue(out['warnings'])
        self.assertIn('Old model-auto-router', Path(out['guidance_path']).read_text())
    def test_guidance_write_failure_restores_previous_install(self):
        first = self.run_install(apply=True)
        old_skill = Path(first['skill_path'], 'SKILL.md').read_bytes()
        old_guidance = Path(first['guidance_path']).read_bytes()
        (self.source / 'SKILL.md').write_text('CHANGED synthetic candidate', encoding='utf-8')
        real_replace = os.replace
        def fail_guidance(src, dst):
            if Path(dst).name == 'AGENTS.md':
                raise OSError('synthetic write failure')
            return real_replace(src, dst)
        with mock.patch('install.os.replace', side_effect=fail_guidance):
            with self.assertRaises(OSError): self.run_install(apply=True)
        self.assertEqual(old_skill, Path(first['skill_path'], 'SKILL.md').read_bytes())
        self.assertEqual(old_guidance, Path(first['guidance_path']).read_bytes())

    def test_legacy_upgrade_guidance_failure_keeps_legacy_and_removes_new_copy(self):
        legacy = self.home / '.agents' / 'skills' / 'model-auto-router'
        legacy.mkdir(parents=True)
        (legacy / 'SKILL.md').write_text(self.legacy_skill, encoding='utf-8')
        self.chome.mkdir()
        guidance = self.chome / 'AGENTS.md'
        original = (LEGACY_BEGIN + '\nLegacy managed guidance\n' + LEGACY_END + '\n').encode()
        guidance.write_bytes(original)
        real_replace = os.replace
        def fail_guidance(src, dst):
            if Path(dst).name == 'AGENTS.md':
                raise OSError('synthetic guidance write failure')
            return real_replace(src, dst)
        with mock.patch('install.os.replace', side_effect=fail_guidance):
            with self.assertRaises(OSError):
                self.run_install(apply=True)
        self.assertTrue(legacy.exists())
        self.assertEqual(self.legacy_skill, (legacy / 'SKILL.md').read_text())
        self.assertFalse((self.home / '.agents' / 'skills' / 'modelrouter').exists())
        self.assertEqual(original, guidance.read_bytes())

    def test_legacy_retirement_failure_rolls_back_new_skill_and_guidance(self):
        legacy = self.home / '.agents' / 'skills' / 'model-auto-router'
        legacy.mkdir(parents=True)
        (legacy / 'SKILL.md').write_text(self.legacy_skill, encoding='utf-8')
        self.chome.mkdir()
        guidance = self.chome / 'AGENTS.md'
        original = (LEGACY_BEGIN + '\nLegacy managed guidance\n' + LEGACY_END + '\n').encode()
        guidance.write_bytes(original)
        real_replace = os.replace
        def fail_retirement(src, dst):
            if Path(src) == legacy:
                raise OSError('synthetic legacy retirement failure')
            return real_replace(src, dst)
        with mock.patch('install.os.replace', side_effect=fail_retirement):
            with self.assertRaises(OSError):
                self.run_install(apply=True)
        self.assertTrue(legacy.exists())
        self.assertEqual(self.legacy_skill, (legacy / 'SKILL.md').read_text())
        self.assertFalse((self.home / '.agents' / 'skills' / 'modelrouter').exists())
        self.assertEqual(original, guidance.read_bytes())

    def test_utf8_bom_preserved(self):
        self.chome.mkdir()
        before = b'\xef\xbb\xbfPreserve BOM\n'
        (self.chome / 'AGENTS.md').write_bytes(before)
        out = self.run_install(apply=True)
        self.assertTrue(Path(out['guidance_path']).read_bytes().startswith(before))

    def test_source_symlink_rejected(self):
        try:
            (self.source / 'link').symlink_to(self.source / 'SKILL.md')
        except NotImplementedError as exc:
            self.skipTest(f'symlink capability unavailable: {exc}')
        except OSError as exc:
            if (getattr(exc, 'winerror', None) in {1, 50, 1314}
                    or exc.errno in {errno.ENOSYS, errno.EOPNOTSUPP}):
                self.skipTest(f'symlink capability unavailable: {exc}')
            raise
        with self.assertRaises(ValueError): self.run_install(apply=True)
        self.assertFalse(self.home.exists())
        self.assertFalse(self.chome.exists())
    def test_reversed_markers_rejected(self):
        with self.assertRaises(ValueError): merge_guidance(END + BEGIN, self.snippet)

class CommonTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.path = Path(temp.name) / 'data.json'
    def test_duplicate_json_key_rejected(self):
        self.path.write_text('{"a":1,"a":2}', encoding='utf-8')
        with self.assertRaises(ValueError): load_json(self.path)
    def test_nan_json_rejected(self):
        self.path.write_text('{"a":NaN}', encoding='utf-8')
        with self.assertRaises(ValueError): load_json(self.path)
    def test_atomic_roundtrip(self):
        atomic_json(self.path, {'meaning': '合成測試'})
        self.assertEqual({'meaning': '合成測試'}, load_json(self.path))

    def test_output_refuses_unrequested_overwrite(self):
        self.path.write_bytes(b'keep')
        with self.assertRaises(ValueError):
            atomic_json(self.path, {'overwrite': True})
        self.assertEqual(b'keep', self.path.read_bytes())

    def test_output_replace_requires_explicit_flag(self):
        self.path.write_bytes(b'old')
        atomic_json(self.path, {'new': True}, replace=True)
        self.assertEqual({'new': True}, load_json(self.path))

    def test_output_rejects_symlinked_parent_and_preserves_outside(self):
        outside = self.path.parent / 'outside'; outside.mkdir()
        alias = self.path.parent / 'alias'
        try:
            alias.symlink_to(outside, target_is_directory=True)
        except OSError as exc:
            if getattr(exc, 'winerror', None) == 1314:
                self.skipTest('Windows symlink privilege unavailable')
            raise
        with self.assertRaises(ValueError):
            atomic_json(alias / 'catalog.json', {'bad': True})
        self.assertEqual([], list(outside.iterdir()))
    def test_display_name_does_not_become_model_id(self):
        with self.assertRaises(ValueError): normalize_model({'displayName': 'UI name'})
    def test_missing_modalities_conservative(self):
        m = normalize_model({'model': 'fixture-id', 'supportedReasoningEfforts': []})
        self.assertEqual(['text'], m['input_modalities'])
        self.assertFalse(m['modalities_observed'])
    def test_default_effort_must_be_supported(self):
        with self.assertRaises(ValueError): normalize_model({'model': 'fixture-id', 'defaultReasoningEffort': 'unknown', 'supportedReasoningEfforts': []})
    def test_unknown_effort_retained_as_data(self):
        m = normalize_model({'model': 'fixture-id', 'supportedReasoningEfforts': [{'reasoningEffort': 'future-value', 'description': 'Synthetic only'}]})
        self.assertEqual('future-value', m['efforts'][0]['value'])

    def test_release_log_normalization_redacts_raw_and_json_escaped_paths(self):
        secret = r'C:\Users\private\repo'
        data = (secret + '\n' + json.dumps({'path': secret})).encode('utf-8')
        cleaned = normalized_log(data, [(secret, '<SOURCE>')]).decode('utf-8')
        self.assertNotIn(secret, cleaned)
        self.assertNotIn(json.dumps(secret)[1:-1], cleaned)
        self.assertEqual(2, cleaned.count('<SOURCE>'))
    def test_duplicate_effort_rejected(self):
        entry = {'reasoningEffort': 'medium', 'description': 'fixture'}
        with self.assertRaises(ValueError): normalize_model({'model': 'fixture-id', 'supportedReasoningEfforts': [entry, entry]})

if __name__ == '__main__': unittest.main()
