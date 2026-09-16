"""Synthetic local tests of evidence_gate; no model calls or real-project claims."""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "skills" / "modelrouter" / "scripts" / "evidence_gate.py"
spec = importlib.util.spec_from_file_location("evidence_gate", SCRIPT)
assert spec and spec.loader
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


class EvidenceGateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.artifacts = self.root / "artifacts"
        self.artifacts.mkdir()
        self.manifest = {
            "schema_version": 1,
            "task_id": "SYNTHETIC-PARSER-TEST",
            "candidate_snapshot": "synthetic-candidate-v1",
            "protected_baseline": "synthetic-protected-v1",
            "author_ids": ["synthetic-author"],
            "acceptance_ids": ["AC1"],
            "minimum_isolation": "procedural_only",
            "checks": [{
                "id": "unit", "kind": "junit", "argv": ["test-command", "--junit"],
                "cwd": "/synthetic/candidate", "data_kind": "synthetic_unit_fixture",
                "acceptance_ids": ["AC1"], "minimum_executed": 1,
                "required_cases": ["sample::test_contract"], "allowed_skipped_cases": [],
            }],
        }
        check = copy.deepcopy(self.manifest["checks"][0])
        check.update({
            "status": "passed", "exit_code": 0, "candidate_snapshot": "synthetic-candidate-v1",
            "stdout": self.write("stdout.log", b"SYNTHETIC fixture output; not a real task run\n"),
            "stderr": self.write("stderr.log", b""),
            "report": self.write("tests.xml", b'<testsuite tests="1" failures="0" errors="0"><testcase classname="sample" name="test_contract"/></testsuite>'),
        })
        self.receipt = {
            "schema_version": 1, "task_id": "SYNTHETIC-PARSER-TEST",
            "snapshot_before": "synthetic-candidate-v1", "snapshot_after": "synthetic-candidate-v1",
            "protected_before": "synthetic-protected-v1", "protected_after": "synthetic-protected-v1",
            "runner_id": "synthetic-runner", "run_id": "synthetic-parser-fixture-run",
            "checks": [check],
            "review": {
                "reviewer_id": "synthetic-reviewer", "candidate_snapshot": "synthetic-candidate-v1",
                "verdict": "accept", "blocking_findings": [], "acceptance_ids": ["AC1"],
                "isolation": "procedural_only",
                "report": self.write("review.txt", b"SYNTHETIC review fixture, not an independent model review.\n"),
            },
        }

    def write(self, name, payload):
        (self.artifacts / name).write_bytes(payload)
        return {"path": name, "sha256": hashlib.sha256(payload).hexdigest()}

    def replace_xml(self, xml):
        self.receipt["checks"][0]["report"] = self.write("tests.xml", xml.encode())

    def result(self):
        return gate.validate(self.manifest, self.receipt, self.artifacts)

    def rejected(self, contains=None):
        result = self.result()
        self.assertEqual("REJECTED", result["status"], result)
        if contains:
            self.assertIn(contains, " ".join(result["issues"]))

    def test_consistent_synthetic_records_do_not_claim_authenticity(self):
        result = self.result()
        self.assertEqual("EVIDENCE_COMPLETE", result["status"])
        self.assertEqual("NOT_AUTHENTICATED_BY_THIS_TOOL", result["authenticity"])
        self.assertEqual("NOT_ESTABLISHED_BY_THIS_TOOL", result["semantic_correctness"])
        self.assertEqual(1, result["test_summaries"]["unit"]["executed"])

    def test_rejects_wrong_task(self):
        self.receipt["task_id"] = "other"
        self.rejected("task identity")

    def test_rejects_candidate_modified_after_run(self):
        self.receipt["snapshot_after"] = "different"
        self.rejected("stale/changed")

    def test_rejects_stale_check_snapshot(self):
        self.receipt["checks"][0]["candidate_snapshot"] = "old"
        self.rejected("stale candidate")

    def test_rejects_changed_protected_test_baseline(self):
        self.receipt["protected_after"] = "changed"
        self.rejected("protected baseline")

    def test_rejects_absent_runner_id(self):
        del self.receipt["runner_id"]
        self.rejected("runner_id")

    def test_rejects_nonzero_exit_even_with_passing_report(self):
        self.receipt["checks"][0]["exit_code"] = 1
        self.rejected("exit code")

    def test_rejects_boolean_instead_of_exit_code(self):
        self.receipt["checks"][0]["exit_code"] = False
        self.rejected("exit code")

    def test_rejects_zero_collected_tests(self):
        self.replace_xml('<testsuite tests="0"/>')
        self.rejected("zero test")

    def test_rejects_skipped_required_test(self):
        self.replace_xml('<testsuite><testcase classname="sample" name="test_contract"><skipped/></testcase></testsuite>')
        self.rejected("skipped")

    def test_rejects_failure_hidden_by_zero_exit_code(self):
        self.replace_xml('<testsuite><testcase classname="sample" name="test_contract"><failure message="bad"/></testcase></testsuite>')
        self.rejected("test failed")

    def test_rejects_suite_level_collection_error(self):
        self.replace_xml('<testsuite errors="1"><testcase classname="sample" name="test_contract"/></testsuite>')
        self.rejected("reports errors")

    def test_rejects_required_test_missing_from_selected_subset(self):
        self.replace_xml('<testsuite><testcase classname="sample" name="unrelated"/></testsuite>')
        self.rejected("required testcase")

    def test_rejects_inconsistent_suite_test_count(self):
        self.replace_xml('<testsuite tests="99"><testcase classname="sample" name="test_contract"/></testsuite>')
        self.rejected("inconsistent JUnit tests")

    def test_rejects_inconsistent_suite_skip_count(self):
        self.replace_xml('<testsuite tests="1" skipped="1"><testcase classname="sample" name="test_contract"/></testsuite>')
        self.rejected("inconsistent JUnit skipped")

    def test_rejects_too_few_executed_tests(self):
        self.manifest["checks"][0]["minimum_executed"] = 2
        self.rejected("too few")

    def test_rejects_notrun_status(self):
        self.replace_xml('<testsuite><testcase classname="sample" name="test_contract" status="notrun"/></testsuite>')
        self.rejected("not confirmed executed")

    def test_rejects_duplicate_testcase_identities(self):
        self.replace_xml('<testsuite><testcase classname="sample" name="test_contract"/><testcase classname="sample" name="test_contract"/></testsuite>')
        self.rejected("duplicate JUnit")

    def test_allows_preapproved_skip_only_outside_required_cases(self):
        self.manifest["checks"][0]["allowed_skipped_cases"] = ["sample::optional_platform"]
        self.replace_xml('<testsuite><testcase classname="sample" name="test_contract"/><testcase classname="sample" name="optional_platform"><skipped/></testcase></testsuite>')
        self.assertEqual("EVIDENCE_COMPLETE", self.result()["status"])

    def test_rejects_exempting_required_case_from_execution(self):
        self.manifest["checks"][0]["allowed_skipped_cases"] = ["sample::test_contract"]
        self.rejected("cannot be exempted")

    def test_rejects_missing_raw_log(self):
        (self.artifacts / "stdout.log").unlink()
        self.rejected()

    def test_rejects_modified_log_with_old_hash(self):
        (self.artifacts / "stdout.log").write_text("fabricated replacement")
        self.rejected("hash mismatch")

    def test_rejects_path_traversal(self):
        self.receipt["checks"][0]["stdout"]["path"] = "../outside"
        self.rejected("inside artifact root")

    def test_rejects_symlink_outside_artifact_root(self):
        outside = self.root / "outside"
        outside.write_bytes(b"outside")
        symlink = self.artifacts / "linked"
        try:
            symlink.symlink_to(outside)
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f"symlink unsupported: {exc}")
        self.receipt["checks"][0]["stdout"] = {"path": "linked", "sha256": hashlib.sha256(b"outside").hexdigest()}
        self.rejected("escapes root")

    def test_rejects_author_as_sole_approver(self):
        self.receipt["review"]["reviewer_id"] = "synthetic-author"
        self.rejected("author cannot")

    def test_rejects_missing_independent_review(self):
        del self.receipt["review"]
        self.rejected("review metadata")

    def test_rejects_review_for_other_candidate(self):
        self.receipt["review"]["candidate_snapshot"] = "old"
        self.rejected("different candidate")

    def test_rejects_pending_blocker(self):
        self.receipt["review"]["blocking_findings"] = ["AC1 fails"]
        self.rejected("blocking findings")

    def test_rejects_unaccepted_review(self):
        self.receipt["review"]["verdict"] = "needs_work"
        self.rejected("does not accept")

    def test_rejects_weaker_than_required_isolation(self):
        self.manifest["minimum_isolation"] = "runtime_enforced"
        self.rejected("insufficient declared")

    def test_rejects_silent_command_change(self):
        self.receipt["checks"][0]["argv"] = ["echo", "PASS"]
        self.rejected("argv mismatch")

    def test_rejects_mock_relabel_as_real_integration(self):
        self.manifest["checks"][0]["data_kind"] = "real_integration"
        self.rejected("data_kind mismatch")

    def test_rejects_unverified_required_criterion(self):
        self.manifest["acceptance_ids"].append("AC2")
        self.rejected("lack required check coverage")

    def test_rejects_review_omitting_a_criterion(self):
        self.receipt["review"]["acceptance_ids"] = ["different"]
        self.rejected("review does not cover")

    def test_rejects_missing_check(self):
        self.receipt["checks"] = []
        self.rejected()

    def test_rejects_duplicate_check_id(self):
        self.receipt["checks"].append(copy.deepcopy(self.receipt["checks"][0]))
        self.rejected("duplicate id")

    def test_rejects_not_executed_status(self):
        self.receipt["checks"][0]["status"] = "blocked"
        self.rejected("not passed")

    def test_rejects_dtd_in_report(self):
        self.replace_xml('<!DOCTYPE testsuite [<!ENTITY x "bad">]><testsuite><testcase name="x"/></testsuite>')
        self.rejected("DTD/entity")

    def test_rejects_dtd_and_entity_in_multibyte_xml(self):
        xml = ('<!DOCTYPE testsuite [<!ENTITY contract "test_contract">]>'
               '<testsuite><testcase classname="sample" name="&contract;"/></testsuite>')
        for encoding in ("utf-16", "utf-16-le", "utf-16-be", "utf-32", "utf-32-le", "utf-32-be"):
            with self.subTest(encoding=encoding):
                self.receipt["checks"][0]["report"] = self.write("tests.xml", xml.encode(encoding))
                self.rejected()

    def test_accepts_passing_utf16_xml_without_dtd(self):
        xml = '<testsuite><testcase classname="sample" name="test_contract"/></testsuite>'
        for encoding in ("utf-16", "utf-16-le", "utf-16-be"):
            with self.subTest(encoding=encoding):
                self.receipt["checks"][0]["report"] = self.write("tests.xml", xml.encode(encoding))
                self.assertEqual("EVIDENCE_COMPLETE", self.result()["status"])

    def test_rejects_malformed_xml(self):
        self.replace_xml('<testsuite>')
        self.rejected("malformed JUnit")

    def test_rejects_duplicate_json_keys(self):
        path = self.root / "duplicates.json"
        path.write_text('{"a":1,"a":2}')
        with self.assertRaises(gate.EvidenceError):
            gate.load_json(path)

    def test_rejects_unsupported_schema(self):
        self.receipt["schema_version"] = 2
        self.rejected("schema_version")

    def test_plain_command_check_requires_logs_and_matching_command(self):
        self.manifest["checks"][0]["kind"] = "command"
        self.receipt["checks"][0]["kind"] = "command"
        self.assertEqual("EVIDENCE_COMPLETE", self.result()["status"])
        del self.receipt["checks"][0]["stderr"]
        self.rejected()

    def test_cli_success_rejection_and_input_error_exit_codes(self):
        manifest_path = self.root / "manifest.json"
        receipt_path = self.root / "receipt.json"
        manifest_path.write_text(json.dumps(self.manifest))
        receipt_path.write_text(json.dumps(self.receipt))
        argv = [sys.executable, str(SCRIPT), "--manifest", str(manifest_path), "--receipt", str(receipt_path), "--artifacts", str(self.artifacts)]
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=10)
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        self.assertEqual("EVIDENCE_COMPLETE", json.loads(proc.stdout)["status"])
        self.receipt["checks"][0]["exit_code"] = 1
        receipt_path.write_text(json.dumps(self.receipt))
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=10)
        self.assertEqual(1, proc.returncode)
        receipt_path.write_text("not json")
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=10)
        self.assertEqual(2, proc.returncode)

    def test_cli_accepts_utf8_bom_records(self):
        manifest_path = self.root / "manifest.json"
        receipt_path = self.root / "receipt.json"
        manifest_path.write_text(json.dumps(self.manifest), encoding="utf-8-sig")
        receipt_path.write_text(json.dumps(self.receipt), encoding="utf-8-sig")
        argv = [sys.executable, str(SCRIPT), "--manifest", str(manifest_path), "--receipt", str(receipt_path), "--artifacts", str(self.artifacts)]
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=10)
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        self.assertEqual("EVIDENCE_COMPLETE", json.loads(proc.stdout)["status"])

    def test_cli_rejects_nonfinite_json_constants_in_either_record(self):
        manifest_path = self.root / "manifest.json"
        receipt_path = self.root / "receipt.json"
        argv = [sys.executable, str(SCRIPT), "--manifest", str(manifest_path), "--receipt", str(receipt_path), "--artifacts", str(self.artifacts)]
        for target in ("manifest", "receipt"):
            for constant in (float("nan"), float("inf"), float("-inf")):
                with self.subTest(target=target, constant=constant):
                    manifest, receipt = copy.deepcopy(self.manifest), copy.deepcopy(self.receipt)
                    record = manifest if target == "manifest" else receipt
                    record["metadata"] = {"invalid": constant}
                    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
                    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
                    proc = subprocess.run(argv, capture_output=True, text=True, timeout=10)
                    self.assertEqual(2, proc.returncode, proc.stdout + proc.stderr)
                    self.assertEqual("INPUT_ERROR", json.loads(proc.stdout)["status"])


if __name__ == "__main__":
    unittest.main()
