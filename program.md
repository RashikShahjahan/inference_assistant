# generate autoresearch

This is an experiment to have the LLM do its own research.

## Setup

To set up a new experiment, work with the user to:

1. **Agree on the memory ceiling**: set `max_peak_metal_mb` in `config.json`. The harness refuses to run `setup` or `eval` until this is a positive value.
2. **Read the in-scope files**: The sandbox is small. Read these files for full context:
   - `README.md` — repository context and command summary.
   - `baseline.py` — frozen reference implementation. Do not modify.
   - `runtime.py` — the file you modify.
   - `harness.py` — fixed benchmark, correctness checks, result logging, and incumbent promotion. Do not modify.
   - `run.py` — CLI entrypoint for `setup`, `eval`, `reset`, and `status`.
   - `config.json` — benchmark contract, especially the peak Metal memory limit.
3. **Initialize the sandbox**: run `uv run python run.py setup`.
4. **Verify state exists**: `setup` should create the reference outputs, the incumbent snapshot, the best-metrics file, and `results.tsv`.
5. **Confirm and go**: Confirm setup looks good. The setup run establishes the baseline and syncs `runtime.py` to the incumbent.

Once you get confirmation, kick off the experimentation.

## Experimentation

Each experiment runs through the harness. Iterate with quick runs, and only use full runs to advance the incumbent.

**What you CAN do:**
- Modify `runtime.py` — this is the only file you edit during research.
- Change generate-path implementation details such as prefill chunk sizing, one-shot vs chunked prefill, `mx.eval()` cadence, `mx.clear_cache()` policy, token collection strategy, detokenization timing, local reference caching in the decode loop, and stop-token checks.

**What you CANNOT do:**
- Modify `baseline.py`.
- Modify `harness.py`.
- Modify `fixtures/benchmark.jsonl`.
- Modify files outside this sandbox.
- Change the correctness contract: candidate output token ids must exactly match the frozen baseline.
- Use batching, worker scheduling changes, model swaps, prompt-template changes, or speculative decoding.

**The goal is simple: maximize `output_tokens_per_sec` while staying at or below `max_peak_metal_mb`.** Correctness is strict, and the peak Metal memory ceiling is a hard constraint.

**Promotion rules**: Quick runs are for iteration only. Only `uv run python run.py eval --full --description "..."` can promote a new incumbent.

**Simplicity criterion**: All else being equal, simpler is better. A tiny throughput win that adds awkward complexity is usually not worth it. Equal throughput with meaningfully lower memory is a win. Equal or better results from less code is an especially good outcome.

**The first run**: Your first run should always be `uv run python run.py setup`. That freezes the reference outputs, records the baseline, and initializes the incumbent snapshot.

## Output format

After `eval`, the CLI prints a JSON summary like this:

```json
{
  "run_id": "20260416-123456",
  "mode": "quick",
  "description": "adjust prefill chunk size",
  "candidate": {
    "ok": true,
    "candidate_hash": "abc123def456",
    "mode": "quick",
    "fixture_count": 3,
    "repeats": 2,
    "elapsed_seconds": 1.2345,
    "output_tokens": 987,
    "output_tokens_per_sec": 799.5132,
    "peak_metal_mb": 12345.6
  },
  "incumbent": {
    "ok": true,
    "candidate_hash": "def456abc123",
    "mode": "quick",
    "fixture_count": 3,
    "repeats": 2,
    "elapsed_seconds": 1.2520,
    "output_tokens": 987,
    "output_tokens_per_sec": 788.3387,
    "peak_metal_mb": 12380.4
  },
  "status": "trial",
  "decision_reason": "quick_win_1.42_percent"
}
```

The exact numbers will vary by machine and by change. The fields that matter most are `candidate.output_tokens_per_sec`, `candidate.peak_metal_mb`, `status`, and `decision_reason`.

If you redirected the run to a log file, you can pull the key lines back out with:

```bash
grep '"output_tokens_per_sec"\|"peak_metal_mb"\|"status"\|"decision_reason"' run.log
```

## Logging results

When an experiment finishes, the harness appends a row to `results.tsv` automatically. Do not hand-maintain it during normal runs.

The TSV has a header row and 7 columns:

```text
run_id	mode	candidate_hash	output_tokens_per_sec	peak_metal_mb	status	description
```

1. run identifier, formatted like `YYYYMMDD-HHMMSS`
2. benchmark mode: `quick` or `full`
3. content hash of the candidate `runtime.py`
4. candidate throughput in output tokens per second
5. candidate peak Metal memory in MB
6. harness decision: `trial`, `promoted`, or `discard`
7. short description of what the experiment tried

Example:

```text
run_id	mode	candidate_hash	output_tokens_per_sec	peak_metal_mb	status	description
20260416-100000	full	111aaa222bbb	781.4421	12144.0	promoted	baseline setup
20260416-101500	quick	333ccc444ddd	792.8830	12120.4	trial	increase prefill chunk size
20260416-102300	full	333ccc444ddd	790.5512	12120.4	promoted	increase prefill chunk size
20260416-103100	full	555eee666fff	775.2044	12180.7	discard	clear cache less often
```

## The experiment loop

The incumbent lives in `state/best_runtime.py`, and `uv run python run.py reset` restores `runtime.py` from that snapshot.

LOOP FOREVER:

1. Look at the current state with `uv run python run.py status`.
2. Reset `runtime.py` from the incumbent with `uv run python run.py reset`.
3. Tune `runtime.py` with one concrete idea.
4. Run a quick benchmark: `uv run python run.py eval --description "describe the change"`.
5. If the quick run looks promising, run the full benchmark: `uv run python run.py eval --full --description "describe the change"`.
6. Trust the harness decision. If the result is `promoted`, the incumbent advanced automatically. If the result is `discard`, reset and move on. If the result is `trial`, you only have quick evidence so far.
7. Inspect `results.tsv` or `runs/<run_id>/result.json` if you need the recorded metrics after a run.
8. Repeat with the next idea.

The idea is that you are an autonomous researcher making small, testable changes to `runtime.py`. Keep changes that beat the incumbent under the real benchmark contract, and discard changes that do not.

**Failures**: If a run crashes because of an obvious bug, fix it and rerun. If the idea itself is fundamentally bad or violates the correctness or memory contract, discard it and move on.

**NEVER STOP**: Once the experiment loop has begun, do not pause to ask the human if you should continue. Keep iterating until you are manually stopped.
