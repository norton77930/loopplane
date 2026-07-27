import { useEffect, useRef, useState } from "react";

import type { ApiClient } from "../api/client";
import { PaperclipIcon, XIcon } from "./icons/Icons";

// File attachments for the composer (028, FR-005): upload one or more files (picker/drop) with a
// per-file status (uploading -> done/error); completed opaque references are reported to the
// parent and sent through the structured uploads field.
export interface Attachment {
  name: string;
  reference?: string;
  mediaType?: string;
  status: "uploading" | "done" | "error";
}

interface Props {
  client: ApiClient;
  value?: Attachment[];
  onChange: (items: Attachment[]) => void;
}

export function Attachments({ client, value, onChange }: Props) {
  const [items, setItems] = useState<Attachment[]>(value ?? []);
  const itemsRef = useRef<Attachment[]>(value ?? []);

  useEffect(() => {
    if (value) {
      itemsRef.current = value;
      setItems(value);
    }
  }, [value]);

  function commit(next: Attachment[]) {
    itemsRef.current = next;
    setItems(next);
    onChange(next);
  }

  async function add(fileList: FileList | null) {
    if (!fileList) return;
    for (const file of Array.from(fileList)) {
      const pending: Attachment = {
        name: file.name,
        mediaType: file.type,
        status: "uploading",
      };
      commit([...itemsRef.current, pending]);
      try {
        const result = await client.uploadFile(file);
        if (!itemsRef.current.includes(pending)) continue;
        commit(itemsRef.current.map((item) =>
          item === pending
            ? {
                name: result.name,
                reference: result.reference,
                mediaType: pending.mediaType,
                status: "done" as const,
              }
            : item,
        ));
      } catch {
        if (!itemsRef.current.includes(pending)) continue;
        commit(itemsRef.current.map((item) =>
          item === pending ? { ...item, status: "error" as const } : item,
        ));
      }
    }
  }

  return (
    <div className="attachments">
      <label className="attach-button">
        <PaperclipIcon />
        <span>Attach</span>
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
              <button
                type="button"
                className="attachment-remove"
                aria-label={`Remove ${item.name}`}
                onClick={() => commit(items.filter((_, itemIndex) => itemIndex !== index))}
              >
                <XIcon />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
