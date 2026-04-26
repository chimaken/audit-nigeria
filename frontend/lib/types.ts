/**
 * Mirrors FastAPI `/results/*` JSON shapes (see backend/app/api/results.py).
 */

export type PartyResults = Record<string, number>;

export interface NationalTotalsResponse {
  election_id: number;
  party_results: PartyResults;
  updated_at: string | null;
  /** True when at least one PU cluster is DISPUTED but still contributes best-effort figures to rollups. */
  includes_provisional_disputed?: boolean;
}

export interface StateListItem {
  state_id: number;
  state_name: string;
}

export interface LgaRow {
  lga_id: number;
  lga_name: string;
  party_results: PartyResults;
  updated_at: string | null;
}

export interface StateDrilldownResponse {
  election_id: number;
  state_id: number;
  state_name: string;
  state_party_results: PartyResults;
  lgas: LgaRow[];
}

export interface PollingUnitListItem {
  pu_id: number;
  pu_name: string;
  pu_code: string;
  consensus_status: "VERIFIED" | "DISPUTED" | "PENDING" | "NO_CLUSTER";
}

export interface LgaPollingUnitsResponse {
  election_id: number;
  lga_id: number;
  lga_name: string;
  lga_party_results: PartyResults;
  polling_units: PollingUnitListItem[];
}

export interface ProofImage {
  upload_id: number;
  cluster_id: number;
  image_url: string;
  blur_score: number | null;
}

export interface PuDetailResponse {
  election_id: number;
  pu_id: number;
  pu_name: string;
  pu_code: string;
  ward: string | null;
  lga_id: number;
  lga_name: string;
  state_id: number;
  state_name: string;
  primary_cluster_id: number;
  consensus_status: string;
  party_results: PartyResults;
  consensus: Record<string, unknown> | null;
  form_header: Record<string, string> | null;
  ai_detected_location_line: string | null;
  confidence_score: number | null;
  proof_images: ProofImage[];
  /** When DISPUTED, copy of `consensus.reason` for quick UI (e.g. extraction_failed). */
  review_reason?: string | null;
  /** When DISPUTED, copy of `consensus.errors` (vision/API failures). */
  review_errors?: string[] | null;
}

export interface PuLookupResponse {
  pu_id: number;
  pu_code: string;
  pu_name: string;
  lga_id: number;
  lga_name: string;
  state_id: number;
  state_name: string | null;
}

/** Office / race lens for the command UI (query `race=`). Presidency = national presidential-style rollups. */
export type ElectionRace = "presidency" | "senate";

/** @deprecated Use `ElectionRace`; kept for older imports. */
export type ElectionViewMode = ElectionRace;

/** `/public/geo/nigeria-lga-centroids.json` (from scripts/download_nigeria_lga_geo.py). */
export interface NigeriaCentroidRecord {
  stateName: string;
  lgaName: string;
  admin2Pcod: string;
  lng: number;
  lat: number;
}

export interface NigeriaCentroidsPayload {
  version: number;
  records: NigeriaCentroidRecord[];
  featureCount?: number;
}

/** Successful `POST /upload` body (see backend/app/api/uploads.py). */
export interface SheetUploadResponse {
  upload_id: number;
  cluster_id: number;
  resolved_pu_id: number;
  image_path: string;
  blur_score: number;
  blur_score_original?: number;
  blur_best_strategy?: string;
  blur_scores_by_strategy?: Record<string, number>;
  phash: string;
  form_header?: Record<string, string>;
  ai_detected_location_line?: string;
  ingestion_warnings?: string[];
}
