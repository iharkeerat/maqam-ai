"""Formal-only pronunciation/rhythm alignment research pilot.

This module does NOT validate natural-language pronunciations, Raag grammar,
or artistic musical suitability. See README.md in this directory.
"""
from .core import (Candidate, RhythmSpec, AlignmentCase, Solution, SolveResult,
                   exact_oracle, composed_dp, top_k, exhaustive_two_stage,
                   verify_solution)
