# PS 6: Semantic Search, Chunking, and VDB Schema (vocadito)

Oct 29, 2026 · @Barak

## Chunking Cost Model

Across all 40 clips, 12-note windows with stride 6 give 351 chunks for annotator A1 and 287 for A2, costing 51,948 and 42,476 bytes (94,424 bytes in total). The worked example on vocadito_1 shows the arithmetic: its 57 annotated notes give 9 chunks costing 1,332 bytes, against 740 bytes for non-overlapping windows.

A chunk is one annotator's window of consecutive notes, embedded as a 37-dimension float32 vector (12 pitch-class + 25 interval dimensions). One vector costs 37 × 4 = 148 bytes. For a clip with L notes, window size n, stride s and dimension d:

$$N_{chunks} = 1 + \lceil (L - n)/s \rceil \quad (L > n), \qquad \text{storage} = N_{chunks} \cdot d \cdot 4 \text{ bytes}$$
$$\rho = 1 - s/n, \qquad \text{overlap inflation} = \frac{1}{1-\rho} = \frac{n}{s}$$

| Strategy | n (notes) | s (notes) | ρ | Chunks for L = 57 | Storage (bytes) |
| --- | --- | --- | --- | --- | --- |
| Fixed window, no overlap | 12 | 12 | 0 | 1 + ⌈45/12⌉ = 5 | 5 × 148 = 740 |
| Fixed window, chosen | 12 | 6 | 0.5 | 1 + ⌈45/6⌉ = 9 | 9 × 148 = 1,332 |
| Phrase-boundary (>0.1s gap)| variable | n/a | n/a | 663 (corpus total) | 663 × 148 = 98,124 |
| Structure-aware (whole clip) | 57 | n/a | 0 | 1 | 148 |

The measured storage ratio on clip 1 is 1,332 / 740 = 1.8. It approaches the inflation factor n/s = 2 as L grows, because the first and last windows have no overlap partner. With s = 6 the window starts are notes 0, 6, ..., 48. The last window holds only notes 48 to 56 (9 notes). It is kept and marked with n_notes = 9. The structure-aware row is a comparison point only: a 57-note chunk exceeds the schema's 12-note cap, so it is never stored.

**Whole corpus.** Running the entire corpus with no overlap (s = 12) yields 381 chunks requiring 56,388 bytes. Comparing our chosen s = 6 configuration (638 chunks, 94,424 bytes) to this baseline gives a measured corpus inflation factor of 1.67, which aligns with the theoretical upper bound of n/s = 2.

**Chunk-length cap.** The cap is min(30 s, 12 notes), and the contract rejects a chunk that breaks either limit.
- 30 s: the MP5 conditional approval requires chunks of at most 30 seconds. Twelve notes can exceed this if notes are held long, so both checks are needed.
- No encoder limit: the embedding is a histogram that can be computed for any length, so no model maximum sequence length applies. The 12-note cap is a design choice.
- Trope granularity: a contour label describes a phrase-sized window. Across the full 40 clips (2,237 notes, 759.46s), notes average 0.339s, making the 12-note window approximately 4.07 seconds. A shorter window gives fewer intervals per histogram (8 notes give 7 intervals spread over 25 bins), so vectors get sparser.

## Index and Similarity Analysis

On unit-normalized vectors, inner product equals cosine, so IndexFlatIP returns the exact cosine ranking, and at this corpus size flat search is the index to use. IVF and HNSW are analyzed because the assignment asks for it, but are not selected.

**Similarity.** For unit vectors a and b:

$$\cos(a,b) = \frac{a \cdot b}{\Vert{}a\Vert{}\,\Vert{}b\Vert{}} = a \cdot b \quad (\Vert{}a\Vert{} = \Vert{}b\Vert{} = 1), \qquad \Vert{}a-b\Vert{}^2 = 2 - 2\,a \cdot b$$

Ranking by inner product therefore gives the same order as ranking by cosine (and by L2 distance, in reverse). IndexFlatIP is exact because it scores the query against every stored vector and returns the k largest scores, with no approximation step. Cost is N × d multiply-adds per query. Each stored vector is L2-normalized before insertion, which the vdb_upsert contract checks.

| Index | Query cost | Build and memory | Recall | Update and delete |
| --- | --- | --- | --- | --- |
| IndexFlatIP | N × d multiply-adds | No training; N × d × 4 bytes | 1.0 (exact) | Removal supported through the ID wrapper (adapted to IndexFlat) |
| IndexIVFFlat (nlist, nprobe) | nlist + nprobe × N / nlist distances, assuming balanced lists | k-means training of nlist centroids; N × d × 4 bytes for vectors + nlist × d × 4 bytes for centroids | Drops when the true neighbor sits in an unprobed cell; nprobe = nlist recovers exact search | Removal by id only with the optional DirectMap, off by default |
| IndexHNSWFlat (M, efSearch) | Sublinear graph search; larger efSearch raises recall and cost | No training; (d × 4) + (M × 2 × 4) bytes per vector | Tuned by efSearch and M | Removal not supported |

