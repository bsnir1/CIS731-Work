"""Label note windows from vocadito note CSVs and print the label distribution.

Usage (from the schema/ directory):
    python label_windows.py vocadito_1_notesA1.csv --max-onset 30
    python label_windows.py path/to/*_notesA1.csv path/to/*_notesA2.csv --verbose

CSV format: no header; columns are onset_s, frequency_hz, duration_s.
Windows: n notes, stride s (defaults 12 and 6). The last window may be partial.
"""
import argparse
import csv
import math
import os
from collections import Counter, defaultdict

import contour_labeler
from contour_labeler import contour_label


def hz_to_midi(hz: float) -> int:
    """Nearest integer MIDI note, rounding as in MP5: floor(x + 0.5)."""
    return int(math.floor(69 + 12 * math.log2(hz / 440.0) + 0.5))


def load_midi(path: str, max_onset=None):
    rows = []
    with open(path, newline="") as f:
        for r in csv.reader(f):
            if not r:
                continue
            onset, hz = float(r[0]), float(r[1])
            if max_onset is None or onset < max_onset:
                rows.append((onset, hz_to_midi(hz)))
    rows.sort()
    return [m for _, m in rows]


def windows(midi, n, s):
    """Fixed windows: chunks = 1 + ceil((L - n)/s) for L > n, else 1."""
    L = len(midi)
    if L == 0:
        return []
    count = 1 if L <= n else 1 + math.ceil((L - n) / s)
    return [midi[i * s: i * s + n] for i in range(count)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csvs", nargs="+")
    ap.add_argument("--n", type=int, default=12)
    ap.add_argument("--s", type=int, default=6)
    ap.add_argument("--max-onset", type=float, default=None,
                    help="keep only notes with onset < this many seconds")
    ap.add_argument("--verbose", action="store_true", help="print every window")
    ap.add_argument("--min-swing", type=int, default=None,
                    help="override REVERSAL_MIN_SWING (semitones)")
    ap.add_argument("--min-reversals", type=int, default=None,
                    help="override UNDULATING_MIN_REVERSALS")
    ap.add_argument("--min-windows", type=int, default=10,
                    help="a label needs at least this many windows to be eligible for retrieval queries")
    ap.add_argument("--min-clips", type=int, default=3,
                    help="a label needs windows from at least this many distinct clips to be eligible")
    a = ap.parse_args()
    if a.min_swing is not None:
        contour_labeler.REVERSAL_MIN_SWING = a.min_swing
    if a.min_reversals is not None:
        contour_labeler.UNDULATING_MIN_REVERSALS = a.min_reversals
    print(f"thresholds: swing>={contour_labeler.REVERSAL_MIN_SWING}, "
          f"reversals>={contour_labeler.UNDULATING_MIN_REVERSALS}")

    total = Counter()
    clips = defaultdict(set)   # label -> distinct clip ids that contain it
    for path in a.csvs:
        midi = load_midi(path, a.max_onset)
        wins = windows(midi, a.n, a.s)
        labels = [contour_label(w) for w in wins]
        counts = Counter(labels)
        total.update(counts)
        clip_id = os.path.basename(path).split("_notes")[0]
        for lab in counts:
            clips[lab].add(clip_id)
        print(f"{path}: {len(midi)} notes, {len(wins)} windows")
        for lab, c in sorted(counts.items()):
            print(f"    {lab}: {c}")
        if a.verbose:
            for i, (w, lab) in enumerate(zip(wins, labels)):
                print(f"    w{i * a.s:04d} n={len(w):2d} {lab}  {w}")
    if len(a.csvs) > 1:
        print("TOTAL")
        for lab, c in sorted(total.items()):
            print(f"    {lab}: {c}")
        print(f"ELIGIBLE LABELS (>= {a.min_windows} windows from >= {a.min_clips} clips; "
              "mixed and undetermined are always excluded)")
        for lab, c in sorted(total.items()):
            k = len(clips[lab])
            ok = (c >= a.min_windows and k >= a.min_clips
                  and lab not in ("contour.mixed", "contour.undetermined"))
            print(f"    {lab}: {c} windows, {k} clips -> {'eligible' if ok else 'EXCLUDED'}")


if __name__ == "__main__":
    main()