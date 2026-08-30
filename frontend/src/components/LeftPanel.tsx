import { useEffect, useState } from 'react';
import { fetchJSON } from '../lib/api';
import type { IncidentSummary, Scenario } from '../lib/types';

export default function LeftPanel({
  activeId,
  onOpen,
  onRunOne,
  onRunAll,
  busy,
  stage,
  stageText
}: {
  activeId: string | null;
  onOpen: (id: string) => void;
  onRunOne: (slug: string) => void;
  onRunAll: () => void;
  busy: boolean;
  stage: number;
  stageText: string;
}) {
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [sel, setSel] = useState<string>('arabian-tanker');
  const [incidents, setIncidents] = useState<IncidentSummary[]>([]);

  const loadScenarios = async () => {
    const r: any = await fetchJSON('/api/scenarios');
    setScenarios(r.scenarios || []);
    if (r.scenarios?.length) setSel(r.scenarios[0].slug);
  };
  const loadIncidents = async () => {
    const r: any = await fetchJSON('/api/incidents');
    setIncidents(r.incidents || []);
  };

  useEffect(() => { loadScenarios(); loadIncidents(); const id=setInterval(loadIncidents, 4000); return()=>clearInterval(id);}, []);
  // expose reload
  useEffect(() => { (window as any).__reloadIncidents = loadIncidents; }, []);

  const cur = scenarios.find(s => s.slug === sel);
  const isReal = sel === 'zenodo-real';

  return (
    <div className="flex flex-col h-full bg-white">
      <div className="p-4 border-b border-slate-100">
        <div className="text-[11px] font-semibold tracking-[0.14em] text-slate-500 flex items-center gap-2 mb-2">
          <span className="w-3.5 h-0.5 bg-brand-500 rounded-full" /> SCENARIO
        </div>
        <select
          value={sel}
          onChange={e => setSel(e.target.value)}
          className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-2.5 text-sm text-slate-900 focus:outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-500/20"
        >
          {scenarios.map(s => (
            <option key={s.slug} value={s.slug}>
              {(s.slug === 'zenodo-real' ? '⬢ ' : '') + s.name}  ({s.difficulty})
            </option>
          ))}
        </select>

        {cur && (
          <div className={`mt-2 text-xs leading-relaxed p-2.5 rounded-lg border ${isReal ? 'bg-emerald-50 border-emerald-200 text-emerald-900' : 'bg-sky-50 border-sky-200 text-slate-700'}`}>
            {isReal && <span className="font-semibold">⬢ Real-data path §4.1- </span>}{cur.story.slice(0, 220)}…
            {isReal && <span className="text-brand-600 font-medium"> Click Run to execute.</span>}
          </div>
        )}

        <button
          onClick={() => onRunOne(sel)}
          disabled={busy}
          className={`w-full mt-3 py-2.5 rounded-lg text-sm font-semibold transition ${busy ? 'bg-slate-100 text-slate-400 cursor-wait' : 'bg-brand-500 text-white hover:bg-brand-600 shadow-soft'}`}
        >
          {busy ? 'Running…' : '▶ Run pipeline'}
        </button>
        <button
          onClick={onRunAll}
          disabled={busy}
          className="w-full mt-2 py-2 rounded-lg text-sm border border-slate-200 text-slate-600 hover:bg-slate-50 disabled:opacity-50"
        >
          ▶▶ Run every scenario
        </button>

        <div className="mt-3 h-1.5 bg-slate-100 rounded-full overflow-hidden">
          <div className="h-full bg-brand-500 transition-all duration-500" style={{ width: `${(stage/6)*100}%` }} />
        </div>
        <div className="mt-1.5 font-mono text-[11px] text-slate-500 min-h-[16px]">{stageText}</div>
      </div>

      <div className="flex-1 overflow-y-auto p-2">
        <div className="text-[11px] font-semibold tracking-[0.14em] text-slate-500 px-2 py-2 flex items-center gap-2">
          <span className="w-3.5 h-0.5 bg-brand-500 rounded-full" /> ACTIVE INCIDENTS
        </div>
        {incidents.length === 0 && (
          <div className="mx-2 p-3 bg-slate-50 border border-slate-200 rounded-lg text-xs text-slate-500 leading-relaxed text-center">
            No incidents yet- pick a scenario and run the pipeline. The 7th card (Zenodo- REAL) is the live-data path.
          </div>
        )}
        <div className="space-y-2">
          {incidents.map(i => {
            const mode = (i.data_mode || '').replace(/_/g, ' ');
            const modeColor = mode.includes('REAL') ? 'text-emerald-700 bg-emerald-50 border-emerald-200' : 'text-amber-700 bg-amber-50 border-amber-200';
            return (
              <button
                key={i.incident_id}
                onClick={() => onOpen(i.incident_id)}
                className={`w-full text-left bg-white border rounded-xl p-3 hover:shadow-card transition text-sm ${activeId === i.incident_id ? 'border-brand-500 ring-2 ring-brand-500/15 shadow-card' : 'border-slate-200'}`}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="font-mono text-[11px] font-semibold text-slate-900">{i.incident_id}</span>
                  <span className="flex items-center gap-1.5">
                    <span className={`hidden sm:inline font-mono text-[10px] px-1.5 py-0.5 rounded-full border font-semibold ${modeColor}`}>{mode}</span>
                    <span className={`font-mono text-[10px] px-2 py-0.5 rounded-full border font-semibold
                      ${i.severity==='CRITICAL'?'text-red-600 border-red-200 bg-red-50':
                        i.severity==='HIGH'?'text-orange-600 border-orange-200 bg-orange-50':
                        'text-amber-700 border-amber-200 bg-amber-50'}`}>{i.severity}</span>
                  </span>
                </div>
                <div className="font-medium text-slate-900 leading-snug mt-1 line-clamp-2">{i.scenario.subtitle}{mode.includes('REAL') && <span className="text-emerald-600 text-xs"> ⬢ REAL</span>}</div>
                <div className="font-mono text-[11px] text-slate-500 mt-1">
                  {Number(i.area_km2).toFixed(0)} km² · P(oil) {Number(i.p_oil).toFixed(2)} · {i.jurisdiction} · {Number(i.nearest_coast.km).toFixed(0)} km to {i.nearest_coast.name}
                </div>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
