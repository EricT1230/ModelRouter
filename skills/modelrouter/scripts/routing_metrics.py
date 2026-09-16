#!/usr/bin/env python3
"""Record and compare bounded local routing outcomes without calling models."""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import stat
import sys
import time
from typing import Any

from common import atomic_json, load_json, nonempty, regular_path, require, timestamp


SCHEMA_VERSION = 1
STATE_FILE = "state.json"
EVENTS_DIR = "events"
FINAL_STATES = {"accepted", "failed", "blocked", "incomplete"}
RISKS = {"low", "medium", "high", "critical"}
VERIFICATION_LEVELS = {"self-check", "procedural-separation", "enforced-isolation"}
DISPATCH_STATES = {"not-requested", "completed", "failed", "cancelled", "unknown"}
MAX_COUNTER = 10**18
MAX_MEASUREMENT = 10**18


def text(value: Any, field: str, *, maximum: int = 256, nullable: bool = False) -> str | None:
    if value is None and nullable:
        return None
    result = nonempty(value, field).strip()
    require(len(result) <= maximum, f"{field}: maximum length is {maximum}")
    require("\x00" not in result and "\r" not in result and "\n" not in result,
            f"{field}: control/newline characters are not accepted")
    return result


def integer(value: Any, field: str, *, minimum: int = 0, maximum: int = MAX_COUNTER,
            nullable: bool = False) -> int | None:
    if value is None and nullable:
        return None
    require(type(value) is int and value >= minimum, f"{field}: integer >= {minimum} required")
    require(value <= maximum, f"{field}: integer <= {maximum} required")
    return value


def number(value: Any, field: str, *, maximum: float | int = MAX_MEASUREMENT,
           nullable: bool = False) -> float | int | None:
    if value is None and nullable:
        return None
    require(type(value) in (int, float) and value >= 0,
            f"{field}: finite nonnegative number required")
    if type(value) is float:
        require(math.isfinite(value), f"{field}: finite nonnegative number required")
    require(value <= maximum, f"{field}: number <= {maximum} required")
    return value


def object_only(value: Any, field: str, allowed: set[str], required: set[str]) -> dict[str, Any]:
    require(isinstance(value, dict), f"{field}: object required")
    unknown = set(value) - allowed
    missing = required - set(value)
    require(not unknown, f"{field}: unknown fields: {sorted(unknown)}")
    require(not missing, f"{field}: missing fields: {sorted(missing)}")
    return value


def regular_file(path: Path) -> Path:
    path = regular_path(path)
    info = path.lstat()
    require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1,
            f"regular unlinked file required: {path}")
    return path


def stable_load_json(path: Path, *, attempts: int = 50, delay: float = 0.01) -> dict[str, Any]:
    """Read after atomic hard-link publication settles; never accept persistent links."""
    last: Exception | None = None
    for attempt in range(attempts):
        try:
            return load_json(regular_file(path))
        except (FileNotFoundError, ValueError) as error:
            last = error
            checked = regular_path(path)
            if checked.exists():
                info = checked.lstat()
                if not stat.S_ISREG(info.st_mode) or info.st_nlink <= 1:
                    raise
            if attempt + 1 < attempts:
                time.sleep(delay)
    raise ValueError(f"file did not settle as a regular unlinked JSON file: {path}") from last


def state_root(path: Path, *, must_exist: bool) -> Path:
    path = regular_path(path)
    require(path.parent != path, "state root cannot be a filesystem root")
    if path.exists():
        require(path.is_dir(), "state root must be a directory")
    elif must_exist:
        raise ValueError("state root is not initialized")
    return path


def validate_state(data: dict[str, Any]) -> dict[str, Any]:
    object_only(data, "state", {"schema_version", "host_scope", "created_at", "data_policy"},
                {"schema_version", "host_scope", "created_at", "data_policy"})
    require(data["schema_version"] == SCHEMA_VERSION, "unsupported state schema_version")
    text(data["host_scope"], "state.host_scope")
    timestamp(data["created_at"])
    require(data["data_policy"] == "no-prompts-no-secrets-bounded-outcomes",
            "unexpected state data_policy")
    return data


