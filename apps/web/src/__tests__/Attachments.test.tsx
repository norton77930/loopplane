import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import type { ApiClient } from "../api/client";
import { Attachments } from "../components/Attachments";

describe("Attachments", () => {
  it("uploads an attached file and reports it done", async () => {
    const uploadFile = vi.fn().mockResolvedValue({ reference: "ref1", name: "notes.txt" });
    const onChange = vi.fn();
    const client = { uploadFile } as unknown as ApiClient;
    render(<Attachments client={client} onChange={onChange} />);
    const file = new File(["hi"], "notes.txt", { type: "text/plain" });
    fireEvent.change(screen.getByLabelText("attach files"), { target: { files: [file] } });
    expect(await screen.findByText("notes.txt")).toBeInTheDocument();
    await waitFor(() =>
      expect(onChange).toHaveBeenCalledWith([
        { name: "notes.txt", reference: "ref1", status: "done" },
      ]),
    );
  });

  it("surfaces an upload error", async () => {
    const uploadFile = vi.fn().mockRejectedValue(new Error("nope"));
    const client = { uploadFile } as unknown as ApiClient;
    render(<Attachments client={client} onChange={() => undefined} />);
    const file = new File(["x"], "bad.txt");
    fireEvent.change(screen.getByLabelText("attach files"), { target: { files: [file] } });
    expect(await screen.findByText("error")).toBeInTheDocument();
  });
});
