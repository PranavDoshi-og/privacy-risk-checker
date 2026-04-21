import json
import os

BASE_DIR = os.path.dirname(os.path.dirname(__file__))

class SessionStore:
    def __init__(self):
        self.session_dir = os.path.join(BASE_DIR, 'data', 'sessions')
        os.makedirs(self.session_dir, exist_ok=True)

    def save_session(self, data):
        file_path = os.path.join(self.session_dir, "session.json")
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2)
        return "session_saved"


class AuditLogger:
    def __init__(self):
        self.log_file = os.path.join(BASE_DIR, 'data', 'audit_log.json')

    def log(self, session_id, score, risk_label, issues_count):
        entry = {
            "session_id": session_id,
            "score": score,
            "risk": risk_label,
            "issues": issues_count
        }

        logs = []
        if os.path.exists(self.log_file):
            with open(self.log_file, 'r') as f:
                try:
                    logs = json.load(f)
                except:
                    logs = []

        logs.append(entry)

        with open(self.log_file, 'w') as f:
            json.dump(logs, f, indent=2)