"""FastAPI entry point: WebRTC signaling over a WebSocket endpoint."""

from __future__ import annotations

import logging

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from config import config
from openai_realtime import OpenAIRealtimeClient
from rtc import VoicePeer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("voice-chat")

app = FastAPI(title="WebRTC Voice Chat", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict:
    return {
        "status": "ok",
        "model": config.model,
        "api_key_configured": bool(config.openai_api_key),
    }


@app.websocket("/ws")
async def signaling(websocket: WebSocket) -> None:
    """Exchange SDP/ICE with the browser and bridge audio to OpenAI.

    Client -> server: {"type": "offer"|"candidate"|"stop", ...}
    Server -> client: {"type": "answer"|"candidate"|"transcript"|"turn_done"|"error", ...}
    """
    await websocket.accept()

    peer: VoicePeer | None = None
    realtime: OpenAIRealtimeClient | None = None

    try:
        first = await websocket.receive_json()
        if first.get("type") != "offer":
            await websocket.send_json(
                {"type": "error", "message": "Expected an offer message"}
            )
            return

        if not config.openai_api_key:
            await websocket.send_json(
                {
                    "type": "error",
                    "message": "Server is missing OPENAI_API_KEY. Set it in backend/.env",
                }
            )
            return

        realtime = OpenAIRealtimeClient(
            api_key=config.openai_api_key,
            model=config.model,
            voice=config.voice,
            instructions=config.instructions,
            safety_identifier=config.safety_identifier,
        )
        await realtime.connect()
        log.info("Connected to OpenAI Realtime (%s)", config.model)

        async def send_event(event: dict) -> None:
            await websocket.send_json(event)

        peer = VoicePeer(realtime, send_event)
        await peer.handle_offer(first["sdp"], first.get("sdpType", "offer"))

        while True:
            message = await websocket.receive_json()
            mtype = message.get("type")
            if mtype == "candidate":
                await peer.add_ice_candidate(
                    message.get("candidate", ""),
                    message.get("sdpMid"),
                    message.get("sdpMLineIndex"),
                )
            elif mtype == "stop":
                log.info("Client requested stop")
                break

    except WebSocketDisconnect:
        log.info("Client disconnected")
    except Exception as exc:  # noqa: BLE001
        log.exception("Signaling error: %s", exc)
        try:
            await websocket.send_json({"type": "error", "message": str(exc)})
        except Exception:  # noqa: BLE001 - socket may already be closed
            pass
    finally:
        if peer is not None:
            await peer.close()
        elif realtime is not None:
            await realtime.close()


if __name__ == "__main__":
    uvicorn.run("main:app", host=config.host, port=config.port, reload=True)
