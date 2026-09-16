"""Synthetic policy tests. No model inference, account data, or live host claims."""
from __future__ import annotations
import copy
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills' / 'modelrouter' / 'scripts'))
from common import entry_digest, normalize_model
from route import select_route

NOW = datetime(2030, 1, 2, tzinfo=timezone.utc)


def fixtures():
    models, profiles = [], []
    for name, klass, cost in [('fixture-worker', 'worker', 'low'),
                              ('fixture-general', 'generalist', 'standard'),
                              ('fixture-reasoner', 'reasoner', 'premium'),
                              ('fixture-frontier', 'frontier', 'premium')]:
        levels = ['low', 'medium', 'high', 'xhigh', 'max', 'ultra']
        model = normalize_model({'model': name, 'displayName': name, 'hidden': False,
            'inputModalities': ['text', 'image'], 'defaultReasoningEffort': 'medium',
            'supportedReasoningEfforts': [{'reasoningEffort': e, 'description': 'SYNTHETIC fixture'} for e in levels]})
        models.append(model)
        profiles.append({'id': name, 'catalog_entry_sha256': model['catalog_entry_sha256'],
            'checked_at': NOW.isoformat(), 'basis': 'documented', 'capability_class': klass,
            'roles': ['inspect', 'implement', 'architect', 'diagnose', 'review', 'research', 'answer'],
            'cost_band': cost, 'source_refs': ['fixture://synthetic-official-role-evidence'],
            'effort_bindings': {e: e for e in levels}})
    catalog = {'schema_version': 1, 'source': {'source_ref': 'fixture://catalog',
        'host_scope': 'synthetic-host', 'complete': True, 'session_bound': True,
        'observed_at': NOW.isoformat()}, 'models': models}
    task = {'task_id': 'synthetic-task', 'goal': 'Synthetic bounded task', 'phase': 'implement',
        'risk': 'low', 'depth': 'routine', 'obstacle': 'none', 'bounded': True,
        'contract_clear': True, 'evidence_refs': ['fixture://requirement'],
        'required_modalities': ['text'], 'reasoning_gap': '', 'independent_tracks': 0}
    return task, catalog, {'schema_version': 1, 'profiles': profiles}


