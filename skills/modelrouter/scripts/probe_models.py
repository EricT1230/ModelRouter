#!/usr/bin/env python3
"""Read model/list via an installed local Codex app-server; never start an inference turn.

Output remains unbound to the user's active GUI/IDE session until host identity is checked.
The CLI may perform its normal startup/auth/network reads. No login or config writes sent.
"""
from __future__ import annotations
import argparse
import hashlib
import os
import json
import queue
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any
from common import atomic_json, nonempty, normalize_model, output_path, regular_path, require, utcnow

MAX_LINE = 2 * 1024 * 1024
MAX_WIRE_BYTES = 16 * 1024 * 1024
MAX_PAGES = 50


class ReadOnlyRPC:
    def __init__(self, command: list[str], timeout: float):
        require(0 < timeout <= 120, 'timeout must be between 0 and 120 seconds')
        self.deadline = time.monotonic() + timeout
        self.events: queue.Queue[Any] = queue.Queue(maxsize=1024)
        self.proc = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=subprocess.DEVNULL, shell=False)
        self.counter = 0
        self.reader = threading.Thread(target=self._read, daemon=True)
        self.reader.start()

    def _read(self) -> None:
        total = 0
        try:
            assert self.proc.stdout is not None
            while True:
                raw = self.proc.stdout.readline(MAX_LINE + 1)
                if not raw:
                    self.events.put_nowait(RuntimeError('app-server closed stdout'))
                    return
                total += len(raw)
                require(len(raw) <= MAX_LINE and total <= MAX_WIRE_BYTES, 'app-server response size limit')
                msg = json.loads(raw.decode('utf-8'))
                require(isinstance(msg, dict), 'app-server JSON object required')
                self.events.put_nowait(msg)
        except Exception as exc:
            try:
                self.events.put_nowait(exc)
            except queue.Full:
                # Consumer will eventually time out; never silently accept a partial catalog.
                pass

    def _send(self, message: dict[str, Any]) -> None:
        require(self.proc.poll() is None, 'app-server exited')
        assert self.proc.stdin is not None
        self.proc.stdin.write((json.dumps(message) + '\n').encode('utf-8'))
        self.proc.stdin.flush()

    def notify_initialized(self) -> None:
        self._send({'method': 'initialized', 'params': {}})

    def call(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        require(method in {'initialize', 'model/list'}, 'read-only protocol allowlist violation')
        self.counter += 1
        request_id = self.counter
        self._send({'method': method, 'id': request_id, 'params': params})
        while True:
            remaining = self.deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError('catalog discovery timed out; cached file was not replaced')
            try:
                msg = self.events.get(timeout=remaining)
            except queue.Empty as exc:
                raise TimeoutError('catalog discovery timed out; cached file was not replaced') from exc
            if isinstance(msg, Exception):
                raise RuntimeError(f'app-server stream error: {msg}') from msg
            if 'method' in msg and 'id' in msg:
                raise RuntimeError('unexpected server request; no approvals or actions will be granted')
            if msg.get('id') != request_id:
                continue
            if 'error' in msg:
                code = msg['error'].get('code') if isinstance(msg['error'], dict) else 'unknown'
                raise RuntimeError(f'{method} rejected (code {code}); no credentials/config were modified')
            result = msg.get('result')
            require(isinstance(result, dict), 'app-server result object required')
            return result

    def close(self) -> None:
        if self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait(timeout=3)
        self.reader.join(timeout=1)
        for stream in (self.proc.stdin, self.proc.stdout):
            if stream is not None:
                stream.close()


def collect_catalog(command: list[str], *, host_scope: str,
                    timeout: float = 30, version: str | None = None) -> dict[str, Any]:
    """Tests use an explicitly synthetic server command; production CLI uses installed codex."""
    nonempty(host_scope, 'host_scope')
    rpc = ReadOnlyRPC(command, timeout)
    try:
        rpc.call('initialize', {'clientInfo': {'name': 'modelrouter_catalog',
                  'title': 'ModelRouter catalog probe', 'version': '5.7.0'}})
        rpc.notify_initialized()
        models: list[dict[str, Any]] = []
        ids: set[str] = set()
        cursors: set[str] = set()
        cursor: str | None = None
        for _ in range(MAX_PAGES):
            params: dict[str, Any] = {'limit': 100, 'includeHidden': False}
            if cursor is not None:
                params['cursor'] = cursor
            page = rpc.call('model/list', params)
            require(isinstance(page.get('data'), list), 'model/list data must be a list')
            for raw in page['data']:
                model = normalize_model(raw)
                require(model['id'] not in ids, 'duplicate model across catalog pages')
                ids.add(model['id'])
                models.append(model)
            require('nextCursor' in page, 'pagination completion is unknown')
            cursor = page['nextCursor']
            if cursor is None:
                break
            nonempty(cursor, 'nextCursor')
            require(cursor not in cursors, 'repeated pagination cursor')
            cursors.add(cursor)
        else:
            raise RuntimeError('pagination cap reached; refusing incomplete catalog')
        return {'schema_version': 1, 'illustrative_only': False,
                'source': {'kind': 'codex_app_server_model_list',
                           'source_ref': 'local installed CLI: initialize + paginated model/list',
                           'host_scope': host_scope, 'cli_version': version,
                           'observed_at': utcnow().isoformat(), 'complete': True,
                           'session_bound': False},
                'models': sorted(models, key=lambda m: m['id'])}
    finally:
        rpc.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--output-root', type=Path, required=True, help='Existing trusted output directory')
    parser.add_argument('--replace', action='store_true', help='Explicitly replace an existing regular JSON file')
    parser.add_argument('--codex', type=Path, required=True, help='Absolute trusted native executable; no PATH lookup')
    parser.add_argument('--codex-sha256', required=True, help='Expected executable hash from a trusted installation')
    parser.add_argument('--host-scope', default='unbound-local-cli')
    parser.add_argument('--timeout', type=float, default=30)
    args = parser.parse_args()
    try:
        require(0 < args.timeout <= 120, 'timeout must be between 0 and 120 seconds')
        require(args.codex.is_absolute(), 'codex must be an absolute executable path')
        executable = regular_path(args.codex)
        require(executable.is_file(), 'codex executable is missing')
        require(executable.suffix.lower() not in {'.cmd', '.bat', '.ps1', '.sh', '.py'},
                'script wrappers are not accepted; select the native Codex executable')
        require(os.name != 'nt' or executable.suffix.lower() == '.exe', 'Windows requires a native .exe')
        expected = args.codex_sha256.lower()
        require(len(expected) == 64 and all(c in '0123456789abcdef' for c in expected), 'invalid executable SHA-256')
        digest = hashlib.sha256()
        with executable.open('rb') as handle:
            header = handle.read(4)
            native = (header[:2] == b'MZ' if os.name == 'nt' else
                      header == b'\x7fELF' or header in {
                          b'\xfe\xed\xfa\xce', b'\xce\xfa\xed\xfe',
                          b'\xfe\xed\xfa\xcf', b'\xcf\xfa\xed\xfe',
                          b'\xca\xfe\xba\xbe', b'\xbe\xba\xfe\xca',
                          b'\xca\xfe\xba\xbf', b'\xbf\xba\xfe\xca'})
            require(native, 'native executable header required; scripts are not accepted')
            handle.seek(0)
            for chunk in iter(lambda: handle.read(1024 * 1024), b''):
                digest.update(chunk)
        require(digest.hexdigest() == expected, 'executable SHA-256 mismatch; client was not started')
        target = output_path(args.output, root=args.output_root, replace=args.replace)
        catalog = collect_catalog([str(executable), 'app-server'], host_scope=args.host_scope,
                                  timeout=args.timeout, version=None)
        catalog['source'].update(executable_path=str(executable), executable_sha256=expected)
        atomic_json(target, catalog, root=args.output_root, replace=args.replace)
        output = {'status': 'CATALOG_DISCOVERED', 'path': str(args.output),
                  'models': len(catalog['models']), 'session_bound': False,
                  'inference_turn_started': False,
                  'executable_path': str(executable), 'executable_sha256': expected,
                  'next': 'Confirm active-host/account scope, then bootstrap evidence-backed profiles.'}
        code = 0
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        output = {'status': 'DISCOVERY_FAILED', 'reason': str(exc), 'inference_turn_started': False}
        code = 2
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return code

if __name__ == '__main__':
    sys.exit(main())
