import { RASA_KEYS, type RasaKey } from "../data/types";
import type { PoetryFeatures } from "./musicology-engine";

export interface SemanticEvidence {
  text: string;
  interpretation: string;
  rasa: RasaKey;
  confidence: number;
}

export interface SemanticPoetryProfile {
  language: "Punjabi" | "Hindi" | "Urdu" | "Roman/Latin" | "Mixed";
  scripts: string[];
  form: string;
  rasaVector: number[];
  primaryRasa: RasaKey;
  secondaryRasa: RasaKey;
  themes: string[];
  evidence: SemanticEvidence[];
  timeImagery: string[];
  seasonImagery: string[];
  devotionalSignal: number;
  romanticSignal: number;
  summary: string;
  confidence: number;
}

const RASA_ENUM = [...RASA_KEYS];

const SEMANTIC_SCHEMA = {
  type: "object",
  additionalProperties: false,
  properties: {
    language: { type: "string", enum: ["Punjabi", "Hindi", "Urdu", "Roman/Latin", "Mixed"] },
    scripts: { type: "array", minItems: 1, maxItems: 5, items: { type: "string" } },
    form: { type: "string", description: "Likely poetic or performance form; use unknown when evidence is insufficient." },
    rasaVector: {
      type: "array",
      minItems: 9,
      maxItems: 9,
      items: { type: "number", minimum: 0, maximum: 1 },
      description: "Exactly nine scores ordered as karuna, bhakti, shringara, vira, raudra, bhayanaka, bibhatsa, adbhuta, shanta.",
    },
    primaryRasa: { type: "string", enum: RASA_ENUM },
    secondaryRasa: { type: "string", enum: RASA_ENUM },
    themes: { type: "array", maxItems: 8, items: { type: "string" } },
    evidence: {
      type: "array",
      maxItems: 10,
      items: {
        type: "object",
        additionalProperties: false,
        properties: {
          text: { type: "string" },
          interpretation: { type: "string" },
          rasa: { type: "string", enum: RASA_ENUM },
          confidence: { type: "number", minimum: 0, maximum: 1 },
        },
        required: ["text", "interpretation", "rasa", "confidence"],
      },
    },
    timeImagery: { type: "array", maxItems: 5, items: { type: "string" } },
    seasonImagery: { type: "array", maxItems: 5, items: { type: "string" } },
    devotionalSignal: { type: "number", minimum: 0, maximum: 1 },
    romanticSignal: { type: "number", minimum: 0, maximum: 1 },
    summary: { type: "string" },
    confidence: { type: "number", minimum: 0, maximum: 1 },
  },
  required: [
    "language", "scripts", "form", "rasaVector", "primaryRasa", "secondaryRasa", "themes",
    "evidence", "timeImagery", "seasonImagery", "devotionalSignal", "romanticSignal", "summary", "confidence",
  ],
};

function clamp01(value: unknown): number {
  return Math.max(0, Math.min(1, Number(value) || 0));
}

function isRasa(value: unknown): value is RasaKey {
  return typeof value === "string" && RASA_KEYS.includes(value as RasaKey);
}

function findJsonText(value: unknown, depth = 0): string | null {
  if (depth > 8 || value == null) return null;
  if (typeof value === "string") {
    const trimmed = value.trim();
    if (trimmed.startsWith("{") && trimmed.endsWith("}")) return trimmed;
    return null;
  }
  if (Array.isArray(value)) {
    for (const item of value) {
      const found = findJsonText(item, depth + 1);
      if (found) return found;
    }
    return null;
  }
  if (typeof value === "object") {
    const object = value as Record<string, unknown>;
    for (const key of ["output_text", "outputText", "text", "content"]) {
      const found = findJsonText(object[key], depth + 1);
      if (found) return found;
    }
    for (const nested of Object.values(object)) {
      const found = findJsonText(nested, depth + 1);
      if (found) return found;
    }
  }
  return null;
}

