"""Optional high-fidelity synthesis API for MAQAM AI."""
from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from backend.synthesis import NoteEvent, synthesize
from backend.research import metrics as research_metrics, predict as research_predict

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "outputs"
OUTPUT_DIR.mkdir(exist_ok=True)

app = FastAPI(
    title="MAQAM AI Synthesis API",
    version="3.0.0",
    description="Audio synthesis plus reproducible MAQAM research-baseline inference.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
app.mount("/audio", StaticFiles(directory=OUTPUT_DIR), name="audio")


class NotationPayload(BaseModel):
    swar: str = Field(max_length=2)
    saptak: str = "madhya"
    ornament: str = "none"
    duration_beats: float = Field(default=1.0, ge=0.25, le=8)


class SynthesisRequest(BaseModel):
    notation: list[NotationPayload]
    bpm: int = Field(default=76, ge=30, le=240)
    tonic_hz: float = Field(default=261.63, ge=100, le=600)


class ResearchPredictionRequest(BaseModel):
    poetry: str = Field(min_length=1, max_length=12_000)
    language: str = Field(default="unknown", max_length=40)
    form: str = Field(default="unknown", max_length=80)
    time_hint: str = Field(default="unknown", max_length=80)
    top_k: int = Field(default=5, ge=1, le=10)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "engine": "maqam-research-and-synthesis-v3"}


@app.post("/synthesize")
def create_audio(payload: SynthesisRequest) -> dict[str, str]:
    filename = f"composition-{uuid4().hex[:10]}.wav"
    output_path = OUTPUT_DIR / filename
    try:
        events = [NoteEvent(**item.model_dump()) for item in payload.notation]
        synthesize(events, output_path, bpm=payload.bpm, tonic_hz=payload.tonic_hz)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return {"file_url": f"http://localhost:8000/audio/{filename}", "filename": filename}


@app.get("/research/metrics")
def get_research_metrics() -> dict[str, object]:
    return research_metrics()


@app.post("/research/predict")
def create_research_prediction(payload: ResearchPredictionRequest) -> dict[str, object]:
    try:
        return research_predict(
            payload.poetry,
            language=payload.language,
            form=payload.form,
            time_hint=payload.time_hint,
            top_k=payload.top_k,
        )
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error

# Formal-only symbolic-score preview. It never returns score-encoded lyric gold.
# The K syllables are supplied by the caller, NOT inferred from score labels.
class FormalScorePreviewRequest(BaseModel):
    mscx_xml: str = Field(min_length=20, max_length=1_500_000)
    syllable_count: int = Field(ge=1, le=350)
    max_events_per_syllable: int = Field(default=3, ge=1, le=8)


@app.post('/research/score/formal-preview')
def preview_formal_score(payload: FormalScorePreviewRequest) -> dict[str, object]:
    from research.score_ingestion.notation_adapter import extract_score, UnsupportedNotation
    from xml.etree.ElementTree import ParseError
    from research.score_ingestion.integration import formal_case, sanitized_projection
    from research.score_ingestion.identifiability import summarize_for_public_api, formal_spans_crossing_rests
    from research.pronunciation_rhythm.core import composed_dp, verify_solution

    try:
        raw=extract_score(payload.mscx_xml.encode('utf-8'))
        public=sanitized_projection(raw)
        if public['normalized_event_count']>350:
            raise UnsupportedNotation('formal API capped at 350 note events')
        case=formal_case(public,payload.syllable_count,
                         max_events_per_syllable=payload.max_events_per_syllable)
        result=composed_dp(case)
        if result.solution is not None and not verify_solution(case,result.solution):
            raise AssertionError('independent formal witness verification failed')
        starts=([0]+list(result.solution.ends[:-1])) if result.solution else None
        source_chords=([public['normalized_groups'][i][0] for i in starts] if starts is not None else None)
        rest_crossings=(formal_spans_crossing_rests(
            result.solution.ends,public['rest_gap_before_normalized_event_indices'])
            if result.solution is not None else [])
        ambiguity=summarize_for_public_api(
            public['normalized_event_count'],payload.syllable_count,
            payload.max_events_per_syllable,public['normalized_groups'])
        if result.solution is not None and result.solution.cost != ambiguity['formal_minimum_cost']:
            raise AssertionError('untargeted cost does not match independent composition audit')
        if (result.solution is not None) != bool(int(ambiguity['number_of_equal_cost_optimal_paths'])):
            raise AssertionError('independent feasibility audit disagrees with solver')
        return {
            'research_status':'formal-diagnostic-only',
            'original_chords':public['original_chord_count'],
            'normalized_note_events':public['normalized_event_count'],
            'source_sha256':public['source_sha256'],
            'status':result.status,
            'predicted_original_chord_indices':source_chords,
            'formal_cost':result.solution.cost if result.solution else None,
            'formal_identifiability':ambiguity,
            'note_event_rests_removed':raw['rests'],
            'rest_gaps_before_normalized_event_indices':public['rest_gap_before_normalized_event_indices'],
            'predicted_syllable_indices_crossing_score_rests':rest_crossings,
            'cost_is_not_singing_accuracy':True,
            'gold_annotation_positions_exposed':False,
            'audio_or_linguistic_accuracy_evaluated':False,
            'warnings':['Lyrics in the input are never used as predictions or exposed as gold',
                        'Rests omitted from formal event-time; do not read times as sung durations',
                        'Exact DP solves a constructed objective; not a validated musical aligner',
                        'Untargeted formal cost is N-K for every feasible assignment; review formal_identifiability before treating any placement as determined'],
        }
    except (UnsupportedNotation, ValueError, ParseError) as exc:
        raise HTTPException(status_code=422,detail=str(exc)) from exc


