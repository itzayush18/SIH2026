import { useState, useEffect } from 'react';
import { fetchJSON, postDecision, isStatic } from '../lib/api';
import type { AnalystDecision } from '../lib/api';
import type { Report } from '../lib/types';

const VERDICT: Record<string, { label: string; cls: string }> = {
  RANKED:                { label: 'RANKED LEAD',          cls: 'text-red-700 bg-red-50 border-red-200' },
  REVIEW:                { label: 'ANALYST REVIEW',       cls: 'text-amber-700 bg-amber-50 border-amber-200' },
  INSUFFICIENT_EVIDENCE: { label: 'INSUFFICIENT EVIDENCE', cls: 'text-slate-600 bg-slate-100 border-slate-300' },
};

const QUALITY: Record<string, string> = {
  HIGH:   'text-emerald-700 bg-emerald-50 border-emerald-200',
  MEDIUM: 'text-amber-700 bg-amber-50 border-amber-200',
  LOW:    'text-red-700 bg-red-50 border-red-200',
  NONE:   'text-slate-600 bg-slate-100 border-slate-300',
  ND:     'text-slate-600 bg-slate-100 border-slate-300',
};

/** Accept / Reject / Escalate for one candidate.
 *
 * The model proposes; the analyst disposes. Nothing here changes the score-
 * the ruling is recorded alongside it so the audit trail shows both what the
 * system computed and what the human decided.
 */
