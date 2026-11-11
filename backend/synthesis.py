"""Small expressive synthesis engine used by the optional FastAPI service."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import math
import wave

import numpy as np

SAMPLE_RATE = 44_100
SWAR_RATIOS = {
    "S": 1.0,
    "r": 16 / 15,
    "R": 9 / 8,
    "g": 6 / 5,
    "G": 5 / 4,
    "m": 4 / 3,
    "M": 45 / 32,
    "P": 3 / 2,
    "d": 8 / 5,
    "D": 5 / 3,
    "n": 9 / 5,
    "N": 15 / 8,
}


@dataclass(frozen=True)
class NoteEvent:
    swar: str
    saptak: str = "madhya"
    ornament: str = "none"
    duration_beats: float = 1.0


def _octave_multiplier(saptak: str) -> float:
    return {"mandra": 0.5, "madhya": 1.0, "taar": 2.0}.get(saptak, 1.0)


def _frequency(event: NoteEvent, tonic_hz: float) -> float:
    return tonic_hz * SWAR_RATIOS[event.swar] * _octave_multiplier(event.saptak)


def _envelope(size: int) -> np.ndarray:
    attack = max(1, int(size * 0.08))
    release = max(1, int(size * 0.16))
    sustain = max(0, size - attack - release)
    return np.concatenate(
        [
            np.linspace(0.0, 1.0, attack, endpoint=False),
            np.ones(sustain),
            np.linspace(1.0, 0.0, release),
        ]
    )[:size]


def _render_note(
    event: NoteEvent,
    next_event: NoteEvent | None,
    tonic_hz: float,
    seconds: float,
) -> np.ndarray:
    size = max(1, int(SAMPLE_RATE * seconds))
    t = np.arange(size, dtype=np.float64) / SAMPLE_RATE
    start_hz = _frequency(event, tonic_hz)
    frequency = np.full(size, start_hz, dtype=np.float64)

    if event.ornament == "meend" and next_event and next_event.swar in SWAR_RATIOS:
        end_hz = _frequency(next_event, tonic_hz)
        curve = 1 / (1 + np.exp(-10 * (np.linspace(0, 1, size) - 0.5)))
        frequency = start_hz + (end_hz - start_hz) * curve
    elif event.ornament == "murki":
        frequency *= 2 ** ((55 * np.sin(2 * math.pi * 10 * t)) / 1200)
    elif event.ornament == "khatka":
        cents = 120 * np.exp(-18 * t)
        frequency *= 2 ** (cents / 1200)

    phase = 2 * math.pi * np.cumsum(frequency) / SAMPLE_RATE
    # Two slightly detuned reed layers produce a light harmonium-like sketch.
    reed_a = 2 / math.pi * np.arctan(2.7 * np.sin(phase))
    reed_b = 0.34 * np.sin(2.002 * phase)
    bellows = 0.88 + 0.12 * np.sin(2 * math.pi * 0.72 * t)
    return (reed_a + reed_b) * bellows * _envelope(size)


def synthesize(
    events: list[NoteEvent],
    output_path: Path,
    bpm: int = 76,
    tonic_hz: float = 261.63,
) -> Path:
    playable = [event for event in events if event.swar in SWAR_RATIOS]
    if not playable:
        raise ValueError("The composition contains no playable swars.")
    if not 30 <= bpm <= 240:
        raise ValueError("BPM must be between 30 and 240.")

    beat_seconds = 60 / bpm
    chunks: list[np.ndarray] = []
    for index, event in enumerate(playable):
        next_event = playable[index + 1] if index + 1 < len(playable) else None
        chunks.append(
            _render_note(
                event,
                next_event,
                tonic_hz,
                beat_seconds * max(0.25, event.duration_beats),
            )
        )

    audio = np.concatenate(chunks)
    peak = float(np.max(np.abs(audio))) or 1.0
    pcm = np.int16(np.clip(audio / peak * 0.88, -1.0, 1.0) * 32767)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(output_path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(SAMPLE_RATE)
        wav_file.writeframes(pcm.tobytes())
    return output_path
