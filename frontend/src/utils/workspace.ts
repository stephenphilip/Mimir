import type { Conversation } from "../types";

export interface Project {
  id: string;
  name: string;
}

export interface WorkspaceState {
  projects: Project[];
  pinned: string[];
  archived: string[];
  projectByChat: Record<string, string>;
  titleOverrides: Record<string, string>;
}

const KEY = "mimir.workspace.v1";

const DEFAULT: WorkspaceState = {
  projects: [],
  pinned: [],
  archived: [],
  projectByChat: {},
  titleOverrides: {},
};

export function loadWorkspace(): WorkspaceState {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return { ...DEFAULT, projects: [] };
    const parsed = JSON.parse(raw) as WorkspaceState;
    return {
      projects: parsed.projects || [],
      pinned: parsed.pinned || [],
      archived: parsed.archived || [],
      projectByChat: parsed.projectByChat || {},
      titleOverrides: parsed.titleOverrides || {},
    };
  } catch {
    return { ...DEFAULT, projects: [] };
  }
}

export function saveWorkspace(state: WorkspaceState): void {
  localStorage.setItem(KEY, JSON.stringify(state));
}

export function enrichConversations(
  conversations: Conversation[],
  ws: WorkspaceState
): Conversation[] {
  return conversations.map((c) => ({
    ...c,
    title: ws.titleOverrides[c.id] || c.title,
    pinned: ws.pinned.includes(c.id),
    archived: ws.archived.includes(c.id),
    project_id: ws.projectByChat[c.id],
  }));
}

export function newId(prefix: string): string {
  return `${prefix}_${Math.random().toString(36).slice(2, 10)}`;
}
