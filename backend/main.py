import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
try:
    from backend.config import config
    from backend.websocket import handle_websocket
    from backend.student_manager import student_manager
    from backend.alerts import alert_engine
    from backend.supabase_db import supabase_db
except ModuleNotFoundError:
    from config import config
    from websocket import handle_websocket
    from student_manager import student_manager
    from alerts import alert_engine
    from supabase_db import supabase_db


# Configure logging format
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("backend_main")

async def heartbeat_loop():
    """Periodic background task to mark inactive students as offline."""
    while True:
        try:
            await asyncio.sleep(5.0)
            await student_manager.check_heartbeats(config.HEARTBEAT_TIMEOUT_SECONDS)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Error in heartbeat loop: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("SmartClassMonitor Backend starting up...")
    heartbeat_task = asyncio.create_task(heartbeat_loop())
    yield
    logger.info("SmartClassMonitor Backend shutting down...")
    heartbeat_task.cancel()

app = FastAPI(
    title="SmartClassMonitor Backend",
    description="Real-time relay server for student screen monitoring and alert system",
    version="1.0.0",
    lifespan=lifespan
)

# Enable CORS for frontend dashboard (Vite / React)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

import json
import urllib.request
from pydantic import BaseModel

class GoogleAuthPayload(BaseModel):
    credential: str

@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "service": "SmartClassMonitor Backend",
        "connected_students": len(student_manager.student_sockets),
        "connected_faculty": len(student_manager.faculty_sockets)
    }

@app.get("/api/auth/config")
async def get_auth_config():
    return {
        "google_client_id": config.GOOGLE_CLIENT_ID
    }

@app.post("/api/auth/google")
async def verify_google_token(payload: GoogleAuthPayload):
    """Verify Google ID token via Google OAuth2 tokeninfo API and store details in Supabase."""
    try:
        url = f"https://oauth2.googleapis.com/tokeninfo?id_token={payload.credential}"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode('utf-8'))
            
            # Verify client ID matches
            if config.GOOGLE_CLIENT_ID and data.get("aud") != config.GOOGLE_CLIENT_ID:
                return {"success": False, "error": "Invalid client ID recipient"}
            
            email = data.get("email")
            name = data.get("name", "")
            first_name = name.split(" ")[0] if name else ""
            last_name = " ".join(name.split(" ")[1:]) if name and len(name.split(" ")) > 1 else ""

            # Save user profiles to database
            try:
                supabase_db.save_user(email=email, first_name=first_name, last_name=last_name)
            except Exception as db_err:
                logger.error(f"Error saving google auth user to Supabase: {db_err}")

            return {
                "success": True,
                "user": {
                    "email": email,
                    "name": name,
                    "picture": data.get("picture"),
                    "email_verified": data.get("email_verified")
                }
            }
    except Exception as e:
        logger.error(f"Google token verification failed: {e}")
        return {"success": False, "error": f"Token verification failed: {str(e)}"}

class RegisterPayload(BaseModel):
    email: str
    first_name: str
    last_name: str

class SessionPayload(BaseModel):
    user_email: str
    classroom: str
    session_title: str
    ai_gaze: bool
    ai_tabs: bool
    ai_objects: bool

@app.post("/api/auth/register")
async def register_user(payload: RegisterPayload):
    """Register standard form signups and archive in database."""
    success = supabase_db.save_user(
        email=payload.email,
        first_name=payload.first_name,
        last_name=payload.last_name
    )
    return {"success": success}

@app.post("/api/sessions")
async def create_session(payload: SessionPayload):
    """Archive initialized classroom monitoring sessions in database."""
    success = supabase_db.save_session(
        user_email=payload.user_email,
        classroom=payload.classroom,
        session_title=payload.session_title,
        ai_gaze=payload.ai_gaze,
        ai_tabs=payload.ai_tabs,
        ai_objects=payload.ai_objects
    )
    return {"success": success}

@app.get("/api/students")
async def get_students():
    return student_manager.get_roster_payload()

@app.get("/api/alerts")
async def get_alerts():
    return {"alerts": alert_engine.get_recent_alerts()}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await handle_websocket(websocket)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=config.HOST, port=config.PORT)

