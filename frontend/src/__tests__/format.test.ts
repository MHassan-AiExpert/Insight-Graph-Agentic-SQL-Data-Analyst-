import { describe, expect, it } from "vitest";
import { formatNumber, humanize } from "../format";

describe("humanize", () => {
  it("turns snake_case columns into labels", () => {
    expect(humanize("total_revenue")).toBe("Total revenue");
    expect(humanize("q3_2026_revenue")).toBe("Q3 2026 revenue");
  });
});

describe("formatNumber", () => {
  it("formats money columns", () => {
    expect(formatNumber(472022.45, "total_revenue")).toBe("$472,022");
    expect(formatNumber(815, "avg_order_value")).toBe("$815.00");
    expect(formatNumber(342.4321, "avg_order_value")).toBe("$342.43");
  });
  it("formats percentage columns given as 0-1 or 0-100", () => {
    expect(formatNumber(52.3, "share_pct")).toBe("52.3%");
    expect(formatNumber(0.481, "gross_margin")).toBe("48.1%");
  });
  it("formats counts and compact axis labels", () => {
    expect(formatNumber(1467, "orders")).toBe("1,467");
    expect(formatNumber(450000, "total_revenue", true)).toBe("$450K");
  });
  it("handles missing and text values", () => {
    expect(formatNumber(null, "x")).toBe("—");
    expect(formatNumber("Europe", "region")).toBe("Europe");
  });
});
