import argparse
import json
import os
from dataclasses import dataclass, field
from typing import List


@dataclass
class AgentConfig:
    backend_url: str = "ws://10.131.131.188:8000/ws"
    student_id: str = "PC01"
    student_name: str = "Student 1"
    auth_token: str = "student-secret"
    fps: float = 1.0
    target_width: int = 480
    jpeg_quality: int = 60
    monitor_interval: float = 1.5
    blacklist_processes: List[str] = field(
        default_factory=lambda: [
            "discord.exe",
            "telegram.exe",
            "whatsapp.exe",
            "torrent.exe",
            "steam.exe",
        ]
    )
    blacklist_keywords: List[str] = field(
        default_factory=lambda: [
            "chatgpt",
            "gemini",
            "claude",
            "youtube",
            "facebook",
            "instagram",
            "tiktok",
            "reddit",
            "twitter",
            "x.com",
        ]
    )

    @property
    def capture_interval(self) -> float:
        return 1.0 / self.fps if self.fps > 0 else 0.33

    @classmethod
    def load(cls, config_path: str = None) -> "AgentConfig":
        config = cls()
        if config_path and os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                for key, val in data.items():
                    if hasattr(config, key):
                        setattr(config, key, val)

        # Environment variable overrides
        config.backend_url = os.getenv("BACKEND_URL", config.backend_url)
        config.student_id = os.getenv("STUDENT_ID", config.student_id)
        config.student_name = os.getenv("STUDENT_NAME", config.student_name)
        config.auth_token = os.getenv("AUTH_TOKEN", config.auth_token)

        return config

    @classmethod
    def parse_cli_args(cls, args: List[str] = None) -> "AgentConfig":
        parser = argparse.ArgumentParser(description="SmartClassMonitor Student Agent")
        parser.add_argument("--backend-url", type=str, help="Backend WebSocket URL")
        parser.add_argument("--student-id", type=str, help="Unique Student / PC ID")
        parser.add_argument("--student-name", type=str, help="Student display name")
        parser.add_argument("--auth-token", type=str, help="Authentication token")
        parser.add_argument("--fps", type=float, help="Screen capture frame rate (FPS)")
        parser.add_argument("--target-width", type=int, help="Resized frame width in pixels")
        parser.add_argument("--jpeg-quality", type=int, help="JPEG compression quality (1-100)")
        parser.add_argument("--config-file", type=str, help="Path to JSON config file")

        parsed = parser.parse_args(args)

        config = cls.load(parsed.config_file)

        if parsed.backend_url:
            config.backend_url = parsed.backend_url
        if parsed.student_id:
            config.student_id = parsed.student_id
        if parsed.student_name:
            config.student_name = parsed.student_name
        if parsed.auth_token:
            config.auth_token = parsed.auth_token
        if parsed.fps is not None:
            config.fps = parsed.fps
        if parsed.target_width is not None:
            config.target_width = parsed.target_width
        if parsed.jpeg_quality is not None:
            config.jpeg_quality = parsed.jpeg_quality

        return config
