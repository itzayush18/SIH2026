import React, { useEffect, useRef } from 'react';
import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';

/**
 * MapView — MapLibre GL canvas with a dark basemap.
 *
 * Scaffold: displays the map centered on the demo AOI (Arabian Sea).
 * Production: would render SAR tiles, slick polygons, contours, AIS tracks.
 */
export default function MapView() {
  const mapContainer = useRef(null);
  const mapRef = useRef(null);

  useEffect(() => {
    if (mapRef.current) return;

    const map = new maplibregl.Map({
      container: mapContainer.current,
      // Free dark basemap — no API key needed
      style: {
        version: 8,
        name: 'OilTrace Dark',
        sources: {
          'osm-tiles': {
            type: 'raster',
            tiles: [
              'https://basemaps.cartocdn.com/dark_all/{z}/{x}/{y}@2x.png',
            ],
            tileSize: 256,
            attribution: '&copy; CARTO &copy; OpenStreetMap contributors',
          },
        },
        layers: [
          {
            id: 'osm-tiles-layer',
            type: 'raster',
            source: 'osm-tiles',
            minzoom: 0,
            maxzoom: 19,
          },
        ],
      },
      center: [72.86, 18.96], // Demo AOI center — off Mumbai coast
      zoom: 11,
      attributionControl: true,
    });

    map.addControl(new maplibregl.NavigationControl(), 'bottom-right');

    // Add demo AOI outline after style loads
    map.on('load', () => {
      map.addSource('demo-aoi', {
        type: 'geojson',
        data: {
          type: 'Feature',
          properties: { name: 'Demo AOI' },
          geometry: {
            type: 'Polygon',
            coordinates: [[
              [72.80, 18.90], [72.92, 18.90],
              [72.92, 19.02], [72.80, 19.02],
              [72.80, 18.90],
            ]],
          },
        },
      });

      map.addLayer({
        id: 'demo-aoi-outline',
        type: 'line',
        source: 'demo-aoi',
        paint: {
          'line-color': '#38bdf8',
          'line-width': 2,
          'line-dasharray': [4, 3],
          'line-opacity': 0.7,
        },
      });

      map.addLayer({
        id: 'demo-aoi-fill',
        type: 'fill',
        source: 'demo-aoi',
        paint: {
          'fill-color': '#38bdf8',
          'fill-opacity': 0.05,
        },
      });

      // Demo slick polygon
      map.addSource('demo-slick', {
        type: 'geojson',
        data: {
          type: 'Feature',
          properties: { name: 'Detected Slick' },
          geometry: {
            type: 'Polygon',
            coordinates: [[
              [72.85, 18.95], [72.87, 18.95],
              [72.87, 18.97], [72.86, 18.98],
              [72.85, 18.97], [72.85, 18.95],
            ]],
          },
        },
      });

      map.addLayer({
        id: 'demo-slick-fill',
        type: 'fill',
        source: 'demo-slick',
        paint: {
          'fill-color': '#f43f5e',
          'fill-opacity': 0.3,
        },
      });

      map.addLayer({
        id: 'demo-slick-outline',
        type: 'line',
        source: 'demo-slick',
        paint: {
          'line-color': '#fb7185',
          'line-width': 2,
        },
      });
    });

    mapRef.current = map;

    return () => map.remove();
  }, []);

  return <div ref={mapContainer} className="map-container" id="map-view" />;
}
