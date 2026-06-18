import ReactMarkdown from "react-markdown";
import rehypeHighlight from "rehype-highlight";
import remarkGfm from "remark-gfm";

// Render assistant output as markdown (FR-001, unit 025) with language-aware code highlighting
// (unit 029, rehype-highlight). react-markdown renders to React nodes and, with no rehype-raw
// plugin, raw HTML in model output is inert text (no injection); rehype-highlight adds `hljs`
// classes to fenced code and falls back to plain text for an unknown language.
export function Markdown({ children }: { children: string }) {
  return (
    <div className="markdown">
      <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeHighlight]}>
        {children}
      </ReactMarkdown>
    </div>
  );
}
