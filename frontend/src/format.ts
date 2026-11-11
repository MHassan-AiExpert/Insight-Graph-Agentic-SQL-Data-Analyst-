const MONEY = /(revenue|sales|profit|cost|value|amount|price|aov|spend|ltv)/i;
const PERCENT = /(rate|pct|percent|share|margin)/i;

export function humanize(column: string): string {
  const text = column.replace(/_/g, " ").trim();
  return text.charAt(0).toUpperCase() + text.slice(1);
}

export function formatNumber(value: unknown, column = "", compact = false): string {
  if (value === null || value === undefined || value === "") return "—";
  if (typeof value !== "number") return String(value);
  const isPercent = PERCENT.test(column) && Math.abs(value) <= 100;
  if (isPercent) {
    const pct = Math.abs(value) <= 1 ? value * 100 : value;
    return `${pct.toLocaleString(undefined, { maximumFractionDigits: 1 })}%`;
  }
  const money = MONEY.test(column);
  let opts: Intl.NumberFormatOptions;
  if (compact) opts = { notation: "compact", maximumFractionDigits: 1 };
  else if (money) opts = Math.abs(value) >= 1000 ? { maximumFractionDigits: 0 } : { minimumFractionDigits: 2, maximumFractionDigits: 2 };
  else opts = { maximumFractionDigits: Number.isInteger(value) ? 0 : 2 };
  const formatted = value.toLocaleString("en-US", opts);
  return money ? `$${formatted}` : formatted;
}
