MP5: Structured Streaming with vocadito Note Tokens
Schema and Contracts
The source fixture uses vocadito_1.wav and its corresponding A1 reference-note annotations. The original audio is approximately 33.212 seconds long; preparation preserves the original and creates a derived WAV containing exactly the first 30 seconds. This satisfies MP5’s maximum chunk-duration constraint.

The text field contains reference musical-note tokens rather than lyrics or an ASR transcript. The annotation CSV contains onset, frequency, and duration. Notes with onsets in [0,30) are converted from frequency to nearest-semitone pitch names, preserving octave and using sharp spellings. The resulting sequence contains 57 tokens and 10 distinct note names. A note beginning before the cutoff is included even if its reference ending extends beyond it. The text field contains A1 reference-note names, not an ASR transcript or predicted notes.

The explicit schema in contracts.py is:

| Fields                           | Spark type | Nullable |
| -------------------------------- | ---------- | -------- |
| record_id, track, source_id      | String     | No       |
| ts_start, ts_end, ingest_ts      | Timestamp  | No       |
| text, audio_uri                  | String     | No       |
| offset_start_sec, offset_end_sec | Double     | No       |
| source_revision, license_class   | String     | No       |
ts_end supplies event time for window assignment. ingest_ts supports lateness measurement. Identity, source, and version fields provide traceability; nonempty text is required for token analytics.

Admission checks enforce required types and values, timezone-aware timestamps, ts_start < ts_end, positive duration of at most 30 seconds, valid audio offsets, timestamp/offset-duration consistency, and matching source-manifest information. The publisher validates records before placing complete JSON files into the watched directory. A separate validator checks WAV existence and duration. The admission flag records a configured decision; it does not itself establish instructor approval of the music-track adaptation.

Watermark and State Analysis
The experiment uses synthetic replay timestamps and repeated reference-note text from one recording. Each event has a unique ID. Lateness is measured as:

L=ingest_ts−ts end
​
 
Here, ingest_ts is publisher admission before JSON publication, not Spark processing time.

An initial 12-event calibration produced p95 lateness of 8.352092 seconds. The watermark delay was selected as:


D=⌈8.352092+2⌉=11 seconds
The subsequent 240-event replay produced:

| Measurement | Seconds  |
| ----------- | -------- |
| p50         | 1.490623 |
| p95         | 9.987405 |
| p99         | 9.997991 |
| Maximum     | 9.999325 |
The preselected 11-second delay was retained. Although it exceeded the observed maximum admission lateness, this does not guarantee retention under every event ordering. Increasing the delay retains state and postpones final output; decreasing it can finalize results sooner at greater late-data risk. Spark advances the watermark using event-time progress rather than elapsed wall-clock time.

Both queries logged a maximum watermark of 2026-10-21T00:38:46.027Z. Maximum input event time was 00:38:57.027908 UTC, consistent with the configured delay. The comparison horizon is windows ending at or before 00:38:00 UTC.

State is organized by window, without source-level grouping. Each window retains ten fixed-vocabulary note counters and aggregate state rather than an unlimited token list. Maximum observed state rows were two for tumbling windows and six for sliding windows. These observations describe this fixture, not a universal memory bound; retained state depends on window duration, slide, watermark progress, and aggregate structures.

Query Design
The CPU-local Spark job uses an explicit JSON schema, UTC session timezone, and multiline JSON input. Validated records are published through complete-file rename. Two independent queries compute:

60-second tumbling windows.

Five-minute windows sliding every minute.

Both apply an 11-second watermark to ts_end and write finalized results in append mode to separate Parquet sinks with separate checkpoints.

The queries compute chunk count, approximate distinct-note count, mean admission latency, and top-10 note frequencies. Tokenization preserves pitch spelling and octave. After token expansion, only the first token position contributes to chunk count and mean latency, avoiding token-weighted record statistics. Top-note ties are resolved deterministically by note name.

