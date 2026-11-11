"""Conservative MuseScore 3 written-score adapter. No audio/lyric alignment model.

Supports direct/voice-wrapped measures, simple nonnested tuplets, explicit
measure-rest duration variants, and annotation-only tick markers. Fails closed
when score timing could be interpreted in multiple ways. Python stdlib only.
"""
from __future__ import annotations
from collections import Counter
from fractions import Fraction
from pathlib import Path
import hashlib, json, re, xml.etree.ElementTree as ET

class UnsupportedNotation(ValueError):
    pass

DURATIONS={'longa':16,'breve':8,'whole':4,'half':2,'quarter':1,'eighth':Fraction(1,2),
           '16th':Fraction(1,4),'32nd':Fraction(1,8),'64th':Fraction(1,16)}
TIME_OPERATORS={'location','tickOffset','RepeatMeasure','TimeTick','MeasureRepeat'}

def fraction_string(f):
    return str(f.numerator) if f.denominator==1 else f'{f.numerator}/{f.denominator}'

def event_duration(item,div):
    tag=(item.findtext('durationType') or '').strip()
    if tag == 'measure':
        if item.tag!='Rest': raise UnsupportedNotation('measure duration on non-Rest')
        el=item.find('duration')
        if el is None: raise UnsupportedNotation('measure rest duration missing')
        if el.get('z') is not None or el.get('n') is not None:
            try:
                if el.get('z') is None or el.get('n') is None:raise ValueError()
                z=int(el.get('z')); n=int(el.get('n'))
                if z<=0 or n<=0:raise ValueError()
                whole=Fraction(z,n)
            except (ValueError,ZeroDivisionError): raise UnsupportedNotation('bad z/n measure duration') from None
        else:
            raw=(el.text or '').strip()
            if not re.fullmatch(r'\d+/[1-9]\d*',raw):raise UnsupportedNotation('bad textual measure duration')
            whole=Fraction(raw)
        if not Fraction(0)<whole<=8:raise UnsupportedNotation('unreasonable measure length')
        return whole*4*div
    if tag not in DURATIONS:raise UnsupportedNotation('unknown duration type '+repr(tag))
    dots_txt=(item.findtext('dots') or '0').strip()
    if not dots_txt.isdecimal():raise UnsupportedNotation('invalid dot count')
    dots=int(dots_txt)
    if not 0<=dots<=3:raise UnsupportedNotation('unsupported dot count')
    return div*Fraction(DURATIONS[tag])*sum((Fraction(1,2**j) for j in range(dots+1)),Fraction(0))

def measure_stream(measure, i):
    """Choose one timing stream; never discard timing tokens outside a voice.

    MuseScore 3 permits either direct Chord/Rest measure children or one voice
    wrapper.  If a wrapped measure also contains direct timing instructions,
    silently selecting only the voice would lose timing evidence.
    """
    voices=measure.findall('voice')
    direct_timing={'Chord','Rest','Tuplet','endTuplet','tick'} | TIME_OPERATORS
    outside=[x.tag for x in measure if x.tag in direct_timing]
    if len(voices)>1 or (voices and outside):
        raise UnsupportedNotation(f'measure {i}: mixed voices or outside-voice timing: {outside}')
    return list(voices[0]) if voices else list(measure), ('wrapped' if voices else 'direct')

