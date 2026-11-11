import { extractPhraseTokens } from "../data/knowledge";
import type { RaagRecord, TaalRecord } from "../data/types";

export type Saptak = "mandra" | "madhya" | "taar";
export type Ornament = "none" | "meend" | "murki" | "khatka" | "andolan" | "gamak";

export interface NotationEvent {
  swar: string;
  bol: string;
  saptak: Saptak;
  ornament: Ornament;
  kan: string;
  locked?: boolean;
}

export type DiagnosticSeverity = "pass" | "info" | "warn" | "fail";

export interface GrammarDiagnostic {
  id: string;
  label: string;
  severity: DiagnosticSeverity;
  value: string;
  detail: string;
  affectedBeats: number[];
}

const PITCH_INDEX: Record<string, number> = {
  S: 0,
  r: 1,
  R: 2,
  g: 3,
  G: 4,
  m: 5,
  M: 6,
  P: 7,
  d: 8,
  D: 9,
  n: 10,
  N: 11,
};

function notePitch(event: NotationEvent): number | null {
  const base = PITCH_INDEX[event.swar];
  if (base === undefined) return null;
  const offset = event.saptak === "mandra" ? -12 : event.saptak === "taar" ? 12 : 0;
  return base + offset;
}

function phraseContains(sequence: string[], phrase: string[]): boolean {
  if (!phrase.length || sequence.length < phrase.length) return false;
  for (let start = 0; start <= sequence.length - phrase.length; start += 1) {
    if (phrase.every((note, index) => sequence[start + index] === note)) return true;
  }
  return false;
}

function longestOrderedMatch(sequence: string[], phrase: string[]): number {
  let best = 0;
  for (let start = 0; start < sequence.length; start += 1) {
    let phraseIndex = 0;
    for (let index = start; index < sequence.length && phraseIndex < phrase.length; index += 1) {
      if (sequence[index] === phrase[phraseIndex]) phraseIndex += 1;
    }
    best = Math.max(best, phraseIndex);
  }
  return best;
}

