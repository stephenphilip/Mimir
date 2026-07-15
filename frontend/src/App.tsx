import React, { useState, useEffect, useRef } from "react";
import { 
  MessageSquare, Plus, Trash2, Settings, Cpu, HardDrive, 
  Download as DlIcon, FileText, CheckCircle, AlertTriangle, 
  Sparkles, Terminal, Activity, ChevronRight, X
} from "lucide-react";

interface Conversation {
  id: string;
  title: string;
  updated_at: string;
}

interface Artifact {
  id: number;
  file_name: string;
  file_path: string;
  file_type: string;
  file_size: number;
}

interface Message {
  id?: number;
  sender: "user" | "assistant";
  content: string;
  created_at?: string;
  artifacts?: Artifact[];
  isStreaming?: boolean;
  pipelineStatus?: string[];
  executionResult?: {
    success: boolean;
    stdout: string;
    stderr: string;
    exit_code: number;
    artifacts: Artifact[];
  };
}

interface HardwareInfo {
  ram_gb: number;
  has_gpu: boolean;
  gpu_name: string;
  vram_mb: number;
  category: "high" | "low";
}

interface InstalledModel {
  name: string;
  size: string;
  status: string;
}

interface ModelDownload {
  model_name: string;
  progress: number;
  status: string;
  error?: string;
}

interface SystemStatus {
  hardware: HardwareInfo;
  installed_models: InstalledModel[];
  downloads: ModelDownload[];
}

const BACKEND_URL = "http://localhost:8000";

