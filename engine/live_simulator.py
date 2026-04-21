"""
engine/live_simulator.py
-------------------------
NEW MODULE — Upgrade Feature #1: Live Data Simulation

Simulates real-world privacy risk events that occur over time:
  - Permission changes on device
  - Password exposure alerts
  - App activity anomalies
  - Network events (public WiFi connect, VPN drop)
  - Breach notifications

Events are loaded from a configurable JSON config.
Each event has a risk_delta (+ or -) and an affected rule ID.
The simulator generates realistic time-stamped event streams.

SE Model: Evolutionary (new events added via JSON).
Design Pattern: Observer/Event pattern.
"""

import json
import os
import random
import datetime
from typing import Dict, List, Optional

EVENTS_CONFIG_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'live_events.json')


class LiveEventSimulator:
    """
    Generates simulated real-time privacy risk events.
    Each event modifies the live risk environment of a user session.
    """

    def __init__(self, events_path: str = EVENTS_CONFIG_PATH):
        self.events_path = events_path
        self._events_config: Optional[Dict] = None
        self._load_or_create()

    def _load_or_create(self):
        if not os.path.exists(self.events_path):
            self._create_default_events()
        with open(self.events_path, 'r') as f:
            self._events_config = json.load(f)

    def _create_default_events(self):
        """Create the default live events config if it doesn't exist."""
        config = {
            "version": "1.0.0",
            "event_types": {
                "password_exposure": {
                    "label": "Password Exposure Alert",
                    "icon": "🔓",
                    "description": "One of your passwords was found in a new data breach",
                    "risk_delta": +18,
                    "affected_rule": "AS01",
                    "severity": "critical",
                    "category": "account_security",
                    "mitigatable": True,
                    "mitigation": "Change the affected password immediately and enable 2FA"
                },
                "public_wifi_connect": {
                    "label": "Public WiFi Connected",
                    "icon": "📡",
                    "description": "Device connected to an unsecured public network",
                    "risk_delta": +12,
                    "affected_rule": "NS01",
                    "severity": "high",
                    "category": "network_security",
                    "mitigatable": True,
                    "mitigation": "Activate VPN immediately"
                },
                "vpn_activated": {
                    "label": "VPN Activated",
                    "icon": "🛡️",
                    "description": "VPN connection established — traffic encrypted",
                    "risk_delta": -8,
                    "affected_rule": "NS02",
                    "severity": "positive",
                    "category": "network_security",
                    "mitigatable": False,
                    "mitigation": ""
                },
                "app_permission_granted": {
                    "label": "Sensitive Permission Granted",
                    "icon": "📲",
                    "description": "App granted access to Location + Contacts",
                    "risk_delta": +10,
                    "affected_rule": "DE04",
                    "severity": "medium",
                    "category": "data_exposure",
                    "mitigatable": True,
                    "mitigation": "Review and revoke unnecessary app permissions"
                },
                "security_update_installed": {
                    "label": "Security Update Installed",
                    "icon": "✅",
                    "description": "OS security patch applied successfully",
                    "risk_delta": -10,
                    "affected_rule": "DS02",
                    "severity": "positive",
                    "category": "device_security",
                    "mitigatable": False,
                    "mitigation": ""
                },
                "2fa_disabled": {
                    "label": "2FA Disabled on Account",
                    "icon": "⚠️",
                    "description": "Two-factor authentication was turned off on a major account",
                    "risk_delta": +15,
                    "affected_rule": "AS02",
                    "severity": "high",
                    "category": "account_security",
                    "mitigatable": True,
                    "mitigation": "Re-enable 2FA on all critical accounts immediately"
                },
                "social_media_made_public": {
                    "label": "Social Profile Made Public",
                    "icon": "👁️",
                    "description": "Your social media profile privacy was changed to public",
                    "risk_delta": +14,
                    "affected_rule": "DE01",
                    "severity": "high",
                    "category": "data_exposure",
                    "mitigatable": True,
                    "mitigation": "Revert profile to private or friends-only"
                },
                "phishing_attempt_detected": {
                    "label": "Phishing Attempt Detected",
                    "icon": "🎣",
                    "description": "A suspicious phishing email was delivered to your inbox",
                    "risk_delta": +8,
                    "affected_rule": "BH01",
                    "severity": "medium",
                    "category": "behavioral",
                    "mitigatable": True,
                    "mitigation": "Do not click any links. Report and delete the email."
                },
                "password_manager_enabled": {
                    "label": "Password Manager Enabled",
                    "icon": "🗝️",
                    "description": "User activated a password manager",
                    "risk_delta": -8,
                    "affected_rule": "AS04",
                    "severity": "positive",
                    "category": "account_security",
                    "mitigatable": False,
                    "mitigation": ""
                },
                "device_screen_lock_disabled": {
                    "label": "Screen Lock Disabled",
                    "icon": "🔓",
                    "description": "Device screen lock was turned off",
                    "risk_delta": +12,
                    "affected_rule": "DS04",
                    "severity": "high",
                    "category": "device_security",
                    "mitigatable": True,
                    "mitigation": "Re-enable screen lock with PIN or biometrics"
                }
            }
        }
        os.makedirs(os.path.dirname(self.events_path), exist_ok=True)
        with open(self.events_path, 'w') as f:
            json.dump(config, f, indent=2)
        self._events_config = config

    def generate_random_events(self, count: int = 3, seed: Optional[int] = None) -> List[Dict]:
        """Generate a list of random simulated events for demo purposes."""
        if seed is not None:
            random.seed(seed)

        event_types = list(self._events_config['event_types'].items())
        selected = random.choices(event_types, k=count)

        events = []
        base_time = datetime.datetime.now()
        for i, (etype_id, etype) in enumerate(selected):
            offset_minutes = random.randint(1, 120) * i
            event_time = base_time - datetime.timedelta(minutes=offset_minutes)
            events.append({
                'event_id': f"EVT_{etype_id.upper()}_{i:03d}",
                'type': etype_id,
                'label': etype['label'],
                'icon': etype['icon'],
                'description': etype['description'],
                'risk_delta': etype['risk_delta'],
                'affected_rule': etype['affected_rule'],
                'severity': etype['severity'],
                'category': etype['category'],
                'mitigatable': etype['mitigatable'],
                'mitigation': etype['mitigation'],
                'simulated_at': event_time.isoformat(),
                'simulated': True
            })

        events.sort(key=lambda e: e['simulated_at'])
        return events

    def apply_events_to_score(self, base_score: float, events: List[Dict]) -> Dict:
        """Apply a list of events to a base score, tracking each step."""
        timeline = []
        current_score = base_score

        for event in events:
            prev_score = current_score
            current_score = max(0, min(100, current_score + event['risk_delta']))
            timeline.append({
                **event,
                'score_before': round(prev_score, 1),
                'score_after':  round(current_score, 1),
                'delta_applied': event['risk_delta']
            })

        total_delta = round(current_score - base_score, 1)
        return {
            'base_score':    round(base_score, 1),
            'live_score':    round(current_score, 1),
            'total_delta':   total_delta,
            'timeline':      timeline,
            'events_count':  len(events),
            'risk_events':   sum(1 for e in events if e['risk_delta'] > 0),
            'positive_events': sum(1 for e in events if e['risk_delta'] < 0)
        }

    def get_all_event_types(self) -> Dict:
        return self._events_config['event_types']
