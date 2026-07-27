import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";

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
        {
          name: "notes.txt",
          reference: "ref1",
          mediaType: "text/plain",
          status: "done",
        },
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

  it("clears consumed attachments when the parent value is reset", async () => {
    const uploadFile = vi.fn().mockResolvedValue({ reference: "ref1", name: "notes.txt" });
    const client = { uploadFile } as unknown as ApiClient;
    const { rerender } = render(
      <Attachments client={client} value={[]} onChange={() => undefined} />,
    );
    const file = new File(["hi"], "notes.txt", { type: "text/plain" });

    fireEvent.change(screen.getByLabelText("attach files"), { target: { files: [file] } });
    expect(await screen.findByText("notes.txt")).toBeInTheDocument();

    rerender(<Attachments client={client} value={[]} onChange={() => undefined} />);
    await waitFor(() => expect(screen.queryByText("notes.txt")).not.toBeInTheDocument());
  });

  it("does not revive an upload that resolves after the parent cleared it", async () => {
    let resolveUpload!: (result: { reference: string; name: string }) => void;
    const uploadFile = vi.fn().mockReturnValue(
      new Promise<{ reference: string; name: string }>((resolve) => {
        resolveUpload = resolve;
      }),
    );
    const client = { uploadFile } as unknown as ApiClient;
    const { rerender } = render(
      <Attachments client={client} value={[]} onChange={() => undefined} />,
    );
    const file = new File(["hi"], "slow.txt", { type: "text/plain" });

    fireEvent.change(screen.getByLabelText("attach files"), { target: { files: [file] } });
    expect(await screen.findByText("slow.txt")).toBeInTheDocument();
    rerender(<Attachments client={client} value={[]} onChange={() => undefined} />);
    await waitFor(() => expect(screen.queryByText("slow.txt")).not.toBeInTheDocument());

    await act(async () => {
      resolveUpload({ reference: "slow-ref", name: "slow.txt" });
      await Promise.resolve();
    });
    expect(screen.queryByText("slow.txt")).not.toBeInTheDocument();
  });

  it("does not resurrect a cleared first file when a second selected file starts", async () => {
    let resolveFirst!: (result: { reference: string; name: string }) => void;
    const uploadFile = vi
      .fn()
      .mockReturnValueOnce(
        new Promise<{ reference: string; name: string }>((resolve) => {
          resolveFirst = resolve;
        }),
      )
      .mockResolvedValueOnce({ reference: "second-ref", name: "second.txt" });
    const client = { uploadFile } as unknown as ApiClient;
    const { rerender } = render(
      <Attachments client={client} value={[]} onChange={() => undefined} />,
    );

    fireEvent.change(screen.getByLabelText("attach files"), {
      target: {
        files: [new File(["1"], "first.txt"), new File(["2"], "second.txt")],
      },
    });
    expect(await screen.findByText("first.txt")).toBeInTheDocument();
    rerender(<Attachments client={client} value={[]} onChange={() => undefined} />);

    await act(async () => {
      resolveFirst({ reference: "first-ref", name: "first.txt" });
      await Promise.resolve();
    });
    expect(await screen.findByText("second.txt")).toBeInTheDocument();
    expect(screen.queryByText("first.txt")).not.toBeInTheDocument();
  });
});
