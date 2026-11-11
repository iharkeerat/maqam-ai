"""Regression tests for fail-closed MSCX measure-time ingestion.

All scores are constructed; no test claims an original OpenScore replay.
"""
import unittest

from research.score_ingestion.notation_adapter import extract_score, UnsupportedNotation

CHORD = '<Chord><durationType>quarter</durationType><Note><pitch>60</pitch></Note></Chord>'
REST = '<Rest><durationType>measure</durationType><duration>1/4</duration></Rest>'
TIMESIG = '<TimeSig><sigN>4</sigN><sigD>4</sigD></TimeSig>'

def score(*measures):
    body=''.join(f'<Measure>{m}</Measure>' for m in measures)
    return ('<museScore version="3.02"><Score><Division>480</Division>'
            '<Staff id="1">'+body+'</Staff></Score></museScore>').encode()

class TimingIntegrityTests(unittest.TestCase):
    def test_wrapped_and_direct_measures_still_supported(self):
        r=extract_score(score(CHORD, '<voice>'+CHORD+'</voice>'))
        self.assertEqual(r['chord_count'],2)
        self.assertEqual(r['written_total_ticks'],'960')
        self.assertEqual(r['measure_modes'],{'direct':1,'wrapped':1})

    def test_wrapped_voice_with_harmless_measure_metadata_supported(self):
        r=extract_score(score(TIMESIG+'<voice>'+CHORD+'</voice>'))
        self.assertEqual(r['chord_count'],1)
        self.assertEqual(r['measure_modes'],{'wrapped':1})

    def test_direct_measure_rest_with_timing_supported(self):
        r=extract_score(score(REST,CHORD))
        self.assertEqual(r['rests'],1)
        self.assertEqual(r['written_total_ticks'],'960')

    def test_direct_tick_equal_cursor_allowed(self):
        r=extract_score(score(CHORD,'<tick>480</tick>'+CHORD))
        self.assertEqual(r['chord_count'],2)

    def test_direct_tick_disagreeing_with_cursor_rejected(self):
        with self.assertRaisesRegex(UnsupportedNotation,'does not match'):
            extract_score(score(CHORD,'<tick>960</tick>'+CHORD))

    def test_empty_first_measure_rejected(self):
        with self.assertRaisesRegex(UnsupportedNotation,'no timed chord/rest'):
            extract_score(score('',CHORD))

    def test_empty_intermediate_measure_rejected(self):
        with self.assertRaisesRegex(UnsupportedNotation,'no timed chord/rest'):
            extract_score(score(CHORD,'',CHORD))

    def test_metadata_only_direct_measure_rejected(self):
        with self.assertRaisesRegex(UnsupportedNotation,'no timed chord/rest'):
            extract_score(score(CHORD,TIMESIG,CHORD))

    def test_empty_explicit_voice_rejected(self):
        with self.assertRaisesRegex(UnsupportedNotation,'no timed chord/rest'):
            extract_score(score(CHORD,'<voice>'+TIMESIG+'</voice>',CHORD))

    def test_wrapped_measure_outside_voice_tick_rejected(self):
        with self.assertRaisesRegex(UnsupportedNotation,'outside-voice timing'):
            extract_score(score('<tick>0</tick><voice>'+CHORD+'</voice>'))

    def test_wrapped_measure_outside_voice_location_rejected(self):
        with self.assertRaisesRegex(UnsupportedNotation,'outside-voice timing'):
            extract_score(score('<location><fractions>0/1</fractions></location><voice>'+CHORD+'</voice>'))

    def test_wrapped_measure_outside_voice_tuplet_rejected(self):
        with self.assertRaisesRegex(UnsupportedNotation,'outside-voice timing'):
            extract_score(score('<Tuplet/><voice>'+CHORD+'</voice>'))

    def test_wrapped_measure_outside_voice_chord_rejected(self):
        with self.assertRaisesRegex(UnsupportedNotation,'outside-voice timing'):
            extract_score(score(CHORD+'<voice>'+CHORD+'</voice>'))

    def test_multiple_voices_rejected(self):
        with self.assertRaisesRegex(UnsupportedNotation,'mixed voices'):
            extract_score(score('<voice>'+CHORD+'</voice><voice>'+CHORD+'</voice>'))

    def test_no_score_chords_rejected(self):
        with self.assertRaisesRegex(UnsupportedNotation,'no timed chord/rest'):
            extract_score(score('<Measure/>'))  # metadata-only Measure

if __name__=='__main__': unittest.main()
