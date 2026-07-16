import { Download, ExternalLink, FileSpreadsheet, FileText, FileArchive, Image as ImageIcon } from "lucide-react";
import type { Artifact } from "../types";
import { api } from "../api/client";
import { artifactLabel } from "../utils/artifacts";
import { formatBytes } from "../utils/format";

function iconFor(type: string) {
  const t = type.toLowerCase();
  if (["png", "jpg", "jpeg", "webp"].includes(t)) return ImageIcon;
  if (["xlsx", "xls", "csv"].includes(t)) return FileSpreadsheet;
  if (t === "zip") return FileArchive;
  return FileText;
}

interface Props {
  artifact: Artifact;
}

export function ArtifactCard({ artifact }: Props) {
  const Icon = iconFor(artifact.file_type);
  const url = api.artifactUrl(artifact.file_path);
  const label = artifactLabel(artifact.file_type);
  const isImage = ["png", "jpg", "jpeg", "webp"].includes(artifact.file_type.toLowerCase());

  return (
    <article className="artifact-card" aria-label={`${label}: ${artifact.file_name}`}>
      <div className="artifact-card-top">
        <div className="artifact-icon" data-type={artifact.file_type.toLowerCase()}>
          <Icon size={18} aria-hidden="true" />
        </div>
        <div className="artifact-meta">
          <span className="artifact-kind">{label}</span>
          <span className="artifact-name" title={artifact.file_name}>
            {artifact.file_name}
          </span>
          <span className="artifact-sub">
            Generated successfully
            {artifact.file_size > 0 ? ` · ${formatBytes(artifact.file_size)}` : ""}
            {artifact.created_at ? ` · ${new Date(artifact.created_at).toLocaleString()}` : ""}
          </span>
        </div>
      </div>

      {isImage && (
        <div className="artifact-preview">
          <img src={url} alt={artifact.file_name} loading="lazy" />
        </div>
      )}

      <div className="artifact-actions">
        <a className="btn-ghost" href={url} target="_blank" rel="noreferrer">
          <ExternalLink size={14} aria-hidden="true" />
          Open
        </a>
        <a className="btn-primary-sm" href={url} download={artifact.file_name}>
          <Download size={14} aria-hidden="true" />
          Download
        </a>
      </div>
    </article>
  );
}
