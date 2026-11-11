# Reading MAQAM V8 score-preview results correctly

**API:** `POST /research/score/formal-preview` with JSON `{"mscx_xml":"<museScore>...</museScore>","syllable_count":3,"max_events_per_syllable":3}`. The syllable count **must come from the caller independently**, not from the uploaded score's `Lyrics` fields. Supported MuseScore 3 notation only.

The response includes `formal_identifiability` with these fields:

| Field | Meaning |
|---|---|
| `number_of_equal_cost_optimal_paths` | Exact integer rendered as a decimal **string**, so large counts do not lose precision. |
| `unique_formal_path` | Whether there is exactly one feasible formal event-to-token partition. Does not establish correct music alignment. |
| `number_of_syllable_starts_with_multiple_possible_positions` | Number of ordered syllables that could start at more than one normalized note group. |
| `first_ten_possible_original_chord_index_ranges` | Lower/upper possible original 0-based chord starts, after verified tie-chain collapsing. A compact range of possibilities; it is not a confidence band. |
| `formal_minimum_cost` | `N-K` for any feasible untargeted formal assignment, otherwise null. |
| `all_feasible_paths_have_same_cost` | Expected true if the formal model is feasible. False when no formal path exists. |

The preview also returns `note_event_rests_removed`, `rest_gaps_before_normalized_event_indices`, and `predicted_syllable_indices_crossing_score_rests`. **Rests are not modelled as vocal events** and their compression can create artificial continuity; examine the rest warnings before interpreting timing. The endpoint never returns the score's lyric-reference positions.

### Simple constructed example

Five normal quarter-note chords and externally declared three syllables, maximum span three: **six** equally optimal alignments. Their cost is 2 and the start positions of syllables 2 and 3 are ambiguous. In this formal preview, the native exact DP returns a deterministic representative from the tie set, **not the statistically most probable or musically preferred one**.

### Running tests

```bash
python -m pytest -q tests/test_score_identifiability_v8.py
python -m pytest -q
```

All tests use constructed XML, mathematical enumeration and software-interface assertions. They do **not** claim genuine singing-audio or real score lyric-onset accuracy. Original OpenScore score bytes are not bundled.
