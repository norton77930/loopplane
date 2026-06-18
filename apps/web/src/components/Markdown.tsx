import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

// Render assistant output as markdown (FR-001). react-markdown renders to React nodes and,
// with no rehype-raw plugin, raw HTML in model output is inert text (no injection) — the
// FR-001 edge case is satisfied without a separate sanitizer (research R1).
export function Markdown({ children }: { children: string }) {
  return (
    <div className="markdown">
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{children}</ReactMarkdown>
    </div>
  );
}
