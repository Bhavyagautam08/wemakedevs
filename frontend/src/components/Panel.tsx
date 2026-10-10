import { ReactNode, useEffect, useRef, useState } from "react";
import { PanelLeftClose, PanelLeftOpen } from "lucide-react";

interface PanelProps {
  label: string;
  /** Always-visible header (title, primary action, KPIs). */
  head: ReactNode;
  children: ReactNode;
}

/**
 * Floating side panel on desktop (collapsible to the left edge) and a bottom sheet on
 * mobile (collapsed shows only the header). Publishes its height as --sheet-h so the
 * timeline dock can sit above the sheet on small screens.
 */
export function Panel({ label, head, children }: PanelProps) {
  // Phones open map-first: the sheet starts collapsed to its header
  const [collapsed, setCollapsed] = useState(() => window.matchMedia("(max-width: 760px)").matches);
  const ref = useRef<HTMLElement | null>(null);

  useEffect(() => {
    document.documentElement.classList.toggle("panel-collapsed", collapsed);
    return () => document.documentElement.classList.remove("panel-collapsed");
  }, [collapsed]);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const ro = new ResizeObserver(() => {
      document.documentElement.style.setProperty("--sheet-h", `${el.getBoundingClientRect().height}px`);
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  return (
    <>
      <aside ref={ref} className={`surface panel${collapsed ? " collapsed" : ""}`} aria-label={label}>
        <button
          className="sheet-handle"
          aria-label={collapsed ? "Expand panel" : "Collapse panel"}
          aria-expanded={!collapsed}
          onClick={() => setCollapsed((c) => !c)}
        />
        <div className="panel-head">
          {head}
        </div>
        <div className="panel-body">{children}</div>
        <button
          className="icon-btn sm collapse-btn"
          style={{ position: "absolute", top: 12, right: 10 }}
          aria-label="Hide panel"
          title="Hide panel"
          onClick={() => setCollapsed(true)}
        >
          <PanelLeftClose size={16} />
        </button>
      </aside>
      {collapsed && (
        <button
          className="surface icon-btn panel-reopen"
          style={{ width: 44, height: 44 }}
          aria-label="Show panel"
          title="Show panel"
          onClick={() => setCollapsed(false)}
        >
          <PanelLeftOpen size={18} />
        </button>
      )}
    </>
  );
}
