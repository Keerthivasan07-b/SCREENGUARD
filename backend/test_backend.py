import sys
import json
import time
import asyncio
import logging
from backend.config import config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_backend")

try:
    import websockets
except ImportError:
    logger.error("websockets package required for running tests. Install via: pip install websockets")
    sys.exit(1)


async def run_integration_test():
    ws_url = f"ws://127.0.0.1:{config.PORT}/ws"
    logger.info(f"Connecting to test server at {ws_url}...")

    # Step 1: Connect Faculty client
    async with websockets.connect(ws_url) as faculty_ws:
        faculty_reg = {
            "type": "register",
            "role": "faculty",
            "facultyId": "prof-test",
            "authToken": config.FACULTY_AUTH_TOKEN
        }
        await faculty_ws.send(json.dumps(faculty_reg))

        # Receive initial roster sync
        initial_roster_raw = await faculty_ws.recv()
        initial_roster = json.loads(initial_roster_raw)
        logger.info(f"[PASS] Faculty received initial roster: {initial_roster}")
        assert initial_roster.get("type") == "roster", "Expected roster message"

        # Step 2: Connect Student client
        student_id = "S23-TEST-01"
        student_name = "Test Student"
        async with websockets.connect(ws_url) as student_ws:
            student_reg = {
                "type": "register",
                "role": "student",
                "studentId": student_id,
                "studentName": student_name,
                "authToken": config.STUDENT_AUTH_TOKEN
            }
            await student_ws.send(json.dumps(student_reg))

            # Faculty should receive roster update showing student online
            updated_roster_raw = await faculty_ws.recv()
            updated_roster = json.loads(updated_roster_raw)
            logger.info(f"[PASS] Faculty received updated roster after student connect: {updated_roster}")
            students = updated_roster.get("students", [])
            online_student = next((s for s in students if s["studentId"] == student_id), None)
            assert online_student is not None, "Student not found in roster"
            assert online_student["status"] == "online", "Student status should be online"

            # Step 3: Student sends a live frame
            frame_payload = {
                "type": "frame",
                "studentId": student_id,
                "timestamp": int(time.time() * 1000),
                "encoding": "jpeg-base64",
                "data": "/9j/4AAQSkZJRgABAQEASABIAAD/2wBD..."
            }
            await student_ws.send(json.dumps(frame_payload))

            # Faculty receives the frame
            relayed_frame_raw = await faculty_ws.recv()
            relayed_frame = json.loads(relayed_frame_raw)
            logger.info(f"[PASS] Faculty received frame relay: {relayed_frame.get('studentId')}")
            assert relayed_frame.get("type") == "frame", "Expected frame message"
            assert relayed_frame.get("studentId") == student_id, "Frame studentId mismatch"

            # Step 4: Student sends an alert
            alert_payload = {
                "type": "alert",
                "studentId": student_id,
                "studentName": student_name,
                "timestamp": int(time.time() * 1000),
                "reason": "blacklisted_process",
                "detail": "chrome.exe - ChatGPT detected",
                "severity": "high"
            }
            await student_ws.send(json.dumps(alert_payload))

            # Faculty receives the alert
            relayed_alert_raw = await faculty_ws.recv()
            relayed_alert = json.loads(relayed_alert_raw)
            logger.info(f"[PASS] Faculty received alert relay: {relayed_alert.get('reason')}")
            assert relayed_alert.get("type") == "alert", "Expected alert message"
            assert relayed_alert.get("reason") == "blacklisted_process", "Alert reason mismatch"

            logger.info("Closing student connection...")

        # Step 5: Faculty receives roster update showing student offline
        offline_roster_raw = await faculty_ws.recv()
        offline_roster = json.loads(offline_roster_raw)
        logger.info(f"[PASS] Faculty received offline status roster update: {offline_roster}")
        students = offline_roster.get("students", [])
        offline_student = next((s for s in students if s["studentId"] == student_id), None)
        assert offline_student is not None and offline_student["status"] == "offline", "Student should be offline"

    logger.info("\nALL BACKEND INTEGRATION TESTS PASSED SUCCESSFULLY! 🎉")


if __name__ == "__main__":
    asyncio.run(run_integration_test())
