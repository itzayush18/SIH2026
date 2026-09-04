export interface Scenario {
  slug: string;
  name: string;
  subtitle: string;
  difficulty: string;
  story: string;
  tags: string[];
  center: { lat: number; lon: number };
}

export interface IncidentSummary {
  incident_id: string;
  scenario: Scenario;
  severity: string;
  area_km2: number;
  p_oil: number;
  centroid: { lat: number; lon: number };
  jurisdiction: string;
  nearest_coast: { km: number; name: string };
  prime_suspect: { mmsi: string; name: string; score: number } | null;
  n_alerts: number;
  n_patrol: number;
  data_mode: string;
}

export interface Source {
  id: string;
  name: string;
  category: string;
  tier: string;
  endpoint: string;
  status: string;
  latency_hint: string;
}

export interface Report {
  generated_for: string;
  scene: {
    bounds: [[number, number], [number, number]];
    size: number;
    pixel_m: number;
    mean_wind_ms: number;
    center: { lat: number; lon: number };
    sar_png: string;
    slick_png: string;
  };
  detections: {
    id: string;
    p_oil: number;
    area_km2: number;
    length_km: number;
    width_km: number;
    orientation_deg: number;
    centroid_lonlat: [number, number];
    contour_lonlat: [number, number][];
  }[];
  characterization: {
    bonn_class: string;
    thickness_m: number;
    volume_m3: number;
    tonnes: number;
    age_best_h: number;
    confidence: string;
    age_uncertainty_factor: number;
  };
  source: {
    t_start: number;
    duration: number;
    course_deg: number;
    speed_kn: number;
    start_lat: number;
    start_lon: number;
    iou: number;
    track: { lat: number; lon: number; t_rel_s: number }[];
    search_dispersion: { position_sd_km: number; t_start_sd_h: number; course_sd_deg: number; iou_range: [number, number] };
  };
  origin_pdf: {
    png: string;
    bounds: [[number, number], [number, number]];
    slices: { png: string; t_from_h: number; t_to_h: number; weight: number }[];
    t_centers_h: number[];
    cell_m: number;
  };
  origin_peak: { lat: number; lon: number; t_rel_s: number; prob: number };
  hindcast: { t_rel_h: number; points: [number, number][] }[];
  forecast: { t_rel_h: number; points: [number, number][] }[];
  vessels: { mmsi: string; name: string; type: string; length: number; track: [number, number, number][]; gaps: [number, number][] }[];
  suspects: {
    mmsi: string;
    name: string;
    type_name: string;
    length: number;
    score: number;
    terms: Record<string, number>;
    evidence: string[];
    closest_approach_km: number;
    track: [number, number, number][];
    narrative?: string;
    verdict?: 'RANKED' | 'REVIEW' | 'INSUFFICIENT_EVIDENCE';
    verdict_reason?: string;
    ais_quality?: number;
    ais_quality_grade?: 'HIGH' | 'MEDIUM' | 'LOW' | 'NONE' | 'ND';
    supporting_axes?: number;
    analyst_decision?: {
      action: 'ACCEPT' | 'REJECT' | 'ESCALATE';
      analyst: string;
      note: string;
      at: string;
    } | null;
  }[];
  validation: {
    segmentation: { iou: number; f1: number; precision: number; recall: number };
    inversion_error_km: number;
    inversion_time_error_h: number;
    inversion_course_error_deg: number;
    inversion_iou: number;
    attribution_correct: boolean | null;
  };
  oiltrace: {
    incident_id: string;
    scenario: Scenario;
    jurisdiction: { name: string; kind: string; sovereign: string; marpol_regime: string; source: string };
    nearest_coast: { km: number; name: string };
    alerts: { id: string; severity: string; kind: string; title: string; message: string }[];
    patrol: { id: string; priority: string; action: string; asset_class: string; target: string; lat: number; lon: number; radius_km: number; eta_hint: string; eta: string; reason: string; nearest_asset?: { station: string; distance_km: number } }[];
    evidence_pack: { json: string; geojson: string; csv: string; outdir: string };
    provenance: { generated_at: string; data_mode: string; chain: string[]; model_versions: Record<string, string> };
    data_mode: string;
    /** Which model produced the detections: "unet" or "logistic-8feature". */
    detector?: string;
    providers: Source[];
  };
  dark_vessels?: { mmsi: string; lat: number; lon: number; is_dark: boolean }[];
}
