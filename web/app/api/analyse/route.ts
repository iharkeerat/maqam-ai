import { NextResponse } from "next/server";
import { BUILT_IN_RAAGS, PRACTICAL_TAALS, mergeRaagLibraries, mergeTaalLibraries } from "../../data/knowledge";
import type { RaagRecord, TaalRecord } from "../../data/types";
import { analysePoetryFeatures, runMusicologyAnalysisFromFeatures, type RecommendationConstraints } from "../../lib/musicology-engine";
import { analyseWithGemini, mergeSemanticProfile } from "../../lib/semantic-ai";

interface RequestBody {
  poetry?: string;
  constraints?: RecommendationConstraints;
  importedRaags?: RaagRecord[];
  importedTaals?: TaalRecord[];
}

function safeImportedRecords(records: unknown): RaagRecord[] {
  if (!Array.isArray(records)) return [];
  return records
    .slice(0, 320)
    .filter((record): record is RaagRecord => Boolean(
      record
      && typeof record === "object"
      && typeof (record as RaagRecord).id === "string"
      && typeof (record as RaagRecord).displayName === "string"
      && Array.isArray((record as RaagRecord).rasaVector)
      && Array.isArray((record as RaagRecord).allowedSwars),
    ))
    .map((record) => {
      const allowedSwars = record.allowedSwars.slice(0, 12);
      const rasaVector = record.rasaVector.slice(0, 9).map((value) => Math.max(0, Math.min(1, Number(value) || 0)));
      return {
        ...record,
        id: record.id.slice(0, 80),
        displayName: record.displayName.slice(0, 120),
        aliases: Array.isArray(record.aliases) ? record.aliases.slice(0, 12).map((value) => String(value).slice(0, 120)) : [],
        rasaVector,
        allowedSwars,
        forbiddenSwars: Array.isArray(record.forbiddenSwars) ? record.forbiddenSwars.slice(0, 12) : [],
        signaturePhrases: Array.isArray(record.signaturePhrases) ? record.signaturePhrases.slice(0, 12) : [],
        generationReady: Boolean(record.aaroh && record.avroh && record.pakad && allowedSwars.length >= 4 && rasaVector.some((value) => value > 0)),
        provenance: ["client-imported-master"],
      };
    });
}

function safeImportedTaals(records: unknown): TaalRecord[] {
  if (!Array.isArray(records)) return [];
  return records
    .slice(0, 240)
    .filter((record): record is TaalRecord => Boolean(
      record
      && typeof record === "object"
      && typeof (record as TaalRecord).id === "string"
      && typeof (record as TaalRecord).name === "string"
      && Number.isFinite((record as TaalRecord).beats)
      && Array.isArray((record as TaalRecord).divisions),
    ))
    .map((record) => {
      const beats = Math.max(1, Math.min(128, Math.round(Number(record.beats) || 1)));
      const divisions = record.divisions.slice(0, 32).map((value) => Math.max(1, Math.round(Number(value) || 1)));
      const structurallyValid = divisions.length > 0 && divisions.reduce((sum, value) => sum + value, 0) === beats;
      return {
        ...record,
        id: record.id.slice(0, 80),
        name: record.name.slice(0, 120),
        aliases: Array.isArray(record.aliases) ? record.aliases.slice(0, 12).map((value) => String(value).slice(0, 120)) : [],
        beats,
        divisions,
        marks: Array.isArray(record.marks) ? record.marks.slice(0, 32).map((value) => String(value).slice(0, 12)) : [],
        suitableForms: Array.isArray(record.suitableForms) ? record.suitableForms.slice(0, 20).map(String) : [],
        suitableLaya: Array.isArray(record.suitableLaya) ? record.suitableLaya.slice(0, 12).map(String) : [],
        generationReady: Boolean(record.theka && structurallyValid && beats <= 32),
        provenance: ["client-imported-master"],
      };
    });
}

export async function POST(request: Request) {
  let body: RequestBody;
  try {
    body = (await request.json()) as RequestBody;
  } catch {
    return NextResponse.json({ error: "The analysis request is not valid JSON." }, { status: 400 });
  }

  const poetry = body.poetry?.trim();
  if (!poetry) return NextResponse.json({ error: "Poetry is required." }, { status: 400 });
  if (poetry.length > 12_000) return NextResponse.json({ error: "Keep the verse under 12,000 characters." }, { status: 413 });

  try {
    const library = mergeRaagLibraries(BUILT_IN_RAAGS, safeImportedRecords(body.importedRaags));
    const taalLibrary = mergeTaalLibraries(PRACTICAL_TAALS, safeImportedTaals(body.importedTaals));
    const offlineFeatures = analysePoetryFeatures(poetry);
    const model = process.env.GEMINI_MODEL?.trim() || "gemini-3.6-flash";

    if (process.env.GEMINI_API_KEY?.trim()) {
      try {
        const semantic = await analyseWithGemini(poetry);
        const features = mergeSemanticProfile(offlineFeatures, semantic);
        const result = runMusicologyAnalysisFromFeatures(poetry, features, library, body.constraints ?? {}, taalLibrary, {
          engine: "gemini-structured",
          confidence: semantic.confidence,
          summary: semantic.summary,
          form: semantic.form,
          model,
        });
        return NextResponse.json(result);
      } catch (semanticError) {
        const reason = semanticError instanceof Error ? semanticError.message : "unknown semantic-model error";
        const result = runMusicologyAnalysisFromFeatures(poetry, offlineFeatures, library, body.constraints ?? {}, taalLibrary, {
          engine: "offline-heuristic",
          confidence: 0.4,
          summary: `Gemini was configured but unavailable, so the deterministic multilingual fallback was used. ${reason.slice(0, 220)}`,
          form: body.constraints?.preferredForm || "unknown",
        });
        result.uncertainty.push("The configured semantic model failed during this request; inspect the server log and API health endpoint before treating the interpretation as AI-assisted.");
        return NextResponse.json(result);
      }
    }

    const result = runMusicologyAnalysisFromFeatures(poetry, offlineFeatures, library, body.constraints ?? {}, taalLibrary, {
      engine: "offline-heuristic",
      confidence: 0.45,
      summary: "No server-side Gemini key is configured. The transparent multilingual lexicon fallback interpreted the verse.",
      form: body.constraints?.preferredForm || "unknown",
    });
    return NextResponse.json(result);
  } catch (error) {
    const message = error instanceof Error ? error.message : "Analysis failed.";
    return NextResponse.json({ error: message }, { status: 422 });
  }
}