function validateProfile(raw: unknown): SemanticPoetryProfile {
  if (!raw || typeof raw !== "object") throw new Error("Gemini returned an empty semantic profile.");
  const value = raw as Record<string, unknown>;
  const language = ["Punjabi", "Hindi", "Urdu", "Roman/Latin", "Mixed"].includes(String(value.language))
    ? value.language as SemanticPoetryProfile["language"]
    : "Mixed";
  const vector = Array.isArray(value.rasaVector) ? value.rasaVector.slice(0, 9).map(clamp01) : [];
  while (vector.length < 9) vector.push(0);
  const primaryRasa = isRasa(value.primaryRasa) ? value.primaryRasa : RASA_KEYS[vector.indexOf(Math.max(...vector))] ?? "shanta";
  const secondaryRasa = isRasa(value.secondaryRasa) ? value.secondaryRasa : "shanta";
  const evidence = Array.isArray(value.evidence)
    ? value.evidence.slice(0, 10).flatMap((item): SemanticEvidence[] => {
        if (!item || typeof item !== "object") return [];
        const record = item as Record<string, unknown>;
        if (!isRasa(record.rasa)) return [];
        return [{
          text: String(record.text ?? "").slice(0, 160),
          interpretation: String(record.interpretation ?? "").slice(0, 320),
          rasa: record.rasa,
          confidence: clamp01(record.confidence),
        }];
      })
    : [];
  return {
    language,
    scripts: Array.isArray(value.scripts) ? value.scripts.slice(0, 5).map((item) => String(item).slice(0, 50)) : ["Unknown"],
    form: String(value.form ?? "unknown").slice(0, 100),
    rasaVector: vector,
    primaryRasa,
    secondaryRasa,
    themes: Array.isArray(value.themes) ? value.themes.slice(0, 8).map((item) => String(item).slice(0, 100)) : [],
    evidence,
    timeImagery: Array.isArray(value.timeImagery) ? value.timeImagery.slice(0, 5).map((item) => String(item).slice(0, 80).toLowerCase()) : [],
    seasonImagery: Array.isArray(value.seasonImagery) ? value.seasonImagery.slice(0, 5).map((item) => String(item).slice(0, 80).toLowerCase()) : [],
    devotionalSignal: clamp01(value.devotionalSignal),
    romanticSignal: clamp01(value.romanticSignal),
    summary: String(value.summary ?? "Semantic interpretation completed.").slice(0, 700),
    confidence: clamp01(value.confidence),
  };
}

export async function analyseWithGemini(poetry: string): Promise<SemanticPoetryProfile> {
  const apiKey = process.env.GEMINI_API_KEY?.trim();
  if (!apiKey) throw new Error("GEMINI_API_KEY is not configured.");
  const model = process.env.GEMINI_MODEL?.trim() || "gemini-3.6-flash";
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 18_000);
  const prompt = `You are the language-analysis layer of MAQAM AI, an explainable computational-musicology system for Punjabi, Hindi and Urdu poetry.\n\nInterpret the verse semantically, but DO NOT recommend a Raag, Taal, notation, Gharana or musical rule. Those decisions belong to a deterministic knowledge engine. Identify ambiguity rather than inventing certainty. Use the nine rasa keys in this exact order: karuna, bhakti, shringara, vira, raudra, bhayanaka, bibhatsa, adbhuta, shanta. Evidence snippets must occur in the submitted text.\n\nVERSE:\n${poetry}`;
  try {
    const response = await fetch("https://generativelanguage.googleapis.com/v1beta/interactions", {
      method: "POST",
      headers: { "Content-Type": "application/json", "x-goog-api-key": apiKey },
      body: JSON.stringify({
        model,
        input: prompt,
        response_format: { type: "text", mime_type: "application/json", schema: SEMANTIC_SCHEMA },
      }),
      signal: controller.signal,
      cache: "no-store",
    });
    const payload = await response.json() as unknown;
    if (!response.ok) {
      const message = payload && typeof payload === "object" ? JSON.stringify(payload).slice(0, 500) : "unknown error";
      throw new Error(`Gemini semantic request failed (${response.status}): ${message}`);
    }
    const jsonText = findJsonText(payload);
    if (!jsonText) throw new Error("Gemini response did not contain a readable structured JSON profile.");
    return validateProfile(JSON.parse(jsonText) as unknown);
  } finally {
    clearTimeout(timer);
  }
}

export function mergeSemanticProfile(base: PoetryFeatures, semantic: SemanticPoetryProfile): PoetryFeatures {
  return {
    ...base,
    language: semantic.language,
    scripts: semantic.scripts.length ? semantic.scripts : base.scripts,
    rasaVector: semantic.rasaVector,
    primaryRasa: semantic.primaryRasa,
    secondaryRasa: semantic.secondaryRasa,
    themes: semantic.themes,
    evidence: semantic.evidence.map((item) => ({ token: item.text, rasa: item.rasa, weight: item.confidence })),
    timeImagery: semantic.timeImagery,
    seasonImagery: semantic.seasonImagery,
    devotionalSignal: semantic.devotionalSignal,
    romanticSignal: semantic.romanticSignal,
  };
}
