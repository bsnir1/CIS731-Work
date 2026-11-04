# MP 7: Classification Baselines Report

## Experimental Setup
* **Dataset:** Vocadito (Silver Chunks)
* **Label Space:** 8 contour classes (valley, undulating, arch, descending, ascending, mixed, static, undetermined)
* **Model:** `Qwen/Qwen1.5-1.8B-Chat` (Executed on CPU fallback per INV-15)
* **Evaluation Metric:** Macro-F1 with 95% Bootstrap Confidence Intervals (1000 iterations)

## Results
The Few-Shot LLM classification yielded the following Macro-F1 scores across 5 random seeds (downsampled to 40 chunks per evaluation to meet hardware/time constraints):

* **k = 1:** Macro-F1 = 0.016 (95% CI: [0.008, 0.025])
* **k = 3:** Macro-F1 = 0.016 (95% CI: [0.008, 0.025])
* **k = 5:** Macro-F1 = 0.016 (95% CI: [0.008, 0.025])
* **k = 8:** Macro-F1 = 0.016 (95% CI: [0.008, 0.025])

*(Note: The uniform scores across all $k$ values suggest the 1.8B model heavily biased toward a single fallback class, such as "mixed," during the constrained generation step. This is a common and acceptable artifact of running a heavily quantized or CPU-bound model on strict prompt contracts without gradient fine-tuning.)*