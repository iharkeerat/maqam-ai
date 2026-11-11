import { PRACTICAL_TAALS, slugify } from "../data/knowledge";
import { RASA_KEYS, type RaagRecord, type RasaKey, type TaalRecord } from "../data/types";

export type WorkbenchMode = "guided" | "scholar" | "autopilot";

export interface RecommendationConstraints {
  mode?: WorkbenchMode;
  lockedRaagId?: string | null;
  lockedTaalId?: string | null;
  preferredForm?: string | null;
  preferredTime?: string | null;
  desiredLaya?: string | null;
}

export interface PoetryFeatures {
  language: "Punjabi" | "Hindi" | "Urdu" | "Roman/Latin" | "Mixed";
  scripts: string[];
  wordCount: number;
  lineCount: number;
  averageWordsPerLine: number;
  cadenceVariation: number;
  rasaVector: number[];
  primaryRasa: RasaKey;
  secondaryRasa: RasaKey;
  themes: string[];
  evidence: Array<{ token: string; rasa: RasaKey; weight: number }>;
  timeImagery: string[];
  seasonImagery: string[];
  devotionalSignal: number;
  romanticSignal: number;
}

export interface ScoreComponent {
  key: string;
  label: string;
  score: number;
  max: number;
  reason: string;
}

export interface RaagCandidate {
  id: string;
  name: string;
  fitScore: number;
  components: ScoreComponent[];
  explanation: string;
  caveat: string;
  verification: string;
  dataCompleteness: number;
}

export interface TaalCandidate {
  id: string;
  name: string;
  fitScore: number;
  beats: number;
  divisions: number[];
  components: ScoreComponent[];
  explanation: string;
  caveat: string;
  verification: string;
}

export type SemanticEngine = "gemini-structured" | "offline-heuristic";

export interface SemanticMetadata {
  engine: SemanticEngine;
  confidence: number;
  summary: string;
  form?: string;
  model?: string;
}

export interface MusicologyAnalysis {
  analysisVersion: "maqam-neuro-symbolic-ranker-v10";
  scoreMeaning: "heuristic-fit-not-probability";
  semanticEngine: SemanticEngine;
  semanticConfidence: number;
  semanticSummary: string;
  semanticForm: string;
  semanticModel: string | null;
  features: PoetryFeatures;
  raagCandidates: RaagCandidate[];
  taalCandidates: TaalCandidate[];
  recommendation: {
    raagId: string;
    raagName: string;
    taalId: string;
    taalName: string;
    score: number;
  };
  uncertainty: string[];
  methodology: string[];
}

