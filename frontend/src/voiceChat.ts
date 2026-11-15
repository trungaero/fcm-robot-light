/**
 * Browser-side WebRTC + signaling client.
 *
 * Flow:
 *  1. Capture the mic with getUserMedia.
 *  2. Open the signaling WebSocket to the FastAPI backend.
 *  3. Create an offer, send it, and apply the server's SDP answer.
 *  4. Trickle ICE candidates in both directions.
 *  5. Play the model's audio from the `ontrack` stream and surface transcripts.
 */

export type Role = "user" | "assistant" | "error";

export interface ChatMessage {
  id: string;
  role: Role;
  text: string;
  final: boolean;
}

type TranscriptHandler = (role: Role, text: string, final: boolean) => void;
type TurnDoneHandler = () => void;
type StatusHandler = (status: string) => void;
type ErrorHandler = (message: string) => void;

interface ServerMessage {
  type: string;
  sdp?: string;
  sdpType?: RTCSdpType;
  candidate?: string;
  sdpMid?: string | null;
  sdpMLineIndex?: number | null;
  role?: Role;
  text?: string;
  final?: boolean;
  message?: string;
}

const ICE_SERVERS: RTCIceServer[] = [
  { urls: "stun:stun.l.google.com:19302" },
];

export class VoiceChat {
  private pc?: RTCPeerConnection;
  private ws?: WebSocket;
  private stream?: MediaStream;
  private audio?: HTMLAudioElement;
  private pendingCandidates: RTCIceCandidateInit[] = [];
  private remoteDescriptionSet = false;

  onTranscript?: TranscriptHandler;
  onTurnDone?: TurnDoneHandler;
  onStatus?: StatusHandler;
  onError?: ErrorHandler;

  get active(): boolean {
    return this.pc !== undefined;
  }

  async start(): Promise<void> {
    if (this.pc) return;

    this.pendingCandidates = [];
    this.remoteDescriptionSet = false;
    this.onStatus?.("Requesting microphone…");

    this.stream = await navigator.mediaDevices.getUserMedia({
      audio: { echoCancellation: true, noiseSuppression: true },
    });

    this.onStatus?.("Connecting…");

    this.audio = new Audio();
    this.audio.autoplay = true;

    const pc = new RTCPeerConnection({ iceServers: ICE_SERVERS });
    this.pc = pc;

    pc.ontrack = (event) => {
      if (this.audio && event.streams[0]) {
        this.audio.srcObject = event.streams[0];
        void this.audio.play().catch(() => {
          /* autoplay may be blocked until user gesture; mic start is a gesture */
        });
      }
    };

    pc.onconnectionstatechange = () => {
      if (pc.connectionState === "connected") {
        this.onStatus?.("Connected — start talking");
      } else if (pc.connectionState === "failed") {
        this.onError?.("WebRTC connection failed");
      }
    };

    for (const track of this.stream.getAudioTracks()) {
      pc.addTrack(track, this.stream);
    }

    pc.onicecandidate = (event) => {
      if (event.candidate) {
        this.send({
          type: "candidate",
          candidate: event.candidate.candidate,
          sdpMid: event.candidate.sdpMid,
          sdpMLineIndex: event.candidate.sdpMLineIndex,
        });
      }
    };

    const url = new URL("/ws", window.location.href);
    url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
    const ws = new WebSocket(url);
    this.ws = ws;
    ws.onmessage = (event) => this.handleServerMessage(JSON.parse(event.data));

    await new Promise<void>((resolve, reject) => {
      if (ws.readyState === WebSocket.OPEN) return resolve();
      ws.addEventListener("open", () => resolve(), { once: true });
      ws.addEventListener(
        "error",
        () => reject(new Error("Could not connect to the signaling server")),
        { once: true }
      );
    });

    const offer = await pc.createOffer();
    await pc.setLocalDescription(offer);
    this.send({ type: "offer", sdp: offer.sdp, sdpType: offer.type });
  }

  private handleServerMessage(message: ServerMessage): void {
    switch (message.type) {
      case "answer": {
        if (!this.pc || this.remoteDescriptionSet) return;
        this.remoteDescriptionSet = true;
        this.pc
          .setRemoteDescription({
            type: message.sdpType ?? "answer",
            sdp: message.sdp,
          })
          .then(() => this.flushCandidates())
          .catch((err) =>
            this.onError?.(`Failed to set remote description: ${err.message}`)
          );
        break;
      }
      case "candidate": {
        if (!this.pc || !message.candidate) return;
        const candidate: RTCIceCandidateInit = {
          candidate: message.candidate,
          sdpMid: message.sdpMid ?? undefined,
          sdpMLineIndex: message.sdpMLineIndex ?? undefined,
        };
        if (this.remoteDescriptionSet) {
          void this.pc.addIceCandidate(candidate).catch(() => undefined);
        } else {
          this.pendingCandidates.push(candidate);
        }
        break;
      }
      case "transcript":
        if (message.role && message.text !== undefined) {
          this.onTranscript?.(message.role, message.text, message.final ?? true);
        }
        break;
      case "turn_done":
        this.onTurnDone?.();
        break;
      case "error":
        this.onError?.(message.message ?? "Unknown error");
        break;
      default:
        break;
    }
  }

  private async flushCandidates(): Promise<void> {
    if (!this.pc) return;
    for (const candidate of this.pendingCandidates) {
      try {
        await this.pc.addIceCandidate(candidate);
      } catch {
        /* ignore stale candidates */
      }
    }
    this.pendingCandidates = [];
  }

  private send(message: unknown): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(message));
    }
  }

  stop(): void {
    this.send({ type: "stop" });
    this.ws?.close();
    this.ws = undefined;

    this.pc?.getSenders().forEach((sender) => sender.track?.stop());
    this.pc?.close();
    this.pc = undefined;

    this.stream?.getTracks().forEach((track) => track.stop());
    this.stream = undefined;

    if (this.audio) {
      this.audio.srcObject = null;
      this.audio = undefined;
    }

    this.pendingCandidates = [];
    this.remoteDescriptionSet = false;
    this.onStatus?.("Disconnected");
  }
}