class RouterTests(unittest.TestCase):
    def setUp(self):
        self.task, self.catalog, self.profiles = fixtures()

    def route(self, **kwargs):
        return select_route(self.task, self.catalog, self.profiles, now=NOW, **kwargs)

    def assert_state(self, state, **kwargs):
        value = self.route(**kwargs)
        self.assertEqual(state, value['status'], value)
        self.assertIs(value['executed'], False)
        self.assertIsNone(value['observed_model'])
        self.assertIsNone(value['observed_effort'])
        return value

    def exceptional(self):
        self.task.update(phase='diagnose', risk='high', depth='exceptional', reasoning_gap='Synthetic interacting invariant problem')
        return {'task_id': self.task['task_id'], 'exceptional_stages_used': 0}

    def test_small_implementation_uses_worker_and_requires_strong_review(self):
        out = self.assert_state('PLAN_READY')
        self.assertEqual('fixture-worker', out['proposed_model'])
        self.assertEqual('medium', out['proposed_native_effort'])
        self.assertTrue(out['independent_review_required'])
        self.assertEqual('reasoner', out['review_minimum_class'])

    def test_no_fixed_names_arbitrary_future_id_can_win(self):
        model = copy.deepcopy(self.catalog['models'][0])
        model['id'] = 'arbitrary-provider-future-model-123'
        model['catalog_entry_sha256'] = entry_digest(model)
        profile = copy.deepcopy(self.profiles['profiles'][0])
        profile.update(id=model['id'], catalog_entry_sha256=model['catalog_entry_sha256'], basis='evaluated')
        self.catalog['models'].append(model)
        self.profiles['profiles'].append(profile)
        self.assertEqual(model['id'], self.assert_state('PLAN_READY')['proposed_model'])

    def test_evaluated_frontier_does_not_capture_all_small_work(self):
        self.profiles['profiles'][3]['basis'] = 'evaluated'
        self.assertEqual('fixture-worker', self.assert_state('PLAN_READY')['proposed_model'])

    def test_high_risk_review_prefers_evaluated_eligible_route(self):
        self.task.update(phase='review', risk='high')
        self.profiles['profiles'][3]['basis'] = 'evaluated'
        self.assertEqual('fixture-frontier', self.assert_state('PLAN_READY')['proposed_model'])

    def test_equal_new_documented_model_does_not_displace_incumbent_by_name(self):
        self.profiles['profiles'][0]['incumbent_roles'] = ['implement']
        model = copy.deepcopy(self.catalog['models'][0])
        model['id'] = 'aaa-new-model'
        model['catalog_entry_sha256'] = entry_digest(model)
        profile = copy.deepcopy(self.profiles['profiles'][0])
        profile.update(id=model['id'], catalog_entry_sha256=model['catalog_entry_sha256'], incumbent_roles=[])
        self.catalog['models'].append(model)
        self.profiles['profiles'].append(profile)
        self.assertEqual('fixture-worker', self.assert_state('PLAN_READY')['proposed_model'])

    def test_older_identifier_not_excluded(self):
        self.catalog['models'][0]['id'] = 'legacy-0001'
        self.catalog['models'][0]['catalog_entry_sha256'] = entry_digest(self.catalog['models'][0])
        self.profiles['profiles'][0].update(id='legacy-0001', catalog_entry_sha256=self.catalog['models'][0]['catalog_entry_sha256'])
        self.assertEqual('legacy-0001', self.assert_state('PLAN_READY')['proposed_model'])

    def test_review_never_chooses_worker(self):
        self.task['phase'] = 'review'
        out = self.assert_state('PLAN_READY')
        self.assertEqual('fixture-reasoner', out['proposed_model'])
        self.assertTrue(out['fresh_context_required'])
        self.assertFalse(out['may_reuse_parent_if_effective_pair_suitable'])

    def test_architecture_uses_high(self):
        self.task['phase'] = 'architect'
        out = self.assert_state('PLAN_READY')
        self.assertEqual('fixture-reasoner', out['proposed_model'])
        self.assertEqual('high', out['proposed_native_effort'])

    def test_normal_implementation_generalist(self):
        self.task['depth'] = 'normal'
        self.assertEqual('fixture-general', self.assert_state('PLAN_READY')['proposed_model'])

    def test_explicit_xhigh_requires_gap_even_for_normal_implementation(self):
        self.task.update(depth='normal', effort_preference='xhigh', reasoning_gap='')
        self.assert_state('NEEDS_REASONING_GAP')
        self.task['reasoning_gap'] = 'Resolve interacting parser invariants'
        self.assertEqual('xhigh', self.assert_state('PLAN_READY')['semantic_effort'])

    def lifecycle(self, round_number=4):
        self.task.update(depth='normal', risk='high')
        self.task['lifecycle'] = {
            'deliverable_id': 'synthetic-deliverable', 'attempt_id': 'synthetic-fix',
            'stage_kind': 'correction', 'correction_round': round_number,
            'max_correction_rounds': 5, 'escalate_after_round': 3,
            'baseline_capability_class': 'generalist',
            'source_ref': 'fixture://approved-lifecycle-limits',
        }

    def test_correction_escalates_and_requires_fresh_context(self):
        self.lifecycle()
        out = self.assert_state('PLAN_READY')
        self.assertEqual('fixture-reasoner', out['proposed_model'])
        self.assertTrue(out['fresh_context_required'])
        self.assertFalse(out['may_reuse_parent_if_effective_pair_suitable'])
        self.assertEqual('synthetic-deliverable', out['lifecycle']['deliverable_id'])

    def test_correction_limit_never_resets_on_new_task_id(self):
        self.lifecycle(6)
        self.task['task_id'] = 'new-attempt-id'
        self.assert_state('BUDGET_BLOCKED')

    def test_escalation_fails_closed_at_highest_class_or_without_fresh_host(self):
        self.lifecycle()
        self.task['lifecycle']['baseline_capability_class'] = 'frontier'
        self.assert_state('NO_SUPPORTED_ROUTE')
        self.task['lifecycle']['baseline_capability_class'] = 'generalist'
        self.assert_state('DISPATCH_LIMITED', host={'fresh_context_available': False})

    def test_lifecycle_needs_source_and_rejects_fake_rounds(self):
        self.lifecycle()
        for field, value in [('source_ref', ''), ('correction_round', True),
                             ('stage_kind', 'fix'), ('max_correction_rounds', -1)]:
            with self.subTest(field=field):
                before = copy.deepcopy(self.task['lifecycle'])
                self.task['lifecycle'][field] = value
                with self.assertRaises(ValueError):
                    self.route()
                self.task['lifecycle'] = before

    def test_early_correction_preserves_suitable_class(self):
        self.lifecycle(1)
        self.assertEqual('fixture-general', self.assert_state('PLAN_READY')['proposed_model'])

    def test_unknown_cost_tie_is_explained_without_claiming_price_evidence(self):
        self.task['depth'] = 'normal'
        model = copy.deepcopy(self.catalog['models'][1])
        model['id'] = 'aaa-equal'
        model['catalog_entry_sha256'] = entry_digest(model)
        profile = copy.deepcopy(self.profiles['profiles'][1])
        profile.update(id=model['id'], catalog_entry_sha256=model['catalog_entry_sha256'], cost_band='unknown')
        self.catalog['models'].append(model)
        self.profiles['profiles'] = [self.profiles['profiles'][1], profile]
        self.profiles['profiles'][0]['cost_band'] = 'unknown'
        out = self.assert_state('PLAN_READY')
        self.assertEqual('unknown', out['selected_cost_band'])
        self.assertEqual('unknown', out['cost_basis'])
        self.assertEqual('model_id_tie_break', out['tie_break'])
        self.assertEqual('aaa-equal', out['proposed_model'])

    def test_high_risk_review_high_effort(self):
        self.task.update(phase='review', risk='high')
        self.assertEqual('high', self.assert_state('PLAN_READY')['semantic_effort'])

    def test_tiny_answer_can_stay_parent(self):
        self.task['phase'] = 'answer'
        out = self.assert_state('PLAN_READY')
        self.assertEqual('low', out['semantic_effort'])
        self.assertTrue(out['may_reuse_parent_if_effective_pair_suitable'])
        self.assertFalse(out['independent_review_required'])

    def test_integrity_has_priority(self):
        self.task.update(obstacle='integrity', risk='unknown', evidence_refs=[])
        self.catalog = {}
        self.assert_state('INTEGRITY_FAILURE')

    def test_environment_is_not_more_reasoning(self):
        self.task['obstacle'] = 'environment'
        self.assert_state('BLOCKED_ENVIRONMENT')

    def test_intent_ambiguity(self):
        self.task['obstacle'] = 'requirements'
        self.assert_state('NEEDS_CLARIFICATION')

    def test_unknown_risk_not_low(self):
        self.task['risk'] = 'unknown'
        self.assert_state('NEEDS_INSPECTION')

    def test_no_evidence_requires_inspection(self):
        self.task['evidence_refs'] = []
        self.assert_state('NEEDS_INSPECTION')

    def test_unclear_contract(self):
        self.task['contract_clear'] = False
        self.assert_state('NEEDS_CONTRACT')

    def test_unbounded_implementation(self):
        self.task['bounded'] = False
        self.assert_state('NEEDS_CONTRACT')

    def test_deep_implementation_needs_separate_design(self):
        self.task['depth'] = 'deep'
        self.assert_state('NEEDS_CONTRACT')

    def test_deep_named_gap_xhigh(self):
        self.task.update(phase='diagnose', depth='deep', reasoning_gap='A concrete synthetic gap')
        self.assertEqual('xhigh', self.assert_state('PLAN_READY')['semantic_effort'])

    def test_deep_requires_gap(self):
        self.task.update(phase='diagnose', depth='deep')
        self.assert_state('NEEDS_REASONING_GAP')

    def test_max_direct_initial_choice(self):
        ledger = self.exceptional()
        out = self.assert_state('PLAN_READY', ledger=ledger)
        self.assertEqual('max', out['proposed_native_effort'])
        self.assertTrue(out['exceptional_stage_to_charge_on_execution'])

    def test_max_requires_shared_ledger(self):
        self.exceptional()
        self.assert_state('BUDGET_STATE_REQUIRED')

    def test_max_budget_exhausted(self):
        ledger = self.exceptional()
        ledger['exceptional_stages_used'] = 1
        self.assert_state('BUDGET_BLOCKED', ledger=ledger)

    def test_budget_wrong_task_rejected(self):
        ledger = self.exceptional()
        ledger['task_id'] = 'other'
        with self.assertRaises(ValueError): self.route(ledger=ledger)

    def test_ultra_unknown_control_not_simulated(self):
        ledger = self.exceptional()
        self.task['independent_tracks'] = 2
        self.assert_state('ULTRA_CONTROL_UNCONFIRMED', ledger=ledger)

    def test_ultra_reasoning_only_supported(self):
        ledger = self.exceptional()
        self.task['effort_preference'] = 'ultra'
        host = {'host_scope': 'synthetic-host', 'source_ref': 'fixture://host', 'ultra_semantics': 'reasoning_only'}
        out = self.assert_state('PLAN_READY', ledger=ledger, host=host)
        self.assertEqual('ultra', out['proposed_native_effort'])
        self.assertEqual(0, self.task['independent_tracks'])

    def test_ultra_bounded_spawning(self):
        ledger = self.exceptional()
        self.task['independent_tracks'] = 2
        host = {'host_scope': 'synthetic-host', 'source_ref': 'fixture://host', 'ultra_semantics': 'may_spawn',
                'controls_observed': True, 'enforced_child_limit': 2, 'enforced_depth_limit': 1}
        self.assertEqual('ultra', self.assert_state('PLAN_READY', ledger=ledger, host=host)['semantic_effort'])

    def test_ultra_unbounded_descendants_rejected(self):
        ledger = self.exceptional()
        self.task['independent_tracks'] = 2
        host = {'source_ref': 'fixture://host', 'ultra_semantics': 'may_spawn', 'controls_observed': True,
                'enforced_child_limit': 8, 'enforced_depth_limit': 4}
        self.assert_state('ULTRA_CONTROL_UNCONFIRMED', ledger=ledger, host=host)

    def test_effort_below_quality_floor_rejected(self):
        self.task.update(phase='architect', effort_preference='low')
        self.assert_state('QUALITY_CONSTRAINT')

    def test_future_native_effort_binding_requires_no_code_change(self):
        self.task['phase'] = 'architect'
        model = self.catalog['models'][2]
        model['efforts'] = [{'value': 'deliberate-next', 'description': 'SYNTHETIC high equivalent'}]
        model['default_effort'] = 'deliberate-next'
        model['catalog_entry_sha256'] = entry_digest(model)
        profile = self.profiles['profiles'][2]
        profile['catalog_entry_sha256'] = model['catalog_entry_sha256']
        profile['effort_bindings'] = {'high': 'deliberate-next'}
        self.assertEqual('deliberate-next', self.assert_state('PLAN_READY')['proposed_native_effort'])

    def test_new_unprofiled_model_does_not_auto_promote(self):
        model = copy.deepcopy(self.catalog['models'][0])
        model['id'] = 'new-unclassified'
        model['catalog_entry_sha256'] = entry_digest(model)
        self.catalog['models'].append(model)
        self.assertEqual('fixture-worker', self.assert_state('PLAN_READY')['proposed_model'])

    def test_new_catalog_ids_require_profile_refresh_after_retirement(self):
        for model in self.catalog['models']:
            model['id'] = 'replacement-' + model['id']
            model['catalog_entry_sha256'] = entry_digest(model)
        out = self.assert_state('PROFILE_UPDATE_REQUIRED')
        self.assertEqual(sorted(m['id'] for m in self.catalog['models']), out['unprofiled_model_ids'])
        self.assertNotIn('proposed_model', out)

    def test_unprofiled_ineligible_models_do_not_request_profile_refresh(self):
        for unavailable in ('hidden', 'modality', 'effort'):
            with self.subTest(unavailable=unavailable):
                self.task, self.catalog, self.profiles = fixtures()
                for model in self.catalog['models']:
                    model['id'] = 'replacement-' + model['id']
                    if unavailable == 'hidden':
                        model['hidden'] = True
                    elif unavailable == 'modality':
                        model['input_modalities'] = ['image']
                    else:
                        model['efforts'] = []
                        model['default_effort'] = None
                    model['catalog_entry_sha256'] = entry_digest(model)
                out = self.assert_state('NO_SUPPORTED_ROUTE')
                self.assertNotIn('proposed_model', out)

    def test_retired_profiles_do_not_make_absent_models_usable(self):
        self.catalog['models'] = []
        out = self.assert_state('NO_SUPPORTED_ROUTE')
        self.assertNotIn('proposed_model', out)

    def test_provisional_not_default(self):
        self.profiles['profiles'][0]['basis'] = 'provisional'
        self.assertEqual('fixture-general', self.assert_state('PLAN_READY')['proposed_model'])

    def test_only_provisional_requires_explicit_canary(self):
        self.profiles['profiles'] = self.profiles['profiles'][:1]
        self.profiles['profiles'][0]['basis'] = 'provisional'
        self.assert_state('NO_SUPPORTED_ROUTE')
        self.task['canary_authorized'] = True
        out = self.assert_state('PLAN_READY', policy={'allow_provisional_canary': True})
        self.assertEqual('provisional', out['basis'])

    def test_provisional_never_critical_reviewer(self):
        self.task.update(phase='review', risk='high', canary_authorized=True)
        for p in self.profiles['profiles']: p['basis'] = 'provisional'
        self.assert_state('NO_SUPPORTED_ROUTE', policy={'allow_provisional_canary': True})

    def test_expired_catalog(self):
        self.catalog['source']['observed_at'] = (NOW - timedelta(hours=25)).isoformat()
        self.assert_state('CAPABILITY_REFRESH_REQUIRED')

    def test_future_catalog(self):
        self.catalog['source']['observed_at'] = (NOW + timedelta(days=1)).isoformat()
        self.assert_state('CAPABILITY_REFRESH_REQUIRED')

    def test_unbound_local_cli_catalog(self):
        self.catalog['source']['session_bound'] = False
        self.assert_state('CAPABILITY_REFRESH_REQUIRED')

    def test_incomplete_pagination_not_accepted(self):
        self.catalog['source']['complete'] = False
        self.assert_state('CAPABILITY_REFRESH_REQUIRED')

    def test_illustrative_catalog(self):
        self.catalog['illustrative_only'] = True
        self.assert_state('CAPABILITY_REFRESH_REQUIRED')

    def test_different_host_account_scope(self):
        self.assert_state('CAPABILITY_REFRESH_REQUIRED', host={'host_scope': 'different-host'})

    def test_model_removed_uses_remaining_eligible(self):
        self.catalog['models'] = self.catalog['models'][1:]
        self.assertEqual('fixture-general', self.assert_state('PLAN_READY')['proposed_model'])

    def test_hidden_model_not_selected(self):
        self.catalog['models'][0]['hidden'] = True
        self.catalog['models'][0]['catalog_entry_sha256'] = entry_digest(self.catalog['models'][0])
        self.assertEqual('fixture-general', self.assert_state('PLAN_READY')['proposed_model'])

    def test_expired_all_profiles(self):
        for p in self.profiles['profiles']: p['checked_at'] = (NOW - timedelta(days=31)).isoformat()
        self.assert_state('PROFILE_UPDATE_REQUIRED')

    def test_catalog_metadata_change_invalidates_profile(self):
        self.catalog['models'][0]['description'] = 'changed deployment description'
        self.catalog['models'][0]['catalog_entry_sha256'] = entry_digest(self.catalog['models'][0])
        self.assertEqual('fixture-general', self.assert_state('PLAN_READY')['proposed_model'])

    def test_forged_fingerprint_is_input_error(self):
        self.catalog['models'][0]['description'] = 'changed without recomputing'
        with self.assertRaises(ValueError): self.route()

    def test_unsupported_modality(self):
        self.task['required_modalities'] = ['audio']
        self.assert_state('NO_SUPPORTED_ROUTE')

    def test_unsupported_effort_not_silently_downgraded(self):
        self.task['phase'] = 'architect'
        for p in self.profiles['profiles']: p['effort_bindings'].pop('high')
        self.assert_state('NO_SUPPORTED_ROUTE')

    def test_duplicate_models_rejected(self):
        self.catalog['models'].append(copy.deepcopy(self.catalog['models'][0]))
        with self.assertRaises(ValueError): self.route()

    def test_duplicate_profiles_rejected(self):
        self.profiles['profiles'].append(copy.deepcopy(self.profiles['profiles'][0]))
        with self.assertRaises(ValueError): self.route()

    def test_unknown_policy_field_rejected(self):
        with self.assertRaises(ValueError): self.route(policy={'silently_skip_tests': True})

    def test_booleans_cannot_impersonate_counters(self):
        ledger = self.exceptional()
        ledger['exceptional_stages_used'] = True
        with self.assertRaises(ValueError): self.route(ledger=ledger)

    def test_absent_profiles_request_bootstrap(self):
        self.profiles['profiles'] = []
        self.assert_state('PROFILE_UPDATE_REQUIRED')

    def test_source_refs_mandatory(self):
        self.profiles['profiles'][0]['source_refs'] = []
        with self.assertRaises(ValueError): self.route()

if __name__ == '__main__': unittest.main()
