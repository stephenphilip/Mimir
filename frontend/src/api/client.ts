import type { Conversation, Message, SystemStatus } from "../types";

export const BACKEND_URL = "http://localhost:8000";

async function json<T>(path: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(`${BACKEND_URL}${path}`, init);
  if (!resp.ok) {
    throw new Error(`${init?.method || "GET"} ${path} failed (${resp.status})`);
  }
  return resp.json() as Promise<T>;
}

export const api = {
  getConversations: () => json<Conversation[]>("/api/conversations"),
  createConversation: (projectId?: string | null) =>
    json<Conversation>("/api/conversations" + (projectId ? `?project_id=${projectId}` : ""), { method: "POST" }),
  updateConversationProject: (id: string, projectId: string | null) =>
    json<{ status: string }>(`/api/conversations/${id}/project` + (projectId ? `?project_id=${projectId}` : ""), {
      method: "POST",
    }),
  deleteConversation: (id: string) =>
    json<{ status: string }>(`/api/conversations/${id}`, { method: "DELETE" }),
  getMessages: (id: string) => json<Message[]>(`/api/conversations/${id}/messages`),
  getSettings: () => json<Record<string, string>>("/api/settings"),
  saveSettings: (body: { user_name: string; personality: string; theme: string }) =>
    json<{ status: string }>("/api/settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  getSystemStatus: () => json<SystemStatus>("/api/system/status"),
  chatStream: (conversationId: string, prompt: string) =>
    fetch(`${BACKEND_URL}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ conversation_id: conversationId, prompt }),
    }),
  artifactUrl: (filePath: string) => {
    if (filePath.startsWith("http")) return filePath;
    return `${BACKEND_URL}${filePath.startsWith("/") ? "" : "/"}${filePath}`;
  },
};