The initial configuration admitted one file per trigger with five-second triggers. During troubleshooting, the admission limit was increased to ten files per trigger. These exploratory settings are distinguished from the consistently configured reference/recovery experiment.

Input coverage contained 240 records and 240 distinct IDs. Seven finalized tumbling windows matched batch-reference counts:

text
31, 29, 31, 29, 31, 29, 31
These account for 211 events. The remaining 29 belong to 00:38–00:39, which is beyond the final watermark’s completion boundary. Seven finalized sliding-window counts also matched the batch reference:

text
31, 60, 91, 120, 151, 149, 151
All displayed windows reported approximately ten distinct notes. Frequency checks were internally consistent: a 31-record window contained 372 occurrences each of D3 and D#3, matching 12 occurrences per fixture record.

Fault-Tolerance Reconciliation
The exploratory run included interruption and restart during troubleshooting, but that alone does not establish recovery correctness. A controlled reference/recovery comparison is currently in progress.

The experiment uses identical saved input records, query logic, watermark, and admission settings. The recovery process is terminated during execution and restarted with its original checkpoint and sink directories. Reference and recovery outputs will be compared within the finalized horizon.

| Check                                        | Expected successful result |
| -------------------------------------------- | -------------------------- |
| Reference rows within the comparison horizon | 7                          |
| Recovery rows within the comparison horizon  | 7                          |
| Duplicate keys                               | 0                          |
| Reference-only keys                          | 0                          |
| Recovery-only keys                           | 0                          |
| Aggregate mismatches                         | 0                          |
The logical key is (window_type, window_start, window_end). Checkpoints preserve source progress and state; the Parquet file sink maintains commit metadata. The test evaluates their combined recovery behavior, rather than assuming checkpointing makes every sink exactly-once. 


The recovery process was terminated during execution and restarted using its original checkpoint and Parquet sink locations. The uninterrupted reference and recovery runs used identical saved input, query definitions, watermark delay, and admission settings. Comparison was restricted to windows ending at or before 2026-10-21 00:38:00 UTC, after confirming both watermarks passed that boundary.

Each query produced seven reference and seven recovery windows. Reconciliation found zero duplicate keys, zero missing or unexpected keys, and zero aggregate mismatches. Mean admission latency was compared with a tolerance of  
10^−6
 seconds. These results support correct recovery within the tested finalized horizon; they do not establish a universal guarantee for other sources or sinks.

Metrics and Reproducibility
The exploratory progress-log summary was:

| Metric                        | Tumbling  | Sliding   |
| ----------------------------- | --------- | --------- |
| Logged progress entries       | 239       | 238       |
| Data-bearing batches          | 234       | 233       |
| Logged source input rows      | 239       | 238       |
| Mean batch input rows/s       | 0.169     | 0.168     |
| Mean batch processed rows/s   | 0.326     | 0.314     |
| Mean trigger execution, ms    | 4,787.113 | 4,823.693 |
| Maximum trigger execution, ms | 13,130    | 18,012    |
| Maximum operator state rows   | 2         | 6         |
Some batches exceeded the five-second trigger interval, explaining the processing-time warnings. Mean batch rates are not sustained end-to-end throughput, and publisher-admission lateness excludes waiting time inside Spark.

The logged input totals are lower than the 240 saved records. Therefore, the progress log is not treated as complete input-accounting evidence; interruption, polling coverage, and batch history must be examined. Input-file coverage and finalized-window comparisons provide separate evidence. Counts must not be summed across queries because both consume the same fixture.

Reproduction uses prepare_mp5_input.py, validate_mp5_input.py, replay_mp5_windows.py, and streaming_job.py. The fixture contains one independent audio recording, not 240 independent samples.


GenAI Audit
Generative AI assisted with schema/contracts, preparation and validation scripts, replay design, streaming implementation, troubleshooting, and report drafting. The preparation, validation, replay, window-output inspection, and metrics-summary steps were executed locally. The required GenAI.pdf will document this assistance.