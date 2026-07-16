import { Activity, Cpu, HardDrive, Radio, Sparkles } from "lucide-react";
import type { SystemStatus } from "../types";

interface Props {
  status: SystemStatus | null;
  currentModel?: string | null;
  connected: boolean;
}

export function StatusBar({ status, currentModel, connected }: Props) {
  const hw = status?.hardware;
  const model =
    currentModel ||
    status?.installed_models?.[0]?.name ||
    "No model";

  return (
    <footer className="status-bar" role="status" aria-live="polite">
      <div className="status-item">
        <Activity size={13} aria-hidden="true" />
        <span>Runtime</span>
        <strong className={connected ? "ok" : "warn"}>{connected ? "Online" : "Offline"}</strong>
      </div>
      <div className="status-item">
        <Cpu size={13} aria-hidden="true" />
        <span>GPU</span>
        <strong>{hw?.has_gpu ? hw.gpu_name : "CPU"}</strong>
      </div>
      <div className="status-item">
        <HardDrive size={13} aria-hidden="true" />
        <span>RAM</span>
        <strong>{hw ? `${hw.ram_gb} GB` : "—"}</strong>
      </div>
      <div className="status-item">
        <Sparkles size={13} aria-hidden="true" />
        <span>Model</span>
        <strong title={model}>{model}</strong>
      </div>
      <div className="status-item">
        <Radio size={13} aria-hidden="true" />
        <span>Connection</span>
        <strong className={connected ? "ok" : "warn"}>{connected ? "Local" : "Disconnected"}</strong>
      </div>
    </footer>
  );
}
