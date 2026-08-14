/** Visible public-safe runtime diagnostic surface (078 T089). */

export type RuntimeUnavailableProps = {
  active?: boolean;
  children: string;
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
