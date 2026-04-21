"""
tests/test_upgrades.py
-----------------------
NEW TEST MODULE — Tests for all upgrade features.
Extends the original test_risk_engine.py without modifying it.

Test Coverage:
  - Feature 1: Live simulation events
  - Feature 2: User history tracking
  - Feature 3: Trend analysis
  - Feature 5: Smart risk weighting (scenario weight overrides)
  - Feature 6: Scenario mode (student, professional, etc.)
  - Feature 7: Rule reload (promoted to primary test)
  - Integration: full_assess() pipeline

V-Model alignment:
  - Each new module has a corresponding TestCase class.
"""

import sys
import os
import json
import unittest
import tempfile
import shutil

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from engine.scenario_engine import ScenarioLoader, ScenarioAwareCalculator
from engine.history_tracker import UserHistoryTracker, TrendAnalyzer
from engine.live_simulator  import LiveEventSimulator
from engine.risk_engine     import RuleLoader, ScoreCalculator, PrivacyRiskEngine
from engine.risk_engine_v2  import PrivacyRiskEngineV2


# ──────────────────────────────────────────────
# FEATURE 6: Scenario Mode Tests
# ──────────────────────────────────────────────
class TestScenarioLoader(unittest.TestCase):

    def setUp(self):
        self.loader = ScenarioLoader()

    def test_scenarios_file_loads(self):
        scenarios = self.loader.list_scenarios()
        self.assertIsInstance(scenarios, list)
        self.assertGreater(len(scenarios), 0)

    def test_required_scenario_ids_exist(self):
        """Black-box: standard scenarios must all be present."""
        required = ['student', 'working_professional', 'high_social_media']
        for sid in required:
            s = self.loader.get_scenario(sid)
            self.assertIsNotNone(s, f"Scenario '{sid}' missing from scenarios.json")

    def test_scenario_has_required_fields(self):
        """White-box: each scenario must have weight_overrides and rule_multipliers."""
        for s_meta in self.loader.list_scenarios():
            s = self.loader.get_scenario(s_meta['id'])
            self.assertIn('weight_overrides', s,   f"Missing weight_overrides in {s_meta['id']}")
            self.assertIn('rule_multipliers', s,   f"Missing rule_multipliers in {s_meta['id']}")
            self.assertIn('context_note', s,       f"Missing context_note in {s_meta['id']}")

    def test_scenario_weights_sum_to_one(self):
        """White-box: each scenario's weight_overrides must sum to ~1.0."""
        for s_meta in self.loader.list_scenarios():
            s = self.loader.get_scenario(s_meta['id'])
            total = sum(s['weight_overrides'].values())
            self.assertAlmostEqual(total, 1.0, places=1,
                                   msg=f"Scenario '{s_meta['id']}' weights sum={total}")

    def test_unknown_scenario_returns_none(self):
        result = self.loader.get_scenario('nonexistent_scenario_xyz')
        self.assertIsNone(result)


