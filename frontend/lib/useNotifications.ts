import { useCallback, useEffect, useRef, useState } from "react";

import { api, wsUrl } from "./api";
import { getAccessToken } from "./auth";
import type { NotificationRead } from "./types";

export function useNotifications(enabled: boolean) {
  const [notifications, setNotifications] = useState<NotificationRead[]>([]);
  const socketRef = useRef<WebSocket | null>(null);

  const refresh = useCallback(async () => {
    try {
      const items = await api.get<NotificationRead[]>("/api/v1/notifications");
      setNotifications(items);
    } catch {
      // not authenticated yet or backend unreachable — ignore, will retry on next mount
    }
  }, []);

  useEffect(() => {
    if (!enabled) return;
    refresh();

    const token = getAccessToken();
    if (!token) return;

    // Token is sent as the first message, not in the URL, so it is never
    // captured by server access logs or browser history.
    const socket = new WebSocket(wsUrl("/api/v1/notifications/ws"));
    socketRef.current = socket;

    socket.onopen = () => {
      socket.send(JSON.stringify({ type: "auth", token }));
    };

    socket.onmessage = (event) => {
      const payload = JSON.parse(event.data) as NotificationRead;
      setNotifications((prev) => [payload, ...prev]);
    };

    return () => {
      socket.close();
      socketRef.current = null;
    };
  }, [enabled, refresh]);

  const markAllRead = useCallback(async () => {
    await api.post("/api/v1/notifications/read-all");
    setNotifications((prev) => prev.map((n) => ({ ...n, is_read: true })));
  }, []);

  const unreadCount = notifications.filter((n) => !n.is_read).length;

  return { notifications, unreadCount, markAllRead, refresh };
}
