"use client";

import { useState } from "react";

import { useNotifications } from "@/lib/useNotifications";

export function NotificationBell() {
  const { notifications, unreadCount, markAllRead } = useNotifications(true);
  const [open, setOpen] = useState(false);

  return (
    <div className="relative">
      <button
        onClick={() => setOpen((o) => !o)}
        className="relative flex h-11 w-11 items-center justify-center rounded-full text-slate-600 hover:bg-slate-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-400 focus-visible:ring-offset-1"
        aria-label="Notifications"
        aria-expanded={open}
      >
        🔔
        {unreadCount > 0 && (
          <span className="absolute right-1 top-1 flex h-4 w-4 items-center justify-center rounded-full bg-red-500 text-[10px] font-bold text-white">
            {unreadCount > 9 ? "9+" : unreadCount}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 z-20 mt-2 w-[min(20rem,calc(100vw-2rem))] rounded-lg border border-slate-200 bg-white shadow-lg">
          <div className="flex items-center justify-between border-b border-slate-100 px-4 py-2">
            <span className="text-sm font-semibold text-slate-800">Notifications</span>
            <button
              onClick={markAllRead}
              className="text-xs font-medium text-blue-600 hover:underline"
            >
              Mark all read
            </button>
          </div>
          <div className="max-h-96 overflow-y-auto">
            {notifications.length === 0 && (
              <p className="px-4 py-6 text-center text-sm text-slate-400">No notifications yet.</p>
            )}
            {notifications.map((n) => (
              <div
                key={n.id}
                className={`border-b border-slate-50 px-4 py-3 text-sm ${n.is_read ? "bg-white" : "bg-blue-50"}`}
              >
                <p className="break-words font-medium text-slate-800">{n.title}</p>
                {n.body && <p className="mt-0.5 break-words text-slate-500">{n.body}</p>}
                <p className="mt-1 text-[11px] text-slate-400">
                  {new Date(n.created_at).toLocaleString()}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
