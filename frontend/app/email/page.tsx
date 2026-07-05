"use client";

import { useEffect, useRef, useState } from "react";

import { AppShell } from "@/components/AppShell";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { api, ApiError } from "@/lib/api";
import type { EmailDraftRead } from "@/lib/types";

const STATUS_STYLES: Record<string, string> = {
  pending_approval: "bg-amber-100 text-amber-700",
  approved: "bg-blue-100 text-blue-700",
  sent: "bg-green-100 text-green-700",
  rejected: "bg-slate-100 text-slate-500",
  failed: "bg-red-100 text-red-700",
};

// Editable fields kept locally per draft while in pending state.
interface DraftEdits {
  to: string;       // comma-separated
  subject: string;
  body: string;
  dirty: boolean;   // true = user has changed something
  saving: boolean;
}

function useAutoResize(ref: React.RefObject<HTMLTextAreaElement | null>) {
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${el.scrollHeight}px`;
  });
}

function BodyTextarea({
  value,
  onChange,
}: {
  value: string;
  onChange: (v: string) => void;
}) {
  const ref = useRef<HTMLTextAreaElement>(null);
  useAutoResize(ref);
  return (
    <textarea
      ref={ref}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      rows={1}
      className="mt-3 w-full resize-none rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-800 focus:border-slate-400 focus:bg-white focus:outline-none"
    />
  );
}

function EmailCard({
  draft,
  onUpdated,
}: {
  draft: EmailDraftRead;
  onUpdated: () => void;
}) {
  const isPending = draft.status === "pending_approval";

  const [edits, setEdits] = useState<DraftEdits>({
    to: draft.to_addresses.join(", "),
    subject: draft.subject,
    body: draft.body,
    dirty: false,
    saving: false,
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function update<K extends keyof DraftEdits>(key: K, value: DraftEdits[K]) {
    setEdits((prev) => ({ ...prev, [key]: value, dirty: true }));
  }

  async function saveEdits() {
    if (!edits.dirty) return;
    setEdits((prev) => ({ ...prev, saving: true }));
    try {
      await api.patch(`/api/v1/email/drafts/${draft.id}`, {
        to_addresses: edits.to.split(",").map((s) => s.trim()).filter(Boolean),
        subject: edits.subject,
        body: edits.body,
      });
      setEdits((prev) => ({ ...prev, dirty: false, saving: false }));
    } catch {
      setEdits((prev) => ({ ...prev, saving: false }));
    }
  }

  async function approve() {
    setBusy(true);
    setError(null);
    try {
      // Persist any unsaved edits before sending.
      if (edits.dirty) await saveEdits();
      await api.post(`/api/v1/email/drafts/${draft.id}/approve`);
      onUpdated();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to send email.");
      setBusy(false);
    }
  }

  async function reject() {
    setBusy(true);
    try {
      await api.post(`/api/v1/email/drafts/${draft.id}/reject`);
      onUpdated();
    } catch {
      setBusy(false);
    }
  }

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5">
      {/* Header row */}
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0 flex-1">
          {isPending ? (
            <>
              <input
                value={edits.subject}
                onChange={(e) => update("subject", e.target.value)}
                onBlur={saveEdits}
                placeholder="Subject"
                className="w-full rounded-md border border-slate-200 bg-slate-50 px-3 py-1.5 text-sm font-medium text-slate-900 focus:border-slate-400 focus:bg-white focus:outline-none"
              />
              <div className="mt-1.5 flex items-center gap-1.5">
                <span className="shrink-0 text-xs text-slate-400">To:</span>
                <input
                  value={edits.to}
                  onChange={(e) => update("to", e.target.value)}
                  onBlur={saveEdits}
                  placeholder="recipient@example.com, another@example.com"
                  className="min-w-0 flex-1 rounded-md border border-slate-200 bg-slate-50 px-3 py-1 text-xs text-slate-700 focus:border-slate-400 focus:bg-white focus:outline-none"
                />
              </div>
            </>
          ) : (
            <>
              <p className="font-medium text-slate-900">{draft.subject || "(no subject)"}</p>
              <p className="text-xs text-slate-400">To: {draft.to_addresses.join(", ")}</p>
            </>
          )}
        </div>
        <span
          className={`shrink-0 rounded-full px-2.5 py-1 text-xs font-medium ${STATUS_STYLES[draft.status] ?? ""}`}
        >
          {draft.status.replace(/_/g, " ")}
        </span>
      </div>

      {/* Body */}
      {isPending ? (
        <BodyTextarea value={edits.body} onChange={(v) => update("body", v)} />
      ) : (
        <p className="mt-3 whitespace-pre-wrap text-sm text-slate-600">{draft.body}</p>
      )}

      {/* Save indicator */}
      {isPending && edits.dirty && (
        <p className="mt-1 text-xs text-slate-400">{edits.saving ? "Saving…" : "Unsaved changes"}</p>
      )}

      {error && <p className="mt-2 text-sm text-red-600">{error}</p>}

      {/* Action buttons */}
      {isPending && (
        <div className="mt-4 flex gap-2">
          <button
            onClick={approve}
            disabled={busy}
            className="rounded-md bg-slate-900 px-3 py-1.5 text-xs font-medium text-white hover:bg-slate-800 disabled:opacity-50"
          >
            Approve &amp; send
          </button>
          <button
            onClick={reject}
            disabled={busy}
            className="rounded-md border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-50 disabled:opacity-50"
          >
            Reject
          </button>
        </div>
      )}
    </div>
  );
}

function EmailContent() {
  const [drafts, setDrafts] = useState<EmailDraftRead[]>([]);

  async function refresh() {
    const items = await api.get<EmailDraftRead[]>("/api/v1/email/drafts");
    setDrafts(items);
  }

  useEffect(() => {
    refresh().catch(() => {});
  }, []);

  return (
    <div>
      <h1 className="text-2xl font-semibold text-slate-900">Email</h1>
      <p className="mt-1 text-slate-500">
        Drafts your Email Agent prepared. Edit them freely before sending — nothing leaves until you approve.
      </p>

      <div className="mt-6 space-y-4">
        {drafts.map((draft) => (
          <EmailCard key={draft.id} draft={draft} onUpdated={refresh} />
        ))}
        {drafts.length === 0 && (
          <p className="text-sm text-slate-400">
            No email drafts yet — ask your assistant in Chat to draft one.
          </p>
        )}
      </div>
    </div>
  );
}

export default function EmailPage() {
  return (
    <ProtectedRoute>
      <AppShell>
        <EmailContent />
      </AppShell>
    </ProtectedRoute>
  );
}
