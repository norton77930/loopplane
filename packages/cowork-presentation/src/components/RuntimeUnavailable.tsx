/**
 * Visible public-safe runtime diagnostic surface (078 T089).
 *
 * The packaged smoke locates this group by a fixed accessible name and fails if
 * it resolves to anything other than exactly one element, so it is present in
 * both states and never unmounted or hidden. What it may not be is empty
 * furniture: a line that reads "No runtime diagnostic." whenever nothing is
 * wrong occupies the most prominent row under the header and says nothing. The
 * host therefore passes the session's context in the healthy state and the
 * diagnostic in the failing one — the same strip, always carrying something.
 */

export type RuntimeUnavailableProps = {
  active?: boolean;
  /** Widened from `string` so a host can pass a structured context strip. */
  children: import("react").ReactNode;
};

export function RuntimeUnavailable({
  active = true,
  children,
}: RuntimeUnavailableProps) {
  return (
    <div
      className="runtime-unavailable"
      role="group"
      aria-label="LoopPlane smoke runtime diagnostic"
      aria-live={active ? "polite" : "off"}
      // Styling hook only. The group stays present and named in both states so
      // the fixed accessibility locator keeps resolving.
      data-active={active ? "true" : "false"}
    >
      <span role={active ? "alert" : undefined}>{children}</span>
    </div>
  );
}