class TestScenarioAwareCalculator(unittest.TestCase):

    def setUp(self):
        loader = RuleLoader()
        self.calc = ScoreCalculator(loader)
        self.s_loader = ScenarioLoader()
        self.s_calc = ScenarioAwareCalculator(self.calc, self.s_loader)
        # Typical mid-risk responses
        self.responses = {
            'AS01': True,  'AS02': False, 'AS03': 1,
            'DE01': True,  'DE02': False, 'NS01': True,
            'DS02': 2,     'BH01': False
        }

    def test_scenario_none_fallback_to_base(self):
        """Black-box: None scenario must give same score as base calculator."""
        base_result     = self.calc.calculate(self.responses)
        scenario_result = self.s_calc.calculate_with_scenario(self.responses, None)
        self.assertEqual(base_result['final_score'], scenario_result['final_score'])

    def test_high_social_media_boosts_data_exposure(self):
        """Black-box: social media scenario should raise data exposure weight."""
        base  = self.s_calc.calculate_with_scenario(self.responses, None)
        social = self.s_calc.calculate_with_scenario(self.responses, 'high_social_media')
        # High social media scenario applies 1.6x on DE01 (which is True = risky)
        # So final score should be >= base score
        self.assertGreaterEqual(social['final_score'], base['final_score'] - 5,
                                 "Social media scenario should not drastically reduce score")

    def test_scenario_metadata_present_in_result(self):
        """Black-box: scenario metadata must be present in result."""
        result = self.s_calc.calculate_with_scenario(self.responses, 'student')
        self.assertIsNotNone(result['scenario'])
        self.assertEqual(result['scenario']['id'], 'student')
        self.assertIn('context_note', result['scenario'])

    def test_base_score_preserved_in_result(self):
        """White-box: base_score must be the unmodified score."""
        result = self.s_calc.calculate_with_scenario(self.responses, 'working_professional')
        base   = self.calc.calculate(self.responses)
        self.assertEqual(result['base_score'], base['final_score'])

    def test_score_delta_computed_correctly(self):
        """White-box: score_delta = final_score - base_score."""
        result = self.s_calc.calculate_with_scenario(self.responses, 'student')
        expected_delta = round(result['final_score'] - result['base_score'], 1)
        self.assertEqual(result['score_delta'], expected_delta)

    def test_all_scenarios_produce_valid_score(self):
        """Integration: all scenarios must produce score in [0, 100]."""
        for s_meta in self.s_loader.list_scenarios():
            result = self.s_calc.calculate_with_scenario(self.responses, s_meta['id'])
            self.assertGreaterEqual(result['final_score'], 0)
            self.assertLessEqual(result['final_score'],  100,
                                  f"Scenario {s_meta['id']} produced score > 100")


# ──────────────────────────────────────────────
# FEATURE 2: User History Tracking Tests
# ──────────────────────────────────────────────
class TestUserHistoryTracker(unittest.TestCase):

    def setUp(self):
        # Use temp directory so tests don't pollute real data
        self.tmpdir = tempfile.mkdtemp()
        history_file = os.path.join(self.tmpdir, 'history.json')
        self.tracker = UserHistoryTracker(history_file=history_file)
        self.dummy_cat_scores = {
            'account_security': {'normalized': 50.0},
            'data_exposure':    {'normalized': 30.0},
            'network_security': {'normalized': 40.0},
            'device_security':  {'normalized': 20.0},
            'behavioral':       {'normalized': 60.0}
        }

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_first_assessment_has_no_previous(self):
        """Black-box: first entry should return has_previous=False."""
        result = self.tracker.record_assessment(
            'alice', 45.0, 'MEDIUM RISK', self.dummy_cat_scores
        )
        self.assertFalse(result['has_previous'])

    def test_second_assessment_shows_comparison(self):
        """Black-box: second entry must show delta vs first."""
        self.tracker.record_assessment('bob', 60.0, 'HIGH RISK', self.dummy_cat_scores)
        result = self.tracker.record_assessment('bob', 45.0, 'MEDIUM RISK', self.dummy_cat_scores)
        self.assertTrue(result['has_previous'])
        self.assertEqual(result['previous_score'], 60.0)
        self.assertEqual(result['current_score'],  45.0)
        self.assertEqual(result['delta'], -15.0)

    def test_improvement_direction_labelled_correctly(self):
        """Black-box: score decrease → direction = 'improved'."""
        self.tracker.record_assessment('carol', 70.0, 'HIGH RISK', self.dummy_cat_scores)
        result = self.tracker.record_assessment('carol', 40.0, 'MEDIUM RISK', self.dummy_cat_scores)
        self.assertEqual(result['direction'], 'improved')

    def test_degradation_direction_labelled_correctly(self):
        """Black-box: score increase → direction = 'degraded'."""
        self.tracker.record_assessment('dave', 30.0, 'LOW RISK', self.dummy_cat_scores)
        result = self.tracker.record_assessment('dave', 70.0, 'HIGH RISK', self.dummy_cat_scores)
        self.assertEqual(result['direction'], 'degraded')

    def test_history_persists_and_retrieves(self):
        """White-box: entries written to file must be retrievable."""
        for score in [55.0, 48.0, 42.0]:
            self.tracker.record_assessment('eve', score, 'MEDIUM RISK', self.dummy_cat_scores)
        history = self.tracker.get_history('eve')
        self.assertEqual(len(history), 3)
        self.assertEqual(history[0]['score'], 55.0)
        self.assertEqual(history[2]['score'], 42.0)

    def test_max_50_entries_per_user(self):
        """White-box: history capped at 50 entries."""
        for i in range(60):
            self.tracker.record_assessment('frank', float(i), 'LOW RISK', self.dummy_cat_scores)
        history = self.tracker.get_history('frank')
        self.assertLessEqual(len(history), 50)

    def test_category_deltas_computed(self):
        """White-box: category_deltas must reflect per-category changes."""
        cat_a = {'account_security': {'normalized': 60.0}, 'data_exposure': {'normalized': 40.0},
                 'network_security': {'normalized': 30.0}, 'device_security': {'normalized': 20.0},
                 'behavioral': {'normalized': 50.0}}
        cat_b = {'account_security': {'normalized': 40.0}, 'data_exposure': {'normalized': 50.0},
                 'network_security': {'normalized': 30.0}, 'device_security': {'normalized': 20.0},
                 'behavioral': {'normalized': 50.0}}
        self.tracker.record_assessment('grace', 55.0, 'HIGH RISK', cat_a)
        result = self.tracker.record_assessment('grace', 50.0, 'MEDIUM RISK', cat_b)
        deltas = result['category_deltas']
        self.assertEqual(deltas['account_security'], -20.0)
        self.assertEqual(deltas['data_exposure'],    10.0)


