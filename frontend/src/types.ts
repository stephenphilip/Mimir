export type NavView =
  | "home"
  | "chats"
  | "models"
  | "marketplace"
  | "memory"
  | "settings"
  | "files"
  | "runtime";

export interface Conversation {
  id: string;
  title: string;
  updated_at: string;
  pinned?: boolean;
  archived?: boolean;
  project_id?: string;
  workspace_id?: string;
}

export interface Artifact {
  id?: number | string;
  artifact_id?: string;
  file_name: string;
  file_path: string;
  file_type: string;
  file_size: number;
  mime_type?: string;
  provider?: string;
  workspace_id?: string;
  status?: string;
  thumbnail?: string;
  created_at?: string;
  source?: "api" | "execution" | "parsed";
}

export interface ExecutionResult {
  success: boolean;
  stdout: string;
  stderr: string;
  exit_code: number;
  artifacts: Artifact[];
}

export interface Message {
  id?: number;
  sender: "user" | "assistant";
  content: string;
  created_at?: string;
  artifacts?: Artifact[];
  isStreaming?: boolean;
  pipelineStatus?: string[];
  executionResult?: ExecutionResult;
}

export interface HardwareInfo {
  ram_gb: number;
  has_gpu: boolean;
  gpu_name: string;
  vram_mb: number;
  category: "high" | "low";
}

export interface InstalledModel {
  name: string;
  size: string;
  status: string;
  provider?: string;
  quantization?: string;
  health?: "healthy" | "unknown" | "error";
}

export interface ModelDownload {
  model_name: string;
  progress: number;
  status: string;
  error?: string;
}

export interface SystemStatus {
  hardware: HardwareInfo;
  installed_models: InstalledModel[];
  downloads: ModelDownload[];
}

export interface Workspace {
  id: string;
  name: string;
  model?: string | null;
  is_default?: boolean;
  created_at?: string;
  updated_at?: string;
}

export interface ManagedFile {
  id: string;
  workspace_id: string;
  file_name: string;
  file_path: string;
  mime_type: string;
  file_type: string;
  category: "document" | "image" | "spreadsheet" | "other";
  file_size: number;
  source: string;
  pinned: boolean;
  created_at?: string;
  updated_at?: string;
}

export interface PromptVariant {
  id: string;
  label: string;
  prompt: string;
}

export interface PromptStudioResult {
  original: string;
  variants: PromptVariant[];
  used_model?: string;
  execution?: Record<string, unknown>;
  image_prompt?: {
    enhanced_prompt?: string;
    negative_prompt?: string;
    suggested_style?: string;
    suggested_resolution?: string;
    suggested_aspect_ratio?: string;
  } | null;
}

export interface RuntimeDashboard {
  system_status: string;
  current_model: string | null;
  workspace: { id: string | null; name: string | null };
  resources: {
    ram: { total_gb: number; used_gb: number; available_gb: number; percent: number };
    cpu: { percent: number; count: number };
    gpu: {
      available: boolean;
      name: string | null;
      vram_total_mb: number;
      vram_used_mb: number;
      utilization_percent: number;
    };
    loaded_model: string | null;
    running_tasks: Array<{ id: string; kind: string; detail: string }>;
  };
  hardware: HardwareInfo;
  plugins: Array<{ id: string; name: string; version: string; capability: string; enabled: boolean }>;
  installed_models: InstalledModel[];
  downloads: ModelDownload[];
  artifacts_generated: number;
  supported_creator_types: string[];
  capabilities?: Array<Record<string, unknown>>;
  packs?: MarketplaceItem[];
  diagnostics?: Record<string, unknown>;
  telemetry?: Record<string, unknown>;
}

export interface MarketplaceItem {
  id: string;
  name: string;
  developer: string;
  version: string;
  description: string;
  category: string;
  rating: number;
  installs: number;
  featured?: boolean;
  installed?: boolean;
  hasUpdate?: boolean;
  capabilities?: string[];
}

export interface AttachedFile {
  id: string;
  file: File;
  name: string;
  size: number;
  type: string;
  previewText?: string;
}

export interface TimelineStep {
  id: string;
  label: string;
  status: "pending" | "active" | "done" | "error";
}
