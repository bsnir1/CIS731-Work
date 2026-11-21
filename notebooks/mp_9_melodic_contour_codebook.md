# MP 9 Gold-Standard Annotation Codebook: Vocadito Melodic Contours

**Project:** Automated Vocal Melody Transcription & Contour Classification (CIS 731 — VDB Track)  
**Annotator:** Barak Snir  
**Data Source:** `vocadito` (Zenodo record 5578807, v3; CC-BY-4.0)  
**Unit of Annotation:** Bounded 12-note vocal audio segments defined by `[ts_start, ts_end]` from `gold_raw.csv` ($\le 50$ objects, $\le 2.0$ hours).

---

## 1. Annotation Protocol (Audio-Only Mandate)
To prevent methodological circularity with the geometric MIDI heuristics used in the weak-supervision silver pool (`source=silver`), human gold-standard annotation (`source=gold`) strictly follows an **audio-only perceptual protocol**:

1. **Audio-Only Input:** Listen strictly to the raw audio clip bounded by `[ts_start, ts_end]`. Do **not** view the MIDI pitch numbers (`text` column) or silver labels while deciding.
2. **Replay Limit:** Listen to each segment at most **3 times** before committing a label to keep effort within the $\le 2.0$-hour cap.
3. **Locked Label Space:** Assign exactly one lowercase label from the 8 locked classes below.

---

## 2. Label Definitions
| Label | Perceptual Definition |
| :--- | :--- |
| `ascending` | General ascending melodic line (overall audible pitch trajectory moves upward). |
| `descending` | General descending melodic line (overall audible pitch trajectory moves downward). |
| `arch` | Upside-down U shape: rises to a clear high peak and falls back down. |
| `valley` | U shape: drops to a clear low floor and rises back up. |
| `undulating` | Melodic line hovers around a center pitch in a sine- or cosine-like waveform with repeated audible direction changes. |
| `static` | Little to no pitch motion; voice stays around the same note. |
| `mixed` | Mixture of contour forms or no single clear perceptual shape to tie to. |
| `undetermined` | Too much interference, vocal noise, or ambiguity to categorize confidently. |

---

## 3. Tie-Breaking Precedence Hierarchy
When a vocal phrase exhibits overlapping traits (e.g., vibrato on a rising line, or a brief opening flourish before a dip), apply rules in the following order:

1. **`undetermined` first:** If audio quality, breath noise, or clipping prevents hearing the pitch trajectory, label `undetermined`.
2. **`static` second:** If pitch variation is purely micro-tonal vibrato or negligible wobble around one pitch center, label `static`.
3. **Single global extremum (`arch` / `valley`) vs. `undulating`:**
   * Choose `arch` or `valley` if the phrase is dominated by a **single** clear rise-and-fall or fall-and-rise.
   * Choose `undulating` if the voice weaves up and down around a center pitch with **multiple** audible reversals (even if the final note drops or rises slightly).
4. **Dominant body over tail:** If the body of the phrase clearly follows one contour (e.g., hovering/undulating) and only the last note shifts, label according to the dominant body.
5. **Global directional trend (`ascending` / `descending`):** If the phrase steps noticeably higher or lower overall—even with a brief early dip or plateau—label `ascending` or `descending`.
6. **Fallback (`mixed`):** Use `mixed` only when two distinct contours split the clip roughly evenly and neither dominates.

---

## 4. Human-Labeled Boundary Examples
The following examples from the human-annotated gold set (`source=gold`) illustrate how the precedence rules resolve ambiguous cases:

| `item_id` | Audio Window (`ts_start` – `ts_end`) | Gold Label | Ambiguity & Decision Rationale |
| :--- | :--- | :--- | :--- |
| `vocadito_3:A2:w0030` | `13.22s – 18.04s` | `undulating` | *Boundary:* `valley` vs. `undulating`. Although the phrase dips in the middle and rises at the end, the audible opening rise and mid-phrase hover create a wave-like motion rather than a single clean U-shape. |
| `vocadito_23:A1:w0000` | `1.49s – 4.85s` | `undulating` | *Boundary:* `undulating` vs. `descending`/`mixed`. The phrase drops slightly at the tail, but the dominant body hovers repeatedly around a central pitch in a wave pattern. |
| `vocadito_33:A2:w0072` | `24.50s – 27.87s` | `ascending` | *Boundary:* `ascending` vs. `mixed` (110s deliberation). Contains a brief early dip before leaping up and plateauing; classified `ascending` because the net perceptual trajectory is clearly upward. |

---

## 5. Partner Overlap & Adjudication Protocol (`overlap_ids.txt`)
* **Overlap Size:** 20 items sampled from `gold_raw.csv` (`overlap_ids.txt`) are sent **blinded** (without Annotator 1's `gold_trope` column) alongside this codebook to the assigned partner.
* **Agreement Metric:** Compute percent agreement, the $8 \times 8$ confusion matrix, and Cohen's $\kappa$ with a 95% non-parametric percentile bootstrap CI ($B = 1,000$).
* **Adjudication Rules:** For any item where Annotator 1 and Annotator 2 disagree:
  1. Re-listen jointly (or exchange a 1-sentence rationale referencing Section 3 precedence).
  2. Apply the Section 3 precedence hierarchy strictly to resolve tie-breaks.
  3. If disagreement remains unresolved after one pass, assign `mixed` (if two valid shapes compete) or `undetermined` (if acoustically unclear), and log the resolution in `gold_adjudicated.jsonl`.