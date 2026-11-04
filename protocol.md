# MP 7 Experimental Protocol

**Label Space**
The classification targets 8 contour labels:
1. `valley`
2. `undulating`
3. `arch`
4. `descending`
5. `ascending`
6. `mixed`
7. `static`
8. `undetermined`

**Instruction-Tuned Model Identifier**
*   **Model:** `Qwen/Qwen1.5-1.8B-Chat`
*   **Hardware Constraint:** CPU-only execution (INV-15)

**Shot Sweep Parameters**
*   **k-values:** 0, 1, 3, 5, 8
*   **Random Seeds:** 42, 1024, 2048, 4096, 8192 (5 distinct seeds for demonstration selection and permutation)

**Statistical Evaluation**
*   **Metric:** Macro-F1
*   **Confidence Interval:** 95% Bootstrap Confidence Interval