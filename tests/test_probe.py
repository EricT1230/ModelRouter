"""Protocol tests against the synthetic subprocess, not an installed Codex."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills' / 'modelrouter' / 'scripts'))
from probe_models import collect_catalog

class ProbeTests(unittest.TestCase):
    def probe(self, mode='normal', timeout=3):
        return collect_catalog([sys.executable, str(Path(__file__).with_name('fake_appserver.py')), mode],
                               host_scope='synthetic-host', timeout=timeout)
    def test_paginated_catalog_unbound(self):
        out = self.probe()
        self.assertEqual(2, len(out['models']))
        self.assertTrue(out['source']['complete'])
        self.assertFalse(out['source']['session_bound'])
        self.assertEqual('synthetic-model-1', out['models'][0]['id'])
    def test_unknown_effort_preserved(self):
        self.assertIn('future-native', [e['value'] for e in self.probe('unknown-effort')['models'][0]['efforts']])
    def test_timeout_never_partial_success(self):
        with self.assertRaises(TimeoutError): self.probe('timeout', timeout=0.25)
    def test_rpc_error(self):
        with self.assertRaises(RuntimeError): self.probe('error')
    def test_no_server_approval(self):
        with self.assertRaises(RuntimeError): self.probe('server-request')
    def test_malformed_stream(self):
        with self.assertRaises(RuntimeError): self.probe('garbage')
    def test_early_process_exit(self):
        with self.assertRaises(RuntimeError): self.probe('exit')
    def test_duplicate_models_fail(self):
        with self.assertRaises(ValueError): self.probe('duplicate')
    def test_repeated_cursor_fails(self):
        with self.assertRaises(ValueError): self.probe('repeat-cursor')
    def test_missing_pagination_completion_fails(self):
        with self.assertRaises(ValueError): self.probe('missing-cursor')
    def test_invalid_timeout_rejected(self):
        with self.assertRaises(ValueError): self.probe(timeout=-1)

if __name__ == '__main__': unittest.main()
