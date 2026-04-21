"""
engine/risk_engine_v2.py
------------------------
UPGRADED MODULE — PrivacyRiskEngine v2

Extends the original PrivacyRiskEngine (unchanged) with:
  - Scenario-aware scoring (ScenarioAwareCalculator)
  - User history tracking (UserHistoryTracker)
  - Trend analysis (TrendAnalyzer)
  - Live event simulation (LiveEventSimulator)
  - Dynamic rule reload (existing, promoted to primary interface)

SE Models applied:
  - Incremental: each new feature is a new composed module
  - Evolutionary: new capabilities added without breaking existing interface
  - Open/Closed: original PrivacyRiskEngine NOT modified; extended via composition

Usage:
    engine = PrivacyRiskEngineV2()
    result = engine.full_assess(user_data, scenario_id='student', simulate_events=True)
"""

import datetime
from typing import Dict, List, Optional

# Import original (unchanged) modules
from engine.risk_engine import PrivacyRiskEngine, RuleLoader, ScoreCalculator

# Import new modules
from engine.scenario_engine  import ScenarioLoader, ScenarioAwareCalculator
from engine.history_tracker  import UserHistoryTracker, TrendAnalyzer
from engine.live_simulator   import LiveEventSimulator
from engine.data_handler     import SessionStore, AuditLogger


class PrivacyRiskEngineV2:
    """
    Extended engine facade — all v1 functionality preserved.
    New capabilities: scenarios, history, trends, live simulation.
    """

    def __init__(self):
        # ── Original modules (unchanged) ──
        self._v1 = PrivacyRiskEngine()

        # ── New modules ──
        self.scenario_loader   = ScenarioLoader()
        self.scenario_calc     = ScenarioAwareCalculator(self._v1.calculator, self.scenario_loader)
        self.history_tracker   = UserHistoryTracker()
        self.trend_analyzer    = TrendAnalyzer(self.history_tracker)
        self.live_simulator    = LiveEventSimulator()
        self.session_store     = SessionStore()
        self.audit_logger      = AuditLogger()

    # ────────────────────────────────────────────────────
    # PRIMARY METHOD — Full assessment with all features
    # ────────────────────────────────────────────────────
    def full_assess(self,
                    user_data: Dict,
                    scenario_id: Optional[str] = None,
                    simulate_events: bool = False,
                    event_count: int = 3) -> Dict:
        """
        Complete assessment pipeline v2:
        responses → scenario-aware score → recommendations
        → history comparison → trend → live simulation → full report
        """
        responses  = user_data.get('responses', {})
        user_info  = user_data.get('user_info', {})
        user_key   = user_info.get('name', 'anonymous').lower().strip()

        # 1. Scenario-aware scoring
        score_result = self.scenario_calc.calculate_with_scenario(responses, scenario_id)

        # 2. Recommendations (reuse v1 engine)
        recommendations = self._v1.rec_engine.get_recommendations(
            score_result['rule_details'], responses
        )

        # 3. History tracking + comparison
        comparison = self.history_tracker.record_assessment(
            user_key=user_key,
            score=score_result['final_score'],
            risk_label=score_result['risk_level']['label'],
            category_scores=score_result['category_scores'],
            scenario_id=scenario_id
        )

        # 4. Trend analysis
        trend = self.trend_analyzer.analyze(user_key)

        # 5. Live event simulation (optional)
        live_data = None
        if simulate_events:
            events = self.live_simulator.generate_random_events(count=event_count)
            live_data = self.live_simulator.apply_events_to_score(
                score_result['final_score'], events
            )

        # 6. Summary
        summary = self._generate_summary_v2(score_result, recommendations, comparison, trend)

        # 7. Persist session
        full_result = {
            'user_info':       user_info,
            'score_result':    score_result,
            'recommendations': recommendations,
            'general_resources': self._v1.rec_engine.general_resources,
            'rules_version':   self._v1.rule_loader.version,
            'summary':         summary,
            'history_comparison': comparison,
            'trend':           trend,
            'live_simulation': live_data,
            'scenario_id':     scenario_id,
            'assessed_at':     datetime.datetime.now().isoformat()
        }

        session_id = self.session_store.save_session(full_result)
        self.audit_logger.log(
            session_id=session_id,
            score=score_result['final_score'],
            risk_label=score_result['risk_level']['label'],
            issues_count=len(recommendations)
        )

        return full_result

    # ────────────────────────────────────────────────────
    # V1 COMPATIBILITY — All original methods preserved
    # ────────────────────────────────────────────────────
    def assess(self, user_data: Dict) -> Dict:
        """Original v1 interface — unchanged for backward compatibility."""
        return self._v1.assess(user_data)

    def get_questions(self) -> List[Dict]:
        return self._v1.get_questions()

    def reload_rules(self) -> str:
        self._v1.reload_rules()
        return f"Rules reloaded. Version: {self._v1.rule_loader.version}"

    # ────────────────────────────────────────────────────
    # SCENARIO METHODS
    # ────────────────────────────────────────────────────
    def list_scenarios(self) -> List[Dict]:
        return self.scenario_loader.list_scenarios()

    def get_scenario(self, scenario_id: str) -> Optional[Dict]:
        return self.scenario_loader.get_scenario(scenario_id)

    # ────────────────────────────────────────────────────
    # HISTORY & TREND METHODS
    # ────────────────────────────────────────────────────
    def get_user_history(self, user_key: str) -> List[Dict]:
        return self.history_tracker.get_history(user_key)

    def get_trend(self, user_key: str) -> Dict:
        return self.trend_analyzer.analyze(user_key)

    # ────────────────────────────────────────────────────
    # LIVE SIMULATION METHODS
    # ────────────────────────────────────────────────────
    def simulate_live_events(self, base_score: float, count: int = 3) -> Dict:
        events = self.live_simulator.generate_random_events(count=count)
        return self.live_simulator.apply_events_to_score(base_score, events)

    def get_event_types(self) -> Dict:
        return self.live_simulator.get_all_event_types()

    # ────────────────────────────────────────────────────
    # ANALYTICS
    # ────────────────────────────────────────────────────
    def get_audit_stats(self) -> Dict:
        return self.audit_logger.get_statistics()

    def get_recent_sessions(self, limit: int = 10) -> List[Dict]:
        return self.session_store.get_recent_sessions(limit)

    # ────────────────────────────────────────────────────
    # PRIVATE HELPERS
    # ────────────────────────────────────────────────────
    def _generate_summary_v2(self, score_result, recs, comparison, trend) -> Dict:
        base = self._v1._generate_summary(score_result, recs)
        base['has_comparison']     = comparison.get('has_previous', False)
        base['score_delta']        = comparison.get('delta')
        base['change_label']       = comparison.get('label', 'First assessment')
        base['trend_direction']    = trend.get('trend_direction', 'unknown')
        base['trend_label']        = trend.get('trend_label', '—')
        base['scenario_applied']   = score_result.get('scenario') is not None
        base['scenario_label']     = score_result.get('scenario', {}).get('label', 'None') if score_result.get('scenario') else 'Default'
        base['base_score']         = score_result.get('base_score', score_result['final_score'])
        return base
