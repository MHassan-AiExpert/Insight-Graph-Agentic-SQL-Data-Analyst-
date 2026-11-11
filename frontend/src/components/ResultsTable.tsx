import { useMemo, useState } from "react";
import { ArrowDown, ArrowUp, Download } from "lucide-react";
import { formatNumber, humanize } from "../format";

type Cell = string | number | null;
const PAGE = 25;

function toCsv(columns: string[], rows: Cell[][]): string {
  const esc = (v: Cell) => {
    const s = v === null ? "" : String(v);
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  return [columns.map(esc).join(","), ...rows.map((r) => r.map(esc).join(","))].join("\n");
}

export function ResultsTable({ columns, rows, truncated }: { columns: string[]; rows: Cell[][]; truncated: boolean }) {
  const [sort, setSort] = useState<{ col: number; dir: 1 | -1 } | null>(null);
  const [page, setPage] = useState(0);

  const sorted = useMemo(() => {
    if (!sort) return rows;
    return [...rows].sort((a, b) => {
      const x = a[sort.col];
      const y = b[sort.col];
      if (x === y) return 0;
      if (x === null) return 1;
      if (y === null) return -1;
      return (x > y ? 1 : -1) * sort.dir;
    });
  }, [rows, sort]);

  const pages = Math.max(1, Math.ceil(sorted.length / PAGE));
  const visible = sorted.slice(page * PAGE, page * PAGE + PAGE);
  const numeric = columns.map((_, i) => rows.some((r) => typeof r[i] === "number"));

  const download = () => {
    const blob = new Blob([toCsv(columns, rows)], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "insightgraph-result.csv";
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div>
      <div className="overflow-x-auto rounded-lg border border-grid">
        <table className="w-full border-collapse text-sm">
          <thead className="bg-paper">
            <tr>
              {columns.map((c, i) => (
                <th key={c} scope="col" className={`border-b border-grid px-3 py-2 font-semibold text-ink ${numeric[i] ? "text-right" : "text-left"}`}>
                  <button
                    type="button"
                    className="inline-flex items-center gap-1 hover:text-cobalt"
                    onClick={() => {
                      setPage(0);
                      setSort((s) => (s?.col === i ? { col: i, dir: s.dir === 1 ? -1 : 1 } : { col: i, dir: numeric[i] ? -1 : 1 }));
                    }}
                  >
                    {humanize(c)}
                    {sort?.col === i && (sort.dir === 1 ? <ArrowUp size={13} /> : <ArrowDown size={13} />)}
                  </button>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {visible.map((row, r) => (
              <tr key={r} className="odd:bg-sheet even:bg-paper/50 hover:bg-cobalt-soft/50">
                {row.map((v, i) => (
                  <td key={i} className={`border-b border-grid/70 px-3 py-1.5 whitespace-nowrap ${numeric[i] ? "text-right tabular-nums" : ""}`}>
                    {numeric[i] ? formatNumber(v, columns[i]) : v ?? "—"}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="mt-2 flex flex-wrap items-center justify-between gap-2 text-xs text-ink-soft">
        <span>
          {rows.length.toLocaleString()} row{rows.length === 1 ? "" : "s"}
          {truncated && ", showing the first rows only (row limit reached)"}
        </span>
        <div className="flex items-center gap-2">
          {pages > 1 && (
            <span className="flex items-center gap-1">
              <button type="button" disabled={page === 0} onClick={() => setPage((p) => p - 1)} className="rounded px-2 py-0.5 hover:bg-grid disabled:opacity-40">
                Previous
              </button>
              <span>
                {page + 1} / {pages}
              </span>
              <button type="button" disabled={page >= pages - 1} onClick={() => setPage((p) => p + 1)} className="rounded px-2 py-0.5 hover:bg-grid disabled:opacity-40">
                Next
              </button>
            </span>
          )}
          <button type="button" onClick={download} className="inline-flex items-center gap-1 rounded-md border border-grid px-2 py-1 font-medium text-ink hover:bg-paper">
            <Download size={13} /> Download CSV
          </button>
        </div>
      </div>
    </div>
  );
}
