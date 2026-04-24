---
name: trace-analysis
description: Analyze Instruments traces step by step and turn them into prioritized optimization actions.
compatibility: opencode
metadata:
  audience: performance-engineering
  workflow: trace-analysis
---

## What I do

I analyze Instruments traces using the repository's trace tools.
I follow a fixed 3-step reasoning process:

1. Identify the critical path.
2. Measure time attribution.
3. Record trace-observed inefficiencies.

Use me when you want actionable performance insights from trace data and you can inspect that trace with the available tools.

## Preconditions

- If no `.trace` exists yet, start by using `capture_trace`.


## Command Workflow

1. Export the trace table of contents using the `trace_toc` tool.

2. Inspect the exported TOC and identify the run number, process, and relevant data tables.

3. Export only the entities needed for analysis with `trace_export_table` when the table schema is known.

4. Use `trace_query_xpath` only when you need a more specific XPath than a schema-level export.

5. Repeat exports until you can answer the analysis questions below with evidence.

Do not guess table schemas in advance. Use the TOC first, then export the specific runs and tables that the trace actually contains.

## Workflow

### 1. Identify the Critical Path

Determine whether total runtime is dominated by GPU execution, CPU-side submission/setup delays, or both.

Use the measured post-warmup `batch_generate(...)` call captured by `capture_trace`; do not re-establish a separate baseline window unless the trace contains multiple plausible measured calls.

Measure or estimate from exported tables:

- total GPU execution time in the measured inference window
- GPU idle gaps between kernel groups
- CPU activity around command submission
- whether kernels are tightly packed or separated by waits

Classify the window using the measured distribution of GPU active time, GPU idle gaps, and CPU submission activity. State the evidence for the classification instead of relying on fixed thresholds alone.

Compute when the data is available:

- sum of GPU kernel durations
- union of GPU busy intervals when possible
- total gap time between kernels or encoder groups
- CPU-side setup or submission time where exposed

Example:

```text
Total inference time: 42 ms
Total GPU active time: 38 ms
GPU idle gaps inside window: 4 ms
Conclusion: primarily GPU-bound, with some CPU submission overhead
```

### 2. Measure Time Attribution

Group events by operation or kernel family and sum total duration.

For GPU-bound cases:

- group GPU events by kernel or shader name
- sort by total time descending
- report count, total duration, average duration, and percent of inference time

For CPU-bound cases:

- group CPU-side functions, stacks, categories, or submission markers
- identify where submission/setup overhead is going

Preferred table format:

```text
Kernel name         Count   Total ms   Avg ms   Percent
-------------------------------------------------------
matmul_kernel       36      24.0       0.67     57.1%
softmax_kernel      12       6.0       0.50     14.3%
layer_norm_kernel   12       4.0       0.33      9.5%
add_kernel          24       2.0       0.08      4.8%
other               --       6.0       --       14.3%
```

Optimize by time share, not by event count alone.

### 3. Record Trace-Observed Inefficiencies

Only include issues that are directly supported by exported trace data.

For each issue you report, include:

- the specific trace evidence
- where it appears in the measured inference window
- why it matters for end-to-end inference time

If the trace does not support a particular issue category, say so rather than inferring it.

## Output Template

Use this exact structure when reporting results:

```markdown
# CLI Trace Analysis: [Model Name] - [Date]

## 1. Critical Path
- Trace file: ___
- Exported tables used: ___
- Run number: ___
- Hardware: ___
- Trace source: `trace_toc`, `trace_export_table`, and `trace_query_xpath`
- Total inference time: ___ ms
- GPU active time: ___ ms
- GPU idle gap time: ___ ms
- CPU submission/setup time: ___ ms
- Classification:
  - [ ] GPU-bound
  - [ ] CPU-bound
  - [ ] Mixed

## 2. Time Attribution
Top operations by total time:

| Operation | Count | Total ms | Avg ms | % of inference |
|----------|------:|---------:|-------:|---------------:|
|          |       |          |        |                |
|          |       |          |        |                |
|          |       |          |        |                |

## 3. Trace-Observed Issues
- first issue
- next issue
```

## Working Style

- Use the `trace_toc` tool for TOC export, then `trace_export_table` for common table exports.
- Use `trace_query_xpath` only when a schema-level export is not specific enough.
- Start with the TOC, then export only the relevant tables.
- Be quantitative and specific.
- Prefer direct measurements over guesses.
- If the trace tools fail or the input is not a `.trace` file, state the blocker immediately.
