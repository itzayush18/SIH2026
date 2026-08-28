import React, { useState } from 'react';

/**
 * TimelineScrubber — Time range slider for the observation window.
 *
 * Scaffold: displays a visual slider stub with start/end labels.
 * Production: would control map layer rendering time window.
 */
export default function TimelineScrubber() {
  const [value, setValue] = useState(50);

  // Demo time window
  const start = '2026-08-19 00:00 UTC';
  const end = '2026-08-21 00:00 UTC';

  // Interpolate display time
  const hours = Math.round((value / 100) * 48);
  const displayDate = new Date(Date.UTC(2026, 7, 19, hours));
  const display = displayDate.toISOString().replace('T', ' ').slice(0, 16) + ' UTC';

  return (
    <div className="timeline-scrubber" id="timeline-scrubber">
      <div className="timeline-scrubber__labels">
        <span>{start}</span>
        <span style={{ color: 'var(--accent-cyan)', fontWeight: 600 }}>{display}</span>
        <span>{end}</span>
      </div>
      <input
        type="range"
        min="0"
        max="100"
        value={value}
        onChange={(e) => setValue(Number(e.target.value))}
      />
    </div>
  );
}
