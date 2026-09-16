import copy
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "skills/modelrouter/scripts/routing_metrics.py"
TEMPLATE = REPO / "skills/modelrouter/templates/metrics-event.json"


class RoutingMetricsTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.state = self.root / "state"
        self.cli("init", "--state-root", self.state, "--host-scope", "test-host")

    def cli(self, *args, expected=0):
        result = subprocess.run([sys.executable, "-B", str(SCRIPT), *map(str, args)],
                                capture_output=True, text=True, encoding="utf-8", timeout=20)
        self.assertEqual(expected, result.returncode, result.stdout + result.stderr)
        return json.loads(result.stdout)

    def event(self, event_id, route, outcome="accepted", tokens=100, scope="scope-a"):
        data = json.loads(TEMPLATE.read_text(encoding="utf-8"))
        data.update({"event_id": event_id, "recorded_at": "2026-09-16T00:00:00Z",
                     "host_scope": "test-host", "evidence_scope": scope,
                     "task_id": "task-" + event_id, "task_bucket": "small-fix",
                     "route_label": route, "risk": "low", "outcome": outcome})
        data["quality"] = {"verification_level": "self-check",
                           "evidence_ref": "evidence/" + event_id if outcome == "accepted" else None}
        data["usage"]["total_tokens"] = tokens
        data["usage"]["source_ref"] = "host-receipt/" + event_id if tokens is not None else None
        return data

    def record(self, data, name=None, expected=0):
        source = self.root / ((name or data["event_id"]) + ".json")
        source.write_text(json.dumps(data), encoding="utf-8")
        return self.cli("record", "--state-root", self.state, "--input", source,
                        expected=expected)

    def test_init_is_idempotent_and_refuses_unrelated_directory(self):
        result = self.cli("init", "--state-root", self.state, "--host-scope", "test-host")
        self.assertEqual("ALREADY_INITIALIZED", result["status"])
        unrelated = self.root / "unrelated"; unrelated.mkdir()
        (unrelated / "keep.txt").write_text("keep", encoding="utf-8")
        self.cli("init", "--state-root", unrelated, "--host-scope", "test-host", expected=2)
        self.assertEqual("keep", (unrelated / "keep.txt").read_text())

    def test_record_is_idempotent_and_conflict_fails(self):
        data = self.event("stable-event", "parent")
        self.assertEqual("RECORDED", self.record(data)["status"])
        self.assertEqual("ALREADY_RECORDED", self.record(data, "retry")["status"])
        changed = copy.deepcopy(data); changed["usage"]["total_tokens"] = 101
        self.assertEqual("INPUT_ERROR", self.record(changed, "conflict", expected=2)["status"])

    def test_concurrent_identical_record_is_idempotent(self):
        data = self.event("concurrent-event", "parent")
        source = self.root / "concurrent.json"
        source.write_text(json.dumps(data), encoding="utf-8")
        command = [sys.executable, "-B", str(SCRIPT), "record", "--state-root",
                   str(self.state), "--input", str(source)]
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda _: subprocess.run(command, capture_output=True, text=True,
                                                              encoding="utf-8", timeout=20), range(8)))
        self.assertTrue(all(result.returncode == 0 for result in results),
                        [(result.returncode, result.stdout, result.stderr) for result in results])
        statuses = [json.loads(result.stdout)["status"] for result in results]
        self.assertEqual(1, statuses.count("RECORDED"))
        self.assertEqual(7, statuses.count("ALREADY_RECORDED"))

    def test_concurrent_conflicting_record_has_one_winner(self):
        first = self.event("conflicting-event", "parent", tokens=100)
        second = self.event("conflicting-event", "parent", tokens=101)
        paths = []
        for index, value in enumerate((first, second)):
            path = self.root / f"conflicting-{index}.json"
            path.write_text(json.dumps(value), encoding="utf-8")
            paths.append(path)

        def execute(path):
            return subprocess.run([sys.executable, "-B", str(SCRIPT), "record", "--state-root",
                                   str(self.state), "--input", str(path)], capture_output=True,
                                  text=True, encoding="utf-8", timeout=20)

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(execute, paths))
        self.assertEqual([0, 2], sorted(result.returncode for result in results))
        statuses = sorted(json.loads(result.stdout)["status"] for result in results)
        self.assertEqual(["INPUT_ERROR", "RECORDED"], statuses)

    def test_rejects_unknown_prompt_field_and_accepted_without_evidence(self):
        data = self.event("unknown", "parent"); data["prompt"] = "do not retain this"
        self.assertEqual("INPUT_ERROR", self.record(data, expected=2)["status"])
        data = self.event("no-evidence", "parent"); data["quality"]["evidence_ref"] = None
        self.assertEqual("INPUT_ERROR", self.record(data, expected=2)["status"])

    def test_rejects_unbounded_numbers_before_persistence(self):
        data = self.event("huge-token", "parent")
        data["usage"]["total_tokens"] = 10**401
        data["usage"]["source_ref"] = "host/huge"
        self.assertEqual("INPUT_ERROR", self.record(data, expected=2)["status"])
        data = self.event("huge-elapsed", "parent")
        data["usage"]["elapsed_seconds"] = 10**4000
        data["usage"]["source_ref"] = "host/huge"
        self.assertEqual("INPUT_ERROR", self.record(data, expected=2)["status"])
        summary = self.cli("summary", "--state-root", self.state)
        self.assertEqual(0, summary["events"])

    def test_numeric_boundaries_and_component_provenance(self):
        bounded = self.event("bounded-token", "parent", tokens=10**18)
        self.assertEqual("RECORDED", self.record(bounded)["status"])
        summary = self.cli("summary", "--state-root", self.state)
        self.assertEqual(10**18, summary["groups"][0]["tokens_per_accepted_task"])
        too_large = self.event("too-large-token", "parent", tokens=10**18 + 1)
        self.assertEqual("INPUT_ERROR", self.record(too_large, expected=2)["status"])
        component = self.event("component-only", "parent", tokens=None)
        component["usage"]["input_tokens"] = 25
        self.assertEqual("INPUT_ERROR", self.record(component, expected=2)["status"])

    def test_bounded_aggregate_does_not_overflow(self):
        sys.path.insert(0, str(SCRIPT.parent))
        try:
            from routing_metrics import summarize
            values = [self.event(f"aggregate-{index}", "parent", tokens=10**18)
                      for index in range(1000)]
            result = summarize(values)
        finally:
            sys.path.pop(0)
        self.assertEqual(10**21, result["groups"][0]["total_tokens"])
        self.assertEqual(10**18, result["groups"][0]["tokens_per_accepted_task"])

    def test_reader_waits_for_atomic_publication_link_to_settle(self):
        data = self.event("settling", "parent")
        source = self.root / "settling-source.json"
        source.write_text(json.dumps(data), encoding="utf-8")
        destination = self.state / "events" / ("0" * 64 + ".json")
        destination.parent.mkdir()
        os.link(source, destination)

        def unlink_source():
            import time
            time.sleep(0.05)
            source.unlink()

        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(unlink_source)
            sys.path.insert(0, str(SCRIPT.parent))
            try:
                from routing_metrics import stable_load_json
                self.assertEqual(data, stable_load_json(destination))
            finally:
                sys.path.pop(0)
            future.result()

    def test_summary_is_read_only_and_preserves_unknown_metering(self):
        self.record(self.event("unknown-meter", "parent", tokens=None))
        before = sorted((p.relative_to(self.state), p.read_bytes())
                        for p in self.state.rglob("*" ) if p.is_file())
        summary = self.cli("summary", "--state-root", self.state)
        after = sorted((p.relative_to(self.state), p.read_bytes())
                       for p in self.state.rglob("*") if p.is_file())
        self.assertEqual(before, after)
        self.assertEqual(0, summary["groups"][0]["token_coverage"])
        self.assertIsNone(summary["groups"][0]["tokens_per_accepted_task"])

    def test_comparison_is_failure_inclusive(self):
        for index, tokens in enumerate((100, 100, 100), 1):
            self.record(self.event(f"base-{index}", "baseline", tokens=tokens))
            self.record(self.event(f"candidate-{index}", "candidate", tokens=50))
        self.record(self.event("candidate-failure", "candidate", outcome="failed", tokens=60))
        result = self.cli("compare", "--state-root", self.state,
                          "--evidence-scope", "scope-a", "--task-bucket", "small-fix",
                          "--risk", "low", "--verification-level", "self-check",
                          "--baseline-route", "baseline", "--candidate-route", "candidate")
        self.assertEqual("COMPARISON_READY", result["status"])
        self.assertEqual(100, result["token_comparison"]["baseline"])
        self.assertEqual(70, result["token_comparison"]["candidate"])
        self.assertEqual("fewer", result["token_comparison"]["direction"])

    def test_comparison_requires_complete_metering_and_matched_scope(self):
        for index in range(3):
            self.record(self.event(f"base-{index}", "baseline", tokens=100))
            self.record(self.event(f"candidate-{index}", "candidate", tokens=None))
        result = self.cli("compare", "--state-root", self.state,
                          "--evidence-scope", "scope-a", "--task-bucket", "small-fix",
                          "--risk", "low", "--verification-level", "self-check",
                          "--baseline-route", "baseline", "--candidate-route", "candidate",
                          expected=1)
        self.assertEqual("INSUFFICIENT_EVIDENCE", result["status"])
        self.assertTrue(any("incomplete" in reason for reason in result["reasons"]))
        result = self.cli("compare", "--state-root", self.state,
                          "--evidence-scope", "different", "--task-bucket", "small-fix",
                          "--risk", "low", "--verification-level", "self-check",
                          "--baseline-route", "baseline", "--candidate-route", "candidate",
                          expected=1)
        self.assertTrue(all("no matching" in reason for reason in result["reasons"]))

    def test_output_requires_explicit_trusted_root(self):
        output = self.root / "reports" / "summary.json"
        result = self.cli("summary", "--state-root", self.state, "--output", output,
                          expected=2)
        self.assertEqual("INPUT_ERROR", result["status"])
        reports = self.root / "reports"; reports.mkdir()
        self.cli("summary", "--state-root", self.state, "--output", output,
                 "--output-root", reports)
        self.assertTrue(output.is_file())

    def test_compare_rejects_same_route_and_report_inside_state(self):
        result = self.cli("compare", "--state-root", self.state,
                          "--evidence-scope", "scope-a", "--task-bucket", "small-fix",
                          "--risk", "low", "--verification-level", "self-check",
                          "--baseline-route", "same", "--candidate-route", "same",
                          expected=2)
        self.assertEqual("INPUT_ERROR", result["status"])
        result = self.cli("summary", "--state-root", self.state,
                          "--output", self.state / "report.json", "--output-root", self.state,
                          expected=2)
        self.assertEqual("INPUT_ERROR", result["status"])


if __name__ == "__main__":
    unittest.main()
