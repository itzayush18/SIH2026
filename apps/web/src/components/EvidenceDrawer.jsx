import React from 'react';

/**
 * EvidenceDrawer — Expandable detail panel for a selected candidate.
 *
 * Shows the 4 component score breakdown bars + AIS quality + timestamp.
 */
export default function EvidenceDrawer({ candidate }) {
  if (!candidate) return null;

  const components = candidate.components || {};
  const bars = [
    { key: 'space', label: 'Spatial', value: components.space },
    { key: 'time', label: 'Temporal', value: components.time },
    { key: 'forward_fit', label: 'Forward Fit', value: components.forward_fit },
    { key: 'behaviour', label: 'Behaviour', value: components.behaviour },
  ];

  return (
    <div className="evidence-drawer" id="evidence-drawer">
      <div className="panel-section__title">Evidence Breakdown</div>

      <div className="card">
        <div className="flex justify-between items-center mb-2">
          <span className="text-mono" style={{ fontSize: '0.85rem' }}>
            {candidate.vessel_key}
          </span>
          <span style={{
            fontSize: '1.1rem',
            fontWeight: 800,
            background: 'var(--gradient-score)',
            WebkitBackgroundClip: 'text',
            WebkitTextFillColor: 'transparent',
          }}>
            {candidate.score?.toFixed(1)}
          </span>
        </div>

        {bars.map((bar) => (
          <div key={bar.key} className="score-bar">
            <span className="score-bar__label">{bar.label}</span>
            <div className="score-bar__track">
              <div
                className="score-bar__fill"
                style={{ width: `${(bar.value || 0) * 100}%` }}
              />
            </div>
            <span className="score-bar__value">
              {bar.value != null ? (bar.value * 100).toFixed(0) : '—'}%
            </span>
          </div>
        ))}

        <div className="score-bar mt-2">
          <span className="score-bar__label">AIS Quality</span>
          <div className="score-bar__track">
            <div
              className="score-bar__fill"
              style={{
                width: `${(candidate.ais_quality || 0) * 100}%`,
                background: 'var(--accent-teal)',
              }}
            />
          </div>
          <span className="score-bar__value">
            {candidate.ais_quality != null ? (candidate.ais_quality * 100).toFixed(0) : '—'}%
          </span>
        </div>

        {candidate.evidence_time_utc && (
          <div className="text-muted mt-4" style={{ fontSize: '0.75rem' }}>
            Evidence time: {candidate.evidence_time_utc}
          </div>
        )}

        {candidate.flags?.length > 0 && (
          <div className="mt-2" style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            {candidate.flags.map((f) => (
              <span key={f} className="flag-chip">{f}</span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
