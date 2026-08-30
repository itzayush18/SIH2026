import { useEffect, useState } from 'react';
import { fetchJSON } from '../lib/api';

interface Source {
  id: string;
  name: string;
  category: string;
  tier: string;
  status: string;
  latency_hint: string;
}

export default function TopBar({ mode, incidents, highRisk, candidates }: {
  mode: string;
  incidents: number;
  highRisk: number;
  candidates: number;
}) {
  const [sources, setSources] = useState<Source[]>([]);
  const [metaMode, setMetaMode] = useState<string>(mode);

  const load = async () => {
    try {
      const s: any = await fetchJSON('/api/system/status');
      setSources(s.sources || []);
      if (s._meta?.data_mode) setMetaMode(s._meta.data_mode);
    } catch {}
  };
  useEffect(() => { load(); const id = setInterval(load, 10000); return () => clearInterval(id); }, []);
  useEffect(() => { if (mode) setMetaMode(mode); }, [mode]);

  const modeCls =
    metaMode === 'REAL_IMAGERY_REAL_AIS' ? 'bg-emerald-500 text-white border-emerald-500' :
    metaMode === 'REAL_IMAGERY_SYNTHETIC_AIS' ? 'bg-emerald-50 text-emerald-700 border-emerald-200' :
    metaMode === 'SYNTHETIC_OVERLAY' ? 'bg-amber-50 text-amber-800 border-amber-200' :
    'bg-amber-50 text-amber-700 border-amber-300';

  const dotCls = (st: string) => {
    const s = st.toLowerCase();
    if (s === 'online') return 'bg-emerald-500 shadow-[0_0_6px_rgba(16,185,129,0.6)]';
    if (s === 'cached') return 'bg-sky-500 shadow-[0_0_6px_rgba(14,165,233,0.5)]';
    if (s === 'simulated') return 'bg-amber-400 shadow-[0_0_6px_rgba(251,191,36,0.5)]';
    return 'bg-red-500';
  };

  return (
    <header className="h-[56px] bg-white border-b border-slate-200 flex items-center gap-3 px-3 sm:px-4 shrink-0 sticky top-0 z-40">
      <div className="flex items-center gap-3 shrink-0">
        <div className="leading-none">
          <div className="font-outfit font-bold tracking-[0.18em] text-[13px] text-slate-900">OIL<span className="text-brand-500">TRACE</span></div>
          <div className="font-mono text-[9px] tracking-[0.18em] text-slate-500 font-medium -mt-0.5">SIH26143 · NTRO</div>
        </div>
        <span className={`hidden sm:inline-flex items-center px-2.5 py-1 rounded-full text-[10px] font-mono font-semibold tracking-widest border ${modeCls}`}>
          {metaMode.replace(/_/g, ' ')}
        </span>
      </div>

      <div className="hidden lg:flex items-center gap-2.5 ml-2 flex-wrap">
        {sources.slice(0, 8).map(s => (
          <div key={s.id} title={`${s.name} · ${s.tier} · ${s.status}- ${s.latency_hint}`} className="flex items-center gap-1.5">
            <span className={`w-2 h-2 rounded-full ${dotCls(s.status)}`} />
            <span className="font-mono text-[10px] tracking-wide text-slate-500 hidden xl:inline">{s.category.toUpperCase()}</span>
          </div>
        ))}
      </div>

      <div className="ml-auto flex items-center gap-2 sm:gap-4">
        <div className="hidden sm:flex items-center gap-4 font-mono text-[11px] text-slate-500">
          <span className="hidden md:inline">INCIDENTS <b className="text-slate-900 ml-1">{incidents}</b></span>
          <span className="hidden md:inline">HIGH RISK <b className="text-slate-900 ml-1">{highRisk}</b></span>
          <span>CANDIDATES <b className="text-slate-900 ml-1">{candidates}</b></span>
        </div>
        <div className="sm:hidden font-mono text-[11px] text-slate-600 bg-slate-50 border border-slate-200 rounded-full px-2.5 py-1">
          {incidents} · {candidates}
        </div>
      </div>
    </header>
  );
}
