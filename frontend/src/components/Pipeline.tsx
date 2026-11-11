import { useState } from "react";
import { Check, ChevronDown, CornerDownLeft, OctagonX, RotateCcw } from "lucide-react";
import type { AgentStep } from "../api";

const DATA_STAGES = [
  { key: "classify_intent", label: "Understand", short: "Intent" },
  { key: "select_tables", label: "Pick tables", short: "Tables" },
  { key: "generate_sql", label: "Write SQL", short: "SQL" },
  { key: "validate_sql", label: "Safety check", short: "Safety" },
  { key: "execute_sql", label: "Run query", short: "Run" },
  { key: "analyze_results", label: "Explain", short: "Explain" },
];

const DIRECT_STAGES = [
  { key: "classify_intent", label: "Understand", short: "Intent" },
  { key: "respond_direct", label: "Reply", short: "Reply" },
];

type NodeState = "pending" | "running" | "done" | "retry" | "blocked" | "error";

function stageState(key: string, steps: AgentStep[], running: boolean, nextKey: string | null): NodeState {
  const mine = steps.filter((s) => s.node === key);
  const last = mine[mine.length - 1];
  if (!last) return running && nextKey === key ? "running" : "pending";
  if (last.status === "blocked") return "blocked";
  if (last.status === "error") return "error";
  if (last.status === "retry") return running ? "retry" : "error";
  return "done";
}

function nextStage(stages: { key: string }[], steps: AgentStep[]): string | null {
  const last = steps[steps.length - 1];
  if (!last) return stages[0].key;
  if (last.status === "retry") return "generate_sql";
  const idx = stages.findIndex((s) => s.key === last.node);
  return idx >= 0 && idx < stages.length - 1 ? stages[idx + 1].key : null;
}

const NODE_STYLE: Record<NodeState, string> = {
  pending: "border-grid-strong bg-sheet text-ink-faint",
  running: "border-cobalt bg-cobalt-soft text-cobalt node-running",
  done: "border-moss bg-moss text-white",
  retry: "border-amber bg-amber-soft text-amber",
  blocked: "border-brick bg-brick text-white",
  error: "border-brick bg-brick-soft text-brick",
};

export function Pipeline({ steps, running }: { steps: AgentStep[]; running: boolean }) {
  const [open, setOpen] = useState(false);
  const direct = steps.some((s) => s.node === "respond_direct") || steps.some((s) => s.status === "blocked");
  const stages = direct ? DIRECT_STAGES : DATA_STAGES;
  const next = running ? nextStage(stages, steps) : null;
  const fixes = Math.max(0, steps.filter((s) => s.node === "generate_sql").length - 1);
  const visibleSteps = steps.filter((s) => s.node !== "finalize");

  return (
    <div className="rounded-xl border border-grid bg-paper/60 px-4 pt-4 pb-3">
      <ol className="flex items-start gap-0 overflow-x-auto pb-1" aria-label="Agent progress">
        {stages.map((stage, i) => {
          const state = stageState(stage.key, steps, running, next);
          return (
            <li key={stage.key} className="flex min-w-0 flex-1 items-start sm:min-w-[88px]">
              <div className="flex w-full flex-col items-center gap-1.5">
                <div className="flex w-full items-center">
                  <div className={`h-px flex-1 ${i === 0 ? "bg-transparent" : "bg-grid-strong"}`} />
                  <span
                    className={`grid size-7 shrink-0 place-items-center rounded-full border-2 text-[11px] font-semibold transition-colors ${NODE_STYLE[state]}`}
                    aria-label={`${stage.label}: ${state}`}
                  >
                    {state === "done" ? (
                      <Check size={14} strokeWidth={3} />
                    ) : state === "blocked" || state === "error" ? (
                      <OctagonX size={14} />
                    ) : state === "retry" ? (
                      <RotateCcw size={13} />
                    ) : (
                      i + 1
                    )}
                  </span>
                  <div className={`h-px flex-1 ${i === stages.length - 1 ? "bg-transparent" : "bg-grid-strong"}`} />
                </div>
                <span className={`text-center text-[11px] leading-tight sm:text-xs ${state === "pending" ? "text-ink-faint" : "text-ink"}`}>
                  <span className="sm:hidden">{stage.short}</span>
                  <span className="hidden sm:inline">{stage.label}</span>
                </span>
              </div>
            </li>
          );
        })}
      </ol>

      <div className="mt-2 flex flex-wrap items-center justify-between gap-2 text-xs text-ink-soft">
        <span className="flex items-center gap-1.5">
          {fixes > 0 && (
            <span className="inline-flex items-center gap-1 rounded-full bg-amber-soft px-2 py-0.5 font-medium text-amber">
              <CornerDownLeft size={12} /> Self-corrected {fixes} time{fixes > 1 ? "s" : ""}
            </span>
          )}
          {running && visibleSteps.length > 0 && <span>{visibleSteps[visibleSteps.length - 1].title}…</span>}
        </span>
        {visibleSteps.length > 0 && (
          <button
            type="button"
            onClick={() => setOpen((v) => !v)}
            className="inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 font-medium text-ink-soft hover:bg-grid/60"
            aria-expanded={open}
          >
            {open ? "Hide" : "Show"} reasoning trace
            <ChevronDown size={14} className={`transition-transform ${open ? "rotate-180" : ""}`} />
          </button>
        )}
      </div>

      {open && (
        <ol className="mt-3 space-y-2 border-t border-grid pt-3">
          {visibleSteps.map((s, i) => (
            <li key={i} className="grid grid-cols-[3.5rem_1fr] gap-3 text-sm">
              <span className="pt-0.5 text-right font-mono text-[11px] text-ink-faint">{(s.t_ms / 1000).toFixed(2)}s</span>
              <div>
                <p
                  className={`font-medium ${
                    s.status === "retry" ? "text-amber" : s.status === "blocked" || s.status === "error" ? "text-brick" : "text-ink"
                  }`}
                >
                  {s.title}
                </p>
                {s.detail && <p className="text-ink-soft">{s.detail}</p>}
              </div>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
