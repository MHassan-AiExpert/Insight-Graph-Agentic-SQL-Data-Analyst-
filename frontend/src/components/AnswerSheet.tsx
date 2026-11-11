import { useState } from "react";
import { AlertTriangle, ShieldX, Timer } from "lucide-react";
import type { AgentStep, AskResult } from "../api";
import { Pipeline } from "./Pipeline";
import { ResultChart } from "./ResultChart";
import { ResultsTable } from "./ResultsTable";
import { SqlViewer } from "./SqlViewer";

export interface Turn {
  id: string;
  question: string;
  steps: AgentStep[];
  result?: AskResult;
  error?: string;
  running: boolean;
}

type Tab = "results" | "sql" | "details";

export function AnswerSheet({ turn, onAsk }: { turn: Turn; onAsk: (q: string) => void }) {
  const { result } = turn;
  const hasData = result?.status === "answered" && result.columns.length > 0;
  const [tab, setTab] = useState<Tab>("results");
  const reinterpreted =
    result?.standalone_question && result.standalone_question.trim().toLowerCase() !== turn.question.trim().toLowerCase();

  return (
    <article className="rounded-2xl border border-grid bg-sheet shadow-[0_1px_0_#dde3dc,0_12px_32px_-24px_rgba(23,32,51,0.35)]">
      <header className="border-b border-grid px-6 pt-5 pb-4">
        <h2 className="text-lg leading-snug font-semibold text-ink">{turn.question}</h2>
        {reinterpreted && <p className="mt-1 text-sm text-ink-soft">Interpreted as: {result!.standalone_question}</p>}
      </header>

      <div className="space-y-5 px-6 py-5">
        <Pipeline steps={turn.steps} running={turn.running} />

        {turn.error && (
          <div className="flex gap-3 rounded-lg border border-brick/30 bg-brick-soft px-4 py-3 text-sm text-brick">
            <AlertTriangle size={18} className="mt-0.5 shrink-0" />
            <p>{turn.error}</p>
          </div>
        )}

        {result && (
          <>
            <section aria-label="Answer">
              {result.status === "refused" && (
                <p className="mb-2 inline-flex items-center gap-1.5 rounded-full bg-brick-soft px-2.5 py-1 text-xs font-medium text-brick">
                  <ShieldX size={13} /> Blocked: read-only assistant
                </p>
              )}
              <p className="max-w-[72ch] whitespace-pre-line text-[15.5px] text-ink">{result.answer}</p>
              {result.key_findings.length > 0 && (
                <ul className="mt-3 max-w-[72ch] space-y-1.5">
                  {result.key_findings.map((f, i) => (
                    <li key={i} className="flex gap-2.5 text-[15px] text-ink-soft">
                      <span className="mt-2 size-1.5 shrink-0 rounded-full bg-cobalt" />
                      {f}
                    </li>
                  ))}
                </ul>
              )}
            </section>

            {hasData && result.chart && result.chart.type !== "table" && (
              <section aria-label="Chart" className="rounded-xl border border-grid p-4">
                {result.chart.title && <h3 className="mb-3 text-sm font-semibold text-ink">{result.chart.title}</h3>}
                <ResultChart spec={result.chart} columns={result.columns} rows={result.rows} />
              </section>
            )}

            {(hasData || result.sql) && (
              <section>
                <div role="tablist" className="mb-3 flex gap-1 border-b border-grid">
                  {(
                    [
                      ["results", "Results", hasData],
                      ["sql", "SQL", Boolean(result.sql)],
                      ["details", "How it was built", true],
                    ] as [Tab, string, boolean][]
                  )
                    .filter(([, , show]) => show)
                    .map(([key, label]) => (
                      <button
                        key={key}
                        role="tab"
                        aria-selected={tab === key}
                        onClick={() => setTab(key)}
                        className={`-mb-px border-b-2 px-3 py-2 text-sm font-medium ${
                          tab === key ? "border-cobalt text-cobalt" : "border-transparent text-ink-soft hover:text-ink"
                        }`}
                      >
                        {label}
                      </button>
                    ))}
                </div>
                {tab === "results" && hasData && <ResultsTable columns={result.columns} rows={result.rows} truncated={result.truncated} />}
                {(tab === "sql" || (tab === "results" && !hasData)) && result.sql && <SqlViewer sql={result.sql} />}
                {tab === "details" && (
                  <dl className="grid gap-x-6 gap-y-3 text-sm sm:grid-cols-[10rem_1fr]">
                    <dt className="text-ink-faint">Approach</dt>
                    <dd className="text-ink">{result.sql_reasoning || "—"}</dd>
                    <dt className="text-ink-faint">Tables used</dt>
                    <dd className="flex flex-wrap gap-1.5">
                      {result.selected_tables.map((t) => (
                        <code key={t} className="rounded bg-paper px-1.5 py-0.5 font-mono text-xs">
                          {t}
                        </code>
                      ))}
                    </dd>
                    {result.assumptions.length > 0 && (
                      <>
                        <dt className="text-ink-faint">Assumptions</dt>
                        <dd>
                          <ul className="list-disc space-y-1 pl-4 text-ink">
                            {result.assumptions.map((a, i) => (
                              <li key={i}>{a}</li>
                            ))}
                          </ul>
                        </dd>
                      </>
                    )}
                    <dt className="text-ink-faint">Attempts</dt>
                    <dd className="text-ink">
                      {result.attempts}
                      {result.attempt_log.length > 0 && (
                        <ul className="mt-2 space-y-2">
                          {result.attempt_log.map((a, i) => (
                            <li key={i} className="rounded-md border border-amber/30 bg-amber-soft px-3 py-2">
                              <p className="font-medium text-amber">
                                Attempt {a.attempt}: {a.stage.replace("_", " ")}
                              </p>
                              <p className="text-ink-soft">{a.error}</p>
                            </li>
                          ))}
                        </ul>
                      )}
                    </dd>
                  </dl>
                )}
              </section>
            )}

            <footer className="flex flex-wrap items-center justify-between gap-3 border-t border-grid pt-4">
              <div className="flex flex-wrap gap-2">
                {result.follow_ups.map((q) => (
                  <button
                    key={q}
                    type="button"
                    onClick={() => onAsk(q)}
                    className="rounded-full border border-grid-strong bg-sheet px-3 py-1 text-sm text-ink hover:border-cobalt hover:text-cobalt"
                  >
                    {q}
                  </button>
                ))}
              </div>
              <span className="inline-flex items-center gap-1 text-xs text-ink-faint">
                <Timer size={13} />{" "}
                {result.elapsed_ms < 1000 ? `${Math.round(result.elapsed_ms)} ms` : `${(result.elapsed_ms / 1000).toFixed(1)} s`} total
                {hasData && `, query ${result.exec_ms.toFixed(0)} ms`}
              </span>
            </footer>
          </>
        )}
      </div>
    </article>
  );
}
