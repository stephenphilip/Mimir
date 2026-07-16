import {
  forwardRef,
  useCallback,
  useEffect,
  useImperativeHandle,
  useRef,
  useState,
} from "react";
import type { Message, TimelineStep } from "../types";
import { ChatBubble } from "./ChatBubble";
import { buildOutline, ChatOutline } from "./ChatOutline";

export interface ChatWindowHandle {
  scrollToAnchor: (anchorId: string) => void;
  scrollToBottom: () => void;
}

interface Props {
  messages: Message[];
  liveMessage?: Message | null;
  liveTimeline?: TimelineStep[];
  streamError?: string | null;
  isGenerating?: boolean;
  onRetryMessage?: (assistantIndex: number) => void;
}

export const ChatWindow = forwardRef<ChatWindowHandle, Props>(function ChatWindow(
  {
    messages,
    liveMessage,
    liveTimeline,
    streamError,
    isGenerating,
    onRetryMessage,
  },
  ref
) {
  const feedRef = useRef<HTMLDivElement>(null);
  const stickToBottom = useRef(true);
  const [activeOutline, setActiveOutline] = useState<string | null>(null);
  const outline = buildOutline(messages);

  const isNearBottom = (el: HTMLElement) =>
    el.scrollHeight - el.scrollTop - el.clientHeight < 120;

  const scrollToBottom = useCallback((smooth = true) => {
    const el = feedRef.current;
    if (!el) return;
    el.scrollTo({ top: el.scrollHeight, behavior: smooth ? "smooth" : "auto" });
  }, []);

  const scrollToAnchor = useCallback((anchorId: string) => {
    const el = feedRef.current;
    if (!el) return;
    const target = el.querySelector<HTMLElement>(`#${CSS.escape(anchorId)}`);
    if (!target) return;
    stickToBottom.current = false;
    target.scrollIntoView({ behavior: "smooth", block: "start" });
    setActiveOutline(anchorId);
    target.classList.add("is-flash");
    window.setTimeout(() => target.classList.remove("is-flash"), 900);
  }, []);

  useImperativeHandle(ref, () => ({ scrollToAnchor, scrollToBottom }), [
    scrollToAnchor,
    scrollToBottom,
  ]);

  useEffect(() => {
    const el = feedRef.current;
    if (!el) return;

    const onScroll = () => {
      stickToBottom.current = isNearBottom(el);

      // Highlight outline item for the user turn nearest the viewport top
      const nodes = Array.from(el.querySelectorAll<HTMLElement>(".message-row[data-sender='user']"));
      let current: string | null = null;
      for (const node of nodes) {
        const top = node.getBoundingClientRect().top - el.getBoundingClientRect().top;
        if (top <= 80) current = node.dataset.anchor || null;
      }
      if (current) setActiveOutline(current);
    };

    el.addEventListener("scroll", onScroll, { passive: true });
    return () => el.removeEventListener("scroll", onScroll);
  }, []);

  // Auto-scroll only while the user is already near the bottom (or generating fresh)
  useEffect(() => {
    if (!stickToBottom.current && !isGenerating) return;
    if (isGenerating || stickToBottom.current) {
      scrollToBottom(Boolean(liveMessage?.content));
    }
  }, [messages.length, liveMessage?.content, liveTimeline, isGenerating, scrollToBottom]);

  return (
    <div className="chat-layout">
      <div
        className="chat-feed"
        ref={feedRef}
        role="log"
        aria-live="polite"
        aria-relevant="additions"
      >
        {messages.map((msg, i) => (
          <ChatBubble
            key={msg.id ?? `${msg.sender}-${i}`}
            message={msg}
            index={i}
            actionsDisabled={isGenerating}
            onRetry={
              msg.sender === "assistant" && onRetryMessage
                ? () => onRetryMessage(i)
                : undefined
            }
          />
        ))}

        {isGenerating && liveMessage && (
          <ChatBubble
            message={liveMessage}
            index={messages.length}
            timeline={liveTimeline}
            isLive
            error={streamError}
          />
        )}

        {!isGenerating && streamError && (
          <ChatBubble
            message={{ sender: "assistant", content: "" }}
            index={messages.length}
            error={streamError}
          />
        )}
      </div>

      {/* Collapsed OpenAI-style context rail (ticks → hover popover) */}
      <ChatOutline items={outline} activeId={activeOutline} onJump={scrollToAnchor} />
    </div>
  );
});
