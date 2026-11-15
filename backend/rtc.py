"""WebRTC peer that bridges browser audio to the OpenAI Realtime session."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Awaitable, Callable

from aiortc import (
    RTCIceCandidate,
    RTCPeerConnection,
    RTCSessionDescription,
    MediaStreamTrack,
)
from aiortc.mediastreams import MediaStreamError

from audio import (
    CHUNK_BYTES,
    CHUNK_SECONDS,
    make_mic_resampler,
    make_playback_resampler,
    pcm24_to_frame,
    resample_to_pcm24,
)
from openai_realtime import (
    AudioChunk,
    ErrorEvent,
    OpenAIRealtimeClient,
    Transcript,
    TurnDone,
)

log = logging.getLogger(__name__)

SendEvent = Callable[[dict], Awaitable[None]]


class OpenAIAudioTrack(MediaStreamTrack):
    """A send-only audio track that plays back the model's speech.

    OpenAI delivers PCM16 mono @ 24 kHz in arbitrary-sized chunks. We buffer
    them, emit fixed 20 ms frames resampled to 48 kHz stereo, and pace delivery
    against the wall clock so playback stays real-time.
    """

    kind = "audio"

    def __init__(self) -> None:
        super().__init__()
        self._queue: asyncio.Queue[bytes | None] = asyncio.Queue()
        self._buffer = bytearray()
        self._resampler = make_playback_resampler()
        self._timestamp = 0
        self._next_time: float | None = None
        self._closed = False

    def push(self, data: bytes) -> None:
        if not self._closed:
            self._queue.put_nowait(data)

    def stop(self) -> None:
        self._closed = True
        self._queue.put_nowait(None)

    async def recv(self) -> "av.AudioFrame":  # type: ignore[name-defined]
        while True:
            while len(self._buffer) < CHUNK_BYTES:
                chunk = await self._queue.get()
                if chunk is None:
                    raise MediaStreamError
                self._buffer.extend(chunk)

            data = bytes(self._buffer[:CHUNK_BYTES])
            del self._buffer[:CHUNK_BYTES]

            frame = pcm24_to_frame(data, self._resampler, self._timestamp)
            if frame is None:
                continue

            now = time.monotonic()
            if self._next_time is None or self._next_time < now - 0.1:
                self._next_time = now
            wait = self._next_time - now
            if wait > 0:
                await asyncio.sleep(wait)
            self._next_time += CHUNK_SECONDS

            self._timestamp += frame.samples
            return frame


def parse_ice_candidate(
    sdp: str, sdp_mid: str | None, sdp_mline_index: int | None
) -> RTCIceCandidate:
    """Build an aiortc RTCIceCandidate from a browser candidate SDP line."""
    line = sdp.strip()
    if line.startswith("a="):
        line = line[2:]
    if line.startswith("candidate:"):
        line = line[len("candidate:") :]

    parts = line.split()
    foundation = parts[0]
    component = int(parts[1])
    protocol = parts[2].lower()
    priority = int(parts[3])
    ip = parts[4]
    port = int(parts[5])
    cand_type = parts[7] if len(parts) > 7 else "host"

    related_address: str | None = None
    related_port: int | None = None
    index = 8
    while index + 1 < len(parts):
        key, value = parts[index], parts[index + 1]
        if key == "raddr":
            related_address = value
        elif key == "rport":
            related_port = int(value)
        index += 2

    return RTCIceCandidate(
        component=component,
        foundation=foundation,
        ip=ip,
        port=port,
        priority=priority,
        protocol=protocol,
        type=cand_type,
        relatedAddress=related_address,
        relatedPort=related_port,
        sdpMid=sdp_mid,
        sdpMLineIndex=sdp_mline_index if sdp_mline_index is not None else 0,
    )


class VoicePeer:
    """Owns the RTCPeerConnection and pumps audio in both directions."""

    def __init__(self, realtime: OpenAIRealtimeClient, send_event: SendEvent) -> None:
        self.realtime = realtime
        self._send_event = send_event
        self.pc = RTCPeerConnection()
        self.playback = OpenAIAudioTrack()
        self.pc.addTrack(self.playback)

        self._mic_task: asyncio.Task | None = None
        self._realtime_task: asyncio.Task | None = None
        self._closed = False

        @self.pc.on("track")
        def on_track(track: MediaStreamTrack) -> None:
            if track.kind == "audio":
                self._mic_task = asyncio.create_task(self._mic_loop(track))

        @self.pc.on("icecandidate")
        async def on_icecandidate(candidate: RTCIceCandidate | None) -> None:
            if candidate is None:
                return
            await self._send_event(
                {
                    "type": "candidate",
                    "candidate": candidate.to_sdp(),
                    "sdpMid": candidate.sdpMid,
                    "sdpMLineIndex": candidate.sdpMLineIndex,
                }
            )

        @self.pc.on("connectionstatechange")
        async def on_connectionstatechange() -> None:
            log.info("WebRTC connection state: %s", self.pc.connectionState)

    async def handle_offer(self, sdp: str, sdp_type: str = "offer") -> None:
        await self.pc.setRemoteDescription(
            RTCSessionDescription(sdp=sdp, type=sdp_type)  # type: ignore[arg-type]
        )
        answer = await self.pc.createAnswer()
        await self.pc.setLocalDescription(answer)

        local = self.pc.localDescription
        assert local is not None
        await self._send_event(
            {"type": "answer", "sdp": local.sdp, "sdpType": local.type}
        )

        self._realtime_task = asyncio.create_task(self._realtime_loop())

    async def add_ice_candidate(
        self,
        candidate_sdp: str,
        sdp_mid: str | None,
        sdp_mline_index: int | None,
    ) -> None:
        try:
            candidate = parse_ice_candidate(candidate_sdp, sdp_mid, sdp_mline_index)
            await self.pc.addIceCandidate(candidate)
        except Exception as exc:  # noqa: BLE001 - candidate parse is best-effort
            log.warning("Failed to add ICE candidate: %s", exc)

    async def _mic_loop(self, track: MediaStreamTrack) -> None:
        resampler = make_mic_resampler()
        try:
            while not self._closed:
                frame = await track.recv()
                pcm = resample_to_pcm24(frame, resampler)
                if pcm:
                    await self.realtime.send_audio(pcm)
        except MediaStreamError:
            pass
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            log.exception("Microphone loop error: %s", exc)

    async def _realtime_loop(self) -> None:
        try:
            async for event in self.realtime.stream():
                if isinstance(event, AudioChunk):
                    self.playback.push(event.data)
                elif isinstance(event, Transcript):
                    await self._send_event(
                        {
                            "type": "transcript",
                            "role": event.role,
                            "text": event.text,
                            "final": event.final,
                        }
                    )
                elif isinstance(event, TurnDone):
                    await self._send_event({"type": "turn_done"})
                elif isinstance(event, ErrorEvent):
                    await self._send_event(
                        {"type": "error", "message": event.message}
                    )
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            log.exception("Realtime loop error: %s", exc)

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        for task in (self._mic_task, self._realtime_task):
            if task is not None:
                task.cancel()
        self.playback.stop()
        await self.pc.close()
        await self.realtime.close()
