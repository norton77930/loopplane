import type { ReactNode } from "react";

// The two-pane shell (FR-007, unit 025) + an optional right-side inspection panel (unit 027):
// a sessions sidebar, a chat column with a sticky header and a sticky composer, and (when open)
// the inspection panel. The scrolling message region is supplied as `children`.
interface Props {
  sidebar: ReactNode;
  header: ReactNode;
  banner?: ReactNode;
  composer: ReactNode;
  panel?: ReactNode;
  children: ReactNode;
}

export function AppShell({ sidebar, header, banner, composer, panel, children }: Props) {
  return (
    <div className={panel ? "shell shell-with-panel" : "shell"}>
      <aside className="sidebar">{sidebar}</aside>
      <section className="chat-column">
        {header}
        {banner}
        {children}
        {composer}
      </section>
      {panel}
    </div>
  );
}