function DecisionBar({ iid, mmsi, existing }: {
  iid: string; mmsi: string; existing?: AnalystDecision | null;
}) {
  const [decision, setDecision] = useState<AnalystDecision | null>(existing ?? null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  const [analyst, setAnalyst] = useState(() => localStorage.getItem('oiltrace.analyst') || '');
  const [offline, setOffline] = useState(false);

  useEffect(() => { isStatic().then(setOffline).catch(()=>{}); }, []);
  useEffect(() => { setDecision(existing ?? null); }, [existing]);

  async function act(action: AnalystDecision['action']) {
    if (!analyst.trim()) { setErr('enter your name first- decisions are attributable'); return; }
    setBusy(true); setErr('');
    try {
      localStorage.setItem('oiltrace.analyst', analyst.trim());
      setDecision(await postDecision(iid, mmsi, action, analyst.trim()));
    } catch (e: any) {
      setErr(e?.message || 'could not record decision');
    } finally { setBusy(false); }
  }

  if (offline) {
    return (
      <div className="mt-2 pt-2 border-t border-slate-100 text-[11px] font-mono text-slate-400">
        analyst review unavailable in static export
      </div>
    );
  }

  return (
    <div className="mt-2 pt-2 border-t border-slate-100">
      {decision && (
        <div className="text-[11px] font-mono text-slate-600 mb-1.5">
          <span className="font-semibold text-slate-800">{decision.action}</span>
          {' by '}{decision.analyst}
          <span className="text-slate-400"> · {decision.at}</span>
        </div>
      )}
      <div className="flex items-center gap-1.5">
        <input
          value={analyst}
          onChange={e=>setAnalyst(e.target.value)}
          placeholder="analyst"
          aria-label="Analyst name"
          className="flex-1 min-w-0 px-2 py-1 text-[11px] font-mono border border-slate-200 rounded-md focus:outline-none focus:border-brand-400"
        />
        {(['ACCEPT','REJECT','ESCALATE'] as const).map(a=> (
          <button
            key={a}
            onClick={()=>act(a)}
            disabled={busy}
            title={`${a[0]}${a.slice(1).toLowerCase()} this candidate`}
            className={`px-2 py-1 text-[10px] font-mono font-semibold rounded-md border transition disabled:opacity-40 ${
              decision?.action===a ? 'bg-slate-800 text-white border-slate-800'
                                   : 'bg-white text-slate-600 border-slate-200 hover:border-slate-400'}`}
          >{a[0]}</button>
        ))}
      </div>
      {err && <div className="mt-1 text-[10px] font-mono text-red-600">{err}</div>}
    </div>
  );
}

const TERMS: [string, string][] = [
  ['source_match','Source track'],
  ['spatiotemporal','Origin envelope'],
  ['behaviour','Behaviour'],
  ['dark','AIS gap'],
  ['alignment','Axis align'],
  ['prior','Vessel prior'],
];

function risk(s: number) {
  if (s >= 0.75) return { label: 'PRIME SUSPECT', color: 'text-red-600 bg-red-50 border-red-200', hex: '#dc2626' };
  if (s >= 0.45) return { label: 'PERSON OF INTEREST', color: 'text-orange-600 bg-orange-50 border-orange-200', hex: '#ea580c' };
  if (s >= 0.20) return { label: 'TO ELIMINATE', color: 'text-amber-700 bg-amber-50 border-amber-200', hex: '#d97706' };
  return { label: 'CLEARED', color: 'text-emerald-700 bg-emerald-50 border-emerald-200', hex: '#059669' };
}

function Bars({ terms }: { terms: Record<string, number> }) {
  return (
    <div className="space-y-1.5 mt-2">
      {TERMS.map(([k, label]) => {
        const v = Math.max(0, Math.min(1, terms[k] ?? 0));
        return (
          <div key={k} className="grid grid-cols-[96px_1fr_36px] items-center gap-2 text-xs text-slate-600">
            <span className="text-[11px]">{label}</span>
            <div className="h-1.5 bg-slate-100 rounded-full overflow-hidden">
              <div className="h-full bg-brand-500 rounded-full transition-all duration-500" style={{ width: `${(v*100).toFixed(0)}%` }} />
            </div>
            <span className="font-mono text-[11px] text-slate-500 text-right">{v.toFixed(2)}</span>
          </div>
        );
      })}
    </div>
  );
}

function Stack({ terms }: { terms: Record<string, number> }) {
  const cols = ['#10b981','#2f7de2','#ea580c','#f59e0b','#8b5cf6','#059669'];
  return (
    <div className="flex h-1.5 rounded-full overflow-hidden bg-slate-100 mt-1.5">
      {TERMS.map(([k], i) => {
        const v = Math.max(0, Math.min(1, terms[k] ?? 0));
        if (v < 0.02) return null;
        return <div key={k} style={{ width: `${(v*18).toFixed(1)}%`, background: cols[i] }} />;
      })}
    </div>
  );
}

export default function RightPanel({ report }: { report: Report | null }) {
  const [tab, setTab] = useState<'overview'|'suspects'|'alerts'|'patrol'|'timeline'|'evidence'>('overview');
  const [timeline, setTimeline] = useState<any[]>([]);

  useEffect(() => {
    if (!report || tab!=='timeline') return;
    fetchJSON<any>(`/api/incidents/${report.oiltrace.incident_id}/timeline`).then(j=> setTimeline(j.events||[])).catch(()=>{});
  }, [report, tab]);

  if (!report) {
    return (
      <div className="p-4">
        <div className="bg-slate-50 border border-slate-200 rounded-xl p-4 text-sm text-slate-500 text-center">
          Select an incident on the left.
        </div>
      </div>
    );
  }

  const d = report.detections[0];
  const c = report.characterization;
  const o = report.oiltrace;
  const dm = o.data_mode;
  const v = report.validation;

  return (
    <div className="flex flex-col h-full">
      <div className="flex gap-1 border-b border-slate-200 sticky top-0 bg-white z-10 px-1">
        {(['overview','suspects','alerts','patrol','timeline','evidence'] as const).map(t=> (
          <button
            key={t}
            onClick={()=> setTab(t)}
            className={`flex-1 py-2.5 text-[11px] font-semibold tracking-widest uppercase border-b-2 transition ${tab===t ? 'text-slate-900 border-brand-500' : 'text-slate-500 border-transparent hover:text-slate-700'}`}
          >
            {t}
          </button>
        ))}
      </div>

      <div className="flex-1 overflow-y-auto p-3 space-y-3">
        {tab==='overview' && (
          <>
            <div className="bg-white border border-slate-200 rounded-xl p-3">
              <div className="text-xs text-slate-500 leading-relaxed">
                <span className="font-semibold text-slate-900">{o.incident_id}</span> · {o.scenario.name}<br />
                <span className={`inline-flex items-center px-1.5 py-0.5 rounded-full text-[10px] font-mono border font-semibold mt-1 ${dm.includes('REAL') ? 'bg-emerald-50 text-emerald-700 border-emerald-200' : 'bg-amber-50 text-amber-700 border-amber-200'}`}>{dm.replace(/_/g,' ')}</span>
                <span className="ml-1">· {report.generated_for} UTC · {Number(report.scene.mean_wind_ms).toFixed(1)} m/s wind</span>
              </div>
              <div className="mt-2 text-xs bg-slate-50 border border-slate-200 rounded-lg p-2.5 leading-relaxed text-slate-700">
                <span className="font-semibold text-slate-900">Provenance:</span> {o.provenance.chain[0]}<br />
                <span className="text-slate-500">Mode {dm} · forcing: {(o.provenance as any).forcing_product || 'see registry'}</span>
              </div>
            </div>

            <div>
              <h3 className="text-[11px] font-semibold tracking-widest text-slate-500 flex items-center gap-2 mb-2"><span className="w-3.5 h-0.5 bg-brand-500 rounded-full"/> SLICK</h3>
              <div className="grid grid-cols-2 gap-2">
                <div className="bg-white border border-slate-200 rounded-xl p-3">
                  <div className="text-[10px] tracking-widest text-slate-500 font-semibold">AREA</div>
                  <div className="font-mono text-lg font-semibold text-slate-900">{Number(d.area_km2).toFixed(1)}<span className="text-xs font-normal text-slate-500"> km²</span></div>
                </div>
                <div className="bg-white border border-slate-200 rounded-xl p-3">
                  <div className="text-[10px] tracking-widest text-slate-500 font-semibold">EXTENT</div>
                  <div className="font-mono text-lg font-semibold text-slate-900">{Number(d.length_km).toFixed(1)}<span className="text-xs font-normal text-slate-500"> × {Number(d.width_km).toFixed(1)} km</span></div>
                </div>
                <div className="bg-white border border-slate-200 rounded-xl p-3">
                  <div className="text-[10px] tracking-widest text-slate-500 font-semibold">P(OIL)</div>
                  <div className="font-mono text-lg font-semibold text-slate-900">{Number(d.p_oil).toFixed(3)}</div>
                </div>
                <div className="bg-white border border-slate-200 rounded-xl p-3">
                  <div className="text-[10px] tracking-widest text-slate-500 font-semibold">EST. AGE</div>
                  <div className="font-mono text-lg font-semibold text-slate-900">{Number(c.age_best_h).toFixed(1)}<span className="text-xs font-normal text-slate-500"> h</span></div>
                </div>
              </div>
              <div className="bg-white border border-slate-200 rounded-xl p-3 mt-2 divide-y divide-slate-100">
                <div className="flex justify-between py-1.5 text-sm"><span className="text-slate-500">Bonn appearance</span><span className="font-mono font-semibold">{c.bonn_class}</span></div>
                <div className="flex justify-between py-1.5 text-sm"><span className="text-slate-500">Thickness</span><span className="font-mono font-semibold">{(c.thickness_m*1e6).toFixed(1)} µm</span></div>
                <div className="flex justify-between py-1.5 text-sm"><span className="text-slate-500">Volume</span><span className="font-mono font-semibold">{Number(c.volume_m3).toFixed(0)} m³ · {Number(c.tonnes).toFixed(0)} t</span></div>
                <div className="flex justify-between py-1.5 text-sm"><span className="text-slate-500">Age confidence</span><span className="font-mono font-semibold">{c.confidence} (×{Number(c.age_uncertainty_factor).toFixed(1)})</span></div>
                <div className="flex justify-between py-1.5 text-sm"><span className="text-slate-500">Detector</span><span className="font-mono font-semibold">{o.detector === 'unet' ? 'U-Net segmenter' : '8-feature logistic'}</span></div>
              </div>
            </div>

            <div>
              <h3 className="text-[11px] font-semibold tracking-widest text-slate-500 flex items-center gap-2 mb-2"><span className="w-3.5 h-0.5 bg-brand-500 rounded-full"/> JURISDICTION</h3>
              <div className="bg-white border border-slate-200 rounded-xl p-3 divide-y divide-slate-100 text-sm">
                <div className="flex justify-between py-1.5"><span className="text-slate-500">Area</span><span className="font-semibold">{o.jurisdiction.name}</span></div>
                <div className="flex justify-between py-1.5"><span className="text-slate-500">Sovereign</span><span className="font-semibold">{o.jurisdiction.sovereign || '—'}</span></div>
                <div className="flex justify-between py-1.5"><span className="text-slate-500">MARPOL regime</span><span className={`font-semibold ${o.jurisdiction.marpol_regime==='special_area'?'text-amber-600':''}`}>{o.jurisdiction.marpol_regime}</span></div>
                <div className="flex justify-between py-1.5"><span className="text-slate-500">Nearest coast</span><span className="font-mono font-semibold">{Number(o.nearest_coast.km).toFixed(0)} km · {o.nearest_coast.name}</span></div>
              </div>
            </div>

            <div>
              <h3 className="text-[11px] font-semibold tracking-widest text-slate-500 flex items-center gap-2 mb-2"><span className="w-3.5 h-0.5 bg-brand-500 rounded-full"/> RECONSTRUCTED ORIGIN</h3>
              <div className="bg-white border border-slate-200 rounded-xl p-3 divide-y divide-slate-100 text-sm">
                <div className="flex justify-between py-1.5"><span className="text-slate-500">Release start</span><span className="font-mono font-semibold">{(report.source.t_start/3600).toFixed(1)} h before acq</span></div>
                <div className="flex justify-between py-1.5"><span className="text-slate-500">Duration</span><span className="font-mono font-semibold">{(report.source.duration/3600).toFixed(1)} h</span></div>
                <div className="flex justify-between py-1.5"><span className="text-slate-500">Course / speed</span><span className="font-mono font-semibold">{Number(report.source.course_deg).toFixed(0)}° · {Number(report.source.speed_kn).toFixed(1)} kn</span></div>
                <div className="flex justify-between py-1.5"><span className="text-slate-500">Start position</span><span className="font-mono font-semibold">{Number(report.source.start_lat).toFixed(3)}, {Number(report.source.start_lon).toFixed(3)}</span></div>
                <div className="flex justify-between py-1.5"><span className="text-slate-500">Inversion IoU</span><span className="font-mono font-semibold">{Number(report.source.iou).toFixed(3)}</span></div>
                <div className="flex justify-between py-1.5"><span className="text-slate-500">Search dispersion</span><span className="font-mono font-semibold">{Number(report.source.search_dispersion.position_sd_km).toFixed(1)} km · {Number(report.source.search_dispersion.t_start_sd_h).toFixed(1)} h</span></div>
              </div>
            </div>

            {Number.isFinite(v?.segmentation?.iou) ? (
              <div>
                <h3 className="text-[11px] font-semibold tracking-widest text-slate-500 flex items-center gap-2 mb-2"><span className="w-3.5 h-0.5 bg-brand-500 rounded-full"/> VALIDATION VS TRUTH</h3>
                <div className="bg-white border border-slate-200 rounded-xl p-3 divide-y divide-slate-100 text-sm">
                  <div className="flex justify-between py-1.5"><span className="text-slate-500">Segmentation IoU / F1</span><span className="font-mono font-semibold">{Number(v.segmentation.iou).toFixed(3)} / {Number(v.segmentation.f1).toFixed(3)}</span></div>
                  <div className="flex justify-between py-1.5"><span className="text-slate-500">Origin error</span><span className="font-mono font-semibold">{Number(v.inversion_error_km).toFixed(2)} km</span></div>
                  <div className="flex justify-between py-1.5"><span className="text-slate-500">Time error</span><span className="font-mono font-semibold">{Number(v.inversion_time_error_h*60).toFixed(0)} min</span></div>
                  <div className="flex justify-between py-1.5"><span className="text-slate-500">Attribution</span><span className={`font-semibold ${v.attribution_correct?'text-emerald-600':'text-red-600'}`}>{v.attribution_correct?'correct':'incorrect'}</span></div>
                </div>
              </div>
            ) : (
              <div>
                <h3 className="text-[11px] font-semibold tracking-widest text-slate-500 flex items-center gap-2 mb-2"><span className="w-3.5 h-0.5 bg-brand-500 rounded-full"/> VALIDATION</h3>
                <div className="bg-white border border-slate-200 rounded-xl p-3 text-sm text-slate-600 leading-relaxed">
                  {(v as any)?.note || 'Real satellite input- no laboratory ground truth.'}<br />
                  Confidence rests on inversion IoU ({Number(report.source.iou).toFixed(3)}) and search dispersion.
                </div>
              </div>
            )}

            <div className="text-xs text-slate-500 leading-relaxed">
              Rankings are evidence indices (0–1), not probabilities. Enforcement under MARPOL requires corroboration (oil fingerprinting, port state inspection).
            </div>
          </>
        )}

        {tab==='suspects' && (
          <>
            <div className="flex flex-wrap gap-1.5 text-[11px] font-mono text-slate-600">
              <span className="inline-flex items-center gap-1"><i className="w-2.5 h-2.5 rounded-sm bg-brand-500 inline-block"/>AIS</span>
              <span className="inline-flex items-center gap-1"><i className="w-2.5 h-2.5 rounded-sm bg-[#d95926] inline-block"/>slick</span>
              <span className="inline-flex items-center gap-1"><i className="w-2.5 h-2.5 rounded-sm bg-emerald-500 inline-block"/>source</span>
              <span className="inline-flex items-center gap-1"><i className="w-2.5 h-2.5 rounded-sm bg-red-600 inline-block"/>prime</span>
              <span className="inline-flex items-center gap-1"><i className="w-2.5 h-2.5 rounded-sm border border-amber-400 inline-block bg-transparent"/>dark</span>
            </div>
            {report.suspects.length===0 && (
              <div className="bg-amber-50 border border-amber-200 rounded-xl p-3 text-sm text-amber-900">
                <span className="font-semibold">Insufficient evidence</span>- no vessel scored above threshold. This is an honest terminal state.
              </div>
            )}
            {report.suspects.slice(0,6).map((s,i)=> {
              const r=risk(s.score);
              const isDark = (s.terms as any)?.is_dark || String(s.mmsi).startsWith('DARK');
              return (
                <div key={s.mmsi} className={`bg-white border rounded-xl p-3 hover:shadow-card transition ${i===0?'border-brand-200 shadow-card': isDark?'border-amber-300 border-dashed bg-amber-50/50':'border-slate-200'}`}>
                  <div className="flex items-baseline justify-between gap-2">
                    <div>
                      <span className="font-semibold text-sm text-slate-900">{s.name}</span>
                      <span className="font-mono text-xs text-slate-500"> · MMSI {s.mmsi}{isDark && <span className="text-amber-600"> ⬡ DARK</span>}</span>
                    </div>
                    <span className="font-mono text-lg font-bold" style={{ color: r.hex }}>{s.score.toFixed(2)}</span>
                  </div>
                  <div className="flex items-center justify-between mt-1">
                    <span className="font-mono text-xs text-slate-500">{s.type_name} · {Number(s.length).toFixed(0)} m</span>
                    <span className={`text-[10px] font-mono px-2 py-0.5 rounded-full border font-semibold ${r.color}`}>{r.label}</span>
                  </div>
                  <div className="flex flex-wrap items-center gap-1.5 mt-1.5">
                    {s.verdict && (
                      <span className={`text-[10px] font-mono px-2 py-0.5 rounded-full border font-semibold ${VERDICT[s.verdict]?.cls ?? ''}`}>
                        {VERDICT[s.verdict]?.label ?? s.verdict}
                      </span>
                    )}
                    {s.ais_quality_grade && (
                      <span className={`text-[10px] font-mono px-2 py-0.5 rounded-full border ${QUALITY[s.ais_quality_grade] ?? ''}`}
                            title="Quality of the AIS record over the release window">
                        AIS {s.ais_quality_grade}
                      </span>
                    )}
                  </div>
                  {s.verdict_reason && (
                    <div className="mt-1 text-[11px] text-slate-500 italic leading-snug">{s.verdict_reason}</div>
                  )}
                  <Stack terms={s.terms} />
                  <Bars terms={s.terms} />
                  <ul className="mt-2 list-disc pl-4 space-y-1 text-xs text-slate-600 leading-relaxed">
                    {s.evidence.map((e,idx)=><li key={idx}>{e}</li>)}
                  </ul>
                  <DecisionBar iid={report.oiltrace.incident_id} mmsi={s.mmsi}
                               existing={s.analyst_decision} />
                </div>
              );
            })}
            <details className="bg-white border border-slate-200 rounded-xl p-3">
              <summary className="text-xs font-mono text-slate-600 cursor-pointer">Evidence table (accessible view)</summary>
              <div className="overflow-x-auto mt-2">
                <table className="w-full text-xs font-mono">
                  <thead><tr className="text-slate-500"><th className="text-left py-1">Vessel</th>{TERMS.map(([k,l])=> <th key={k} className="text-right px-1">{l}</th>)}<th className="text-right">Score</th></tr></thead>
                  <tbody className="divide-y divide-slate-100">
                    {report.suspects.slice(0,6).map(s=> (
                      <tr key={s.mmsi}><td className="py-1 text-left">{s.name}{(s.terms as any)?.is_dark?' ⬡':''}</td>{TERMS.map(([k])=> <td key={k} className="text-right px-1">{Number(s.terms[k]??0).toFixed(2)}</td>)}<td className="text-right font-semibold">{s.score.toFixed(2)}</td></tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </details>
          </>
        )}

        {tab==='alerts' && (
          <>
            {o.alerts.length===0 && <div className="bg-white border border-slate-200 rounded-xl p-3 text-sm text-slate-500">No alerts- incident below threshold.</div>}
            {o.alerts.map(a=> {
              const isDark = a.kind==='DARK_VESSEL_NO_AIS';
              return (
                <div key={a.id} className={`bg-white border rounded-xl p-3 ${isDark ? 'border-amber-200 bg-amber-50/50' : 'border-slate-200'} ${a.severity==='CRITICAL'?'border-l-4 border-l-red-600': a.severity==='HIGH'?'border-l-4 border-l-orange-500': a.severity==='MEDIUM'?'border-l-4 border-l-amber-400':'border-l-4 border-l-slate-300'}`}>
                  <div className="text-[11px] font-mono font-semibold tracking-widest text-slate-500">■ {a.severity} · {a.kind}{isDark?' ⬡ DARK':''}</div>
                  <div className="font-semibold text-sm text-slate-900 mt-1">{a.title}</div>
                  <div className="text-xs text-slate-600 leading-relaxed mt-1">{a.message}</div>
                </div>
              );
            })}
          </>
        )}

        {tab==='patrol' && (
          <>
            <div className="bg-sky-50 border border-sky-200 rounded-xl p-3 text-xs leading-relaxed text-slate-700">
              Decision-support tasking. Not tactical guidance- dispatch, boarding and use of force remain under human authority. Nearest asset + ETA from representative ICG stations (demo, §4.6).
            </div>
            {o.patrol.map(t=> (
              <div key={t.id} className="bg-white border border-slate-200 rounded-xl p-3">
                <div className="flex justify-between text-[11px] font-mono font-semibold tracking-widest text-slate-500">
                  <span className={t.priority==='P1'?'text-red-600': t.priority==='P2'?'text-orange-600':'text-sky-600'}>● {t.priority} · {t.action}</span>
                  <span>{t.asset_class}</span>
                </div>
                <div className="font-semibold text-sm text-slate-900 mt-1">{t.target}</div>
                <div className="text-xs text-slate-600 leading-relaxed mt-1">{t.reason}</div>
                <div className="text-xs font-mono text-slate-500 mt-1">{Number(t.lat).toFixed(3)}, {Number(t.lon).toFixed(3)} · r={Number(t.radius_km).toFixed(0)} km</div>
                <div className="mt-2 bg-slate-50 border border-slate-200 rounded-lg p-2 text-xs text-slate-700">
                  <span className="font-semibold">Nearest:</span> {t.nearest_asset?.station || '—'}- {t.eta || t.eta_hint}
                </div>
              </div>
            ))}
          </>
        )}

        {tab==='timeline' && (
          <>
            <h3 className="text-[11px] font-semibold tracking-widest text-slate-500">INCIDENT TIMELINE</h3>
            <div className="bg-white border border-slate-200 rounded-xl overflow-hidden divide-y divide-slate-100">
              {timeline.length===0 && <div className="p-3 text-sm text-slate-500">Loading timeline…</div>}
              {timeline.map((ev:any, i:number)=> (
                <div key={i} className="flex gap-3 p-3">
                  <span className="font-mono text-xs text-slate-500 min-w-[56px]">{ev.t_rel_h < 0 ? Number(ev.t_rel_h).toFixed(1) : `+${Number(ev.t_rel_h).toFixed(1)}`}h</span>
                  <span className={`w-2 h-2 rounded-full mt-1.5 shrink-0 ${ev.kind==='acquisition'?'bg-emerald-500': ev.kind.includes('release')?'bg-orange-500': ev.kind.includes('ais_gap')?'bg-red-500':'bg-sky-500'}`} />
                  <span className="text-sm text-slate-900 leading-relaxed flex-1">{ev.label}</span>
                </div>
              ))}
            </div>
            <div className="text-xs text-slate-500">Times relative to SAR acquisition. Negative = before, positive = after.</div>
          </>
        )}

        {tab==='evidence' && (
          <>
            <div className="bg-white border border-slate-200 rounded-xl p-3">
              <div className="font-semibold text-sm text-slate-900">Evidence package</div>
              <div className="text-xs text-slate-600 leading-relaxed mt-1">A traceable investigation dossier for {o.incident_id}. Every claim is linked to its model version and dataset via the provenance chain.</div>
              <div className="flex flex-wrap gap-2 mt-3">
                <a href={`/incidents/${o.incident_id}/${o.evidence_pack.json}`} download className="px-3 py-1.5 bg-white border border-slate-200 rounded-lg text-xs font-medium hover:bg-slate-50">⬇ JSON</a>
                <a href={`/incidents/${o.incident_id}/${o.evidence_pack.geojson}`} download className="px-3 py-1.5 bg-white border border-slate-200 rounded-lg text-xs font-medium hover:bg-slate-50">⬇ GeoJSON</a>
                <a href={`/incidents/${o.incident_id}/${o.evidence_pack.csv}`} download className="px-3 py-1.5 bg-white border border-slate-200 rounded-lg text-xs font-medium hover:bg-slate-50">⬇ Suspects CSV</a>
                <a href={`/api/incidents/${o.incident_id}/evidence.pdf`} download className="px-3 py-1.5 bg-brand-500 text-white rounded-lg text-xs font-medium hover:bg-brand-600">⬇ PDF report</a>
              </div>
            </div>

            <h3 className="text-[11px] font-semibold tracking-widest text-slate-500">INVESTIGATOR BRIEFS (GROUNDED, NFR-10)</h3>
            {report.suspects.slice(0,3).map(s=> {
              const txt = (s as any).narrative || `${s.name} (MMSI ${s.mmsi})- evidence index ${s.score.toFixed(2)} (source-track ${(s.terms.source_match||0).toFixed(2)}, origin-envelope ${(s.terms.spatiotemporal||0).toFixed(2)}). Time-space provenance: inversion from ${(report.source.t_start/3600).toFixed(1)}h before acq, duration ${(report.source.duration/3600).toFixed(1)}h on course ${Number(report.source.course_deg).toFixed(0)}° at ${Number(report.source.speed_kn).toFixed(1)} kn (IoU ${Number(report.source.iou).toFixed(3)}). Evidence: ${s.evidence.slice(0,2).join('; ')}. This is an investigative lead, not a finding of guilt- corroboration required.`;
              return (
                <div key={s.mmsi} className="bg-sky-50 border border-sky-200 rounded-xl p-3">
                  <div className="text-[11px] font-mono font-semibold tracking-widest text-slate-500">◈ GROUNDED BRIEF- NFR-10 SAFE</div>
                  <p className="text-sm text-slate-900 leading-relaxed mt-1">{txt}</p>
                  <div className="text-xs font-mono text-slate-500 border-t border-sky-200 pt-2 mt-2">Trace: evidence index {s.score.toFixed(2)} · source {(report.source.t_start/3600).toFixed(1)}h · {s.evidence[0]?.slice(0,60) || ''}</div>
                </div>
              );
            })}

            <h3 className="text-[11px] font-semibold tracking-widest text-slate-500">PROVENANCE CHAIN</h3>
            <div className="bg-white border border-slate-200 rounded-xl p-3 divide-y divide-slate-100">
              {o.provenance.chain.map((line,idx)=> (
                <div key={idx} className="flex gap-2 py-1.5 text-xs"><span className="font-mono text-slate-400">Step {idx+1}</span><span className="text-slate-700 flex-1">{line}</span></div>
              ))}
              <div className="flex justify-between py-1.5 text-xs"><span className="text-slate-500">Generated</span><span className="font-mono font-semibold">{o.provenance.generated_at}</span></div>
              <div className="flex justify-between py-1.5 text-xs"><span className="text-slate-500">Data mode</span><span className={`px-2 py-0.5 rounded-full border text-[11px] font-mono font-semibold ${dm.includes('REAL')?'bg-emerald-50 text-emerald-700 border-emerald-200':'bg-amber-50 text-amber-700 border-amber-200'}`}>{dm}</span></div>
            </div>

            <h3 className="text-[11px] font-semibold tracking-widest text-slate-500">MODEL VERSIONS</h3>
            <div className="bg-white border border-slate-200 rounded-xl p-3 divide-y divide-slate-100">
              {Object.entries(o.provenance.model_versions).map(([k,v])=> (
                <div key={k} className="flex justify-between py-1.5 text-xs"><span className="text-slate-500">{k}</span><span className="font-mono text-slate-900">{v as string}</span></div>
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
