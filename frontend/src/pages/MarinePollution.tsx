import { Link } from 'react-router-dom';

export default function MarinePollution() {
  return (
    <div className="min-h-screen bg-white font-outfit text-slate-900 flex flex-col">
      <div className="max-w-6xl mx-auto w-full px-6 py-12 flex-grow">
        <div className="mb-8 flex items-center justify-between border-b-2 border-slate-900 pb-6">
          <div>
            <h1 className="text-4xl font-bold tracking-tight mb-2">Marine Pollution Intelligence</h1>
            <p className="text-slate-500">Detect and monitor other environmental hazards</p>
          </div>
          <Link to="/" className="text-slate-900 hover:text-white font-semibold border-2 border-slate-900 px-6 py-2 hover:bg-slate-900 transition-colors uppercase tracking-wider text-sm">
            &larr; Back to Home
          </Link>
        </div>

        <div className="prose max-w-none mb-12">
          <p className="text-lg text-slate-700 leading-relaxed max-w-4xl">
            Beyond oil spills, the marine environment is threatened by plastics, debris, and harmful algal blooms. This intelligence module taps into multispectral and hyperspectral satellite imagery to detect these hazards using advanced indexing (FDI/NDVI/Chlorophyll-a). Crucially, it links directly into OilTrace's core Hindcast Drift Model to predict where the pollution will spread or wash ashore.
          </p>
        </div>

        <div className="border-2 border-slate-900 p-6 bg-[#f8fafc] mb-16 shadow-[8px_8px_0px_0px_rgba(15,23,42,1)]">
          <h2 className="text-2xl font-bold mb-6 text-center border-b-2 border-slate-200 pb-4">Integration Architecture</h2>
          <img src="/arch_pollution.svg" alt="Marine Pollution Intelligence Architecture" className="w-full h-auto" />
        </div>
        
        <div className="border-2 border-slate-900 p-8 flex flex-col items-center justify-center text-center max-w-2xl mx-auto bg-slate-50">
          <svg className="w-12 h-12 text-slate-900 mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="square" strokeLinejoin="miter" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
            <path strokeLinecap="square" strokeLinejoin="miter" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
          </svg>
          <h3 className="text-xl font-bold mb-2 uppercase tracking-wide">Module Under Development</h3>
          <p className="text-slate-600">
            This module is actively being built and integrated into the OilTrace ecosystem. Stay tuned for upcoming beta releases.
          </p>
        </div>
      </div>
    </div>
  );
}
