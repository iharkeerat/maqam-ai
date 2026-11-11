import raagSeedJson from "./raag_seed.json";
import raagCatalogueJson from "./raag_catalogue.json";
import taalJson from "./taals.json";
import historicalTaalJson from "./historical_taals.json";
import sourceJson from "./sources.json";
import type {
  AndolanRule,
  HistoricalTaalRecord,
  MasterJsonPayload,
  MasterJsonRaag,
  MasterJsonTaal,
  RaagRecord,
  SourceRef,
  TaalRecord,
} from "./types";

export const BUILT_IN_RAAGS = raagSeedJson as RaagRecord[];
export const RAAG_CATALOGUE = raagCatalogueJson as Array<{
  ordinal: number;
  id: string;
  name: string;
  tier: "generation-ready" | "catalogue-only";
  verification: string;
  generationReady: boolean;
  thaat: string | null;
  dataCompleteness: number;
}>;
export const PRACTICAL_TAALS = taalJson as TaalRecord[];
export const HISTORICAL_TAALS = historicalTaalJson as HistoricalTaalRecord[];
export const SOURCE_REGISTER = sourceJson as SourceRef[];

export const THAATS = [
  "Bilawal",
  "Khamaj",
  "Kafi",
  "Asavari",
  "Bhairavi",
  "Bhairav",
  "Kalyan",
  "Marwa",
  "Purvi",
  "Todi",
] as const;

const SWAR_ORDER = ["S", "r", "R", "g", "G", "m", "M", "P", "d", "D", "n", "N"];
const ALL_SWARS = new Set(SWAR_ORDER);

export function slugify(value: string): string {
  return value
    .normalize("NFKD")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
}

