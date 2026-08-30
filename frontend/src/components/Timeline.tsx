import { useEffect, useRef, useState } from 'react';

export default function Timeline({
  time,
  min,
  max,
  source,
  onChange,
  onPlayingChange
}: {
  time: number;
  min: number;
  max: number;
  source: { t_start: number; duration: number } | null;
  onChange: (t: number) => void;
  onPlayingChange?: (p: boolean) => void;
}) {
  const [playing, setPlaying] = useState(false);
  const raf = useRef<number | null>(null);
  const last = useRef<number>(0);

  useEffect(() => { onPlayingChange?.(playing); }, [playing]);

  useEffect(() => {
    if (!playing) return;
    const step = (now: number) => {
      const dt = (now - last.current) / 1000;
      last.current = now;
      let nt = time + dt * 4.5;
      if (nt >= max) { onChange(max); setPlaying(false); return; }
      // use functional update via onChange closure stale, so we need to read latest time via ref
      onChange(nt);
      raf.current = requestAnimationFrame(step);
    };
    // hack: we read time from closure, so restart loop on time change via effect
    return () => {};
  }, [playing, time, max, onChange]);

  // alternative loop that reads latest time via ref
  const timeRef = useRef(time);
  timeRef.current = time;
  useEffect(() => {
    if (!playing) { if (raf.current) cancelAnimationFrame(raf.current); return; }
    last.current = performance.now();
    const loop = (now: number) => {
      const dt = (now - last.current) / 1000;
      last.current = now;
      let nt = timeRef.current + dt * 4.5;
      if (nt >= max) { onChange(max); setPlaying(false); return; }
      onChange(nt);
      raf.current = requestAnimationFrame(loop);
    };
    raf.current = requestAnimationFrame(loop);
    return () => { if (raf.current) cancelAnimationFrame(raf.current); };
  }, [playing, max, onChange]);

  const toggle = () => {
    if (playing) setPlaying(false);
    else {
      if (time >= max - 0.01) onChange(min);
      setPlaying(true);
    }
  };

  const epochMs = Date.now(); // not needed, we just show relative
  // clock will be computed in parent from report generated_for, so we show relative here
  // But we still show time value
  return (
    <div className="bg-white border-t border-slate-200 px-3 sm:px-4 py-3">
      <div className="flex items-center gap-3">
        <button
          onClick={toggle}
          className={`w-9 h-9 rounded-full flex items-center justify-center text-white shrink-0 ${playing ? 'bg-slate-900' : 'bg-brand-500 hover:bg-brand-600'}`}
          aria-label={playing ? 'Pause' : 'Play'}
        >
          <span className="text-sm leading-none">{playing ? '❚❚' : '▶'}</span>
        </button>
        <input
          type="range"
          min={min}
          max={max}
          step={0.25}
          value={time}
          onChange={e => { setPlaying(false); onChange(parseFloat(e.target.value)); }}
          className="flex-1 accent-brand-500 h-1.5"
        />
        <div className="hidden sm:block text-right min-w-[140px]">
          <div className="font-mono text-sm font-semibold text-slate-900">{time < 0 ? time.toFixed(1) : `+${time.toFixed(1)}`} h</div>
          <div className="text-[11px] text-slate-500 -mt-0.5">{time === 0 ? 'ACQUISITION' : time < 0 ? 'BEFORE ACQUISITION' : 'AFTER ACQUISITION'}</div>
        </div>
        <div className="sm:hidden font-mono text-xs font-semibold text-slate-900 min-w-[64px] text-right">{time.toFixed(1)}h</div>
      </div>

      <div className="relative h-5 mt-2 mx-1 sm:mx-12 text-[10px] font-mono text-slate-500">
        {Array.from({ length: Math.floor((max - min)/6)+1 }).map((_, i) => {
          const h = Math.ceil(min) + i*6;
          if (h > max) return null;
          const pct = ((h - min) / (max - min)) * 100;
          return (
            <span key={h} className={`absolute -translate-x-1/2 ${h===0?'text-slate-900 font-semibold':''}`} style={{ left: `${pct}%` }}>
              {h===0?'ACQ': (h<0?`${h}h`:`+${h}h`)}
            </span>
          );
        })}
        {source && (
          <span
            className="absolute top-3 text-[10px] text-emerald-700 font-mono font-semibold border-l-2 border-emerald-500 pl-1 whitespace-nowrap"
            style={{ left: `${((source.t_start/3600 - min)/(max-min))*100}%` }}
          >
            release {(source.t_start/3600).toFixed(1)}→{((source.t_start+source.duration)/3600).toFixed(1)} h
          </span>
        )}
      </div>
    </div>
  );
}