# V9 experimental lock-edit trace: one in-request pointer cache, not durable
# session state. Original note/lyrics annotations remain inaccessible to solver.
class FormalNormalizedLock(BaseModel):
    normalized_event_index: int = Field(ge=0, le=119)
    syllable_index: int = Field(ge=0, le=119)


class FormalLockStep(BaseModel):
    locks: list[FormalNormalizedLock] = Field(default_factory=list, max_length=25)


class FormalScoreLockTraceRequest(BaseModel):
    mscx_xml: str = Field(min_length=20, max_length=1_500_000)
    syllable_count: int = Field(ge=1, le=120)
    max_events_per_syllable: int = Field(default=3, ge=1, le=8)
    edits: list[FormalLockStep] = Field(default_factory=list, max_length=20)


@app.post('/research/score/formal-lock-trace')
def preview_formal_lock_edits(payload: FormalScoreLockTraceRequest) -> dict[str, object]:
    """Compare formal placements after arbitrary normalized-event lock edits.

    Caller provides K; no score-based lyrics are used.  Each request owns its
    cache and releases it after responding.  No unlicensed learning or audio.
    """
    from xml.etree.ElementTree import ParseError
    from research.score_ingestion.notation_adapter import extract_score, UnsupportedNotation
    from research.score_ingestion.integration import formal_case, sanitized_projection
    from research.pronunciation_rhythm.pointer_cached_v9 import PointerCachedLockDP
    from research.pronunciation_rhythm.core import composed_dp
    from research.score_ingestion.locked_identifiability_v10 import summarize_lock_trace_ambiguity

    try:
        raw=extract_score(payload.mscx_xml.encode('utf-8'))
        public=sanitized_projection(raw)
        n=public['normalized_event_count']
        if n>120 or n*payload.syllable_count*payload.max_events_per_syllable>90_000:
            raise UnsupportedNotation('lock trace capped at 120 events and 90000 state-span work units')
        case=formal_case(public,payload.syllable_count,
                         max_events_per_syllable=payload.max_events_per_syllable)
        engine=PointerCachedLockDP(case)
        original=composed_dp(case)
        base=engine.result()
        if (base.status,base.solution)!=(original.status,original.solution):
            raise AssertionError('V9 initial pointer/native parity failed')

        def present(result,locks_for_count=(),stats=None):
            audit=summarize_lock_trace_ambiguity(
                n,payload.syllable_count,payload.max_events_per_syllable,
                locks_for_count,public['normalized_groups'])
            if (result.solution is not None) != bool(int(audit['number_of_equal_cost_optimal_paths'])):
                raise AssertionError('V10 locked feasibility count disagrees with exact pointer solver')
            if result.solution is not None and result.solution.cost != audit['formal_minimum_cost']:
                raise AssertionError('V10 locked minimum cost disagrees with pointer witness')
            starts=([0]+list(result.solution.ends[:-1])) if result.solution is not None else None
            mapped=([public['normalized_groups'][j][0] for j in starts]
                    if starts is not None else None)
            return {
                'status':result.status,
                'formal_cost':result.solution.cost if result.solution else None,
                'formal_identifiability':audit,
                'predicted_original_chord_indices':mapped,
                'recomputed_states':stats.recomputed_states if stats else None,
                'changed_state_values':stats.changed_state_values if stats else None,
                'edges_scanned':stats.edges_scanned if stats else None,
            }

        updates=[]
        for edit in payload.edits:
            locks=[]
            for lock in edit.locks:
                if lock.normalized_event_index>=n:
                    raise ValueError('lock event index outside normalized score')
                if lock.syllable_index>=payload.syllable_count:
                    raise ValueError('lock syllable index outside supplied count')
                locks.append((lock.normalized_event_index,'token_'+str(lock.syllable_index)))
            result,stats=engine.update(tuple(sorted(locks)))
            updates.append(present(result,tuple((lock.normalized_event_index,lock.syllable_index) for lock in edit.locks),stats))
        return {
            'research_status':'constructed-formal-lock-edit-trace-only',
            'source_sha256':public['source_sha256'],
            'normalized_note_events':n,
            'original_chords':public['original_chord_count'],
            'initial':present(base),
            'updates':updates,
            'static_states':engine.graph.static_states,
            'static_edges':engine.graph.static_edges,
            'gold_positions_exposed':False,
            'real_alignment_accuracy_evaluated':False,
            'cache_scope':'one request only; not a persistent interactive session',
            'warnings':[
                'All token labels are constructed from caller-provided syllable_count',
                'Locks refer to normalized event indices after tie collapsing',
                'Formal cost and tie-break are not singing accuracy or probabilities',
                'V10 recomputes exact lock-conditioned ambiguity counts after each edit',
                'Rests are omitted from the formal note-event sequence',
            ],
        }
    except (UnsupportedNotation, ValueError, ParseError) as exc:
        raise HTTPException(status_code=422,detail=str(exc)) from exc
