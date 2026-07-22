import asyncio
import logging
import signal
import sys
import time
from config import AgentConfig
from capture import ScreenCapturer
from compress import FrameCompressor
from monitor import WindowMonitor
from process_detector import ProcessDetector
from sender import WebSocketSender

# Setup Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("student_agent")


async def frame_capture_loop(
    config: AgentConfig,
    capturer: ScreenCapturer,
    compressor: FrameCompressor,
    sender: WebSocketSender,
    stop_event: asyncio.Event,
):
    """Loop capturing desktop frames at target FPS and pushing to WebSocket queue."""
    capturer.start()
    interval = config.capture_interval
    logger.info(f"Starting frame capture loop (Target FPS: {config.fps:.1f}, Interval: {interval:.3f}s)")

    frames_sent = 0
    start_time = time.time()

    try:
        while not stop_event.is_set():
            loop_start = time.time()

            frame_bgr = capturer.capture_frame()
            if frame_bgr is not None:
                compressed_res = compressor.compress(frame_bgr)
                if compressed_res:
                    b64_str, byte_size = compressed_res
                    sender.enqueue_frame(b64_str)
                    frames_sent += 1

                    # Log performance every 100 frames
                    if frames_sent % 100 == 0:
                        elapsed = time.time() - start_time
                        actual_fps = frames_sent / elapsed if elapsed > 0 else 0
                        logger.info(
                            f"Stats: {frames_sent} frames sent ({actual_fps:.1f} FPS, last frame ~{byte_size / 1024:.1f} KB)"
                        )

            # Sleep to match target FPS interval
            elapsed_work = time.time() - loop_start
            sleep_time = max(0.005, interval - elapsed_work)
            await asyncio.sleep(sleep_time)
    finally:
        capturer.stop()
        logger.info("Frame capture loop stopped.")


async def blacklist_monitor_loop(
    config: AgentConfig,
    window_monitor: WindowMonitor,
    detector: ProcessDetector,
    sender: WebSocketSender,
    stop_event: asyncio.Event,
):
    """Loop polling active window titles and processes for policy violations."""
    logger.info(f"Starting process/window blacklist monitor (Interval: {config.monitor_interval}s)")

    while not stop_event.is_set():
        try:
            active_title = window_monitor.get_active_window_title()
            alert_payload = detector.scan(active_title)

            if alert_payload:
                logger.warning(
                    f"⚠ POLICY VIOLATION DETECTED [{alert_payload.get('reason')}]: {alert_payload.get('detail')}"
                )
                await sender.send_alert_immediate(alert_payload)

        except Exception as e:
            logger.error(f"Error in blacklist monitor loop: {e}")

        await asyncio.sleep(config.monitor_interval)

    logger.info("Blacklist monitor loop stopped.")


async def main():
    config = AgentConfig.parse_cli_args()

    logger.info("=" * 60)
    logger.info(f"Starting SmartClassMonitor Student Agent")
    logger.info(f"Student ID:     {config.student_id}")
    logger.info(f"Student Name:   {config.student_name}")
    logger.info(f"Backend URL:    {config.backend_url}")
    logger.info(f"Target Frame:   {config.target_width}px width @ {config.fps} FPS")
    logger.info("=" * 60)

    capturer = ScreenCapturer()
    compressor = FrameCompressor(
        target_width=config.target_width, jpeg_quality=config.jpeg_quality
    )
    window_monitor = WindowMonitor()
    detector = ProcessDetector(
        blacklist_processes=config.blacklist_processes,
        blacklist_keywords=config.blacklist_keywords,
    )
    sender = WebSocketSender(config)

    stop_event = asyncio.Event()

    # Handle signal interrupts gracefully
    def _shutdown_signal_handler():
        logger.info("Shutdown signal received. Stopping tasks...")
        stop_event.set()

    loop = asyncio.get_running_loop()
    if sys.platform != "win32":
        for s in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(s, _shutdown_signal_handler)

    tasks = [
        asyncio.create_task(sender.connect_and_run(stop_event)),
        asyncio.create_task(
            frame_capture_loop(config, capturer, compressor, sender, stop_event)
        ),
        asyncio.create_task(
            blacklist_monitor_loop(config, window_monitor, detector, sender, stop_event)
        ),
    ]

    try:
        await asyncio.gather(*tasks)
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt received. Shutting down...")
        stop_event.set()
        await asyncio.gather(*tasks, return_exceptions=True)

    logger.info("Student agent stopped cleanly.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
