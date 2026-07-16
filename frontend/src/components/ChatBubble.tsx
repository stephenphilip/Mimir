import { AlertTriangle, Check, Copy, Terminal } from "lucide-react";
import { useState } from "react";
import type { Message, TimelineStep } from "../types";
import { displayContent, mergeArtifacts, parseArtifactsFromText } from "../utils/artifacts";
import { ArtifactCard } from "./ArtifactCard";
import { ExecutionTimeline } from "./ExecutionTimeline";
import { MarkdownContent } from "./MarkdownContent";
import { MessageActions } from "./MessageActions";
import { messageAnchorId } from "./ChatOutline";

interface Props {
  message: Message;
  index: number;
  timeline?: TimelineStep[];
  isLive?: boolean;
  error?: string | null;
  onRetry?: () => void;
  actionsDisabled?: boolean;
}

export function ChatBubble({
  message,
  index,
  timeline,
  isLive,
  error,
  onRetry,
  actionsDisabled,
}: Props) {
  const [copiedTop, setCopiedTop] = useState(false);
  const structured = message.artifacts || message.executionResult?.artifacts || [];
  const parsed = parseArtifactsFromText(
    `${message.content}\n${message.executionResult?.stdout || ""}`
  );
  const artifacts = mergeArtifacts(structured, parsed);
  const content = displayContent(message.content, artifacts);
  const anchorId = messageAnchorId(message, index);

  const copyAll = async () => {
    if (!content) return;
    try {
      await navigator.clipboard.writeText(content);
      setCopiedTop(true);
      window.setTimeout(() => setCopiedTop(false), 1200);
    } catch {
      /* ignore */
    }
  };

  return (
    <div
      id={anchorId}
      className={`message-row ${message.sender}`}
      data-sender={message.sender}
      data-anchor={anchorId}
    >
      <div className={`message-bubble ${message.sender === "user" ? "is-user" : "is-assistant"}`}>
        {!isLive && message.sender === "assistant" && content && (
          <div className="bubble-topbar">
            <span className="bubble-role">Mimir</span>
            <button
              type="button"
              className="snippet-copy-btn icon-only"
              onClick={copyAll}
              disabled={actionsDisabled}
              aria-label={copiedTop ? "Copied response" : "Copy response"}
              title={copiedTop ? "Copied" : "Copy"}
            >
              {copiedTop ? <Check size={14} /> : <Copy size={14} />}
            </button>
          </div>
        )}

        {timeline && timeline.length > 0 && <ExecutionTimeline steps={timeline} />}

        {content &&
          (message.sender === "assistant" ? (
            <MarkdownContent content={content} />
          ) : (
            <p className="user-text">{content}</p>
          ))}

        {message.executionResult && (message.executionResult.stdout || message.executionResult.stderr) && (
          <details className="exec-console">
            <summary>
              <Terminal size={12} aria-hidden="true" />
              Python console · {message.executionResult.success ? "Success" : "Failed"}
            </summary>
            <pre>{message.executionResult.stdout || message.executionResult.stderr}</pre>
          </details>
        )}

        {artifacts.length > 0 && (
          <div className="artifacts-gallery" role="list">
            {artifacts.map((art) => (
              <div key={String(art.id)} role="listitem">
                <ArtifactCard artifact={art} />
              </div>
            ))}
          </div>
        )}

        {error && (
          <div className="stream-error" role="alert">
            <AlertTriangle size={15} />
            <span>{error}</span>
          </div>
        )}

        {!isLive && message.sender === "assistant" && (content || artifacts.length > 0) && (
          <MessageActions
            messageKey={anchorId}
            content={content}
            timestamp={message.created_at}
            onRetry={onRetry}
            disabled={actionsDisabled}
          />
        )}
      </div>
    </div>
  );
}
