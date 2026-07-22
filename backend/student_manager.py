import time
import asyncio
import logging
from typing import Dict, Set, Optional, Any
from fastapi import WebSocket, WebSocketDisconnect
try:
    from backend.models import RosterMessage, StudentStatus
except ModuleNotFoundError:
    from models import RosterMessage, StudentStatus


logger = logging.getLogger("student_manager")

class StudentManager:
    def __init__(self):
        # Maps studentId -> WebSocket
        self.student_sockets: Dict[str, WebSocket] = {}
        # Set of active faculty WebSockets
        self.faculty_sockets: Set[WebSocket] = set()
        # Maps studentId -> {"studentName": str, "status": str, "last_seen": float}
        self.students: Dict[str, Dict[str, Any]] = {}
        # Maps studentId -> dict (latest frame JSON payload)
        self.latest_frames: Dict[str, Dict[str, Any]] = {}
        self._lock = asyncio.Lock()

    async def register_student(self, student_id: str, student_name: str, websocket: WebSocket):
        async with self._lock:
            self.student_sockets[student_id] = websocket
            self.students[student_id] = {
                "studentName": student_name,
                "status": "online",
                "last_seen": time.time()
            }
        logger.info(f"Student registered: {student_id} ({student_name})")
        await self.broadcast_roster()

    async def register_faculty(self, websocket: WebSocket):
        async with self._lock:
            self.faculty_sockets.add(websocket)
        logger.info(f"Faculty registered. Total faculty connections: {len(self.faculty_sockets)}")
        
        # Send current roster immediately
        roster = self.get_roster_payload()
        try:
            await websocket.send_json(roster)
        except Exception as e:
            logger.warning(f"Error sending roster to new faculty connection: {e}")

        # Send latest cached frames for all online/known students
        for student_id, frame_payload in list(self.latest_frames.items()):
            try:
                await websocket.send_json(frame_payload)
            except Exception as e:
                logger.warning(f"Error sending initial frame to faculty: {e}")

    async def unregister_student(self, student_id: str):
        async with self._lock:
            if student_id in self.student_sockets:
                del self.student_sockets[student_id]
            if student_id in self.students:
                self.students[student_id]["status"] = "offline"
        logger.info(f"Student disconnected: {student_id}")
        await self.broadcast_roster()

    async def unregister_faculty(self, websocket: WebSocket):
        async with self._lock:
            self.faculty_sockets.discard(websocket)
        logger.info(f"Faculty disconnected. Remaining faculty: {len(self.faculty_sockets)}")

    def update_ping(self, student_id: str):
        if student_id in self.students:
            self.students[student_id]["last_seen"] = time.time()
            if self.students[student_id]["status"] == "offline":
                self.students[student_id]["status"] = "online"
                asyncio.create_task(self.broadcast_roster())

    def update_frame(self, student_id: str, frame_payload: Dict[str, Any]):
        self.latest_frames[student_id] = frame_payload
        if student_id in self.students:
            self.students[student_id]["last_seen"] = time.time()
            if self.students[student_id]["status"] == "offline":
                self.students[student_id]["status"] = "online"
                asyncio.create_task(self.broadcast_roster())
        # Broadcast frame to all faculty dashboards asynchronously
        asyncio.create_task(self.broadcast_to_faculty(frame_payload))

    def get_roster_payload(self) -> Dict[str, Any]:
        students_list = []
        for s_id, info in self.students.items():
            students_list.append({
                "studentId": s_id,
                "studentName": info["studentName"],
                "status": info["status"]
            })
        return {
            "type": "roster",
            "students": students_list
        }

    async def broadcast_roster(self):
        roster = self.get_roster_payload()
        await self.broadcast_to_faculty(roster)

    async def broadcast_to_faculty(self, message: Dict[str, Any]):
        if not self.faculty_sockets:
            return

        dead_sockets = set()
        # Non-blocking broadcast across faculty sockets
        for socket in list(self.faculty_sockets):
            try:
                await socket.send_json(message)
            except Exception as e:
                logger.warning(f"Failed to send message to faculty socket: {e}")
                dead_sockets.add(socket)

        if dead_sockets:
            async with self._lock:
                for socket in dead_sockets:
                    self.faculty_sockets.discard(socket)

    async def check_heartbeats(self, timeout_seconds: float = 15.0):
        now = time.time()
        status_changed = False
        for s_id, info in self.students.items():
            if info["status"] == "online" and (now - info["last_seen"]) > timeout_seconds:
                info["status"] = "offline"
                status_changed = True
                logger.warning(f"Student {s_id} marked offline due to heartbeat timeout.")

        if status_changed:
            await self.broadcast_roster()

student_manager = StudentManager()
