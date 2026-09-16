#!/usr/bin/env python3
"""Check evidence consistency. This does NOT authenticate runs or prove correctness.

Python 3.10+, standard library only. No network access and no command execution.
Trusted orchestration must supply and protect the manifest, receipts and artifacts.
Exit 0: EVIDENCE_COMPLETE; exit 1: REJECTED; exit 2: malformed input/IO failure.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

MAX_JSON = 5 * 1024 * 1024
MAX_ARTIFACT = 50 * 1024 * 1024
MAX_XML = 10 * 1024 * 1024
HEX64 = re.compile(r"^[0-9a-f]{64}$")


class EvidenceError(ValueError):
    """Invalid or insufficient evidence; never interpret as success."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise EvidenceError(message)


def text(value: Any, field: str) -> str:
    require(isinstance(value, str) and bool(value.strip()), f"{field}: nonempty string required")
    return value


def strings(value: Any, field: str, *, nonempty: bool = True) -> list[str]:
    require(isinstance(value, list), f"{field}: list required")
    require(not nonempty or bool(value), f"{field}: cannot be empty")
    result = [text(item, field) for item in value]
    require(len(result) == len(set(result)), f"{field}: duplicate entries")
    return result


def records(value: Any, field: str) -> dict[str, dict[str, Any]]:
    require(isinstance(value, list) and bool(value), f"{field}: nonempty list required")
    result: dict[str, dict[str, Any]] = {}
    for item in value:
        require(isinstance(item, dict), f"{field}: each entry must be an object")
        key = text(item.get("id"), f"{field}.id")
        require(key not in result, f"{field}: duplicate id {key}")
        result[key] = item
    return result


def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        require(key not in result, f"duplicate JSON key: {key}")
        result[key] = value
    return result


def invalid_constant(value: str) -> None:
    raise EvidenceError(f"non-finite JSON number: {value}")


def load_json(path: Path) -> dict[str, Any]:
    with path.open("rb") as handle:
        raw = handle.read(MAX_JSON + 1)
    require(len(raw) <= MAX_JSON, "JSON exceeds size limit")
    result = json.loads(raw.decode("utf-8-sig"), object_pairs_hook=unique_object,
                        parse_constant=invalid_constant)
    require(isinstance(result, dict), "top-level JSON must be an object")
    return result


def artifact_bytes(reference: Any, root: Path, *, limit: int = MAX_ARTIFACT) -> bytes:
    require(isinstance(reference, dict), "artifact reference must be an object")
    rel = Path(text(reference.get("path"), "artifact.path"))
    require(not rel.is_absolute() and ".." not in rel.parts, "artifact path must remain inside artifact root")
    root = root.resolve(strict=True)
    path = (root / rel).resolve(strict=True)
    require(path.is_relative_to(root) and path.is_file(), "artifact path escapes root or is not a file")
    digest = text(reference.get("sha256"), "artifact.sha256")
    require(HEX64.fullmatch(digest) is not None, "artifact SHA-256 must be 64 lowercase hex characters")
    with path.open("rb") as handle:
        payload = handle.read(limit + 1)
    require(len(payload) <= limit, f"artifact exceeds size limit: {rel}")
    require(hashlib.sha256(payload).hexdigest() == digest, f"artifact hash mismatch: {rel}")
    return payload


class _NoDoctypeTreeBuilder(ET.TreeBuilder):
    def doctype(self, name: str, pubid: str | None, system: str | None) -> None:
        # The XML parser handles encoding before this callback. Reject the DTD
        # before internal or external entity declarations can be consumed.
        raise EvidenceError("DTD/entity declarations are not accepted")


