import { useState } from "react";
import {
  MessageSquare,
  Store,
  Settings,
  Plus,
  Search,
  Pin,
  Sparkles,
  Folder,
  Pencil,
  FolderOpen,
  Activity,
  ChevronDown,
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
  onFocusChatSearch: () => void;
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
  developerToolsEnabled?: boolean;
}

export function Sidebar({
  view,
  onNavigate,
  conversations,
  activeConvId,
  onSelectChat,
  onNewChat,
  onFocusChatSearch,
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
  developerToolsEnabled = false,
}: Props) {
  const [collapsedProjects, setCollapsedProjects] = useState<Record<string, boolean>>({});
  const q = search.trim().toLowerCase();
  
  const visible = conversations.filter((c) => !c.archived);
  const pinned = visible.filter((c) => c.pinned);
  
  const filter = (list: Conversation[]) =>
    q ? list.filter((c) => c.title.toLowerCase().includes(q)) : list;

  const toggleProject = (id: string) => {
    setCollapsedProjects((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  const directChats = visible.filter((c) => !c.project_id);

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
        <button
          type="button"
          className={`side-nav-item ${view === "chats" ? "is-active" : ""}`}
          onClick={() => {
            onSelectProject(null);
            onNavigate("chats");
          }}
          aria-current={view === "chats" ? "page" : undefined}
        >
          <MessageSquare size={16} aria-hidden="true" />
          <span>Chats</span>
        </button>
        <button
          type="button"
          className={`side-nav-item ${view === "files" ? "is-active" : ""}`}
          onClick={() => onNavigate("files")}
          aria-current={view === "files" ? "page" : undefined}
        >
          <FolderOpen size={16} aria-hidden="true" />
          <span>Files</span>
        </button>
        {developerToolsEnabled && (
          <button
            type="button"
            className={`side-nav-item ${view === "runtime" ? "is-active" : ""}`}
            onClick={() => onNavigate("runtime")}
            aria-current={view === "runtime" ? "page" : undefined}
          >
            <Activity size={16} aria-hidden="true" />
            <span>Runtime</span>
          </button>
        )}
        <button
          type="button"
          className={`side-nav-item ${view === "marketplace" ? "is-active" : ""}`}
          onClick={() => onNavigate("marketplace")}
          aria-current={view === "marketplace" ? "page" : undefined}
        >
          <Store size={16} aria-hidden="true" />
          <span>Marketplace</span>
        </button>
      </nav>

      <div className="btn-new-chat-wrap">
        <button type="button" className="btn-new-chat" onClick={onNewChat}>
          <Plus size={16} />
          <span>New Chat</span>
        </button>
      </div>

      <div className="side-chats">
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
                onNewChat={onNewChat}
                onFocusChatSearch={onFocusChatSearch}
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

          <div className="projects-container">
            {projects.map((p) => {
              const projectChats = visible.filter((c) => c.project_id === p.id);
              const isCollapsed = collapsedProjects[p.id];
              const isSelected = activeProjectId === p.id;
              return (
                <div key={p.id} className={`project-group-wrap ${isSelected ? "is-selected" : ""}`}>
                  <div className="project-group-header">
                    <button
                      type="button"
                      className="project-group-toggle"
                      onClick={() => {
                        onSelectProject(p.id);
                        toggleProject(p.id);
                      }}
                    >
                      <ChevronDown
                        size={12}
                        className={`caret-icon ${isCollapsed ? "is-collapsed" : ""}`}
                      />
                      <Folder size={13} />
                      <span className="project-name">{p.name}</span>
                    </button>
                    <button
                      type="button"
                      className="icon-btn project-edit"
                      aria-label={`Rename ${p.name}`}
                      onClick={() => onRenameProject(p.id)}
                    >
                      <Pencil size={11} />
                    </button>
                  </div>
                  {!isCollapsed && (
                    <div className="project-group-chats">
                      {filter(projectChats).length === 0 ? (
                        <p className="side-empty-project">No chats in project</p>
                      ) : (
                        filter(projectChats).map((c) => (
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
                  )}
                </div>
              );
            })}
          </div>
        </div>

        <div className="chat-group">
          <div className="chat-group-title">Direct Chats</div>
          {filter(directChats).length === 0 ? (
            <p className="side-empty">No direct chats</p>
          ) : (
            filter(directChats).map((c) => (
              <ChatRow
                key={c.id}
                conv={c}
                projects={projects}
                active={activeConvId === c.id}
                onSelect={() => {
                  onSelectChat(c.id);
                  onNavigate("chats");
                }}
                onNewChat={onNewChat}
                onFocusChatSearch={onFocusChatSearch}
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

      <div className="sidebar-bottom">
        <button
          type="button"
          className={`side-nav-item bottom-settings ${view === "settings" ? "is-active" : ""}`}
          onClick={() => onNavigate("settings")}
        >
          <Settings size={16} />
          <span>Settings</span>
        </button>
      </div>
    </aside>
  );
}

function ChatRow({
  conv,
  projects,
  active,
  onSelect,
  onNewChat,
  onFocusChatSearch,
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
  onNewChat: () => void;
  onFocusChatSearch: () => void;
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
        onNewChat={onNewChat}
        onFocusChatSearch={onFocusChatSearch}
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
