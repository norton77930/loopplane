/** Maps only host-projected public status enums to stable display text. */
export function inspectionStatusLabel(status: string | undefined): string {
  switch (status) {
    case "available": return "Available";
    case "read_only": return "Read only";
    case "priced": return "Priced";
    case "unpriced": return "Unpriced";
    case "partially_unpriced": return "Partially unpriced";
    case "unavailable": return "Unavailable";
    default: return "Unknown";
  }
}
