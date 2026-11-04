"""Label note windows from vocadito note CSVs and export to JSONL.

Usage (from the schema/ directory):
    python label_windows.py vocadito_1_notesA1.csv --max-onset 30
    python label_windows.py path/to/*_notesA1.csv path/to/*_notesA2.csv --verbose --out silver_vocadito_chunks.jsonl
"""
import argparse
import csv
import math
import os
import json
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
    ap.add_argument("--out", type=str, default="silver_vocadito_chunks.jsonl",
                    help="output JSONL file path for the chunk records")
    a = ap.parse_args()

    if a.min_swing is not None:
        contour_labeler.REVERSAL_MIN_SWING = a.min_swing
    if a.min_reversals is not None:
        contour_labeler.UNDULATING_MIN_REVERSALS = a.min_reversals
    print(f"thresholds: swing>={contour_labeler.REVERSAL_MIN_SWING}, "
          f"reversals>={contour_labeler.UNDULATING_MIN_REVERSALS}")

    total = Counter()
    clips = defaultdict(set)
    all_chunks = []  # Accumulator for JSONL export

    for path in a.csvs:
        midi = load_midi(path, a.max_onset)
        wins = windows(midi, a.n, a.s)
        labels = [contour_label(w) for w in wins]
        counts = Counter(labels)
        total.update(counts)
        
        # Parse metadata for the schema
        filename = os.path.basename(path)
        clip_id = filename.split("_notes")[0]
        annotator = "A1" if "A1" in filename else "A2"
        
        for lab in counts:
            clips[lab].add(clip_id)
            
        print(f"{path}: {len(midi)} notes, {len(wins)} windows")
        for lab, c in sorted(counts.items()):
            print(f"    {lab}: {c}")
            
        for i, (w, lab) in enumerate(zip(wins, labels)):
            chunk_id = f"{clip_id}:{annotator}:w{i * a.s:04d}"
            
            # Construct the schema-compliant record
            record = {
                "chunk_id": chunk_id,
                "doc_id": clip_id,
                "annotator": annotator,
                "n_notes": len(w),
                "text": " ".join(map(str, w)),
                "trope_ids": [lab]
                # Downstream: Add the 37-d "vector" array before FAISS ingestion
            }
            all_chunks.append(record)
            
            if a.verbose:
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

    # Export to JSONL
    if a.out:
        with open(a.out, "w") as f:
            for chunk in all_chunks:
                f.write(json.dumps(chunk) + "\n")
        print(f"\nSaved {len(all_chunks)} chunks to {a.out}")

if __name__ == "__main__":
    main()