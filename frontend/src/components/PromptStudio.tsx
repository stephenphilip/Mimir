import { Copy, Sparkles, X } from "lucide-react";
import { useState } from "react";
import type { PromptStudioResult } from "../types";

interface Props {
  open: boolean;
  loading: boolean;
  result: PromptStudioResult | null;
  onClose: () => void;
  onUseOriginal: () => void;
  onReplace: (prompt: string) => void;
}

export function PromptStudio({
  open,
  loading,
  result,
  onClose,
  onUseOriginal,
  onReplace,
}: Props) {
  const [copied, setCopied] = useState<string | null>(null);

  if (!open) return null;

  const copy = async (text: string, id: string) => {
    await navigator.clipboard.writeText(text);
    setCopied(id);
    setTimeout(() => setCopied(null), 1500);
  };

  return (
    <div className="prompt-studio-overlay" role="dialog" aria-label="Prompt Studio">
      <div className="prompt-studio-panel glass-panel">
        <header className="prompt-studio-header">
          <div>
            <h2>
              <Sparkles size={18} aria-hidden="true" /> Prompt Studio
            </h2>
            <p>Choose an enhanced prompt — Mimir never replaces without your approval.</p>
          </div>
          <button type="button" className="icon-btn" onClick={onClose} aria-label="Close">
            <X size={18} />
          </button>
        </header>

        {loading && <div className="prompt-studio-loading">Analyzing your prompt…</div>}

        {result && (
          <div className="prompt-studio-body">
                <div className="prompt-studio-meta">
                  <span className="chip">
                    Using model: {result.used_model || "default"}
                  </span>
                </div>
            <section className="prompt-studio-original">
              <h3>Original</h3>
              <p>{result.original}</p>
              <div className="prompt-studio-actions">
                <button type="button" className="btn-ghost" onClick={onUseOriginal}>
                  Use Original
                </button>
              </div>
            </section>

            {result.variants.map((v) => (
              <section key={v.id} className="prompt-studio-variant">
                <h3>{v.label}</h3>
                <p>{v.prompt}</p>
                <div className="prompt-studio-actions">
                  <button
                    type="button"
                    className="btn-primary-sm"
                    onClick={() => onReplace(v.prompt)}
                  >
                    Replace Prompt
                  </button>
                  <button
                    type="button"
                    className="btn-ghost"
                    onClick={() => void copy(v.prompt, v.id)}
                  >
                    <Copy size={14} />
                    {copied === v.id ? "Copied" : "Copy"}
                  </button>
                </div>
              </section>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