export function validatePhrase(
  notation: NotationEvent[],
  raag: RaagRecord,
  taal: TaalRecord,
): GrammarDiagnostic[] {
  const filled = notation
    .map((event, beat) => ({ event, beat, pitch: notePitch(event) }))
    .filter((item) => item.event.swar && item.pitch !== null);
  const swars = filled.map((item) => item.event.swar);
  const diagnostics: GrammarDiagnostic[] = [];

  const forbidden = filled.filter((item) => raag.forbiddenSwars.includes(item.event.swar));
  diagnostics.push({
    id: "swar-set",
    label: "Swar-set integrity",
    severity: forbidden.length ? "fail" : "pass",
    value: forbidden.length ? `${forbidden.length} exception${forbidden.length === 1 ? "" : "s"}` : "Within working profile",
    detail: forbidden.length
      ? `The phrase contains ${[...new Set(forbidden.map((item) => item.event.swar))].join(", ")}, outside the current Raag profile.`
      : "All entered Swars belong to the selected working profile.",
    affectedBeats: forbidden.map((item) => item.beat),
  });

  const vadiBeats = raag.vadiSwar ? filled.filter((item) => item.event.swar === raag.vadiSwar).map((item) => item.beat) : [];
  const samvadiBeats = raag.samvadiSwar ? filled.filter((item) => item.event.swar === raag.samvadiSwar).map((item) => item.beat) : [];
  diagnostics.push({
    id: "tonal-hierarchy",
    label: "Vadi–Samvadi emphasis",
    severity: vadiBeats.length && samvadiBeats.length ? "pass" : vadiBeats.length ? "info" : "warn",
    value: `${vadiBeats.length}/${samvadiBeats.length} occurrences`,
    detail: raag.vadiSwar && raag.samvadiSwar
      ? `${raag.vadi ?? raag.vadiSwar} and ${raag.samvadi ?? raag.samvadiSwar} are checked separately; simple occurrence does not prove correct treatment.`
      : "The imported record does not specify a complete Vadi–Samvadi pair.",
    affectedBeats: [...vadiBeats, ...samvadiBeats],
  });

  const signatures = raag.signaturePhrases.filter((phrase) => phrase.length >= 3);
  const exactSignature = signatures.find((phrase) => phraseContains(swars, phrase));
  const bestPartial = signatures.reduce((best, phrase) => Math.max(best, longestOrderedMatch(swars, phrase) / phrase.length), 0);
  diagnostics.push({
    id: "pakad",
    label: "Pakad / characteristic contact",
    severity: exactSignature ? "pass" : bestPartial >= 0.66 ? "info" : "warn",
    value: exactSignature ? exactSignature.join(" ") : signatures.length ? `${Math.round(bestPartial * 100)}% ordered contact` : "Not encoded",
    detail: exactSignature
      ? "A characteristic phrase fragment occurs in the entered sequence."
      : signatures.length
        ? "The phrase uses allowed Swars but has not yet established a strong characteristic contour."
        : "No machine-readable Pakad phrase is available in this record.",
    affectedBeats: [],
  });

  let ascending = 0;
  let descending = 0;
  let largeLeaps = 0;
  const leapBeats: number[] = [];
  for (let index = 1; index < filled.length; index += 1) {
    const previous = filled[index - 1];
    const current = filled[index];
    const delta = (current.pitch ?? 0) - (previous.pitch ?? 0);
    if (delta > 0) ascending += 1;
    if (delta < 0) descending += 1;
    if (Math.abs(delta) > 7) {
      largeLeaps += 1;
      leapBeats.push(current.beat);
    }
  }
  diagnostics.push({
    id: "contour",
    label: "Phrase contour",
    severity: largeLeaps > Math.max(1, filled.length / 4) ? "warn" : "pass",
    value: `↑${ascending} · ↓${descending} · ${largeLeaps} wide leap${largeLeaps === 1 ? "" : "s"}`,
    detail: largeLeaps
      ? "Wide leaps are not automatically wrong, but they should be checked against Chalan and Gharana-specific movement."
      : "The contour is predominantly conjunct at the current resolution.",
    affectedBeats: leapBeats,
  });

  const lastFilled = filled.at(-1);
  const nyasSet = new Set(raag.nyasSwars);
  const stableEnding = Boolean(lastFilled && nyasSet.has(lastFilled.event.swar));
  diagnostics.push({
    id: "nyas",
    label: "Phrase-ending stability",
    severity: stableEnding ? "pass" : lastFilled ? "info" : "warn",
    value: lastFilled ? `${lastFilled.event.swar} at matra ${lastFilled.beat + 1}` : "No ending",
    detail: stableEnding
      ? "The phrase closes on a documented Nyas candidate."
      : `The current ending is not in the working Nyas set (${raag.nyasSwars.join(", ") || "not documented"}). This may still be valid inside a longer passage.`,
    affectedBeats: lastFilled ? [lastFilled.beat] : [],
  });

  const ornamentWarnings: number[] = [];
  for (const item of filled) {
    if (item.event.ornament === "andolan" && !raag.andolan[item.event.swar]) ornamentWarnings.push(item.beat);
    if (item.event.ornament === "meend" && item.beat === notation.length - 1) ornamentWarnings.push(item.beat);
    if (item.event.kan && !raag.allowedSwars.includes(item.event.kan)) ornamentWarnings.push(item.beat);
  }
  diagnostics.push({
    id: "ornaments",
    label: "Ornament context",
    severity: ornamentWarnings.length ? "warn" : "pass",
    value: ornamentWarnings.length ? `${ornamentWarnings.length} review point${ornamentWarnings.length === 1 ? "" : "s"}` : "No obvious conflict",
    detail: ornamentWarnings.length
      ? "An ornament lacks an encoded Raag-specific rule, ends without a target, or uses a Kan outside the profile."
      : "Encoded ornament checks found no direct contradiction. Absence of a warning is not a performance endorsement.",
    affectedBeats: ornamentWarnings,
  });

  const taalLengthValid = notation.length === taal.beats;
  const divisionTotal = taal.divisions.reduce((sum, division) => sum + division, 0);
  diagnostics.push({
    id: "taal-structure",
    label: "Taal cycle structure",
    severity: taalLengthValid && divisionTotal === taal.beats ? "pass" : "fail",
    value: `${notation.length}/${taal.beats} matras · ${taal.divisions.join("+")}`,
    detail: taalLengthValid && divisionTotal === taal.beats
      ? "The event grid and Vibhag totals match the selected cycle."
      : "The event grid or division total does not match the selected Taal definition.",
    affectedBeats: [],
  });

  const bolBeats = notation.map((event, beat) => event.bol.trim() ? beat : -1).filter((beat) => beat >= 0);
  diagnostics.push({
    id: "bol-alignment",
    label: "Bol alignment",
    severity: bolBeats.length === 0 ? "info" : bolBeats.length >= Math.min(taal.beats, 4) ? "pass" : "warn",
    value: `${bolBeats.length}/${taal.beats} occupied matras`,
    detail: bolBeats.length
      ? "Bol occupancy is measured, but syllabic weight and poetic metre still require musical judgement."
      : "No lyrics are aligned to the active cycle.",
    affectedBeats: bolBeats,
  });

  const samEvent = notation[0];
  diagnostics.push({
    id: "sam",
    label: "Sam landing",
    severity: samEvent?.swar || samEvent?.bol ? "pass" : "info",
    value: samEvent?.swar || samEvent?.bol || "Open",
    detail: samEvent?.swar || samEvent?.bol
      ? "The cycle has an explicit event on Sam. Musical emphasis still depends on duration and approach."
      : "Sam is currently empty; this can be intentional but should be reviewed.",
    affectedBeats: [0],
  });

  return diagnostics;
}

export function grammarScore(diagnostics: GrammarDiagnostic[]): number {
  const weights: Record<DiagnosticSeverity, number> = { pass: 1, info: 0.72, warn: 0.4, fail: 0 };
  if (!diagnostics.length) return 0;
  return Math.round((diagnostics.reduce((sum, item) => sum + weights[item.severity], 0) / diagnostics.length) * 100);
}

export function makeSeedNotation(raag: RaagRecord, taal: TaalRecord): NotationEvent[] {
  const source = raag.defaultNotation.length
    ? raag.defaultNotation
    : [...extractPhraseTokens(raag.aaroh), ...extractPhraseTokens(raag.avroh)];
  return Array.from({ length: taal.beats }, (_, index) => ({
    swar: source[index % Math.max(1, source.length)] ?? "",
    bol: "",
    saptak: index === taal.beats - 1 && source[index % Math.max(1, source.length)] === "S" ? "taar" : "madhya",
    ornament: "none",
    kan: "",
    locked: false,
  }));
}
