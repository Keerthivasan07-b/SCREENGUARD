import json
import urllib.request
import logging
try:
    from backend.config import config
except ModuleNotFoundError:
    from config import config

logger = logging.getLogger("supabase_db")

class SupabaseDB:
    def __init__(self):
        self.url = config.SUPABASE_URL
        self.key = config.SUPABASE_KEY

    def _post(self, table_name: str, data: dict) -> bool:
        if not self.url or not self.key:
            logger.warning(f"Supabase credentials not configured. Skipping save to '{table_name}'.")
            return False
        try:
            url = f"{self.url.rstrip('/')}/rest/v1/{table_name}"
            headers = {
                "apikey": self.key,
                "Authorization": f"Bearer {self.key}",
                "Content-Type": "application/json",
                "Prefer": "return=minimal"
            }
            body = json.dumps(data).encode("utf-8")
            req = urllib.request.Request(url, data=body, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=5) as response:
                status = response.getcode()
                return 200 <= status < 300
        except Exception as e:
            logger.error(f"Failed to post to Supabase table '{table_name}': {e}")
            return False

    def save_user(self, email: str, first_name: str = "", last_name: str = "") -> bool:
        """Upsert user profile details in the users table."""
        if not self.url or not self.key:
            return False
        data = {
            "email": email,
            "first_name": first_name,
            "last_name": last_name
        }
        try:
            url = f"{self.url.rstrip('/')}/rest/v1/users"
            headers = {
                "apikey": self.key,
                "Authorization": f"Bearer {self.key}",
                "Content-Type": "application/json",
                "Prefer": "resolution=merge-duplicates"
            }
            body = json.dumps(data).encode("utf-8")
            req = urllib.request.Request(url, data=body, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=5) as response:
                return 200 <= response.getcode() < 300
        except Exception as e:
            logger.error(f"Failed to save user {email} to Supabase: {e}")
            return False

    def save_session(self, user_email: str, classroom: str, session_title: str, ai_gaze: bool, ai_tabs: bool, ai_objects: bool) -> bool:
        """Insert classroom session details in classroom_sessions table."""
        data = {
            "user_email": user_email,
            "classroom": classroom,
            "session_title": session_title,
            "ai_gaze": ai_gaze,
            "ai_tabs": ai_tabs,
            "ai_objects": ai_objects
        }
        return self._post("classroom_sessions", data)

    def save_alert(self, session_title: str, student_name: str, alert_type: str, alert_message: str) -> bool:
        """Insert student anomaly alert logs in alerts table."""
        data = {
            "session_title": session_title,
            "student_name": student_name,
            "alert_type": alert_type,
            "alert_message": alert_message
        }
        return self._post("alerts", data)

supabase_db = SupabaseDB()
