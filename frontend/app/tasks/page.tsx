"use client";

import { useEffect, useState } from "react";

import { AppShell } from "@/components/AppShell";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { api } from "@/lib/api";
import type { TaskRead } from "@/lib/types";

function TasksContent() {
  const [tasks, setTasks] = useState<TaskRead[]>([]);
  const [title, setTitle] = useState("");

  async function refresh() {
    const items = await api.get<TaskRead[]>("/api/v1/tasks");
    setTasks(items);
  }

  useEffect(() => {
    refresh().catch(() => {});
  }, []);

  async function addTask(e: React.FormEvent) {
    e.preventDefault();
    if (!title.trim()) return;
    await api.post("/api/v1/tasks", { title });
    setTitle("");
    await refresh();
  }

  async function toggleStatus(task: TaskRead) {
    const nextStatus = task.status === "done" ? "open" : "done";
    await api.patch(`/api/v1/tasks/${task.id}`, { status: nextStatus });
    await refresh();
  }

  async function removeTask(id: string) {
    await api.delete(`/api/v1/tasks/${id}`);
    await refresh();
  }

  return (
    <div>
      <h1 className="text-xl font-semibold text-slate-900 sm:text-2xl">Tasks</h1>
      <p className="mt-1 text-slate-500">Things to follow up on -- yours or created by your assistant.</p>

      <form
        onSubmit={addTask}
        className="mt-6 flex flex-col gap-3 rounded-xl border border-slate-200 bg-white p-4 sm:flex-row"
      >
        <input
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="Add a task..."
          className="min-w-0 flex-1 rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none focus:ring-2 focus:ring-slate-300"
        />
        <button
          type="submit"
          className="rounded-md bg-slate-900 px-4 py-2.5 text-sm font-medium text-white hover:bg-slate-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-400 focus-visible:ring-offset-1 sm:py-2"
        >
          Add
        </button>
      </form>

      <div className="mt-6 space-y-2">
        {tasks.map((task) => (
          <div
            key={task.id}
            className="flex items-center justify-between gap-3 rounded-lg border border-slate-200 bg-white px-4 py-3"
          >
            <div className="flex min-w-0 flex-1 items-center gap-3">
              <input
                type="checkbox"
                checked={task.status === "done"}
                onChange={() => toggleStatus(task)}
                className="h-5 w-5 shrink-0"
              />
              <div className="min-w-0 flex-1">
                <p
                  className={`break-words text-sm ${task.status === "done" ? "text-slate-400 line-through" : "text-slate-800"}`}
                >
                  {task.title}
                </p>
                {task.description && (
                  <p className="break-words text-xs text-slate-400">{task.description}</p>
                )}
              </div>
            </div>
            <button
              onClick={() => removeTask(task.id)}
              className="shrink-0 rounded px-2 py-2 text-xs text-slate-400 hover:text-red-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-400 focus-visible:ring-offset-1"
            >
              Delete
            </button>
          </div>
        ))}
        {tasks.length === 0 && <p className="text-sm text-slate-400">No tasks yet.</p>}
      </div>
    </div>
  );
}

export default function TasksPage() {
  return (
    <ProtectedRoute>
      <AppShell>
        <TasksContent />
      </AppShell>
    </ProtectedRoute>
  );
}
