import L from "leaflet";
import "leaflet/dist/leaflet.css";

const ARC = "https://server.arcgisonline.com/ArcGIS/rest/services";

export type BasemapId = "streets" | "satellite" | "dark";

/** Keyless Esri basemaps. "theme" tells data layers which colours read well on top. */
export const BASEMAPS: Record<BasemapId, { label: string; theme: "light" | "dark"; base: string; labels?: string; attribution: string }> = {
  streets: {
    label: "Streets",
    theme: "light",
    base: `${ARC}/World_Street_Map/MapServer/tile/{z}/{y}/{x}`,
    attribution: "Tiles &copy; Esri &mdash; Esri, HERE, Garmin, USGS, &copy; OpenStreetMap contributors",
  },
  satellite: {
    label: "Satellite",
    theme: "dark",
    base: `${ARC}/World_Imagery/MapServer/tile/{z}/{y}/{x}`,
    labels: `${ARC}/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}`,
    attribution: "Tiles &copy; Esri &mdash; Esri, Maxar, Earthstar Geographics",
  },
  dark: {
    label: "Dark",
    theme: "dark",
    base: `${ARC}/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}`,
    labels: `${ARC}/Canvas/World_Dark_Gray_Reference/MapServer/tile/{z}/{y}/{x}`,
    attribution: "Tiles &copy; Esri &mdash; Esri, HERE, Garmin, &copy; OpenStreetMap contributors",
  },
};

const activeTiles = new WeakMap<L.Map, L.TileLayer[]>();

/** Swaps the basemap tiles (data layers are untouched) and exposes its theme on <html>. */
export function setBasemap(map: L.Map, id: BasemapId) {
  for (const t of activeTiles.get(map) ?? []) t.remove();
  const def = BASEMAPS[id];
  const tiles = [L.tileLayer(def.base, { attribution: def.attribution, maxZoom: 19, maxNativeZoom: 18 }).addTo(map)];
  // Satellite/dark keep labels in a pane above the smoke so place names stay readable;
  // the street map has labels baked into its tiles.
  if (def.labels) tiles.push(L.tileLayer(def.labels, { pane: "labels", maxZoom: 19, maxNativeZoom: 18 }).addTo(map));
  activeTiles.set(map, tiles);
  document.documentElement.dataset.basemap = def.theme;
}

/**
 * Creates the single, persistent map used by every view. Tiles are added with setBasemap().
 */
export function createBaseMap(container: HTMLElement): L.Map {
  const map = L.map(container, {
    center: [22.8, 79.5], // all of India
    zoom: 5,
    minZoom: 4,
    maxZoom: 18,
    zoomControl: false,
    attributionControl: false,
    // Whole zoom levels keep raster tiles and labels pixel-crisp (fractional zoom shows tile seams)
    zoomSnap: 1,
    zoomDelta: 1,
    preferCanvas: true,
  });

  L.control.attribution({ position: "bottomright", prefix: false }).addTo(map);

  map.createPane("labels");
  const labels = map.getPane("labels")!;
  labels.style.zIndex = "640";
  labels.style.pointerEvents = "none";

  // Smoke polygons sit below labels; points (fires, schools) above them.
  map.createPane("smoke").style.zIndex = "420";
  map.createPane("points").style.zIndex = "660";
  // Schools above fire markers: they sit next to the fires and must never be hidden by them.
  map.createPane("schools").style.zIndex = "670";

  return map;
}

/** Popup / tooltip content built with DOM text nodes, never HTML strings (names come from OSM). */
export function popupContent(title: string, rows: Array<[string, string]>): HTMLElement {
  const root = document.createElement("div");
  const h = document.createElement("div");
  h.className = "pop-title";
  h.textContent = title;
  root.append(h);
  for (const [label, value] of rows) {
    const row = document.createElement("div");
    row.className = "pop-row";
    const l = document.createElement("span");
    l.textContent = label;
    const v = document.createElement("b");
    v.textContent = value;
    row.append(l, v);
    root.append(row);
  }
  return root;
}

export function fireIcon(sizePx: number): L.DivIcon {
  const s = Math.round(sizePx);
  return L.divIcon({
    className: "fire-marker",
    html: `<i style="--s:${s}px"></i>`,
    iconSize: [s + 8, s + 8],
    iconAnchor: [(s + 8) / 2, (s + 8) / 2],
  });
}

/** Map position from the URL (?ll=lat,lng&z=zoom), if present. */
export function urlView(): { center: [number, number]; zoom: number } | null {
  const q = new URLSearchParams(window.location.search);
  const ll = q.get("ll")?.split(",").map(Number);
  const z = Number(q.get("z"));
  if (!ll || ll.length !== 2 || ll.some((v) => !Number.isFinite(v)) || !Number.isFinite(z)) return null;
  return { center: [ll[0], ll[1]], zoom: z };
}

/** True once, for the first auto-fit after load, when the URL already fixes the view. */
let urlViewPending = urlView() !== null;
export function consumeUrlView(): boolean {
  const v = urlViewPending;
  urlViewPending = false;
  return v;
}

/** fitBounds padding that keeps data clear of the floating panel / bottom sheet and the dock. */
export function fitPadding(): Pick<L.FitBoundsOptions, "paddingTopLeft" | "paddingBottomRight"> {
  const root = document.documentElement;
  if (window.innerWidth <= 760) {
    const sheet = parseFloat(getComputedStyle(root).getPropertyValue("--sheet-h")) || 200;
    return { paddingTopLeft: [24, 70], paddingBottomRight: [70, sheet + 90] };
  }
  const panel = root.classList.contains("panel-collapsed") ? 80 : 400;
  return { paddingTopLeft: [panel, 80], paddingBottomRight: [80, 110] };
}

const SATELLITES: Record<string, string> = { N: "Suomi NPP", "1": "NOAA-20", "2": "NOAA-21" };
const CONFIDENCE: Record<string, string> = { l: "low", n: "nominal", h: "high" };
export const satelliteName = (code: string) => SATELLITES[code] ?? code;
export const confidenceName = (code: string | null | undefined, pct: number) =>
  (code && CONFIDENCE[code.toLowerCase()]) || `${Math.round(pct)}%`;

/** OSM has many unnamed schools; show a clean label and keep the id for the tooltip. */
export function schoolLabel(name: string): { label: string; detail?: string } {
  const m = /^Unnamed school \(OSM (\w+)\/(\d+)\)$/.exec(name);
  return m ? { label: "Unnamed school", detail: `OSM ${m[1]} ${m[2]}` } : { label: name };
}