def load_state(root: Path) -> tuple[Path, dict[str, Any]]:
    root = state_root(root, must_exist=True)
    marker = root / STATE_FILE
    return root, validate_state(stable_load_json(marker))


def route_record(value: Any, field: str, *, child: bool = False) -> dict[str, Any]:
    allowed = {"requested_model", "requested_effort", "observed_model", "observed_effort"}
    required = set(allowed)
    if child:
        allowed |= {"role", "dispatch_status"}
        required |= {"role", "dispatch_status"}
    value = object_only(value, field, allowed, required)
    out = {key: text(value[key], f"{field}.{key}", nullable=True) for key in
           ("requested_model", "requested_effort", "observed_model", "observed_effort")}
    if child:
        out["role"] = text(value["role"], f"{field}.role")
        out["dispatch_status"] = text(value["dispatch_status"], f"{field}.dispatch_status")
        require(out["dispatch_status"] in DISPATCH_STATES, f"{field}.dispatch_status: unsupported value")
    return out


def validate_event(data: dict[str, Any], host_scope: str) -> dict[str, Any]:
    fields = {"schema_version", "event_id", "recorded_at", "host_scope", "evidence_scope",
              "task_id", "task_bucket", "route_label", "risk", "outcome", "quality",
              "route", "work", "usage"}
    data = object_only(data, "event", fields, fields)
    require(data["schema_version"] == SCHEMA_VERSION, "unsupported event schema_version")
    result: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "event_id": text(data["event_id"], "event.event_id"),
        "recorded_at": text(data["recorded_at"], "event.recorded_at"),
        "host_scope": text(data["host_scope"], "event.host_scope"),
        "evidence_scope": text(data["evidence_scope"], "event.evidence_scope"),
        "task_id": text(data["task_id"], "event.task_id"),
        "task_bucket": text(data["task_bucket"], "event.task_bucket"),
        "route_label": text(data["route_label"], "event.route_label"),
        "risk": text(data["risk"], "event.risk"),
        "outcome": text(data["outcome"], "event.outcome"),
    }
    timestamp(result["recorded_at"])
    require(result["host_scope"] == host_scope, "event host_scope does not match initialized state")
    require(result["risk"] in RISKS, "event.risk: unsupported value")
    require(result["outcome"] in FINAL_STATES, "event.outcome: unsupported value")

    quality = object_only(data["quality"], "event.quality",
                          {"verification_level", "evidence_ref"},
                          {"verification_level", "evidence_ref"})
    verification = text(quality["verification_level"], "event.quality.verification_level")
    require(verification in VERIFICATION_LEVELS, "unsupported verification_level")
    evidence_ref = text(quality["evidence_ref"], "event.quality.evidence_ref", maximum=512,
                        nullable=True)
    if result["outcome"] == "accepted":
        require(evidence_ref is not None, "accepted outcomes require an evidence_ref")
    result["quality"] = {"verification_level": verification, "evidence_ref": evidence_ref}

    route = object_only(data["route"], "event.route", {"parent", "children"},
                        {"parent", "children"})
    require(isinstance(route["children"], list) and len(route["children"]) <= 16,
            "event.route.children: list with at most 16 entries required")
    result["route"] = {
        "parent": route_record(route["parent"], "event.route.parent"),
        "children": [route_record(item, f"event.route.children[{index}]", child=True)
                     for index, item in enumerate(route["children"])],
    }

    work = object_only(data["work"], "event.work", {"attempts", "repair_passes"},
                       {"attempts", "repair_passes"})
    result["work"] = {
        "attempts": integer(work["attempts"], "event.work.attempts", minimum=1,
                            maximum=1_000_000),
        "repair_passes": integer(work["repair_passes"], "event.work.repair_passes",
                                 maximum=1_000_000),
    }

    usage_fields = {"total_tokens", "input_tokens", "cached_input_tokens", "output_tokens",
                    "reasoning_tokens", "billed_credits", "currency_cost", "currency",
                    "pricing_version", "service_tier", "elapsed_seconds", "source_ref"}
    usage = object_only(data["usage"], "event.usage", usage_fields, usage_fields)
    normalized_usage = {
        "total_tokens": integer(usage["total_tokens"], "event.usage.total_tokens", nullable=True),
        "input_tokens": integer(usage["input_tokens"], "event.usage.input_tokens", nullable=True),
        "cached_input_tokens": integer(usage["cached_input_tokens"],
                                       "event.usage.cached_input_tokens", nullable=True),
        "output_tokens": integer(usage["output_tokens"], "event.usage.output_tokens", nullable=True),
        "reasoning_tokens": integer(usage["reasoning_tokens"],
                                    "event.usage.reasoning_tokens", nullable=True),
        "billed_credits": number(usage["billed_credits"], "event.usage.billed_credits", nullable=True),
        "currency_cost": number(usage["currency_cost"], "event.usage.currency_cost", nullable=True),
        "currency": text(usage["currency"], "event.usage.currency", maximum=12, nullable=True),
        "pricing_version": text(usage["pricing_version"], "event.usage.pricing_version", nullable=True),
        "service_tier": text(usage["service_tier"], "event.usage.service_tier", nullable=True),
        "elapsed_seconds": number(usage["elapsed_seconds"], "event.usage.elapsed_seconds", nullable=True),
        "source_ref": text(usage["source_ref"], "event.usage.source_ref", maximum=512, nullable=True),
    }
    if normalized_usage["cached_input_tokens"] is not None and normalized_usage["input_tokens"] is not None:
        require(normalized_usage["cached_input_tokens"] <= normalized_usage["input_tokens"],
                "cached_input_tokens cannot exceed input_tokens")
    if normalized_usage["currency_cost"] is not None:
        require(normalized_usage["currency"] is not None, "currency_cost requires currency")
    observed = any(normalized_usage[key] is not None for key in
                   ("total_tokens", "input_tokens", "cached_input_tokens", "output_tokens",
                    "reasoning_tokens", "billed_credits", "currency_cost", "elapsed_seconds"))
    if observed:
        require(normalized_usage["source_ref"] is not None,
                "observed aggregate usage requires source_ref")
    result["usage"] = normalized_usage
    return result


