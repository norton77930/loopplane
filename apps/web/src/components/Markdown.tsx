import { useRef, type ComponentPropsWithoutRef } from "react";
import ReactMarkdown from "react-markdown";
import rehypeHighlight from "rehype-highlight";
import remarkGfm from "remark-gfm";

import { copyText } from "../lib/clipboard";

// Render assistant output as markdown (FR-001, unit 025) with language-aware code highlighting
// (unit 029, rehype-highlight) and a per-code-block copy button (unit 031). react-markdown
// renders to React nodes and, with no rehype-raw plugin, raw HTML in model output is inert text
// (no injection). The `pre` override wraps each fenced block with a copy button that copies the
// block's exact text (the button sits outside the <pre>, so it is excluded from the copied text).
function CodeBlock({ children, ...props }: ComponentPropsWithoutRef<"pre">) {
  const ref = useRef<HTMLPreElement>(null);
  return (
    <div className="code-block">
      <button
        type="button"
        className="code-copy"
        aria-label="Copy code"
        onClick={() => void copyText(ref.current?.textContent ?? "")}
      >
        Copy
      </button>
      <pre {...props} ref={ref}>
        {children}
      </pre>
    </div>
  );
}

export function Markdown({ children }: { children: string }) {
  return (
    <div className="markdown">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeHighlight]}
        components={{ pre: CodeBlock }}
      >
        {children}
      </ReactMarkdown>
    </div>
  );
}
