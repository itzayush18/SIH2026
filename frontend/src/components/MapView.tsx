import { useEffect, useRef, useState } from 'react';
import maplibregl from 'maplibre-gl';
import { styleFor, bboxFromCorners, ringPoly, emptyFC, circleGeoJSON } from '../lib/map';
import type { Report } from '../lib/types';

export default function MapView({
  report,
  time,
  onTimeChange
}: {
  report: Report | null;
  time: number;
  onTimeChange?: (t: number) => void;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const [readout, setReadout] = useState('move the cursor over the map');
  const [basemap, setBasemap] = useState<keyof typeof import('../lib/map').BASEMAPS>('esri-imagery');
  const [vectorsOn, setVectorsOn] = useState(false);
  const originSlices = useRef<string[]>([]);
  const activeSlice = useRef<number>(-1);

  // init map
  useEffect(() => {
    if (!ref.current || mapRef.current) return;
    const m = new maplibregl.Map({
      container: ref.current,
      style: styleFor(basemap),
      center: [73.5, 18.5],
      zoom: 5.2,
      attributionControl: { compact: true } as any
    });
    m.addControl(new maplibregl.NavigationControl({ visualizePitch: true } as any), 'top-left');
    m.addControl(new maplibregl.ScaleControl({ maxWidth: 180, unit: 'metric' } as any), 'bottom-left');
    m.on('mousemove', e => {
      setReadout(`${e.lngLat.lat.toFixed(4)}°N  ${e.lngLat.lng.toFixed(4)}°E · z${m.getZoom().toFixed(1)} · p${m.getPitch().toFixed(0)}°`);
    });
    mapRef.current = m;
    m.once('load', async () => {
      await ensureBase(m);
      await loadJurisdictions(m);
    });
    return () => { m.remove(); mapRef.current = null; };
  }, []);

  // basemap switch
  useEffect(() => {
    const m = mapRef.current;
    if (!m) return;
    const center = m.getCenter();
    const zoom = m.getZoom();
    const pitch = m.getPitch();
    const bearing = m.getBearing();
    // @ts-ignore
    m.setStyle(styleFor(basemap));
    m.once('styledata', async () => {
      await ensureBase(m);
      await loadJurisdictions(m);
      if (report) installIncident(m, report);
      m.jumpTo({ center: [center.lng, center.lat], zoom, pitch, bearing });
      setTimeOnMap(time, report, m);
    });
  }, [basemap]);

  // when report changes
  useEffect(() => {
    const m = mapRef.current;
    if (!m || !report) return;
    const doInstall = () => installIncident(m, report);
    if (m.isStyleLoaded()) doInstall(); else m.once('load', doInstall);
  }, [report]);

  // time change
  useEffect(() => {
    const m = mapRef.current;
    if (!m || !report) return;
    setTimeOnMap(time, report, m);
    if (vectorsOn) refreshVectors(m, report, time);
  }, [time, vectorsOn]);

  const frame = () => {
    if (!report || !mapRef.current) return;
    const b = report.scene.bounds;
    mapRef.current.fitBounds([[b[0][1], b[0][0]], [b[1][1], b[1][0]]] as any, { padding: { top: 70, bottom: 130, left: 30, right: 20 }, duration: 900 } as any);
  };

  return (
    <div className="relative w-full h-full bg-slate-100">
      <div ref={ref} className="absolute inset-0" />

      <div className="absolute left-2 bottom-2 font-mono text-[11px] bg-white/90 backdrop-blur border border-slate-200 rounded-md px-2 py-1 text-slate-600">
        {readout}
      </div>

      <div className="absolute top-2 right-2 bg-white/95 backdrop-blur border border-slate-200 rounded-xl p-1.5 flex gap-1.5 shadow-soft">
        <select value={basemap} onChange={e => setBasemap(e.target.value as any)} className="bg-white border border-slate-200 rounded-md px-2 py-1.5 text-xs text-slate-700">
          <option value="esri-imagery">Esri satellite</option>
          <option value="esri-ocean">Ocean bathymetry</option>
          <option value="carto-light">Carto light</option>
          <option value="osm">OpenStreetMap</option>
        </select>
        <button onClick={() => setVectorsOn(v => !v)} className={`px-2.5 py-1.5 rounded-md text-xs border ${vectorsOn ? 'bg-brand-500 text-white border-brand-500' : 'bg-white text-slate-600 border-slate-200'}`}>Vectors</button>
        <button onClick={() => {
          const m = mapRef.current; if (!m) return;
          const on = m.getPitch() < 15;
          m.easeTo({ pitch: on ? 55 : 0, bearing: on ? -20 : 0, duration: 900 });
        }} className="px-2.5 py-1.5 rounded-md text-xs border bg-white text-slate-600 border-slate-200">3D</button>
        <button onClick={frame} className="px-2.5 py-1.5 rounded-md text-xs border bg-white text-slate-600 border-slate-200">Frame slick</button>
      </div>
    </div>
  );

  async function ensureBase(m: maplibregl.Map) {
    if (!m.getSource('coast')) {
      m.addSource('coast', { type: 'geojson', data: emptyFC() as any });
      m.addLayer({ id: 'coast-l', type: 'line', source: 'coast', paint: { 'line-color': '#94a3b8', 'line-width': 0.7, 'line-opacity': 0.35 } } as any);
    }
    if (!m.getSource('jur')) {
      m.addSource('jur', { type: 'geojson', data: emptyFC() as any });
      m.addLayer({ id: 'jur-fill', type: 'fill', source: 'jur', paint: { 'fill-color': ['match', ['get', 'kind'], 'SPECIAL_AREA', '#f59e0b', 'EEZ', '#2f7de2', '#64748b'], 'fill-opacity': 0.06 } } as any);
      m.addLayer({ id: 'jur-line', type: 'line', source: 'jur', paint: { 'line-color': ['match', ['get', 'kind'], 'SPECIAL_AREA', '#f59e0b', 'EEZ', '#2f7de2', '#64748b'], 'line-width': 1.2, 'line-dasharray': [3, 3], 'line-opacity': 0.55 } } as any);
    }
    if (!m.getSource('vec')) {
      m.addSource('vec', { type: 'geojson', data: emptyFC() as any });
      m.addLayer({ id: 'vec-current', type: 'line', source: 'vec', filter: ['==', ['get', 'kind'], 'current'], paint: { 'line-color': '#2f7de2', 'line-width': 1.5, 'line-opacity': 0.85 } } as any);
      m.addLayer({ id: 'vec-wind', type: 'line', source: 'vec', filter: ['==', ['get', 'kind'], 'wind'], paint: { 'line-color': '#f59e0b', 'line-width': 1.2, 'line-opacity': 0.7 } } as any);
      m.setLayoutProperty('vec-current', 'visibility', 'none');
      m.setLayoutProperty('vec-wind', 'visibility', 'none');
    }
    if (!m.getSource('patrol')) {
      m.addSource('patrol', { type: 'geojson', data: emptyFC() as any });
      m.addLayer({ id: 'patrol-fill', type: 'fill', source: 'patrol', paint: { 'fill-color': ['match', ['get', 'priority'], 'P1', '#dc2626', 'P2', '#ea580c', '#2f7de2'], 'fill-opacity': 0.08 } } as any);
      m.addLayer({ id: 'patrol-line', type: 'line', source: 'patrol', paint: { 'line-color': ['match', ['get', 'priority'], 'P1', '#dc2626', 'P2', '#ea580c', '#2f7de2'], 'line-width': 1.5 } } as any);
    }
  }
  async function loadJurisdictions(m: maplibregl.Map) {
    try {
      const gj = await (await fetch('/api/jurisdictions.geojson')).json();
      (m.getSource('jur') as any)?.setData(gj);
      const cg = await (await fetch('/api/coast.geojson')).json();
      (m.getSource('coast') as any)?.setData(cg);
    } catch {}
  }
  function installIncident(m: maplibregl.Map, rep: Report) {
    ['sar','slick','originAll','originSlice','slick-ring','ais','source','source-start','past','future','vessels','vessels-dark'].forEach(id=>{
      const s = m.getSource(id); if (!s) return;
      m.getStyle().layers.filter(l=> (l as any).source===id).forEach(l=> m.removeLayer(l.id));
      m.removeSource(id);
    });
    const iid = rep.oiltrace.incident_id;
    const prefix = `./incidents/${iid}/`;
    m.addSource('sar', { type: 'image', url: prefix+'sar.png', coordinates: bboxFromCorners(rep.scene.bounds) as any });
    m.addSource('slick', { type: 'image', url: prefix+'slick.png', coordinates: bboxFromCorners(rep.scene.bounds) as any });
    m.addSource('originAll', { type: 'image', url: prefix+rep.origin_pdf.png, coordinates: bboxFromCorners(rep.origin_pdf.bounds) as any });
    const slices = (rep.origin_pdf.slices||[]).map(s=> prefix+s.png);
    originSlices.current = slices; activeSlice.current = -1;
    slices.forEach(u=>{ const im=new Image(); im.src=u; });
    m.addSource('originSlice', { type: 'image', url: slices[0]||prefix+'origin.png', coordinates: bboxFromCorners(rep.origin_pdf.bounds) as any });
    m.addLayer({ id:'sar-l', type:'raster', source:'sar', paint:{'raster-opacity':0.82}} as any);
    m.addLayer({ id:'originAll-l', type:'raster', source:'originAll', paint:{'raster-opacity':0.28}} as any);
    m.addLayer({ id:'originSlice-l', type:'raster', source:'originSlice', paint:{'raster-opacity':0.62, 'raster-fade-duration':400}} as any);
    m.addLayer({ id:'slick-l', type:'raster', source:'slick', paint:{'raster-opacity':0.88}} as any);
    const ring = rep.detections[0].contour_lonlat||[];
    if (ring.length) {
      m.addSource('slick-ring', { type:'geojson', data: ringPoly(ring as any) as any });
      m.addLayer({ id:'slick-fill', type:'fill', source:'slick-ring', paint:{'fill-color':'#d95926','fill-opacity':0.08}} as any);
      m.addLayer({ id:'slick-halo', type:'line', source:'slick-ring', paint:{'line-color':'#000','line-width':7,'line-opacity':0.45,'line-blur':3}} as any);
      m.addLayer({ id:'slick-outline', type:'line', source:'slick-ring', paint:{'line-color':'#d95926','line-width':2.2}} as any);
    }
    m.addSource('ais', { type:'geojson', data:{ type:'FeatureCollection', features: rep.vessels.map(v=>({ type:'Feature', properties:{mmsi:v.mmsi,name:v.name,type:v.type}, geometry:{type:'LineString', coordinates: v.track.map(p=>[p[0],p[1]])}}))} as any});
    m.addLayer({ id:'ais-l', type:'line', source:'ais', paint:{'line-color':'#2f7de2','line-width':1.2,'line-opacity':0.25}} as any);
    const st = rep.source.track.map(p=>[p.lon,p.lat]);
    m.addSource('source', { type:'geojson', data:{ type:'Feature', properties:{}, geometry:{type:'LineString', coordinates: st}} as any});
    m.addLayer({ id:'source-halo', type:'line', source:'source', paint:{'line-color':'#000','line-width':6,'line-opacity':0.35,'line-blur':2}} as any);
    m.addLayer({ id:'source-l', type:'line', source:'source', paint:{'line-color':'#10b981','line-width':3,'line-dasharray':[2,1.5]}} as any);
    m.addSource('source-start', { type:'geojson', data:{ type:'Feature', properties:{label:`Release start`}, geometry:{type:'Point', coordinates: st[0]}} as any});
    m.addLayer({ id:'source-start-l', type:'circle', source:'source-start', paint:{'circle-radius':6,'circle-color':'#10b981','circle-stroke-width':2,'circle-stroke-color':'white'}} as any);
    m.addSource('past', { type:'geojson', data: emptyFC() as any});
    m.addSource('future', { type:'geojson', data: emptyFC() as any});
    m.addLayer({ id:'past-l', type:'circle', source:'past', paint:{'circle-radius':['interpolate',['linear'],['zoom'],7,1.4,12,2.8],'circle-color':'#d95926','circle-opacity':0.55,'circle-blur':0.3}} as any);
    m.addLayer({ id:'future-l', type:'circle', source:'future', paint:{'circle-radius':['interpolate',['linear'],['zoom'],7,1.4,12,2.8],'circle-color':'#2f7de2','circle-opacity':0.55,'circle-blur':0.3}} as any);
    m.addSource('vessels', { type:'geojson', data: emptyFC() as any});
    m.addSource('vessels-dark', { type:'geojson', data: emptyFC() as any});
    m.addLayer({ id:'vessel-shadow', type:'circle', source:'vessels', paint:{'circle-radius':9,'circle-color':'#000','circle-opacity':0.15,'circle-blur':0.6}} as any);
    m.addLayer({ id:'vessel-body', type:'circle', source:'vessels', paint:{'circle-radius':['interpolate',['linear'],['zoom'],7,4.5,12,7],'circle-color':['get','color'],'circle-stroke-width':1.5,'circle-stroke-color':'white','circle-opacity':['get','opacity']}} as any);
    m.addLayer({ id:'vessel-dark-halo', type:'circle', source:'vessels-dark', paint:{'circle-radius':9,'circle-color':'transparent','circle-stroke-color':'#f59e0b','circle-stroke-width':2,'circle-opacity':0.9}} as any);
    m.addLayer({ id:'vessel-dark-core', type:'circle', source:'vessels-dark', paint:{'circle-radius':3.5,'circle-color':'#f59e0b','circle-opacity':0.95,'circle-stroke-width':1,'circle-stroke-color':'#000'}} as any);
    (m.getSource('patrol') as any)?.setData({ type:'FeatureCollection', features: (rep.oiltrace.patrol||[]).map((t:any)=> circleGeoJSON(t))});
    const popup = new maplibregl.Popup({ closeButton:false, closeOnClick:false, offset:12 } as any);
    const enter = (e:any)=>{ (m.getCanvas() as any).style.cursor='pointer'; const f=e.features[0], p=f.properties||{}; popup.setLngLat(e.lngLat).setHTML(p.mmsi?`<b>${p.name}</b><br>MMSI ${p.mmsi} · ${p.type||''}`+(String(p.mmsi).startsWith('DARK')?' <span style="color:#f59e0b">⬡ DARK</span>':''): p.name?`<b>${p.name}</b>`: p.label||'').addTo(m);};
    const leave = ()=>{ (m.getCanvas() as any).style.cursor=''; popup.remove();};
    ['ais-l','vessel-body','vessel-dark-core','source-l'].forEach(id=>{ if (!m.getLayer(id)) return; m.on('mouseenter', id, enter); m.on('mouseleave', id, leave);});
    // fit
    const b = rep.scene.bounds;
    m.fitBounds([[b[0][1],b[0][0]],[b[1][1],b[1][0]]] as any, { padding:{top:60,bottom:100,left:30,right:20}, duration:800} as any);
  }
  function setTimeOnMap(t: number, rep: Report | null, m: maplibregl.Map) {
    if (!rep || !m.getSource('past')) return;
    // particles
    const set = t<=0 ? rep.hindcast : rep.forecast;
    let a=set[0], b=set[0], best=1e9, best2=1e9;
    for (const s of set) {
      const d=Math.abs(s.t_rel_h-t);
      if (d<best){best2=best;b=a;best=d;a=s;} else if(d<best2){best2=d;b=s;}
    }
    const span=(a.t_rel_h-b.t_rel_h)||1, f=Math.max(0,Math.min(1,(t-b.t_rel_h)/span));
    const n=Math.min(a.points.length,b.points.length);
    const feats=new Array(n);
    for(let i=0;i<n;i++){ const p=a.points[i], q=b.points[i]; feats[i]={type:'Feature',properties:{}, geometry:{type:'Point',coordinates:[q[0]+(p[0]-q[0])*f, q[1]+(p[1]-q[1])*f]}}; }
    const src = t<=0? m.getSource('past') as any : m.getSource('future') as any;
    const other = t<=0? m.getSource('future') as any : m.getSource('past') as any;
    src?.setData({type:'FeatureCollection',features:feats});
    other?.setData(emptyFC() as any);
    // vessels
    const rank = new Map(rep.suspects.map(s=>[s.mmsi,s]));
    const featsV: any[]=[], dark: any[]=[];
    const posAt = (track:[number,number,number][], tt:number)=>{
      if(!track.length|| tt<track[0][2]|| tt>track[track.length-1][2]) return null;
      for(let i=1;i<track.length;i++){ const A=track[i-1],B=track[i]; if(tt>=A[2]&&tt<=B[2]){ const s=(B[2]-A[2])||1, k=(tt-A[2])/s; return {lon:A[0]+k*(B[0]-A[0]), lat:A[1]+k*(B[1]-A[1])}; }}
      return null;
    };
    for (const v of rep.vessels) {
      const p = posAt(v.track as any, t*3600); if(!p) continue;
      const s = rank.get(v.mmsi) as any;
      const isDark = s && (s.terms?.is_dark || String(s.mmsi).startsWith('DARK'));
      const hex = s? (s.score>=0.75?'#dc2626': s.score>=0.45?'#ea580c': '#f59e0b') : '#2f7de2';
      if (isDark) dark.push({type:'Feature',properties:{mmsi:v.mmsi,name:v.name,type:v.type,color:'#f59e0b',opacity:1}, geometry:{type:'Point',coordinates:[p.lon,p.lat]}});
      else featsV.push({type:'Feature',properties:{mmsi:v.mmsi,name:v.name,type:v.type,color:hex,opacity:1}, geometry:{type:'Point',coordinates:[p.lon,p.lat]}});
    }
    for (const s of rep.suspects) {
      if(!( (s.terms as any)?.is_dark || String(s.mmsi).startsWith('DARK'))) continue;
      if(s.track && s.track.length===1 && Math.abs(t)<=0.6){
        const pt=s.track[0];
        dark.push({type:'Feature',properties:{mmsi:s.mmsi,name:s.name,type:s.type_name,color:'#f59e0b',opacity:1}, geometry:{type:'Point',coordinates:[pt[0],pt[1]]}});
      }
    }
    (m.getSource('vessels') as any)?.setData({type:'FeatureCollection',features:featsV});
    (m.getSource('vessels-dark') as any)?.setData({type:'FeatureCollection',features:dark});
    // origin slice
    if (rep.origin_pdf.slices) {
      let want=-1;
      if (t<0) rep.origin_pdf.slices.forEach((s:any,i:number)=>{ if(t<=s.t_from_h+1e-6 && t>=s.t_to_h-1e-6) want=i;});
      if (want!==activeSlice.current) {
        activeSlice.current=want;
        const slices = originSlices.current;
        const iid = rep.oiltrace.incident_id;
        const url = want>=0? slices[want] : `./incidents/${iid}/origin.png`;
        (m.getSource('originSlice') as any)?.updateImage?.({ url, coordinates: bboxFromCorners(rep.origin_pdf.bounds) as any});
        try{ m.setPaintProperty('originSlice-l','raster-opacity', want>=0?0.62:0); } catch{}
      }
    }
  }
  async function refreshVectors(m: maplibregl.Map, rep: Report, t:number) {
    const b=rep.scene.bounds;
    const q=`south=${b[0][0]}&west=${b[0][1]}&north=${b[1][0]}&east=${b[1][1]}&t_rel_h=${t}&n=18`;
    try{ const gj=await (await fetch(`/api/environment/vectors?${q}`)).json(); (m.getSource('vec') as any)?.setData(gj); m.setLayoutProperty('vec-current','visibility','visible'); m.setLayoutProperty('vec-wind','visibility','visible'); } catch{}
  }
}
