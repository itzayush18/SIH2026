/**
 * OilTrace — API client.
 *
 * All fetch calls target the FastAPI backend at localhost:8000.
 * In production, this would use environment-based URLs.
 */

const API_BASE = 'http://localhost:8000';

async function request(method, path, body = null) {
  const opts = {
    method,
    headers: { 'Content-Type': 'application/json' },
  };
  if (body) opts.body = JSON.stringify(body);

  const res = await fetch(`${API_BASE}${path}`, opts);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `API error ${res.status}`);
  }
  return res.json();
}

// -- Cases ----------------------------------------------------------------

export function createCase(data = {}) {
  return request('POST', '/cases', {
    aoi: data.aoi || {},
    start_utc: data.start_utc || new Date().toISOString(),
    end_utc: data.end_utc || new Date().toISOString(),
    created_by: data.created_by || 'analyst',
  });
}

// -- Assets ---------------------------------------------------------------

export function registerAsset(caseId, uri, assetType = 'other') {
  return request('POST', `/cases/${caseId}/assets`, {
    uri,
    asset_type: assetType,
  });
}

// -- Detection ------------------------------------------------------------

export function runDetection(caseId) {
  return request('POST', `/cases/${caseId}/detect`);
}

export function reviewDetection(runId, verdict = 'accepted', reason = '') {
  return request('POST', `/detections/${runId}/review`, {
    verdict,
    reason,
  });
}

// -- Drift ----------------------------------------------------------------

export function runDrift(caseId) {
  return request('POST', `/cases/${caseId}/drift`);
}

// -- Candidates -----------------------------------------------------------

export function getCandidates(caseId) {
  return request('GET', `/cases/${caseId}/candidates`);
}

// -- Export ----------------------------------------------------------------

export function exportCase(caseId) {
  return request('POST', `/cases/${caseId}/export`);
}

// -- Jobs -----------------------------------------------------------------

export function getJobStatus(jobId) {
  return request('GET', `/jobs/${jobId}`);
}
