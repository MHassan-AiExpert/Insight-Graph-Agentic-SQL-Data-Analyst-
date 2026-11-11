import { Fragment, useState } from "react";
import { Check, Copy } from "lucide-react";

const KEYWORDS = new Set(
  (
    "select from where join left right inner outer on group by order having limit as and or not in is null " +
    "with case when then else end distinct union all asc desc between like count sum avg min max round cast " +
    "strftime coalesce over partition date_trunc extract nullif"
  ).split(" "),
);

const TOKEN = /('(?:[^']|'')*')|(\b\d+(?:\.\d+)?\b)|([A-Za-z_][A-Za-z0-9_]*)|(\s+)|(.)/g;

function highlight(sql: string) {
  const parts: JSX.Element[] = [];
  let m: RegExpExecArray | null;
  let i = 0;
  TOKEN.lastIndex = 0;
  while ((m = TOKEN.exec(sql))) {
    const [text, str, num, word] = m;
    if (str) parts.push(<span key={i++} className="sql-string">{text}</span>);
    else if (num) parts.push(<span key={i++} className="sql-number">{text}</span>);
    else if (word && KEYWORDS.has(word.toLowerCase())) parts.push(<span key={i++} className="sql-keyword">{text}</span>);
    else parts.push(<Fragment key={i++}>{text}</Fragment>);
  }
  return parts;
}

export function SqlViewer({ sql }: { sql: string }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(sql);
      setCopied(true);
      setTimeout(() => setCopied(false), 1600);
    } catch {
      setCopied(false);
    }
  };
  return (
    <div className="relative rounded-lg border border-grid bg-paper">
      <button
        type="button"
        onClick={copy}
        className="absolute top-2 right-2 inline-flex items-center gap-1 rounded-md border border-grid bg-sheet px-2 py-1 text-xs font-medium text-ink hover:bg-paper"
      >
        {copied ? <Check size={13} /> : <Copy size={13} />} {copied ? "Copied" : "Copy SQL"}
      </button>
      <pre className="overflow-x-auto p-4 pr-28 font-mono text-[13px] leading-relaxed text-ink">
        <code>{highlight(sql)}</code>
      </pre>
    </div>
  );
}
