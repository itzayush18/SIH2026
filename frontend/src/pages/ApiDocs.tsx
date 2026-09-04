import { Link } from 'react-router-dom';
import { ArrowLeft, Terminal, Server, Key, Shield } from 'lucide-react';
import React from 'react';

export default function ApiDocs() {
  return (
    <div className="min-h-screen bg-white font-outfit text-black flex flex-col md:flex-row">
      {/* Sidebar */}
      <aside className="w-full md:w-64 bg-gray-50 border-r border-gray-200 p-6 flex-shrink-0 md:h-screen md:sticky md:top-0 md:overflow-y-auto">
        <Link to="/" className="flex items-center gap-2 hover:opacity-80 transition-opacity mb-10">
          <img src="/logo_oiltrace.png" alt="OilTrace Logo" className="h-8 w-auto object-contain" />
        </Link>

        <div className="mb-8">
          <h4 className="text-xs font-bold uppercase tracking-widest text-gray-400 mb-4">Getting Started</h4>
          <ul className="space-y-3 text-sm font-medium text-gray-700">
            <li><a href="#introduction" className="hover:text-black">Introduction</a></li>
            <li><a href="#authentication" className="hover:text-black">Authentication</a></li>
            <li><a href="#errors" className="hover:text-black">Errors</a></li>
          </ul>
        </div>

        <div>
          <h4 className="text-xs font-bold uppercase tracking-widest text-gray-400 mb-4">API Reference</h4>
          <ul className="space-y-3 text-sm font-medium text-gray-700">
            <li><a href="#list-incidents" className="hover:text-black">List Incidents</a></li>
            <li><a href="#get-incident" className="hover:text-black">Get Incident Details</a></li>
            <li><a href="#run-hindcast" className="hover:text-black">Run Hindcast Drift</a></li>
            <li><a href="#attribute-vessels" className="hover:text-black">Attribute Vessels</a></li>
          </ul>
        </div>

        <div className="mt-12 pt-6 border-t border-gray-200">
          <Link to="/" className="text-xs font-bold uppercase tracking-widest text-gray-400 hover:text-black transition-colors flex items-center gap-2">
            <ArrowLeft size={14} /> Back to Platform
          </Link>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 p-8 md:p-16 max-w-5xl">
        <div className="mb-16" id="introduction">
          <h1 className="text-4xl font-bold mb-4 tracking-tight">API Reference</h1>
          <p className="text-gray-600 text-lg leading-relaxed mb-6">
            The OilTrace API is organized around REST. Our API has predictable resource-oriented URLs, accepts form-encoded request bodies, returns JSON-encoded responses, and uses standard HTTP response codes, authentication, and verbs.
          </p>
          <div className="bg-gray-100 p-4 font-mono text-sm border border-gray-200 flex items-center gap-3">
            <Server size={18} className="text-gray-500" />
            <span>https://api.oiltrace.io/v1</span>
          </div>
        </div>

        <div className="mb-16 border-t border-gray-200 pt-10" id="authentication">
          <h2 className="text-2xl font-bold mb-4">Authentication</h2>
          <p className="text-gray-600 mb-6">
            The OilTrace API uses API keys to authenticate requests. You can view and manage your API keys in the OilTrace Dashboard.
          </p>
          <p className="text-gray-600 mb-6">
            Authentication to the API is performed via HTTP Bearer Auth. Provide your API key as the bearer token value.
          </p>
          <div className="bg-black text-gray-300 p-6 rounded-none font-mono text-sm overflow-x-auto shadow-inner">
            <div className="flex items-center gap-2 mb-2 text-gray-500"><Terminal size={14}/> <span>cURL Example</span></div>
            <code>
              curl https://api.oiltrace.io/v1/incidents \<br/>
              &nbsp;&nbsp;-H "Authorization: Bearer ot_live_xxxxxxxxxxxxxxxxx"
            </code>
          </div>
        </div>

        {/* Endpoint 1 */}
        <div className="mb-16 border-t border-gray-200 pt-10" id="list-incidents">
          <div className="flex flex-col xl:flex-row gap-10">
            <div className="flex-1">
              <h2 className="text-2xl font-bold mb-2">List all incidents</h2>
              <p className="text-gray-600 mb-6">Returns a list of your organization's detected oil spill incidents. The incidents are returned sorted by detection date, with the most recent incidents appearing first.</p>
              
              <h4 className="font-bold text-sm uppercase tracking-widest text-gray-400 mb-4">HTTP Request</h4>
              <div className="bg-gray-50 px-4 py-2 border border-gray-200 font-mono text-sm mb-6 inline-block">
                <span className="text-green-600 font-bold mr-2">GET</span> /v1/incidents
              </div>

              <h4 className="font-bold text-sm uppercase tracking-widest text-gray-400 mb-4">Query Parameters</h4>
              <div className="border border-gray-200 text-sm">
                <div className="grid grid-cols-3 border-b border-gray-200 p-3 bg-gray-50 font-bold">
                  <div>Parameter</div>
                  <div className="col-span-2">Description</div>
                </div>
                <div className="grid grid-cols-3 border-b border-gray-200 p-3">
                  <div className="font-mono">limit</div>
                  <div className="col-span-2 text-gray-600">A limit on the number of objects to be returned. Limit can range between 1 and 100, and the default is 10.</div>
                </div>
                <div className="grid grid-cols-3 p-3">
                  <div className="font-mono">severity</div>
                  <div className="col-span-2 text-gray-600">Only return incidents with the specified severity (e.g., <code className="bg-gray-100 px-1">high</code>).</div>
                </div>
              </div>
            </div>

            <div className="flex-1 bg-gray-900 text-gray-300 p-6 shadow-inner font-mono text-xs overflow-x-auto">
              <div className="text-gray-500 mb-4 uppercase tracking-widest text-[10px] font-bold">Response JSON</div>
              <pre>
{`{
  "object": "list",
  "url": "/v1/incidents",
  "has_more": false,
  "data": [
    {
      "id": "inc_89f3a9",
      "object": "incident",
      "status": "investigating",
      "detected_at": 1746093600,
      "coordinates": {
        "lat": 15.341,
        "lng": 71.902
      },
      "estimated_volume_barrels": 4500,
      "severity": "high"
    }
  ]
}`}
              </pre>
            </div>
          </div>
        </div>

        {/* Endpoint 2 */}
        <div className="mb-16 border-t border-gray-200 pt-10" id="attribute-vessels">
          <div className="flex flex-col xl:flex-row gap-10">
            <div className="flex-1">
              <h2 className="text-2xl font-bold mb-2">Attribute Vessels</h2>
              <p className="text-gray-600 mb-6">Cross-references the origin point of a spill against historical AIS data to return a ranked suspect matrix.</p>
              
              <h4 className="font-bold text-sm uppercase tracking-widest text-gray-400 mb-4">HTTP Request</h4>
              <div className="bg-gray-50 px-4 py-2 border border-gray-200 font-mono text-sm mb-6 inline-block">
                <span className="text-green-600 font-bold mr-2">GET</span> /v1/incidents/&#123;id&#125;/attribution
              </div>

              <div className="mt-8 bg-blue-50 border-l-4 border-blue-500 p-4">
                <div className="flex gap-2">
                  <Shield size={20} className="text-blue-600 shrink-0" />
                  <p className="text-sm text-blue-900">
                    <strong>Premium Endpoint:</strong> This endpoint requires a Govt & Defence or Offshore Operator tier API key. Self-serve keys will receive a 403 Forbidden.
                  </p>
                </div>
              </div>
            </div>

            <div className="flex-1 bg-gray-900 text-gray-300 p-6 shadow-inner font-mono text-xs overflow-x-auto">
              <div className="text-gray-500 mb-4 uppercase tracking-widest text-[10px] font-bold">Response JSON</div>
              <pre>
{`{
  "object": "attribution_report",
  "incident_id": "inc_89f3a9",
  "generated_at": 1746101200,
  "suspects": [
    {
      "mmsi": "352898000",
      "vessel_name": "MSC ELSA 3",
      "vessel_type": "Crude Oil Tanker",
      "confidence_score": 0.984,
      "intersection_distance_nm": 0.4,
      "is_dark_vessel": false
    },
    {
      "mmsi": "419000123",
      "vessel_name": "OCEANIC PIONEER",
      "vessel_type": "Bulk Carrier",
      "confidence_score": 0.121,
      "intersection_distance_nm": 4.2,
      "is_dark_vessel": false
    }
  ]
}`}
              </pre>
            </div>
          </div>
        </div>

      </main>
    </div>
  );
}
