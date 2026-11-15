import { useEffect, useRef, useState } from "react";
import { VoiceChat, type ChatMessage, type Role } from "./voiceChat";

let idCounter = 0;
const nextId = () => `m${++idCounter}`;

export default function App() {
  const chatRef = useRef<VoiceChat | null>(null);
  if (!chatRef.current) chatRef.current = new VoiceChat();

  const [active, setActive] = useState(false);
  const [status, setStatus] = useState("Idle");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const chat = chatRef.current!;

    chat.onStatus = setStatus;
    chat.onError = (message) => {
      setError(message);
      setStatus("Error");
    };

    chat.onTranscript = (role: Role, text: string, final: boolean) => {
      setMessages((prev) => {
        if (role === "assistant") {
          const last = prev[prev.length - 1];
          if (last && last.role === "assistant" && !last.final) {
            return [
              ...prev.slice(0, -1),
              { ...last, text: last.text + text, final },
            ];
          }
        }
        return [...prev, { id: nextId(), role, text, final }];
      });
    };

    chat.onTurnDone = () => {
      setMessages((prev) => {
        const last = prev[prev.length - 1];
        if (last && last.role === "assistant" && !last.final) {
          return [...prev.slice(0, -1), { ...last, final: true }];
        }
        return prev;
      });
    };

    return () => chat.stop();
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleStart = async () => {
    setError(null);
    setMessages([]);
    try {
      await chatRef.current!.start();
      setActive(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setStatus("Error");
      chatRef.current!.stop();
      setActive(false);
    }
  };

  const handleStop = () => {
    chatRef.current!.stop();
    setActive(false);
  };

  return (
    <main className="app">
      <header className="header">
        <h1>Voice Chat</h1>
        <p className="subtitle">Talk to an OpenAI realtime model over WebRTC</p>
      </header>

      <div className="controls">
        <button
          className="btn primary"
          onClick={handleStart}
          disabled={active}
        >
          Start talking
        </button>
        <button className="btn" onClick={handleStop} disabled={!active}>
          Stop
        </button>
        <span className={`status ${active ? "live" : ""}`}>{status}</span>
      </div>

      {error && <div className="error">{error}</div>}

      <section className="transcript">
        {messages.length === 0 && (
          <p className="empty">
            Press “Start talking” and speak. Your conversation will appear
            here.
          </p>
        )}
        {messages.map((message) => (
          <div key={message.id} className={`bubble ${message.role}`}>
            <span className="label">
              {message.role === "user" ? "You" : "Assistant"}
            </span>
            <span className="text">
              {message.text || "…"}
              {!message.final && <span className="cursor" />}
            </span>
          </div>
        ))}
        <div ref={bottomRef} />
      </section>
    </main>
  );
}
