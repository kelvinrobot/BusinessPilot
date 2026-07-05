"use client";

import { useEffect, useRef, useState } from "react";

import { AppShell } from "@/components/AppShell";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { VoiceButton } from "@/components/VoiceButton";
import { api, downloadAndSave } from "@/lib/api";
import type {
  ChatResponse,
  ConversationDetail,
  ConversationRead,
  GeneratedDocument,
  MessageRead,
  PendingApproval,
} from "@/lib/types";

interface DisplayMessage {
  role: string;
  content: string;
  documents?: GeneratedDocument[];
  pendingApprovals?: PendingApproval[];
}

function ChatContent() {
  const [conversations, setConversations] = useState<ConversationRead[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<DisplayMessage[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [partialCaption, setPartialCaption] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api.get<ConversationRead[]>("/api/v1/chat/conversations").then(setConversations).catch(() => {});
  }, []);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, partialCaption]);

  async function loadConversation(id: string) {
    const detail = await api.get<ConversationDetail>(`/api/v1/chat/conversations/${id}`);
    setConversationId(detail.id);
    setMessages(detail.messages.map((m: MessageRead) => ({ role: m.role, content: m.content })));
  }

  function startNewChat() {
    setConversationId(null);
    setMessages([]);
    setPartialCaption("");
  }

  async function sendMessage() {
    const text = input.trim();
    if (!text || sending) return;
    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: text }]);
    setSending(true);
    try {
      const response = await api.post<ChatResponse>("/api/v1/chat", {
        message: text,
        conversation_id: conversationId,
      });
      setConversationId(response.conversation_id);
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: response.reply,
          documents: response.documents,
          pendingApprovals: response.pending_approvals,
        },
      ]);
      if (!conversations.some((c) => c.id === response.conversation_id)) {
        setConversations((prev) => [
          { id: response.conversation_id, title: text.slice(0, 60), channel: "text", created_at: new Date().toISOString() },
          ...prev,
        ]);
      }
    } catch {
      setMessages((prev) => [...prev, { role: "assistant", content: "Sorry, something went wrong processing that." }]);
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="flex h-full gap-6">
      <aside className="w-56 flex-shrink-0 overflow-y-auto border-r border-slate-200 pr-3">
        <button
          onClick={startNewChat}
          className="mb-3 w-full rounded-md bg-slate-900 px-3 py-2 text-sm font-medium text-white hover:bg-slate-800"
        >
          + New chat
        </button>
        <div className="space-y-1">
          {conversations.map((c) => (
            <button
              key={c.id}
              onClick={() => loadConversation(c.id)}
              className={`block w-full truncate rounded-md px-2 py-1.5 text-left text-sm ${
                c.id === conversationId ? "bg-slate-100 font-medium text-slate-900" : "text-slate-600 hover:bg-slate-50"
              }`}
            >
              {c.title}
            </button>
          ))}
        </div>
      </aside>

      <div className="flex flex-1 flex-col">
        <div ref={scrollRef} className="flex-1 space-y-4 overflow-y-auto pb-4">
          {messages.length === 0 && (
            <p className="mt-10 text-center text-sm text-slate-400">
              Ask BusinessPilot to draft a document, plan a campaign, manage email, or schedule a meeting.
            </p>
          )}
          {messages.map((m, i) => (
            <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
              <div
                className={`max-w-2xl rounded-2xl px-4 py-2.5 text-sm whitespace-pre-wrap ${
                  m.role === "user" ? "bg-slate-900 text-white" : "bg-white border border-slate-200 text-slate-800"
                }`}
              >
                {m.content}
                {m.documents && m.documents.length > 0 && (
                  <div className="mt-2 space-y-1">
                    {m.documents.map((d) => (
                      <button
                        key={d.document_id}
                        onClick={() =>
                          d.download_url && downloadAndSave(d.download_url, `${d.title || "document"}`)
                        }
                        className="block text-left text-xs font-medium text-blue-600 hover:underline"
                      >
                        📄 Download: {d.title}
                      </button>
                    ))}
                  </div>
                )}
                {m.pendingApprovals && m.pendingApprovals.length > 0 && (
                  <p className="mt-2 text-xs font-medium text-amber-600">
                    Awaiting your approval — review it under Email or Calendar.
                  </p>
                )}
              </div>
            </div>
          ))}
          {partialCaption && (
            <div className="flex justify-end">
              <div className="max-w-2xl rounded-2xl bg-slate-200 px-4 py-2.5 text-sm italic text-slate-500">
                {partialCaption}
              </div>
            </div>
          )}
        </div>

        <div className="flex items-end gap-3 border-t border-slate-200 pt-4">
          <VoiceButton
            conversationId={conversationId}
            onPartial={(text) => setPartialCaption(text)}
            onFinal={(text) => {
              setPartialCaption("");
              setMessages((prev) => [...prev, { role: "user", content: text }]);
            }}
            onReply={(payload) => {
              setConversationId(payload.conversation_id);
              setMessages((prev) => [
                ...prev,
                {
                  role: "assistant",
                  content: payload.text,
                  documents: payload.documents,
                  pendingApprovals: payload.pending_approvals,
                },
              ]);
            }}
          />
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
              }
            }}
            placeholder="Type a message..."
            rows={1}
            className="flex-1 resize-none rounded-xl border border-slate-300 px-4 py-3 text-sm focus:border-slate-500 focus:outline-none"
          />
          <button
            onClick={sendMessage}
            disabled={sending}
            className="rounded-xl bg-slate-900 px-4 py-3 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50"
          >
            Send
          </button>
        </div>
      </div>
    </div>
  );
}

export default function ChatPage() {
  return (
    <ProtectedRoute>
      <AppShell>
        <ChatContent />
      </AppShell>
    </ProtectedRoute>
  );
}
