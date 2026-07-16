import { Check, Copy, RefreshCw, ThumbsDown, ThumbsUp } from "lucide-react";
import { useEffect, useState } from "react";
import { formatTime } from "../utils/format";

export type Feedback = "up" | "down" | null;

interface Props {
  messageKey: string;
  content: string;
  timestamp?: string;
  disabled?: boolean;
  onRetry?: () => void;
}

function loadFeedback(key: string): Feedback {
  try {
    const raw = localStorage.getItem(`mimir-feedback:${key}`);
    if (raw === "up" || raw === "down") return raw;
  } catch {
    /* ignore */
  }
  return null;
}

function saveFeedback(key: string, value: Feedback) {
  try {
    if (!value) localStorage.removeItem(`mimir-feedback:${key}`);
    else localStorage.setItem(`mimir-feedback:${key}`, value);
  } catch {
    /* ignore */
  }
}

export function MessageActions({ messageKey, content, timestamp, disabled, onRetry }: Props) {
  const [copied, setCopied] = useState(false);
  const [feedback, setFeedback] = useState<Feedback>(null);

  useEffect(() => {
    setFeedback(loadFeedback(messageKey));
  }, [messageKey]);

  const onCopy = async () => {
    try {
      await navigator.clipboard.writeText(content);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1400);
    } catch {
      /* ignore */
    }
  };

  const setFb = (value: Feedback) => {
    const next = feedback === value ? null : value;
    setFeedback(next);
    saveFeedback(messageKey, next);
  };

  return (
    <div className="message-actions" role="toolbar" aria-label="Response actions">
      {timestamp && <span className="message-time">{formatTime(timestamp)}</span>}

      <button
        type="button"
        className={`action-btn icon-only ${copied ? "is-on" : ""}`}
        onClick={onCopy}
        disabled={disabled || !content}
        aria-label={copied ? "Copied" : "Copy response"}
        title={copied ? "Copied" : "Copy"}
      >
        {copied ? <Check size={14} /> : <Copy size={14} />}
      </button>

      <button
        type="button"
        className={`action-btn ${feedback === "up" ? "is-good" : ""}`}
        onClick={() => setFb("up")}
        disabled={disabled}
        aria-label="Good response"
        aria-pressed={feedback === "up"}
        title="Good response"
      >
        <ThumbsUp size={14} />
        <span>Good</span>
      </button>

      <button
        type="button"
        className={`action-btn ${feedback === "down" ? "is-bad" : ""}`}
        onClick={() => setFb("down")}
        disabled={disabled}
        aria-label="Bad response"
        aria-pressed={feedback === "down"}
        title="Bad response"
      >
        <ThumbsDown size={14} />
        <span>Bad</span>
      </button>

      {onRetry && (
        <button
          type="button"
          className="action-btn"
          onClick={onRetry}
          disabled={disabled}
          aria-label="Try again"
          title="Try again"
        >
          <RefreshCw size={14} />
          <span>Try again</span>
        </button>
      )}
    </div>
  );
}
