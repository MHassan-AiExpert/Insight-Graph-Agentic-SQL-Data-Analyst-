import { useCallback, useEffect, useRef, useState } from "react";
import { BarChart3, LineChart, Menu, PieChart, ShieldCheck, Trophy, X } from "lucide-react";
import { api, askStream, type Health, type TableInfo } from "./api";
import { AnswerSheet, type Turn } from "./components/AnswerSheet";
import { Composer } from "./components/Composer";
import { Logo, Sidebar } from "./components/Sidebar";

const STARTERS = [
  { q: "What is total revenue by region?", icon: BarChart3, hint: "Compare categories" },
  { q: "Show monthly revenue for 2026 as a trend", icon: LineChart, hint: "Spot a trend" },
  { q: "Who are the top 10 customers by lifetime value?", icon: Trophy, hint: "Rank and filter" },
  { q: "What share of orders comes from each sales channel?", icon: PieChart, hint: "See the mix" },
];

export default function App() {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [threadId, setThreadId] = useState<string | null>(null);
  const [tables, setTables] = useState<TableInfo[]>([]);
  const [dialect, setDialect] = useState("");
  const [health, setHealth] = useState<Health | null>(null);
  const [menuOpen, setMenuOpen] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const endRef = useRef<HTMLDivElement>(null);
  const busy = turns.some((t) => t.running);

  useEffect(() => {
    api.health().then(setHealth).catch(() => setHealth(null));
    api
      .schema()
      .then((s) => {
        setTables(s.tables);
        setDialect(s.dialect);
      })
      .catch(() => setTables([]));
  }, []);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [turns.length]);

  const update = (id: string, fn: (t: Turn) => Turn) => setTurns((all) => all.map((t) => (t.id === id ? fn(t) : t)));

  const ask = useCallback(
    async (question: string) => {
      if (busy) return;
      const id = crypto.randomUUID();
      setTurns((all) => [...all, { id, question, steps: [], running: true }]);
      const controller = new AbortController();
      abortRef.current = controller;
      await askStream(
        question,
        threadId,
        {
          onStart: (tid) => setThreadId(tid),
          onStep: (step) => update(id, (t) => ({ ...t, steps: [...t.steps, step] })),
          onResult: (result) => update(id, (t) => ({ ...t, result, running: false })),
          onError: (message) => update(id, (t) => ({ ...t, error: message, running: false })),
        },
        controller.signal,
      ).catch(() => undefined);
      update(id, (t) => (t.running ? { ...t, running: false, error: t.result ? undefined : "Stopped." } : t));
    },
    [busy, threadId],
  );

  const newChat = () => {
    abortRef.current?.abort();
    setTurns([]);
    setThreadId(null);
    setMenuOpen(false);
  };

  return (
    <div className="flex h-full">
      <div className="hidden lg:block">
        <Sidebar tables={tables} dialect={dialect} health={health} onNewChat={newChat} />
      </div>
      {menuOpen && (
        <div className="fixed inset-0 z-30 flex lg:hidden">
          <Sidebar tables={tables} dialect={dialect} health={health} onNewChat={newChat} />
          <button type="button" aria-label="Close menu" className="flex-1 bg-ink/30" onClick={() => setMenuOpen(false)} />
        </div>
      )}

      <main className="graph-paper flex min-w-0 flex-1 flex-col">
        <div className="flex items-center gap-3 border-b border-grid bg-sheet px-4 py-3 lg:hidden">
          <button type="button" onClick={() => setMenuOpen((v) => !v)} aria-label="Open menu" className="rounded-md p-1 hover:bg-paper">
            {menuOpen ? <X size={20} /> : <Menu size={20} />}
          </button>
          <Logo />
          <span className="font-semibold">InsightGraph</span>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto">
          <div className="mx-auto w-full max-w-[920px] px-4 py-8 sm:px-6">
            {turns.length === 0 ? (
              <section className="pt-6 sm:pt-14">
                <h1 className="max-w-[20ch] text-[2.6rem] text-balance leading-[1.05] font-semibold tracking-[-0.02em] text-ink sm:text-[3.4rem]">
                  Ask your database a question.
                </h1>
                <p className="mt-4 max-w-[58ch] text-[17px] text-ink-soft">
                  InsightGraph writes the SQL, checks it is safe, runs it, fixes its own mistakes and explains the
                  result with a chart. Every step is shown, so you can trust the answer.
                </p>
                <p className="mt-4 inline-flex items-center gap-2 rounded-full border border-moss/30 bg-moss-soft px-3 py-1 text-sm text-moss">
                  <ShieldCheck size={15} /> Read-only access. Your data is never changed.
                </p>
                <div className="mt-10 grid gap-3 sm:grid-cols-2">
                  {STARTERS.map(({ q, icon: Icon, hint }) => (
                    <button
                      key={q}
                      type="button"
                      onClick={() => ask(q)}
                      className="group flex items-start gap-3 rounded-xl border border-grid bg-sheet p-4 text-left hover:border-cobalt"
                    >
                      <span className="grid size-9 shrink-0 place-items-center rounded-lg bg-cobalt-soft text-cobalt">
                        <Icon size={18} />
                      </span>
                      <span>
                        <span className="block font-medium text-ink group-hover:text-cobalt">{q}</span>
                        <span className="text-sm text-ink-faint">{hint}</span>
                      </span>
                    </button>
                  ))}
                </div>
              </section>
            ) : (
              <div className="space-y-6">
                {turns.map((t) => (
                  <AnswerSheet key={t.id} turn={t} onAsk={ask} />
                ))}
              </div>
            )}
            <div ref={endRef} />
          </div>
        </div>

        <div className="border-t border-grid/70 bg-paper/90 backdrop-blur">
          <div className="mx-auto w-full max-w-[920px] px-4 py-3 sm:px-6">
            <Composer busy={busy} onSubmit={ask} onStop={() => abortRef.current?.abort()} />
            <p className="mt-2 text-center text-xs text-ink-faint">
              Follow-up questions remember this conversation. Press Shift + Enter for a new line.
            </p>
          </div>
        </div>
      </main>
    </div>
  );
}
