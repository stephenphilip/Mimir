import { Check, Loader2, X } from "lucide-react";
import type { TimelineStep } from "../types";

interface Props {
  steps: TimelineStep[];
}

export function ExecutionTimeline({ steps }: Props) {
  if (!steps.length) return null;

  return (
    <ol className="exec-timeline" aria-label="Execution timeline">
      {steps.map((step, index) => (
        <li key={step.id} className={`timeline-step is-${step.status}`}>
          <div className="timeline-rail" aria-hidden="true">
            <span className="timeline-dot">
              {step.status === "done" && <Check size={10} />}
              {step.status === "active" && <Loader2 size={10} className="spin" />}
              {step.status === "error" && <X size={10} />}
              {step.status === "pending" && <span className="dot-idle" />}
            </span>
            {index < steps.length - 1 && <span className="timeline-line" />}
          </div>
          <span className="timeline-label">{step.label}</span>
        </li>
      ))}
    </ol>
  );
}
