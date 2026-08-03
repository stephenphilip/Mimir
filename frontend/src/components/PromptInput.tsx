import { Mic, Plus, Search, SendHorizontal, Sparkles, Upload } from "lucide-react";
import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import type { AttachedFile } from "../types";
import { FileUploader, buildPromptWithAttachments } from "./FileUploader";

interface Props {
  value: string;
  onChange: (value: string) => void;
  files: AttachedFile[];
  onFilesChange: (files: AttachedFile[]) => void;
  onSend: (finalPrompt: string) => void;
  disabled?: boolean;
  placeholder?: string;
  compact?: boolean;
  promptStudioEnabled?: boolean;
  onPromptStudioToggle?: (enabled: boolean) => void;
  onOpenPromptStudio?: () => void;
  researchModeEnabled?: boolean;
  onResearchModeToggle?: (enabled: boolean) => void;
}

export function PromptInput({
  value,
  onChange,
  files,
  onFilesChange,
  onSend,
  disabled,
  placeholder = "Ask Mimir anything...",
  compact,
  promptStudioEnabled = false,
  onPromptStudioToggle,
  onOpenPromptStudio,
  researchModeEnabled = false,
  onResearchModeToggle,
}: Props) {
  const taRef = useRef<HTMLTextAreaElement>(null);
  const [showUploader, setShowUploader] = useState(files.length > 0);
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (files.length > 0) setShowUploader(true);
  }, [files.length]);

  useEffect(() => {
    const el = taRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 180)}px`;
  }, [value]);

  useEffect(() => {
    if (!menuOpen) return;
    const onDoc = (e: MouseEvent) => {
      const target = e.target as Node;
      if (!menuRef.current?.contains(target)) setMenuOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [menuOpen]);

  const submit = () => {
    const trimmed = value.trim();
    if (!trimmed || disabled) return;
    if (promptStudioEnabled && onOpenPromptStudio) {
      onOpenPromptStudio();
      return;
    }
    onSend(buildPromptWithAttachments(trimmed, files));
  };

  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  };

  return (
    <div className={`prompt-shell ${compact ? "is-compact" : ""}`}>
      {(showUploader || files.length > 0) && (
        <FileUploader files={files} onChange={onFilesChange} disabled={disabled} />
      )}

      <div className="prompt-bar" role="group" aria-label="Message composer">
        <div className="composer-plus-wrap" ref={menuRef}>
          <button
            type="button"
            className="icon-btn prompt-action"
            aria-label="Composer options"
            title="Options"
            disabled={disabled}
            onClick={() => setMenuOpen((v) => !v)}
          >
            <Plus size={18} />
          </button>

          {menuOpen && (
            <div className="composer-plus-menu glass-panel" role="menu">
              <button
                type="button"
                className="composer-plus-item"
                role="menuitem"
                onClick={() => {
                  setShowUploader(true);
                  setMenuOpen(false);
                }}
              >
                <Upload size={14} /> Upload files
              </button>

              <label className="composer-plus-toggle" role="menuitem">
                <input
                  type="checkbox"
                  checked={promptStudioEnabled}
                  onChange={(e) => onPromptStudioToggle?.(e.target.checked)}
                  disabled={disabled}
                />
                <Sparkles size={14} /> Prompt Studio
              </label>

              <label className="composer-plus-toggle" role="menuitem">
                <input
                  type="checkbox"
                  checked={researchModeEnabled}
                  onChange={(e) => onResearchModeToggle?.(e.target.checked)}
                  disabled={disabled}
                />
                <Search size={14} /> Research mode
              </label>
            </div>
          )}
        </div>

        <textarea
          ref={taRef}
          className="prompt-textarea"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={onKeyDown}
          placeholder={placeholder}
          disabled={disabled}
          rows={1}
          aria-label="Message"
        />

        <button
          type="button"
          className="icon-btn prompt-action is-muted"
          aria-label="Voice input coming soon"
          title="Microphone (coming soon)"
          disabled
        >
          <Mic size={18} />
        </button>

        <button
          type="button"
          className="send-btn"
          aria-label="Send message"
          disabled={disabled || !value.trim()}
          onClick={submit}
        >
          <SendHorizontal size={18} />
        </button>
      </div>

      <div className="prompt-hint">
        <kbd>Enter</kbd> send · <kbd>Shift</kbd>+<kbd>Enter</kbd> new line
      </div>
    </div>
  );
}
