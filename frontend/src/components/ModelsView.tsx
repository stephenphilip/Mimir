import { Box, Download } from "lucide-react";
import type { SystemStatus } from "../types";

interface Props {
  status: SystemStatus | null;
}

export function ModelsView({ status }: Props) {
  const models = status?.installed_models || [];
  const downloads = status?.downloads || [];

  return (
    <section className="panel-page" aria-labelledby="models-title">
      <header className="panel-header">
        <h1 id="models-title">Models</h1>
        <p>Local models discovered from Ollama. Downloads happen on demand during chat.</p>
      </header>

      <div className="models-grid">
        {models.length === 0 ? (
          <div className="empty-card glass-card">
            <Box size={22} />
            <p>No models installed yet. Send a chat and Mimir will pull what it needs.</p>
          </div>
        ) : (
          models.map((m) => (
            <article key={m.name} className="model-card glass-card">
              <div className="model-card-top">
                <Box size={18} />
                <span className="model-status">{m.status}</span>
              </div>
              <h3>{m.name}</h3>
              <p>{m.size || "Size unknown"}</p>
            </article>
          ))
        )}
      </div>

      {downloads.length > 0 && (
        <div className="downloads-block">
          <h2>
            <Download size={16} /> Active pulls
          </h2>
          {downloads.map((d) => (
            <div key={d.model_name} className="download-row glass-card">
              <div className="download-row-head">
                <strong>{d.model_name}</strong>
                <span>{d.status}</span>
              </div>
              {d.status === "downloading" && (
                <div className="progress-track">
                  <div className="progress-fill" style={{ width: `${d.progress}%` }} />
                </div>
              )}
              {d.error && <p className="download-error">{d.error}</p>}
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
