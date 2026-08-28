import React from 'react';

/**
 * StatusBar — Top bar showing case ID, status badge, and timestamps.
 */
export default function StatusBar({ caseId, status }) {
  const statusClass = `status-badge status-badge--${status || 'created'}`;

  return (
    <header className="status-bar" id="status-bar">
      <div className="status-bar__brand">
        <span className="status-bar__logo">◉ OilTrace</span>
      </div>
      <div className="status-bar__case">
        {caseId && (
          <>
            <span className="status-bar__case-id">{caseId}</span>
            <span className={statusClass}>
              <span style={{
                width: 6, height: 6, borderRadius: '50%',
                background: 'currentColor', display: 'inline-block',
              }} />
              {(status || 'created').replace(/_/g, ' ')}
            </span>
          </>
        )}
        {!caseId && (
          <span className="text-muted">No active case</span>
        )}
      </div>
    </header>
  );
}
