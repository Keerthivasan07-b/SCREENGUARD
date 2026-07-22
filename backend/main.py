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
except ModuleNotFoundError:
    from config import config
    from websocket import handle_websocket
    from student_manager import student_manager
    from alerts import alert_engine


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

@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "service": "SmartClassMonitor Backend",
        "connected_students": len(student_manager.student_sockets),
        "connected_faculty": len(student_manager.faculty_sockets)
    }

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

