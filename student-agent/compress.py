import base64
import logging
from typing import Optional, Tuple
import cv2
import numpy as np

logger = logging.getLogger("student_agent.compress")


class FrameCompressor:
    """Resizes and compresses raw screen frames into JPEG Base64 strings."""

    def __init__(self, target_width: int = 480, jpeg_quality: int = 60):
        self.target_width = target_width
        self.jpeg_quality = max(1, min(100, jpeg_quality))

    def compress(self, frame_bgr: np.ndarray) -> Optional[Tuple[str, int]]:
        """
        Resizes frame to target_width and encodes as JPEG Base64.
        Returns tuple of (base64_str, byte_size) or None on failure.
        """
        if frame_bgr is None or frame_bgr.size == 0:
            return None

        try:
            h, w = frame_bgr.shape[:2]

            # Calculate resized dimensions preserving aspect ratio
            if w > self.target_width:
                target_height = int(h * (self.target_width / float(w)))
                resized = cv2.resize(
                    frame_bgr, (self.target_width, target_height), interpolation=cv2.INTER_AREA
                )
            else:
                resized = frame_bgr

            # Encode as JPEG
            encode_params = [int(cv2.IMWRITE_JPEG_QUALITY), self.jpeg_quality]
            success, buffer = cv2.imencode(".jpg", resized, encode_params)

            if not success:
                logger.error("Failed to encode frame as JPEG")
                return None

            # Convert to Base64 string
            jpg_bytes = buffer.tobytes()
            b64_str = base64.b64encode(jpg_bytes).decode("ascii")
            return b64_str, len(jpg_bytes)

        except Exception as e:
            logger.error(f"Error compressing frame: {e}")
            return None
