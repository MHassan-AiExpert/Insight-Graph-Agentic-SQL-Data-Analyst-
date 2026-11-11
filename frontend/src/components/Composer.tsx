import { useEffect, useRef, useState } from "react";
import { ArrowUp, Square } from "lucide-react";

interface Props {
  busy: boolean;
  onSubmit: (question: string) => void;
  onStop: () => void;
}

export function Composer({ busy, onSubmit, onStop }: Props) {
  const [value, setValue] = useState("");
  const ref = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
  }, [value]);

  const submit = () => {
    const q = value.trim();
    if (!q || busy) return;
    onSubmit(q);
    setValue("");
  };

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        submit();
      }}
      className="flex items-end gap-2 rounded-2xl border border-grid-strong bg-sheet p-2 pl-4 shadow-[0_8px_30px_-18px_rgba(23,32,51,0.45)] focus-within:border-cobalt"
    >
      <label htmlFor="question" className="sr-only">
        Ask a question about your data
      </label>
      <textarea
        id="question"
        ref={ref}
        rows={1}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            submit();
          }
        }}
        placeholder="Ask about revenue, customers, products or orders…"
        className="max-h-40 flex-1 resize-none bg-transparent py-2 text-[15px] text-ink outline-none placeholder:text-ink-faint focus-visible:outline-none"
      />
      {busy ? (
        <button type="button" onClick={onStop} className="grid size-10 place-items-center rounded-xl bg-ink text-paper hover:bg-ink/90" aria-label="Stop">
          <Square size={14} fill="currentColor" />
        </button>
      ) : (
        <button
          type="submit"
          disabled={!value.trim()}
          className="grid size-10 place-items-center rounded-xl bg-cobalt text-white hover:bg-cobalt/90 disabled:bg-grid-strong"
          aria-label="Ask"
        >
          <ArrowUp size={18} strokeWidth={2.4} />
        </button>
      )}
    </form>
  );
}