export default function App() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeConvId, setActiveConvId] = useState<string>("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [prompt, setPrompt] = useState<string>("");
  const [isGenerating, setIsGenerating] = useState<boolean>(false);
  const [hudOpen, setHudOpen] = useState<boolean>(true);
  const [settingsOpen, setSettingsOpen] = useState<boolean>(false);
  const [systemStatus, setSystemStatus] = useState<SystemStatus | null>(null);
  
  // Settings Form States
  const [userName, setUserName] = useState<string>("Stephen");
  const [personality, setPersonality] = useState<string>("helpful, concise expert data analyst and assistant");
  const [theme, setTheme] = useState<string>("dark");

  // Streaming status overlays
  const [currentPipeline, setCurrentPipeline] = useState<string[]>([]);
  const [activeDownload, setActiveDownload] = useState<{ model: string; progress: number } | null>(null);
  const [currentStreamingText, setCurrentStreamingText] = useState<string>("");
  const [currentExecution, setCurrentExecution] = useState<any | null>(null);
  const [streamError, setStreamError] = useState<string | null>(null);

  const chatFeedRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // Initial fetch
    fetchConversations();
    fetchSystemStatus();
    fetchSettings();
    
    // Poll system status every 4 seconds to get updates on downloads/hardware
    const statusInterval = setInterval(fetchSystemStatus, 4000);
    return () => clearInterval(statusInterval);
  }, []);

  useEffect(() => {
    if (activeConvId) {
      fetchMessages(activeConvId);
    } else {
      setMessages([]);
    }
  }, [activeConvId]);

  useEffect(() => {
    // Scroll to bottom of chat feed when messages change
    if (chatFeedRef.current) {
      chatFeedRef.current.scrollTop = chatFeedRef.current.scrollHeight;
    }
  }, [messages, currentStreamingText, currentPipeline]);

  const fetchConversations = async () => {
    try {
      const resp = await fetch(`${BACKEND_URL}/api/conversations`);
      if (resp.ok) {
        const data = await resp.json();
        setConversations(data);
        if (data.length > 0 && !activeConvId) {
          setActiveConvId(data[0].id);
        }
      }
    } catch (err) {
      console.error("Error fetching conversations:", err);
    }
  };

  const fetchMessages = async (convId: string) => {
    try {
      const resp = await fetch(`${BACKEND_URL}/api/conversations/${convId}/messages`);
      if (resp.ok) {
        const data = await resp.json();
        setMessages(data);
      }
    } catch (err) {
      console.error("Error fetching messages:", err);
    }
  };

  const fetchSystemStatus = async () => {
    try {
      const resp = await fetch(`${BACKEND_URL}/api/system/status`);
      if (resp.ok) {
        const data = await resp.json();
        setSystemStatus(data);
        
        // Update active downloads from the system status
        const activeDl = data.downloads.find((d: any) => d.status === "downloading" || d.status === "pending");
        if (activeDl) {
          setActiveDownload({ model: activeDl.model_name, progress: activeDl.progress });
        } else {
          setActiveDownload(null);
        }
      }
    } catch (err) {
      console.error("Error fetching system status:", err);
    }
  };

  const fetchSettings = async () => {
    try {
      const resp = await fetch(`${BACKEND_URL}/api/settings`);
      if (resp.ok) {
        const data = await resp.json();
        if (data.user_name) setUserName(data.user_name);
        if (data.personality) setPersonality(data.personality);
        if (data.theme) setTheme(data.theme);
      }
    } catch (err) {
      console.error("Error fetching settings:", err);
    }
  };

  const saveSettings = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const resp = await fetch(`${BACKEND_URL}/api/settings`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_name: userName, personality, theme })
      });
      if (resp.ok) {
        setSettingsOpen(false);
        fetchSystemStatus(); // Refresh status
      }
    } catch (err) {
      console.error("Error saving settings:", err);
    }
  };

  const handleCreateChat = async () => {
    try {
      const resp = await fetch(`${BACKEND_URL}/api/conversations`, { method: "POST" });
      if (resp.ok) {
        const data = await resp.json();
        setConversations(prev => [data, ...prev]);
        setActiveConvId(data.id);
      }
    } catch (err) {
      console.error("Error creating chat:", err);
    }
  };

  const handleDeleteChat = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      const resp = await fetch(`${BACKEND_URL}/api/conversations/${id}`, { method: "DELETE" });
      if (resp.ok) {
        setConversations(prev => prev.filter(c => c.id !== id));
        if (activeConvId === id) {
          setActiveConvId("");
        }
      }
    } catch (err) {
      console.error("Error deleting chat:", err);
    }
  };

  const handleSend = async () => {
    if (!prompt.trim() || isGenerating) return;
    
    let convId = activeConvId;
    if (!convId) {
      // Create new conversation on the fly
      try {
        const resp = await fetch(`${BACKEND_URL}/api/conversations`, { method: "POST" });
        if (resp.ok) {
          const data = await resp.json();
          convId = data.id;
          setActiveConvId(data.id);
          setConversations(prev => [data, ...prev]);
        } else {
          return;
        }
      } catch (err) {
        console.error(err);
        return;
      }
    }

    const userPrompt = prompt;
    setPrompt("");
    setIsGenerating(true);
    setStreamError(null);
    setCurrentPipeline([]);
    setCurrentStreamingText("");
    setCurrentExecution(null);

    // Append user message locally immediately
    setMessages(prev => [...prev, { sender: "user", content: userPrompt }]);

    try {
      const response = await fetch(`${BACKEND_URL}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ conversation_id: convId, prompt: userPrompt })
      });

      if (!response.body) return;

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          const trimmed = line.trim();
          if (trimmed.startsWith("data: ")) {
            const jsonStr = trimmed.substring(6);
            try {
              const payload = JSON.parse(jsonStr);
              if (payload.type === "status") {
                setCurrentPipeline(prev => [...prev, payload.status]);
              } else if (payload.type === "download_progress") {
                setActiveDownload({ model: payload.model, progress: payload.progress });
              } else if (payload.type === "error") {
                setStreamError(payload.message);
                setIsGenerating(false);
                setActiveDownload(null);
              } else if (payload.type === "content") {
                // Remove active download overlay once content starts streaming
                setActiveDownload(null);
                setCurrentStreamingText(prev => prev + payload.text);
              } else if (payload.type === "execution_result") {
                setCurrentExecution({
                  success: payload.success,
                  stdout: payload.stdout,
                  stderr: payload.stderr,
                  exit_code: payload.exit_code,
                  artifacts: payload.artifacts
                });
              } else if (payload.type === "done") {
                // Done generating, fetch complete state
                fetchMessages(convId);
                fetchConversations();
                fetchSystemStatus();
                setIsGenerating(false);
                setCurrentPipeline([]);
                setCurrentStreamingText("");
                setCurrentExecution(null);
              }
            } catch (err) {
              console.error("Error parsing chunk", err);
            }
          }
        }
      }
    } catch (err) {
      console.error("Error posting message:", err);
      setIsGenerating(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const formatSize = (bytes: number) => {
    if (bytes === 0) return "0 Bytes";
    const k = 1024;
    const sizes = ["Bytes", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
  };

  const activeConv = conversations.find(c => c.id === activeConvId);

  return (
    <div className="app-container">
      {/* Sidebar - History */}
      <aside className="sidebar">
        <div className="brand-section">
          <div className="brand-logo">
            <Sparkles size={18} className="text-white" />
          </div>
          <span className="brand-name gradient-text">Mimir</span>
        </div>

        <button className="new-chat-btn" onClick={handleCreateChat}>
          <Plus size={16} />
          New Assistant Chat
        </button>

        <div className="history-section">
          <div className="history-title">Recent Conversations</div>
          {conversations.map(conv => (
            <div 
              key={conv.id} 
              className={`history-item ${activeConvId === conv.id ? "active" : ""}`}
              onClick={() => setActiveConvId(conv.id)}
            >
              <div className="history-item-title">{conv.title}</div>
              <button className="delete-chat-btn" onClick={(e) => handleDeleteChat(conv.id, e)}>
                <Trash2 size={14} />
              </button>
            </div>
          ))}
        </div>

        <div className="settings-section">
          <button className="settings-btn" onClick={() => setSettingsOpen(true)}>
            <Settings size={18} />
            Platform Settings
          </button>
        </div>
      </aside>

      {/* Main Chat Feed */}
      <main className="chat-main">
        <header className="chat-header">
          <div className="chat-header-title">
            {activeConv ? activeConv.title : "Assistant Chat"}
          </div>
          <button className="hud-toggle-btn" onClick={() => setHudOpen(!hudOpen)}>
            <Activity size={16} />
            {hudOpen ? "Hide System HUD" : "Show System HUD"}
          </button>
        </header>

        {/* Chat Messages */}
        <div className="chat-feed" ref={chatFeedRef}>
          {messages.length === 0 && !isGenerating ? (
            <div className="empty-chat">
              <div className="empty-logo">✨</div>
              <h1 className="empty-title">Your Local Personal Assistant</h1>
              <p className="empty-subtitle">
                Ask me to write reports, organize data lists, generate Excel sheets, or analyze calculations. Everything runs locally on your machine.
              </p>
            </div>
          ) : (
            <>
              {messages.map((msg, index) => (
                <div key={index} className={`message-row ${msg.sender}`}>
                  <div className="message-bubble">
                    <div style={{ whiteSpace: "pre-wrap" }}>
                      {msg.content}
                    </div>
                    
                    {/* Render Code Execution Artifacts if exists */}
                    {msg.artifacts && msg.artifacts.length > 0 && (
                      <div className="artifacts-gallery">
                        {msg.artifacts.map(art => (
                          <div key={art.id} className="artifact-card glass-panel">
                            <div className="artifact-info">
                              <div className="artifact-icon">
                                <FileText size={18} />
                              </div>
                              <div className="artifact-details">
                                <span className="artifact-name">{art.file_name}</span>
                                <span className="artifact-meta">
                                  {art.file_type.toUpperCase()} • {formatSize(art.file_size)}
                                </span>
                              </div>
                            </div>
                            <a 
                              href={`${BACKEND_URL}${art.file_path}`} 
                              download 
                              className="artifact-action-btn"
                              target="_blank" 
                              rel="noreferrer"
                            >
                              <DlIcon size={14} />
                              Download File
                            </a>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              ))}

              {/* Streaming Assistant Feed */}
              {isGenerating && (
                <div className="message-row assistant">
                  <div className="message-bubble">
                    {/* Render live pipeline stages */}
                    {currentPipeline.length > 0 && (
                      <div style={{ marginBottom: "12px" }}>
                        {currentPipeline.map((status, i) => (
                          <div key={i} className="pipeline-status">
                            {i === currentPipeline.length - 1 && !currentStreamingText ? (
                              <div className="pipeline-spinner" />
                            ) : (
                              <CheckCircle size={12} className="text-emerald-500" />
                            )}
                            {status}
                          </div>
                        ))}
                      </div>
                    )}

                    {/* Active Download status bar overlay */}
                    {activeDownload && (
                      <div className="hud-card" style={{ marginTop: "8px", border: "1px solid var(--color-primary)" }}>
                        <div className="hud-stat-row">
                          <span className="hud-stat-label">Model Auto-download: {activeDownload.model}</span>
                          <span className="hud-stat-value">{activeDownload.progress}%</span>
                        </div>
                        <div className="download-progress-bar">
                          <div className="download-progress-fill" style={{ width: `${activeDownload.progress}%` }} />
                        </div>
                      </div>
                    )}

                    {/* Text Stream output */}
                    <div style={{ whiteSpace: "pre-wrap" }}>
                      {currentStreamingText}
                    </div>

                    {/* Live Execution output */}
                    {currentExecution && (
                      <div style={{ marginTop: "12px" }}>
                        <div className="code-header">
                          <div className="flex items-center gap-2">
                            <Terminal size={12} />
                            <span>Python Execution Console</span>
                          </div>
                          <span>{currentExecution.success ? "Success" : "Failed (Code: " + currentExecution.exit_code + ")"}</span>
                        </div>
                        <pre>
                          {currentExecution.stdout || currentExecution.stderr || "Success. Generating files..."}
                        </pre>

                        {currentExecution.artifacts.length > 0 && (
                          <div style={{ marginTop: "8px" }}>
                            {currentExecution.artifacts.map((art: any, i: number) => (
                              <div key={i} className="artifact-card glass-panel">
                                <div className="artifact-info">
                                  <div className="artifact-icon">
                                    <FileText size={18} />
                                  </div>
                                  <div className="artifact-details">
                                    <span className="artifact-name">{art.file_name}</span>
                                    <span className="artifact-meta">
                                      {art.file_type.toUpperCase()} • {formatSize(art.file_size)}
                                    </span>
                                  </div>
                                </div>
                                <a href={`${BACKEND_URL}${art.file_path}`} download className="artifact-action-btn">
                                  <DlIcon size={14} />
                                  Download File
                                </a>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              )}

              {streamError && (
                <div className="message-row assistant">
                  <div className="message-bubble" style={{ borderLeftColor: "#ef4444", background: "rgba(239, 68, 68, 0.05)", borderLeftWidth: "4px" }}>
                    <div className="pipeline-status" style={{ background: "transparent", borderLeft: "none", color: "#f87171", padding: 0 }}>
                      <AlertTriangle size={16} style={{ marginRight: "8px" }} />
                      <span className="font-semibold">System Alert: Prompt Processing Failed</span>
                    </div>
                    <div style={{ marginTop: "8px", color: "var(--text-secondary)", fontSize: "0.9rem" }}>
                      {streamError}
                    </div>
                  </div>
                </div>
              )}
            </>
          )}
        </div>

        {/* Input Bar */}
        <div className="chat-input-container">
          <div className="chat-input-wrapper">
            <textarea 
              className="chat-textarea"
              placeholder="Ask Mimir... (e.g. 'Create an excel expense tracker spreadsheet for this year' or 'Write an email draft')"
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={isGenerating}
              rows={1}
            />
            <button 
              className="send-btn" 
              onClick={handleSend}
              disabled={!prompt.trim() || isGenerating}
            >
              <ChevronRight size={20} />
            </button>
          </div>
        </div>
      </main>

      {/* System HUD Panel */}
      {hudOpen && systemStatus && (
        <aside className="hud-panel">
          <div>
            <h2 className="hud-section-title">
              <Cpu size={18} className="text-secondary" />
              Hardware Metrics
            </h2>
            <div className="hud-card" style={{ marginTop: "12px" }}>
              <div className="hud-stat-row">
                <span className="hud-stat-label">System RAM</span>
                <span className="hud-stat-value">{systemStatus.hardware.ram_gb} GB</span>
              </div>
              <div className="hud-stat-row">
                <span className="hud-stat-label">GPU Acceleration</span>
                <span className="hud-stat-value">{systemStatus.hardware.has_gpu ? "Active" : "Disabled (CPU)"}</span>
              </div>
              {systemStatus.hardware.has_gpu && (
                <>
                  <div className="hud-stat-row">
                    <span className="hud-stat-label">GPU Device</span>
                    <span className="hud-stat-value" style={{ maxWidth: "160px", textOverflow: "ellipsis", overflow: "hidden", whiteSpace: "nowrap" }}>
                      {systemStatus.hardware.gpu_name}
                    </span>
                  </div>
                  <div className="hud-stat-row">
                    <span className="hud-stat-label">Dedicated VRAM</span>
                    <span className="hud-stat-value">{systemStatus.hardware.vram_mb} MB</span>
                  </div>
                </>
              )}
              <div className="hud-stat-row">
                <span className="hud-stat-label">Power Profile</span>
                <span className="hud-stat-value" style={{ textTransform: "capitalize" }}>
                  {systemStatus.hardware.category} Spec
                </span>
              </div>
            </div>
          </div>

          <div>
            <h2 className="hud-section-title">
              <HardDrive size={18} className="text-primary" />
              AI Capabilities
            </h2>
            <div style={{ display: "flex", flexDirection: "column", gap: "10px", marginTop: "12px" }}>
              {systemStatus.installed_models.length === 0 ? (
                <div className="text-xs text-muted" style={{ padding: "8px" }}>
                  No capabilities deployed. They will install automatically on demand.
                </div>
              ) : (
                systemStatus.installed_models.map((model, i) => (
                  <div key={i} className="model-pill">
                    <div style={{ display: "flex", flexDirection: "column" }}>
                      <span className="font-semibold">{model.name}</span>
                      <span className="text-[10px] text-muted">{model.size}</span>
                    </div>
                    <span className="text-[10px] uppercase font-bold" style={{ color: "var(--color-secondary)" }}>
                      Active
                    </span>
                  </div>
                ))
              )}
            </div>
          </div>

          {systemStatus.downloads && systemStatus.downloads.length > 0 && (
            <div>
              <h2 className="hud-section-title">
                <DlIcon size={18} className="text-amber-500" />
                System Model Pulls
              </h2>
              <div style={{ display: "flex", flexDirection: "column", gap: "10px", marginTop: "12px" }}>
                {systemStatus.downloads.map((dl, i) => (
                  <div key={i} className="hud-card" style={{ gap: "6px" }}>
                    <div className="hud-stat-row" style={{ fontSize: "11px" }}>
                      <span className="font-semibold" style={{ maxWidth: "140px", textOverflow: "ellipsis", overflow: "hidden", whiteSpace: "nowrap" }}>
                        {dl.model_name}
                      </span>
                      <span className="capitalize font-bold" style={{ 
                        color: dl.status === "failed" ? "#ef4444" : dl.status === "completed" ? "#10b981" : "var(--color-secondary)",
                        fontSize: "10px"
                      }}>
                        {dl.status}
                      </span>
                    </div>
                    {dl.status === "downloading" && (
                      <div className="download-progress-bar">
                        <div className="download-progress-fill" style={{ width: `${dl.progress}%` }} />
                      </div>
                    )}
                    {dl.status === "failed" && dl.error && (
                      <div style={{ fontSize: "10px", color: "#f87171", marginTop: "4px", lineHeight: "1.4", wordBreak: "break-word" }}>
                        {dl.error}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </aside>
      )}

      {/* Settings Modal */}
      {settingsOpen && (
        <div className="modal-overlay">
          <div className="modal-content glass-panel">
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <h2 className="modal-header">Platform Settings</h2>
              <button 
                style={{ background: "transparent", border: "none", color: "var(--text-secondary)", cursor: "pointer" }}
                onClick={() => setSettingsOpen(false)}
              >
                <X size={18} />
              </button>
            </div>
            
            <form onSubmit={saveSettings} style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
              <div className="form-group">
                <label className="form-label">User Display Name</label>
                <input 
                  type="text" 
                  className="form-input"
                  value={userName} 
                  onChange={(e) => setUserName(e.target.value)} 
                  required
                />
              </div>

              <div className="form-group">
                <label className="form-label">Assistant Personality Prompt</label>
                <textarea 
                  className="form-input" 
                  style={{ minHeight: "80px", resize: "vertical" }}
                  value={personality} 
                  onChange={(e) => setPersonality(e.target.value)} 
                  required
                />
              </div>

              <div className="form-group">
                <label className="form-label">Interface Theme</label>
                <select 
                  className="form-input" 
                  value={theme} 
                  onChange={(e) => setTheme(e.target.value)}
                >
                  <option value="dark">Obsidian Dark Mode</option>
                  <option value="light">Vanilla Light Mode (Deprecated)</option>
                </select>
              </div>

              <div className="modal-actions">
                <button type="button" className="btn-secondary" onClick={() => setSettingsOpen(false)}>
                  Cancel
                </button>
                <button type="submit" className="btn-primary">
                  Save Changes
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
