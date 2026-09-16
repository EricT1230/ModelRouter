#!/usr/bin/env python3
"""Offline route planner. It neither dispatches models nor authenticates input records.

Python 3.10+, standard library. PLAN_READY is a plan, never an execution/approval.
"""
from __future__ import annotations
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from common import (boolean, entry_digest, fresh, integer, load_json, nonempty,
                    require, string_list, utcnow)

ROLES = {'inspect', 'implement', 'architect', 'diagnose', 'review', 'research', 'answer'}
CLASSES = {'worker': 1, 'generalist': 2, 'reasoner': 3, 'frontier': 4}
DEPTHS = {'routine', 'normal', 'complex', 'deep', 'exceptional'}
EFFORTS = {'low': 0, 'medium': 1, 'high': 2, 'xhigh': 3, 'max': 4, 'ultra': 5}
COSTS = {'low': 0, 'standard': 1, 'premium': 2, 'unknown': 3}
DEFAULTS_PATH = Path(__file__).resolve().parents[1] / 'policy' / 'defaults.json'


def result(status: str, reason: str, **extra: Any) -> dict[str, Any]:
    return {'status': status, 'reason': reason, 'executed': False,
            'observed_model': None, 'observed_effort': None, **extra}


def choice(obj: dict[str, Any], key: str, allowed: set[str]) -> str:
    value = obj.get(key)
    hint = ('; corrections use phase=implement, obstacle=none, lifecycle.stage_kind=correction'
            if key in {'phase', 'obstacle'} else '')
    require(isinstance(value, str) and value in allowed, f'{key}: expected one of {sorted(allowed)}{hint}')
    return value


def lifecycle_context(task: dict[str, Any], role: str) -> dict[str, Any] | None:
    context = task.get('lifecycle')
    if context is None:
        return None
    fields = {'deliverable_id', 'attempt_id', 'stage_kind', 'correction_round',
              'max_correction_rounds', 'escalate_after_round', 'baseline_capability_class', 'source_ref'}
    require(isinstance(context, dict) and set(context) == fields,
            f'lifecycle requires exactly these fields: {sorted(fields)}')
    for key in ('deliverable_id', 'attempt_id', 'source_ref'):
        nonempty(context[key], f'lifecycle.{key}')
    stage = choice(context, 'stage_kind', {'initial', 'correction', 'review'})
    require((stage == 'review') == (role == 'review'), 'lifecycle stage must match phase')
    require(stage != 'correction' or role == 'implement', 'correction requires phase=implement')
    round_number = integer(context['correction_round'], 'lifecycle.correction_round')
    maximum = integer(context['max_correction_rounds'], 'lifecycle.max_correction_rounds')
    threshold = integer(context['escalate_after_round'], 'lifecycle.escalate_after_round')
    require(threshold <= maximum, 'escalation threshold exceeds correction allowance')
    require(stage != 'initial' or round_number == 0, 'initial stage requires round zero')
    require(stage != 'correction' or round_number >= 1, 'correction stage requires round >= 1')
    choice(context, 'baseline_capability_class', set(CLASSES))
    return dict(context)


