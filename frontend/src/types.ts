export type NavView = "home" | "chats" | "models" | "marketplace" | "memory" | "settings";

export interface Conversation {
  id: string;
  title: string;
  updated_at: string;
  pinned?: boolean;
  archived?: boolean;
  project_id?: string;
}

export interface Artifact {
  id?: number | string;
  file_name: string;
  file_path: string;
  file_type: string;
  file_size: number;
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