def event_path(root: Path, event_id: str) -> Path:
    digest = hashlib.sha256(event_id.encode("utf-8")).hexdigest()
    return root / EVENTS_DIR / (digest + ".json")


def init_command(args: argparse.Namespace) -> dict[str, Any]:
    root = state_root(args.state_root, must_exist=False)
    host_scope = text(args.host_scope, "host_scope")
    if root.exists():
        marker = root / STATE_FILE
        if marker.exists():
            existing = validate_state(load_json(regular_file(marker)))
            require(existing["host_scope"] == host_scope, "existing state has a different host_scope")
            return {"status": "ALREADY_INITIALIZED", "state_root": str(root),
                    "host_scope": host_scope}
        require(not any(root.iterdir()), "refusing unrelated non-empty directory without state marker")
    else:
        root.mkdir(parents=True, exist_ok=False)
    root = state_root(root, must_exist=True)
    marker_data = {
        "schema_version": SCHEMA_VERSION,
        "host_scope": host_scope,
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "data_policy": "no-prompts-no-secrets-bounded-outcomes",
    }
    atomic_json(root / STATE_FILE, marker_data, root=root)
    return {"status": "INITIALIZED", "state_root": str(root), "host_scope": host_scope}


def record_command(args: argparse.Namespace) -> dict[str, Any]:
    root, state = load_state(args.state_root)
    source = load_json(regular_file(args.input))
    event = validate_event(source, state["host_scope"])
    destination = event_path(root, event["event_id"])
    try:
        atomic_json(destination, event, root=root)
    except (FileExistsError, ValueError):
        if not destination.exists():
            raise
        existing = stable_load_json(destination)
        if existing == event:
            return {"status": "ALREADY_RECORDED", "event_id": event["event_id"],
                    "event_file": str(destination)}
        raise ValueError("event_id already exists with different content")
    return {"status": "RECORDED", "event_id": event["event_id"],
            "event_file": str(destination)}