def check_junit(payload: bytes, spec: dict[str, Any]) -> dict[str, int]:
    try:
        root = ET.fromstring(payload, parser=ET.XMLParser(target=_NoDoctypeTreeBuilder()))
    except ET.ParseError as exc:
        raise EvidenceError(f"malformed JUnit XML: {exc}") from exc
    require(root.tag in {"testsuite", "testsuites"}, "expected a JUnit testsuite/testsuites root")
    minimum = spec.get("minimum_executed", 1)
    require(type(minimum) is int and minimum >= 1, "minimum_executed must be a positive integer")
    required = set(strings(spec.get("required_cases", []), "required_cases", nonempty=False))
    allowed_skips = set(strings(spec.get("allowed_skipped_cases", []), "allowed_skipped_cases", nonempty=False))
    require(not required.intersection(allowed_skips), "a required case cannot be exempted as skipped")

    # Fail closed on suite-level errors even if a report omits error testcase nodes.
    for suite in root.iter():
        if suite.tag not in {"testsuite", "testsuites"}:
            continue
        for key in ("errors", "failures"):
            if key in suite.attrib:
                value = suite.attrib[key]
                require(value.isdigit(), f"invalid JUnit {key} count")
                require(int(value) == 0, f"JUnit suite reports {key}")
        suite_cases = list(suite.iter("testcase"))
        actual_counts = {
            "tests": len(suite_cases),
            "skipped": sum(case.find("skipped") is not None for case in suite_cases),
        }
        for key, count in actual_counts.items():
            if key in suite.attrib:
                value = suite.attrib[key]
                require(value.isdigit() and int(value) == count, f"inconsistent JUnit {key} count")
    cases = list(root.iter("testcase"))
    require(bool(cases), "JUnit contains zero test cases")
    passed: set[str] = set()
    seen: set[str] = set()
    skipped = 0
    for case in cases:
        name = text(case.get("name"), "testcase.name")
        classname = case.get("classname", "")
        case_id = f"{classname}::{name}"
        require(case_id not in seen, f"duplicate JUnit testcase identity: {case_id}")
        seen.add(case_id)
        require(case.find("failure") is None and case.find("error") is None, f"JUnit test failed: {case_id}")
        if case.find("skipped") is not None:
            skipped += 1
            require(case_id in allowed_skips, f"unapproved skipped test: {case_id}")
        else:
            # Some producers encode not-run status without a <skipped> element.
            status = case.get("status", "run").lower()
            require(status in {"run", "passed", "pass", "success", "completed"}, f"test not confirmed executed: {case_id}")
            passed.add(case_id)
    require(len(passed) >= minimum, "too few executed passing tests")
    require(required.issubset(passed), "required testcase missing or not passing")
    return {"cases": len(cases), "executed": len(passed), "skipped": skipped}


