import time
import numpy as np

try:
    import faiss
    HAS_FAISS = True
except ImportError:
    HAS_FAISS = False
    print("FAISS not found. Falling back to numpy dot product for T_ann simulation.")

def encode_vector(notes):
    vector = np.zeros(37, dtype=np.float32)
    # 12 pitch classes
    for p in notes:
        vector[p % 12] += 1
    # 11 intervals (capped at +/- 12)
    intervals = np.diff(notes)
    for iv in intervals:
        idx = int(np.clip(iv + 12, 0, 24))
        vector[12 + idx] += 1
    # L2 normalize
    norm = np.linalg.norm(vector)
    if norm > 0:
        vector /= norm
    return vector

def dtw_11(seq1, seq2):
    # 11x11 DTW distance
    n, m = len(seq1), len(seq2)
    dtw = np.full((n+1, m+1), np.inf)
    dtw[0, 0] = 0
    for i in range(1, n+1):
        for j in range(1, m+1):
            cost = abs(seq1[i-1] - seq2[j-1])
            dtw[i, j] = cost + min(dtw[i-1, j], dtw[i, j-1], dtw[i-1, j-1])
    return dtw[n, m]

def measure_latencies():
    iters = 10000
    
    # --- 1. T_enc (Vector Encoding) ---
    notes_batch = [np.random.randint(45, 75, size=12) for _ in range(iters)]
    
    start = time.perf_counter()
    for notes in notes_batch:
        encode_vector(notes)
    t_enc = (time.perf_counter() - start) / iters
    
    # --- 2. T_ann (Flat Search N=351, d=37) ---
    N = 351
    d = 37
    k = 50
    db = np.random.randn(N, d).astype(np.float32)
    queries = np.random.randn(iters, d).astype(np.float32)
    
    if HAS_FAISS:
        faiss.normalize_L2(db)
        faiss.normalize_L2(queries)
        index = faiss.IndexFlatIP(d)
        index.add(db)
        
        start = time.perf_counter()
        for i in range(iters):
            index.search(queries[i:i+1], k)
        t_ann = (time.perf_counter() - start) / iters
    else:
        # Numpy fallback
        db /= np.linalg.norm(db, axis=1, keepdims=True)
        queries /= np.linalg.norm(queries, axis=1, keepdims=True)
        start = time.perf_counter()
        for i in range(iters):
            scores = np.dot(db, queries[i])
            np.argpartition(scores, -k)[-k:]
        t_ann = (time.perf_counter() - start) / iters

    # --- 3. T_ce (DTW Rescoring for 1 pair) ---
    seqs1 = [np.random.randint(-12, 12, size=11) for _ in range(iters)]
    seqs2 = [np.random.randint(-12, 12, size=11) for _ in range(iters)]
    
    start = time.perf_counter()
    for i in range(iters):
        dtw_11(seqs1[i], seqs2[i])
    t_ce = (time.perf_counter() - start) / iters
    
    # Total latency per query
    k_candidates = 50
    total_latency = t_enc + t_ann + (k_candidates * t_ce)
    
    print(f"Latency Measurements (averaged over {iters} runs):")
    print(f"T_enc (Encoding 12 notes):        {t_enc * 1000:.4f} ms")
    print(f"T_ann (Flat Search N=351, k=50):  {t_ann * 1000:.4f} ms")
    print(f"T_ce  (1 DTW pair, 11x11):        {t_ce * 1000:.4f} ms")
    print(f"Total T_ce (for k=50 candidates): {(k_candidates * t_ce) * 1000:.4f} ms")
    print("-" * 50)
    print(f"Total Latency T:                  {total_latency * 1000:.4f} ms per query")

if __name__ == '__main__':
    measure_latencies()
