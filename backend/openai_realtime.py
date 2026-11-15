"""Thin async client for the OpenAI Realtime API over WebSocket (server-to-server).

Protocol reference: https://developers.openai.com/api/docs/guides/voice-websockets

We stream raw PCM16 mono audio (24 kHz) into the session and receive the model's
spoken reply as base64 PCM16 deltas plus rolling transcripts. Server-side voice
activity detection (VAD) handles turn-taking, so no manual buffer commits are
needed.

The translation layer accepts both the current GA event names
(``response.output_audio.*``) and the legacy beta names (``response.audio.*``) so
the app keeps working across API revisions.
"""

from __future__ import annotations

import base64
import json
import logging
from dataclasses import dataclass
from typing import Any, AsyncIterator, Union

import websockets

log = logging.getLogger(__name__)


@dataclass
class AudioChunk:
    """A chunk of the model's spoken output (raw PCM16 mono @ 24 kHz)."""

    data: bytes


@dataclass
class Transcript:
    role: str
    text: str
    final: bool


@dataclass
class TurnDone:
    role: str = "assistant"


@dataclass
class ErrorEvent:
    message: str


Event = Union[AudioChunk, Transcript, TurnDone, ErrorEvent]


class OpenAIRealtimeClient:
    def __init__(
        self,
        api_key: str,
        model: str,
        voice: str,
        instructions: str,
        safety_identifier: str = "voice-chat-demo",
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._voice = voice
        self._instructions = instructions
        self._safety_identifier = safety_identifier
        self._ws: Any | None = None

    @property
    def url(self) -> str:
        return f"wss://api.openai.com/v1/realtime?model={self._model}"

    async def connect(self) -> None:
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "OpenAI-Safety-Identifier": self._safety_identifier,
        }
        kwargs = {
            "max_size": 2**24,
            "ping_interval": 20,
        }
        try:
            # websockets >= 12
            self._ws = await websockets.connect(
                self.url, additional_headers=headers, **kwargs
            )
        except TypeError:
            # websockets < 12
            self._ws = await websockets.connect(
                self.url, extra_headers=headers, **kwargs
            )
        await self._configure()

    async def _configure(self) -> None:
        await self._send(
            {
                "type": "session.update",
                "session": {
                    "type": "realtime",
                    "instructions": self._instructions,
                    "audio": {
                        "input": {
                            "format": {"type": "audio/pcm", "rate": 24000},
                            "turn_detection": {
                                "type": "server_vad",
                                "silence_duration_ms": 600,
                            },
                            "transcription": {"model": "gpt-4o-mini-transcribe"},
                        },
                        "output": {
                            "format": {"type": "audio/pcm", "rate": 24000},
                            "voice": self._voice,
                        },
                    },
                },
            }
        )

    async def _send(self, event: dict) -> None:
        if self._ws is None:
            raise RuntimeError("Realtime socket is not connected")
        await self._ws.send(json.dumps(event))

    async def send_audio(self, pcm: bytes) -> None:
        """Append a chunk of mic audio to the session's input buffer."""
        if not pcm or self._ws is None:
            return
        await self._send(
            {
                "type": "input_audio_buffer.append",
                "audio": base64.b64encode(pcm).decode("ascii"),
            }
        )

    async def stream(self) -> AsyncIterator[Event]:
        """Yield translated events for the lifetime of the connection."""
        if self._ws is None:
            raise RuntimeError("Realtime socket is not connected")
        async for raw in self._ws:
            try:
                event = json.loads(raw)
            except (TypeError, ValueError):
                continue
            for translated in self._translate(event):
                yield translated

    def _translate(self, event: dict) -> list[Event]:
        etype = event.get("type")
        out: list[Event] = []

        if etype in ("response.output_audio.delta", "response.audio.delta"):
            delta = event.get("delta") or ""
            if delta:
                out.append(AudioChunk(base64.b64decode(delta)))

        elif etype in (
            "response.output_audio_transcript.delta",
            "response.audio_transcript.delta",
        ):
            delta = event.get("delta") or ""
            if delta:
                out.append(Transcript("assistant", delta, False))

        elif etype == "conversation.item.input_audio_transcription.completed":
            text = event.get("transcript") or ""
            if text:
                out.append(Transcript("user", text, True))

        elif etype == "response.done":
            out.append(TurnDone())

        elif etype == "error":
            error = event.get("error") or {}
            message = error.get("message") or json.dumps(error)
            log.error("Realtime API error: %s", message)
            out.append(ErrorEvent(message))

        return out

    async def close(self) -> None:
        if self._ws is not None:
            try:
                await self._ws.close()
            finally:
                self._ws = None