export function normaliseSwarToken(raw: string): string | null {
  const clean = raw
    .replace(/M[#^]/g, "M")
    .replace(/_(low|high)/gi, "")
    .replace(/[.'’`̣̇]/g, "")
    .replace(/[()\[\]{}]/g, "")
    .trim();
  return ALL_SWARS.has(clean) ? clean : null;
}

export function extractSwarTokens(...texts: Array<string | null | undefined>): string[] {
  const values: string[] = [];
  for (const text of texts) {
    if (!text) continue;
    for (const raw of text.split(/[\s,;:|/·—–-]+/g)) {
      const token = normaliseSwarToken(raw);
      if (token && !values.includes(token)) values.push(token);
    }
  }
  return values;
}

export function extractPhraseTokens(text: string | null | undefined): string[] {
  if (!text) return [];
  return text
    .split(/[\s,;:|/·—–-]+/g)
    .map(normaliseSwarToken)
    .filter((token): token is string => Boolean(token));
}

function extractNamedSwar(label?: string): string | null {
  if (!label) return null;
  const parenthetical = label.match(/\(([SrRgGmMPdDnN])\)/);
  if (parenthetical) return parenthetical[1];
  const lower = label.toLowerCase();
  const map: Array<[string, string]> = [
    ["shadaj", "S"],
    ["rishabh", "R"],
    ["gandhar", "G"],
    ["madhyam", "m"],
    ["pancham", "P"],
    ["dhaivat", "D"],
    ["nishad", "N"],
  ];
  for (const [name, swar] of map) {
    if (!lower.includes(name)) continue;
    if (lower.includes("komal")) return swar.toLowerCase();
    if (lower.includes("tivra") && swar === "m") return "M";
    return swar;
  }
  return null;
}

function normaliseAndolan(source: MasterJsonRaag["acoustic_layer"]): Record<string, AndolanRule> {
  const result: Record<string, AndolanRule> = {};
  for (const [swar, rule] of Object.entries(source?.andolan_logic ?? {})) {
    if (!rule) continue;
    const token = normaliseSwarToken(swar);
    if (!token) continue;
    result[token] = {
      widthCents: Number(rule.width_cents ?? 0),
      speedHz: Number(rule.speed_hz ?? 0),
      asymmetry: Number(rule.asymmetry_coeff ?? 0),
    };
  }
  return result;
}

function makeSignaturePhrases(pakad: string | null): string[][] {
  const phrase = extractPhraseTokens(pakad);
  const phrases: string[][] = [];
  for (const length of [3, 4, 5]) {
    if (phrase.length < length) continue;
    phrases.push(phrase.slice(0, length));
    if (phrase.length > length + 1) phrases.push(phrase.slice(-length));
  }
  return phrases;
}

export function normaliseMasterRaag(name: string, source: MasterJsonRaag): RaagRecord {
  const symbolic = source.symbolic_layer ?? {};
  const acoustic = source.acoustic_layer ?? {};
  const affective = source.affective_layer ?? {};
  const allowedSwars = extractSwarTokens(symbolic.aaroh, symbolic.avroh, symbolic.pakad);
  const forbiddenSwars = SWAR_ORDER.filter((swar) => !allowedSwars.includes(swar));
  const vadiSwar = extractNamedSwar(symbolic.vadi);
  const samvadiSwar = extractNamedSwar(symbolic.samvadi);
  const defaultNotation = [
    ...extractPhraseTokens(symbolic.aaroh),
    ...extractPhraseTokens(symbolic.avroh),
  ].slice(0, 16);

  const requiredFields = [
    symbolic.thaat,
    symbolic.vadi,
    symbolic.samvadi,
    symbolic.gayan_samay,
    symbolic.aaroh,
    symbolic.avroh,
    symbolic.pakad,
    affective.primary_rasa,
  ].filter(Boolean).length;
  const completeness = Math.min(96, 42 + requiredFields * 6 + (acoustic.ratios ? 5 : 0) + (acoustic.andolan_logic ? 3 : 0));

  return {
    id: slugify(name),
    name,
    displayName: name.replaceAll("_", " "),
    aliases: [name, name.replaceAll("_", " ")],
    thaat: symbolic.thaat ?? null,
    vadi: symbolic.vadi ?? null,
    vadiSwar,
    samvadi: symbolic.samvadi ?? null,
    samvadiSwar,
    prakriti: symbolic.prakriti ?? null,
    time: symbolic.gayan_samay ?? null,
    aaroh: symbolic.aaroh ?? null,
    avroh: symbolic.avroh ?? null,
    pakad: symbolic.pakad ?? null,
    allowedSwars,
    forbiddenSwars,
    nyasSwars: [...new Set([vadiSwar, samvadiSwar, "S"].filter((value): value is string => Boolean(value)))],
    signaturePhrases: makeSignaturePhrases(symbolic.pakad ?? null),
    recommendedTaals: [],
    recommendedForms: [],
    defaultNotation,
    tuningSystem: acoustic.tuning_system ?? null,
    ratios: acoustic.ratios ?? {},
    andolan: normaliseAndolan(acoustic),
    rasaVector: Array.isArray(affective.rasa_vector)
      ? affective.rasa_vector.slice(0, 9).map((value) => Number(value) || 0)
      : Array(9).fill(0),
    primaryRasa: affective.primary_rasa ?? null,
    contextLogic: affective.context_logic ?? null,
    generationReady: Boolean(symbolic.aaroh && symbolic.avroh && symbolic.pakad && allowedSwars.length >= 5),
    dataCompleteness: completeness,
    verification: "imported-master",
    reviewStatus: "needs-expert-review",
    provenance: ["runtime-master-json-import"],
  };
}


function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : {};
}

function firstValue(records: Array<Record<string, unknown>>, keys: string[]): unknown {
  for (const record of records) {
    for (const key of keys) {
      if (record[key] !== undefined && record[key] !== null && record[key] !== "") return record[key];
    }
  }
  return undefined;
}

function parsePositiveInteger(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value) && value > 0) return Math.round(value);
  if (typeof value === "string") {
    const match = value.match(/\d+/);
    if (match) {
      const parsed = Number(match[0]);
      if (Number.isFinite(parsed) && parsed > 0) return Math.round(parsed);
    }
  }
  return null;
}

function parseNumberList(value: unknown): number[] {
  if (Array.isArray(value)) {
    return value.map(parsePositiveInteger).filter((item): item is number => item !== null);
  }
  if (typeof value === "string") {
    return value.split(/[^0-9]+/g).map(parsePositiveInteger).filter((item): item is number => item !== null);
  }
  return [];
}

function parseStringList(value: unknown): string[] {
  if (Array.isArray(value)) return value.map((item) => String(item).trim()).filter(Boolean);
  if (typeof value === "string") return value.split(/[|,;]+/g).map((item) => item.trim()).filter(Boolean);
  return [];
}

function normaliseTaalFamily(value: unknown): TaalRecord["family"] {
  const text = String(value ?? "").toLowerCase();
  if (text.includes("dhrupad")) return "dhrupad";
  if (text.includes("folk")) return "folk";
  if (text.includes("light") || text.includes("thumri") || text.includes("dadra")) return "light-classical";
  if (text.includes("histor")) return "historical";
  if (text.includes("khayal") || text.includes("khyal")) return "khayal";
  return "general";
}

export function normaliseMasterTaal(name: string, source: MasterJsonTaal): TaalRecord | null {
  const direct = asRecord(source);
  const rhythmic = asRecord(source.rhythmic_layer);
  const symbolic = asRecord(source.symbolic_layer);
  const taalLayer = asRecord(source.taal_layer);
  const records = [direct, rhythmic, symbolic, taalLayer];
  const beats = parsePositiveInteger(firstValue(records, ["beats", "matras", "matra", "total_matras", "totalMatras", "total_beats", "cycle_length", "avartan"]));
  if (!beats || beats > 128) return null;

  let divisions = parseNumberList(firstValue(records, ["divisions", "vibhags", "vibhag", "vibhag_pattern", "section_pattern", "khands", "khand", "anga_pattern"]));
  if (!divisions.length) divisions = [beats];
  const divisionTotal = divisions.reduce((sum, item) => sum + item, 0);
  const marks = parseStringList(firstValue(records, ["marks", "chinhs", "chinh", "tali_khali", "taliKhali", "claps", "symbols"]));
  const thekaValue = firstValue(records, ["theka", "bols", "bol_pattern", "bolPattern", "basic_theka", "pattern"]);
  const theka = typeof thekaValue === "string" && thekaValue.trim() ? thekaValue.trim() : null;
  const suitableForms = parseStringList(firstValue(records, ["suitable_forms", "forms", "usage", "musical_forms"]));
  const suitableLaya = parseStringList(firstValue(records, ["suitable_laya", "laya", "layas", "tempo"]));
  const aliases = parseStringList(firstValue(records, ["aliases", "alternate_names", "variants"]));
  const completeStructure = divisionTotal === beats && divisions.every((item) => item > 0);
  const generationReady = completeStructure && beats <= 32 && Boolean(theka);
  const populated = [beats, divisions.length, marks.length, theka, suitableForms.length, suitableLaya.length].filter(Boolean).length;

  return {
    id: slugify(name),
    name: name.replaceAll("_", " "),
    aliases: [...new Set([name, name.replaceAll("_", " "), ...aliases])],
    beats,
    divisions,
    marks: marks.length === divisions.length ? marks : divisions.map((_, index) => index === 0 ? "X" : String(index + 1)),
    theka,
    family: normaliseTaalFamily(firstValue(records, ["family", "type", "tradition", "style"])),
    suitableForms,
    suitableLaya: suitableLaya.length ? suitableLaya : ["Vilambit", "Madhya", "Drut"],
    generationReady,
    dataCompleteness: Math.min(94, 34 + populated * 9 + (completeStructure ? 6 : 0)),
    verification: "imported-master",
    reviewStatus: "needs-expert-review",
    note: generationReady
      ? "Imported cycle passed structural checks; Theka and performance variants still require expert review."
      : "Imported record is retained for study but blocked from automatic composition until its cycle and Theka are complete.",
    provenance: ["runtime-master-json-import"],
  };
}

export function importMasterKnowledge(payload: unknown): { raags: RaagRecord[]; taals: TaalRecord[]; warnings: string[]; metadata: Record<string, unknown> } {
  if (!payload || typeof payload !== "object") {
    throw new Error("The selected file is not a JSON object.");
  }
  const parsed = payload as MasterJsonPayload;
  const sourceRaags = parsed.ragas ?? parsed.raags;
  if (!sourceRaags || typeof sourceRaags !== "object") {
    throw new Error("No `ragas` or `raags` object was found in the master JSON.");
  }
  const warnings: string[] = [];
  const raags = Object.entries(sourceRaags)
    .filter(([, value]) => value && typeof value === "object")
    .map(([name, value]) => normaliseMasterRaag(name, value));

  const sourceTaals = parsed.taals ?? parsed.talas ?? {};
  const taalEntries = Object.entries(sourceTaals).filter(([, value]) => value && typeof value === "object");
  const taals = taalEntries
    .map(([name, value]) => normaliseMasterTaal(name, value))
    .filter((record): record is TaalRecord => Boolean(record));
  const skippedTaals = taalEntries.length - taals.length;

  const duplicateIds = raags
    .map((record) => record.id)
    .filter((id, index, values) => values.indexOf(id) !== index);
  if (duplicateIds.length) warnings.push(`${new Set(duplicateIds).size} duplicate canonical IDs need alias review.`);
  const incomplete = raags.filter((record) => !record.generationReady).length;
  if (incomplete) warnings.push(`${incomplete} records are catalogue-only because required grammar fields are incomplete.`);
  if (raags.length < 50) warnings.push(`Only ${raags.length} Raag records were detected; the expected master file contains substantially more.`);
  if (skippedTaals) warnings.push(`${skippedTaals} Taal records lacked a readable positive matra count and were not activated.`);
  const blockedTaals = taals.filter((record) => !record.generationReady).length;
  if (blockedTaals) warnings.push(`${blockedTaals} imported Taals are study-only until their Vibhag totals and Thekas are complete.`);

  return {
    raags,
    taals,
    warnings,
    metadata: parsed.metadata ?? {},
  };
}

export function mergeRaagLibraries(base: RaagRecord[], imported: RaagRecord[]): RaagRecord[] {
  const merged = new Map<string, RaagRecord>();
  for (const record of base) merged.set(record.id, record);
  for (const record of imported) merged.set(record.id, record);
  return [...merged.values()].sort((a, b) => a.displayName.localeCompare(b.displayName));
}

export function findRaag(library: RaagRecord[], idOrName: string): RaagRecord | undefined {
  const slug = slugify(idOrName);
  return library.find((record) => record.id === slug || record.aliases.some((alias) => slugify(alias) === slug));
}

export function mergeTaalLibraries(base: TaalRecord[], imported: TaalRecord[]): TaalRecord[] {
  const merged = new Map<string, TaalRecord>();
  for (const record of base) merged.set(record.id, record);
  for (const record of imported) merged.set(record.id, record);
  return [...merged.values()].sort((a, b) => a.name.localeCompare(b.name));
}

export function findTaal(library: TaalRecord[], idOrName: string): TaalRecord | undefined {
  const slug = slugify(idOrName);
  return library.find((record) => record.id === slug || record.aliases.some((alias) => slugify(alias) === slug));
}
