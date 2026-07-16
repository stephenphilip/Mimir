import type { TimelineStep } from "../types";

/** Map raw orchestrator status strings into a clear investor-facing timeline. */
export function mapStatusToStep(status: string): { key: string; label: string } {
  const s = status.toLowerCase();

  if (s.includes("detected intent")) {
    const intent = status
      .replace(/^Detected intent:\s*/i, "")
      .replace(/\s*\(confidence.*$/i, "")
      .trim();
    return { key: "intent", label: `Intent: ${intent}` };
  }
  if (s.includes("detecting intent")) {
    return { key: "intent", label: "Detecting intent" };
  }
  if (s.includes("capability") || s.includes("requirement") || s.includes("mapping")) {
    if (s.startsWith("requirements:")) {
      return { key: "capabilities", label: status.replace(/^Requirements:\s*/i, "Needs: ") };
    }
    return { key: "capabilities", label: "Mapping capabilities" };
  }
  if (s.includes("queuing recommended") || s.includes("download")) {
    return { key: "download", label: status.length > 64 ? `${status.slice(0, 61)}…` : status };
  }
  if (s.includes("selected model") || s.includes("selecting best") || s.includes("target model")) {
    return {
      key: "model",
      label: status.includes("Selected model:")
        ? status.replace(/^Selected model:\s*/i, "Model: ")
        : "Selecting model",
    };
  }
  if (s.includes("bypass") || s.includes("running on loaded")) {
    return { key: "model", label: "Using faster local model" };
  }
  if (s.includes("preparing runtime") || s.includes("optimizing") || s.includes("unload")) {
    return { key: "prepare", label: "Preparing runtime" };
  }
  if (s.includes("generating response")) {
    const model = status.replace(/^.*using\s+/i, "").replace(/\.\.\.$/, "").trim();
    return {
      key: "generate",
      label: model ? `Generating with ${model}` : "Generating response",
    };
  }
  if (s.includes("executing") || s.includes("python")) {
    return { key: "execute", label: "Running Python" };
  }
  if (s.includes("pdf")) return { key: "artifact", label: "Generating PDF" };
  if (s.includes("excel") || s.includes("spreadsheet")) {
    return { key: "artifact", label: "Generating spreadsheet" };
  }
  return { key: status.slice(0, 40), label: status };
}

export function buildTimeline(
  statuses: string[],
  opts?: { hasContent?: boolean; done?: boolean; error?: boolean }
): TimelineStep[] {
  const seen = new Map<string, TimelineStep>();
  for (const status of statuses) {
    const { key, label } = mapStatusToStep(status);
    seen.set(key, { id: key, label, status: "done" });
  }

  const steps = Array.from(seen.values());
  if (steps.length === 0) return [];

  if (opts?.error) {
    steps[steps.length - 1] = { ...steps[steps.length - 1], status: "error" };
    return steps;
  }

  if (opts?.done) {
    return [
      ...steps.map((s) => ({ ...s, status: "done" as const })),
      { id: "completed", label: "Completed", status: "done" },
    ];
  }

  return steps.map((s, i) =>
    i === steps.length - 1 && !opts?.hasContent
      ? { ...s, status: "active" }
      : {
          ...s,
          status: i === steps.length - 1 && opts?.hasContent ? "active" : "done",
        }
  );
}
