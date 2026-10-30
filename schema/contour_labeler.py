"""Deterministic melodic-contour labeler for PS6 (vocadito note windows).

Input: integer MIDI pitches of one window (up to 12 notes, onset order).
Output: one trope_id from the schema's contour set.

Decision list, first match wins:
  1. undetermined : fewer than MIN_NOTES notes
  2. static       : pitch range <= STATIC_RANGE_MAX semitones
  3. undulating   : >= UNDULATING_MIN_REVERSALS direction reversals, each after
                    a swing of >= REVERSAL_MIN_SWING semitones
  4. arch/valley  : an interior extremum sticks out >= EXCURSION_MIN semitones
                    beyond both end notes (larger excursion wins; a tie is mixed)
  5. ascending / descending : net change (last - first) of >= NET_MIN semitones
  6. mixed        : everything else
"""
from typing import Sequence

MIN_NOTES = 3
STATIC_RANGE_MAX = 2
UNDULATING_MIN_REVERSALS = 4
REVERSAL_MIN_SWING = 2   # semitones; frozen 2026-10-29 after comparing swing 1 vs 2 on all 40 clips (A1, A2)
EXCURSION_MIN = 3
NET_MIN = 3

_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def token_to_midi(token: str) -> int:
    """'D#3' -> 51 (sharp spellings, C4 = 60), matching the MP5 token scheme."""
    name, octave = token[:-1], int(token[-1])
    return 12 * (octave + 1) + _NAMES.index(name)


def direction_reversals(midi: Sequence[int]) -> int:
    """Direction reversals, counted only after a swing of >= REVERSAL_MIN_SWING
    semitones away from the last extreme (a zigzag filter).

    With REVERSAL_MIN_SWING = 1 this equals the number of sign changes in the
    interval sequence after dropping repeated notes. Larger values ignore
    small wobbles (pitch-tracking jitter, 1-semitone ornaments).
    """
    ext, direction, count = midi[0], 0, 0
    for p in midi[1:]:
        if direction == 0:
            if abs(p - ext) >= REVERSAL_MIN_SWING:
                direction, ext = (1 if p > ext else -1), p
        elif direction == 1:
            if p > ext:
                ext = p
            elif ext - p >= REVERSAL_MIN_SWING:
                count, direction, ext = count + 1, -1, p
        else:
            if p < ext:
                ext = p
            elif p - ext >= REVERSAL_MIN_SWING:
                count, direction, ext = count + 1, 1, p
    return count


def contour_label(midi: Sequence[int]) -> str:
    if len(midi) < MIN_NOTES:
        return "contour.undetermined"
    lo, hi = min(midi), max(midi)
    if hi - lo <= STATIC_RANGE_MAX:
        return "contour.static"
    if direction_reversals(midi) >= UNDULATING_MIN_REVERSALS:
        return "contour.undulating"
    arch = hi - max(midi[0], midi[-1])      # how far the peak clears both ends
    valley = min(midi[0], midi[-1]) - lo    # how far the trough clears both ends
    if arch >= EXCURSION_MIN and valley >= EXCURSION_MIN and arch == valley:
        return "contour.mixed"
    if arch >= EXCURSION_MIN and arch > valley:
        return "contour.arch"
    if valley >= EXCURSION_MIN and valley > arch:
        return "contour.valley"
    net = midi[-1] - midi[0]
    if net >= NET_MIN:
        return "contour.ascending"
    if net <= -NET_MIN:
        return "contour.descending"
    return "contour.mixed"