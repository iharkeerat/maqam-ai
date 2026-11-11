"""Generate a short standalone audio example without starting the API."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.synthesis import NoteEvent, synthesize  # noqa: E402


def main() -> None:
    phrase = [
        NoteEvent("S"),
        NoteEvent("r", ornament="meend"),
        NoteEvent("G"),
        NoteEvent("m", ornament="murki"),
        NoteEvent("P"),
        NoteEvent("d", ornament="khatka"),
        NoteEvent("N"),
        NoteEvent("S", saptak="taar", duration_beats=2),
    ]
    path = synthesize(phrase, ROOT / "outputs" / "bhairav_demo.wav", bpm=72)
    print(f"Generated: {path}")


if __name__ == "__main__":
    main()
