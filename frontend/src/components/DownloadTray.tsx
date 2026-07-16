import { ChevronDown, ChevronUp, Download, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import type { ModelDownload } from "../types";

interface Props {
  downloads: ModelDownload[];
  /** Live SSE progress overrides (model → percent) */
  live?: Record<string, number>;
}

/**
 * Browser-style collapsible download tray (top-right).
 * Shows Ollama model pulls without blocking the chat.
 */
export function DownloadTray({ downloads, live = {} }: Props) {
  const [collapsed, setCollapsed] = useState(false);
  const [dismissed, setDismissed] = useState<Set<string>>(new Set());

  const items = useMemo(() => {
    const byName = new Map<string, ModelDownload>();
    for (const d of downloads) {
      byName.set(d.model_name, d);
    }
    for (const [model, progress] of Object.entries(live)) {
      const prev = byName.get(model);
      byName.set(model, {
        model_name: model,
        progress,
        status: progress >= 100 ? "completed" : "downloading",
        error: prev?.error,
      });
    }
    return Array.from(byName.values()).filter(
      (d) =>
        !dismissed.has(d.model_name) &&
        (d.status === "downloading" || d.status === "pending" || d.status === "failed")
    );
  }, [downloads, live, dismissed]);

  // Auto-expand when a new pull starts
  useEffect(() => {
    if (items.some((d) => d.status === "downloading" || d.status === "pending")) {
      setCollapsed(false);
    }
  }, [items.length]);

  if (items.length === 0) return null;

  const activeCount = items.filter((d) => d.status !== "failed").length;

  return (
    <div className={`download-tray ${collapsed ? "is-collapsed" : ""}`} role="region" aria-label="Model downloads">
      <div className="download-tray-head">
        <div className="download-tray-title">
          <Download size={14} aria-hidden="true" />
          <span>
            {activeCount > 0 ? `${activeCount} model pull${activeCount > 1 ? "s" : ""}` : "Downloads"}
          </span>
        </div>
        <div className="download-tray-actions">
          <button
            type="button"
            className="icon-btn"
            aria-label={collapsed ? "Expand downloads" : "Collapse downloads"}
            onClick={() => setCollapsed((v) => !v)}
          >
            {collapsed ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
          </button>
        </div>
      </div>

      {!collapsed && (
        <ul className="download-tray-list">
          {items.map((d) => (
            <li key={d.model_name} className={`download-tray-item is-${d.status}`}>
              <div className="download-tray-row">
                <strong title={d.model_name}>{d.model_name}</strong>
                <button
                  type="button"
                  className="icon-btn"
                  aria-label={`Dismiss ${d.model_name}`}
                  onClick={() => setDismissed((prev) => new Set(prev).add(d.model_name))}
                >
                  <X size={12} />
                </button>
              </div>
              <div className="download-tray-meta">
                {d.status === "failed" ? (
                  <span className="is-fail">{d.error || "Failed"}</span>
                ) : (
                  <span>{Math.round(d.progress)}%</span>
                )}
              </div>
              {d.status !== "failed" && (
                <div className="progress-track">
                  <div className="progress-fill" style={{ width: `${Math.min(100, d.progress)}%` }} />
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
