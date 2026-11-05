export type Band = "LOW" | "MEDIUM" | "HIGH" | "UNCERTAIN";
export type Tier = "fast" | "deep" | "doc" | "identity" | "claim";

export interface Signal {
  name: string;
  score: number | null;          // 0 authentic … 1 manipulated; null = abstained / not applicable
  confidence: number;            // 0..1
  reason: string;                // show verbatim
  evidence: Record<string, any>;
  abstained: boolean;
  applicable: boolean;
  tier: Tier;
}

export interface Region {
  box: [number, number, number, number]; // [x1, y1, x2, y2]
  area_frac: number;
  signals: Record<string, number>;
  reason: string;
  stage: 1 | 2;
}

export interface ClaimScore {
  image_score: number | null;
  document_score: number | null;
  identity_score: number | null;
  overall: number;
  band: Band;
  waterfall: [string, number][];   // [["baseline", 0.5], ["localizer", 0.21], ...]
  regions: Region[];
  signals: Signal[];
  pending_deep: boolean;
}

export interface ImageResult {
  index: number;
  name: string;
  sha256: string;
  claim: ClaimScore;
  quality_flag: boolean;
  quality_reasons: string[];
  timing: {
    first_card_s: number | null;
    fast_tier_s: number;
    deep_s: number | null;
  };
  urls: {
    photo: string;
    heatmap: string | null;
    reconstruction: string | null;
  };
}

export interface DocResult {
  index: number;
  name: string;
  sha256: string;
  doc_type: "invoice" | "medical" | "id" | "other";
  from_ocr: boolean;
  text: string;
  claim: ClaimScore;
  timing: { total_s: number };
  urls: { page: string | null };
}

export interface CaseResult {
  case_id: string;
  title: string;
  status: "done";
  claim: ClaimScore;
  images: ImageResult[];
  documents: DocResult[];
  identity: {
    signals: Signal[];
    urls: { id: string; selfie: string };
  } | null;
  narrative: {
    text: string;
    source: "template" | "llm";
  };
  hashes: string[];
}

export interface Attack {
  kind: string;
  method: "nova" | "local_sd15" | "pregenerated" | "recompress";
  note: string;
  seconds: number;
}

export interface InboxCase {
  case_id: string;
  title: string;
  counts: {
    photos: number;
    documents: number;
    id: boolean;
    selfie: boolean;
  };
  last_band: Band | null;
}

export interface ApiConfig {
  bands: {
    low_max: number;
    medium_max: number;
  };
  weights: {
    image: Record<string, number>;
    document: Record<string, number>;
    identity: Record<string, number>;
    claim: Record<string, number>;
  };
  arena_attacks: string[];
  arena_default_prompt: string;
  accepted_types: {
    image: string[];
    document: string[];
  };
}

export interface HealthStatus {
  ok: boolean;
  problems: string[];
  device: string;
}

export interface AuditRecord {
  case_id: string;
  reviewer: string;
  action: "accept" | "reject" | "escalate";
  note: string;
  band: Band;
  ts: string;
}

export interface SeedItem {
  name: string;
  url: string;
}
