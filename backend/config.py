import os

class Config:
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", 8000))
    STUDENT_AUTH_TOKEN: str = os.getenv("STUDENT_AUTH_TOKEN", "student-secret")
    FACULTY_AUTH_TOKEN: str = os.getenv("FACULTY_AUTH_TOKEN", "faculty-secret")
    REQUIRE_AUTH: bool = os.getenv("REQUIRE_AUTH", "true").lower() == "true"
    HEARTBEAT_TIMEOUT_SECONDS: float = float(os.getenv("HEARTBEAT_TIMEOUT_SECONDS", 15.0))
    MAX_ALERT_HISTORY: int = int(os.getenv("MAX_ALERT_HISTORY", 100))

config = Config()
