// A shimmer placeholder shown while a region's data loads (unit 032, FR-006).
export function Skeleton({ rows = 3 }: { rows?: number }) {
  return (
    <div className="skeleton" data-testid="skeleton" aria-hidden="true">
      {Array.from({ length: rows }, (_, index) => (
        <div key={index} className="skeleton-row" />
      ))}
    </div>
  );
}
