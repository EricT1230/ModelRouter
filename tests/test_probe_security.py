"""Probe CLI boundary checks; never launch a real model client."""
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/modelrouter/scripts'))
import probe_models


class ProbeSecurityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.binary = self.root / 'synthetic-codex.exe'
        with open(sys.executable, 'rb') as handle:
            header = handle.read(4)
        self.binary.write_bytes(header + b'SYNTHETIC, never executable')
        self.digest = hashlib.sha256(self.binary.read_bytes()).hexdigest()
        self.args = ['probe', '--codex', str(self.binary), '--codex-sha256', self.digest,
                     '--output-root', str(self.root), '--output', str(self.root / 'catalog.json')]

    def invoke(self, args):
        output = io.StringIO()
        with mock.patch.object(sys, 'argv', args), contextlib.redirect_stdout(output):
            code = probe_models.main()
        return code, json.loads(output.getvalue())

    def test_valid_pinned_binary_and_output_write_unbound_catalog(self):
        with mock.patch.object(probe_models, 'collect_catalog', return_value={'models': [], 'source': {'session_bound': False}}) as collect:
            code, result = self.invoke(self.args)
        self.assertEqual(0, code)
        self.assertEqual(str(self.binary), collect.call_args.args[0][0])
        self.assertEqual(self.digest, result['executable_sha256'])
        self.assertFalse(json.loads((self.root / 'catalog.json').read_text())['source']['session_bound'])

    def test_invalid_trust_or_output_never_starts_client(self):
        cases = [
            ('--codex', 'codex'),
            ('--codex-sha256', '0' * 64),
            ('--output', str(self.root.parent / 'outside.json')),
            ('--output', str(self.root / 'config.toml')),
            ('--timeout', '-1'),
        ]
        for flag, value in cases:
            args = list(self.args)
            if flag in args:
                args[args.index(flag) + 1] = value
            else:
                args += [flag, value]
            with self.subTest(flag=flag), mock.patch.object(probe_models, 'collect_catalog') as collect:
                code, result = self.invoke(args)
                self.assertEqual(2, code)
                self.assertEqual('DISCOVERY_FAILED', result['status'])
                collect.assert_not_called()
        self.assertFalse((self.root / 'catalog.json').exists())

    def test_existing_output_preserved_before_launch(self):
        target = self.root / 'catalog.json'
        target.write_bytes(b'private data')
        with mock.patch.object(probe_models, 'collect_catalog') as collect:
            code, _ = self.invoke(self.args)
            self.assertEqual(2, code)
            collect.assert_not_called()
        self.assertEqual(b'private data', target.read_bytes())

    def test_script_wrapper_rejected_even_with_matching_hash(self):
        wrapper = self.root / 'codex.cmd'
        wrapper.write_bytes(self.binary.read_bytes())
        args = list(self.args); args[args.index('--codex') + 1] = str(wrapper)
        with mock.patch.object(probe_models, 'collect_catalog') as collect:
            code, _ = self.invoke(args)
            self.assertEqual(2, code)
            collect.assert_not_called()

    def test_extensionless_script_with_matching_hash_never_starts(self):
        wrapper = self.root / ('codex.exe' if os.name == 'nt' else 'codex')
        wrapper.write_bytes(b'#!/bin/sh\nexit 0\n')
        args = list(self.args)
        args[args.index('--codex') + 1] = str(wrapper)
        args[args.index('--codex-sha256') + 1] = hashlib.sha256(wrapper.read_bytes()).hexdigest()
        with mock.patch.object(probe_models, 'collect_catalog') as collect:
            code, _ = self.invoke(args)
            self.assertEqual(2, code)
            collect.assert_not_called()

    def test_file_ancestor_refused_before_client_starts(self):
        parent = self.root / 'ordinary-file'
        parent.write_bytes(b'keep')
        args = list(self.args)
        args[args.index('--output') + 1] = str(parent / 'catalog.json')
        with mock.patch.object(probe_models, 'collect_catalog') as collect:
            code, _ = self.invoke(args)
            self.assertEqual(2, code)
            collect.assert_not_called()