def load_events(root: Path, state: dict[str, Any]) -> list[dict[str, Any]]:
    folder = regular_path(root / EVENTS_DIR)
    if not folder.exists():
        return []
    require(folder.is_dir(), "events path must be a directory")
    events = []
    seen: set[str] = set()
    for path in sorted(folder.iterdir()):
        require(path.suffix == ".json", f"unexpected file in events directory: {path.name}")
        event = validate_event(stable_load_json(path), state["host_scope"])
        require(event["event_id"] not in seen, "duplicate event_id in state")
        require(path == event_path(root, event["event_id"]), "event filename does not match event_id")
        seen.add(event["event_id"])
        events.append(event)
    return events


def summarize(events: list[dict[str, Any]]) -> dict[str, Any]:
    groups: dict[tuple[str, str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        key = (event["evidence_scope"], event["task_bucket"], event["risk"],
               event["quality"]["verification_level"], event["route_label"])
        groups[key].append(event)
    rows = []
    for key, values in sorted(groups.items()):
        accepted = sum(item["outcome"] == "accepted" for item in values)
        token_values = [item["usage"]["total_tokens"] for item in values]
        credit_values = [item["usage"]["billed_credits"] for item in values]
        cost_values = [item["usage"]["currency_cost"] for item in values]
        currencies = sorted({item["usage"]["currency"] for item in values
                             if item["usage"]["currency"] is not None})
        total_tokens = sum(token_values) if all(value is not None for value in token_values) else None
        total_credits = sum(credit_values) if all(value is not None for value in credit_values) else None
        total_cost = (sum(cost_values) if all(value is not None for value in cost_values)
                      and len(currencies) <= 1 else None)
        tokens_per_accepted = None
        credits_per_accepted = None
        cost_per_accepted = None
        if accepted:
            try:
                tokens_per_accepted = total_tokens / accepted if total_tokens is not None else None
                credits_per_accepted = total_credits / accepted if total_credits is not None else None
                cost_per_accepted = total_cost / accepted if total_cost is not None else None
            except OverflowError:
                # Persisted values are bounded, but remain defensive against an impractical aggregate.
                pass
        rows.append({
            "evidence_scope": key[0], "task_bucket": key[1], "risk": key[2],
            "verification_level": key[3], "route_label": key[4],
            "tasks": len(values), "accepted_tasks": accepted,
            "failed_tasks": sum(item["outcome"] == "failed" for item in values),
            "blocked_tasks": sum(item["outcome"] == "blocked" for item in values),
            "incomplete_tasks": sum(item["outcome"] == "incomplete" for item in values),
            "attempts": sum(item["work"]["attempts"] for item in values),
            "repair_passes": sum(item["work"]["repair_passes"] for item in values),
            "token_coverage": sum(value is not None for value in token_values) / len(values),
            "total_tokens": total_tokens,
            "tokens_per_accepted_task": tokens_per_accepted,
            "credit_coverage": sum(value is not None for value in credit_values) / len(values),
            "total_billed_credits": total_credits,
            "credits_per_accepted_task": credits_per_accepted,
            "currency_cost_coverage": sum(value is not None for value in cost_values) / len(values),
            "currency": currencies[0] if len(currencies) == 1 else None,
            "total_currency_cost": total_cost,
            "currency_cost_per_accepted_task": cost_per_accepted,
        })
    return {"schema_version": SCHEMA_VERSION, "events": len(events), "groups": rows,
            "metering_note": "Totals are failure-inclusive. Null means incomplete or incomparable telemetry; components are not added to derive total_tokens."}


def filtered(events: list[dict[str, Any]], args: argparse.Namespace) -> list[dict[str, Any]]:
    return [event for event in events
            if event["evidence_scope"] == args.evidence_scope
            and event["task_bucket"] == args.task_bucket
            and event["risk"] == args.risk
            and event["quality"]["verification_level"] == args.verification_level]


def compare_command(args: argparse.Namespace) -> dict[str, Any]:
    root, state = load_state(args.state_root)
    for field in ("evidence_scope", "task_bucket", "risk", "verification_level",
                  "baseline_route", "candidate_route"):
        setattr(args, field, text(getattr(args, field), field))
    require(args.baseline_route != args.candidate_route,
            "baseline_route and candidate_route must differ")
    events = filtered(load_events(root, state), args)
    summary = summarize(events)
    by_route = {row["route_label"]: row for row in summary["groups"]}
    baseline = by_route.get(args.baseline_route)
    candidate = by_route.get(args.candidate_route)
    reasons = []
    for label, row in (("baseline", baseline), ("candidate", candidate)):
        if row is None:
            reasons.append(f"{label} route has no matching events")
        elif row["accepted_tasks"] < args.min_accepted:
            reasons.append(f"{label} route needs at least {args.min_accepted} accepted tasks")
        elif row["token_coverage"] != 1:
            reasons.append(f"{label} route has incomplete total_tokens telemetry")
        elif row["tokens_per_accepted_task"] is None:
            reasons.append(f"{label} route token aggregate is not safely representable")
    result: dict[str, Any] = {
        "status": "INSUFFICIENT_EVIDENCE" if reasons else "COMPARISON_READY",
        "filters": {"host_scope": state["host_scope"], "evidence_scope": args.evidence_scope,
                    "task_bucket": args.task_bucket, "risk": args.risk,
                    "verification_level": args.verification_level},
        "minimum_accepted_tasks": args.min_accepted,
        "baseline": baseline,
        "candidate": candidate,
        "reasons": reasons,
        "claim_boundary": "This compares measured failure-inclusive tokens for matched recorded tasks; it does not prove universal savings or causality.",
    }
    if not reasons:
        base = baseline["tokens_per_accepted_task"]
        cand = candidate["tokens_per_accepted_task"]
        delta = cand - base
        result["token_comparison"] = {
            "metric": "failure_inclusive_total_tokens_per_accepted_task",
            "baseline": base,
            "candidate": cand,
            "candidate_minus_baseline": delta,
            "percent_change": (delta / base * 100) if base else None,
            "direction": "fewer" if delta < 0 else "more" if delta > 0 else "equal",
        }
    return result


def emit(result: dict[str, Any], args: argparse.Namespace) -> None:
    if getattr(args, "output", None):
        output_root = regular_path(args.output_root)
        require(output_root.is_dir(), "output_root must be an existing trusted directory")
        atomic_json(args.output, result, root=output_root, replace=args.replace)
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    sub = root.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init", help="initialize an explicit host-scoped state directory")
    init.add_argument("--state-root", required=True, type=Path)
    init.add_argument("--host-scope", required=True)
    record = sub.add_parser("record", help="record one bounded outcome event")
    record.add_argument("--state-root", required=True, type=Path)
    record.add_argument("--input", required=True, type=Path)
    for name in ("summary", "compare"):
        command = sub.add_parser(name, help=f"{name} recorded outcomes without writing state")
        command.add_argument("--state-root", required=True, type=Path)
        command.add_argument("--output", type=Path)
        command.add_argument("--output-root", type=Path)
        command.add_argument("--replace", action="store_true")
        if name == "compare":
            command.add_argument("--evidence-scope", required=True)
            command.add_argument("--task-bucket", required=True)
            command.add_argument("--risk", required=True, choices=sorted(RISKS))
            command.add_argument("--verification-level", required=True,
                                 choices=sorted(VERIFICATION_LEVELS))
            command.add_argument("--baseline-route", required=True)
            command.add_argument("--candidate-route", required=True)
            command.add_argument("--min-accepted", type=int, default=3)
    return root


def main() -> int:
    args = parser().parse_args()
    try:
        if getattr(args, "output", None):
            require(args.output_root is not None, "--output requires --output-root")
            output = regular_path(args.output)
            state = regular_path(args.state_root)
            require(not output.is_relative_to(state), "report output must be outside state root")
        else:
            require(getattr(args, "output_root", None) is None and not getattr(args, "replace", False),
                    "--output-root/--replace require --output")
        if args.command == "init":
            result = init_command(args)
        elif args.command == "record":
            result = record_command(args)
        elif args.command == "summary":
            root, state = load_state(args.state_root)
            result = summarize(load_events(root, state))
            result["host_scope"] = state["host_scope"]
        else:
            require(args.min_accepted >= 1, "--min-accepted must be >= 1")
            result = compare_command(args)
        emit(result, args)
        return 0 if result.get("status") != "INSUFFICIENT_EVIDENCE" else 1
    except (OSError, ValueError, OverflowError, json.JSONDecodeError) as error:
        print(json.dumps({"status": "INPUT_ERROR", "message": str(error)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    sys.exit(main())
