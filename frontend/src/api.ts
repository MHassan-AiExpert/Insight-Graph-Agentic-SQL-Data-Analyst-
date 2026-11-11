export type StepStatus = "done" | "retry" | "blocked" | "error";

export interface AgentStep {
  node: string;
  title: string;
  detail: string;
  status: StepStatus;
  data: Record<string, unknown>;
  t_ms: number;
}

export interface ChartSpec {
  type: "bar" | "line" | "pie" | "kpi" | "table";
  x: string | null;
  y: string[];
  title: string;
}

export interface AttemptRecord {
  attempt: number;
  sql: string;
  stage: string;
  error: string;
}

export interface AskResult {
  thread_id: string;
  question: string;
  standalone_question: string;
  status: "answered" | "chat" | "refused" | "failed";
  intent: string;
  answer: string;
  key_findings: string[];
  sql: string;
  sql_reasoning: string;
  assumptions: string[];
  selected_tables: string[];
  columns: string[];
  rows: (string | number | null)[][];
  row_count: number;
  chart: ChartSpec | null;
  follow_ups: string[];
  attempts: number;
  attempt_log: AttemptRecord[];
  limit_applied: boolean;
  truncated: boolean;
  exec_ms: number;
  elapsed_ms: number;
}

export interface ColumnInfo {
  name: string;
  type: string;
  nullable: boolean;
  primary_key: boolean;
}

export interface TableInfo {
  name: string;
  row_count: number;
  columns: ColumnInfo[];
  foreign_keys: { columns: string[]; references_table: string; references_columns: string[] }[];
}

export interface Health {
  status: "ok" | "degraded";
  llm: { provider: string; model: string; ready: boolean; error?: string };
  database: { dialect: string; tables: number };
}

const BASE = import.meta.env.VITE_API_BASE ?? "";

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) throw new Error(`${path} returned ${res.status}`);
  return res.json() as Promise<T>;
}

export const api = {
  health: () => getJson<Health>("/api/health"),
  schema: () => getJson<{ dialect: string; tables: TableInfo[] }>("/api/schema"),
  examples: () => getJson<{ questions: string[] }>("/api/examples"),
};

export interface StreamHandlers {
  onStart?: (threadId: string) => void;
  onStep: (step: AgentStep) => void;
  onResult: (result: AskResult) => void;
  onError: (message: string) => void;
}

/** POST a question and consume the Server-Sent Events stream. */
export async function askStream(
  question: string,
  threadId: string | null,
  handlers: StreamHandlers,
  signal?: AbortSignal,
): Promise<void> {
  let res: Response;
  try {
    res = await fetch(`${BASE}/api/ask/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
      body: JSON.stringify({ question, thread_id: threadId }),
      signal,
    });
  } catch {
    handlers.onError("Can't reach the InsightGraph API. Check that the backend is running on port 8000.");
    return;
  }
  if (!res.ok || !res.body) {
    handlers.onError(`The API returned ${res.status}. Check the question and try again.`);
    return;
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  const dispatch = (block: string) => {
    let event = "message";
    const dataLines: string[] = [];
    for (const raw of block.split(/\r?\n/)) {
      if (raw.startsWith("event:")) event = raw.slice(6).trim();
      else if (raw.startsWith("data:")) dataLines.push(raw.slice(5).trimStart());
    }
    if (!dataLines.length) return;
    const data = JSON.parse(dataLines.join("\n"));
    if (event === "start") handlers.onStart?.(data.thread_id);
    else if (event === "step") handlers.onStep(data as AgentStep);
    else if (event === "result") handlers.onResult(data as AskResult);
    else if (event === "error") handlers.onError(data.message);
  };

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const blocks = buffer.split(/\r?\n\r?\n/);
    buffer = blocks.pop() ?? "";
    blocks.forEach(dispatch);
  }
  if (buffer.trim()) dispatch(buffer);
}
