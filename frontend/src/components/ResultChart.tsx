import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { ChartSpec } from "../api";
import { formatNumber, humanize } from "../format";

const SERIES = ["#2d5bd8", "#2e7d52", "#c97f0c", "#7a4fc2", "#b8402b", "#1f8a9c"];

interface Props {
  spec: ChartSpec;
  columns: string[];
  rows: (string | number | null)[][];
}

export function ResultChart({ spec, columns, rows }: Props) {
  if (spec.type === "table" || !rows.length) return null;

  if (spec.type === "kpi") {
    return (
      <div className="flex flex-wrap gap-4">
        {spec.y.map((col) => {
          const value = rows[0][columns.indexOf(col)];
          return (
            <div key={col} className="min-w-44 rounded-xl border border-grid bg-paper px-5 py-4">
              <p className="text-sm text-ink-soft">{humanize(col)}</p>
              <p className="mt-1 text-3xl font-semibold tracking-tight text-ink">{formatNumber(value, col)}</p>
            </div>
          );
        })}
      </div>
    );
  }

  const data = rows.slice(0, 60).map((row) => Object.fromEntries(columns.map((c, i) => [c, row[i]])));
  const x = spec.x ?? columns[0];
  const tick = { fill: "#4a5468", fontSize: 12 };
  const yFormatter = (v: number) => formatNumber(v, spec.y[0], true);
  const tooltip = (
    <Tooltip
      formatter={(value, name) => [formatNumber(value as number, String(name)), humanize(String(name))]}
      contentStyle={{ borderRadius: 10, border: "1px solid #dde3dc", fontSize: 13 }}
    />
  );

  return (
    <div className="h-72 w-full" role="img" aria-label={spec.title || "Result chart"}>
      <ResponsiveContainer width="100%" height="100%">
        {spec.type === "line" ? (
          <LineChart data={data} margin={{ top: 8, right: 16, left: 4, bottom: 4 }}>
            <CartesianGrid stroke="#e8ece7" vertical={false} />
            <XAxis dataKey={x} tick={tick} tickLine={false} axisLine={{ stroke: "#c5cec4" }} minTickGap={16} />
            <YAxis tick={tick} tickLine={false} axisLine={false} tickFormatter={yFormatter} width={64} />
            {tooltip}
            {spec.y.length > 1 && <Legend formatter={(v) => humanize(String(v))} />}
            {spec.y.map((col, i) => (
              <Line key={col} type="monotone" dataKey={col} stroke={SERIES[i % SERIES.length]} strokeWidth={2.4} dot={{ r: 2.5 }} activeDot={{ r: 5 }} />
            ))}
          </LineChart>
        ) : spec.type === "pie" ? (
          <PieChart>
            {tooltip}
            <Legend formatter={(v) => <span className="text-ink-soft">{String(v)}</span>} />
            <Pie data={data} dataKey={spec.y[0]} nameKey={x} innerRadius="52%" outerRadius="82%" paddingAngle={2} stroke="none">
              {data.map((_, i) => (
                <Cell key={i} fill={SERIES[i % SERIES.length]} />
              ))}
            </Pie>
          </PieChart>
        ) : (
          <BarChart data={data} margin={{ top: 8, right: 16, left: 4, bottom: 4 }}>
            <CartesianGrid stroke="#e8ece7" vertical={false} />
            <XAxis dataKey={x} tick={tick} tickLine={false} axisLine={{ stroke: "#c5cec4" }} interval={0} angle={data.length > 6 ? -25 : 0} textAnchor={data.length > 6 ? "end" : "middle"} height={data.length > 6 ? 70 : 30} />
            <YAxis tick={tick} tickLine={false} axisLine={false} tickFormatter={yFormatter} width={64} />
            {tooltip}
            {spec.y.length > 1 && <Legend formatter={(v) => humanize(String(v))} />}
            {spec.y.map((col, i) => (
              <Bar key={col} dataKey={col} fill={SERIES[i % SERIES.length]} radius={[5, 5, 0, 0]} maxBarSize={56} />
            ))}
          </BarChart>
        )}
      </ResponsiveContainer>
    </div>
  );
}
