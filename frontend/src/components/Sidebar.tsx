import {
  Home,
  MessageSquare,
  Box,
  Store,
  Brain,
  Settings,
  Plus,
  Search,
  Pin,
  Sparkles,
  Folder,
  Pencil,
} from "lucide-react";
import type { Conversation, NavView } from "../types";
import type { Project } from "../utils/workspace";
import { ChatContextMenu } from "./ChatContextMenu";

interface Props {
  view: NavView;
  onNavigate: (view: NavView) => void;
  conversations: Conversation[];
  activeConvId: string;
  onSelectChat: (id: string) => void;
  onNewChat: () => void;
  onDeleteChat: (id: string) => void;
  search: string;
  onSearchChange: (value: string) => void;
  projects: Project[];
  activeProjectId: string | null;
  onSelectProject: (id: string | null) => void;
  onCreateProject: () => void;
  onRenameProject: (id: string) => void;
  onPinChat: (id: string) => void;
  onArchiveChat: (id: string) => void;
  onRenameChat: (id: string) => void;
  onShareChat: (id: string) => void;
  onMoveChatToProject: (chatId: string, projectId: string | null) => void;
  onStartGroup: (id: string) => void;
}

const NAV: { id: NavView; label: string; icon: typeof Home; soon?: boolean }[] = [
  { id: "home", label: "Home", icon: Home },
  { id: "chats", label: "Chats", icon: MessageSquare },
  { id: "models", label: "Models", icon: Box },
  { id: "marketplace", label: "Marketplace", icon: Store, soon: true },
  { id: "memory", label: "Memory", icon: Brain, soon: true },
  { id: "settings", label: "Settings", icon: Settings },
];

