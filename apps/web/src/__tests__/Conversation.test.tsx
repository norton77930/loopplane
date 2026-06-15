import { render, screen } from "@testing-library/react";

import { Conversation } from "../components/Conversation";

describe("Conversation", () => {
  it("renders user and assistant turns", () => {
    render(
      <Conversation
        turns={[
          { role: "user", text: "hello" },
          { role: "assistant", text: "hi there" },
        ]}
      />,
    );
    expect(screen.getByText("hello")).toBeInTheDocument();
    expect(screen.getByText("hi there")).toBeInTheDocument();
  });
});
