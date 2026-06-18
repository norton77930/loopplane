import { useState } from "react";

import type { ApiClient } from "../api/client";

// File attachments for the composer (028, FR-005): upload one or more files (picker/drop) with a
// per-file status (uploading -> done/error); the references are reported to the parent, which
// appends them to the prompt so the agent can read them via the read_upload tool.
export interface Attachment {
  name: string;
  reference?: string;
  status: "uploading" | "done" | "error";
}

interface Props {
  client: ApiClient;
  onChange: (items: Attachment[]) => void;
}

export function Attachments({ client, onChange }: Props) {
  const [items, setItems] = useState<Attachment[]>([]);

  function commit(next: Attachment[]) {
    setItems(next);
    onChange(next);
  }

  async function add(fileList: FileList | null) {
    if (!fileList) return;
    let current = items;
    for (const file of Array.from(fileList)) {
      const pending: Attachment = { name: file.name, status: "uploading" };
      current = [...current, pending];
      commit(current);
      try {
        const result = await client.uploadFile(file);
        current = current.map((item) =>
          item === pending
            ? { name: result.name, reference: result.reference, status: "done" as const }
            : item,
        );
      } catch {
        current = current.map((item) =>
          item === pending ? { ...item, status: "error" as const } : item,
        );
      }
      commit(current);
    }
  }

  return (
    <div className="attachments">
      <label className="attach-button">
        Attach
        <input
          type="file"
          multiple
          aria-label="attach files"
          style={{ display: "none" }}
          onChange={(event) => void add(event.target.files)}
        />
      </label>
      {items.length > 0 && (
        <ul className="attachment-list">
          {items.map((item, index) => (
            <li key={index} className={`attachment attachment-${item.status}`}>
              <span className="attachment-name">{item.name}</span>
              <span className="attach-status">{item.status}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