The IVF distance count and the removal limits for IVF and HNSW come from the Faiss library paper (Eq. 18 and Sec. 6.1). A worked case with the real corpus, one index per annotator: N = 351 vectors for A1 and N = 287 for A2. Flat search scores every vector, so 351 × 37 = 12,987 and 287 × 37 = 10,619 multiply-adds per query. IVF with nlist = 16 and nprobe = 2 scores nlist + nprobe × N / nlist distances: 16 + 2 × 351 / 16 = 59.9 for A1 and 16 + 2 × 287 / 16 = 51.9 for A2, assuming balanced lists. That is about 2,215 multiply-adds for A1 (59.9 × 37), a saving of roughly 10,800 per query. The count is smallest at nlist = √(nprobe × N), about 26.5 for A1, giving about 53 distances. Flat search stays the choice: a full scan is already about 13 thousand multiply-adds, and IVF would add a training step on a few hundred vectors and some recall loss.

**Re-ranking latency.** The pipeline retrieves k = 50 candidates with the flat index, re-ranks them, and returns the top 10:

$$T = T_{enc} + T_{ann} + k\,T_{ce}, \qquad k = 50 \rightarrow \text{top } 10$$

- T_enc: building the query's 37-d vector from its note window. Measured at 0.0431 ms.
- T_ann: the flat search, N × d multiply-adds. Measured at 0.0085 ms.
- T_ce: rescoring step via dynamic time warping (DTW) over the two windows' interval sequences (key-invariant). A full window has 11 intervals, so one DTW costs 11 × 11 = 121 cell updates. Measured at 0.0487 ms per pair.
- Total pipeline latency T: 0.0431 + 0.0085 + (50 × 0.0487) = 2.4854 ms per query.

Sources: The Faiss library (arXiv 2401.08281), faiss::IndexHNSW API page, IndexIDMap.h API page, FAISS Wiki.

## Retrieval Evaluation Protocol

Retrieval is scored with P@k, Recall@k and MRR, where a chunk is relevant to a query chunk when it has the same melodic-contour label and comes from a different clip. Contour is a key-invariant property, so absolute pitch does not affect relevance. 

For a query chunk q, let top_k(q) be the k highest-scoring chunks and R_q the set of relevant chunks in the index:

$$P@k(q) = \frac{\vert{}R_q \cap \text{top}_k(q)\vert{}}{k}, \qquad Recall@k(q) = \frac{\vert{}R_q \cap \text{top}_k(q)\vert{}}{\vert{}R_q\vert{}}, \qquad MRR = \frac{1}{\vert{}Q\vert{}}\sum_{q \in Q} \frac{1}{\text{rank}_q}$$

rank_q is the position of the first relevant result, and the term is 0 when none is retrieved. Scores are averaged over all queries in Q.

**Relevance judgment rule.** A candidate chunk c is relevant to query q if all three hold:
1. c carries the same contour label as q. Labels come from a deterministic decision list over the window's MIDI pitches, in order: undetermined (fewer than 3 notes); static (range ≤ 2 semitones); undulating (≥ 4 direction reversals, each counted only after a swing of at least 2 semitones); arch or valley (the peak or trough clears both end notes by ≥ 3 semitones, the larger excursion wins, a tie is mixed); ascending or descending (net change ≥ 3 or ≤ -3 semitones); otherwise mixed.
2. c comes from a different clip than q. Windows of one clip overlap by 50%, so same-clip matches would be trivial.
3. The shared label is in the evaluated label set. Mixed and undetermined are excluded as catch-alls with no shape to retrieve, and any other label with fewer than 10 windows or windows from fewer than 3 distinct clips is excluded as too rare to query. Queries with excluded labels are left out of Q.

Borderline cases follow the rule exactly: a window with a peak clearing the ends by 2 semitones is not an arch. There is no human adjudication, since the rule is the judge. For the MP 9 codebook, this rule becomes the starting definition of a relevant chunk. 

**Threshold choice.** A direction reversal counts only after a swing of at least 2 semitones, and undulating needs at least 4 of them. At a 1-semitone swing, undulating took 55.0% of annotator A1's windows and 50.9% of A2's, because small pitch wobble counted as direction change. Swing 2 was chosen because it balanced the labels. Windows per label with the chosen thresholds (A1: 351 windows, A2: 287 windows, counted separately):

| Label | A1 windows | A2 windows |
| --- | --- | --- |
| valley | 90 | 77 |
| undulating | 89 | 74 |
| arch | 87 | 67 |
| descending | 45 | 34 |
| ascending | 26