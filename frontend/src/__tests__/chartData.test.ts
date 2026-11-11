import { describe, expect, it } from "vitest";
import { toChartData } from "../chartData";

describe("toChartData", () => {
  it("pivots long results into one series per value", () => {
    const { data, keys, valueColumn } = toChartData(
      { type: "bar", x: "region", y: ["revenue"], title: "", series: "year" },
      ["region", "year", "revenue"],
      [["Asia", "2026", 2], ["Asia", "2025", 1], ["Europe", "2025", 3], ["Europe", "2026", 4]],
    );
    expect(keys).toEqual(["2025", "2026"]);
    expect(valueColumn).toBe("revenue");
    expect(data).toEqual([
      { region: "Asia", "2026": 2, "2025": 1 },
      { region: "Europe", "2025": 3, "2026": 4 },
    ]);
  });

  it("keeps wide results as they are", () => {
    const { data, keys } = toChartData(
      { type: "bar", x: "region", y: ["q3_2025", "q3_2026"], title: "" },
      ["region", "q3_2025", "q3_2026"],
      [["Asia", 1, 2]],
    );
    expect(keys).toEqual(["q3_2025", "q3_2026"]);
    expect(data).toEqual([{ region: "Asia", q3_2025: 1, q3_2026: 2 }]);
  });
});
