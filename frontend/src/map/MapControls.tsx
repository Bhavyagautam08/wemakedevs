import { ReactNode, useEffect, useRef, useState } from "react";
import type L from "leaflet";
import { Layers, Minus, Plus, Scan } from "lucide-react";
import { BasemapId, BASEMAPS } from "./baseMap";

interface MapControlsProps {
  map: L.Map | null;
  onFit?: () => void;
  fitLabel?: string;
  /** Extra content of the layers popover (data layers). */
  layers?: ReactNode;
  basemap: BasemapId;
  onBasemap: (id: BasemapId) => void;
}

/** Floating zoom / fit / layers controls (top right). */
export function MapControls({ map, onFit, fitLabel = "Fit to data", layers, basemap, onBasemap }: MapControlsProps) {
  const [open, setOpen] = useState(false);
  const anchor = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (anchor.current && !anchor.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", onDoc);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDoc);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  return (
    <div className="map-controls">
      <div className="surface control-group" role="group" aria-label="Map navigation">
        <button className="icon-btn" aria-label="Zoom in" title="Zoom in" onClick={() => map?.zoomIn()} disabled={!map}>
          <Plus size={18} />
        </button>
        <div className="divider" />
        <button className="icon-btn" aria-label="Zoom out" title="Zoom out" onClick={() => map?.zoomOut()} disabled={!map}>
          <Minus size={18} />
        </button>
      </div>
      <div className="surface control-group">
        {onFit && (
          <button className="icon-btn" aria-label={fitLabel} title={fitLabel} onClick={onFit} disabled={!map}>
            <Scan size={18} />
          </button>
        )}
        {(
          <>
            {onFit && <div className="divider" />}
            <div className="layers-anchor" ref={anchor}>
              <button
                className="icon-btn"
                aria-label="Map layers"
                title="Map layers"
                aria-expanded={open}
                aria-haspopup="dialog"
                onClick={() => setOpen((o) => !o)}
              >
                <Layers size={18} />
              </button>
              {open && (
                <div className="surface popover" role="dialog" aria-label="Map layers">
                  <div className="group">
                    <h3>Map style</h3>
                    <div className="segmented full" role="group" aria-label="Map style">
                      {(Object.keys(BASEMAPS) as BasemapId[]).map((id) => (
                        <button key={id} aria-pressed={basemap === id} onClick={() => onBasemap(id)}>
                          {BASEMAPS[id].label}
                        </button>
                      ))}
                    </div>
                  </div>
                  {layers}
                </div>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}

interface SwitchRowProps {
  label: string;
  checked: boolean;
  onChange: (v: boolean) => void;
  swatch?: ReactNode;
}

export function SwitchRow({ label, checked, onChange, swatch }: SwitchRowProps) {
  return (
    <label className="switch-row">
      <span className="label">
        {swatch}
        {label}
      </span>
      <span className="switch">
        <input type="checkbox" role="switch" checked={checked} onChange={(e) => onChange(e.target.checked)} />
        <span />
      </span>
    </label>
  );
}