def validate(manifest: dict[str, Any], receipt: dict[str, Any], artifact_root: Path) -> dict[str, Any]:
    """Validate supplied records only; do not authenticate their provenance."""
    problems: list[str] = []
    summaries: dict[str, dict[str, int]] = {}
    try:
        require(isinstance(manifest, dict) and isinstance(receipt, dict), "manifest/receipt must be objects")
        for label, obj in (("manifest", manifest), ("receipt", receipt)):
            require(type(obj.get("schema_version")) is int and obj["schema_version"] == 1, f"{label}: unsupported schema_version")
        for field in ("task_id", "candidate_snapshot", "protected_baseline"):
            text(manifest.get(field), f"manifest.{field}")
        require(receipt.get("task_id") == manifest["task_id"], "task identity mismatch")
        for field in ("snapshot_before", "snapshot_after"):
            require(receipt.get(field) == manifest["candidate_snapshot"], f"stale/changed candidate: {field}")
        for field in ("protected_before", "protected_after"):
            require(receipt.get(field) == manifest["protected_baseline"], f"protected baseline mismatch: {field}")
        # Declared identities are checked for consistency, not authenticated.
        text(receipt.get("run_id"), "receipt.run_id")
        text(receipt.get("runner_id"), "receipt.runner_id")
        authors = set(strings(manifest.get("author_ids"), "author_ids"))
        criteria = set(strings(manifest.get("acceptance_ids"), "acceptance_ids"))
        expected = records(manifest.get("checks"), "manifest.checks")
        actual = records(receipt.get("checks"), "receipt.checks")
        require(set(actual) == set(expected), "check IDs do not match the frozen manifest")
        covered: set[str] = set()
        for check_id, spec in expected.items():
            check = actual[check_id]
            kind = spec.get("kind")
            require(kind in {"command", "junit"}, f"{check_id}: unsupported check kind")
            argv = spec.get("argv")
            require(isinstance(argv, list) and bool(argv) and all(isinstance(v, str) and v for v in argv), f"{check_id}: nonempty argv string array required")
            text(spec.get("cwd"), f"{check_id}.cwd")
            text(spec.get("data_kind"), f"{check_id}.data_kind")
            claims = set(strings(spec.get("acceptance_ids"), f"{check_id}.acceptance_ids"))
            require(claims.issubset(criteria), f"{check_id}: unknown acceptance ID")
            covered.update(claims)
            require(check.get("kind") == kind, f"{check_id}: kind mismatch")
            require(check.get("status") == "passed", f"{check_id}: not passed")
            require(check.get("candidate_snapshot") == manifest["candidate_snapshot"], f"{check_id}: stale candidate")
            for field in ("argv", "cwd", "data_kind"):
                require(check.get(field) == spec[field], f"{check_id}: {field} mismatch")
            require(type(check.get("exit_code")) is int and check["exit_code"] == 0, f"{check_id}: nonzero/missing exit code")
            artifact_bytes(check.get("stdout"), artifact_root)
            artifact_bytes(check.get("stderr"), artifact_root)
            if kind == "junit":
                payload = artifact_bytes(check.get("report"), artifact_root, limit=MAX_XML)
                summaries[check_id] = check_junit(payload, spec)
        require(covered == criteria, "acceptance criteria lack required check coverage")

        review = receipt.get("review")
        require(isinstance(review, dict), "independent review metadata missing")
        reviewer = text(review.get("reviewer_id"), "review.reviewer_id")
        require(reviewer not in authors, "author cannot be the approving reviewer")
        require(review.get("candidate_snapshot") == manifest["candidate_snapshot"], "review is for a different candidate")
        require(review.get("verdict") == "accept", "independent review does not accept")
        require(review.get("blocking_findings") == [], "blocking findings exist or are unspecified")
        assessed = set(strings(review.get("acceptance_ids"), "review.acceptance_ids"))
        require(assessed == criteria, "review does not cover the acceptance criteria")
        levels = {"procedural_only": 1, "runtime_enforced": 2}
        minimum_isolation = manifest.get("minimum_isolation")
        require(minimum_isolation in levels, "manifest minimum_isolation is required")
        isolation = review.get("isolation")
        require(isolation in levels and levels[isolation] >= levels[minimum_isolation], "insufficient declared review isolation")
        artifact_bytes(review.get("report"), artifact_root)
    except (EvidenceError, OSError, ValueError, TypeError, KeyError) as exc:
        problems.append(str(exc))
    return {
        "status": "REJECTED" if problems else "EVIDENCE_COMPLETE",
        "issues": problems,
        "test_summaries": summaries,
        "authenticity": "NOT_AUTHENTICATED_BY_THIS_TOOL",
        "semantic_correctness": "NOT_ESTABLISHED_BY_THIS_TOOL",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--receipt", required=True, type=Path)
    parser.add_argument("--artifacts", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        manifest = load_json(args.manifest)
        receipt = load_json(args.receipt)
        result = validate(manifest, receipt, args.artifacts)
    except (OSError, ValueError, UnicodeError) as exc:
        print(json.dumps({"status": "INPUT_ERROR", "error": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["status"] == "EVIDENCE_COMPLETE" else 1


if __name__ == "__main__":
    sys.exit(main())
