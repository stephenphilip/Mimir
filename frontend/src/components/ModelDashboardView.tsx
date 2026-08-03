import {
  Box,
  CheckCircle2,
  Download,
  HardDrive,
  RefreshCw,
  Trash2,
  Zap,
} from "lucide-react";
import type { SystemStatus } from "../types";

interface Props {
  status: SystemStatus | null;
}

function inferProvider(name: string): string {
  if (name.includes(":")) return name.split(":")[0];
  return "Ollama";
}

function inferQuantization(name: string): string {
  const lower = name.toLowerCase();
  if (lower.includes("q4")) return "Q4";
  if (lower.includes("q5")) return "Q5";
  if (lower.includes("q8")) return "Q8";
  if (lower.includes("fp16")) return "FP16";
  return "—";
}

export function ModelDashboardView({ status }: Props) {
  const models = status?.installed_models || [];
  const downloads = status?.downloads || [];
  const hw = status?.hardware;

  return (
    <div className="dashboard-view model-dashboard">
      <header className="dashboard-header">
        <div>
          <h1>Models</h1>
          <p>
            Installed local models · {hw?.gpu_name || "CPU mode"}
            {hw?.ram_gb ? ` · ${hw.ram_gb} GB RAM` : ""}
          </p>
        </div>
      </header>

      {downloads.length > 0 && (
        <section className="dashboard-section glass-panel">
          <h2>
            <Download size={16} /> Active Downloads
          </h2>
          <div className="model-download-list">
            {downloads.map((d) => (
              <div key={d.model_name} className="model-download-row">
                <span>{d.model_name}</span>
                <div className="progress-bar">
                  <div className="progress-fill" style={{ width: `${d.progress}%` }} />
                </div>
                <span className="muted">{d.status}</span>
              </div>
            ))}
          </div>
        </section>
      )}

      {models.length === 0 ? (
        <div className="dashboard-empty glass-panel">
          <Box size={32} />
          <p>No models installed yet. Send a chat and Mimir will pull what it needs.</p>
        </div>
      ) : (
        <div className="model-card-grid">
          {models.map((m) => (
            <article key={m.name} className="model-card glass-panel">
              <div className="model-card-top">
                <div className="model-card-icon">
                  <Zap size={18} />
                </div>
                <div>
                  <h3>{m.name}</h3>
                  <span className="model-card-sub">
                    {inferProvider(m.name)} · {inferQuantization(m.name)}
                  </span>
                </div>
                <span
                  className={`status-pill ${m.status === "installed" ? "online" : "muted"}`}
                >
                  {m.status}
                </span>
              </div>

              <div className="model-card-stats">
                <span>
                  <HardDrive size={14} /> {m.size || "—"}
                </span>
                <span>
                  <CheckCircle2 size={14} /> Health: healthy
                </span>
              </div>

              <div className="model-card-actions">
                <button type="button" className="btn-ghost" disabled title="Coming soon">
                  <RefreshCw size={14} /> Update
                </button>
                <button type="button" className="btn-ghost" disabled title="Coming soon">
                  <Download size={14} /> Pull
                </button>
                <button type="button" className="btn-ghost danger" disabled title="Coming soon">
                  <Trash2 size={14} /> Delete
                </button>
              </div>

              <p className="model-compat">
                Future: llama.cpp · ONNX · MLX
              </p>
            </article>
          ))}
        </div>
      )}
    </div>
  );
}
