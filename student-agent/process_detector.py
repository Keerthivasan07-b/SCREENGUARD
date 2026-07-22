import logging
import time
from typing import Dict, List, Optional
import psutil

logger = logging.getLogger("student_agent.process_detector")


class ProcessDetector:
    """Detects blacklisted processes and active window keyword violations."""

    def __init__(
        self,
        blacklist_processes: Optional[List[str]] = None,
        blacklist_keywords: Optional[List[str]] = None,
        alert_cooldown_seconds: float = 5.0,
    ):
        self.blacklist_processes = [
            p.lower() for p in (blacklist_processes or ["discord.exe", "telegram.exe", "whatsapp.exe"])
        ]
        self.blacklist_keywords = [
            k.lower() for k in (blacklist_keywords or ["chatgpt", "gemini", "claude", "youtube"])
        ]
        self.alert_cooldown_seconds = alert_cooldown_seconds
        self.last_alerts: Dict[str, float] = {}

    def _should_fire_alert(self, key: str) -> bool:
        now = time.time()
        last_time = self.last_alerts.get(key, 0.0)
        if now - last_time >= self.alert_cooldown_seconds:
            self.last_alerts[key] = now
            return True
        return False

    def scan(self, active_window_title: str) -> Optional[Dict]:
        """
        Scans active window title and running process list against blacklists.
        Returns alert payload dict if violation is found, otherwise None.
        """
        # 1. Check Active Window Title against keywords
        if active_window_title:
            window_title_lower = active_window_title.lower()
            for kw in self.blacklist_keywords:
                if kw in window_title_lower:
                    alert_key = f"keyword_{kw}"
                    if self._should_fire_alert(alert_key):
                        return {
                            "type": "alert",
                            "reason": "blacklisted_process",
                            "detail": f"Active window title contains blacklisted keyword '{kw}': '{active_window_title}'",
                            "severity": "high",
                            "timestamp": int(time.time() * 1000),
                        }

        # 2. Check Running Processes against blacklisted process names
        try:
            for proc in psutil.process_iter(["name"]):
                try:
                    pname = proc.info.get("name")
                    if pname:
                        pname_lower = pname.lower()
                        for b_proc in self.blacklist_processes:
                            if b_proc in pname_lower or pname_lower == b_proc:
                                alert_key = f"process_{b_proc}"
                                if self._should_fire_alert(alert_key):
                                    return {
                                        "type": "alert",
                                        "reason": "blacklisted_process",
                                        "detail": f"Blacklisted application running: '{pname}'",
                                        "severity": "high",
                                        "timestamp": int(time.time() * 1000),
                                    }
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
        except Exception as e:
            logger.error(f"Error iterating process list: {e}")

        return None
