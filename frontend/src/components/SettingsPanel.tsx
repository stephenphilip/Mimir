import type { FormEvent } from "react";

interface Props {
  userName: string;
  personality: string;
  theme: string;
  responsiveLayoutEnabled: boolean;
  promptStudioDefault: boolean;
  developerToolsEnabled: boolean;
  showRuntimeTaskManager: boolean;
  isSaving?: boolean;
  saveMessage?: string | null;
  onUserName: (v: string) => void;
  onPersonality: (v: string) => void;
  onTheme: (v: string) => void;
  onResponsiveLayoutEnabled: (v: boolean) => void;
  onPromptStudioDefault: (v: boolean) => void;
  onDeveloperToolsEnabled: (v: boolean) => void;
  onShowRuntimeTaskManager: (v: boolean) => void;
  onSave: (e: FormEvent) => void;
  saved?: boolean;
}

export function SettingsPanel({
  userName,
  personality,
  theme,
  responsiveLayoutEnabled,
  promptStudioDefault,
  developerToolsEnabled,
  showRuntimeTaskManager,
  isSaving = false,
  saveMessage = null,
  onUserName,
  onPersonality,
  onTheme,
  onResponsiveLayoutEnabled,
  onPromptStudioDefault,
  onDeveloperToolsEnabled,
  onShowRuntimeTaskManager,
  onSave,
  saved,
}: Props) {
  const themes = [
    { id: "dark", label: "Obsidian Dark" },
    { id: "obsidian", label: "Obsidian (glass)" },
    { id: "aurora", label: "Aurora" },
    { id: "midnight", label: "Midnight" },
    { id: "mono", label: "Mono (high contrast)" },
    { id: "light", label: "Light (limited)" },
  ] as const;

  return (
    <section className="panel-page" aria-labelledby="settings-title">
      <header className="panel-header">
        <h1 id="settings-title">Settings</h1>
        <p>Personalize how Mimir talks and appears.</p>
      </header>

      <form className="settings-form glass-card" onSubmit={onSave}>
        <label className="field">
          <span>Display name</span>
          <input value={userName} onChange={(e) => onUserName(e.target.value)} required />
        </label>

        <label className="field">
          <span>Personality</span>
          <textarea
            value={personality}
            onChange={(e) => onPersonality(e.target.value)}
            rows={4}
            required
          />
        </label>

        <div className="field">
          <span>Theme</span>
          <div className="theme-picker" role="radiogroup" aria-label="Theme">
            {themes.map((t) => (
              <button
                key={t.id}
                type="button"
                className={`theme-option ${theme === t.id ? "is-active" : ""}`}
                role="radio"
                aria-checked={theme === t.id}
                onClick={() => onTheme(t.id)}
              >
                <span className="theme-option-swatch" aria-hidden="true" />
                {t.label}
              </button>
            ))}
          </div>
        </div>

        <label className="field">
          <span>Refit layout to window size</span>
          <div className="toggle-row">
            <input
              type="checkbox"
              checked={responsiveLayoutEnabled}
              onChange={(e) => onResponsiveLayoutEnabled(e.target.checked)}
            />
            <span className="toggle-label">Automatically adapts when you drag the window</span>
          </div>
        </label>

        <label className="field">
          <span>Prompt Studio default</span>
          <div className="toggle-row">
            <input
              type="checkbox"
              checked={promptStudioDefault}
              onChange={(e) => onPromptStudioDefault(e.target.checked)}
            />
            <span className="toggle-label">Enable Prompt Studio automatically</span>
          </div>
        </label>

        <div className="settings-sep" />

        <label className="field">
          <span>Developer tools</span>
          <div className="toggle-row">
            <input
              type="checkbox"
              checked={developerToolsEnabled}
              onChange={(e) => onDeveloperToolsEnabled(e.target.checked)}
            />
            <span className="toggle-label">Show developer-only UI</span>
          </div>
        </label>

        {developerToolsEnabled && (
          <label className="field">
            <span>Runtime task manager</span>
            <div className="toggle-row">
              <input
                type="checkbox"
                checked={showRuntimeTaskManager}
                onChange={(e) => onShowRuntimeTaskManager(e.target.checked)}
              />
              <span className="toggle-label">Show running tasks in Runtime</span>
            </div>
          </label>
        )}

        <div className="form-actions" style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          <button
            type="submit"
            className="btn-primary"
            disabled={isSaving}
          >
            {isSaving ? "Saving…" : "Save changes"}
          </button>
          {saved && (
            <span className="settings-saved-indicator" style={{ color: "var(--ok)", fontSize: "13px", fontWeight: 500 }}>
              ✓ Settings saved!
            </span>
          )}
        </div>

        {saveMessage && (
          <div
            className={`settings-save-feedback ${
              saveMessage.toLowerCase().includes("error") ? "is-error" : ""
            }`}
            role="status"
            aria-live="polite"
          >
            {saveMessage}
          </div>
        )}
      </form>
    </section>
  );
}
