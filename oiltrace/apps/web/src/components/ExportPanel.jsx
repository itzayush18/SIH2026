import React from 'react';

/**
 * ExportPanel — GeoJSON / CSV / PDF export buttons.
 */
export default function ExportPanel({ caseId, onExport, exportData, disabled }) {
  return (
    <div className="export-panel" id="export-panel">
      <div className="panel-section__title">Export</div>

      <button
        className="btn btn--primary"
        onClick={onExport}
        disabled={disabled}
        id="btn-export"
      >
        📦 Export Report Bundle
      </button>

      {exportData && (
        <div className="card mt-2">
          <div className="text-muted" style={{ fontSize: '0.75rem', marginBottom: 8 }}>
            Exported at: {exportData.exported_at}
          </div>
          <div style={{ fontSize: '0.8rem' }}>
            {exportData.artefacts && Object.entries(exportData.artefacts).map(([key, val]) => (
              <div key={key} className="flex justify-between" style={{ marginBottom: 4 }}>
                <span style={{ textTransform: 'uppercase', color: 'var(--accent-teal)', fontSize: '0.7rem', fontWeight: 600 }}>
                  {key}
                </span>
                <span className="text-muted">
                  {val.feature_count != null && `${val.feature_count} features`}
                  {val.row_count != null && `${val.row_count} rows`}
                  {val.status === 'stub' && 'stub'}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
