// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { Pipeline } from "../components/Pipeline";
import { ResultsTable } from "../components/ResultsTable";
import { Composer } from "../components/Composer";
import type { AgentStep } from "../api";

afterEach(cleanup);

const step = (node: string, status: AgentStep["status"] = "done", title = node): AgentStep => ({
  node, title, detail: "", status, data: {}, t_ms: 1,
});

describe("Pipeline", () => {
  it("marks completed stages and shows the self-correction badge", () => {
    const steps = [
      step("classify_intent"), step("select_tables"), step("generate_sql"), step("validate_sql"),
      step("execute_sql", "retry"), step("generate_sql"), step("validate_sql"), step("execute_sql"), step("analyze_results"),
    ];
    render(<Pipeline steps={steps} running={false} />);
    expect(screen.getByLabelText("Run query: done")).toBeTruthy();
    expect(screen.getByLabelText("Explain: done")).toBeTruthy();
    expect(screen.getByText(/Self-corrected 1 time/)).toBeTruthy();
  });

  it("collapses to Understand and Reply for a blocked request", () => {
    render(<Pipeline steps={[step("classify_intent", "blocked"), step("respond_direct")]} running={false} />);
    expect(screen.getByLabelText("Understand: blocked")).toBeTruthy();
    expect(screen.getByLabelText("Reply: done")).toBeTruthy();
    expect(screen.queryByText("Write SQL")).toBeNull();
  });

  it("shows the running stage while streaming", () => {
    render(<Pipeline steps={[step("classify_intent")]} running />);
    expect(screen.getByLabelText("Pick tables: running")).toBeTruthy();
  });

  it("expands the reasoning trace", () => {
    render(<Pipeline steps={[step("classify_intent", "done", "Understood the question")]} running={false} />);
    fireEvent.click(screen.getByText(/Show reasoning trace/));
    expect(screen.getByText("Understood the question")).toBeTruthy();
  });
});

describe("ResultsTable", () => {
  const columns = ["region", "total_revenue"];
  const rows = [["Europe", 412031.4], ["Asia Pacific", 318857.45], ["North America", 472022.45]];

  it("formats numbers and sorts by a column", () => {
    render(<ResultsTable columns={columns} rows={rows} truncated={false} />);
    expect(screen.getByText("$412,031")).toBeTruthy();
    fireEvent.click(screen.getByText("Region"));
    const firstCell = () => document.querySelector("tbody tr td")!.textContent;
    expect(firstCell()).toBe("Asia Pacific");
    fireEvent.click(screen.getByText("Total revenue"));
    expect(firstCell()).toBe("North America");
  });

  it("only mentions the row limit when results were truncated", () => {
    const { rerender } = render(<ResultsTable columns={columns} rows={rows} truncated={false} />);
    expect(screen.queryByText(/row limit reached/)).toBeNull();
    rerender(<ResultsTable columns={columns} rows={rows} truncated />);
    expect(screen.getByText(/row limit reached/)).toBeTruthy();
  });
});

describe("Composer", () => {
  it("submits on Enter and keeps Shift+Enter for new lines", () => {
    const onSubmit = vi.fn();
    render(<Composer busy={false} onSubmit={onSubmit} onStop={vi.fn()} />);
    const box = screen.getByLabelText("Ask a question about your data");
    fireEvent.change(box, { target: { value: "Revenue by region" } });
    fireEvent.keyDown(box, { key: "Enter", shiftKey: true });
    expect(onSubmit).not.toHaveBeenCalled();
    fireEvent.keyDown(box, { key: "Enter" });
    expect(onSubmit).toHaveBeenCalledWith("Revenue by region");
  });

  it("does not submit an empty question and shows Stop while busy", () => {
    const onSubmit = vi.fn();
    const { rerender } = render(<Composer busy={false} onSubmit={onSubmit} onStop={vi.fn()} />);
    fireEvent.keyDown(screen.getByLabelText("Ask a question about your data"), { key: "Enter" });
    expect(onSubmit).not.toHaveBeenCalled();
    rerender(<Composer busy onSubmit={onSubmit} onStop={vi.fn()} />);
    expect(screen.getByLabelText("Stop")).toBeTruthy();
  });
});
