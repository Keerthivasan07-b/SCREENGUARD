import json
import logging
from fastapi import WebSocket, WebSocketDisconnect
try:
    from backend.config import config
    from backend.student_manager import student_manager
    from backend.alerts import alert_engine
except ModuleNotFoundError:
    from config import config
    from student_manager import student_manager
    from alerts import alert_engine


logger = logging.getLogger("websocket_handler")

async def handle_websocket(websocket: WebSocket):
    await websocket.accept()
    role = None
    student_id = None

    try:
        # First message must be registration handshake
        init_data_raw = await websocket.receive_text()
        try:
            init_data = json.loads(init_data_raw)
        except Exception:
            await websocket.close(code=1008, reason="Invalid JSON payload")
            return

        msg_type = init_data.get("type")
        if msg_type != "register":
            await websocket.close(code=1008, reason="First message must be registration")
            return

        role = init_data.get("role")
        auth_token = init_data.get("authToken")

        if role == "student":
            if config.REQUIRE_AUTH and auth_token != config.STUDENT_AUTH_TOKEN:
                logger.warning(f"Unauthorized student registration attempt from {websocket.client}")
                await websocket.close(code=1008, reason="Invalid student auth token")
                return

            student_id = init_data.get("studentId")
            student_name = init_data.get("studentName", student_id or "Unknown Student")

            if not student_id:
                await websocket.close(code=1008, reason="Missing studentId")
                return

            await student_manager.register_student(student_id, student_name, websocket)
            logger.info(f"Student WebSocket loop started for {student_id}")

            # Student message handling loop
            while True:
                data_raw = await websocket.receive_text()
                data = json.loads(data_raw)
                m_type = data.get("type")

                if m_type == "frame":
                    data["studentId"] = student_id
                    student_manager.update_frame(student_id, data)
                elif m_type == "alert":
                    data["studentId"] = student_id
                    if "studentName" not in data:
                        data["studentName"] = student_name
                    await alert_engine.process_and_relay_alert(data)
                elif m_type == "ping":
                    student_manager.update_ping(student_id)
                else:
                    logger.debug(f"Unhandled student message type '{m_type}' from {student_id}")

        elif role == "faculty":
            if config.REQUIRE_AUTH and auth_token != config.FACULTY_AUTH_TOKEN:
                logger.warning(f"Unauthorized faculty registration attempt from {websocket.client}")
                await websocket.close(code=1008, reason="Invalid faculty auth token")
                return

            await student_manager.register_faculty(websocket)
            logger.info("Faculty WebSocket loop started")

            # Faculty message handling loop
            while True:
                data_raw = await websocket.receive_text()
                data = json.loads(data_raw)
                m_type = data.get("type")
                if m_type == "ping":
                    await websocket.send_json({"type": "pong"})

        else:
            await websocket.close(code=1008, reason=f"Unsupported role: {role}")
            return

    except WebSocketDisconnect:
        logger.info(f"WebSocket connection closed (role={role}, student_id={student_id})")
    except Exception as e:
        logger.error(f"WebSocket exception (role={role}, student_id={student_id}): {e}")
    finally:
        if role == "student" and student_id:
            await student_manager.unregister_student(student_id)
        elif role == "faculty":
            await student_manager.unregister_faculty(websocket)
