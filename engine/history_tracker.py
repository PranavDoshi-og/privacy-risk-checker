"""
engine/history_tracker.py
--------------------------
NEW MODULE — Upgrade Features #2, #3:
  - User History Tracking
  - Risk Trend Analysis

Maintains per-user assessment history keyed by name/email.
Computes score deltas, improvement/degradation labels, and trend direction.
All storage is JSON-backed — no database required.

SE Model: Evolutionary (grows as users complete multiple assessments).
Design Pattern: Repository pattern for user history records.
"""

import json
import os
import datetime
from typing import Dict, List, Optional, Tuple

HISTORY_FILE = os.path.join(os.path.dirname(__file__), '..', 'data', 'user_history.json')


class UserHistoryTracker:
    """
    Stores and retrieves per-user assessment history.
    Computes trends, deltas, and progress labels.
    """

    def __init__(self, history_file: str = HISTORY_FILE):
        self.history_file = history_file
        self._ensure_file()

    def _ensure_file(self):
        if not os.path.exists(self.history_file):
            os.makedirs(os.path.dirname(self.history_file), exist_ok=True)
            self._write({})

    def record_assessment(self, user_key: str, score: float, risk_label: str,
                          category_scores: Dict, scenario_id: Optional[str] = None) -> Dict:
        """
        Save a new assessment entry for a user.
        Returns the comparison result (delta vs previous).
        """
        history = self._read()
        if user_key not in history:
            history[user_key] = []

        entry = {
            'timestamp': datetime.datetime.now().isoformat(),
            'score': round(score, 1),
            'risk_label': risk_label,
            'scenario': scenario_id,
            'category_scores': {
                cat_id: round(cat_data.get('normalized', 0), 1)
                for cat_id, cat_data in category_scores.items()
            }
        }

        history[user_key].append(entry)
        # Keep last 50 entries per user
        history[user_key] = history[user_key][-50:]
        self._write(history)

        comparison = self.compare_with_previous(user_key)
        return comparison

    def compare_with_previous(self, user_key: str) -> Dict:
        """Compare latest assessment against the previous one."""
        history = self._read()
        entries = history.get(user_key, [])

        if len(entries) < 2:
            return {
                'has_previous': False,
                'message': 'First assessment — no prior data to compare.',
                'delta': None,
                'category_deltas': {}
            }

        current  = entries[-1]
        previous = entries[-2]

        delta = round(current['score'] - previous['score'], 1)
        cat_deltas = {}
        for cat_id in current['category_scores']:
            prev_val = previous['category_scores'].get(cat_id, 0)
            curr_val = current['category_scores'].get(cat_id, 0)
            cat_deltas[cat_id] = round(curr_val - prev_val, 1)

        direction, label, emoji = self._interpret_delta(delta)

        return {
            'has_previous': True,
            'current_score': current['score'],
            'previous_score': previous['score'],
            'delta': delta,
            'direction': direction,
            'label': label,
            'emoji': emoji,
            'previous_risk_label': previous['risk_label'],
            'current_risk_label':  current['risk_label'],
            'category_deltas': cat_deltas,
            'previous_timestamp': previous['timestamp'],
            'days_since_last': self._days_between(previous['timestamp'], current['timestamp'])
        }

    def _interpret_delta(self, delta: float) -> Tuple[str, str, str]:
        if delta <= -10:  return ('improved',    'Significant Improvement', '📈')
        if delta <= -3:   return ('improved',    'Slight Improvement',      '↗️')
        if delta < 3:     return ('stable',      'No Significant Change',   '➡️')
        if delta < 10:    return ('degraded',    'Slight Degradation',      '↘️')
        return ('degraded', 'Significant Degradation', '📉')

    def _days_between(self, ts1: str, ts2: str) -> int:
        try:
            d1 = datetime.datetime.fromisoformat(ts1)
            d2 = datetime.datetime.fromisoformat(ts2)
            return abs((d2 - d1).days)
        except Exception:
            return 0

    def get_history(self, user_key: str) -> List[Dict]:
        history = self._read()
        return history.get(user_key, [])

    def get_all_users(self) -> List[str]:
        return list(self._read().keys())

    def _read(self) -> Dict:
        try:
            with open(self.history_file, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return {}

    def _write(self, data: Dict):
        with open(self.history_file, 'w') as f:
            json.dump(data, f, indent=2)


class TrendAnalyzer:
    """
    Analyses risk trends over time for a given user.
    Produces textual + numeric trend indicators.
    """

    def __init__(self, history_tracker: UserHistoryTracker):
        self.tracker = history_tracker

    def analyze(self, user_key: str) -> Dict:
        """Full trend analysis for a user — returns structured trend report."""
        entries = self.tracker.get_history(user_key)

        if len(entries) < 2:
            return {
                'has_trend': False,
                'message': 'Need at least 2 assessments for trend analysis.',
                'entries_count': len(entries)
            }

        scores = [e['score'] for e in entries]
        timestamps = [e['timestamp'] for e in entries]

        trend_direction = self._compute_trend(scores)
        moving_avg = self._moving_average(scores, window=3)
        peak  = max(scores)
        trough = min(scores)
        latest = scores[-1]
        first  = scores[0]
        overall_delta = round(latest - first, 1)

        # Per-category trend
        cat_trends = {}
        if entries and 'category_scores' in entries[-1]:
            for cat_id in entries[-1]['category_scores']:
                cat_scores = [e['category_scores'].get(cat_id, 0) for e in entries]
                cat_trends[cat_id] = {
                    'direction': self._compute_trend(cat_scores),
                    'latest': round(cat_scores[-1], 1),
                    'delta': round(cat_scores[-1] - cat_scores[0], 1)
                }

        # Streak computation
        improving_streak, degrading_streak = self._compute_streaks(scores)

        return {
            'has_trend': True,
            'entries_count': len(entries),
            'scores': scores,
            'timestamps': timestamps,
            'trend_direction': trend_direction,
            'trend_label': self._trend_label(trend_direction),
            'overall_delta': overall_delta,
            'peak_score': round(peak, 1),
            'trough_score': round(trough, 1),
            'latest_score': round(latest, 1),
            'first_score': round(first, 1),
            'moving_average_3': moving_avg,
            'category_trends': cat_trends,
            'improving_streak': improving_streak,
            'degrading_streak': degrading_streak,
            'summary': self._build_summary(trend_direction, overall_delta, improving_streak, degrading_streak, len(entries))
        }

    def _compute_trend(self, scores: List[float]) -> str:
        if len(scores) < 2:
            return 'stable'
        # Simple linear regression slope
        n = len(scores)
        x_mean = (n - 1) / 2
        y_mean = sum(scores) / n
        numerator   = sum((i - x_mean) * (scores[i] - y_mean) for i in range(n))
        denominator = sum((i - x_mean) ** 2 for i in range(n))
        slope = numerator / denominator if denominator != 0 else 0

        if slope > 1.5:  return 'worsening'
        if slope > 0.3:  return 'slightly_worsening'
        if slope < -1.5: return 'improving'
        if slope < -0.3: return 'slightly_improving'
        return 'stable'

    def _trend_label(self, direction: str) -> str:
        labels = {
            'worsening':           '📉 Risk Worsening',
            'slightly_worsening':  '↘️ Slightly Worsening',
            'stable':              '➡️ Stable',
            'slightly_improving':  '↗️ Slightly Improving',
            'improving':           '📈 Improving'
        }
        return labels.get(direction, 'Unknown')

    def _moving_average(self, scores: List[float], window: int = 3) -> List[float]:
        result = []
        for i in range(len(scores)):
            start = max(0, i - window + 1)
            avg = sum(scores[start:i+1]) / (i - start + 1)
            result.append(round(avg, 1))
        return result

    def _compute_streaks(self, scores: List[float]) -> Tuple[int, int]:
        if len(scores) < 2:
            return 0, 0
        improving = 0
        degrading = 0
        for i in range(len(scores)-1, 0, -1):
            if scores[i] < scores[i-1]:
                improving += 1
            else:
                break
        for i in range(len(scores)-1, 0, -1):
            if scores[i] > scores[i-1]:
                degrading += 1
            else:
                break
        return improving, degrading

    def _build_summary(self, direction: str, delta: float, imp_streak: int,
                       deg_streak: int, count: int) -> str:
        parts = [f"Across {count} assessments: "]
        if delta < 0:
            parts.append(f"overall risk improved by {abs(delta)} points.")
        elif delta > 0:
            parts.append(f"overall risk increased by {delta} points.")
        else:
            parts.append("risk has remained stable.")
        if imp_streak >= 2:
            parts.append(f" Currently on a {imp_streak}-assessment improvement streak.")
        if deg_streak >= 2:
            parts.append(f" Warning: {deg_streak} consecutive assessments show increased risk.")
        return ' '.join(parts)
