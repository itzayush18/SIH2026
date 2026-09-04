import { Link, useNavigate } from 'react-router-dom';
import { 
  Droplet, Ship, Crosshair, Waves, 
  ArrowRight, CheckCircle2, ShieldAlert,
  BarChart4, Satellite, Target
} from 'lucide-react';

export default function Landing() {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-white font-outfit text-black selection:bg-black selection:text-white">
      
      {/* Top Announcement Ribbon */}
      <div className="w-full bg-black text-white text-xs py-2 text-center font-medium tracking-wide">
        Read our Technical Evaluation Report. <Link to="/case-study" className="underline hover:text-gray-300">Read the Case Study &rarr;</Link>
      </div>

      {/* Navigation */}
      <nav className="w-full border-b border-gray-100">
        <div className="max-w-7xl mx-auto px-6 h-20 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <img src="/logo_oiltrace.png" alt="OilTrace Logo" className="h-10 w-auto object-contain" />
          </div>
          <div className="hidden md:flex items-center gap-8 text-sm font-medium">
            <a href="#modules" className="hover:text-gray-500 transition-colors">Product</a>
            <a href="#architecture" className="hover:text-gray-500 transition-colors">Architecture</a>
            <a href="#competitors" className="hover:text-gray-500 transition-colors">Competitors</a>
            <a href="#pricing" className="hover:text-gray-500 transition-colors">Pricing</a>
          </div>
          <div>
            <Link to="/app" className="bg-black hover:bg-gray-800 text-white px-6 py-2.5 text-xs font-bold tracking-widest uppercase rounded-none transition-colors">
              DASHBOARD
            </Link>
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="pt-24 pb-20 px-6">
        <div className="max-w-4xl mx-auto text-center">
          <div className="flex justify-center items-center gap-4 mb-8">
             <div className="flex items-center gap-2 border border-gray-200 px-3 py-1 text-xs font-semibold rounded-none">
               <span className="w-4 h-4 bg-blue-600 flex items-center justify-center text-white font-bold text-[10px]">E</span>
               Enterprise AI Infrastructure
             </div>
             <div className="flex items-center gap-2 border border-green-200 bg-green-50 text-green-700 px-3 py-1 text-xs font-semibold rounded-none">
               <span className="w-2 h-2 rounded-full bg-green-500"></span>
               Trained on Free Satellite Data
             </div>
          </div>
          
          <h1 className="text-5xl md:text-7xl font-bold tracking-tight mb-8 leading-[1.1]">
            The Autonomous Maritime <br/>Intelligence Platform
          </h1>
          
          <p className="text-xl text-gray-500 mb-12 max-w-2xl mx-auto leading-relaxed">
            Create intelligent pipelines that detect spills, dynamically hindcast drift, and execute suspect attribution reliably via automated Sentinel-1 and AIS correlation.
          </p>

          <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
            <Link to="/app" className="w-full sm:w-auto bg-black hover:bg-gray-800 text-white px-8 py-4 text-sm font-bold tracking-widest uppercase rounded-none transition-colors flex items-center justify-center gap-2">
              TRY DEMO DASHBOARD <ArrowRight size={16} />
            </Link>
            <a href="#competitors" className="w-full sm:w-auto border border-black hover:bg-gray-50 text-black px-8 py-4 text-sm font-bold tracking-widest uppercase rounded-none transition-colors text-center">
              VIEW COMPETITOR ANALYSIS
            </a>
          </div>
        </div>
      </section>

      {/* Gradient Divider (from reference image) */}
      <div className="w-full h-48 bg-gradient-to-t from-blue-500 to-white opacity-20"></div>

      {/* Intelligence Modules Section */}
      <section id="modules" className="py-24 px-6 border-t border-gray-100">
        <div className="max-w-7xl mx-auto">
          <div className="mb-16">
            <h2 className="text-3xl font-bold tracking-tight mb-4">4 Major Intelligence Modules</h2>
            <p className="text-gray-500 max-w-2xl">The same underlying infrastructure reused to solve different maritime domain awareness challenges across the Indian Ocean Region.</p>
          </div>

          <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-6">
            {/* Module 1 */}
            <div className="border border-gray-200 p-8 hover:border-black transition-colors rounded-none flex flex-col">
              <div className="w-12 h-12 bg-black text-white flex items-center justify-center mb-6">
                <Droplet size={24} />
              </div>
              <h3 className="text-lg font-bold mb-3">OilTrace Spill Intelligence</h3>
              <p className="text-sm text-gray-600 mb-8 flex-grow">Detect → trace → attribute oil spills. Fully automated pipeline with no human-in-the-loop required.</p>
              <div className="pt-4 border-t border-gray-100 mb-6">
                 <span className="text-[10px] font-bold text-gray-400 uppercase tracking-widest block mb-1">Customers</span>
                 <p className="text-xs font-medium">Coast Guard, INCOIS, MoEFCC</p>
              </div>
              <Link to="/app" className="text-sm font-bold flex items-center gap-1 hover:underline">Access Dashboard <ArrowRight size={14} /></Link>
            </div>

            {/* Module 2 */}
            <div className="border border-gray-200 p-8 hover:border-black transition-colors rounded-none flex flex-col">
              <div className="w-12 h-12 bg-gray-100 text-black flex items-center justify-center mb-6">
                <Ship size={24} />
              </div>
              <h3 className="text-lg font-bold mb-3">Vessel Intelligence</h3>
              <p className="text-sm text-gray-600 mb-8 flex-grow">Detect ships, track behaviour, and identify anomalies like dark vessels disabling AIS.</p>
              <div className="pt-4 border-t border-gray-100 mb-6">
                 <span className="text-[10px] font-bold text-gray-400 uppercase tracking-widest block mb-1">Customers</span>
                 <p className="text-xs font-medium">Coast Guard, Navy, Ports</p>
              </div>
              <Link to="/vessel-intelligence" className="text-sm font-bold flex items-center gap-1 text-gray-400 hover:text-black transition-colors text-left">View Architecture <ArrowRight size={14} /></Link>
            </div>

            {/* Module 3 */}
            <div className="border border-gray-200 p-8 hover:border-black transition-colors rounded-none flex flex-col">
              <div className="w-12 h-12 bg-gray-100 text-black flex items-center justify-center mb-6">
                <Crosshair size={24} />
              </div>
              <h3 className="text-lg font-bold mb-3">Fisheries & Border</h3>
              <p className="text-sm text-gray-600 mb-8 flex-grow">Detect fishing activity, zone violations, and vessel conflicts near sensitive borders.</p>
              <div className="pt-4 border-t border-gray-100 mb-6">
                 <span className="text-[10px] font-bold text-gray-400 uppercase tracking-widest block mb-1">Customers</span>
                 <p className="text-xs font-medium">Fisheries Dept, Coast Guard</p>
              </div>
              <Link to="/fisheries-intelligence" className="text-sm font-bold flex items-center gap-1 text-gray-400 hover:text-black transition-colors text-left">View Architecture <ArrowRight size={14} /></Link>
            </div>

            {/* Module 4 */}
            <div className="border border-gray-200 p-8 hover:border-black transition-colors rounded-none flex flex-col">
              <div className="w-12 h-12 bg-gray-100 text-black flex items-center justify-center mb-6">
                <Waves size={24} />
              </div>
              <h3 className="text-lg font-bold mb-3">Marine Pollution</h3>
              <p className="text-sm text-gray-600 mb-8 flex-grow">Detect and monitor other environmental hazards beyond oil across the EEZ.</p>
              <div className="pt-4 border-t border-gray-100 mb-6">
                 <span className="text-[10px] font-bold text-gray-400 uppercase tracking-widest block mb-1">Customers</span>
                 <p className="text-xs font-medium">Govt, Ports, Env Agencies</p>
              </div>
              <Link to="/marine-pollution" className="text-sm font-bold flex items-center gap-1 text-gray-400 hover:text-black transition-colors text-left">View Architecture <ArrowRight size={14} /></Link>
            </div>
          </div>
        </div>
      </section>

      {/* Competitor Analysis Section */}
      <section id="competitors" className="py-24 px-6 bg-gray-50 border-t border-gray-200">
        <div className="max-w-7xl mx-auto">
          <div className="mb-16">
            <h2 className="text-3xl font-bold tracking-tight mb-4">Competitor Landscape</h2>
            <p className="text-gray-600 max-w-3xl leading-relaxed">
              Why not just use existing tools? Because none offer an end-to-end automated pipeline (detect &rarr; characterise &rarr; hindcast &rarr; attribute) tuned for the Indian EEZ and deployable on-premise for a security agency.
            </p>
          </div>

          {/* Global Incumbents Table */}
          <div className="mb-16">
            <h3 className="text-xl font-bold mb-6 flex items-center gap-2"><Satellite size={20} className="text-blue-600"/> Full-Service Operators (Global)</h3>
            <div className="overflow-x-auto border border-gray-200 bg-white rounded-none">
              <table className="w-full text-left text-sm">
                <thead className="bg-gray-100 text-xs uppercase tracking-wider text-gray-500 border-b border-gray-200">
                  <tr>
                    <th className="p-4 font-bold">Competitor</th>
                    <th className="p-4 font-bold">What They Offer</th>
                    <th className="p-4 font-bold">Pricing Model</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  <tr className="hover:bg-gray-50">
                    <td className="p-4 font-bold">EMSA CleanSeaNet</td>
                    <td className="p-4 text-gray-600">Pan-European SAR detection, vessel ID. Uses Sentinel-1 (same as OilTrace).</td>
                    <td className="p-4"><span className="font-mono bg-gray-100 px-2 py-1">≈ ₹36 Cr/yr</span> (Funded via EU budget)</td>
                  </tr>
                  <tr className="hover:bg-gray-50">
                    <td className="p-4 font-bold">KSAT / e-GEOS / CLS</td>
                    <td className="p-4 text-gray-600">Major contractors for CleanSeaNet providing NRT detection & AIS replay.</td>
                    <td className="p-4">Quote-based / Custom Contracts</td>
                  </tr>
                  <tr className="hover:bg-gray-50">
                    <td className="p-4 font-bold">Windward (Maritime AI)</td>
                    <td className="p-4 text-gray-600">Platform fusing AIS, SAR, and RF for dark-vessel and sanctions detection.</td>
                    <td className="p-4"><span className="font-mono bg-gray-100 px-2 py-1">≈ ₹2.5 Cr/user</span> (Enterprise AWS Listing)</td>
                  </tr>
                  <tr className="bg-black text-white">
                    <td className="p-4 font-bold flex items-center gap-2"><img src="/logo_oiltrace.png" alt="OilTrace" className="h-5 w-auto object-contain"/></td>
                    <td className="p-4 text-gray-300">Fully automated attribution, sovereign on-prem deployment, explainable ranking.</td>
                    <td className="p-4"><span className="font-mono bg-gray-800 px-2 py-1">~₹2 Cr/yr</span> (National Govt Licence)</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          {/* Domestic & Free Options */}
          <div className="grid md:grid-cols-2 gap-8">
            <div>
               <h3 className="text-xl font-bold mb-6 flex items-center gap-2"><Target size={20} className="text-green-600"/> Indian Space Players</h3>
               <div className="border border-gray-200 bg-white rounded-none p-6">
                 <ul className="space-y-6">
                   <li className="border-b border-gray-100 pb-4">
                     <div className="font-bold mb-1">PierSight Space</div>
                     <p className="text-sm text-gray-600 mb-2">Building SAR+AIS constellation (Varuna). Explicitly targeting EEZ surveillance and spills.</p>
                     <span className="text-xs bg-gray-100 px-2 py-1 font-mono">Hardware Focus</span>
                   </li>
                   <li className="border-b border-gray-100 pb-4">
                     <div className="font-bold mb-1">GalaxEye Space</div>
                     <p className="text-sm text-gray-600 mb-2">"Drishti" SAR + optical fusion constellation for maritime analytics.</p>
                     <span className="text-xs bg-gray-100 px-2 py-1 font-mono">Contract Stage</span>
                   </li>
                   <li>
                     <div className="font-bold mb-1">ISRO NRSC / INCOIS</div>
                     <p className="text-sm text-gray-600 mb-2">Government advisories & trajectory modelling using RISAT/Sentinel data.</p>
                     <span className="text-xs bg-gray-100 px-2 py-1 font-mono">Free (Govt only)</span>
                   </li>
                 </ul>
               </div>
            </div>

            <div>
               <h3 className="text-xl font-bold mb-6 flex items-center gap-2"><ShieldAlert size={20} className="text-orange-600"/> Free / Open-Source (The ₹0 Comp)</h3>
               <div className="border border-gray-200 bg-white rounded-none p-6">
                 <ul className="space-y-6">
                   <li className="border-b border-gray-100 pb-4">
                     <div className="font-bold mb-1">SkyTruth Cerulean</div>
                     <p className="text-sm text-gray-600 mb-2">AI on free Sentinel-1 to detect pollution. Closest free analogue.</p>
                     <span className="text-xs bg-gray-100 px-2 py-1 font-mono text-orange-700">Lacks Automated Suspect Ranking</span>
                   </li>
                   <li className="border-b border-gray-100 pb-4">
                     <div className="font-bold mb-1">NOAA GNOME Suite</div>
                     <p className="text-sm text-gray-600 mb-2">Trajectory model with back-tracking used by US spill response.</p>
                     <span className="text-xs bg-gray-100 px-2 py-1 font-mono text-orange-700">Physics Engine Only</span>
                   </li>
                   <li>
                     <div className="font-bold mb-1">OpenDrift "OpenOil"</div>
                     <p className="text-sm text-gray-600 mb-2">Python trajectory model for spill contingency and backtracking.</p>
                     <span className="text-xs bg-gray-100 px-2 py-1 font-mono text-orange-700">Requires Developer Integration</span>
                   </li>
                 </ul>
               </div>
            </div>
          </div>

        </div>
      </section>

      {/* Architecture */}
      <section id="architecture" className="py-24 px-6 bg-white border-t border-gray-100">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-12">
            <h2 className="text-3xl font-bold tracking-tight mb-4">System Architecture</h2>
            <p className="text-gray-500 max-w-2xl mx-auto">
              A high-level overview of our automated detection, hindcasting, and attribution pipeline.
            </p>
          </div>
          <div className="border border-gray-200 shadow-sm p-4 bg-[#f8fafc]">
            <img src="/architecture.svg" alt="OilTrace System Architecture" className="w-full h-auto" />
          </div>
        </div>
      </section>

      {/* Pricing Section */}
      <section id="pricing" className="py-24 px-6">
        <div className="max-w-7xl mx-auto">
          
          <div className="bg-black text-white p-8 md:p-12 rounded-none mb-16 flex flex-col md:flex-row items-center justify-between">
            <div className="mb-6 md:mb-0 max-w-xl">
              <h3 className="text-2xl font-bold mb-2">The 95% COGS Advantage</h3>
              <p className="text-gray-400 text-sm leading-relaxed">
                We run entirely on free Sentinel-1 SAR and CMEMS metocean data. Using CPU-only Docker deployment, our infrastructure costs are &lt;₹12 Lakhs/yr. We deliver CleanSeaNet-grade monitoring at ~5% of incumbent cost, retaining 80% gross margins.
              </p>
            </div>
            <div className="text-right">
              <div className="text-4xl font-bold font-mono">₹0</div>
              <div className="text-sm text-gray-400 uppercase tracking-widest mt-1">Satellite Data Cost</div>
            </div>
          </div>

          <div className="text-center mb-12">
            <h2 className="text-3xl font-bold tracking-tight mb-4">Pricing & Monetisation</h2>
            <p className="text-gray-500">From sovereign defence contracts to single-incident forensic evidence packs.</p>
          </div>

          <div className="grid md:grid-cols-3 gap-6">
            {/* Tier 1 */}
            <div className="border-2 border-black p-8 relative rounded-none flex flex-col">
              <div className="absolute top-0 right-0 bg-black text-white text-[10px] font-bold uppercase tracking-widest px-3 py-1">
                Anchor Contract
              </div>
              <h4 className="text-xl font-bold mb-2">Govt & Defence</h4>
              <p className="text-sm text-gray-600 mb-6 flex-grow">NTRO, Coast Guard, State Pollution Boards.</p>
              <div className="mb-8">
                <span className="text-3xl font-bold tracking-tight">₹1.25 Cr - 3.3 Cr</span>
                <span className="text-gray-500 font-medium">/yr</span>
              </div>
              <ul className="space-y-3 text-sm text-gray-800 mb-8 font-medium">
                <li className="flex items-start gap-2"><CheckCircle2 size={18} className="shrink-0 text-black"/> Sovereign on-prem deployment</li>
                <li className="flex items-start gap-2"><CheckCircle2 size={18} className="shrink-0 text-black"/> Unlimited EEZ monitoring</li>
                <li className="flex items-start gap-2"><CheckCircle2 size={18} className="shrink-0 text-black"/> Classifier tuned to Indian waters</li>
              </ul>
              <button className="w-full bg-black text-white font-bold py-3 uppercase tracking-wider text-xs">Contact Sales</button>
            </div>

            {/* Tier 2 */}
            <div className="border border-gray-200 p-8 rounded-none flex flex-col">
              <h4 className="text-xl font-bold mb-2">Offshore Operators</h4>
              <p className="text-sm text-gray-600 mb-6 flex-grow">ONGC, RIL, Cairn, Offshore Wind.</p>
              <div className="mb-8">
                <span className="text-3xl font-bold tracking-tight">₹25L - 83L</span>
                <span className="text-gray-500 font-medium">/yr</span>
              </div>
              <ul className="space-y-3 text-sm text-gray-600 mb-8">
                <li className="flex items-start gap-2"><CheckCircle2 size={18} className="shrink-0 text-gray-400"/> Asset-cluster monitoring</li>
                <li className="flex items-start gap-2"><CheckCircle2 size={18} className="shrink-0 text-gray-400"/> Automated patrol recommendations</li>
                <li className="flex items-start gap-2"><CheckCircle2 size={18} className="shrink-0 text-gray-400"/> +₹2 Lakhs forensic pack per incident</li>
              </ul>
              <button className="w-full border border-black hover:bg-gray-50 text-black font-bold py-3 uppercase tracking-wider text-xs">Request Demo</button>
            </div>

            {/* Tier 3 */}
            <div className="border border-gray-200 p-8 rounded-none flex flex-col">
              <h4 className="text-xl font-bold mb-2">Self-Serve & API</h4>
              <p className="text-sm text-gray-600 mb-6 flex-grow">Ports, Insurers, NGOs, Academic Research.</p>
              <div className="mb-8">
                <span className="text-3xl font-bold tracking-tight">₹8,000</span>
                <span className="text-gray-500 font-medium">/mo</span>
              </div>
              <ul className="space-y-3 text-sm text-gray-600 mb-8">
                <li className="flex items-start gap-2"><CheckCircle2 size={18} className="shrink-0 text-gray-400"/> API Access & Credit bundles</li>
                <li className="flex items-start gap-2"><CheckCircle2 size={18} className="shrink-0 text-gray-400"/> Bring-your-own-scene analytics</li>
                <li className="flex items-start gap-2"><CheckCircle2 size={18} className="shrink-0 text-gray-400"/> Free tier for verified NGOs</li>
              </ul>
              <Link to="/api-docs" className="w-full inline-block text-center border border-gray-300 hover:border-black text-gray-500 hover:text-black font-bold py-3 uppercase tracking-wider text-xs transition-colors">View API Docs</Link>
            </div>
          </div>

        </div>
      </section>

      {/* Footer */}
      <footer className="bg-black text-white pt-20 pb-10 px-6 mt-12">
        <div className="max-w-7xl mx-auto grid grid-cols-2 md:grid-cols-4 gap-10 mb-16">
          <div className="col-span-2 md:col-span-1">
             <div className="flex items-center gap-2 mb-6">
                <img src="/logo_oiltrace.png" alt="OilTrace Logo" className="h-8 w-auto object-contain" />
             </div>
             <p className="text-gray-500 text-sm leading-relaxed mb-6">
               Automated detection, hindcasting, and vessel attribution for the Indian Ocean Region. Built for SIH 26143.
             </p>
          </div>
          
          <div>
            <h4 className="font-bold text-sm uppercase tracking-widest mb-6 text-gray-300">Modules</h4>
            <ul className="space-y-4 text-sm text-gray-500">
              <li><a href="#" className="hover:text-white transition-colors">Spill Intelligence</a></li>
              <li><a href="#" className="hover:text-white transition-colors">Vessel Intelligence</a></li>
              <li><a href="#" className="hover:text-white transition-colors">Fisheries & Border</a></li>
              <li><a href="#" className="hover:text-white transition-colors">Marine Pollution</a></li>
            </ul>
          </div>
          
          <div>
            <h4 className="font-bold text-sm uppercase tracking-widest mb-6 text-gray-300">Company</h4>
            <ul className="space-y-4 text-sm text-gray-500">
              <li><Link to="/case-study" className="hover:text-white transition-colors">Case Studies</Link></li>
              <li><a href="#competitors" className="hover:text-white transition-colors">Market Analysis</a></li>
              <li><a href="#pricing" className="hover:text-white transition-colors">Pricing</a></li>
              <li><Link to="/api-docs" className="hover:text-white transition-colors">API Documentation</Link></li>
            </ul>
          </div>

          <div>
            <h4 className="font-bold text-sm uppercase tracking-widest mb-6 text-gray-300">Legal</h4>
            <ul className="space-y-4 text-sm text-gray-500">
              <li><a href="#" className="hover:text-white transition-colors">Privacy Policy</a></li>
              <li><a href="#" className="hover:text-white transition-colors">Terms of Service</a></li>
              <li><a href="#" className="hover:text-white transition-colors">Data Provenance</a></li>
            </ul>
          </div>
        </div>
        
        <div className="max-w-7xl mx-auto border-t border-gray-800 pt-8 flex flex-col md:flex-row items-center justify-between text-xs text-gray-600">
          <p>&copy; 2026 OilTrace Platform. All rights reserved.</p>
          <div className="flex gap-4 mt-4 md:mt-0">
            <span>Powered by Sentinel-1</span>
            <span>AIS correlation engine</span>
          </div>
        </div>
      </footer>

    </div>
  );
}
