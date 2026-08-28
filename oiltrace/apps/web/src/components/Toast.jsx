import React from 'react';

/**
 * Toast — Notification toast in the bottom-right corner.
 */
export default function Toast({ message }) {
  if (!message) return null;

  return (
    <div className="toast" id="toast">
      {message}
    </div>
  );
}
