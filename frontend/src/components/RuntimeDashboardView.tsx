import { Activity, Box, Cpu, HardDrive, Layers, Monitor, Package } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { RuntimeDashboard } from "../types";

interface Props {
  showRuntimeTaskManager: boolean;
}

export function RuntimeDashboardView({ showRuntimeTaskManager }: Props) {
  const [data, setData] = useState<RuntimeDashboard | null>(null);

  useEffect(() => {
    let mounted = true;
    const load = async () => {
      try {
        const dash = await api.getRuntimeDashboard();
        if (mounted) setData(dash);
      } catch {
        if (mounted) setData(null);
      }
    };
    void load();
    const t = setInterval(() => void load(), 3000);
    return () => {
      mounted = false;
      clearInterval(t);
    };
  }, []);

  if (!data) {
    return (
      <div className="dashboard-view">
        <div className="dashboard-empty">Connecting to runtime…</div>
      </div>
    );
  }

  const { resources: r } = data;

  return (
    <div className="dashboard-view runtime-dashboard">
      <header className="dashboard-header">
        <div>
          <h1>Runtime Dashboard</h1>
          <p>
            Live system status · Workspace: {data.workspace.name || "Default"}
          </p>
        </div>
        <span className={`status-pill ${data.system_status}`}>{data.system_status}</span>
      </header>

      <div className="metric-grid">
        <article className="metric-card glass-panel">
          <Box size={18} />
          <span className="metric-label">Current Model</span>
          <strong>{data.current_model || "None loaded"}</strong>
        </article>
        <article className="metric-card glass-panel">
          <HardDrive size={18} />
          <span className="metric-label">RAM</span>
          <strong>
            {r.ram.used_gb} / {r.ram.total_gb} GB ({r.ram.percent}%)
          </strong>
        </article>
        <article className="metric-card glass-panel">
          <Cpu size={18} />
          <span className="metric-label">CPU</span>
          <strong>
            {r.cpu.percent}% · {r.cpu.count} cores
          </strong>
        </article>
        <article className="metric-card glass-panel">
          <Monitor size={18} />
          <span className="metric-label">GPU</span>
          <strong>
            {r.gpu.available
              ? `${r.gpu.name} · ${r.gpu.vram_used_mb}/${r.gpu.vram_total_mb} MB`
              : "Unavailable"}
          </strong>
        </article>
        <article className="metric-card glass-panel">
          <Package size={18} />
          <span className="metric-label">Artifacts Generated</span>
          <strong>{data.artifacts_generated}</strong>
        </article>
        {showRuntimeTaskManager && (
          <article className="metric-card glass-panel">
            <Activity size={18} />
            <span className="metric-label">Running Tasks</span>
            <strong>{r.running_tasks.length}</strong>
          </article>
        )}
      </div>

      <section className="dashboard-section glass-panel">
        <h2>
          <Layers size={16} /> Loaded Plugins
        </h2>
        <div className="chip-list">
          {data.plugins.map((p) => (
            <span key={p.id} className={`chip ${p.enabled ? "" : "muted"}`}>
              {p.name} v{p.version}
            </span>
          ))}
        </div>
      </section>

      <section className="dashboard-section glass-panel">
        <h2>Creator Types</h2>
        <div className="chip-list">
          {data.supported_creator_types.map((t) => (
            <span key={t} className="chip">
              {t}
            </span>
          ))}
        </div>
      </section>
    </div>
  );
}
