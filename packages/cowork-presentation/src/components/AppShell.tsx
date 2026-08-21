import { useEffect, useRef, useState, type ReactNode, type RefObject } from "react";

import { useTranslation } from "../i18n/i18n";

const INSPECTION_OVERLAY_QUERY = "(max-width: 1199px)";
const FOCUSABLE =
  'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';
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

function useFocusTrap<T extends HTMLElement>(
  onDismiss: () => void,
  enabled: boolean,
  restoreFocusOnCleanup = true,
) {
  const ref = useRef<T>(null);
  const dismissRef = useRef(onDismiss);

  useEffect(() => {
    dismissRef.current = onDismiss;
  }, [onDismiss]);

  useEffect(() => {
    if (!enabled) return;
    const previous = document.activeElement as HTMLElement | null;
    const node = ref.current;
    const items = () =>
      node ? Array.from(node.querySelectorAll<HTMLElement>(FOCUSABLE)) : [];
    (items()[0] ?? node)?.focus();

    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.preventDefault();
        dismissRef.current();
        return;
      }
      if (event.key !== "Tab") return;
      const focusable = items();
      if (focusable.length === 0) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }

    node?.addEventListener("keydown", onKeyDown);
    return () => {
      node?.removeEventListener("keydown", onKeyDown);
      if (restoreFocusOnCleanup) previous?.focus?.();
    };
  }, [enabled, restoreFocusOnCleanup]);

  return ref;
}

export interface AppShellProps {
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

/** Transport-neutral shell: hosts application-supplied controls and presentation state only. */
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
}: AppShellProps) {
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
    if (previousPanelOpen.current && !panelOpen) panelReturnFocusRef?.current?.focus();
    previousPanelOpen.current = panelOpen;
  }, [panelOpen, panelReturnFocusRef]);

  return (
    <div
      className={panel ? "shell shell-with-panel" : "shell"}
      data-sidebar-collapsed={sidebarCollapsed}
      data-mobile-sidebar-open={mobileSidebarOpen}
      data-panel-open={panelOpen}
    >
      {mobileSidebarOpen ? (
        <button
          type="button"
          className="sidebar-backdrop"
          aria-label={t("navigation.close")}
          onClick={onDismissSidebar}
        />
      ) : null}
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
        <div className="composer-slot" hidden={composerHidden}>{composer}</div>
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
              ×
            </button>
          ) : null}
          {panel}
        </div>
      ) : null}
    </div>
  );
}
