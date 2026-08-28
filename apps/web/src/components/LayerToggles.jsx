import React, { useState } from 'react';

/**
 * LayerToggles — Map layer visibility controls.
 *
 * Layers: SAR, Mask (slick), Origin Contours, Forward Envelope, AIS Tracks.
 * Scaffold: toggles state only, no real map layer interaction yet.
 */

const LAYERS = [
  { id: 'sar', label: 'SAR Image', color: '#94a3b8' },
  { id: 'mask', label: 'Slick Mask', color: '#fb7185' },
  { id: 'contours', label: 'Origin Contours', color: '#2dd4bf' },
  { id: 'envelope', label: 'Forward Envelope', color: '#fbbf24' },
  { id: 'ais', label: 'AIS Tracks', color: '#38bdf8' },
];

export default function LayerToggles() {
  const [active, setActive] = useState(new Set(['mask', 'ais']));

  const toggle = (id) => {
    setActive((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  return (
    <div className="layer-toggles" id="layer-toggles">
      {LAYERS.map((layer) => (
        <button
          key={layer.id}
          className={`layer-toggle ${active.has(layer.id) ? 'layer-toggle--active' : ''}`}
          onClick={() => toggle(layer.id)}
          style={{ '--dot-color': layer.color }}
        >
          <span
            className="layer-toggle__dot"
            style={{ background: active.has(layer.id) ? layer.color : 'var(--text-muted)' }}
          />
          {layer.label}
        </button>
      ))}
    </div>
  );
}
