"use client";

import { useEffect, useState } from "react";

import { AppShell } from "@/components/AppShell";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { api, ApiError } from "@/lib/api";
import type { CalendarEventDraftRead } from "@/lib/types";

const STATUS_STYLES: Record<string, string> = {
  pending_approval: "bg-amber-100 text-amber-700",
  approved: "bg-blue-100 text-blue-700",
  created: "bg-green-100 text-green-700",
  rejected: "bg-slate-100 text-slate-500",
  failed: "bg-red-100 text-red-700",
};

function formatRange(start: string, end: string): string {
  const startDate = new Date(start);
  const endDate = new Date(end);
  return `${startDate.toLocaleString()} - ${endDate.toLocaleTimeString()}`;
}

function CalendarContent() {
  const [events, setEvents] = useState<CalendarEventDraftRead[]>([]);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    const items = await api.get<CalendarEventDraftRead[]>("/api/v1/calendar/events");
    setEvents(items);
  }

  useEffect(() => {
    refresh().catch(() => {});
  }, []);

  async function approve(id: string) {
    setBusyId(id);
    setError(null);
    try {
      await api.post(`/api/v1/calendar/events/${id}/approve`);
      await refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to create the calendar event.");
    } finally {
      setBusyId(null);
    }
  }

  async function reject(id: string) {
    setBusyId(id);
    try {
      await api.post(`/api/v1/calendar/events/${id}/reject`);
      await refresh();
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div>
      <h1 className="text-xl font-semibold text-slate-900 sm:text-2xl">Calendar</h1>
      <p className="mt-1 text-slate-500">
        Meetings your Calendar Agent proposed. Nothing is added to your real calendar until you approve it.
      </p>
      {error && <p className="mt-2 text-sm text-red-600">{error}</p>}

      <div className="mt-6 space-y-4">
        {events.map((event) => (
          <div key={event.id} className="rounded-xl border border-slate-200 bg-white p-5">
            <div className="flex items-start justify-between gap-4">
              <div className="min-w-0 flex-1">
                <p className="break-words font-medium text-slate-900">{event.title}</p>
                <p className="text-xs text-slate-400">{formatRange(event.start_time, event.end_time)}</p>
              </div>
              <span
                className={`shrink-0 rounded-full px-2.5 py-1 text-xs font-medium ${STATUS_STYLES[event.status] || ""}`}
              >
                {event.status.replace(/_/g, " ")}
              </span>
            </div>
            {event.description && (
              <p className="mt-3 break-words text-sm text-slate-600">{event.description}</p>
            )}
            {event.attendees.length > 0 && (
              <p className="mt-2 break-words text-xs text-slate-400">
                Attendees: {event.attendees.join(", ")}
              </p>
            )}

            {event.status === "pending_approval" && (
              <div className="mt-4 flex flex-wrap gap-2">
                <button
                  onClick={() => approve(event.id)}
                  disabled={busyId === event.id}
                  className="rounded-md bg-slate-900 px-3 py-2 text-xs font-medium text-white hover:bg-slate-800 disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-400 focus-visible:ring-offset-1"
                >
                  Approve &amp; schedule
                </button>
                <button
                  onClick={() => reject(event.id)}
                  disabled={busyId === event.id}
                  className="rounded-md border border-slate-300 px-3 py-2 text-xs font-medium text-slate-600 hover:bg-slate-50 disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-400 focus-visible:ring-offset-1"
                >
                  Reject
                </button>
              </div>
            )}
          </div>
        ))}
        {events.length === 0 && (
          <p className="text-sm text-slate-400">
            No meeting proposals yet -- ask your assistant in Chat to schedule one.
          </p>
        )}
      </div>
    </div>
  );
}

export default function CalendarPage() {
  return (
    <ProtectedRoute>
      <AppShell>
        <CalendarContent />
      </AppShell>
    </ProtectedRoute>
  );
}
