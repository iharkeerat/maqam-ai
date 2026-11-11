"""Evidence-isolated symbolic score ingress into MAQAM's unchanged *formal* DP.

This is not a real lyrics-to-music predictor: constructing a solver case from a
real score and a separately supplied syllable count does not validate singing.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from math import lcm
from typing import Any

from research.pronunciation_rhythm.core import AlignmentCase, Candidate, RhythmSpec
from .notation_adapter import UnsupportedNotation


@dataclass(frozen=True)
class EventGroup:
    chord_indices: tuple[int, ...]
    first_onset_ticks: str
    duration_ticks: str
    note_pitch: int


def grouped_note_events(score: dict[str, Any]) -> list[EventGroup]:
    """Collapse only explicitly balanced, adjacent, equal-pitch 1-note ties.

    We reject ambiguous polyphonic / loose ends. Crucially this function never
    looks at `lyric_anchor_indices` or `lyric_anchor_count` in score.
    """
    chords=score['chords']
    groups: list[EventGroup]=[]
    prev=None
    for expected_index,chord in enumerate(chords):
        idx=chord['chord_index']
        if idx != expected_index:
            # Check original sequence identity, without trusting chord index gaps.
            raise UnsupportedNotation('nonconsecutive chord index')
        pitch=chord.get('note_pitches')
        if not isinstance(pitch,list) or len(pitch)!=1:
            raise UnsupportedNotation('tie-aware model requires single-pitch vocal chord')
        if not isinstance(pitch[0],int):
            raise UnsupportedNotation('invalid pitch')
        if prev is not None and prev.get('tie_start') and not chord.get('tie_continuation'):
            raise UnsupportedNotation('unmatched forward tie')
        if chord.get('tie_continuation'):
            if not groups or prev is None or not prev.get('tie_start'):
                raise UnsupportedNotation('unpaired backward tie')
            if chord['rests_since_prior_chord'] != 0:
                raise UnsupportedNotation('tie across intervening rest')
            if pitch[0] != prev['note_pitches'][0]:
                raise UnsupportedNotation('tie pitch changes')
            old=groups[-1]
            groups[-1]=EventGroup(
                old.chord_indices+(idx,),old.first_onset_ticks,
                str(Fraction(old.duration_ticks)+Fraction(chord['duration_ticks'])),old.note_pitch)
        else:
            groups.append(EventGroup((idx,),chord['onset_ticks'],chord['duration_ticks'],pitch[0]))
        prev=chord
    if prev is not None and prev.get('tie_start'):
        raise UnsupportedNotation('trailing forward tie')
    if not groups:
        raise UnsupportedNotation('no sounding note events')
    return groups


def sanitized_projection(score: dict[str, Any]) -> dict[str, Any]:
    """Exports only symbolic notes, durations and structural ties, never lyrics."""
    groups=grouped_note_events(score)
    fractions=[Fraction(g.duration_ticks) for g in groups]
    scale=lcm(*(x.denominator for x in fractions))
    if scale>4096:
        raise UnsupportedNotation('unreasonably fine symbolic tick scale')
    dur=[int(x*scale) for x in fractions]
    if any(v<=0 for v in dur):
        raise UnsupportedNotation('nonpositive converted ticks')
    # Score-space rests are not part of the DP event sequence.  Preserve
    # precisely where that compression introduces silent gaps, so a formal
    # witness spanning such a gap can be diagnosed rather than misread as a
    # continuous sung syllable.  No lyric reference field is involved.
    rest_gaps=[j for j,g in enumerate(groups)
               if score['chords'][g.chord_indices[0]]['rests_since_prior_chord']>0]
    if len(dur)>5000 or sum(dur)>100_000_000:
        raise UnsupportedNotation('score exceeds conservative formal solver limits')
    return {
        'format':'MAQAM_SYMBOLIC_INPUT_TO_FORMAL_DP_V7',
        'source_sha256':score['source_sha256'],
        'evidence':'pinned MSCX symbolic notation; constructed formal syllable tokens only',
        'staff_index':score['staff_index'],
        'written_tick_unit':'1/'+str(scale)+' MSCX tick',
        'formal_event_time_excludes_rests':True,
        'rest_gap_before_normalized_event_indices':rest_gaps,
        'original_chord_count':score['chord_count'],
        'normalized_event_count':len(dur),
        'event_durations':dur,
        'normalized_groups':[list(g.chord_indices) for g in groups],
        'original_written_onsets':[g.first_onset_ticks for g in groups],
        'note_pitches':[g.note_pitch for g in groups],
        'slurs_used_as_hard_constraints':False,
        'gold_lyric_positions_in_solver_input':False,
        'interpretation':'symbolic formal diagnostic only, no performance time, no validated sung alignment',
    }


def formal_case(public: dict[str, Any], syllable_count: int, *, max_events_per_syllable: int=3) -> AlignmentCase:
    """Use EXTERNALLY supplied K, NOT inferred from gold annotations."""
    events=tuple(public['event_durations'])
    if not isinstance(syllable_count,int) or not 1<=syllable_count<=len(events):
        raise ValueError('external syllable count must be 1..number of note events')
    if not isinstance(max_events_per_syllable,int) or not 1<=max_events_per_syllable<=32:
        raise ValueError('unsupported formal max span')
    # Distinguish formal model's provenance from real-world lexical validity.
    placeholder=Candidate('constructed_tokens_only',tuple('token_'+str(i) for i in range(syllable_count)))
    return AlignmentCase('mscX_symbolic_diagnostic', (placeholder,),
        RhythmSpec(events=events,cycle_ticks=sum(events),min_syllable_ticks=1,
                   max_syllable_ticks=sum(events),max_events_per_syllable=max_events_per_syllable))


def held_out_reference(score: dict[str, Any]) -> dict[str, Any]:
    """Reference only, must not be included in the inference directory."""
    public=sanitized_projection(score)  # map is structural, not gold
    group_by_chord={i:j for j,indices in enumerate(public['normalized_groups']) for i in indices}
    gold=list(score['lyric_anchor_indices'])
    gold_groups=[group_by_chord[i] for i in gold]
    tied_lyric_onsets=[i for i in gold if i!=public['normalized_groups'][group_by_chord[i]][0]]
    return {
        'format':'MAQAM_SEPARATE_SCORE_ANNOTATION_REFERENCE_V7',
        'source_sha256':score['source_sha256'],
        'original_gold_chord_indices':gold,
        'normalized_gold_group_indices':gold_groups,
        'gold_on_tie_continuation_chord_indices':tied_lyric_onsets,
        'annotated_syllables':len(gold),
        'independently_annotated_audio':False,
        'notes':'This gold comes from the SAME score edition, not from independent audio or listeners.',
    }