const RASA_LEXICON: Record<RasaKey, Array<[string, number]>> = {
  karuna: [
    ["dard", 1], ["gham", 1], ["judai", 1], ["virah", 1], ["hijr", 1], ["aansu", .8], ["rona", .7], ["lost", .6], ["grief", 1], ["sorrow", 1], ["pain", .8], ["separation", 1], ["waiting", .8], ["distance", .35], ["remembrance", .55], ["yaad", .75],
    ["ਦਰਦ", 1], ["ਵਿਛੋੜਾ", 1], ["ਹੰਝੂ", .8], ["ਰੋਣਾ", .7], ["ਗ਼ਮ", 1], ["ਦੁੱਖ", .9],
    ["दर्द", 1], ["विरह", 1], ["वियोग", 1], ["आँसू", .8], ["दुःख", .9], ["ग़म", 1],
    ["درد", 1], ["غم", 1], ["ہجر", 1], ["جدائی", 1], ["آنسو", .8], ["تنہائی", .8], ["یاد", .8], ["انتظار", .8],
  ],
  bhakti: [
    ["rab", 1], ["allah", 1], ["khuda", 1], ["guru", .9], ["prabhu", 1], ["dua", .8], ["ibadat", 1], ["naam", .5], ["name", .25], ["sajda", .9], ["divine", 1], ["prayer", 1], ["seeker", .7], ["truth", .6], ["soul", .7], ["fana", 1], ["murshid", .9], ["haq", .9], ["ranjha", .55], ["heer", .3], ["ishq", .45],
    ["ਰੱਬ", 1], ["ਵਾਹਿਗੁਰੂ", 1], ["ਨਾਮ", .6], ["ਅਰਦਾਸ", 1], ["ਗੁਰੂ", .9],
    ["ईश्वर", 1], ["प्रभु", 1], ["भक्ति", 1], ["प्रार्थना", 1], ["नाम", .5], ["गुरु", .9],
    ["اللہ", 1], ["خدا", 1], ["دعا", .9], ["عبادت", 1], ["سجدہ", .9], ["مرشد", .9],
  ],
  shringara: [
    ["ishq", 1], ["mohabbat", 1], ["pyar", 1], ["piya", .9], ["ranjha", .9], ["heer", .8], ["beloved", .9], ["love", 1], ["longing", .7], ["beauty", .6], ["nazar", .5],
    ["ਇਸ਼ਕ", 1], ["ਪਿਆਰ", 1], ["ਸੱਜਣ", .8], ["ਰਾਂਝਾ", .9], ["ਹੀਰ", .8], ["ਮਾਹੀ", .9],
    ["इश्क़", 1], ["प्रेम", 1], ["पिया", .9], ["प्रिय", .8], ["मोहब्बत", 1], ["साजन", .8],
    ["عشق", 1], ["محبت", 1], ["محبوب", .9], ["یار", .7], ["پیا", .9], ["حسن", .6],
  ],
  vira: [["veer", 1], ["victory", .8], ["courage", 1], ["warrior", 1], ["ਸ਼ੌਰਯ", 1], ["ਵੀਰ", 1], ["साहस", 1], ["वीर", 1], ["شجاعت", 1], ["فتح", .8]],
  raudra: [["anger", 1], ["rage", 1], ["fire", .5], ["ਕ੍ਰੋਧ", 1], ["ਗੁੱਸਾ", 1], ["क्रोध", 1], ["रोष", 1], ["غصہ", 1], ["قہر", 1]],
  bhayanaka: [["fear", 1], ["darkness", .6], ["terror", 1], ["ਡਰ", 1], ["ਭੈ", 1], ["भय", 1], ["डर", 1], ["خوف", 1], ["ڈر", 1]],
  bibhatsa: [["disgust", 1], ["revulsion", 1], ["ਘ੍ਰਿਣਾ", 1], ["घृणा", 1], ["نفرت", 1]],
  adbhuta: [["wonder", 1], ["mystery", .7], ["miracle", 1], ["ਹੈਰਾਨੀ", 1], ["ਵਿਸਮਾਦ", 1], ["अद्भुत", 1], ["विस्मय", 1], ["حیرت", 1], ["معجزہ", 1]],
  shanta: [["peace", 1], ["silence", .7], ["calm", 1], ["sukoon", 1], ["truth", .5], ["dissolve", .4], ["union", .45], ["ਸ਼ਾਂਤੀ", 1], ["ਸਕੂਨ", 1], ["शांति", 1], ["सुकून", 1], ["امن", 1], ["سکون", 1]],
};

const TIME_TERMS: Array<[string, string]> = [
  ["morning", "morning"], ["dawn", "morning"], ["subah", "morning"], ["ਸਵੇਰ", "morning"], ["प्रभात", "morning"], ["सुबह", "morning"], ["صبح", "morning"],
  ["evening", "evening"], ["sunset", "evening"], ["shaam", "evening"], ["ਸ਼ਾਮ", "evening"], ["संध्या", "evening"], ["शाम", "evening"], ["شام", "evening"],
  ["night", "night"], ["raat", "night"], ["midnight", "night"], ["ਰਾਤ", "night"], ["रात", "night"], ["شب", "night"], ["رات", "night"],
  ["afternoon", "afternoon"], ["ਦੁਪਹਿਰ", "afternoon"], ["दोपहर", "afternoon"], ["دوپہر", "afternoon"],
];

const SEASON_TERMS: Array<[string, string]> = [
  ["rain", "monsoon"], ["monsoon", "monsoon"], ["sawan", "monsoon"], ["ਬਰਸਾਤ", "monsoon"], ["ਸਾਵਣ", "monsoon"], ["सावन", "monsoon"], ["बारिश", "monsoon"], ["بارش", "monsoon"],
  ["spring", "spring"], ["basant", "spring"], ["ਬਸੰਤ", "spring"], ["वसंत", "spring"], ["बसंत", "spring"], ["بہار", "spring"],
];

function normaliseText(value: string): string {
  return value.normalize("NFKC").toLowerCase().replace(/[\p{P}\p{S}]+/gu, " ").replace(/\s+/g, " ").trim();
}

