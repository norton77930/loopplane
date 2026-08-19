// Moved from apps/web in 083 Wave 3; apps/web re-exports it unchanged.
export function EmptySection({ message }: { message: string }) {
  return <div className="capability-empty">{message}</div>;
}
