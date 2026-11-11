export type VerificationTier =
  | "legacy-master-seed"
  | "imported-master"
  | "catalogue-only"
  | "source-verified"
  | "variant-sensitive"
  | "historical-observatory";

export type ReviewStatus = "usable-with-caution" | "needs-expert-review" | "catalogue-only" | "source-transcription-required";

export type RasaKey =
  | "karuna"
  | "bhakti"
  | "shringara"
  | "vira"
  | "raudra"
  | "bhayanaka"
  | "bibhatsa"
  | "adbhuta"
  | "shanta";

export const RASA_KEYS: RasaKey[] = [
  "karuna",
  "bhakti",
  "shringara",
  "vira",
  "raudra",
  "bhayanaka",
  "bibhatsa",
  "adbhuta",
  "shanta",
];

export interface SourceRef {
  id: string;
  title: string;
  note: string;
  url?: string;
}

export interface AndolanRule {
  widthCents: number;
  speedHz: number;
  asymmetry: number;
}

export interface RaagRecord {
  id: string;
  name: string;
  displayName: string;
  aliases: string[];
  devanagari?: string;
  thaat: string | null;
  vadi: string | null;
  vadiSwar: string | null;
  samvadi: string | null;
  samvadiSwar: string | null;
  prakriti: string | null;
  time: string | null;
  aaroh: string | null;
  avroh: string | null;
  pakad: string | null;
  allowedSwars: string[];
  forbiddenSwars: string[];
  nyasSwars: string[];
  signaturePhrases: string[][];
  recommendedTaals: string[];
  recommendedForms: string[];
  defaultNotation: string[];
  tuningSystem: string | null;
  ratios: Record<string, string>;
  andolan: Record<string, AndolanRule>;
  rasaVector: number[];
  primaryRasa: string | null;
  contextLogic: string | null;
  generationReady: boolean;
  dataCompleteness: number;
  verification: VerificationTier;
  reviewStatus: ReviewStatus;
  provenance: string[];
}

export interface TaalRecord {
  id: string;
  name: string;
  aliases: string[];
  beats: number;
  divisions: number[];
  marks: string[];
  theka: string | null;
  family: "khayal" | "light-classical" | "dhrupad" | "folk" | "historical" | "general";
  suitableForms: string[];
  suitableLaya: string[];
  generationReady: boolean;
  dataCompleteness: number;
  verification: VerificationTier;
  reviewStatus: ReviewStatus;
  note: string;
  provenance: string[];
}

export interface HistoricalTaalRecord {
  id: string;
  ordinal: number;
  registrySlot: number;
  sourceOrdinal: number | null;
  canonicalName: string | null;
  iast: string | null;
  devanagari: string | null;
  aliases: string[];
  tradition: "deshi";
  classification: string;
  constituentAngas: string[] | null;
  totalKala: number | null;
  kriyaSequence: string[] | null;
  modernCorrespondence: Array<{ name?: string; confidence?: string; note?: string }>;
  rendering: {
    supported: boolean;
    mode: "historical-kriya" | "neutral-percussion" | "unavailable";
    reason: string;
  };
  usableInComposition: false;
  verification: "historical-observatory";
  reviewStatus: "source-transcription-required";
  attestationLevel: "secondary-attested-name" | "unresolved-source-slot" | "primary-transcribed" | "structure-verified";
  sourceWork: "Sangita Ratnakara";
  sourceChapter: "Taladhyaya";
  provenance: string[];
  sourceLocator: {
    edition: string;
    verse: string | null;
    page: number | null;
  };
  note: string;
}

export interface MasterJsonRaag {
  symbolic_layer?: {
    thaat?: string;
    vadi?: string;
    samvadi?: string;
    prakriti?: string;
    gayan_samay?: string;
    aaroh?: string;
    avroh?: string;
    pakad?: string;
  };
  acoustic_layer?: {
    tuning_system?: string;
    ratios?: Record<string, string>;
    andolan_logic?: Record<string, { width_cents?: number; speed_hz?: number; asymmetry_coeff?: number }> | null;
  };
  affective_layer?: {
    rasa_vector?: number[];
    primary_rasa?: string;
    context_logic?: string;
  };
}

export interface MasterJsonTaal {
  rhythmic_layer?: Record<string, unknown>;
  symbolic_layer?: Record<string, unknown>;
  taal_layer?: Record<string, unknown>;
  [key: string]: unknown;
}

export interface MasterJsonPayload {
  metadata?: Record<string, unknown>;
  ragas?: Record<string, MasterJsonRaag>;
  raags?: Record<string, MasterJsonRaag>;
  talas?: Record<string, MasterJsonTaal>;
  taals?: Record<string, MasterJsonTaal>;
}
