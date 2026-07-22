import logging
from typing import Dict, Any, List
try:
    from backend.config import config
    from backend.student_manager import student_manager
    from backend.supabase_db import supabase_db
except ModuleNotFoundError:
    from config import config
    from student_manager import student_manager
    from supabase_db import supabase_db


logger = logging.getLogger("alert_engine")

class AlertEngine:
    def __init__(self):
        self.alert_history: List[Dict[str, Any]] = []

    async def process_and_relay_alert(self, alert_payload: Dict[str, Any]):
        student_id = alert_payload.get("studentId", "unknown")
        reason = alert_payload.get("reason", "unknown")
        detail = alert_payload.get("detail", "")
        severity = alert_payload.get("severity", "high")

        logger.warning(f"ALERT received from {student_id} [{severity.upper()}]: {reason} - {detail}")

        # Add to in-memory history
        self.alert_history.append(alert_payload)
        if len(self.alert_history) > config.MAX_ALERT_HISTORY:
            self.alert_history.pop(0)

        # Archive alert event in Supabase DB asynchronously
        try:
            supabase_db.save_alert(
                session_title=alert_payload.get("sessionTitle", "Live Monitoring Session"),
                student_name=student_id,
                alert_type=reason,
                alert_message=detail
            )
        except Exception as db_err:
            logger.error(f"Error saving alert to Supabase: {db_err}")

        # Relay immediately to all faculty dashboards
        await student_manager.broadcast_to_faculty(alert_payload)

    def get_recent_alerts(self, limit: int = 50) -> List[Dict[str, Any]]:
        return self.alert_history[-limit:]

alert_engine = AlertEngine()