export function Sidebar({
  view,
  onNavigate,
  conversations,
  activeConvId,
  onSelectChat,
  onNewChat,
  onDeleteChat,
  search,
  onSearchChange,
  projects,
  activeProjectId,
  onSelectProject,
  onCreateProject,
  onRenameProject,
  onPinChat,
  onArchiveChat,
  onRenameChat,
  onShareChat,
  onMoveChatToProject,
  onStartGroup,
}: Props) {
  const q = search.trim().toLowerCase();
  const visible = conversations.filter((c) => !c.archived);
  const pinned = visible.filter((c) => c.pinned);
  const inProject = (c: Conversation) =>
    activeProjectId ? c.project_id === activeProjectId : !c.project_id || !activeProjectId;
  // When a project is selected, show its chats; otherwise show chats not filtered by project for recent
  const recentBase = activeProjectId
    ? visible.filter((c) => c.project_id === activeProjectId && !c.pinned)
    : visible.filter((c) => !c.pinned);
  const filter = (list: Conversation[]) =>
    q ? list.filter((c) => c.title.toLowerCase().includes(q)) : list;

  return (
    <aside className="sidebar" aria-label="Primary">
      <div className="brand-row">
        <div className="brand-mark" aria-hidden="true">
          <Sparkles size={16} />
        </div>
        <div>
          <div className="brand-name">Mimir</div>
          <div className="brand-tag">Local AI OS</div>
        </div>
      </div>

      <nav className="side-nav" aria-label="Sections">
        {NAV.map((item) => {
          const Icon = item.icon;
          const active = view === item.id;
          return (
            <button
              key={item.id}
              type="button"
              className={`side-nav-item ${active ? "is-active" : ""}`}
              onClick={() => onNavigate(item.id)}
              aria-current={active ? "page" : undefined}
            >
              <Icon size={16} aria-hidden="true" />
              <span>{item.label}</span>
              {item.soon && <span className="soon-pill">Soon</span>}
            </button>
          );
        })}
      </nav>

      <div className="side-chats">
        <div className="side-chats-head">
          <span>Workspace</span>
          <button type="button" className="icon-btn" onClick={onNewChat} aria-label="New chat" title="New chat">
            <Plus size={15} />
          </button>
        </div>

        <label className="side-search">
          <Search size={14} aria-hidden="true" />
          <input
            value={search}
            onChange={(e) => onSearchChange(e.target.value)}
            placeholder="Search chats"
            aria-label="Search chats"
          />
        </label>

        {filter(pinned).length > 0 && (
          <div className="chat-group">
            <div className="chat-group-title">
              <Pin size={12} /> Pinned
            </div>
            {filter(pinned).map((c) => (
              <ChatRow
                key={c.id}
                conv={c}
                projects={projects}
                active={activeConvId === c.id}
                onSelect={() => {
                  onSelectChat(c.id);
                  onNavigate("chats");
                }}
                onDelete={() => onDeleteChat(c.id)}
                onPin={() => onPinChat(c.id)}
                onArchive={() => onArchiveChat(c.id)}
                onRename={() => onRenameChat(c.id)}
                onShare={() => onShareChat(c.id)}
                onMoveToProject={(pid) => onMoveChatToProject(c.id, pid)}
                onStartGroup={() => onStartGroup(c.id)}
              />
            ))}
          </div>
        )}

        <div className="chat-group">
          <div className="chat-group-title projects-head">
            <span>
              <Folder size={12} /> Projects
            </span>
            <button
              type="button"
              className="icon-btn"
              aria-label="New project"
              title="New project"
              onClick={onCreateProject}
            >
              <Plus size={13} />
            </button>
          </div>

          <button
            type="button"
            className={`project-row ${activeProjectId === null ? "is-active" : ""}`}
            onClick={() => onSelectProject(null)}
          >
            <Folder size={14} />
            <span>All chats</span>
          </button>

          {projects.map((p) => (
            <div key={p.id} className={`project-row-wrap ${activeProjectId === p.id ? "is-active" : ""}`}>
              <button type="button" className="project-row" onClick={() => onSelectProject(p.id)}>
                <Folder size={14} />
                <span>{p.name}</span>
              </button>
              <button
                type="button"
                className="icon-btn project-edit"
                aria-label={`Rename ${p.name}`}
                onClick={() => onRenameProject(p.id)}
              >
                <Pencil size={12} />
              </button>
            </div>
          ))}
        </div>

        <div className="chat-group">
          <div className="chat-group-title">
            {activeProjectId
              ? projects.find((p) => p.id === activeProjectId)?.name || "Chats"
              : "Chats"}
          </div>
          {filter(recentBase).length === 0 ? (
            <p className="side-empty">No chats yet</p>
          ) : (
            filter(recentBase).filter(inProject).map((c) => (
              <ChatRow
                key={c.id}
                conv={c}
                projects={projects}
                active={activeConvId === c.id}
                onSelect={() => {
                  onSelectChat(c.id);
                  onNavigate("chats");
                }}
                onDelete={() => onDeleteChat(c.id)}
                onPin={() => onPinChat(c.id)}
                onArchive={() => onArchiveChat(c.id)}
                onRename={() => onRenameChat(c.id)}
                onShare={() => onShareChat(c.id)}
                onMoveToProject={(pid) => onMoveChatToProject(c.id, pid)}
                onStartGroup={() => onStartGroup(c.id)}
              />
            ))
          )}
        </div>
      </div>
    </aside>
  );
}

function ChatRow({
  conv,
  projects,
  active,
  onSelect,
  onDelete,
  onPin,
  onArchive,
  onRename,
  onShare,
  onMoveToProject,
  onStartGroup,
}: {
  conv: Conversation;
  projects: Project[];
  active: boolean;
  onSelect: () => void;
  onDelete: () => void;
  onPin: () => void;
  onArchive: () => void;
  onRename: () => void;
  onShare: () => void;
  onMoveToProject: (projectId: string | null) => void;
  onStartGroup: () => void;
}) {
  return (
    <div className={`chat-row ${active ? "is-active" : ""}`}>
      <button type="button" className="chat-row-main" onClick={onSelect}>
        {conv.pinned ? <Pin size={13} aria-hidden="true" /> : <MessageSquare size={13} aria-hidden="true" />}
        <span>{conv.title || "New Chat"}</span>
      </button>
      <ChatContextMenu
        conv={conv}
        projects={projects}
        onPin={onPin}
        onArchive={onArchive}
        onRename={onRename}
        onDelete={onDelete}
        onShare={onShare}
        onMoveToProject={onMoveToProject}
        onStartGroup={onStartGroup}
      />
    </div>
  );
}
