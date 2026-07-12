"use client";

import { useRef, useState } from "react";

import { wsUrl } from "@/lib/api";
import { getAccessToken } from "@/lib/auth";
import type { GeneratedDocument, PendingApproval } from "@/lib/types";

interface VoiceReplyPayload {
  text: string;
  conversation_id: string;
  documents: GeneratedDocument[];
  pending_approvals: PendingApproval[];
}

interface VoiceButtonProps {
  conversationId: string | null;
  onPartial?: (text: string) => void;
  onFinal?: (text: string) => void;
  onReply?: (payload: VoiceReplyPayload) => void;
}

// Web Speech API — not fully typed in every TS/lib.dom.d.ts version.
interface SpeechRecognitionEvent extends Event {
  readonly resultIndex: number;
  readonly results: SpeechRecognitionResultList;
}
interface SpeechRecognitionResultList {
  readonly length: number;
  item(index: number): SpeechRecognitionResult;
  [index: number]: SpeechRecognitionResult;
}
interface SpeechRecognitionResult {
  readonly isFinal: boolean;
  readonly length: number;
  item(index: number): SpeechRecognitionAlternative;
  [index: number]: SpeechRecognitionAlternative;
}
interface SpeechRecognitionAlternative {
  readonly transcript: string;
  readonly confidence: number;
}
interface SpeechRecognitionErrorEvent extends Event {
  readonly error: string;
}
interface SpeechRecognition extends EventTarget {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  onresult: ((event: SpeechRecognitionEvent) => void) | null;
  onerror: ((event: SpeechRecognitionErrorEvent) => void) | null;
  onend: (() => void) | null;
  start(): void;
  stop(): void;
  abort(): void;
}
declare let SpeechRecognition: { new (): SpeechRecognition };
declare global {
  interface Window {
    SpeechRecognition: { new (): SpeechRecognition };
    webkitSpeechRecognition: { new (): SpeechRecognition };
  }
}

export function VoiceButton({ conversationId, onPartial, onFinal, onReply }: VoiceButtonProps) {
  const [recording, setRecording] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const socketRef = useRef<WebSocket | null>(null);
  const recognitionRef = useRef<SpeechRecognition | null>(null);
  const activeRef = useRef(false); // stable ref for closures

  function stopSpeaking() {
    if (typeof window !== "undefined" && "speechSynthesis" in window) {
      window.speechSynthesis.cancel();
    }
    setSpeaking(false);
  }

  function stop() {
    activeRef.current = false;
    recognitionRef.current?.abort();
    recognitionRef.current = null;
    if (socketRef.current?.readyState === WebSocket.OPEN) {
      socketRef.current.close();
    }
    socketRef.current = null;
    setRecording(false);
  }

  function start() {
    const token = getAccessToken();
    if (!token) return;

    const SR = window.SpeechRecognition ?? window.webkitSpeechRecognition;
    if (!SR) {
      alert("Your browser does not support the Web Speech API. Use Chrome or Edge.");
      return;
    }

    setError(null);

    // Start recognition immediately — it's a purely browser-native feature
    // (Chrome/Edge's own speech engine) and must not be gated behind the
    // backend WebSocket below, which is only needed to relay the transcript
    // and receive a spoken reply.
    const recognition = new SR();
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = "en-US";
    recognitionRef.current = recognition;
    activeRef.current = true;

    recognition.onresult = (event) => {
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const result = event.results[i];
        const transcript = result[0].transcript;
        if (result.isFinal) {
          onFinal?.(transcript);
          if (socketRef.current?.readyState === WebSocket.OPEN && transcript.trim()) {
            socketRef.current.send(JSON.stringify({ type: "transcript", text: transcript.trim() }));
          }
        } else {
          onPartial?.(transcript);
        }
      }
    };

    recognition.onerror = (event) => {
      // Fatal errors (permission denied, no mic, insecure context) will not
      // resolve on retry — stop instead of silently looping forever.
      if (event.error === "not-allowed" || event.error === "service-not-allowed" || event.error === "audio-capture") {
        setError(
          event.error === "audio-capture"
            ? "No microphone was found."
            : "Microphone access was blocked. Allow microphone permission for this site and try again.",
        );
        stop();
        return;
      }
      if (event.error !== "aborted" && event.error !== "no-speech") {
        console.error("Speech recognition error:", event.error);
      }
    };

    // Continuous mode can stop on silence; restart automatically while recording.
    recognition.onend = () => {
      if (activeRef.current) recognition.start();
    };

    recognition.start();
    setRecording(true);

    // Open the voice WebSocket in parallel. Token is sent as the first
    // message (not in the URL) so it is never captured by server access
    // logs or browser history.
    const wsPath = conversationId
      ? `/api/v1/voice/ws?conversation_id=${encodeURIComponent(conversationId)}`
      : "/api/v1/voice/ws";
    const socket = new WebSocket(wsUrl(wsPath));
    socketRef.current = socket;

    socket.onopen = () => {
      socket.send(JSON.stringify({ type: "auth", token }));
    };

    socket.onmessage = (event) => {
      const payload = JSON.parse(event.data as string);
      if (payload.type === "reply_text") {
        onReply?.({
          text: payload.text,
          conversation_id: payload.conversation_id,
          documents: payload.documents ?? [],
          pending_approvals: payload.pending_approvals ?? [],
        });
        // Speak the reply with the browser's built-in TTS.
        if (typeof window !== "undefined" && "speechSynthesis" in window) {
          setSpeaking(true);
          const utterance = new SpeechSynthesisUtterance(payload.text);
          utterance.onend = () => setSpeaking(false);
          utterance.onerror = () => setSpeaking(false);
          window.speechSynthesis.speak(utterance);
        }
      }
    };

    socket.onerror = () => {
      console.error("Voice WebSocket failed to connect");
      setError("Couldn't reach the voice service — you can still talk, but replies won't be read aloud.");
    };

    socket.onclose = () => {
      if (socketRef.current === socket) socketRef.current = null;
    };
  }

  return (
    <div className="flex items-center gap-3">
      <button
        type="button"
        onClick={() => (recording ? stop() : start())}
        className={`flex h-14 w-14 items-center justify-center rounded-full text-2xl shadow-md transition-colors ${
          recording ? "bg-red-500 text-white" : "bg-slate-900 text-white hover:bg-slate-800"
        }`}
        aria-label={recording ? "Stop voice" : "Start voice"}
      >
        {recording ? "■" : "\u{1F399}"}
      </button>
      {speaking && (
        <button
          type="button"
          onClick={stopSpeaking}
          className="text-xs text-slate-500 underline hover:text-slate-700"
        >
          Stop speaking
        </button>
      )}
      {error && <p className="text-xs text-red-600">{error}</p>}
    </div>
  );
}
