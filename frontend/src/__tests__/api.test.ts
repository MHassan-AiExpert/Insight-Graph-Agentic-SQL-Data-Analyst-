import { afterEach, describe, expect, it, vi } from "vitest";
import { askStream, type AgentStep, type AskResult } from "../api";

function sseResponse(chunks: string[]): Response {
  const encoder = new TextEncoder();
  const body = new ReadableStream<Uint8Array>({
    start(controller) {
      chunks.forEach((c) => controller.enqueue(encoder.encode(c)));
      controller.close();
    },
  });
  return new Response(body, { status: 200, headers: { "Content-Type": "text/event-stream" } });
}

afterEach(() => vi.unstubAllGlobals());

describe("askStream", () => {
  it("parses start, step and result events, even when split across chunks", async () => {
    const stream = [
      'event: start\r\ndata: {"thread_id": "t1", "question": "q"}\r\n\r\n',
      'event: step\r\ndata: {"node": "classify_intent", "title": "Understood", ',
      '"detail": "", "status": "done", "data": {}, "t_ms": 3}\r\n\r\n',
      'event: result\r\ndata: {"thread_id": "t1", "status": "answered", "row_count": 5}\r\n\r\n',
    ];
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(sseResponse(stream)));
    const steps: AgentStep[] = [];
    let result: AskResult | null = null;
    let thread = "";
    await askStream("q", null, {
      onStart: (t) => (thread = t),
      onStep: (s) => steps.push(s),
      onResult: (r) => (result = r),
      onError: () => {
        throw new Error("unexpected error event");
      },
    });
    expect(thread).toBe("t1");
    expect(steps.map((s) => s.node)).toEqual(["classify_intent"]);
    expect(result!.row_count).toBe(5);
  });

  it("forwards server error events", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(sseResponse(['event: error\ndata: {"message": "boom"}\n\n'])));
    const onError = vi.fn();
    await askStream("q", null, { onStep: vi.fn(), onResult: vi.fn(), onError });
    expect(onError).toHaveBeenCalledWith("boom");
  });

  it("reports when the API is unreachable", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("failed")));
    const onError = vi.fn();
    await askStream("q", null, { onStep: vi.fn(), onResult: vi.fn(), onError });
    expect(onError.mock.calls[0][0]).toMatch(/Can't reach the InsightGraph API/);
  });

  it("reports HTTP errors", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("bad", { status: 422 })));
    const onError = vi.fn();
    await askStream("q", null, { onStep: vi.fn(), onResult: vi.fn(), onError });
    expect(onError.mock.calls[0][0]).toMatch(/422/);
  });
});
