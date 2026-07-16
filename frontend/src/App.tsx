import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { api } from "./api/client";
import { CursorGlow } from "./components/CursorGlow";
import { ChatWindow, type ChatWindowHandle } from "./components/ChatWindow";
import { ComingSoon } from "./components/ComingSoon";
import { DownloadTray } from "./components/DownloadTray";
import { Greeting } from "./components/Greeting";
import { ModelsView } from "./components/ModelsView";
import { PromptInput } from "./components/PromptInput";
import { SettingsPanel } from "./components/SettingsPanel";
import { Sidebar } from "./components/Sidebar";
import { StatusBar } from "./components/StatusBar";
import type {
  AttachedFile,
  Conversation,
  ExecutionResult,
  Message,
  NavView,
  SystemStatus,
} from "./types";
import {
  mergeArtifacts,
  normalizeArtifact,
  parseArtifactsFromText,
  stripDownloadPlaceholders,
} from "./utils/artifacts";
import { buildTimeline } from "./utils/timeline";
import {
  enrichConversations,
  loadWorkspace,
  newId,
  saveWorkspace,
  type WorkspaceState,
} from "./utils/workspace";

export default function App() {
  const chatRef = useRef<ChatWindowHandle>(null);
  /** Full prompts (including attachments) for reliable Try again */
  const promptHistory = useRef<string[]>([]);
  const [view, setView] = useState<NavView>("home");
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeConvId, setActiveConvId] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [prompt, setPrompt] = useState("");
  const [files, setFiles] = useState<AttachedFile[]>([]);
  const [isGenerating, setIsGenerating] = useState(false);
  const [systemStatus, setSystemStatus] = useState<SystemStatus | null>(null);
  const [connected, setConnected] = useState(false);
  const [search, setSearch] = useState("");
  const [workspace, setWorkspace] = useState<WorkspaceState>(() => loadWorkspace());
  const [activeProjectId, setActiveProjectId] = useState<string | null>(null);

  const persistWorkspace = (next: WorkspaceState) => {
    setWorkspace(next);
    saveWorkspace(next);
  };

  const displayConversations = useMemo(
    () => enrichConversations(conversations, workspace),
    [conversations, workspace]
  );

  const [userName, setUserName] = useState("User");
  const [personality, setPersonality] = useState(
    "helpful, concise expert data analyst and assistant"
  );
  const [theme, setTheme] = useState("dark");

  const [pipeline, setPipeline] = useState<string[]>([]);
  const [streamText, setStreamText] = useState("");
  const [streamExecution, setStreamExecution] = useState<ExecutionResult | null>(null);
  const [streamError, setStreamError] = useState<string | null>(null);
  const [activeModel, setActiveModel] = useState<string | null>(null);
  const [liveDownloads, setLiveDownloads] = useState<Record<string, number>>({});

  const fetchConversations = useCallback(async () => {
    try {
      const data = await api.getConversations();
      setConversations(data);
      setConnected(true);
    } catch {
      setConnected(false);
    }
  }, []);

  const fetchMessages = useCallback(async (convId: string) => {
    try {
      const data = await api.getMessages(convId);
      setMessages((prev) => {
        const normalized = data.map((m) => ({
          ...m,
          artifacts: (m.artifacts || []).map((a) => normalizeArtifact(a)),
        }));

        // Preserve richer client-side artifacts if the DB row lags behind SSE
        if (prev.length && normalized.length) {
          const lastPrev = prev[prev.length - 1];
          const lastNext = normalized[normalized.length - 1];
          if (
            lastPrev.sender === "assistant" &&
            lastNext.sender === "assistant" &&
            (lastPrev.artifacts?.length || 0) > (lastNext.artifacts?.length || 0)
          ) {
            lastNext.artifacts = mergeArtifacts(lastNext.artifacts, lastPrev.artifacts);
            lastNext.executionResult = lastNext.executionResult || lastPrev.executionResult;
            if (!lastNext.content && lastPrev.content) {
              lastNext.content = lastPrev.content;
            }
          }
        }
        return normalized;
      });
    } catch (err) {
      console.error(err);
    }
  }, []);

  const fetchSystemStatus = useCallback(async () => {
    try {
      const data = await api.getSystemStatus();
      setSystemStatus(data);
      setConnected(true);
      // Drop finished pulls from the live overlay
      setLiveDownloads((prev) => {
        const next = { ...prev };
        for (const d of data.downloads || []) {
          if (d.status === "completed" || d.progress >= 100) {
            delete next[d.model_name];
          }
        }
        return next;
      });
    } catch {
      setConnected(false);
    }
  }, []);

  const fetchSettings = useCallback(async () => {
    try {
      const data = await api.getSettings();
      if (data.user_name) setUserName(data.user_name);
      if (data.personality) setPersonality(data.personality);
      if (data.theme) setTheme(data.theme);
    } catch (err) {
      console.error(err);
    }
  }, []);

  useEffect(() => {
    void fetchConversations();
    void fetchSystemStatus();
    void fetchSettings();
    const id = window.setInterval(() => void fetchSystemStatus(), 5000);
    return () => window.clearInterval(id);
  }, [fetchConversations, fetchSystemStatus, fetchSettings]);

  useEffect(() => {
    if (activeConvId && view === "chats") {
      void fetchMessages(activeConvId);
    }
  }, [activeConvId, view, fetchMessages]);

  const liveTimeline = useMemo(
    () =>
      buildTimeline(pipeline, {
        hasContent: Boolean(streamText),
        error: Boolean(streamError),
      }),
    [pipeline, streamText, streamError]
  );

  const liveMessage: Message | null = useMemo(() => {
    if (!isGenerating) return null;
    const artifacts = mergeArtifacts(
      streamExecution?.artifacts,
      parseArtifactsFromText(`${streamText}\n${streamExecution?.stdout || ""}`)
    );
    return {
      sender: "assistant",
      content: stripDownloadPlaceholders(streamText),
      artifacts,
      executionResult: streamExecution || undefined,
      isStreaming: true,
    };
  }, [isGenerating, streamText, streamExecution]);

  const ensureConversation = async (): Promise<string | null> => {
    if (activeConvId) return activeConvId;
    try {
      const data = await api.createConversation();
      setConversations((prev) => [data, ...prev]);
      setActiveConvId(data.id);
      return data.id;
    } catch {
      return null;
    }
  };

  const handleSend = async (finalPrompt: string) => {
    if (!finalPrompt.trim() || isGenerating) return;

    const convId = await ensureConversation();
    if (!convId) return;

    setView("chats");
    setPrompt("");
    setFiles([]);
    setIsGenerating(true);
    setStreamError(null);
    setPipeline([]);
    setStreamText("");
    setStreamExecution(null);

    const userVisible = finalPrompt.split("\n\n--- Attached file:")[0].trim() || finalPrompt;
    promptHistory.current = [...promptHistory.current, finalPrompt];
    setMessages((prev) => [...prev, { sender: "user", content: userVisible }]);

    // Locals avoid stale closures and preserve artifacts across "done"
    let contentAcc = "";
    let execAcc: ExecutionResult | null = null;
    const statusAcc: string[] = [];

    try {
      const response = await api.chatStream(convId, finalPrompt);
      if (!response.body) throw new Error("No response stream");

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split("\n\n");
        buffer = parts.pop() || "";

        for (const part of parts) {
          const line = part.trim();
          if (!line.startsWith("data: ")) continue;
          try {
            const payload = JSON.parse(line.slice(6));
            if (payload.type === "status") {
              statusAcc.push(payload.status);
              setPipeline([...statusAcc]);
              const m = String(payload.status).match(/model[:\s]+([^\s.]+)/i);
              if (m) setActiveModel(m[1]);
              if (String(payload.status).toLowerCase().includes("generating response using")) {
                const name = String(payload.status).replace(/^.*using\s+/i, "").replace(/\.\.\.$/, "");
                if (name) setActiveModel(name);
              }
            } else if (payload.type === "download_progress") {
              statusAcc.push(`Downloading ${payload.model} (${payload.progress}%)`);
              setPipeline([...statusAcc]);
              setLiveDownloads((prev) => ({
                ...prev,
                [payload.model]: Number(payload.progress) || 0,
              }));
            } else if (payload.type === "content") {
              contentAcc += payload.text;
              setStreamText(contentAcc);
            } else if (payload.type === "execution_result") {
              execAcc = {
                success: payload.success,
                stdout: payload.stdout,
                stderr: payload.stderr,
                exit_code: payload.exit_code,
                artifacts: (payload.artifacts || []).map((a: Record<string, unknown>) =>
                  normalizeArtifact({
                    id: a.id as number | string | undefined,
                    file_name: String(a.file_name || ""),
                    file_path: String(a.file_path || ""),
                    file_type: String(a.file_type || ""),
                    file_size: Number(a.file_size || 0),
                    source: "execution",
                  })
                ),
              };
              setStreamExecution(execAcc);
              statusAcc.push(
                execAcc.artifacts.some((a) => a.file_type === "pdf")
                  ? "Generating PDF"
                  : "Running Python"
              );
              setPipeline([...statusAcc]);
            } else if (payload.type === "error") {
              setStreamError(payload.message);
              setIsGenerating(false);
            } else if (payload.type === "done") {
              const artifacts = mergeArtifacts(
                execAcc?.artifacts,
                parseArtifactsFromText(`${contentAcc}\n${execAcc?.stdout || ""}`)
              );
              const assistantMessage: Message = {
                sender: "assistant",
                content: stripDownloadPlaceholders(contentAcc),
                artifacts,
                executionResult: execAcc || undefined,
                created_at: new Date().toISOString(),
              };

              // Commit structured message immediately so cards never flash away
              setMessages((prev) => [...prev, assistantMessage]);
              setIsGenerating(false);
              setPipeline([]);
              setStreamText("");
              setStreamExecution(null);

              // Reconcile with server (artifacts from DB may include sizes)
              void fetchMessages(convId);
              void fetchConversations();
              void fetchSystemStatus();
            }
          } catch (err) {
            console.error("SSE parse error", err);
          }
        }
      }
    } catch (err) {
      console.error(err);
      setStreamError("Failed to reach Mimir backend. Is the API running on :8000?");
      setIsGenerating(false);
    }
  };

  const handleRetryMessage = (assistantIndex: number) => {
    if (isGenerating) return;
    // Find nearest preceding user message
    let userIndex = -1;
    for (let i = assistantIndex - 1; i >= 0; i -= 1) {
      if (messages[i]?.sender === "user") {
        userIndex = i;
        break;
      }
    }
    if (userIndex < 0) return;

    const userTurnNumber = messages
      .slice(0, userIndex + 1)
      .filter((m) => m.sender === "user").length;
    const fullPrompt =
      promptHistory.current[userTurnNumber - 1] || messages[userIndex].content;

    // Remove the user turn + failed reply so handleSend can re-append cleanly
    setMessages((prev) => prev.slice(0, userIndex));
    promptHistory.current = promptHistory.current.slice(0, Math.max(0, userTurnNumber - 1));
    void handleSend(fullPrompt);
  };

  const handleDeleteChat = async (id: string) => {
    await api.deleteConversation(id);
    setConversations((prev) => prev.filter((c) => c.id !== id));
    const next = { ...workspace };
    next.pinned = next.pinned.filter((x) => x !== id);
    next.archived = next.archived.filter((x) => x !== id);
    delete next.projectByChat[id];
    delete next.titleOverrides[id];
    persistWorkspace(next);
    if (activeConvId === id) {
      setActiveConvId("");
      setMessages([]);
      setView("home");
    }
  };

  const handlePinChat = (id: string) => {
    const pinned = workspace.pinned.includes(id)
      ? workspace.pinned.filter((x) => x !== id)
      : [id, ...workspace.pinned];
    persistWorkspace({ ...workspace, pinned });
  };

  const handleArchiveChat = (id: string) => {
    const archived = workspace.archived.includes(id)
      ? workspace.archived.filter((x) => x !== id)
      : [id, ...workspace.archived];
    const pinned = workspace.pinned.filter((x) => x !== id);
    persistWorkspace({ ...workspace, archived, pinned });
    if (activeConvId === id) {
      setActiveConvId("");
      setMessages([]);
    }
  };

  const handleRenameChat = (id: string) => {
    const current = displayConversations.find((c) => c.id === id)?.title || "";
    const title = window.prompt("Rename chat", current);
    if (title == null) return;
    const trimmed = title.trim();
    if (!trimmed) return;
    persistWorkspace({
      ...workspace,
      titleOverrides: { ...workspace.titleOverrides, [id]: trimmed },
    });
  };

  const handleShareChat = async (id: string) => {
    const conv = displayConversations.find((c) => c.id === id);
    const text = conv?.title || id;
    try {
      await navigator.clipboard.writeText(`Mimir chat: ${text}`);
      window.alert("Chat title copied to clipboard.");
    } catch {
      window.alert("Could not copy share text.");
    }
  };

  const handleMoveChatToProject = (chatId: string, projectId: string | null) => {
    const projectByChat = { ...workspace.projectByChat };
    if (projectId) projectByChat[chatId] = projectId;
    else delete projectByChat[chatId];
    persistWorkspace({ ...workspace, projectByChat });
  };

  const handleCreateProject = () => {
    const name = window.prompt("Project name", "New project");
    if (!name?.trim()) return;
    const project = { id: newId("proj"), name: name.trim() };
    persistWorkspace({ ...workspace, projects: [...workspace.projects, project] });
    setActiveProjectId(project.id);
  };

  const handleRenameProject = (id: string) => {
    const current = workspace.projects.find((p) => p.id === id)?.name || "";
    const name = window.prompt("Rename project", current);
    if (!name?.trim()) return;
    persistWorkspace({
      ...workspace,
      projects: workspace.projects.map((p) =>
        p.id === id ? { ...p, name: name.trim() } : p
      ),
    });
  };

  const handleStartGroup = () => {
    window.alert("Group chats are coming soon in a future Mimir update.");
  };

  const handleCreateChat = async () => {
    const data = await api.createConversation();
    if (activeProjectId) {
      persistWorkspace({
        ...workspace,
        projectByChat: { ...workspace.projectByChat, [data.id]: activeProjectId },
      });
    }
    setConversations((prev) => [data, ...prev]);
    setActiveConvId(data.id);
    setMessages([]);
    promptHistory.current = [];
    setView("chats");
  };

  const saveSettings = async (e: FormEvent) => {
    e.preventDefault();
    await api.saveSettings({ user_name: userName, personality, theme });
  };

  const showHomeComposer = view === "home";
  const showChatComposer = view === "chats";

  return (
    <div className={`app-shell theme-${theme}`}>
      <div className="ambient-glow" aria-hidden="true" />
      <CursorGlow />

      <DownloadTray
        downloads={systemStatus?.downloads || []}
        live={liveDownloads}
      />

      <Sidebar
        view={view}
        onNavigate={setView}
        conversations={displayConversations}
        activeConvId={activeConvId}
        onSelectChat={(id) => {
          setActiveConvId(id);
          promptHistory.current = [];
          setView("chats");
        }}
        onNewChat={() => void handleCreateChat()}
        onDeleteChat={(id) => void handleDeleteChat(id)}
        search={search}
        onSearchChange={setSearch}
        projects={workspace.projects}
        activeProjectId={activeProjectId}
        onSelectProject={setActiveProjectId}
        onCreateProject={handleCreateProject}
        onRenameProject={handleRenameProject}
        onPinChat={handlePinChat}
        onArchiveChat={handleArchiveChat}
        onRenameChat={handleRenameChat}
        onShareChat={(id) => void handleShareChat(id)}
        onMoveChatToProject={handleMoveChatToProject}
        onStartGroup={handleStartGroup}
      />

      <div className="main-column">
        <main className={`main-stage ${view === "chats" ? "is-chat" : ""}`}>
          {view === "home" && (
            <div className="home-stage">
              <Greeting
                userName={userName}
                onQuickAction={(p) => {
                  setPrompt(p);
                  setView("home");
                }}
              />
            </div>
          )}

          {view === "chats" && (
            <div className="chat-stage">
              {messages.length === 0 && !isGenerating ? (
                <div className="chat-empty">
                  <h2>Start a conversation</h2>
                  <p>Ask Mimir to generate documents, analyze data, or write code.</p>
                </div>
              ) : (
                <ChatWindow
                  ref={chatRef}
                  messages={messages}
                  liveMessage={liveMessage}
                  liveTimeline={liveTimeline}
                  streamError={streamError}
                  isGenerating={isGenerating}
                  onRetryMessage={handleRetryMessage}
                />
              )}
            </div>
          )}

          {view === "models" && <ModelsView status={systemStatus} />}
          {view === "marketplace" && (
            <ComingSoon
              title="Marketplace"
              blurb="Install community skills and extensions without leaving Mimir."
            />
          )}
          {view === "memory" && (
            <ComingSoon
              title="Memory"
              blurb="Long-term preferences and project context will live here."
            />
          )}
          {view === "settings" && (
            <SettingsPanel
              userName={userName}
              personality={personality}
              theme={theme}
              onUserName={setUserName}
              onPersonality={setPersonality}
              onTheme={setTheme}
              onSave={(e) => void saveSettings(e)}
            />
          )}
        </main>

        {(showHomeComposer || showChatComposer) && (
          <div className={`composer-dock ${showHomeComposer ? "is-home" : ""}`}>
            <PromptInput
              value={prompt}
              onChange={setPrompt}
              files={files}
              onFilesChange={setFiles}
              onSend={(p) => void handleSend(p)}
              disabled={isGenerating}
              compact={showChatComposer}
            />
          </div>
        )}

        <StatusBar status={systemStatus} currentModel={activeModel} connected={connected} />
      </div>
    </div>
  );
}
