import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Landing from './pages/Landing';
import Dashboard from './pages/Dashboard';
import ComingSoon from './pages/ComingSoon';
import CaseStudy from './pages/CaseStudy';
import ApiDocs from './pages/ApiDocs';
import VesselIntelligence from './pages/VesselIntelligence';
import FisheriesIntelligence from './pages/FisheriesIntelligence';
import MarinePollution from './pages/MarinePollution';

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/app" element={<Dashboard />} />
        <Route path="/coming-soon" element={<ComingSoon />} />
        <Route path="/case-study" element={<CaseStudy />} />
        <Route path="/api-docs" element={<ApiDocs />} />
        <Route path="/vessel-intelligence" element={<VesselIntelligence />} />
        <Route path="/fisheries-intelligence" element={<FisheriesIntelligence />} />
        <Route path="/marine-pollution" element={<MarinePollution />} />
      </Routes>
    </BrowserRouter>
  );
}
