# MP 9: Retrieval-Augmented Classification & Cohort Convolutions
**Author:** Barak Snir (Team 2, Solo — CIS 731)  
**Track & Taxonomy:** Predictive / Multimedia (Audio) / VDB Track (`vocadito`, Zenodo record 5578807, v3; CC-BY-4.0)  
**Environment:** Pinned CPU DevContainer (`transformers==4.38.2`, `torch==2.2.1`, `faiss-cpu==1.8.0`)

---

## Codebook and Attestation

To prevent methodological circularity with the geometric MIDI heuristics used in weak supervision (`source=silver`), human gold-standard annotation (`source=gold`) followed a strict **audio-only perceptual protocol** documented in `codebook.md`. Annotators listened solely to raw vocal audio bounded by `[ts_start, ts_end]` (at most 3 replays, with MIDI sequences and silver labels hidden) and assigned one of the 8 locked contour labels:

* **`ascending` / `descending`:** General upward or downward audible pitch trajectory.
* **`arch` / `valley`:** Single clear upside-down U (high peak) or U (low floor) melodic shape.
* **`undulating`:** Pitch hovers around a center in a sine/cosine-like waveform with repeated audible direction changes.
* **`static`:** Little to no pitch motion; voice stays around the same note.
* **`mixed`:** Mixture of contour forms with no single dominant shape.
* **`undetermined`:** Excess interference or vocal ambiguity preventing confident categorization.

**Tie-Breaking Precedence:** Ambiguous clips follow a fixed hierarchy: `undetermined` $\to$ `static` $\to$ single global extremum (`arch`/`valley`) vs. repeated reversals (`undulating`) $\to$ dominant body over final-note tail $\to$ net `ascending`/`descending` $\to$ `mixed`. Three boundary exemplars from `gold_raw.csv` illustrate these rules:

| `item_id` | Audio Window | Gold Label | Effort | Boundary & Rationale |
| :--- | :--- | :--- | :--- | :--- |
| `vocadito_3:A2:w0030` | `13.22s–18.04s` | `undulating` | 30 s | *`valley` vs. `undulating`:* Brief opening rise and mid-phrase hover create wave-like motion rather than a single U-dip. |
| `vocadito_23:A1:w0000` | `1.49s–4.85s` | `undulating` | 50 s | *`undulating` vs. `descending`/`mixed`:* Dominant body hovers in a wave pattern, overriding a slight tail drop. |
| `vocadito_33:A2:w0072` | `24.50s–27.87s` | `ascending` | 110 s | *`ascending` vs. `mixed`:* Brief early dip followed by an upward leap and high plateau yields a net ascending trajectory. |

**Attestation & CI Gate Compliance (`attestation.md`):** All **50 objects** in `gold_raw.csv` carry `source=gold` and were human-labeled without AI assistance. Cumulative effort logged via per-item `annotation_sec` totaled **1,830 seconds (30.5 minutes / 0.51 hours)**—Mean = 36.6 s, Median = 30.0 s, Max = 110 s—passing both the $\le 50$-object and $\le 2.0$-hour gates for the grader to check by hand or automatically.

---

## Inter-Annotator Agreement and Adjudication

Because Team 2 is a solo CIS 731 project without an assigned teammate, agreement was audited via a **blind intra-annotator (test–retest) overlap** on 20 items sampled deterministically from `gold_raw.csv` (`overlap_ids.txt`). After a multi-hour washout break, the 20 clips were shuffled, stripped of Pass 1 labels, and re-annotated audio-only using `codebook.md`.

* **Percent Agreement:** **100.0%** (20 / 20)
* **Cohen's $\kappa$:** **1.000** (95% non-parametric percentile bootstrap CI: **`[1.000, 1.000]`**, $B = 1{,}000$)

| Pass 1 $\backslash$ Pass 2 | `arch` | `ascending` | `descending` | `mixed` | `undulating` | `valley` |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **`arch`** | 4 | 0 | 0 | 0 | 0 | 0 |
| **`ascending`** | 0 | 4 | 0 | 0 | 0 | 0 |
| **`descending`** | 0 | 0 | 2 | 0 | 0 | 0 |
| **`mixed`** | 0 | 0 | 0 | 2 | 0 | 0 |
| **`undulating`** | 0 | 0 | 0 | 0 | 4 | 0 |
| **`valley`** | 0 | 0 | 0 | 0 | 0 | 4 |

**Adjudication Rules & Limitations:** Under `codebook.md`, any overlap disagreement triggers a joint re-listen, strict application of the precedence hierarchy, and fallback to `mixed` or `undetermined` if unresolved. Zero disagreements occurred (`0/20`), so all 50 rows exported directly to `gold_adjudicated.jsonl` (`source=gold`). Note that $\kappa = 1.000$ reflects single-rater consistency after a multi-hour washout rather than cross-rater variance; future multi-rater pooling in HW 12 will capture inter-human variance on boundary clips.

---

## Weak-Supervision Agreement Analysis

