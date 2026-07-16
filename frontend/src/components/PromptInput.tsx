import { Mic, Paperclip, SendHorizontal } from "lucide-react";
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
}: Props) {
  const taRef = useRef<HTMLTextAreaElement>(null);
  const [showUploader, setShowUploader] = useState(files.length > 0);

  useEffect(() => {
    if (files.length > 0) setShowUploader(true);
  }, [files.length]);

  useEffect(() => {
    const el = taRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 180)}px`;
  }, [value]);

  const submit = () => {
    const trimmed = value.trim();
    if (!trimmed || disabled) return;
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
        <button
          type="button"
          className="icon-btn prompt-action"
          aria-label="Attach files"
          title="Attach files"
          disabled={disabled}
          onClick={() => setShowUploader((v) => !v)}
        >
          <Paperclip size={18} />
        </button>

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
