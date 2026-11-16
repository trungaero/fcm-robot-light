"""Environment-driven configuration for the voice chat backend."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Config:
    openai_api_key: str
    model: str
    voice: str
    instructions: str
    host: str
    port: int
    safety_identifier: str
    stun_url: str
    turn_url: str
    turn_username: str
    turn_credential: str


def load_config() -> Config:
    return Config(
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        model=os.getenv("OPENAI_REALTIME_MODEL", "gpt-realtime-mini"),
        voice=os.getenv("OPENAI_REALTIME_VOICE", "marin"),
        instructions=os.getenv(
            "OPENAI_INSTRUCTIONS",
            "You are a friendly, concise voice assistant. Keep replies short and conversational.",
        ),
        host=os.getenv("BACKEND_HOST", "0.0.0.0"),
        port=int(os.getenv("BACKEND_PORT", "8000")),
        safety_identifier=os.getenv("OPENAI_SAFETY_IDENTIFIER", "voice-chat-demo"),
        stun_url=os.getenv("WEBRTC_STUN_URL", "stun:stun.l.google.com:19302"),
        turn_url=os.getenv("WEBRTC_TURN_URL", ""),
        turn_username=os.getenv("WEBRTC_TURN_USERNAME", ""),
        turn_credential=os.getenv("WEBRTC_TURN_CREDENTIAL", ""),
    )


config = load_config()
