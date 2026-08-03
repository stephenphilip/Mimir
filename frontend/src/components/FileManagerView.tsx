import {
  FileSpreadsheet,
  FileText,
  FolderOpen,
  Image as ImageIcon,
  Pin,
  Search,
  Trash2,
  Upload,
} from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api/client";
import type { ManagedFile } from "../types";
import { formatBytes } from "../utils/format";

const FILTERS = [
  { id: "all", label: "All" },
  { id: "document", label: "Documents" },
  { id: "image", label: "Images" },
  { id: "spreadsheet", label: "Spreadsheets" },
] as const;

interface Props {
  workspaceId?: string | null;
}

function iconFor(category: string) {
  if (category === "image") return ImageIcon;
  if (category === "spreadsheet") return FileSpreadsheet;
  return FileText;
}

export function FileManagerView({ workspaceId }: Props) {
  const [files, setFiles] = useState<ManagedFile[]>([]);
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState<(typeof FILTERS)[number]["id"]>("all");
  const [loading, setLoading] = useState(true);
  const inputRef = useRef<HTMLInputElement>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.listFiles({
        workspace_id: workspaceId || undefined,
        category: filter === "all" ? undefined : filter,
        search: search || undefined,
      });
      setFiles(data);
    } catch {
      setFiles([]);
    } finally {
      setLoading(false);
    }
  }, [workspaceId, filter, search]);

  useEffect(() => {
    void load();
  }, [load]);

  const onUpload = async (fileList: FileList | null) => {
    if (!fileList?.length) return;
    for (const file of Array.from(fileList)) {
      await api.uploadFile(file, workspaceId || undefined);
    }
    void load();
  };

  const onDelete = async (id: string) => {
    await api.deleteFile(id);
    void load();
  };

  const onPin = async (id: string, pinned: boolean) => {
    await api.pinFile(id, pinned);
    void load();
  };

  return (
    <div className="dashboard-view file-manager-view">
      <header className="dashboard-header">
        <div>
          <h1>File Manager</h1>
          <p>Uploaded files and managed workspace resources.</p>
        </div>
        <button
          type="button"
          className="btn-primary-sm"
          onClick={() => inputRef.current?.click()}
        >
          <Upload size={14} /> Upload
        </button>
        <input
          ref={inputRef}
          type="file"
          multiple
          hidden
          onChange={(e) => void onUpload(e.target.files)}
        />
      </header>

      <div className="file-manager-toolbar">
        <div className="search-field">
          <Search size={16} />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search files…"
          />
        </div>
        <div className="filter-pills">
          {FILTERS.map((f) => (
            <button
              key={f.id}
              type="button"
              className={filter === f.id ? "pill active" : "pill"}
              onClick={() => setFilter(f.id)}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <div className="dashboard-empty">Loading files…</div>
      ) : files.length === 0 ? (
        <div className="dashboard-empty glass-panel">
          <FolderOpen size={32} />
          <p>No files yet. Upload documents, images, or spreadsheets.</p>
        </div>
      ) : (
        <div className="file-grid">
          {files.map((f) => {
            const Icon = iconFor(f.category);
            return (
              <article key={f.id} className="file-card glass-panel">
                <div className="file-card-icon">
                  <Icon size={20} />
                </div>
                <div className="file-card-meta">
                  <span className="file-card-name" title={f.file_name}>
                    {f.file_name}
                  </span>
                  <span className="file-card-sub">
                    {f.category} · {formatBytes(f.file_size)}
                    {f.pinned ? " · Pinned" : ""}
                  </span>
                </div>
                <div className="file-card-actions">
                  <a
                    className="btn-ghost"
                    href={api.artifactUrl(f.file_path)}
                    target="_blank"
                    rel="noreferrer"
                  >
                    Preview
                  </a>
                  <button
                    type="button"
                    className="icon-btn"
                    title={f.pinned ? "Unpin" : "Pin"}
                    onClick={() => void onPin(f.id, !f.pinned)}
                  >
                    <Pin size={14} />
                  </button>
                  <button
                    type="button"
                    className="icon-btn danger"
                    title="Delete"
                    onClick={() => void onDelete(f.id)}
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              </article>
            );
          })}
        </div>
      )}
    </div>
  );
}
