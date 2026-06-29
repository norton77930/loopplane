import { fireEvent, render, screen } from "@testing-library/react";

import { MessageList } from "../components/MessageList";

describe("MessageList fork action", () => {
  it("offers a fork action for a message and reports its sequence", () => {
    const onFork = vi.fn();

    render(
      <MessageList
        entries={[
          { kind: "user", text: "start" },
          { kind: "assistant", text: "answer" },
        ]}
        onFork={onFork}
      />,
    );

    fireEvent.click(screen.getAllByText("Fork")[1]);

    expect(onFork).toHaveBeenCalledWith(2);
  });
});
