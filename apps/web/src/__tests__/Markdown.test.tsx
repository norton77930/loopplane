import { render } from "@testing-library/react";

import { Markdown } from "../components/Markdown";

describe("Markdown", () => {
  it("renders headings, lists, links, and gfm tables", () => {
    const { container } = render(
      <Markdown>
        {"# Title\n\n- one\n- two\n\n[link](https://example.com)\n\n| a | b |\n|---|---|\n| 1 | 2 |"}
      </Markdown>,
    );
    expect(container.querySelector("h1")?.textContent).toBe("Title");
    expect(container.querySelectorAll("li")).toHaveLength(2);
    expect(container.querySelector("a")?.getAttribute("href")).toBe("https://example.com");
    expect(container.querySelector("table")).not.toBeNull();
  });

  it("renders fenced code blocks", () => {
    const { container } = render(<Markdown>{"```\ncode here\n```"}</Markdown>);
    expect(container.querySelector("pre code")?.textContent).toContain("code here");
  });

  it("does not inject raw HTML from model output", () => {
    const { container } = render(<Markdown>{"<script>alert(1)</script> hi"}</Markdown>);
    expect(container.querySelector("script")).toBeNull();
    expect(container.textContent).toContain("alert(1)");
  });

  it("highlights a fenced code block with a known language", () => {
    const { container } = render(<Markdown>{"```js\nconst x = 1;\n```"}</Markdown>);
    expect(container.querySelector("code.hljs")).not.toBeNull();
  });

  it("renders an unknown-language code block without error", () => {
    const { container } = render(<Markdown>{"```nosuchlang\nzzz\n```"}</Markdown>);
    expect(container.querySelector("pre code")?.textContent).toContain("zzz");
  });
});
