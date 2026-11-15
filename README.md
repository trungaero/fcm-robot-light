# Voice Chat (WebRTC + OpenAI Realtime)

A minimal voice chat app:

- **Frontend** (React + Vite): captures your microphone and streams it to the
  backend over **WebRTC**, then plays the model's spoken reply.
- **Backend** (FastAPI + aiortc): acts as the WebRTC peer, bridges audio to the
  **OpenAI Realtime API** over WebSocket (`gpt-realtime-mini` by default), and
  relays transcripts back to the browser.

```
Browser mic ──WebRTC(Opus 48kHz)──▶ aiortc ──PCM16 24kHz──▶ OpenAI Realtime
Browser spk ◀─WebRTC(Opus 48kHz)── aiortc ◀─PCM16 24kHz── OpenAI Realtime
```

## Prerequisites

- Python 3.10+
- Node.js 18+
- An OpenAI API key with Realtime access
- On Linux, aiortc needs system libs: `sudo apt install libsrtp2-dev ffmpeg`

## 1. Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # then edit .env and set OPENAI_API_KEY
uvicorn main:app --reload --port 8000
```

Check it is up: `curl http://localhost:8000/health` should show
`"api_key_configured": true`.

## 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173, click **Start talking**, allow the microphone, and
speak. Vite proxies the `/ws` signaling socket to the backend on port 8000.

> `getUserMedia` requires a secure context. `localhost` counts as secure; to use
> the app from another device you'll need HTTPS.

## Docker (optional)

Run the whole stack with Docker Compose — no local Python or Node needed.

```bash
cp .env.example .env        # add your OPENAI_API_KEY
docker compose up --build
```

- Frontend: http://localhost:5173 (nginx serves the built app and proxies `/ws`
  and `/health` to the backend).
- Backend health: http://localhost:8000/health

The images are built from `backend/Dockerfile` (Python) and `frontend/Dockerfile`
(multi-stage Node build → nginx). `backend/.dockerignore` and
`frontend/.dockerignore` keep `.env`, `.venv`, and `node_modules` out of the
images.

## Configuration

All backend settings live in `backend/.env` (see `.env.example`):

| Variable | Default | Purpose |
| --- | --- | --- |
| `OPENAI_API_KEY` | — | Required. |
| `OPENAI_REALTIME_MODEL` | `gpt-realtime-mini` | Try `gpt-realtime-2.1` for higher quality. |
| `OPENAI_REALTIME_VOICE` | `marin` | Output voice. |
| `OPENAI_INSTRUCTIONS` | friendly assistant | System prompt. |
| `BACKEND_HOST` / `BACKEND_PORT` | `0.0.0.0` / `8000` | Bind address. |

## How it works

- `backend/audio.py` resamples WebRTC audio (48 kHz) to the Realtime API's PCM16
  24 kHz and back.
- `backend/openai_realtime.py` is a small async client for the Realtime
  WebSocket, exposing audio chunks, transcripts, and turn boundaries.
- `backend/rtc.py` owns the `RTCPeerConnection`: it sends mic audio to OpenAI and
  plays model audio back through a paced `AudioStreamTrack`.
- `backend/main.py` handles SDP/ICE signaling over `/ws`.
- `frontend/src/voiceChat.ts` does the browser side of WebRTC + signaling.
