import { useEffect, useRef, useState, type ReactNode, type RefObject } from "react";

import { useFocusTrap } from "../hooks/useFocusTrap";
import { useTranslation } from "../i18n/i18n";
import { XIcon } from "./icons/Icons";

const INSPECTION_OVERLAY_QUERY = "(max-width: 1199px)";
const noop = () => undefined;

function useMediaQuery(query: string) {
  const [matches, setMatches] = useState(() =>
    typeof window.matchMedia === "function" && window.matchMedia(query).matches,
  );

  useEffect(() => {
    if (typeof window.matchMedia !== "function") return;
    const media = window.matchMedia(query);
    const update = () => setMatches(media.matches);
    update();
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, [query]);

  return matches;
}

// The two-pane shell (FR-007, unit 025) + an optional right-side inspection panel (unit 027):
// a sessions sidebar, a chat column with a sticky header and a sticky composer, and (when open)
// the inspection panel. The scrolling message region is supplied as `children`.
interface Props {
  sidebar: ReactNode;
  header: ReactNode;
  banner?: ReactNode;
  composer: ReactNode;
  panel?: ReactNode;
  sidebarCollapsed?: boolean;
  mobileSidebarOpen?: boolean;
  onDismissSidebar?: () => void;
  onDismissPanel?: () => void;
  panelReturnFocusRef?: RefObject<HTMLElement>;
  composerHidden?: boolean;
  children: ReactNode;
}

export function AppShell({
  sidebar,
  header,
  banner,
  composer,
  panel,
  sidebarCollapsed = false,
  mobileSidebarOpen = false,
  onDismissSidebar,
  onDismissPanel,
  panelReturnFocusRef,
  composerHidden = false,
  children,
}: Props) {
  const { t } = useTranslation();
  const inspectionOverlay = useMediaQuery(INSPECTION_OVERLAY_QUERY);
  const panelOpen = Boolean(panel);
  const previousPanelOpen = useRef(panelOpen);
  const sidebarRef = useFocusTrap<HTMLElement>(
    onDismissSidebar ?? noop,
    mobileSidebarOpen,
  );
  const panelRef = useFocusTrap<HTMLDivElement>(
    onDismissPanel ?? noop,
    Boolean(panelOpen && onDismissPanel && inspectionOverlay),
    !panelReturnFocusRef,
  );

  useEffect(() => {
    if (previousPanelOpen.current && !panelOpen) {
      panelReturnFocusRef?.current?.focus();
    }
    previousPanelOpen.current = panelOpen;
  }, [panelOpen, panelReturnFocusRef]);

  return (
    <div
      className={panel ? "shell shell-with-panel" : "shell"}
      data-sidebar-collapsed={sidebarCollapsed}
      data-mobile-sidebar-open={mobileSidebarOpen}
      data-panel-open={panelOpen}
    >
      {mobileSidebarOpen && (
        <button
          type="button"
          className="sidebar-backdrop"
          aria-label={t("navigation.close")}
          onClick={onDismissSidebar}
        />
      )}
      <aside
        id="session-navigation"
        className="sidebar"
        aria-label={t("navigation.label")}
        aria-modal={mobileSidebarOpen ? "true" : undefined}
        role={mobileSidebarOpen ? "dialog" : undefined}
        tabIndex={mobileSidebarOpen ? -1 : undefined}
        ref={sidebarRef}
      >
        {sidebar}
      </aside>
      <section className="chat-column">
        {header}
        {banner}
        <div className="chat-content">{children}</div>
        <div className="composer-slot" hidden={composerHidden}>
          {composer}
        </div>
      </section>
      {panel && onDismissPanel ? (
        <button
          type="button"
          className="panel-backdrop"
          aria-label={t("inspection.dismiss")}
          onClick={onDismissPanel}
        />
      ) : null}
      {panel ? (
        <div
          className="shell-panel"
          aria-label={inspectionOverlay ? t("inspection.panel") : undefined}
          aria-modal={inspectionOverlay ? "true" : undefined}
          role={inspectionOverlay ? "dialog" : undefined}
          tabIndex={inspectionOverlay ? -1 : undefined}
          ref={panelRef}
        >
          {onDismissPanel ? (
            <button
              type="button"
              className="panel-close"
              aria-label={t("inspection.close")}
              onClick={onDismissPanel}
            >
              <XIcon />
            </button>
          ) : null}
          {panel}
        </div>
      ) : null}
    </div>
  );
}
