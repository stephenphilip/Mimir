import { useEffect, useRef, useState } from "react";
import type { Message } from "../types";

export interface OutlineItem {
  anchorId: string;
  label: string;
  index: number;
}

interface Props {
  items: OutlineItem[];
  activeId?: string | null;
  onJump: (anchorId: string) => void;
}

export function buildOutline(messages: Message[]): OutlineItem[] {
  return messages
    .map((m, index) => ({ m, index }))
    .filter(({ m }) => m.sender === "user")
    .map(({ m, index }) => ({
      anchorId: messageAnchorId(m, index),
      index,
      label: (m.content || "Untitled").replace(/\s+/g, " ").trim().slice(0, 90),
    }));
}

export function messageAnchorId(message: Message, index: number): string {
  if (message.id != null) return `msg-${message.id}`;
  return `msg-i-${index}`;
}

/**
 * ChatGPT-style collapsed context rail:
 * thin ticks on the right; hover opens a floating list of user prompts.
 */
export function ChatOutline({ items, activeId, onJump }: Props) {
  const [open, setOpen] = useState(false);
  const closeTimer = useRef<number | null>(null);
  const rootRef = useRef<HTMLDivElement>(null);

  const clearClose = () => {
    if (closeTimer.current != null) {
      window.clearTimeout(closeTimer.current);
      closeTimer.current = null;
    }
  };

  const scheduleClose = () => {
    clearClose();
    closeTimer.current = window.setTimeout(() => setOpen(false), 160);
  };

  useEffect(() => () => clearClose(), []);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  if (items.length === 0) return null;

  return (
    <div
      ref={rootRef}
      className={`context-rail ${open ? "is-open" : ""}`}
      onMouseEnter={() => {
        clearClose();
        setOpen(true);
      }}
      onMouseLeave={scheduleClose}
    >
      {/* Collapsed ticks — always visible, like OpenAI */}
      <div className="context-ticks" aria-hidden={!open}>
        {items.map((item) => (
          <button
            key={item.anchorId}
            type="button"
            className={`context-tick ${activeId === item.anchorId ? "is-active" : ""}`}
            aria-label={`Jump to: ${item.label}`}
            title={item.label}
            onFocus={() => {
              clearClose();
              setOpen(true);
            }}
            onClick={() => {
              onJump(item.anchorId);
              setOpen(false);
            }}
          />
        ))}
      </div>

      {/* Hover popover with clickable user chat snippets */}
      {open && (
        <div
          className="context-popover"
          role="menu"
          aria-label="Conversation context"
          onMouseEnter={clearClose}
          onMouseLeave={scheduleClose}
        >
          {items.map((item) => (
            <button
              key={item.anchorId}
              type="button"
              role="menuitem"
              className={`context-popover-item ${activeId === item.anchorId ? "is-active" : ""}`}
              onClick={() => {
                onJump(item.anchorId);
                setOpen(false);
              }}
            >
              {item.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
