import type { FormEvent } from "react";

interface Props {
  userName: string;
  personality: string;
  theme: string;
  onUserName: (v: string) => void;
  onPersonality: (v: string) => void;
  onTheme: (v: string) => void;
  onSave: (e: FormEvent) => void;
  saved?: boolean;
}

export function SettingsPanel({
  userName,
  personality,
  theme,
  onUserName,
  onPersonality,
  onTheme,
  onSave,
  saved,
}: Props) {
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

        <label className="field">
          <span>Theme</span>
          <select value={theme} onChange={(e) => onTheme(e.target.value)}>
            <option value="dark">Obsidian Dark</option>
            <option value="light">Light (limited)</option>
          </select>
        </label>

        <div className="form-actions" style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          <button type="submit" className="btn-primary">
            Save changes
          </button>
          {saved && (
            <span className="settings-saved-indicator" style={{ color: "var(--ok)", fontSize: "13px", fontWeight: 500 }}>
              ✓ Settings saved!
            </span>
          )}
        </div>
      </form>
    </section>
  );
}
