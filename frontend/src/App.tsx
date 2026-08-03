import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { api } from "./api/client";
import { CursorGlow } from "./components/CursorGlow";
import { ChatWindow, type ChatWindowHandle } from "./components/ChatWindow";
import { ComingSoon } from "./components/ComingSoon";
import { DownloadTray } from "./components/DownloadTray";
import { FileManagerView } from "./components/FileManagerView";
import { Greeting } from "./components/Greeting";
import { MarketplaceView } from "./components/MarketplaceView";
import { ModelDashboardView } from "./components/ModelDashboardView";
import { PromptInput } from "./components/PromptInput";
import { buildPromptWithAttachments } from "./components/FileUploader";
import { PromptStudio } from "./components/PromptStudio";
import { RuntimeDashboardView } from "./components/RuntimeDashboardView";
import { SettingsPanel } from "./components/SettingsPanel";
import { Sidebar } from "./components/Sidebar";
import { StatusBar } from "./components/StatusBar";
import type {
  AttachedFile,
  Conversation,
  ExecutionResult,
  Message,
  NavView,
  PromptStudioResult,
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
  const [activeWorkspaceId, setActiveWorkspaceId] = useState<string | null>(null);
  const [promptStudioEnabled, setPromptStudioEnabled] = useState(false);
  const [promptStudioOpen, setPromptStudioOpen] = useState(false);
  const [promptStudioLoading, setPromptStudioLoading] = useState(false);
  const [promptStudioResult, setPromptStudioResult] = useState<PromptStudioResult | null>(null);
  const [pendingStudioPrompt, setPendingStudioPrompt] = useState("");
  const [settingsSaving, setSettingsSaving] = useState(false);
  const [settingsSaveMessage, setSettingsSaveMessage] = useState<string | null>(
    null
  );

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
  const [responsiveLayoutEnabled, setResponsiveLayoutEnabled] = useState(true);
  const [promptStudioDefault, setPromptStudioDefault] = useState(false);
  const [developerToolsEnabled, setDeveloperToolsEnabled] = useState(false);
  const [showRuntimeTaskManager, setShowRuntimeTaskManager] = useState(false);
  const [researchModeEnabled, setResearchModeEnabled] = useState(false);

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
      const parseBool = (v?: string) =>
        String(v || "").trim().toLowerCase() === "true";
      if (data.ui_responsive_layout != null) {
        setResponsiveLayoutEnabled(parseBool(data.ui_responsive_layout));
      }
      if (data.prompt_studio_default != null) {
        const next = parseBool(data.prompt_studio_default);
        setPromptStudioDefault(next);
        setPromptStudioEnabled(next);
      }
      if (data.developer_tools_enabled != null) {
        setDeveloperToolsEnabled(parseBool(data.developer_tools_enabled));
      }
      if (data.show_runtime_task_manager != null) {
        setShowRuntimeTaskManager(
          parseBool(data.show_runtime_task_manager) &&
            parseBool(data.developer_tools_enabled)
        );
      }
    } catch (err) {
      console.error(err);
    }
  }, []);

  useEffect(() => {
    // Toggle a global class to reflow the desktop layout on smaller window sizes.
    if (responsiveLayoutEnabled) {
      document.body.classList.add("ui-responsive");
    } else {
      document.body.classList.remove("ui-responsive");
    }
  }, [responsiveLayoutEnabled]);

  const fetchWorkspaces = useCallback(async () => {
    try {
      const data = await api.getWorkspaces();
      setActiveWorkspaceId((prev) => {
        if (prev) return prev;
        const def = data.find((w) => w.is_default) || data[0];
        return def?.id ?? null;
      });
    } catch {
      /* keep default null */
    }
  }, []);

  useEffect(() => {
    void fetchConversations();
    void fetchSystemStatus();
    void fetchSettings();
    void fetchWorkspaces();
    const id = window.setInterval(() => void fetchSystemStatus(), 5000);
    return () => window.clearInterval(id);
  }, [fetchConversations, fetchSystemStatus, fetchSettings, fetchWorkspaces]);

  useEffect(() => {
    if (activeConvId && view === "chats") {
      void fetchMessages(activeConvId);
    }
  }, [activeConvId, view, fetchMessages]);

  useEffect(() => {
    if (view === "home") {
      setActiveConvId("");
      setMessages([]);
    }
  }, [view]);

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

    const RESEARCH_MARKER = "[[RESEARCH_MODE]]";
    const RESEARCH_INSTRUCTION = [
      "Research Mode: Focus entirely on researching and producing an evidence-backed, deeply structured answer.",
      "If you cannot access web browsing or external sources, clearly state that and rely on internal knowledge; mark uncertain claims as uncertain.",
      "Include: (1) assumptions, (2) research plan, (3) detailed findings, (4) risks/limitations, (5) next steps."
    ].join(" ");

    const applyResearchMode = (p: string) => {
      if (p.startsWith(RESEARCH_MARKER)) return p; // already wrapped (e.g. retry)
      if (!researchModeEnabled) return p;
      return `${RESEARCH_MARKER}\n${RESEARCH_INSTRUCTION}\n\n${p}`;
    };

    const stripResearchForDisplay = (p: string) => {
      if (!p.startsWith(RESEARCH_MARKER)) return p;
      const rest = p.slice(RESEARCH_MARKER.length).replace(/^\s*\n/, "");
      const parts = rest.split("\n\n");
      if (parts.length >= 2) return parts.slice(1).join("\n\n");
      return p;
    };

    const effectivePrompt = applyResearchMode(finalPrompt);

    setView("chats");
    setPrompt("");
    setFiles([]);
    setIsGenerating(true);
    setStreamError(null);
    setPipeline([]);
    setStreamText("");
    setStreamExecution(null);

    const userVisible = stripResearchForDisplay(finalPrompt)
      .split("\n\n--- Attached file:")[0]
      .trim() || stripResearchForDisplay(finalPrompt);
    promptHistory.current = [...promptHistory.current, effectivePrompt];
    setMessages((prev) => [...prev, { sender: "user", content: userVisible }]);

    // Locals avoid stale closures and preserve artifacts across "done"
    let contentAcc = "";
    let execAcc: ExecutionResult | null = null;
    const statusAcc: string[] = [];

    try {
      const response = await api.chatStream(
        convId,
        effectivePrompt,
        activeWorkspaceId || undefined
      );
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

  const focusChatSearch = () => {
    // Keep chat context, but expose chat search immediately (developer UX).
    setView("chats");
    window.setTimeout(() => {
      const el = document.querySelector<HTMLInputElement>(
        "aside .side-search input"
      );
      el?.focus();
      el?.select?.();
    }, 0);
  };

  const openPromptStudio = async () => {
    const trimmed = prompt.trim();
    if (!trimmed) return;
    const withFiles = buildPromptWithAttachments(trimmed, files);
    setPendingStudioPrompt(withFiles);
    setPromptStudioOpen(true);
    setPromptStudioLoading(true);
    setPromptStudioResult(null);
    try {
      const result = await api.enhancePrompt(trimmed);
      setPromptStudioResult(result);
    } catch {
      setPromptStudioResult({
        original: trimmed,
        variants: [
          { id: "professional", label: "Professional", prompt: trimmed },
          { id: "creative", label: "Creative", prompt: trimmed },
          { id: "technical", label: "Technical", prompt: trimmed },
        ],
      });
    } finally {
      setPromptStudioLoading(false);
    }
  };

  const closePromptStudio = () => {
    setPromptStudioOpen(false);
    setPromptStudioResult(null);
    setPendingStudioPrompt("");
  };

  const sendFromStudio = (chosen: string) => {
    closePromptStudio();
    setPrompt("");
    setFiles([]);
    void handleSend(chosen);
  };

  const saveSettings = async (e: FormEvent) => {
    e.preventDefault();
    setSettingsSaving(true);
    setSettingsSaveMessage("Saving…");
    await api.saveSettings({
      user_name: userName,
      personality,
      theme,
      ui_responsive_layout: String(responsiveLayoutEnabled),
      prompt_studio_default: String(promptStudioDefault),
      developer_tools_enabled: String(developerToolsEnabled),
      show_runtime_task_manager: String(showRuntimeTaskManager),
    })
      .then(() => {
        setSettingsSaveMessage("Saved ✓");
        setTimeout(() => setSettingsSaveMessage(null), 2000);
      })
      .catch((err) => {
        console.error(err);
        setSettingsSaveMessage("Save failed. Please try again.");
      })
      .finally(() => setSettingsSaving(false));
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
        onFocusChatSearch={focusChatSearch}
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

          {view === "models" && <ModelDashboardView status={systemStatus} />}
          {view === "files" && <FileManagerView workspaceId={activeWorkspaceId} />}
          {view === "runtime" && (
            <RuntimeDashboardView
              showRuntimeTaskManager={showRuntimeTaskManager}
            />
          )}
          {view === "marketplace" && <MarketplaceView />}
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
              responsiveLayoutEnabled={responsiveLayoutEnabled}
              promptStudioDefault={promptStudioDefault}
              developerToolsEnabled={developerToolsEnabled}
              showRuntimeTaskManager={showRuntimeTaskManager}
              isSaving={settingsSaving}
              saveMessage={settingsSaveMessage}
              onUserName={setUserName}
              onPersonality={setPersonality}
              onTheme={setTheme}
              onResponsiveLayoutEnabled={setResponsiveLayoutEnabled}
              onPromptStudioDefault={(v) => {
                setPromptStudioDefault(v);
                setPromptStudioEnabled(v);
              }}
              onDeveloperToolsEnabled={setDeveloperToolsEnabled}
              onShowRuntimeTaskManager={(v) => setShowRuntimeTaskManager(v)}
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
              promptStudioEnabled={promptStudioEnabled}
              onPromptStudioToggle={setPromptStudioEnabled}
              onOpenPromptStudio={() => void openPromptStudio()}
              researchModeEnabled={researchModeEnabled}
              onResearchModeToggle={setResearchModeEnabled}
            />
          </div>
        )}

        <StatusBar status={systemStatus} currentModel={activeModel} connected={connected} />
      </div>

      <PromptStudio
        open={promptStudioOpen}
        loading={promptStudioLoading}
        result={promptStudioResult}
        onClose={closePromptStudio}
        onUseOriginal={() => sendFromStudio(pendingStudioPrompt || prompt)}
        onReplace={(p) => {
          setPrompt(p);
          sendFromStudio(buildPromptWithAttachments(p, files));
        }}
      />
    </div>
  );
}