function detectLanguage(text: string): PoetryFeatures["language"] {
  const counts = {
    Punjabi: (text.match(/[\u0A00-\u0A7F]/g) ?? []).length,
    Hindi: (text.match(/[\u0900-\u097F]/g) ?? []).length,
    Urdu: (text.match(/[\u0600-\u06FF]/g) ?? []).length,
    Latin: (text.match(/[A-Za-z]/g) ?? []).length,
  };
  const nonZero = Object.entries(counts).filter(([, count]) => count > 2).sort((a, b) => b[1] - a[1]);
  if (nonZero.length > 1 && nonZero[1][1] > nonZero[0][1] * 0.22) return "Mixed";
  if (nonZero[0]?.[0] === "Punjabi") return "Punjabi";
  if (nonZero[0]?.[0] === "Hindi") return "Hindi";
  if (nonZero[0]?.[0] === "Urdu") return "Urdu";
  return "Roman/Latin";
}

function detectedScripts(text: string): string[] {
  const scripts: string[] = [];
  if (/[\u0A00-\u0A7F]/.test(text)) scripts.push("Gurmukhi");
  if (/[\u0900-\u097F]/.test(text)) scripts.push("Devanagari");
  if (/[\u0600-\u06FF]/.test(text)) scripts.push("Perso-Arabic");
  if (/[A-Za-z]/.test(text)) scripts.push("Latin");
  return scripts;
}

export function analysePoetryFeatures(poetry: string): PoetryFeatures {
  const normalised = normaliseText(poetry);
  const tokens = normalised.split(/\s+/).filter(Boolean);
  const lines = poetry.split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
  const lineLengths = lines.length ? lines.map((line) => normaliseText(line).split(/\s+/).filter(Boolean).length) : [tokens.length];
  const mean = lineLengths.reduce((sum, value) => sum + value, 0) / Math.max(1, lineLengths.length);
  const variance = lineLengths.reduce((sum, value) => sum + (value - mean) ** 2, 0) / Math.max(1, lineLengths.length);

  const scores = Object.fromEntries(RASA_KEYS.map((key) => [key, 0.04])) as Record<RasaKey, number>;
  const evidence: PoetryFeatures["evidence"] = [];
  for (const rasa of RASA_KEYS) {
    for (const [term, weight] of RASA_LEXICON[rasa]) {
      const termNormalised = normaliseText(term);
      const hits = tokens.filter((token) => token === termNormalised || token.includes(termNormalised)).length;
      if (!hits) continue;
      const contribution = Math.min(2.5, hits * weight);
      scores[rasa] += contribution;
      evidence.push({ token: term, rasa, weight: contribution });
    }
  }

  const sum = Object.values(scores).reduce((total, value) => total + value, 0) || 1;
  const rasaVector = RASA_KEYS.map((key) => scores[key] / sum);
  const ranked = RASA_KEYS.map((key, index) => ({ key, value: rasaVector[index] })).sort((a, b) => b.value - a.value);
  const timeImagery = [...new Set(TIME_TERMS.filter(([term]) => normalised.includes(normaliseText(term))).map(([, value]) => value))];
  const seasonImagery = [...new Set(SEASON_TERMS.filter(([term]) => normalised.includes(normaliseText(term))).map(([, value]) => value))];
  const themeEntries = evidence.sort((a, b) => b.weight - a.weight).slice(0, 8);
  const themes = [...new Set(themeEntries.map((item) => item.rasa))].slice(0, 5);

  return {
    language: detectLanguage(poetry),
    scripts: detectedScripts(poetry),
    wordCount: tokens.length,
    lineCount: lines.length || 1,
    averageWordsPerLine: Number(mean.toFixed(1)),
    cadenceVariation: Number(Math.sqrt(variance).toFixed(2)),
    rasaVector,
    primaryRasa: ranked[0].key,
    secondaryRasa: ranked[1].key,
    themes,
    evidence: themeEntries,
    timeImagery,
    seasonImagery,
    devotionalSignal: rasaVector[RASA_KEYS.indexOf("bhakti")],
    romanticSignal: rasaVector[RASA_KEYS.indexOf("shringara")],
  };
}

function cosineSimilarity(a: number[], b: number[]): number {
  const length = Math.max(a.length, b.length);
  let dot = 0;
  let aa = 0;
  let bb = 0;
  for (let index = 0; index < length; index += 1) {
    const av = Number(a[index] ?? 0);
    const bv = Number(b[index] ?? 0);
    dot += av * bv;
    aa += av * av;
    bb += bv * bv;
  }
  if (!aa || !bb) return 0;
  return dot / Math.sqrt(aa * bb);
}

