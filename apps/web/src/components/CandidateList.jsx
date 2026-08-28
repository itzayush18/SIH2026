import React from 'react';

/**
 * CandidateList — Ranked list of candidate vessels with score breakdown.
 *
 * Score type is always "evidence_index" — never "probability" or "guilty".
 * This is a hard product rule.
 */
export default function CandidateList({
  candidates = [],
  scoreType = 'evidence_index',
  onSelect,
  selected,
}) {
  if (candidates.length === 0) return null;

  return (
    <div className="panel-section" id="candidate-list">
      <div className="panel-section__title">
        Candidates
        <span className="text-muted" style={{ marginLeft: 8, fontSize: '0.65rem', textTransform: 'none', letterSpacing: 0, fontWeight: 400 }}>
          {scoreType}
        </span>
      </div>

      {candidates.map((cand, idx) => {
        const isSelected = selected?.vessel_key === cand.vessel_key;
        return (
          <div
            key={cand.vessel_key}
            className={`candidate-row ${isSelected ? 'card--active' : ''}`}
            onClick={() => onSelect(cand)}
            id={`candidate-${idx}`}
          >
            <div className="candidate-row__rank">#{idx + 1}</div>
            <div className="candidate-row__info">
              <div className="candidate-row__vessel">{cand.vessel_key}</div>
              <div className="candidate-row__flags">
                {cand.flags?.map((f) => (
                  <span key={f} className="flag-chip">{f}</span>
                ))}
              </div>
            </div>
            <div className="candidate-row__score">
              <div className="candidate-row__score-value">
                {typeof cand.score === 'number' ? cand.score.toFixed(1) : cand.score}
              </div>
              <div className="candidate-row__score-label">/ 100</div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
