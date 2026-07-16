import {
  Archive,
  FolderInput,
  MoreHorizontal,
  Pencil,
  Pin,
  Share2,
  Trash2,
  Users,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import type { Conversation } from "../types";
import type { Project } from "../utils/workspace";

interface Props {
  conv: Conversation;
  projects: Project[];
  onPin: () => void;
  onArchive: () => void;
  onRename: () => void;
  onDelete: () => void;
  onShare: () => void;
  onMoveToProject: (projectId: string | null) => void;
  onStartGroup: () => void;
}

export function ChatContextMenu({
  conv,
  projects,
  onPin,
  onArchive,
  onRename,
  onDelete,
  onShare,
  onMoveToProject,
  onStartGroup,
}: Props) {
  const [open, setOpen] = useState(false);
  const [moveOpen, setMoveOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (!rootRef.current?.contains(e.target as Node)) {
        setOpen(false);
        setMoveOpen(false);
      }
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setOpen(false);
        setMoveOpen(false);
      }
    };
    document.addEventListener("mousedown", onDoc);
    window.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDoc);
      window.removeEventListener("keydown", onKey);
    };
  }, [open]);

  return (
    <div className="chat-menu" ref={rootRef}>
      <button
        type="button"
        className="icon-btn chat-menu-trigger"
        aria-label={`Options for ${conv.title}`}
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={(e) => {
          e.stopPropagation();
          setOpen((v) => !v);
          setMoveOpen(false);
        }}
      >
        <MoreHorizontal size={14} />
      </button>

      {open && (
        <div className="chat-menu-popover" role="menu">
          <button type="button" role="menuitem" onClick={() => { onShare(); setOpen(false); }}>
            <Share2 size={14} /> Share
          </button>
          <button type="button" role="menuitem" onClick={() => { onStartGroup(); setOpen(false); }}>
            <Users size={14} /> Start a group chat
          </button>
          <button type="button" role="menuitem" onClick={() => { onRename(); setOpen(false); }}>
            <Pencil size={14} /> Rename
          </button>

          <div className="chat-menu-submenu">
            <button
              type="button"
              role="menuitem"
              className="has-chevron"
              onClick={(e) => {
                e.stopPropagation();
                setMoveOpen((v) => !v);
              }}
            >
              <FolderInput size={14} />
              <span>Move to project</span>
              <span className="chev">›</span>
            </button>
            {moveOpen && (
              <div className="chat-menu-flyout" role="menu">
                <button
                  type="button"
                  role="menuitem"
                  onClick={() => {
                    onMoveToProject(null);
                    setOpen(false);
                  }}
                >
                  No project
                </button>
                {projects.map((p) => (
                  <button
                    key={p.id}
                    type="button"
                    role="menuitem"
                    onClick={() => {
                      onMoveToProject(p.id);
                      setOpen(false);
                    }}
                  >
                    {p.name}
                  </button>
                ))}
                {projects.length === 0 && (
                  <p className="chat-menu-hint">Create a project first</p>
                )}
              </div>
            )}
          </div>

          <div className="chat-menu-sep" />

          <button type="button" role="menuitem" onClick={() => { onPin(); setOpen(false); }}>
            <Pin size={14} /> {conv.pinned ? "Unpin chat" : "Pin chat"}
          </button>
          <button type="button" role="menuitem" onClick={() => { onArchive(); setOpen(false); }}>
            <Archive size={14} /> {conv.archived ? "Unarchive" : "Archive"}
          </button>
          <button
            type="button"
            role="menuitem"
            className="is-danger"
            onClick={() => {
              onDelete();
              setOpen(false);
            }}
          >
            <Trash2 size={14} /> Delete
          </button>
        </div>
      )}
    </div>
  );
}
