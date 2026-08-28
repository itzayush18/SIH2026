import React from 'react';

/**
 * SlickReviewCard — Accept / Reject / Uncertain controls for detected slicks.
 */
export default function SlickReviewCard({ slicks = [], onReview }) {
  if (slicks.length === 0) return null;

  return (
    <div className="panel-section" id="slick-review">
      <div className="panel-section__title">Slick Review</div>
      {slicks.map((slick, idx) => (
        <div key={slick.slick_id || idx} className="card">
          <div className="flex justify-between items-center mb-2">
            <span className="text-mono" style={{ fontSize: '0.85rem' }}>
              {slick.slick_id || `Slick ${idx + 1}`}
            </span>
            <span className={`status-badge status-badge--${slick.review_state === 'accepted' ? 'exported' : slick.review_state === 'rejected' ? 'review_required' : 'created'}`}>
              {slick.review_state || 'pending'}
            </span>
          </div>
          <div className="text-muted" style={{ fontSize: '0.8rem', marginBottom: 10 }}>
            Area: {slick.area_km2?.toFixed(1) || '—'} km²
          </div>
          <div className="btn-group">
            <button
              className="btn btn--accept"
              onClick={() => onReview('accepted')}
              id={`btn-accept-${idx}`}
            >
              ✓ Accept
            </button>
            <button
              className="btn btn--reject"
              onClick={() => onReview('rejected')}
              id={`btn-reject-${idx}`}
            >
              ✕ Reject
            </button>
            <button
              className="btn btn--uncertain"
              onClick={() => onReview('uncertain')}
              id={`btn-uncertain-${idx}`}
            >
              ? Uncertain
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}
