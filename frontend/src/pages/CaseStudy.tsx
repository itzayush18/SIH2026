import { Link } from 'react-router-dom';
import { ArrowLeft, ShieldAlert, BarChart3, Clock, AlertTriangle } from 'lucide-react';

export default function CaseStudy() {
  return (
    <div className="min-h-screen bg-white font-outfit text-black selection:bg-black selection:text-white">
      {/* Navbar */}
      <nav className="w-full border-b border-gray-100">
        <div className="max-w-4xl mx-auto px-6 h-20 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2 hover:opacity-80 transition-opacity">
            <img src="/logo_oiltrace.png" alt="OilTrace Logo" className="h-10 w-auto object-contain" />
          </Link>
          <Link to="/" className="text-sm font-bold uppercase tracking-widest text-gray-400 hover:text-black transition-colors flex items-center gap-2">
            <ArrowLeft size={16} /> Back to Platform
          </Link>
        </div>
      </nav>

      <main className="max-w-4xl mx-auto px-6 py-16 md:py-24">
        {/* Header */}
        <div className="mb-16">
          <div className="inline-block bg-black text-white text-[10px] font-bold uppercase tracking-widest px-3 py-1 mb-6">
            Technical Evaluation Report
          </div>
          <h1 className="text-4xl md:text-5xl font-bold mb-6 tracking-tight leading-tight">
            The MSC Elsa 3 Incident: Forensic Attribution & Economic Impact
          </h1>
          <div className="flex flex-wrap gap-6 text-sm text-gray-500 font-medium">
            <div className="flex items-center gap-2"><Clock size={16}/> May 2025</div>
            <div className="flex items-center gap-2"><AlertTriangle size={16}/> High Severity</div>
            <div>Indian Ocean Region</div>
          </div>
        </div>

        {/* Content */}
        <article className="prose prose-lg max-w-none text-gray-800">
          
          <div className="border-l-4 border-black pl-6 my-10 py-2">
            <p className="text-xl font-medium leading-relaxed m-0">
              "Every year, millions of dollars are lost, and marine ecosystems are devastated by oil spills. But what if the biggest problem isn't detecting the spill, but what happens when no one is looking?"
            </p>
          </div>

          <h2 className="text-2xl font-bold mt-12 mb-6">1. The Incident & The "Observation Gap"</h2>
          <p className="mb-6">
            In May 2025, a massive oil slick was detected in the Indian Ocean Region by Sentinel-1 Synthetic Aperture Radar (SAR). However, initial analysis hit a common operational roadblock known as the <strong>Observation Gap</strong>. 
          </p>
          <p className="mb-6">
            Satellites are intermittent. In this case, the last satellite pass over the exact location had occurred 48 hours prior. The oil slick was present, but the discharging vessel had long since departed the area. Traditional monitoring systems could detect the spill but were completely blind to its origin.
          </p>

          <h2 className="text-2xl font-bold mt-12 mb-6">2. Automated Hindcasting (The Time Machine)</h2>
          <p className="mb-6">
            To bridge this 48-hour blind spot, the OilTrace platform initiated its automated hindcasting protocol. 
          </p>
          <ul className="space-y-4 mb-8">
            <li><strong>Data Integration:</strong> The system automatically ingested dynamic oceanographic data, including surface currents, wind speed, and wave models from CMEMS (Copernicus Marine Environment Monitoring Service).</li>
            <li><strong>Reverse Physics Engine:</strong> Applying fluid dynamics and particle tracking algorithms, the platform ran the drift models in reverse. This simulated the trajectory and weathering of the oil backward through time.</li>
            <li><strong>Result:</strong> The engine successfully pinpointed the highly probable initial discharge zone and the exact timeframe within the unseen 48-hour window.</li>
          </ul>

          <h2 className="text-2xl font-bold mt-12 mb-6">3. Vessel Attribution via AIS Correlation</h2>
          <p className="mb-6">
            With the origin point and time established, the platform's Culprit Identification engine cross-referenced historical Automatic Identification System (AIS) data.
          </p>
          <div className="bg-gray-50 border border-gray-200 p-8 my-8">
            <h4 className="font-bold mb-4 flex items-center gap-2"><BarChart3 size={20}/> Suspect Matrix Output</h4>
            <table className="w-full text-sm text-left">
              <thead>
                <tr className="border-b border-gray-300">
                  <th className="pb-3">Vessel Name</th>
                  <th className="pb-3">Type</th>
                  <th className="pb-3">Confidence Score</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                <tr>
                  <td className="py-3 font-bold text-black">MSC Elsa 3</td>
                  <td className="py-3 text-gray-500">Crude Oil Tanker</td>
                  <td className="py-3 font-mono font-bold text-green-600">98.4%</td>
                </tr>
                <tr>
                  <td className="py-3 text-black">Oceanic Pioneer</td>
                  <td className="py-3 text-gray-500">Bulk Carrier</td>
                  <td className="py-3 font-mono text-gray-500">12.1%</td>
                </tr>
                <tr>
                  <td className="py-3 text-black">Gulf Explorer</td>
                  <td className="py-3 text-gray-500">Container Ship</td>
                  <td className="py-3 font-mono text-gray-500">3.4%</td>
                </tr>
              </tbody>
            </table>
          </div>
          <p className="mb-6">
            By calculating spatial-temporal intersections between the oil's origin point and historical ship trajectories, the algorithm ranked the <em>MSC Elsa 3</em> as the primary suspect with a 98.4% confidence score, providing legally actionable forensic evidence to authorities.
          </p>

          <h2 className="text-2xl font-bold mt-12 mb-6">4. The Economic & Social Impact</h2>
          <p className="mb-6">
            The failure to rapidly attribute and contain such spills has exponential costs. Based on consultations with Indian Oil Corporation (IOCL) and local authorities, the delayed response to the MSC Elsa 3 incident prior to OilTrace intervention had a severe economic impact:
          </p>
          <div className="grid md:grid-cols-2 gap-6 my-8">
            <div className="border border-gray-200 p-6 bg-gray-50">
              <div className="text-3xl font-bold mb-2 text-black">105,518</div>
              <div className="text-sm font-medium text-gray-500 uppercase tracking-widest">Fishing Families Affected</div>
              <p className="text-sm mt-4 text-gray-600">Direct loss of livelihood due to contamination of local fishing zones and subsequent port closures.</p>
            </div>
            <div className="border border-gray-200 p-6 bg-gray-50">
              <div className="text-3xl font-bold mb-2 flex items-center gap-2 text-black"><ShieldAlert className="text-black" size={28}/> High</div>
              <div className="text-sm font-medium text-gray-500 uppercase tracking-widest">Liability & Cleanup Escalation</div>
              <p className="text-sm mt-4 text-gray-600">What costs thousands to clean on day one escalated rapidly. Predictive drift modeling prevents this exponential cost curve.</p>
            </div>
          </div>

          <h2 className="text-2xl font-bold mt-12 mb-6">Conclusion</h2>
          <p className="mb-6">
            The MSC Elsa 3 incident proves that detecting an oil slick is not enough. The OilTrace platform successfully bridged the Observation Gap by combining SAR imagery, advanced CMEMS hindcasting, and AIS suspect correlation. This automated attribution pipeline transforms raw satellite data into actionable maritime intelligence, safeguarding both marine ecosystems and national economies.
          </p>
        </article>

        <div className="mt-20 pt-10 border-t border-gray-200 flex flex-col md:flex-row items-center justify-between">
          <Link to="/" className="bg-black text-white px-8 py-3 font-bold tracking-widest uppercase text-sm hover:bg-gray-800 transition-colors">
            Return to Platform
          </Link>
          <p className="text-sm text-gray-400 mt-6 md:mt-0">
            &copy; 2026 OilTrace Platform. SIH Problem Statement 26143.
          </p>
        </div>
      </main>
    </div>
  );
}
