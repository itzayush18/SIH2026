import { useEffect, useState, useCallback } from 'react';
import TopBar from './components/TopBar';
import LeftPanel from './components/LeftPanel';
import MapView from './components/MapView';
import Timeline from './components/Timeline';
import RightPanel from './components/RightPanel';
import { fetchJSON } from './lib/api';
import type { Report, IncidentSummary } from './lib/types';

export default function App() {
  const [activeId, setActiveId] = useState<string | null>(null);
  const [report, setReport] = useState<Report | null>(null);
  const [incidents, setIncidents] = useState<IncidentSummary[]>([]);
  const [mode, setMode] = useState<string>('SIMULATION');
  const [time, setTime] = useState(0);
  const [timeRange, setTimeRange] = useState<[number, number]>([-24, 18]);
  const [busy, setBusy] = useState(false);
  const [stage, setStage] = useState(0);
  const [stageText, setStageText] = useState('idle');
  const [mobileTab, setMobileTab] = useState<'incidents'|'map'|'details'>('map');

  const loadIncidents = useCallback(async () => {
    try {
      const r: any = await fetchJSON('/api/incidents');
      setIncidents(r.incidents || []);
      if (r._meta?.data_mode) setMode(r._meta.data_mode);
    } catch {}
  }, []);

  const openIncident = useCallback(async (iid: string) => {
    setActiveId(iid);
    try {
      const j: any = await fetchJSON(`/api/incidents/${iid}`);
      const rep: Report = j.report;
      setReport(rep);
      setMode(rep.oiltrace.data_mode || j._meta?.data_mode || 'SIMULATION');
      // time range
      const tmin = Math.floor(Math.min(...rep.hindcast.map(s=> s.t_rel_h)));
      const tmax = Math.ceil(Math.max(...rep.forecast.map(s=> s.t_rel_h)));
      setTimeRange([tmin, tmax]);
      setTime(Math.max(tmin, rep.source.t_start/3600));
      if (window.innerWidth < 1024) setMobileTab('map');
    } catch (e) {
      console.error(e);
    }
  }, []);

  useEffect(() => {
    loadIncidents();
    // auto-open first incident or ?open=
    (async () => {
      const m = new URLSearchParams(location.search).get('open');
      if (m) {
        // wait for incidents to load
        setTimeout(async () => {
          try {
            const r: any = await fetchJSON('/api/incidents');
            const found = r.incidents.find((x: any)=> x.incident_id===m);
            if (found) openIncident(m);
            else if (r.incidents[0]) openIncident(r.incidents[0].incident_id);
          } catch {}
        }, 600);
      } else {
        setTimeout(async () => {
          try {
            const r: any = await fetchJSON('/api/incidents');
            if (r.incidents[0]) openIncident(r.incidents[0].incident_id);
          } catch {}
        }, 400);
      }
    })();
  }, [loadIncidents, openIncident]);

  const STAGES = ['ingest','detect','characterize','drift','invert','attribute'];
  const stageNames: Record<string,string> = {
    ingest:'Reading SAR scene + metocean',
    detect:'Speckle → detrend → threshold',
    characterize:'Thickness · volume · age',
    drift:'Advecting 4000 particles',
    invert:'Source-term inversion',
    attribute:'Reconstructing AIS · scoring'
  };

  const runOne = async (slug: string) => {
    setBusy(true); setStage(0); setStageText('starting…');
    const es = new EventSource(`/api/analysis/run/stream?scenario=${encodeURIComponent(slug)}`);
    STAGES.forEach(n=>{
      es.addEventListener(n, ()=> {
        const i = STAGES.indexOf(n);
        setStage(i); setStageText(stageNames[n]+' …');
      });
    });
    es.addEventListener('incident', async (ev:any)=>{
      es.close();
      setStage(6); setStageText('complete');
      setBusy(false);
      await loadIncidents();
      const inc = JSON.parse(ev.data);
      openIncident(inc.incident_id);
      setTimeout(()=>{ setStage(0); setStageText('idle');}, 1500);
    });
    es.addEventListener('error', ()=>{
      es.close(); setBusy(false); setStageText('stream lost');
    });
  };

  const runAll = async () => {
    setBusy(true); setStageText('running every scenario…');
    const es = new EventSource('/api/replay/start');
    let curName='';
    es.addEventListener('scenario_start', (ev:any)=>{
      const d=JSON.parse(ev.data);
      curName=d.name; setStage(0); setStageText(`[${d.index+1}/${d.total}] ${d.name}`);
    });
    STAGES.forEach(n=>{
      es.addEventListener(n, ()=>{
        const i=STAGES.indexOf(n);
        setStage(i); setStageText(`${curName}: ${n}…`);
      });
    });
    es.addEventListener('scenario_done', async ()=>{ await loadIncidents(); });
    es.addEventListener('replay_done', ()=>{
      es.close(); setBusy(false); setStage(6); setStageText('replay complete');
      setTimeout(()=>{ setStage(0); setStageText('idle');}, 2000);
    });
    es.addEventListener('error', ()=>{ es.close(); setBusy(false); setStageText('error');});
  };

  // Poll status for top bar
  const highRisk = incidents.filter(i=> i.severity==='CRITICAL'||i.severity==='HIGH').length;
  const candidates = incidents.reduce((a,i)=> a+(i.prime_suspect?1:0),0);

  return (
    <div className="min-h-screen bg-[#f8fafc] flex flex-col">
      <TopBar mode={mode} incidents={incidents.length} highRisk={highRisk} candidates={candidates} />

      {/* Mobile tab switcher */}
      <div className="lg:hidden flex border-b border-slate-200 bg-white sticky top-[56px] z-30">
        {(['incidents','map','details'] as const).map(t=> (
          <button
            key={t}
            onClick={()=> setMobileTab(t)}
            className={`flex-1 py-2.5 text-xs font-semibold tracking-widest uppercase border-b-2 ${mobileTab===t ? 'border-brand-500 text-slate-900' : 'border-transparent text-slate-500'}`}
          >
            {t}
          </button>
        ))}
      </div>

      <div className="flex-1 grid grid-cols-1 lg:grid-cols-[348px_1fr_430px] lg:grid-rows-[1fr_auto] min-h-0">
        {/* Left */}
        <div className={`${mobileTab!=='incidents' ? 'hidden lg:flex' : 'flex'} flex-col border-r border-slate-200 bg-white min-h-0 lg:overflow-hidden`}>
          <div className="flex-1 overflow-y-auto">
            <LeftPanel
              activeId={activeId}
              onOpen={openIncident}
              onRunOne={runOne}
              onRunAll={runAll}
              busy={busy}
              stage={stage}
              stageText={stageText}
            />
          </div>
        </div>

        {/* Center */}
        <div className={`${mobileTab!=='map' ? 'hidden lg:flex' : 'flex'} flex-col min-h-0 border-r border-slate-200`}>
          <div className="flex-1 min-h-[380px] lg:min-h-0 relative">
            <MapView report={report} time={time} />
          </div>
          <Timeline
            time={time}
            min={timeRange[0]}
            max={timeRange[1]}
            source={report?.source || null}
            onChange={setTime}
          />
        </div>

        {/* Right */}
        <div className={`${mobileTab!=='details' ? 'hidden lg:flex' : 'flex'} flex-col bg-[#f8fafc] min-h-0 lg:overflow-hidden`}>
          <div className="flex-1 overflow-y-auto">
            <RightPanel report={report} />
          </div>
        </div>
      </div>

      <footer className="hidden lg:flex items-center gap-4 px-4 py-2 bg-white border-t border-slate-200 text-xs text-slate-500 font-mono">
        <span>OILTRACE v0.4 · SIH26143 · NTRO</span>
        <span className="ml-auto">Evidence index, not probability- rankings are investigative leads.</span>
      </footer>
    </div>
  );
}