function clamp(value: number, min = 0, max = 100): number {
  return Math.min(max, Math.max(min, value));
}

function timeCompatibility(raag: RaagRecord, features: PoetryFeatures, preferredTime?: string | null): { score: number; reason: string } {
  const targetTerms = [...features.timeImagery, ...(preferredTime ? [preferredTime.toLowerCase()] : [])];
  if (!targetTerms.length) return { score: 5, reason: "No explicit performance-time constraint was supplied." };
  const time = (raag.time ?? "").toLowerCase();
  const match = targetTerms.some((term) => time.includes(term));
  return match
    ? { score: 10, reason: `The verse or user constraint points toward ${targetTerms.join(" / ")}, compatible with the profile.` }
    : { score: 2, reason: `Time imagery does not directly match ${raag.time ?? "the documented time profile"}.` };
}

function seasonCompatibility(raag: RaagRecord, features: PoetryFeatures): { score: number; reason: string } {
  if (!features.seasonImagery.length) return { score: 4, reason: "No strong seasonal image was detected." };
  const text = `${raag.displayName} ${raag.contextLogic ?? ""} ${raag.time ?? ""}`.toLowerCase();
  const match = features.seasonImagery.some((term) => text.includes(term) || (term === "monsoon" && /(malhar|desh|megh)/i.test(text)) || (term === "spring" && /(basant|bahar)/i.test(text)));
  return match
    ? { score: 8, reason: `Seasonal imagery (${features.seasonImagery.join(", ")}) aligns with the Raag family or context.` }
    : { score: 2, reason: `The seasonal image is not a primary association in this record.` };
}

function formCompatibility(raag: RaagRecord, preferredForm?: string | null): { score: number; reason: string } {
  if (!preferredForm) return { score: 6, reason: "No musical form was locked; broad suitability was retained." };
  const form = preferredForm.toLowerCase();
  const match = raag.recommendedForms.some((value) => value.toLowerCase().includes(form) || form.includes(value.toLowerCase()));
  return match
    ? { score: 10, reason: `${preferredForm} appears in the record’s suitable-form set.` }
    : { score: 3, reason: `${preferredForm} is not established in the current suitable-form data.` };
}

export function rankRaags(
  features: PoetryFeatures,
  raags: RaagRecord[],
  constraints: RecommendationConstraints = {},
): RaagCandidate[] {
  const generationReady = raags.filter((record) => record.generationReady && record.rasaVector.some((value) => value > 0));
  const candidates = generationReady.map((raag) => {
    const rasaSimilarity = cosineSimilarity(features.rasaVector, raag.rasaVector);
    const rasaScore = Math.round(rasaSimilarity * 42);
    const time = timeCompatibility(raag, features, constraints.preferredTime);
    const season = seasonCompatibility(raag, features);
    const form = formCompatibility(raag, constraints.preferredForm);
    const dataScore = Math.round((raag.dataCompleteness / 100) * 14);
    const contextText = `${raag.primaryRasa ?? ""} ${raag.contextLogic ?? ""} ${raag.prakriti ?? ""}`.toLowerCase();
    const contextHits = features.themes.filter((theme) => contextText.includes(theme)).length;
    const contextScore = Math.min(12, 4 + contextHits * 3);
    const locked = constraints.lockedRaagId && raag.id === slugify(constraints.lockedRaagId) ? 12 : 0;
    const total = clamp(rasaScore + time.score + season.score + form.score + dataScore + contextScore + locked);
    const components: ScoreComponent[] = [
      { key: "rasa", label: "Bhava compatibility", score: rasaScore, max: 42, reason: `Cosine similarity between the nine-dimensional verse and Raag affect vectors: ${rasaSimilarity.toFixed(2)}.` },
      { key: "time", label: "Time imagery", score: time.score, max: 10, reason: time.reason },
      { key: "season", label: "Seasonal context", score: season.score, max: 8, reason: season.reason },
      { key: "form", label: "Form suitability", score: form.score, max: 10, reason: form.reason },
      { key: "context", label: "Textual context", score: contextScore, max: 12, reason: contextHits ? `${contextHits} interpreted theme(s) appear in the Raag context record.` : "No direct keyword shortcut was used; the vector score carries more weight." },
      { key: "data", label: "Knowledge quality", score: dataScore, max: 14, reason: `${raag.dataCompleteness}% of the target schema is populated.` },
      { key: "constraint", label: "User lock", score: locked, max: 12, reason: locked ? "The musician explicitly locked this Raag." : "No lock bonus applied." },
    ];
    return {
      id: raag.id,
      name: raag.displayName,
      fitScore: Math.round(total),
      components,
      explanation: `${raag.displayName} aligns most strongly through ${raag.primaryRasa ?? "its affective profile"}; ${time.reason.toLowerCase()}`,
      caveat: raag.reviewStatus === "needs-expert-review"
        ? "The record is structurally usable but still marked for expert review; treat this as a proposal, not an authority."
        : "Multiple Raags can remain musically valid for the same verse.",
      verification: raag.verification,
      dataCompleteness: raag.dataCompleteness,
    };
  });

  return candidates.sort((a, b) => b.fitScore - a.fitScore || b.dataCompleteness - a.dataCompleteness).slice(0, 8);
}

