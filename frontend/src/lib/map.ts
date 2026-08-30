export const BASEMAPS = {
  'esri-imagery': {
    tiles: ['https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}'],
    attribution: 'Imagery © Esri, Maxar',
    maxzoom: 19
  },
  'esri-ocean': {
    tiles: ['https://server.arcgisonline.com/ArcGIS/rest/services/Ocean/World_Ocean_Base/MapServer/tile/{z}/{y}/{x}'],
    attribution: 'Ocean © Esri, GEBCO',
    maxzoom: 13
  },
  'carto-light': {
    tiles: ['https://a.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png'],
    attribution: '© OSM © CARTO',
    maxzoom: 19
  },
  'osm': {
    tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],
    attribution: '© OSM contributors',
    maxzoom: 19
  },
} as const;

export function styleFor(name: keyof typeof BASEMAPS) {
  const b = BASEMAPS[name];
  return {
    version: 8 as const,
    sources: {
      base: { type: 'raster' as const, tiles: [...b.tiles], tileSize: 256, attribution: b.attribution, maxzoom: b.maxzoom }
    },
    layers: [
      { id: 'bg', type: 'background' as const, paint: { 'background-color': '#f8fafc' } },
      { id: 'base', type: 'raster' as const, source: 'base', paint: { 'raster-opacity': 0.96 } }
    ]
  };
}

export function bboxFromCorners(bounds: [[number, number], [number, number]]) {
  const [[s, w], [n, e]] = bounds;
  return [[w, n], [e, n], [e, s], [w, s]];
}

export function ringPoly(ring: [number, number][]) {
  const r = ring.slice();
  if (r.length && (r[0][0] !== r[r.length - 1][0] || r[0][1] !== r[r.length - 1][1])) r.push(r[0]);
  return { type: 'Feature' as const, geometry: { type: 'Polygon' as const, coordinates: [r] }, properties: {} };
}

export function emptyFC() {
  return { type: 'FeatureCollection' as const, features: [] as any[] };
}

export function circleGeoJSON(t: { lat: number; lon: number; radius_km: number; priority: string; action: string; target: string }) {
  const n = 48, out: [number, number][] = [];
  const R = 6371;
  const lat = t.lat * Math.PI / 180, lon = t.lon * Math.PI / 180;
  for (let i = 0; i <= n; i++) {
    const th = 2 * Math.PI * i / n, rad = t.radius_km / R;
    const la = Math.asin(Math.sin(lat) * Math.cos(rad) + Math.cos(lat) * Math.sin(rad) * Math.cos(th));
    const lo = lon + Math.atan2(Math.sin(th) * Math.sin(rad) * Math.cos(lat), Math.cos(rad) - Math.sin(lat) * Math.sin(la));
    out.push([lo * 180 / Math.PI, la * 180 / Math.PI]);
  }
  return {
    type: 'Feature' as const,
    properties: { priority: t.priority, name: t.action + ': ' + t.target },
    geometry: { type: 'Polygon' as const, coordinates: [out] }
  };
}
