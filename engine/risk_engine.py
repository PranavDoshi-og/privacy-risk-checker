import json
import os

RULES_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'rules.json')


class RuleLoader:
    def __init__(self):
        self.rules = self.load_rules()
        self.version = "1.0"

    def load_rules(self):
        with open(RULES_PATH, 'r') as f:
            return json.load(f)


class ScoreCalculator:
    def __init__(self, rule_loader):
        self.rules = rule_loader.rules

    def calculate(self, responses):
        score = 0
        max_score = 0
        rule_details = []

        for rule in self.rules:
            rule_id = rule["id"]
            weight = rule["weight"]
            max_score += weight

            triggered = responses.get(rule_id, False)

            if triggered:
                score += weight

            rule_details.append({
                "rule_id": rule_id,
                "triggered": triggered,
                "weight": weight
            })

        final_score = round((score / max_score) * 100, 1) if max_score else 0

        return {
            "final_score": final_score,
            "risk_level": self.get_risk_level(final_score),
            "rule_details": rule_details,
            "category_scores": {}
        }

    def get_risk_level(self, score):
        if score >= 75:
            return {"label": "CRITICAL"}
        elif score >= 50:
            return {"label": "HIGH"}
        elif score >= 25:
            return {"label": "MEDIUM"}
        else:
            return {"label": "LOW"}


class RecommendationEngine:
    def get_recommendations(self, rule_details, responses):
        recs = []

        for rule in rule_details:
            if rule["triggered"]:
                recs.append({"title": f"Fix issue for {rule['rule_id']}"})

        return recs

    general_resources = ["Enable 2FA", "Use strong passwords"]


class PrivacyRiskEngine:
    def __init__(self):
        self.rule_loader = RuleLoader()
        self.calculator = ScoreCalculator(self.rule_loader)
        self.rec_engine = RecommendationEngine()

    def assess(self, user_data):
        responses = user_data.get("responses", {})

        score_result = self.calculator.calculate(responses)

        recommendations = self.rec_engine.get_recommendations(
            score_result["rule_details"], responses
        )

        return {
            "score_result": score_result,
            "recommendations": recommendations
        }

    def reload_rules(self):
        self.rule_loader.rules = self.rule_loader.load_rules()