To satisfy the $\ge 1{,}000$-chunk unlabeled pool requirement, all 40 *vocadito* clips (`notesA1`/`notesA2`) were re-windowed with **window = 12 notes, stride = 3**, strictly excluding all 50 gold `item_id`s to prevent evaluation leakage. This produced **1,076 silver chunks** (`silver_pool_expanded.jsonl`, all tagged `source=silver`).

**Labeling Functions & Weighted Vote Aggregation:** Each chunk was labeled by weighted voting across three deterministic labeling functions (ignoring `ABSTAIN` votes):
1. **LF 1 — Geometric Contour Heuristic ($w = 0.50$):** Rules over semitone range ($\le 2 \to$ `static`), direction reversals ($\ge 4$ swings of $\ge 2$ semitones $\to$ `undulating`), peak/valley clearance ($\ge 3$ semitones), and net pitch change ($\ge \pm 3$ semitones).
2. **LF 2 — OLS Linear Trend & Range ($w = 0.30$):** Ordinary least squares slope ($\ge \pm 0.35$ semitones/note $\to$ `ascending`/`descending`) and range ($\le 2 \to$ `static`); abstains on non-monotonic shapes.
3. **LF 3 — Midpoint-vs-Ends Comparison ($w = 0.20$):** Compares middle-third mean pitch against outer thirds ($\ge 2$ semitone gap $\to$ `arch`/`valley`); abstains otherwise.

**Silver-vs-Gold Agreement (50 Gold Objects):**
* **Accuracy:** **0.620** (31 / 50)
* **Macro-F1:** **0.591** (95% Bootstrap CI: **`[0.416, 0.726]`**)

**Silver Failure Modes (19 Total Disagreements):** The largest confusion clusters were `undulating` $\to$ `valley` (4), `ascending` $\to$ `undulating` (3), `ascending` $\to$ `arch` (3), `undulating` $\to$ `descending` (2), `mixed` $\to$ `valley` (2), and `undulating` $\to$ `arch` (2), plus single errors for `arch` $\to$ `undulating`, `mixed` $\to$ `descending`, and `valley` $\to$ `undulating`. Two structural mechanisms drive these errors: (1) **single-note extremum sensitivity**, where one brief ornamental dip or high note triggers LF 1's $\ge 3$-semitone `valley`/`arch` clearance even when the phrase sounds perceptually `undulating` or `ascending`; and (2) **vibrato reversal inflation**, where micro-oscillations along a rising vocal line accumulate $\ge 4$ small reversals and trip the `undulating` rule.

---

## Retrieval-Augmented Classification Results

All 1,076 leak-free silver chunks were embedded into L2-normalized 37-dimensional float32 histograms (12 pitch-class + 25 interval bins) and indexed in `faiss.IndexIDMap(faiss.IndexFlatIP(37))`. For each of the 50 adjudicated gold queries, we retrieved top-$k$ exemplars ($k \in \{3, 5, 10\}$) and evaluated: (a) retrieval quality (`P@k`, `Recall@k`, defining relevance as `silver_label == gold_trope`), (b) a similarity-weighted **RAG-kNN** classifier, and (c) **RAG-LLM** (`Qwen/Qwen1.5-1.8B-Chat`, CPU greedy decoding) conditioned on the $k$ retrieved `(MIDI sequence, silver_label)` exemplars, compared against the MP 7 fixed-demonstration baseline (`Macro-F1 = 0.016`, 95% CI `[0.008, 0.025]`).

| System / Setting | `P@k` (95% CI) | `Recall@k`\* (95% CI) | RAG-kNN Macro-F1 (95% CI) | RAG-LLM Macro-F1 (95% CI) |
| :--- | :---: | :---: | :---: | :---: |
| **MP 7 Baseline** (fixed demos) | — | — | — | `0.016` `[0.008, 0.025]` |
| **RAG ($k=3$)** | `0.387` `[0.287, 0.487]` | `0.387` `[0.287, 0.487]` | `0.368` `[0.208, 0.507]` | `0.086` `[0.023, 0.151]` |
| **RAG ($k=5$)** | `0.336` `[0.256, 0.420]` | `0.336` `[0.256, 0.420]` | **`0.382`** `[0.204, 0.517]` | `0.043` `[0.000, 0.093]` |
| **RAG ($k=10$)** | `0.284` `[0.222, 0.348]` | `0.284` `[0.222, 0.348]` | `0.270` `[0.156, 0.369]` | **`0.101`** `[0.038, 0.181]` |

*\*Note: `Recall@k` used the capped denominator $\min(k, |\text{relevant}|)$; because every populated silver class exceeds 10 chunks, capped `Recall@k` equals `P@k`.*

