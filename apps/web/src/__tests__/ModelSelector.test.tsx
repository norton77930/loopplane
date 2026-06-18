import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import type { ApiClient } from "../api/client";
import { ModelSelector } from "../components/ModelSelector";

describe("ModelSelector", () => {
  it("lists models and reports a selection", async () => {
    const client = {
      listModels: async () => [
        { id: "a", label: "Alpha" },
        { id: "b", label: "Beta" },
      ],
    } as unknown as ApiClient;
    const onChange = vi.fn();
    render(<ModelSelector client={client} value={null} onChange={onChange} />);
    const select = await screen.findByLabelText("model");
    fireEvent.change(select, { target: { value: "b" } });
    expect(onChange).toHaveBeenCalledWith("b");
  });

  it("hides when there is no catalog", async () => {
    const client = { listModels: async () => [] } as unknown as ApiClient;
    const { container } = render(
      <ModelSelector client={client} value={null} onChange={() => undefined} />,
    );
    await waitFor(() => expect(container.querySelector("select")).toBeNull());
  });
});
