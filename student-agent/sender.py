import asyncio
import json
import logging
import time
from typing import Dict, Optional
import websockets

logger = logging.getLogger("student_agent.sender")


class WebSocketSender:
    """Handles WebSocket connection, registration, auto-reconnection, and async message streaming."""

    def __init__(self, config):
        self.config = config
        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        self.connected = False
        self.queue: asyncio.Queue = asyncio.Queue(maxsize=10)
        self.seq_num = 0

    async def connect_and_run(self, stop_event: asyncio.Event):
        """Main connection loop with automatic exponential backoff retry."""
        retry_delay = 1.0
        max_retry_delay = 15.0

        while not stop_event.is_set():
            try:
                logger.info(f"Connecting to backend WebSocket at {self.config.backend_url}...")
                async with websockets.connect(
                    self.config.backend_url, ping_interval=20, ping_timeout=10
                ) as ws:
                    self.ws = ws
                    self.connected = True
                    retry_delay = 1.0  # Reset delay on success
                    logger.info("Successfully connected to backend.")

                    # 1. Send Registration Payload
                    await self._send_registration()

                    # 2. Process outgoing message queue
                    while not stop_event.is_set() and self.connected:
                        try:
                            message = await asyncio.wait_for(self.queue.get(), timeout=0.5)
                            await self.ws.send(json.dumps(message))
                            self.queue.task_done()
                        except asyncio.TimeoutError:
                            continue
                        except websockets.ConnectionClosed:
                            logger.warning("WebSocket connection closed during send.")
                            self.connected = False
                            break

            except (websockets.WebSocketException, OSError) as e:
                self.connected = False
                self.ws = None
                logger.warning(f"Connection failed: {e}. Retrying in {retry_delay:.1f}s...")
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 1.5, max_retry_delay)
            except Exception as e:
                self.connected = False
                self.ws = None
                logger.error(f"Unexpected error in connection loop: {e}")
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 1.5, max_retry_delay)

        self.connected = False
        self.ws = None

    async def _send_registration(self):
        reg_payload = {
            "type": "register",
            "role": "student",
            "studentId": self.config.student_id,
            "studentName": self.config.student_name,
            "authToken": self.config.auth_token,
        }
        await self.ws.send(json.dumps(reg_payload))
        logger.info(f"Sent registration for studentId: '{self.config.student_id}'")

    def enqueue_frame(self, base64_data: str):
        """Puts a captured JPEG frame payload into the send queue (drops oldest if full)."""
        if not self.connected:
            return

        self.seq_num += 1
        frame_payload = {
            "type": "frame",
            "studentId": self.config.student_id,
            "timestamp": int(time.time() * 1000),
            "seq": self.seq_num,
            "encoding": "jpeg-base64",
            "data": base64_data,
        }

        if self.queue.full():
            try:
                self.queue.get_nowait()  # Drop stale frame if queue is full
            except asyncio.QueueEmpty:
                pass

        try:
            self.queue.put_nowait(frame_payload)
        except asyncio.QueueFull:
            pass

    async def send_alert_immediate(self, alert_payload: Dict):
        """Sends an alert payload immediately if connected, or enqueues it."""
        alert_payload["studentId"] = self.config.student_id
        if self.connected and self.ws:
            try:
                await self.ws.send(json.dumps(alert_payload))
                logger.info(f"Sent immediate alert: {alert_payload.get('detail')}")
                return
            except Exception as e:
                logger.error(f"Failed to send immediate alert: {e}")

        # Enqueue if direct send failed
        try:
            self.queue.put_nowait(alert_payload)
        except asyncio.QueueFull:
            pass
