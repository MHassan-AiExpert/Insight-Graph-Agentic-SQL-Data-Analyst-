import { useState } from "react";
import { ChevronRight, KeyRound, Link2, MessageSquarePlus, Table2 } from "lucide-react";
import type { Health, TableInfo } from "../api";

interface Props {
  tables: TableInfo[];
  dialect: string;
  health: Health | null;
  onNewChat: () => void;
}

export function Logo() {
  return (
    <svg viewBox="0 0 32 32" className="size-8" aria-hidden>
      <rect width="32" height="32" rx="8" fill="#172033" />
      <path d="M9 22 16 10 23 19" stroke="#f3f5f2" strokeWidth="1.6" fill="none" />
      <circle cx="9" cy="22" r="3" fill="#2d5bd8" />
      <circle cx="16" cy="10" r="3" fill="#f3f5f2" />
      <circle cx="23" cy="19" r="3" fill="#2d5bd8" />
    </svg>
  );
}

export function Sidebar({ tables, dialect, health, onNewChat }: Props) {
  const [open, setOpen] = useState<string | null>("orders");

  return (
    <aside className="flex h-full w-72 flex-col border-r border-grid bg-sheet">
      <div className="flex items-center gap-2.5 px-5 pt-5 pb-4">
        <Logo />
        <div>
          <p className="text-[17px] leading-tight font-semibold tracking-tight text-ink">InsightGraph</p>
          <p className="text-xs text-ink-soft">Agentic SQL data analyst</p>
        </div>
      </div>

      <div className="px-4">
        <button
          type="button"
          onClick={onNewChat}
          className="flex w-full items-center justify-center gap-2 rounded-lg bg-ink px-3 py-2 text-sm font-medium text-paper hover:bg-ink/90"
        >
          <MessageSquarePlus size={16} /> New conversation
        </button>
      </div>

      <nav aria-label="Database schema" className="mt-5 min-h-0 flex-1 overflow-y-auto px-3 pb-4">
        <div className="mb-2 flex items-baseline justify-between px-2">
          <h2 className="text-sm font-semibold text-ink">Your data</h2>
          <span className="text-xs text-ink-faint">{dialect}</span>
        </div>
        <ul className="space-y-0.5">
          {tables.map((t) => {
            const expanded = open === t.name;
            const fkCols = new Set(t.foreign_keys.flatMap((f) => f.columns));
            return (
              <li key={t.name}>
                <button
                  type="button"
                  onClick={() => setOpen(expanded ? null : t.name)}
                  aria-expanded={expanded}
                  className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm hover:bg-paper"
                >
                  <ChevronRight size={14} className={`text-ink-faint transition-transform ${expanded ? "rotate-90" : ""}`} />
                  <Table2 size={14} className="text-cobalt" />
                  <span className="flex-1 font-medium text-ink">{t.name}</span>
                  <span className="text-xs text-ink-faint tabular-nums">{t.row_count.toLocaleString()}</span>
                </button>
                {expanded && (
                  <ul className="mt-0.5 mb-2 ml-[1.9rem] space-y-0.5 border-l border-grid pl-3">
                    {t.columns.map((c) => (
                      <li key={c.name} className="flex items-center gap-1.5 py-0.5 text-[13px]">
                        {c.primary_key ? (
                          <KeyRound size={12} className="text-amber" aria-label="Primary key" />
                        ) : fkCols.has(c.name) ? (
                          <Link2 size={12} className="text-cobalt" aria-label="Foreign key" />
                        ) : (
                          <span className="size-3" />
                        )}
                        <span className="text-ink">{c.name}</span>
                        <span className="ml-auto font-mono text-[11px] text-ink-faint lowercase">{c.type}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </li>
            );
          })}
        </ul>
      </nav>

      <div className="border-t border-grid px-5 py-3 text-xs text-ink-soft">
        {health ? (
          <p className="flex items-center gap-2">
            <span className={`size-2 rounded-full ${health.llm.ready ? "bg-moss" : "bg-brick"}`} />
            <span className="truncate">
              {!health.llm.ready
                ? "Model not configured"
                : health.llm.provider === "scripted"
                  ? "Evaluation mode: recorded model responses"
                  : `${health.llm.model} via ${health.llm.provider}`}
            </span>
          </p>
        ) : (
          <p>Connecting to API…</p>
        )}
      </div>
    </aside>
  );
}