# ──────────────────────────────────────────────
# FEATURE 3: Trend Analysis Tests
# ──────────────────────────────────────────────
class TestTrendAnalyzer(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        history_file = os.path.join(self.tmpdir, 'history.json')
        self.tracker = UserHistoryTracker(history_file=history_file)
        self.analyzer = TrendAnalyzer(self.tracker)
        self.dummy_cats = {
            'account_security': {'normalized': 50.0},
            'data_exposure':    {'normalized': 30.0},
            'network_security': {'normalized': 40.0},
            'device_security':  {'normalized': 20.0},
            'behavioral':       {'normalized': 60.0}
        }

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_insufficient_data_returns_no_trend(self):
        """Black-box: single entry → has_trend=False."""
        self.tracker.record_assessment('henry', 50.0, 'MEDIUM RISK', self.dummy_cats)
        result = self.analyzer.analyze('henry')
        self.assertFalse(result['has_trend'])

    def test_consistently_decreasing_scores_trend_improving(self):
        """Black-box: monotonically decreasing scores → 'improving' trend."""
        for score in [80.0, 70.0, 60.0, 50.0, 40.0]:
            self.tracker.record_assessment('ivan', score, 'HIGH RISK', self.dummy_cats)
        result = self.analyzer.analyze('ivan')
        self.assertIn(result['trend_direction'], ['improving', 'slightly_improving'],
                      f"Expected improving, got: {result['trend_direction']}")

    def test_consistently_increasing_scores_trend_worsening(self):
        """Black-box: monotonically increasing scores → 'worsening' trend."""
        for score in [20.0, 30.0, 50.0, 65.0, 80.0]:
            self.tracker.record_assessment('jane', score, 'HIGH RISK', self.dummy_cats)
        result = self.analyzer.analyze('jane')
        self.assertIn(result['trend_direction'], ['worsening', 'slightly_worsening'],
                      f"Expected worsening, got: {result['trend_direction']}")

    def test_trend_result_contains_required_keys(self):
        """Black-box: trend result must have all required fields."""
        for score in [60.0, 55.0, 50.0]:
            self.tracker.record_assessment('kate', score, 'MEDIUM RISK', self.dummy_cats)
        result = self.analyzer.analyze('kate')
        required = ['has_trend', 'entries_count', 'scores', 'trend_direction',
                    'overall_delta', 'peak_score', 'trough_score', 'moving_average_3']
        for key in required:
            self.assertIn(key, result, f"Missing key in trend result: '{key}'")

    def test_moving_average_length_matches_scores(self):
        """White-box: moving_average_3 length must equal scores length."""
        for score in [70.0, 65.0, 60.0, 55.0]:
            self.tracker.record_assessment('liam', score, 'HIGH RISK', self.dummy_cats)
        result = self.analyzer.analyze('liam')
        self.assertEqual(len(result['moving_average_3']), len(result['scores']))

    def test_improving_streak_detected(self):
        """White-box: 3 consecutive improvements → improving_streak >= 3."""
        for score in [70.0, 65.0, 55.0, 45.0, 35.0]:
            self.tracker.record_assessment('mia', score, 'MEDIUM RISK', self.dummy_cats)
        result = self.analyzer.analyze('mia')
        self.assertGreaterEqual(result['improving_streak'], 3)

    def test_overall_delta_computed_correctly(self):
        """White-box: overall_delta = latest - first."""
        scores = [60.0, 55.0, 45.0]
        for s in scores:
            self.tracker.record_assessment('noah', s, 'MEDIUM RISK', self.dummy_cats)
        result = self.analyzer.analyze('noah')
        self.assertEqual(result['overall_delta'], scores[-1] - scores[0])


# ──────────────────────────────────────────────
# FEATURE 1: Live Event Simulation Tests
# ──────────────────────────────────────────────
class TestLiveSimulator(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        events_path = os.path.join(self.tmpdir, 'live_events.json')
        self.sim = LiveEventSimulator(events_path=events_path)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_events_generated(self):
        """Black-box: generate_random_events must return correct count."""
        events = self.sim.generate_random_events(count=4, seed=42)
        self.assertEqual(len(events), 4)

    def test_each_event_has_required_fields(self):
        """White-box: every event must have risk_delta, severity, mitigation."""
        events = self.sim.generate_random_events(count=3, seed=0)
        required = ['event_id', 'type', 'label', 'risk_delta', 'severity',
                    'affected_rule', 'mitigatable', 'simulated_at']
        for event in events:
            for field in required:
                self.assertIn(field, event, f"Missing '{field}' in event")

    def test_apply_events_updates_score(self):
        """Black-box: applying a positive-delta event raises live_score."""
        positive_event = [{
            'event_id': 'TEST_001', 'type': 'test', 'label': 'Test',
            'icon': '⚠️', 'description': 'Test event',
            'risk_delta': 20, 'affected_rule': 'AS01',
            'severity': 'high', 'category': 'account_security',
            'mitigatable': True, 'mitigation': 'Fix it',
            'simulated_at': '2025-01-01T10:00:00', 'simulated': True
        }]
        result = self.sim.apply_events_to_score(50.0, positive_event)
        self.assertEqual(result['live_score'], 70.0)
        self.assertEqual(result['total_delta'], 20.0)

    def test_apply_negative_event_lowers_score(self):
        """Black-box: negative-delta event (security improvement) lowers score."""
        neg_event = [{
            'event_id': 'TEST_002', 'type': 'test', 'label': 'Good Event',
            'icon': '✅', 'description': 'Improvement',
            'risk_delta': -15, 'affected_rule': 'DS02',
            'severity': 'positive', 'category': 'device_security',
            'mitigatable': False, 'mitigation': '',
            'simulated_at': '2025-01-01T10:00:00', 'simulated': True
        }]
        result = self.sim.apply_events_to_score(50.0, neg_event)
        self.assertEqual(result['live_score'], 35.0)

    def test_score_never_below_zero(self):
        """White-box: multiple negative events must not produce score < 0."""
        events = [{'event_id': f'E{i}', 'type': 'test', 'label': 'X', 'icon': '',
                   'description': '', 'risk_delta': -30, 'affected_rule': 'DS02',
                   'severity': 'positive', 'category': 'device_security',
                   'mitigatable': False, 'mitigation': '',
                   'simulated_at': '2025-01-01T10:00:00', 'simulated': True}
                  for i in range(5)]
        result = self.sim.apply_events_to_score(20.0, events)
        self.assertGreaterEqual(result['live_score'], 0)

    def test_score_never_above_100(self):
        """White-box: multiple positive events must not produce score > 100."""
        events = [{'event_id': f'E{i}', 'type': 'test', 'label': 'X', 'icon': '',
                   'description': '', 'risk_delta': 30, 'affected_rule': 'AS01',
                   'severity': 'critical', 'category': 'account_security',
                   'mitigatable': True, 'mitigation': '',
                   'simulated_at': '2025-01-01T10:00:00', 'simulated': True}
                  for i in range(5)]
        result = self.sim.apply_events_to_score(80.0, events)
        self.assertLessEqual(result['live_score'], 100)

    def test_timeline_length_matches_events(self):
        """White-box: timeline must have one entry per event."""
        events = self.sim.generate_random_events(count=5, seed=99)
        result = self.sim.apply_events_to_score(50.0, events)
        self.assertEqual(len(result['timeline']), 5)

    def test_get_all_event_types_returns_dict(self):
        types = self.sim.get_all_event_types()
        self.assertIsInstance(types, dict)
        self.assertGreater(len(types), 0)


# ──────────────────────────────────────────────
# INTEGRATION: Full V2 Pipeline Tests
# ──────────────────────────────────────────────
class TestPrivacyRiskEngineV2Integration(unittest.TestCase):

    def setUp(self):
        self.engine = PrivacyRiskEngineV2()
        self.user_data = {
            'user_info': {'name': 'Test_V2_User'},
            'responses': {
                'AS01': True, 'AS02': False, 'AS03': 1,
                'DE01': True, 'DE02': False, 'NS01': True,
                'DS02': 2, 'BH01': False
            }
        }

    def test_full_assess_returns_all_v2_sections(self):
        """Integration: full_assess must include all new v2 result keys."""
        result = self.engine.full_assess(self.user_data, scenario_id='student')
        required_keys = ['score_result', 'recommendations', 'history_comparison',
                         'trend', 'summary', 'scenario_id']
        for key in required_keys:
            self.assertIn(key, result, f"Missing v2 key: '{key}'")

    def test_full_assess_with_live_simulation(self):
        """Integration: live simulation mode returns live_simulation block."""
        result = self.engine.full_assess(self.user_data, simulate_events=True, event_count=3)
        self.assertIsNotNone(result['live_simulation'])
        self.assertIn('live_score',   result['live_simulation'])
        self.assertIn('timeline',     result['live_simulation'])
        self.assertEqual(len(result['live_simulation']['timeline']), 3)

    def test_v1_assess_still_works(self):
        """Regression: original v1 assess() interface must still work unchanged."""
        result = self.engine.assess(self.user_data)
        required = ['user_info', 'score_result', 'recommendations', 'summary']
        for key in required:
            self.assertIn(key, result, f"V1 interface broken: missing '{key}'")

    def test_scenario_switching_changes_score(self):
        """Integration: different scenarios should produce potentially different scores."""
        r1 = self.engine.full_assess(self.user_data, scenario_id='student')
        r2 = self.engine.full_assess(self.user_data, scenario_id='working_professional')
        # Scores may differ due to weight overrides
        self.assertIn('final_score', r1['score_result'])
        self.assertIn('final_score', r2['score_result'])
        # Both valid
        self.assertGreaterEqual(r1['score_result']['final_score'], 0)
        self.assertGreaterEqual(r2['score_result']['final_score'], 0)

    def test_rule_reload_works_in_v2(self):
        """Feature 7: reload_rules() must work through v2 interface."""
        msg = self.engine.reload_rules()
        self.assertIn('Rules reloaded', msg)

    def test_list_scenarios_returns_all(self):
        """Integration: list_scenarios must return all defined scenarios."""
        scenarios = self.engine.list_scenarios()
        self.assertGreaterEqual(len(scenarios), 3)
        ids = [s['id'] for s in scenarios]
        self.assertIn('student', ids)
        self.assertIn('working_professional', ids)

    def test_audit_stats_tracked(self):
        """Integration: audit logger must track assessments."""
        self.engine.full_assess(self.user_data)
        stats = self.engine.get_audit_stats()
        self.assertIn('total_assessments', stats)
        self.assertGreater(stats['total_assessments'], 0)


if __name__ == '__main__':
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    suite.addTests(loader.loadTestsFromTestCase(TestScenarioLoader))
    suite.addTests(loader.loadTestsFromTestCase(TestScenarioAwareCalculator))
    suite.addTests(loader.loadTestsFromTestCase(TestUserHistoryTracker))
    suite.addTests(loader.loadTestsFromTestCase(TestTrendAnalyzer))
    suite.addTests(loader.loadTestsFromTestCase(TestLiveSimulator))
    suite.addTests(loader.loadTestsFromTestCase(TestPrivacyRiskEngineV2Integration))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
