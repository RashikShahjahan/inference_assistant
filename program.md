# autoresearch

This is an experiment to have the LLM do its own inference research.

## Setup

To start or resume a run, work through this checklist:

1. Ensure `config.json` sets `max_peak_metal_mb` to a positive value.
2. Read the in-scope files for full context:
   - `README.md` - repository context and workflow.
   - `prepare.py` - fixed benchmark contract, fixture loading, memory checks, incumbent promotion, and results logging. Do not modify during normal experimentation.
   - `generate.py` - the only file you tune.
   - `config.json` - fixed benchmark configuration for the current run.
3. Run `uv run prepare.py` once after changing the benchmark contract or when initializing a fresh workspace.
4. Verify that `state/best_generate.py` and `results.tsv` exist.
5. Confirm the benchmark is ready, then begin experimentation.

## Experimentation

Each experiment benchmarks `generate.py` against the incumbent snapshot in `state/best_generate.py`.

The repository is intentionally narrow.

**What you CAN do:**
- Modify `generate.py`.
- Run quick comparisons with `uv run generate.py --description "..."`.
- Run full comparisons with `uv run generate.py --full --description "..."`.

**What you CANNOT do during normal experimentation:**
- Modify `prepare.py` or the benchmark logic it defines.
- Change the dataset selection, quick fixture ids, or memory ceiling in `config.json` unless the human explicitly wants the benchmark contract changed.
- Add new dependencies or rely on packages that are not already present in `pyproject.toml`.

**The goal is simple: maximize `output_tokens_per_sec` while staying at or below `max_peak_metal_mb`.**

Memory is a hard constraint. If a candidate exceeds `max_peak_metal_mb`, it is automatically discarded.

**Simplicity criterion:** all else equal, prefer the simpler change. A small throughput gain is not worth a pile of brittle complexity. If a simpler implementation matches or slightly improves throughput while respecting memory, that is a strong result.

**The first run:** establish the local benchmark state first with `uv run prepare.py`. After that, benchmark the current `generate.py` before making more ambitious changes.

## Output format

After a benchmark run, the CLI prints a JSON summary like this:

```json
{
  "run_id": "20260417-120000",
  "mode": "quick",
  "description": "prefill tweak",
  "candidate": {
    "ok": true,
    "mode": "quick",
    "fixture_count": 2,
    "repeats": 2,
    "elapsed_seconds": 1.2345,
    "output_tokens": 987,
    "output_tokens_per_sec": 799.5132,
    "peak_metal_mb": 12345.6,
    "max_peak_metal_mb": 13000.0,
    "failure_reason": null
  },
  "incumbent": {
    "ok": true,
    "mode": "quick",
    "fixture_count": 2,
    "repeats": 2,
    "elapsed_seconds": 1.252,
    "output_tokens": 987,
    "output_tokens_per_sec": 788.3387,
    "peak_metal_mb": 12380.4,
    "max_peak_metal_mb": 13000.0,
    "failure_reason": null
  },
  "status": "trial",
  "decision_reason": "quick_throughput_win"
}
```

The key fields are:

- `candidate.output_tokens_per_sec`: the metric to maximize.
- `candidate.peak_metal_mb`: must stay within the configured ceiling.
- `status`: one of `incumbent`, `trial`, `promoted`, or `discard`.
- `decision_reason`: explains why the candidate was kept or rejected.

If memory exceeds the ceiling, the candidate returns `failure_reason: "memory_limit_exceeded"` and the run is discarded.

## Logging results

Every benchmark appends a row to `results.tsv` automatically. The file is tab-separated and has this header:

```tsv
run_id	mode	candidate_hash	incumbent_hash	candidate_tps	incumbent_tps	peak_metal_mb	status	description
```

The benchmark owns this log. Do not hand-edit it during normal experimentation.

## The experiment loop

LOOP FOREVER:

1. Inspect the current candidate in `generate.py` and the benchmark contract in `README.md`, `prepare.py`, and `config.json` when needed.
2. Implement one concrete idea in `generate.py`.
3. Run the quick benchmark: `uv run generate.py --description "describe the change"`.
4. If the quick run reports a throughput win and stays within memory, run the full benchmark: `uv run generate.py --full --description "describe the change"`.
5. Trust the benchmark result:
   - `trial` means the quick candidate beat the incumbent but has not been promoted.
   - `promoted` means the full candidate beat the incumbent and `state/best_generate.py` was updated automatically.
   - `discard` means the candidate lost on throughput or violated the memory ceiling.
   - `incumbent` means the file is effectively identical to the current best snapshot.
6. If the result is `discard`, overwrite or revert the experiment before trying the next idea.
7. Repeat without asking the human whether to continue.

The human may leave you running unattended. Keep iterating until explicitly stopped.

## Practical guidance

- Prefer quick runs to filter ideas cheaply.
- Use full runs only for candidates that already look promising.
- Group work around throughput bottlenecks in prompt handling, batching, cache management, synchronization, and decode flow.
- Do not chase micro-optimizations that make `generate.py` much harder to reason about unless the throughput gain is clearly meaningful.
- If a change crashes, fix obvious mistakes when the idea still seems sound. If the idea itself appears bad, discard it and move on.
