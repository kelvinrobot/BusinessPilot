"use client";

import { useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import { AppShell } from "@/components/AppShell";
import { useAuth } from "@/components/AuthProvider";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { api, ApiError } from "@/lib/api";
import type { MemoryItemRead } from "@/lib/types";

interface GoogleStatus {
  connected: boolean;
  account_email: string | null;
}

function SettingsContent() {
  const { user } = useAuth();
  const searchParams = useSearchParams();
  const [googleStatus, setGoogleStatus] = useState<GoogleStatus | null>(null);
  const [memory, setMemory] = useState<MemoryItemRead[]>([]);
  const [connecting, setConnecting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [timezoneInput, setTimezoneInput] = useState(user?.timezone ?? "UTC");
  const [tzSaving, setTzSaving] = useState(false);
  const [tzSaved, setTzSaved] = useState(false);

  const oauthResult = searchParams.get("google");

  async function refreshGoogleStatus() {
    const status = await api.get<GoogleStatus>("/api/v1/integrations/google/status");
    setGoogleStatus(status);
  }

  useEffect(() => {
    refreshGoogleStatus().catch(() => {});
    api.get<MemoryItemRead[]>("/api/v1/memory").then(setMemory).catch(() => {});
  }, []);

  async function connectGoogle() {
    setConnecting(true);
    setError(null);
    try {
      const { authorization_url } = await api.get<{ authorization_url: string }>(
        "/api/v1/integrations/google/connect"
      );
      window.location.href = authorization_url;
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not start Google connection.");
      setConnecting(false);
    }
  }

  async function disconnectGoogle() {
    await api.delete("/api/v1/integrations/google");
    await refreshGoogleStatus();
  }

  async function saveTimezone() {
    setTzSaving(true);
    setTzSaved(false);
    try {
      await api.patch("/api/v1/auth/me", { timezone: timezoneInput });
      setTzSaved(true);
    } finally {
      setTzSaving(false);
    }
  }

  async function deleteMemoryItem(id: string) {
    await api.delete(`/api/v1/memory/${id}`);
    setMemory((prev) => prev.filter((m) => m.id !== id));
  }

  return (
    <div className="max-w-2xl space-y-8">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">Settings</h1>
        <p className="mt-1 text-slate-500">Manage your profile, integrations, and what BusinessPilot remembers.</p>
      </div>

      {oauthResult === "connected" && (
        <p className="rounded-md bg-green-50 px-4 py-2 text-sm text-green-700">
          Google account connected successfully.
        </p>
      )}
      {oauthResult === "error" && (
        <p className="rounded-md bg-red-50 px-4 py-2 text-sm text-red-700">
          Something went wrong connecting your Google account. Please try again.
        </p>
      )}

      <section className="rounded-xl border border-slate-200 bg-white p-5">
        <h2 className="text-sm font-semibold text-slate-700">Profile</h2>
        <p className="mt-2 text-sm text-slate-600">{user?.full_name}</p>
        <p className="text-sm text-slate-500">{user?.email}</p>
        {user?.business_name && <p className="text-sm text-slate-500">{user.business_name}</p>}
      </section>

      <section className="rounded-xl border border-slate-200 bg-white p-5">
        <h2 className="text-sm font-semibold text-slate-700">Google (Gmail + Calendar)</h2>
        <p className="mt-1 text-sm text-slate-500">
          Required for the Email and Calendar agents. Sending mail or creating events always requires your
          separate approval.
        </p>
        {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
        <div className="mt-3">
          {googleStatus?.connected ? (
            <div className="flex items-center justify-between">
              <span className="text-sm text-green-700">Connected{googleStatus.account_email ? ` as ${googleStatus.account_email}` : ""}</span>
              <button
                onClick={disconnectGoogle}
                className="rounded-md border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-50"
              >
                Disconnect
              </button>
            </div>
          ) : (
            <button
              onClick={connectGoogle}
              disabled={connecting}
              className="rounded-md bg-slate-900 px-3 py-1.5 text-xs font-medium text-white hover:bg-slate-800 disabled:opacity-50"
            >
              {connecting ? "Redirecting..." : "Connect Google account"}
            </button>
          )}
        </div>
      </section>

      <section className="rounded-xl border border-slate-200 bg-white p-5">
        <h2 className="text-sm font-semibold text-slate-700">Your timezone</h2>
        <p className="mt-1 text-sm text-slate-500">
          Used by the Calendar Agent to resolve dates like "tomorrow at 2 PM" correctly.
        </p>
        <div className="mt-3 flex items-center gap-2">
          <input
            value={timezoneInput}
            onChange={(e) => { setTimezoneInput(e.target.value); setTzSaved(false); }}
            placeholder="e.g. Africa/Lagos"
            className="flex-1 rounded-md border border-slate-300 px-3 py-1.5 text-sm focus:border-slate-500 focus:outline-none"
          />
          <button
            type="button"
            onClick={() => setTimezoneInput(Intl.DateTimeFormat().resolvedOptions().timeZone)}
            className="rounded-md border border-slate-300 px-3 py-1.5 text-xs text-slate-600 hover:bg-slate-50"
          >
            Auto-detect
          </button>
          <button
            type="button"
            onClick={saveTimezone}
            disabled={tzSaving}
            className="rounded-md bg-slate-900 px-3 py-1.5 text-xs font-medium text-white hover:bg-slate-800 disabled:opacity-50"
          >
            {tzSaving ? "Saving…" : "Save"}
          </button>
        </div>
        {tzSaved && <p className="mt-2 text-xs text-green-600">Timezone saved.</p>}
      </section>

      <section className="rounded-xl border border-slate-200 bg-white p-5">
        <h2 className="text-sm font-semibold text-slate-700">What BusinessPilot remembers</h2>
        <p className="mt-1 text-sm text-slate-500">
          Facts and preferences your assistant has picked up from your conversations.
        </p>
        <div className="mt-3 space-y-2">
          {memory.map((item) => (
            <div key={item.id} className="flex items-start justify-between gap-3 rounded-md bg-slate-50 px-3 py-2">
              <div>
                <p className="text-sm text-slate-700">{item.content}</p>
                <p className="text-xs text-slate-400">{item.category}</p>
              </div>
              <button onClick={() => deleteMemoryItem(item.id)} className="text-xs text-slate-400 hover:text-red-600">
                Forget
              </button>
            </div>
          ))}
          {memory.length === 0 && <p className="text-sm text-slate-400">Nothing remembered yet.</p>}
        </div>
      </section>
    </div>
  );
}

export default function SettingsPage() {
  return (
    <ProtectedRoute>
      <AppShell>
        <SettingsContent />
      </AppShell>
    </ProtectedRoute>
  );
}
