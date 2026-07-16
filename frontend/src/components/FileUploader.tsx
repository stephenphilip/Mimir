import { File as FileIcon, FileSpreadsheet, FileText, Image as ImageIcon, X } from "lucide-react";
import { useCallback, useRef, useState, type DragEvent } from "react";
import type { AttachedFile } from "../types";
import { formatBytes } from "../utils/format";

const ACCEPT =
  ".pdf,.docx,.txt,.csv,.xlsx,.xls,.png,.jpg,.jpeg,.webp,application/pdf,text/plain,text/csv,image/*";

const ALLOWED_EXT = new Set([
  "pdf",
  "docx",
  "txt",
  "csv",
  "xlsx",
  "xls",
  "png",
  "jpg",
  "jpeg",
  "webp",
]);

function extOf(name: string) {
  return name.split(".").pop()?.toLowerCase() || "";
}

function iconFor(name: string) {
  const ext = extOf(name);
  if (["png", "jpg", "jpeg", "webp"].includes(ext)) return ImageIcon;
  if (["csv", "xlsx", "xls"].includes(ext)) return FileSpreadsheet;
  if (["txt", "docx", "pdf"].includes(ext)) return FileText;
  return FileIcon;
}

async function readPreview(file: File): Promise<string | undefined> {
  const ext = extOf(file.name);
  if (!["txt", "csv", "md", "json"].includes(ext) && !file.type.startsWith("text/")) {
    return undefined;
  }
  if (file.size > 400_000) return undefined;
  const text = await file.text();
  return text.slice(0, 12000);
}

interface Props {
  files: AttachedFile[];
  onChange: (files: AttachedFile[]) => void;
  disabled?: boolean;
}

export function FileUploader({ files, onChange, disabled }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);

  const addFiles = useCallback(
    async (list: FileList | File[]) => {
      const next: AttachedFile[] = [...files];
      for (const file of Array.from(list)) {
        const ext = extOf(file.name);
        if (!ALLOWED_EXT.has(ext)) continue;
        if (next.some((f) => f.name === file.name && f.size === file.size)) continue;
        const previewText = await readPreview(file);
        next.push({
          id: `${file.name}-${file.size}-${file.lastModified}`,
          file,
          name: file.name,
          size: file.size,
          type: ext,
          previewText,
        });
      }
      onChange(next);
    },
    [files, onChange]
  );

  const onDrop = async (e: DragEvent) => {
    e.preventDefault();
    setDragging(false);
    if (disabled) return;
    if (e.dataTransfer.files?.length) await addFiles(e.dataTransfer.files);
  };

  return (
    <div className="file-uploader">
      {files.length > 0 && (
        <ul className="file-chip-list" aria-label="Attached files">
          {files.map((f) => {
            const Icon = iconFor(f.name);
            return (
              <li key={f.id} className="file-chip">
                <Icon size={14} aria-hidden="true" />
                <span className="file-chip-name" title={f.name}>
                  {f.name}
                </span>
                <span className="file-chip-size">{formatBytes(f.size)}</span>
                <button
                  type="button"
                  className="icon-btn"
                  aria-label={`Remove ${f.name}`}
                  disabled={disabled}
                  onClick={() => onChange(files.filter((x) => x.id !== f.id))}
                >
                  <X size={13} />
                </button>
              </li>
            );
          })}
        </ul>
      )}

      <div
        className={`drop-zone ${dragging ? "is-dragging" : ""}`}
        onDragOver={(e) => {
          e.preventDefault();
          if (!disabled) setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
      >
        <input
          ref={inputRef}
          type="file"
          multiple
          accept={ACCEPT}
          hidden
          disabled={disabled}
          onChange={(e) => {
            if (e.target.files) void addFiles(e.target.files);
            e.target.value = "";
          }}
        />
        <button
          type="button"
          className="drop-zone-btn"
          disabled={disabled}
          onClick={() => inputRef.current?.click()}
        >
          Drag & drop files, or click to upload
        </button>
        <span className="drop-zone-hint">PDF, DOCX, TXT, CSV, XLSX, PNG, JPG, WEBP</span>
      </div>
    </div>
  );
}

export function buildPromptWithAttachments(prompt: string, files: AttachedFile[]): string {
  if (!files.length) return prompt;
  const blocks = files.map((f) => {
    if (f.previewText) {
      return `\n\n--- Attached file: ${f.name} ---\n${f.previewText}\n--- End of ${f.name} ---`;
    }
    return `\n\n[Attached file: ${f.name} (${formatBytes(f.size)}, type=${f.type}). File is attached in the UI; use its name if generating related outputs.]`;
  });
  return `${prompt}${blocks.join("")}`;
}
