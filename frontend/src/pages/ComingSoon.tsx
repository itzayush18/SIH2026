import { Link, useLocation } from 'react-router-dom';

export default function ComingSoon() {
  const location = useLocation();
  const moduleName = location.state?.title || "Module";

  return (
    <div className="min-h-screen bg-gradient-to-b from-sky-50 to-white font-outfit text-slate-900 flex flex-col items-center justify-center p-6">
      <div className="max-w-md w-full bg-white border-2 border-slate-200 p-8 shadow-card text-center rounded-none relative overflow-hidden">
        <div className="absolute top-0 left-0 w-full h-2 bg-brand-500"></div>
        <div className="w-16 h-16 bg-sky-100 text-brand-600 flex items-center justify-center mx-auto mb-6 rounded-none">
          <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="square" strokeLinejoin="miter" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
            <path strokeLinecap="square" strokeLinejoin="miter" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
          </svg>
        </div>
        <h1 className="text-2xl font-bold mb-3">{moduleName}</h1>
        <p className="text-slate-600 mb-8">This intelligence module is currently under development. Stay tuned for updates.</p>
        <Link to="/" className="inline-block bg-brand-600 hover:bg-brand-700 text-white px-6 py-3 font-semibold shadow-soft transition-all rounded-none uppercase tracking-wider">
          Return Home
        </Link>
      </div>
    </div>
  );
}
