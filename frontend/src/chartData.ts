import type { ChartSpec } from "./api";

type Cell = string | number | null;

export interface ChartData {
  data: Record<string, Cell>[];
  /** Keys to plot (column names, or series values for long-format results). */
  keys: string[];
  /** Column whose name drives number formatting (money, %, counts). */
  valueColumn: string;
}

/**
 * Turns result rows into Recharts data. Long results such as
 * (region, year, revenue) are pivoted so every year becomes its own series.
 */
export function toChartData(spec: ChartSpec, columns: string[], rows: Cell[][], limit = 60): ChartData {
  const x = spec.x ?? columns[0];
  const valueColumn = spec.y[0] ?? "";
  if (spec.series && columns.includes(spec.series) && valueColumn) {
    const xi = columns.indexOf(x);
    const si = columns.indexOf(spec.series);
    const yi = columns.indexOf(valueColumn);
    const byX = new Map<string, Record<string, Cell>>();
    const keys: string[] = [];
    for (const row of rows) {
      const xv = String(row[xi]);
      const sv = String(row[si]);
      if (!keys.includes(sv)) keys.push(sv);
      if (!byX.has(xv)) byX.set(xv, { [x]: row[xi] });
      byX.get(xv)![sv] = row[yi];
    }
    keys.sort();
    return { data: [...byX.values()].slice(0, limit), keys, valueColumn };
  }
  const data = rows.slice(0, limit).map((row) => Object.fromEntries(columns.map((c, i) => [c, row[i]])));
  return { data, keys: spec.y, valueColumn };
}