**Key Findings:**
1. **Retrieval Breaks LLM Collapse:** Conditioning `Qwen/Qwen1.5-1.8B-Chat` on FAISS-retrieved neighbors raised Macro-F1 from `0.016` to **`0.101`** at $k=10$ (a **6.3$\times$** gain with non-overlapping 95% CIs `[0.008, 0.025]` vs. `[0.038, 0.181]`), partially overcoming the `"mixed"` fallback trap observed in MP 7.
2. **Metric-Space Voting Outperforms Small CPU LLM:** Similarity-weighted **RAG-kNN** peaked at **`0.382`** ($k=5$), beating RAG-LLM by **3.8$\times$** while running in milliseconds on CPU. As $k$ increases from 3 to 10, `P@k` declines monotonically (`0.387` $\to$ `0.284`), explaining why RAG-kNN degrades at $k=10$ (`0.270`) as distant neighbors dilute local pitch-interval similarity.

---

## Cohort Convolution Analysis

**Ordered Cohort Axis & Kernels:** The 1,076 silver chunks were ordered along the **event-time window index** (`w0000`, `w0003`, ...) grouped into 10 sequential progression cohorts $t \in \{0, \dots, 9\}$ (bin width = 6 notes, tail capped at bin 9). On per-cohort frequency vectors for the dominant contour (`valley`), we applied:
* **Smoothing Kernel `[0.25, 0.50, 0.25]`** with replicate (`edge`) padding of width 1 (`mode="valid"`) to preserve length 10 without zero-padding edge drops.
* **First-Difference Kernel `[-1, 1]`** (`mode="valid"`, computing $\Delta_t = v_{t+1} - v_t$) across the 9 cohort transitions, with stratified cohort bootstrap CIs ($B = 1{,}000$).

| Cohort ($t$) | Smoothed `valley` Freq (95% CI) | Transition ($t \to t+1$) | First-Difference Drift $\Delta_t$ (95% CI) |
| :---: | :---: | :---: | :---: |
| `0` | `0.263` `[0.212, 0.316]` | `0 -> 1` | `+0.065` `[-0.027, +0.160]` |
| `1` | `0.293` `[0.252, 0.334]` | `1 -> 2` | `-0.010` `[-0.114, +0.094]` |
| `2` | `0.286` `[0.241, 0.330]` | `2 -> 3` | `-0.075` `[-0.175, +0.026]` |
| `3` | `0.264` `[0.222, 0.309]` | `3 -> 4` | `+0.075` `[-0.029, +0.178]` |
| `4` | `0.283` `[0.236, 0.336]` | `4 -> 5` | `-0.001` `[-0.132, +0.127]` |
| `5` | `0.265` `[0.209, 0.325]` | **`5 -> 6`** | **`-0.143` `[-0.262, -0.029]`** \* |
| `6` | `0.221` `[0.171, 0.276]` | `6 -> 7` | `+0.112` `[-0.026, +0.249]` |
| `7` | `0.267` `[0.198, 0.334]` | `7 -> 8` | `+0.103` `[-0.087, +0.281]` |
| `8` | `0.328` `[0.243, 0.410]` | `8 -> 9` | `-0.075` `[-0.249, +0.093]` |
| `9` | `0.316` `[0.243, 0.395]` | — | — |

*\*Only `Cohort 5 -> 6` exhibits statistically significant drift (`-0.143`, 95% CI excludes `0.0`), marking a mid-clip dip in `valley` prevalence before rising again in late-clip phrases (`Cohorts 8–9`).*

**CIS 731 Learned 1-D PyTorch Convolutional Kernel:** A causal 1-D PyTorch kernel (`nn.Conv1d(1, 1, kernel_size=3, bias=False)`, CPU, Adam `lr=0.05`, 300 epochs) was trained across all 8 contour classes to forecast cohort $t$ from $[t-3, t-2, t-1]$ on training targets $t \in \{3, \dots, 7\}$ and evaluated on held-out cohorts $t \in \{8, 9\}$ against the fixed `[0.25, 0.50, 0.25]` kernel:

| Model | Kernel Weights $[w_{t-3}, w_{t-2}, w_{t-1}]$ | Held-Out MSE | Held-Out MAE |
| :--- | :---: | :---: | :---: |
| **Fixed Smoothing Kernel** | `[0.2500, 0.5000, 0.2500]` | `0.003699` | `0.0375` |
| **CIS 731 Learned 1-D PyTorch Conv** | **`[0.6774, 0.1100, 0.2046]`** | **`0.003069`** | **`0.0352`** |

The learned kernel reduced held-out MSE by **17.0%** and MAE by **6.2%** relative to the fixed kernel. Its heavier weight on lag $t-3$ (`0.6774`) reflects periodic phrase repetition across overlapping 12-note vocal windows, whereas the symmetric `[0.25, 0.50, 0.25]` filter over-weights the intermediate lag $t-2$.

---

## GenAI Audit

Yes — the Generative AI Kit (v3.3) was used under the "Grammarly on Steroids" policy for workflow structuring, debugging headerless CSV timestamp alignment, verifying leak-free FAISS/PyTorch tensor slicing, and synthesizing this report strictly from raw verified files (`results.json`, `attestation.md`, `codebook.md`, and notebook outputs). Zero human gold labels (`source=gold`) were generated by AI; all 50 gold labels and 20 blind overlap labels were assigned by the student via audio-only listening. The complete interaction log is attached in `GenAI.pdf`.