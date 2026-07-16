import {
  Code2,
  FileSpreadsheet,
  FileText,
  Image as ImageIcon,
  Sparkles,
} from "lucide-react";
import { greetingForNow } from "../utils/format";

const ACTIONS = [
  { id: "pdf", label: "Create PDF", icon: FileText, prompt: "Create a clean, professional PDF document about " },
  { id: "excel", label: "Analyze Excel", icon: FileSpreadsheet, prompt: "Analyze this Excel/CSV data and summarize insights: " },
  { id: "summarize", label: "Summarize Document", icon: Sparkles, prompt: "Summarize the following document clearly: " },
  { id: "code", label: "Generate Code", icon: Code2, prompt: "Write clean, production-ready code to " },
  { id: "image", label: "Analyze Image", icon: ImageIcon, prompt: "Describe and analyze the attached image: " },
] as const;

interface Props {
  userName?: string;
  onQuickAction: (prompt: string) => void;
}

export function Greeting({ userName, onQuickAction }: Props) {
  const { title, subtitle } = greetingForNow(userName);

  return (
    <section className="home-hero" aria-labelledby="home-greeting">
      <p className="home-eyebrow">Mimir</p>
      <h1 id="home-greeting" className="home-title">
        {title}
      </h1>
      <p className="home-subtitle">{subtitle}</p>

      <div className="quick-actions" role="list">
        {ACTIONS.map((action) => {
          const Icon = action.icon;
          return (
            <button
              key={action.id}
              type="button"
              className="quick-action"
              role="listitem"
              onClick={() => onQuickAction(action.prompt)}
            >
              <Icon size={16} aria-hidden="true" />
              {action.label}
            </button>
          );
        })}
      </div>
    </section>
  );
}
