import os
from pathlib import Path

# Load .env file if present
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                os.environ.setdefault(key.strip(), val.strip())

class Config:
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", 8000))
    STUDENT_AUTH_TOKEN: str = os.getenv("STUDENT_AUTH_TOKEN", "student-secret")
    FACULTY_AUTH_TOKEN: str = os.getenv("FACULTY_AUTH_TOKEN", "faculty-secret")
    REQUIRE_AUTH: bool = os.getenv("REQUIRE_AUTH", "true").lower() == "true"
    HEARTBEAT_TIMEOUT_SECONDS: float = float(os.getenv("HEARTBEAT_TIMEOUT_SECONDS", 15.0))
    MAX_ALERT_HISTORY: int = int(os.getenv("MAX_ALERT_HISTORY", 100))

    # Google OAuth
    GOOGLE_CLIENT_ID: str = os.getenv("GOOGLE_CLIENT_ID", "")
    GOOGLE_SECRET_KEY: str = os.getenv("GOOGLE_SECRET_KEY", "")

    # Supabase
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    SUPABASE_KEY: str = os.getenv("SUPABASE_KEY", "")

config = Config()

