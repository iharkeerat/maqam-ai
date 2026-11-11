"""Reproducible *synthetic schema-only* MAQAM V7 ingestion smoke test.

The three constructed vocal chords are NOT external music-data evidence.
"""
from pathlib import Path
import json, sys, tempfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from research.score_ingestion.cli import generate

EXAMPLE=b'''<museScore version="3.02"><Score><Division>480</Division><Staff id="1"><Measure>
<Chord><durationType>quarter</durationType><Lyrics><text>constructed_one</text></Lyrics><Note><pitch>60</pitch><Spanner type="Tie"><next/></Spanner></Note></Chord>
<Chord><durationType>quarter</durationType><Note><pitch>60</pitch><Spanner type="Tie"><prev/></Spanner></Note></Chord>
<Chord><durationType>half</durationType><Lyrics><text>constructed_two</text></Lyrics><Note><pitch>62</pitch></Note></Chord>
</Measure></Staff></Score></museScore>'''


def main():
    with tempfile.TemporaryDirectory() as temp:
        root=Path(temp)
        original=root/'CONSTRUCTED_NOT_REAL.mscx';original.write_bytes(EXAMPLE)
        result=generate(original,root/'public',root/'private',syllables=2)
        inference=json.loads((root/'public'/'SOLVER_INPUT.json').read_text())
        predicted=json.loads((root/'public'/'FORMAL_OUTPUT.json').read_text())
        print(json.dumps({
            'dataset':'CONSTRUCTED_XML_SCHEMA_ONLY',
            'normalized_event_durations':inference['event_durations'],
            'original_chord_mapping':inference['normalized_groups'],
            'solver_status':predicted['status'],
            'formal_accuracy_not_measured':not predicted['real_accuracy_scored'],
            'gold_position_files_outside_public':all('lyric_anchor_indices' not in p.read_text()
                                                   for p in (root/'public').iterdir()),
            'warnings':result['model_scope']},indent=2))

if __name__=='__main__':main()