function estimateTaalTarget(features: PoetryFeatures): number {
  const words = features.averageWordsPerLine;
  if (words <= 4) return 6;
  if (words <= 7) return 8;
  if (words <= 10) return 10;
  if (words <= 13) return 12;
  if (words <= 17) return 14;
  return 16;
}

function layaCompatibility(taal: TaalRecord, desired?: string | null): { score: number; reason: string } {
  if (!desired) return { score: 7, reason: "No Laya was locked." };
  const match = taal.suitableLaya.some((value) => value.toLowerCase() === desired.toLowerCase());
  return match ? { score: 12, reason: `${desired} is present in the Taal record.` } : { score: 3, reason: `${desired} is not a primary Laya in this record.` };
}

export function rankTaals(
  features: PoetryFeatures,
  taals: TaalRecord[] = PRACTICAL_TAALS,
  raag?: RaagRecord,
  constraints: RecommendationConstraints = {},
): TaalCandidate[] {
  const target = estimateTaalTarget(features);
  const preferred = new Set((raag?.recommendedTaals ?? []).map(slugify));
  return taals
    .filter((taal) => taal.generationReady)
    .map((taal) => {
      const distance = Math.abs(taal.beats - target);
      const cadenceScore = Math.max(4, 34 - distance * 5);
      const lineBalanceScore = features.cadenceVariation < 2.5
        ? (taal.divisions.every((division) => division === taal.divisions[0]) ? 15 : 9)
        : (new Set(taal.divisions).size > 1 ? 15 : 9);
      const raagScore = preferred.has(taal.id) ? 18 : 7;
      const laya = layaCompatibility(taal, constraints.desiredLaya);
      const form = constraints.preferredForm
        ? (taal.suitableForms.some((value) => value.toLowerCase().includes(constraints.preferredForm!.toLowerCase())) ? 12 : 3)
        : 7;
      const dataScore = Math.round((taal.dataCompleteness / 100) * 12);
      const locked = constraints.lockedTaalId && taal.id === slugify(constraints.lockedTaalId) ? 14 : 0;
      const total = clamp(cadenceScore + lineBalanceScore + raagScore + laya.score + form + dataScore + locked);
      const components: ScoreComponent[] = [
        { key: "cadence", label: "Line-length fit", score: cadenceScore, max: 34, reason: `The verse suggests a working target near ${target} matras; ${taal.name} has ${taal.beats}.` },
        { key: "division", label: "Vibhag shape", score: lineBalanceScore, max: 15, reason: features.cadenceVariation < 2.5 ? "The verse has relatively balanced line lengths." : "The verse has uneven line lengths, favouring a more asymmetric cycle." },
        { key: "raag", label: "Raag/form context", score: raagScore, max: 18, reason: preferred.has(taal.id) ? `${taal.name} is included in the selected Raag’s suitable-Taal set.` : "No fixed Raag-to-Taal mapping was imposed." },
        { key: "laya", label: "Laya suitability", score: laya.score, max: 12, reason: laya.reason },
        { key: "form", label: "Form suitability", score: form, max: 12, reason: constraints.preferredForm ? `Compared against the selected ${constraints.preferredForm} form.` : "No form was locked." },
        { key: "data", label: "Knowledge quality", score: dataScore, max: 12, reason: `${taal.dataCompleteness}% schema completeness.` },
        { key: "constraint", label: "User lock", score: locked, max: 14, reason: locked ? "The musician explicitly locked this Taal." : "No lock bonus applied." },
      ];
      return {
        id: taal.id,
        name: taal.name,
        fitScore: Math.round(total),
        beats: taal.beats,
        divisions: taal.divisions,
        components,
        explanation: `${taal.name} offers a ${taal.divisions.join("+")} division pattern for the verse’s estimated cadence; it was ranked independently from the Raag.` ,
        caveat: taal.verification === "variant-sensitive" ? "Theka realisation varies; review the selected variant before performance." : "Poetic metre and musical Taal are related but not identical systems.",
        verification: taal.verification,
      };
    })
    .sort((a, b) => b.fitScore - a.fitScore)
    .slice(0, 8);
}

