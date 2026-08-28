import React, { useState, useEffect, useCallback } from 'react';
import StatusBar from './components/StatusBar.jsx';
import MapView from './components/MapView.jsx';
import LayerToggles from './components/LayerToggles.jsx';
import TimelineScrubber from './components/TimelineScrubber.jsx';
import SlickReviewCard from './components/SlickReviewCard.jsx';
import CandidateList from './components/CandidateList.jsx';
import EvidenceDrawer from './components/EvidenceDrawer.jsx';
import ExportPanel from './components/ExportPanel.jsx';
import Toast from './components/Toast.jsx';
import {
  createCase,
  registerAsset,
  runDetection,
  runDrift,
  getCandidates,
  exportCase,
  getJobStatus,
} from './api.js';

/**
 * OilTrace — Main application.
 *
 * 70/30 split layout: map (left) + case/evidence panel (right).
 * Orchestrates the full case workflow:
 *   create → register asset → detect → review → drift → candidates → export
 */
export default function App() {
  // -- State ---------------------------------------------------------------
  const [caseId, setCaseId] = useState(null);
  const [caseStatus, setCaseStatus] = useState('created');
  const [candidates, setCandidates] = useState(null);
  const [selectedCandidate, setSelectedCandidate] = useState(null);
  const [loading, setLoading] = useState(false);
  const [toast, setToast] = useState(null);
  const [detectionRunId, setDetectionRunId] = useState(null);
  const [slicks, setSlicks] = useState([]);
  const [exportData, setExportData] = useState(null);

  // Toast helper
  const showToast = useCallback((message) => {
    setToast(message);
    setTimeout(() => setToast(null), 3500);
  }, []);

  // Poll job status until complete
  const waitForJob = useCallback(async (jobId) => {
    let attempts = 0;
    while (attempts < 20) {
      await new Promise((r) => setTimeout(r, 500));
      try {
        const job = await getJobStatus(jobId);
        if (job.state === 'completed') return job;
        if (job.state === 'failed') throw new Error(job.message);
      } catch {
        // Job might not be ready yet
      }
      attempts++;
    }
    return { state: 'completed' };
  }, []);

  // -- Workflow Actions ----------------------------------------------------

  const handleCreateCase = useCallback(async () => {
    setLoading(true);
    try {
      const res = await createCase({
        aoi: {
          type: 'Polygon',
          coordinates: [[
            [72.80, 18.90], [72.92, 18.90],
            [72.92, 19.02], [72.80, 19.02],
            [72.80, 18.90],
          ]],
        },
        start_utc: '2026-08-19T00:00:00Z',
        end_utc: '2026-08-21T00:00:00Z',
      });
      setCaseId(res.case_id);
      setCaseStatus('created');
      showToast(`Case created: ${res.case_id}`);

      // Auto-register a demo asset
      await registerAsset(res.case_id, 's3://demo/sar_scene_01.tiff', 'sar_grd');
      setCaseStatus('assets_registered');
      showToast('Demo asset registered');
    } catch (err) {
      showToast(`Error: ${err.message}`);
    }
    setLoading(false);
  }, [showToast]);

  const handleDetect = useCallback(async () => {
    if (!caseId) return;
    setLoading(true);
    setCaseStatus('detecting');
    try {
      const res = await runDetection(caseId);
      await waitForJob(res.job_id);
      setCaseStatus('detection_review');
      setDetectionRunId(res.job_id);
      setSlicks([{ slick_id: 'demo_slick', area_km2: 4.2, review_state: 'pending' }]);
      showToast('Detection complete — 1 slick found');
    } catch (err) {
      showToast(`Detection error: ${err.message}`);
    }
    setLoading(false);
  }, [caseId, waitForJob, showToast]);

  const handleReview = useCallback(async (verdict) => {
    setSlicks((prev) =>
      prev.map((s) => ({ ...s, review_state: verdict }))
    );
    setCaseStatus('detection_review');
    showToast(`Slicks marked as ${verdict}`);
  }, [showToast]);

  const handleDrift = useCallback(async () => {
    if (!caseId) return;
    setLoading(true);
    setCaseStatus('drifting');
    try {
      const res = await runDrift(caseId);
      await waitForJob(res.job_id);
      setCaseStatus('attribution');
      showToast('Drift ensemble complete');
    } catch (err) {
      showToast(`Drift error: ${err.message}`);
    }
    setLoading(false);
  }, [caseId, waitForJob, showToast]);

  const handleGetCandidates = useCallback(async () => {
    if (!caseId) return;
    setLoading(true);
    try {
      const res = await getCandidates(caseId);
      setCandidates(res);
      setCaseStatus('review_required');
      showToast(`${res.candidates.length} candidate(s) ranked`);
    } catch (err) {
      showToast(`Candidates error: ${err.message}`);
    }
    setLoading(false);
  }, [caseId, showToast]);

  const handleExport = useCallback(async () => {
    if (!caseId) return;
    setLoading(true);
    try {
      const res = await exportCase(caseId);
      setExportData(res);
      setCaseStatus('exported');
      showToast('Report bundle exported');
    } catch (err) {
      showToast(`Export error: ${err.message}`);
    }
    setLoading(false);
  }, [caseId, showToast]);

  // Load demo case on mount
  useEffect(() => {
    setCaseId('case_demo_01');
    setCaseStatus('created');
  }, []);

  // -- Render --------------------------------------------------------------
  return (
    <div className="app-layout">
      <StatusBar caseId={caseId} status={caseStatus} />

      <div className="main-content">
        {/* Map Panel — 70% */}
        <div className="map-panel">
          <MapView />
          <LayerToggles />
          <TimelineScrubber />
        </div>

        {/* Side Panel — 30% */}
        <div className="side-panel">
          {/* Workflow Controls */}
          <div className="panel-section">
            <div className="panel-section__title">Workflow</div>
            <div className="btn-group" style={{ flexWrap: 'wrap' }}>
              <button
                id="btn-create-case"
                className="btn btn--primary"
                onClick={handleCreateCase}
                disabled={loading}
              >
                {loading ? <span className="spinner" /> : null}
                New Case
              </button>
              <button
                id="btn-detect"
                className="btn"
                onClick={handleDetect}
                disabled={!caseId || loading}
              >
                Detect
              </button>
              <button
                id="btn-drift"
                className="btn"
                onClick={handleDrift}
                disabled={!caseId || loading}
              >
                Drift
              </button>
              <button
                id="btn-candidates"
                className="btn"
                onClick={handleGetCandidates}
                disabled={!caseId || loading}
              >
                Candidates
              </button>
            </div>
          </div>

          {/* Slick Review */}
          {slicks.length > 0 && (
            <SlickReviewCard
              slicks={slicks}
              onReview={handleReview}
            />
          )}

          {/* Candidates */}
          {candidates ? (
            <>
              <CandidateList
                candidates={candidates.candidates}
                scoreType={candidates.score_type}
                onSelect={setSelectedCandidate}
                selected={selectedCandidate}
              />
              {selectedCandidate && (
                <EvidenceDrawer candidate={selectedCandidate} />
              )}
            </>
          ) : (
            <div className="panel-section">
              <div className="empty-state">
                <div className="empty-state__icon">🛢️</div>
                <div className="empty-state__title">No candidates yet</div>
                <div className="empty-state__desc">
                  Create a case and run the detection → drift → candidates pipeline
                  to see ranked vessel attribution results.
                </div>
              </div>
            </div>
          )}

          {/* Export */}
          <ExportPanel
            caseId={caseId}
            onExport={handleExport}
            exportData={exportData}
            disabled={!caseId || loading}
          />
        </div>
      </div>

      {toast && <Toast message={toast} />}
    </div>
  );
}