def select_route(task: dict[str, Any], catalog: dict[str, Any],
                 profiles: dict[str, Any], *, host: dict[str, Any] | None = None,
                 ledger: dict[str, Any] | None = None,
                 policy: dict[str, Any] | None = None,
                 now: datetime | None = None) -> dict[str, Any]:
    require(all(isinstance(v, dict) for v in (task, catalog, profiles)), 'object inputs required')
    cfg = load_json(DEFAULTS_PATH)
    if policy is not None:
        require(isinstance(policy, dict) and not (set(policy) - set(cfg)), 'unknown policy field')
        cfg.update(policy)
    for field in ('catalog_ttl_hours', 'profile_ttl_days'):
        integer(cfg[field], field, 1)
    for field in ('exceptional_stages', 'max_concurrent_children', 'max_delegation_depth'):
        integer(cfg[field], field)
    boolean(cfg['allow_provisional_canary'], 'allow_provisional_canary')
    now = now or utcnow()
    require(now.tzinfo is not None, 'now requires timezone')
    nonempty(task.get('task_id'), 'task_id')
    nonempty(task.get('goal'), 'goal')
    role = choice(task, 'phase', ROLES)
    risk = choice(task, 'risk', {'low', 'medium', 'high', 'unknown'})
    depth = choice(task, 'depth', DEPTHS)
    obstacle = choice(task, 'obstacle', {'none', 'requirements', 'environment', 'integrity'})
    bounded = boolean(task.get('bounded'), 'bounded')
    clear = boolean(task.get('contract_clear'), 'contract_clear')
    evidence = string_list(task.get('evidence_refs'), 'evidence_refs')
    modalities = string_list(task.get('required_modalities', ['text']), 'required_modalities', False)
    gap = task.get('reasoning_gap', '')
    require(isinstance(gap, str), 'reasoning_gap must be string')
    tracks = integer(task.get('independent_tracks', 0), 'independent_tracks')
    preference = task.get('effort_preference')
    require(preference is None or preference in EFFORTS, 'unknown semantic effort preference')
    if obstacle == 'integrity':
        return result('INTEGRITY_FAILURE', 'Preserve evidence and restore a trusted acceptance boundary.')
    if obstacle == 'environment':
        return result('BLOCKED_ENVIRONMENT', 'Remedy the named missing input/environment within authorization.')
    if obstacle == 'requirements':
        return result('NEEDS_CLARIFICATION', 'Resolve the material intent ambiguity before implementation.')
    if risk == 'unknown' or not evidence:
        return result('NEEDS_INSPECTION', 'Inspect routing-critical evidence; unknown risk remains unknown.')
    if role == 'implement' and (not bounded or not clear or depth in {'deep', 'exceptional'}):
        return result('NEEDS_CONTRACT', 'Resolve design/root-cause uncertainty; then assign a bounded implementation.')

    lifecycle = lifecycle_context(task, role)
    escalated = False
    if lifecycle is not None:
        if lifecycle['correction_round'] > lifecycle['max_correction_rounds']:
            return result('BUDGET_BLOCKED', 'Supplied lifecycle correction allowance exhausted.',
                          lifecycle=lifecycle)
        escalated = (lifecycle['stage_kind'] == 'correction' and
                     lifecycle['correction_round'] > lifecycle['escalate_after_round'])
        if escalated and lifecycle['baseline_capability_class'] == 'frontier':
            return result('NO_SUPPORTED_ROUTE', 'No strictly higher capability class is represented.',
                          lifecycle=lifecycle)
        if host is not None and 'fresh_context_available' in host:
            available = boolean(host['fresh_context_available'], 'host.fresh_context_available')
            if (escalated or role == 'review') and not available:
                return result('DISPATCH_LIMITED', 'Lifecycle requires fresh context unavailable on this host.',
                              lifecycle=lifecycle)

    minimum, target = 2, 'medium'
    if role == 'inspect' or (role == 'answer' and depth == 'routine' and risk == 'low'):
        minimum, target = (1, 'low') if depth == 'routine' and risk == 'low' else (2, 'medium')
    elif role == 'implement':
        minimum = 1 if depth == 'routine' and risk == 'low' else 2
        target = 'high' if risk == 'high' or depth == 'complex' else 'medium'
    elif role in {'architect', 'diagnose'}:
        minimum, target = 3, 'high'
    elif role == 'review':
        minimum, target = 3, 'high' if risk == 'high' or depth in {'complex', 'deep', 'exceptional'} else 'medium'
    elif depth == 'complex' or risk == 'high':
        minimum, target = 3, 'high'
    if role not in {'inspect', 'implement'} and depth in {'deep', 'exceptional'}:
        if not gap.strip():
            return result('NEEDS_REASONING_GAP', 'Name the concrete difficult reasoning problem.')
        minimum, target = (3, 'xhigh') if depth == 'deep' else (4, 'ultra' if tracks >= 2 else 'max')
    if preference is not None:
        if EFFORTS[preference] < EFFORTS[target]:
            return result('QUALITY_CONSTRAINT', 'Requested effort is below this phase policy; re-plan explicitly.')
        target = preference
    if target == 'xhigh' and not gap.strip():
        return result('NEEDS_REASONING_GAP', 'Xhigh requires a concrete deep reasoning gap, including explicit preferences.')
    if escalated:
        minimum = max(minimum, CLASSES[lifecycle['baseline_capability_class']] + 1)
    if target in {'max', 'ultra'}:
        if not gap.strip():
            return result('NEEDS_REASONING_GAP', 'Max/Ultra need a named exceptional reasoning problem.')
        minimum = max(minimum, 4)
        if ledger is None:
            return result('BUDGET_STATE_REQUIRED', 'Use the shared deliverable ledger before an exceptional stage.')
        require(isinstance(ledger, dict), 'ledger must be an object')
        require(ledger.get('task_id') == task['task_id'], 'ledger task identity mismatch')
        used = integer(ledger.get('exceptional_stages_used'), 'exceptional_stages_used')
        if used >= cfg['exceptional_stages']:
            return result('BUDGET_BLOCKED', 'Exceptional-stage budget exhausted; keep required validation intact.')
    if target == 'ultra':
        if not isinstance(host, dict) or not isinstance(host.get('source_ref'), str) or not host['source_ref'].strip():
            return result('ULTRA_CONTROL_UNCONFIRMED', 'Obtain actual host-specific Ultra semantics and controls.')
        semantics = host.get('ultra_semantics')
        if semantics == 'may_spawn':
            thread_cap, depth_cap = host.get('enforced_child_limit'), host.get('enforced_depth_limit')
            if (host.get('controls_observed') is not True or type(thread_cap) is not int or
                    type(depth_cap) is not int or thread_cap < 0 or depth_cap < 0 or
                    thread_cap > cfg['max_concurrent_children'] or depth_cap > cfg['max_delegation_depth']):
                return result('ULTRA_CONTROL_UNCONFIRMED', 'Automatic descendants are not demonstrably bounded by this policy.')
        elif semantics != 'reasoning_only':
            return result('ULTRA_CONTROL_UNCONFIRMED', 'Do not infer native Ultra behavior from its label.')

    require(type(catalog.get('schema_version')) is int and catalog['schema_version'] == 1, 'unsupported catalog schema')
    source = catalog.get('source')
    require(isinstance(source, dict), 'catalog.source object required')
    if catalog.get('illustrative_only') is True or source.get('session_bound') is not True or source.get('complete') is not True:
        return result('CAPABILITY_REFRESH_REQUIRED', 'Need a complete catalog bound to the actual target session.')
    nonempty(source.get('host_scope'), 'source.host_scope')
    nonempty(source.get('source_ref'), 'source.source_ref')
    if not fresh(source.get('observed_at'), now, cfg['catalog_ttl_hours'] * 3600):
        return result('CAPABILITY_REFRESH_REQUIRED', 'Catalog is stale or future-dated.')
    if host is not None:
        require(isinstance(host, dict), 'host must be an object')
        if host.get('host_scope') != source['host_scope']:
            return result('CAPABILITY_REFRESH_REQUIRED', 'Catalog and actual host scope differ.')
    models = catalog.get('models')
    require(isinstance(models, list), 'catalog.models list required')
    by_id: dict[str, dict[str, Any]] = {}
    for model in models:
        require(isinstance(model, dict), 'model object required')
        model_id = nonempty(model.get('id'), 'model.id')
        require(model_id not in by_id, 'duplicate model ID')
        require(model.get('catalog_entry_sha256') == entry_digest(model), 'catalog-entry fingerprint mismatch')
        boolean(model.get('hidden'), 'model.hidden')
        string_list(model.get('input_modalities'), 'input_modalities')
        require(isinstance(model.get('efforts'), list), 'model.efforts list required')
        values = [nonempty(e.get('value'), 'effort.value') for e in model['efforts'] if isinstance(e, dict)]
        require(len(values) == len(model['efforts']) and len(values) == len(set(values)), 'invalid/duplicate effort records')
        by_id[model_id] = model
    require(type(profiles.get('schema_version')) is int and profiles['schema_version'] == 1, 'unsupported profiles schema')
    entries = profiles.get('profiles')
    require(isinstance(entries, list), 'profiles list required')
    seen: set[str] = set()
    eligible: list[tuple[tuple[Any, ...], dict[str, Any], str]] = []
    outdated = 0
    for profile in entries:
        require(isinstance(profile, dict), 'profile object required')
        model_id = nonempty(profile.get('id'), 'profile.id')
        require(model_id not in seen, 'duplicate profile ID')
        seen.add(model_id)
        basis = choice(profile, 'basis', {'provisional', 'documented', 'evaluated'})
        klass = choice(profile, 'capability_class', set(CLASSES))
        cost = choice(profile, 'cost_band', set(COSTS))
        roles = string_list(profile.get('roles'), 'profile.roles', False)
        require(set(roles).issubset(ROLES), 'unknown profile role')
        string_list(profile.get('source_refs'), 'profile.source_refs', False)
        bindings = profile.get('effort_bindings')
        require(isinstance(bindings, dict) and not (set(bindings) - set(EFFORTS)), 'invalid semantic effort bindings')
        for val in bindings.values():
            nonempty(val, 'native effort binding')
        model = by_id.get(model_id)
        if model is None or model['hidden']:
            continue
        if (profile.get('catalog_entry_sha256') != model['catalog_entry_sha256'] or
                not fresh(profile.get('checked_at'), now, cfg['profile_ttl_days'] * 86400)):
            outdated += 1
            continue
        if role not in roles or CLASSES[klass] < minimum:
            continue
        if not set(modalities).issubset(model['input_modalities']):
            continue
        if basis == 'provisional':
            canary = task.get('canary_authorized') is True and cfg['allow_provisional_canary'] is True
            if not (canary and risk == 'low' and depth in {'routine', 'normal'} and role in {'inspect', 'implement', 'answer'}):
                continue
        native = bindings.get(target)
        if native is None or native not in {e['value'] for e in model['efforts']}:
            continue
        # Match quality evidence first, then source-backed price heuristics.
        # No empirical savings or universal model ranking is inferred here.
        basis_rank = {'evaluated': 0, 'documented': 1, 'provisional': 2}[basis]
        incumbent_roles = string_list(profile.get('incumbent_roles', []), 'incumbent_roles')
        require(set(incumbent_roles).issubset(ROLES), 'unknown incumbent role')
        incumbent_rank = 0 if role in incumbent_roles else 1
        if risk == 'high' or role in {'architect', 'diagnose', 'review'}:
            key = (basis_rank, COSTS[cost], CLASSES[klass], incumbent_rank, model_id)
        else:
            # Do not let an evaluated expensive frontier displace a suitable
            # documented worker on every ordinary task just because it has history.
            key = (COSTS[cost], CLASSES[klass], basis_rank, incumbent_rank, model_id)
        eligible.append((key, profile, native))
    if not eligible:
        # Missing role evidence is recoverable when the catalog still advertises
        # a visible, modality-compatible pair. It never authorizes that model.
        unprofiled = sorted(model_id for model_id, model in by_id.items()
                            if model_id not in seen and not model['hidden']
                            and set(modalities).issubset(model['input_modalities'])
                            and model['efforts'])
        has_current_profile = any(model_id in by_id and not by_id[model_id]['hidden'] for model_id in seen)
        replaced_catalog = bool(unprofiled) and not has_current_profile
        state = 'PROFILE_UPDATE_REQUIRED' if outdated or not entries or replaced_catalog else 'NO_SUPPORTED_ROUTE'
        return result(state, 'No current evidenced pair satisfies role, effort, modality and safety requirements.',
                      required_class=next(k for k, v in CLASSES.items() if v == minimum), semantic_effort=target,
                      unprofiled_model_ids=unprofiled)
    eligible.sort(key=lambda v: v[0])
    _, selected, native = eligible[0]
    tied = len(eligible) > 1 and eligible[0][0][:-1] == eligible[1][0][:-1]
    order = (['evidence_basis', 'cost_band', 'capability_class', 'incumbent', 'model_id']
             if risk == 'high' or role in {'architect', 'diagnose', 'review'}
             else ['cost_band', 'capability_class', 'evidence_basis', 'incumbent', 'model_id'])
    needs_review = role in {'implement', 'architect'} or (risk == 'high' and role != 'review')
    return result('PLAN_READY', 'Evidence-backed proposed pair; host dispatch and observation still required.',
                  task_id=task['task_id'], phase=role, proposed_model=selected['id'],
                  semantic_effort=target, proposed_native_effort=native,
                  basis=selected['basis'],
                  cost_basis=('unknown' if selected['cost_band'] == 'unknown'
                              else 'documented_band_heuristic_not_measured_savings'),
                  selected_cost_band=selected['cost_band'],
                  cost_evidence_status='unknown' if selected['cost_band'] == 'unknown' else 'declared_band_unmeasured',
                  selection_reason='Ranked eligible profiles using declared metadata, not measured savings.',
                  ranking_order=order, tie_break='model_id_tie_break' if tied else 'not_needed',
                  independent_review_required=needs_review,
                  review_minimum_class='reasoner' if needs_review else None,
                  fresh_context_required=role == 'review' or escalated,
                  lifecycle=lifecycle, lifecycle_check='supplied_limits_only' if lifecycle else 'not_supplied',
                  exceptional_stage_to_charge_on_execution=target in {'max', 'ultra'},
                  may_reuse_parent_if_effective_pair_suitable=role != 'review' and not escalated,
                  alternatives=[{'model': p['id'], 'native_effort': n} for _, p, n in eligible[1:3]])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('task', 'catalog', 'profiles'):
        parser.add_argument('--' + name, type=Path, required=True)
    for name in ('host', 'ledger', 'policy'):
        parser.add_argument('--' + name, type=Path)
    args = parser.parse_args()
    try:
        kwargs = {name: load_json(getattr(args, name)) for name in ('host', 'ledger', 'policy') if getattr(args, name)}
        out = select_route(load_json(args.task), load_json(args.catalog), load_json(args.profiles), **kwargs)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        out = result('INPUT_ERROR', str(exc))
    print(json.dumps(out, ensure_ascii=False, indent=2, allow_nan=False))
    return 0 if out['status'] == 'PLAN_READY' else 2

if __name__ == '__main__':
    sys.exit(main())
