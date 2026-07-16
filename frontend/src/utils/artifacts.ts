import type { Artifact } from "../types";

/** Fake download placeholders models often print instead of real files */
const PLACEHOLDER_RE =
  /\[Download\s+(PDF|File|Excel|CSV|Image|DOCX|Document|Zip|XLSX|PNG|JPG)\]/gi;

const MARKDOWN_DL_RE =
  /\[([^\]]+)\]\((\/artifacts\/[^)\s]+|https?:\/\/[^)\s]*\/artifacts\/[^)\s]+)\)/gi;

const ARTIFACT_PATH_RE = /\/artifacts\/([^\s)'"`]+\.(pdf|xlsx?|csv|png|jpe?g|webp|docx?|zip|txt|json))/gi;

const EXT_TYPE: Record<string, string> = {
  pdf: "pdf",
  xlsx: "xlsx",
  xls: "xls",
  csv: "csv",
  png: "png",
  jpg: "jpg",
  jpeg: "jpeg",
  webp: "webp",
  doc: "doc",
  docx: "docx",
  zip: "zip",
  txt: "txt",
  json: "json",
};

export function normalizeArtifact(raw: Partial<Artifact> & { file_name: string }): Artifact {
  const name = raw.file_name;
  const ext = name.includes(".") ? name.split(".").pop()!.toLowerCase() : "";
  const file_type = (raw.file_type || EXT_TYPE[ext] || ext || "file").toLowerCase();
  const file_path = raw.file_path || `/artifacts/${name}`;
  return {
    id: raw.id ?? `${file_path}-${name}`,
    file_name: name,
    file_path,
    file_type,
    file_size: raw.file_size ?? 0,
    created_at: raw.created_at,
    source: raw.source ?? "api",
  };
}

export function artifactLabel(type: string): string {
  const t = type.toLowerCase();
  if (t === "pdf") return "PDF Generated";
  if (t === "xlsx" || t === "xls") return "Excel Spreadsheet";
  if (t === "csv") return "CSV Dataset";
  if (["png", "jpg", "jpeg", "webp"].includes(t)) return "Image Generated";
  if (t === "docx" || t === "doc") return "Word Document";
  if (t === "zip") return "Archive";
  return `${t.toUpperCase()} File`;
}

/** Remove fake [Download PDF] style text when real artifacts exist (or always clean placeholders). */
export function stripDownloadPlaceholders(content: string): string {
  return content
    .replace(PLACEHOLDER_RE, "")
    .replace(MARKDOWN_DL_RE, "")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

/** Pull artifact paths mentioned in model text / stdout when structured payload is empty. */
export function parseArtifactsFromText(text: string): Artifact[] {
  const found = new Map<string, Artifact>();
  let match: RegExpExecArray | null;
  const re = new RegExp(ARTIFACT_PATH_RE.source, "gi");
  while ((match = re.exec(text)) !== null) {
    const file_name = match[1];
    const art = normalizeArtifact({
      file_name,
      file_path: `/artifacts/${file_name}`,
      file_type: match[2].toLowerCase(),
      file_size: 0,
      source: "parsed",
    });
    found.set(art.file_path, art);
  }

  // Also catch "saved as report.pdf" / "Created: foo.xlsx"
  const nameHints =
    /(?:saved|created|wrote|generated|output)(?:\s+(?:as|to|file))?\s*[:`]?\s*([A-Za-z0-9._-]+\.(pdf|xlsx?|csv|png|jpe?g|webp|docx?|zip|txt))/gi;
  while ((match = nameHints.exec(text)) !== null) {
    const file_name = match[1];
    const path = `/artifacts/${file_name}`;
    if (!found.has(path)) {
      found.set(
        path,
        normalizeArtifact({
          file_name,
          file_path: path,
          file_type: match[2].toLowerCase(),
          file_size: 0,
          source: "parsed",
        })
      );
    }
  }

  return Array.from(found.values());
}

export function mergeArtifacts(...lists: Array<Artifact[] | undefined>): Artifact[] {
  const map = new Map<string, Artifact>();
  for (const list of lists) {
    for (const raw of list || []) {
      const art = normalizeArtifact(raw);
      const prev = map.get(art.file_path);
      if (!prev || (art.file_size && !prev.file_size) || art.source === "api" || art.source === "execution") {
        map.set(art.file_path, { ...prev, ...art, id: art.id ?? prev?.id });
      }
    }
  }
  return Array.from(map.values());
}

export function displayContent(content: string, artifacts: Artifact[]): string {
  const cleaned = stripDownloadPlaceholders(content);
  if (artifacts.length === 0) return cleaned;
  // Drop leftover bare filenames that duplicate artifact cards
  let next = cleaned;
  for (const a of artifacts) {
    const escaped = a.file_name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    next = next.replace(new RegExp(`^\\s*${escaped}\\s*$`, "gim"), "");
  }
  return next.replace(/\n{3,}/g, "\n\n").trim();
}