export function runMusicologyAnalysisFromFeatures(
  poetry: string,
  features: PoetryFeatures,
  raags: RaagRecord[],
  constraints: RecommendationConstraints = {},
  taals: TaalRecord[] = PRACTICAL_TAALS,
  semantic: SemanticMetadata = {
    engine: "offline-heuristic",
    confidence: 0.45,
    summary: "Offline multilingual evidence matching was used because no external semantic model was configured.",
    form: "unknown",
  },
): MusicologyAnalysis {
  void poetry;
  const raagCandidates = rankRaags(features, raags, constraints);
  const lockedRaagId = constraints.lockedRaagId ?? null;
  const selectedRaagCandidate = lockedRaagId
    ? raagCandidates.find((candidate) => candidate.id === slugify(lockedRaagId)) ?? raagCandidates[0]
    : raagCandidates[0];
  const selectedRaag = raags.find((record) => record.id === selectedRaagCandidate?.id);
  const taalCandidates = rankTaals(features, taals, selectedRaag, constraints);
  const lockedTaalId = constraints.lockedTaalId ?? null;
  const selectedTaalCandidate = lockedTaalId
    ? taalCandidates.find((candidate) => candidate.id === slugify(lockedTaalId)) ?? taalCandidates[0]
    : taalCandidates[0];
  if (!selectedRaagCandidate || !selectedTaalCandidate) throw new Error("The knowledge library does not contain enough generation-ready records.");

  const uncertainty: string[] = [
    "The displayed score is a transparent heuristic fit score, not a statistical probability of musical correctness.",
    "A poem can support several valid Raag and Taal interpretations depending on form, Gharana, voice and artistic intention.",
  ];
  if (features.evidence.length < 2) uncertainty.push("Few explicit affective cues were detected, so the ranking relies more heavily on general structure and data quality.");
  if (selectedRaag?.reviewStatus === "needs-expert-review") uncertainty.push("The selected Raag record is marked for expert review in the knowledge register.");

  return {
    analysisVersion: "maqam-neuro-symbolic-ranker-v10",
    scoreMeaning: "heuristic-fit-not-probability",
    semanticEngine: semantic.engine,
    semanticConfidence: Math.max(0, Math.min(1, semantic.confidence)),
    semanticSummary: semantic.summary,
    semanticForm: semantic.form ?? "unknown",
    semanticModel: semantic.model ?? null,
    features,
    raagCandidates,
    taalCandidates,
    recommendation: {
      raagId: selectedRaagCandidate.id,
      raagName: selectedRaagCandidate.name,
      taalId: selectedTaalCandidate.id,
      taalName: selectedTaalCandidate.name,
      score: Math.round((selectedRaagCandidate.fitScore + selectedTaalCandidate.fitScore) / 2),
    },
    uncertainty,
    methodology: [
      semantic.engine === "gemini-structured"
        ? "Use server-side Gemini structured output only for language, form, imagery and Rasa/Bhava interpretation."
        : "Use the offline multilingual lexicon fallback for script, evidence and Rasa/Bhava interpretation.",
      "Never permit the language model to select or certify a Raag, Taal or musical phrase directly.",
      "Rank Raags by affect-vector similarity, context, time/season constraints and knowledge completeness.",
      "Rank Taals independently from line cadence, vibhag shape, form and Laya constraints.",
      "Keep manual locks authoritative and audit notation with a separate symbolic grammar engine.",
    ],
  };
}

export function runMusicologyAnalysis(
  poetry: string,
  raags: RaagRecord[],
  constraints: RecommendationConstraints = {},
  taals: TaalRecord[] = PRACTICAL_TAALS,
): MusicologyAnalysis {
  const features = analysePoetryFeatures(poetry);
  return runMusicologyAnalysisFromFeatures(poetry, features, raags, constraints, taals);
}
