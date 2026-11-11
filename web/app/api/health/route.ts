import { NextResponse } from "next/server";
import { BUILT_IN_RAAGS, HISTORICAL_TAALS, PRACTICAL_TAALS, RAAG_CATALOGUE } from "../../data/knowledge";

export async function GET() {
  const configured = Boolean(process.env.GEMINI_API_KEY?.trim());
  return NextResponse.json({
    status: "ok",
    edition: "MAQAM AI v10 — Research & Evaluation Edition",
    semanticEngine: configured ? "gemini-structured" : "offline-heuristic",
    semanticModel: configured ? (process.env.GEMINI_MODEL?.trim() || "gemini-3.6-flash") : null,
    knowledge: {
      deepRaags: BUILT_IN_RAAGS.filter((record) => record.generationReady).length,
      indexedRaags: RAAG_CATALOGUE.length,
      practicalTaals: PRACTICAL_TAALS.length,
      generationReadyTaals: PRACTICAL_TAALS.filter((record) => record.generationReady).length,
      historicalTaalRegistry: HISTORICAL_TAALS.length,
      secondaryAttestedHistoricalNames: HISTORICAL_TAALS.filter((record) => record.attestationLevel === "secondary-attested-name").length,
    },
  });
}
