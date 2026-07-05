"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { AppShell } from "@/components/AppShell";
import { useAuth } from "@/components/AuthProvider";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { api } from "@/lib/api";
import type { ConversationRead, DocumentRead, EmailDraftRead, TaskRead } from "@/lib/types";

function Card({ title, href, children }: { title: string; href: string; children: React.ReactNode }) {
  return (
    <Link
      href={href}
      className="block rounded-xl border border-slate-200 bg-white p-5 shadow-sm transition-shadow hover:shadow-md"
    >
      <h3 className="text-sm font-semibold text-slate-500">{title}</h3>
      <div className="mt-2">{children}</div>
    </Link>
  );
}

function DashboardContent() {
  const { user } = useAuth();
  const [conversations, setConversations] = useState<ConversationRead[]>([]);
  const [documents, setDocuments] = useState<DocumentRead[]>([]);
  const [tasks, setTasks] = useState<TaskRead[]>([]);
  const [drafts, setDrafts] = useState<EmailDraftRead[]>([]);

  useEffect(() => {
    api.get<ConversationRead[]>("/api/v1/chat/conversations").then(setConversations).catch(() => {});
    api.get<DocumentRead[]>("/api/v1/documents").then(setDocuments).catch(() => {});
    api.get<TaskRead[]>("/api/v1/tasks").then(setTasks).catch(() => {});
    api.get<EmailDraftRead[]>("/api/v1/email/drafts").then(setDrafts).catch(() => {});
  }, []);

  const openTasks = tasks.filter((t) => t.status !== "done");
  const pendingDrafts = drafts.filter((d) => d.status === "pending_approval");

  return (
    <div>
      <h1 className="text-2xl font-semibold text-slate-900">
        Welcome back{user?.full_name ? `, ${user.full_name.split(" ")[0]}` : ""}.
      </h1>
      <p className="mt-1 text-slate-500">Here&apos;s what&apos;s happening with your business.</p>

      <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card title="Conversations" href="/chat">
          <p className="text-3xl font-semibold text-slate-900">{conversations.length}</p>
          <p className="text-xs text-slate-400">Talk to your assistant</p>
        </Card>
        <Card title="Documents" href="/documents">
          <p className="text-3xl font-semibold text-slate-900">{documents.length}</p>
          <p className="text-xs text-slate-400">Generated business documents</p>
        </Card>
        <Card title="Open tasks" href="/tasks">
          <p className="text-3xl font-semibold text-slate-900">{openTasks.length}</p>
          <p className="text-xs text-slate-400">Things still to do</p>
        </Card>
        <Card title="Pending approvals" href="/email">
          <p className="text-3xl font-semibold text-slate-900">{pendingDrafts.length}</p>
          <p className="text-xs text-slate-400">Drafts awaiting your review</p>
        </Card>
      </div>

      <div className="mt-8 rounded-xl border border-slate-200 bg-white p-5">
        <h2 className="text-sm font-semibold text-slate-700">Quick start</h2>
        <p className="mt-2 text-sm text-slate-500">
          Try asking your assistant in <Link href="/chat" className="text-blue-600 hover:underline">Chat</Link>:
        </p>
        <ul className="mt-2 list-inside list-disc space-y-1 text-sm text-slate-600">
          <li>&quot;Write me a one-page business plan for my coffee shop.&quot;</li>
          <li>&quot;Draft a follow-up email to a client about a delayed delivery.&quot;</li>
          <li>&quot;Propose a meeting with my co-founder next week.&quot;</li>
          <li>&quot;Create a SWOT analysis for my business.&quot;</li>
        </ul>
      </div>
    </div>
  );
}

export default function DashboardPage() {
  return (
    <ProtectedRoute>
      <AppShell>
        <DashboardContent />
      </AppShell>
    </ProtectedRoute>
  );
}