def extract_score(source:bytes|Path,*,staff_index=0,verse_index=0):
    raw=source.read_bytes() if isinstance(source,Path) else source
    if len(raw)>3_000_000:
        raise UnsupportedNotation('score XML above conservative 3 MB limit')
    # ET does not fetch external entities, but fail closed for DTDs as a
    # deliberate input-contract guarantee, including oversized expansion.
    if b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper():
        raise UnsupportedNotation('DTD or entity declaration prohibited')
    root=ET.fromstring(raw)
    if root.tag!='museScore':raise UnsupportedNotation('not an MSCX root')
    score=root.find('Score')
    if score is None:raise UnsupportedNotation('missing Score')
    staves=score.findall('Staff')
    if not (0<=staff_index<len(staves)) or verse_index<0:raise UnsupportedNotation('invalid staff or verse')
    value=(score.findtext('Division') or '480').strip()
    if not value.isdecimal() or not 1<=int(value)<=100000:raise UnsupportedNotation('invalid Division')
    div=int(value);t=Fraction(0);chords=[];rests=0;anchors=[];counter=Counter();notes=0;tuplet_count=0; rests_since_chord=0
    for i,measure in enumerate(staves[staff_index].findall('Measure')):
        stream,mode=measure_stream(measure,i);counter[mode]+=1
        tuplet=None
        timed_in_measure=0
        for index,item in enumerate(stream):
            tag=item.tag
            if tag in TIME_OPERATORS: raise UnsupportedNotation(f'measure {i}: timing operator {tag}')
            if tag=='tick':
                # MSCX may attach a time coordinate to tempo metadata; it does
                # not advance the notated vocal event stream.
                nxt=stream[index+1].tag if index+1<len(stream) else None
                tick=(item.text or '').strip()
                if not tick.isdecimal():raise UnsupportedNotation('invalid tick marker')
                if nxt not in ('Tempo','Dynamic','StaffText','Text','Chord','Rest'):
                    raise UnsupportedNotation('tick before unknown event')
                if nxt in ('Chord','Rest') and Fraction(int(tick))!=t:
                    raise UnsupportedNotation(f'event tick {tick} does not match written cursor {fraction_string(t)}')
                counter['tick_metadata' if nxt not in ('Chord','Rest') else 'tick_checked']+=1
                continue
            if tag=='Tuplet':
                if tuplet is not None:raise UnsupportedNotation('nested tuplets not supported')
                try:
                    actual=int(item.findtext('actualNotes',''))
                    normal=int(item.findtext('normalNotes',''))
                    base=(item.findtext('baseNote') or '').strip()
                    if not (1<=actual<=32 and 1<=normal<=32 and base in DURATIONS):raise ValueError()
                except ValueError:raise UnsupportedNotation('bad tuplet ratio/base') from None
                tuplet={'ratio':Fraction(normal,actual),'base':div*Fraction(DURATIONS[base]),'actual':actual,'nominal':Fraction(0)}
                tuplet_count+=1;continue
            if tag=='endTuplet':
                if tuplet is None:raise UnsupportedNotation('unmatched endTuplet')
                expected=tuplet['base']*tuplet['actual']
                if tuplet['nominal']!=expected:
                    raise UnsupportedNotation('tuplet nominal length mismatch: '+fraction_string(tuplet['nominal'])+' != '+fraction_string(expected))
                tuplet=None;continue
            if tag not in ('Chord','Rest'):continue
            timed_in_measure+=1
            if item.tag=='Chord' and item.find('grace') is not None:raise UnsupportedNotation('grace chord unsupported')
            nominal=event_duration(item,div)
            if tuplet is not None:
                tuplet['nominal']+=nominal
                duration=nominal*tuplet['ratio']
            else:duration=nominal
            if duration<=0:raise UnsupportedNotation('nonpositive event duration')
            if tag=='Rest': rests+=1;rests_since_chord+=1
            else:
                notes+=len(item.findall('Note'))
                lyrics=item.findall('Lyrics');verses={}
                for l in lyrics:
                    num=(l.findtext('no') or '0').strip()
                    if not num.isdecimal() or int(num) in verses:raise UnsupportedNotation('duplicate or invalid lyric verse')
                    verses[int(num)]=l
                l=verses.get(verse_index)
                onset=bool(l is not None and (l.findtext('text') or '').strip())
                idx=len(chords)
                tie=any(s.get('type')=='Tie' and s.find('prev') is not None for n in item.findall('Note') for s in n.findall('Spanner'))
                tie_start=any(s.get('type')=='Tie' and s.find('next') is not None for n in item.findall('Note') for s in n.findall('Spanner'))
                pitches=[]
                for note in item.findall('Note'):
                    raw_pitch=(note.findtext('pitch') or '').strip()
                    if not raw_pitch.lstrip('-').isdecimal():
                        raise UnsupportedNotation('note pitch missing or invalid')
                    pitches.append(int(raw_pitch))
                slur=any(s.get('type')=='Slur' and s.find('prev') is not None for s in item.findall('Spanner'))
                chords.append({'chord_index':idx,'measure_index':i,'onset_ticks':fraction_string(t),
                               'duration_ticks':fraction_string(duration),'tie_continuation':tie,
                               'tie_start':tie_start,'note_pitches':pitches,
                               'rests_since_prior_chord':rests_since_chord,
                               'slur_end':slur})
                rests_since_chord=0
                if onset:anchors.append(idx)
            t+=duration
        if tuplet is not None:raise UnsupportedNotation(f'measure {i}: unterminated tuplet')
        if timed_in_measure == 0:
            # Duration cannot be established from metadata-only/empty measures.
            # Do not silently compress a possibly nonzero notated interval.
            raise UnsupportedNotation(f'measure {i}: no timed chord/rest events')
    if not chords:raise UnsupportedNotation('no chord events')
    return {'format':'MAQAM_CONSERVATIVE_MSCX_V6', 'source_sha256':hashlib.sha256(raw).hexdigest(),
            'staff_index':staff_index,'verse_index':verse_index,'division':div,
            'measure_modes':dict(counter),'written_total_ticks':fraction_string(t),
            'chord_count':len(chords),'noteheads':notes,'rests':rests,'tuplets':tuplet_count,
            'lyric_anchor_count':len(anchors),'lyric_anchor_indices':anchors,
            'chords':chords,
            'limitations':['written-time not performance repeat order','not an alignment predictor',
                           'slur ending is not a hard non-onset rule','zero-voice measure may contain direct events',
                           'unknown timing operators refused']}

def main():
    import argparse
    p=argparse.ArgumentParser();p.add_argument('file',type=Path);p.add_argument('--out',type=Path);p.add_argument('--staff',type=int,default=0);p.add_argument('--verse',type=int,default=0)
    a=p.parse_args();result=extract_score(a.file,staff_index=a.staff,verse_index=a.verse)
    v=json.dumps(result,indent=2,ensure_ascii=False)+'\n'
    if a.out:a.out.write_text(v)
    else:print(v)
if __name__=='__main__':main()
