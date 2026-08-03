import type {
  Artifact,
  Conversation,
  ManagedFile,
  MarketplaceItem,
  Message,
  PromptStudioResult,
  RuntimeDashboard,
  SystemStatus,
  Workspace,
} from "../types";

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
  createConversation: () =>
    json<Conversation>("/api/conversations", { method: "POST" }),
  deleteConversation: (id: string) =>
    json<{ status: string }>(`/api/conversations/${id}`, { method: "DELETE" }),
  getMessages: (id: string) => json<Message[]>(`/api/conversations/${id}/messages`),
  getSettings: () => json<Record<string, string>>("/api/settings"),
  saveSettings: (body: {
    user_name: string;
    personality: string;
    theme: string;
    ui_responsive_layout?: string;
    prompt_studio_default?: string;
    developer_tools_enabled?: string;
    show_runtime_task_manager?: string;
  }) =>
    json<{ status: string }>("/api/settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  getSystemStatus: () => json<SystemStatus>("/api/system/status"),
  getRuntimeDashboard: () => json<RuntimeDashboard>("/api/runtime/dashboard"),
  getWorkspaces: () => json<Workspace[]>("/api/workspaces"),
  createWorkspace: (name: string, model?: string) =>
    json<Workspace>("/api/workspaces", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, model }),
    }),
  updateWorkspace: (id: string, body: { name?: string; model?: string }) =>
    json<Workspace>(`/api/workspaces/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  deleteWorkspace: (id: string) =>
    json<{ status: string }>(`/api/workspaces/${id}`, { method: "DELETE" }),
  listArtifacts: (params?: { workspace_id?: string; artifact_type?: string }) => {
    const q = new URLSearchParams();
    if (params?.workspace_id) q.set("workspace_id", params.workspace_id);
    if (params?.artifact_type) q.set("artifact_type", params.artifact_type);
    const qs = q.toString();
    return json<Artifact[]>(`/api/artifacts${qs ? `?${qs}` : ""}`);
  },
  listFiles: (params?: {
    workspace_id?: string;
    category?: string;
    search?: string;
    pinned_only?: boolean;
  }) => {
    const q = new URLSearchParams();
    if (params?.workspace_id) q.set("workspace_id", params.workspace_id);
    if (params?.category) q.set("category", params.category);
    if (params?.search) q.set("search", params.search);
    if (params?.pinned_only) q.set("pinned_only", "true");
    const qs = q.toString();
    return json<ManagedFile[]>(`/api/files${qs ? `?${qs}` : ""}`);
  },
  uploadFile: async (file: File, workspaceId?: string) => {
    const form = new FormData();
    form.append("file", file);
    const q = workspaceId ? `?workspace_id=${encodeURIComponent(workspaceId)}` : "";
    const resp = await fetch(`${BACKEND_URL}/api/files/upload${q}`, {
      method: "POST",
      body: form,
    });
    if (!resp.ok) throw new Error("Upload failed");
    return resp.json() as Promise<ManagedFile>;
  },
  renameFile: (id: string, file_name: string) =>
    json<ManagedFile>(`/api/files/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ file_name }),
    }),
  pinFile: (id: string, pinned: boolean) =>
    json<ManagedFile>(`/api/files/${id}/pin`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ pinned }),
    }),
  deleteFile: (id: string) =>
    json<{ status: string }>(`/api/files/${id}`, { method: "DELETE" }),
  enhancePrompt: (prompt: string, model?: string) =>
    json<PromptStudioResult>("/api/prompt-studio/enhance", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prompt, model }),
    }),
  listPacks: () => json<MarketplaceItem[]>("/api/packs"),
  installPack: (pack_id: string) =>
    json<{ success: boolean; pack: MarketplaceItem }>("/api/packs/install", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ pack_id }),
    }),
  uninstallPack: (pack_id: string) =>
    json<{ success: boolean; pack: MarketplaceItem }>("/api/packs/uninstall", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ pack_id }),
    }),
  chatStream: (conversationId: string, prompt: string, workspaceId?: string) =>
    fetch(`${BACKEND_URL}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        conversation_id: conversationId,
        prompt,
        workspace_id: workspaceId,
      }),
    }),
  artifactUrl: (filePath: string) => {
    if (filePath.startsWith("http")) return filePath;
    if (filePath.startsWith("/api/")) return `${BACKEND_URL}${filePath}`;
    return `${BACKEND_URL}${filePath.startsWith("/") ? "" : "/"}${filePath}`;
  },
};
