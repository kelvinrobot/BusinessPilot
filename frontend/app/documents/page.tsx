"use client";

import { useEffect, useState } from "react";

import { AppShell } from "@/components/AppShell";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { api, ApiError, downloadAndSave } from "@/lib/api";
import type { DocumentRead } from "@/lib/types";

function DocumentsContent() {
  const [documents, setDocuments] = useState<DocumentRead[]>([]);
  const [instruction, setInstruction] = useState("");
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    const items = await api.get<DocumentRead[]>("/api/v1/documents");
    setDocuments(items);
  }

  useEffect(() => {
    refresh().catch(() => {});
  }, []);

  async function handleGenerate(e: React.FormEvent) {
    e.preventDefault();
    if (!instruction.trim() || generating) return;
    setGenerating(true);
    setError(null);
    try {
      await api.post("/api/v1/documents/generate", { instruction });
      setInstruction("");
      await refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to generate document.");
    } finally {
      setGenerating(false);
    }
  }

  return (
    <div>
      <h1 className="text-xl font-semibold text-slate-900 sm:text-2xl">Documents</h1>
      <p className="mt-1 text-slate-500">Real, downloadable business documents your assistant has created.</p>

      <form
        onSubmit={handleGenerate}
        className="mt-6 flex flex-col gap-3 rounded-xl border border-slate-200 bg-white p-4 sm:flex-row"
      >
        <input
          value={instruction}
          onChange={(e) => setInstruction(e.target.value)}
          placeholder="e.g. Create a competitor analysis for my bakery"
          className="min-w-0 flex-1 rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none focus:ring-2 focus:ring-slate-300"
        />
        <button
          type="submit"
          disabled={generating}
          className="rounded-md bg-slate-900 px-4 py-2.5 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-400 focus-visible:ring-offset-1 sm:py-2"
        >
          {generating ? "Generating..." : "Generate"}
        </button>
      </form>
      {error && <p className="mt-2 text-sm text-red-600">{error}</p>}

      <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {documents.map((doc) => (
          <button
            key={doc.id}
            onClick={() =>
              downloadAndSave(`/api/v1/documents/${doc.id}/download`, `${doc.title}.${doc.file_format}`)
            }
            className="rounded-xl border border-slate-200 bg-white p-4 text-left shadow-sm transition-shadow hover:shadow-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-400 focus-visible:ring-offset-1"
          >
            <p className="break-words font-medium text-slate-900">{doc.title}</p>
            <p className="mt-1 text-xs uppercase tracking-wide text-slate-400">
              {doc.doc_type.replace(/_/g, " ")} · {doc.file_format}
            </p>
            <p className="mt-2 text-xs text-slate-400">{new Date(doc.created_at).toLocaleString()}</p>
          </button>
        ))}
        {documents.length === 0 && (
          <p className="text-sm text-slate-400">No documents yet -- generate one above or ask in Chat.</p>
        )}
      </div>
    </div>
  );
}

export default function DocumentsPage() {
  return (
    <ProtectedRoute>
      <AppShell>
        <DocumentsContent />
      </AppShell>
    </ProtectedRoute>
  );
}
