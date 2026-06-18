import type { ReactNode } from "react";

// The two-pane shell (FR-007): a sessions sidebar and a chat column with a sticky header
// and a sticky composer. The scrolling message region is supplied as `children` (it owns
// its own scroll container so it can track auto-scroll / jump-to-latest — FR-011).
interface Props {
  sidebar: ReactNode;
  header: ReactNode;
  banner?: ReactNode;
  composer: ReactNode;
  children: ReactNode;
}

export function AppShell({ sidebar, header, banner, composer, children }: Props) {
  return (
    <div className="shell">
      <aside className="sidebar">{sidebar}</aside>
      <section className="chat-column">
        {header}
        {banner}
        {children}
        {composer}
      </section>
    </div>
  );
}
