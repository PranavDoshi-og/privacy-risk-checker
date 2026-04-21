"""
engine/scenario_engine.py
--------------------------
NEW MODULE — Upgrade Feature #6: User Scenario Mode
Also handles Feature #5: Smart Risk Weighting

Loads user scenario profiles from scenarios.json.
Applies scenario-specific category weight overrides and rule multipliers
to the ScoreCalculator, producing context-aware risk scores.

SE Model: Incremental (new module composing into existing Facade).
Design Pattern: Decorator — wraps ScoreCalculator with scenario context.
"""

import json
import os
from typing import Dict, List, Optional

SCENARIOS_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'scenarios.json')


class ScenarioLoader:
    """Loads and validates user scenario profiles from JSON."""

    def __init__(self, scenarios_path: str = SCENARIOS_PATH):
        self.scenarios_path = scenarios_path
        self._data: Optional[Dict] = None
        self._load()

    def _load(self):
        with open(self.scenarios_path, 'r') as f:
            self._data = json.load(f)

    def get_scenario(self, scenario_id: str) -> Optional[Dict]:
        return self._data['scenarios'].get(scenario_id)

    def list_scenarios(self) -> List[Dict]:
        return [
            {
                'id': sid,
                'label': s['label'],
                'icon': s['icon'],
                'description': s['description'],
                'typical_risks': s['typical_risks']
            }
            for sid, s in self._data['scenarios'].items()
        ]

    @property
    def version(self) -> str:
        return self._data.get('version', 'unknown')


class ScenarioAwareCalculator:
    """
    Extends ScoreCalculator with scenario-based weight/multiplier overrides.
    Composing over existing ScoreCalculator — no modification to original class.
    """

    def __init__(self, base_calculator, scenario_loader: ScenarioLoader):
        self.base = base_calculator
        self.loader = scenario_loader

    def calculate_with_scenario(self, responses: Dict, scenario_id: Optional[str] = None) -> Dict:
        """
        If scenario_id provided: apply weight overrides and rule multipliers.
        Otherwise: falls back to base calculator behaviour.
        Returns enriched result with scenario metadata.
        """
        scenario = self.loader.get_scenario(scenario_id) if scenario_id else None

        if scenario is None:
            result = self.base.calculate(responses)
            result['scenario'] = None
            result['scenario_adjustments'] = {}
            return result

        # Apply rule multipliers to responses (synthetic score boosting)
        # We do this by creating an augmented rule set view
        multipliers = scenario.get('rule_multipliers', {})
        weight_overrides = scenario.get('weight_overrides', {})

        # Calculate with base first
        base_result = self.base.calculate(responses)

        # Apply scenario weight overrides to final score recalculation
        adjusted_cat_scores = {}
        adjustments_log = []

        for cat_id, cat_data in base_result['category_scores'].items():
            override_weight = weight_overrides.get(cat_id, cat_data['weight'])
            original_weight = cat_data['weight']

            # Apply rule multipliers within this category
            cat_normalized = cat_data['normalized']
            multiplier_applied = {}

            for rd in base_result['rule_details']:
                if rd['category'] == cat_data['label'] and rd['rule_id'] in multipliers:
                    m = multipliers[rd['rule_id']]
                    original_contribution = rd['raw_score']
                    boosted = min(original_contribution * m, rd['max_possible'])
                    boost_delta = boosted - original_contribution
                    if boost_delta > 0:
                        cat_normalized = min(100, cat_normalized + (boost_delta / max(cat_data['max_score'], 1)) * 100)
                        multiplier_applied[rd['rule_id']] = round(m, 2)

            weighted_contribution = round(cat_normalized * override_weight, 2)
            adjusted_cat_scores[cat_id] = {
                **cat_data,
                'weight': override_weight,
                'original_weight': original_weight,
                'normalized': round(cat_normalized, 2),
                'weighted_contribution': weighted_contribution,
                'weight_changed': abs(override_weight - original_weight) > 0.001
            }

            if abs(override_weight - original_weight) > 0.001 or multiplier_applied:
                adjustments_log.append({
                    'category': cat_data['label'],
                    'original_weight': original_weight,
                    'adjusted_weight': override_weight,
                    'multiplied_rules': multiplier_applied
                })

        # Recompute final score with scenario weights
        final_score = sum(v['weighted_contribution'] for v in adjusted_cat_scores.values())
        final_score = min(100, round(final_score, 1))

        return {
            **base_result,
            'final_score': final_score,
            'category_scores': adjusted_cat_scores,
           'risk_level': self.base.get_risk_level(final_score),
            'scenario': {
                'id': scenario_id,
                'label': scenario['label'],
                'icon': scenario['icon'],
                'context_note': scenario['context_note'],
                'typical_risks': scenario['typical_risks']
            },
            'scenario_adjustments': adjustments_log,
            'base_score': base_result['final_score'],
            'score_delta': round(final_score - base_result['final_score'], 1)
        }
