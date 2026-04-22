from __future__ import annotations

import csv
import hashlib
import importlib.util
import sys
import time
from pathlib import Path
from typing import Any

from mlx_lm import batch_generate as mlx_lm_batch_generate

from prepare import (
    GENERATE_PATH,
    INCUMBENT_PATH,
    RESULTS_PATH,
    Config,
    build_prompt,
    ensure_results_header,
    load_model_and_tokenizer,
    promote_candidate,
)


def profile_batch_generate_metal(
    batch_generate_fn,
    model,
    tokenizer,
    prompts,
    *,
    max_tokens: int | list[int] = 128,
    trace_path: str | Path = "state/batch_generate_profile.gputrace",
    warmup: bool = True,
    **kwargs,
) -> dict[str, Any]:
    import mlx.core as mx

    trace_path = Path(trace_path)
    if not mx.metal.is_available():
        raise RuntimeError("Metal profiling requires an Apple Silicon / Metal device")
    if trace_path.suffix != ".gputrace":
        raise ValueError("trace_path must end with .gputrace")

    trace_path.parent.mkdir(parents=True, exist_ok=True)
    if trace_path.exists():
        if trace_path.is_dir():
            import shutil

            shutil.rmtree(trace_path)
        else:
            trace_path.unlink()

    if warmup:
        batch_generate_fn(
            model,
            tokenizer,
            prompts,
            max_tokens=max_tokens,
            **kwargs,
        )
        mx.synchronize()

    mx.metal.reset_peak_memory()
    mx.synchronize()

    started = time.perf_counter()
    capture_started = False
    try:
        mx.metal.start_capture(str(trace_path))
        capture_started = True
        response = batch_generate_fn(
            model,
            tokenizer,
            prompts,
            max_tokens=max_tokens,
            **kwargs,
        )
        mx.synchronize()
    except RuntimeError as exc:
        if "Capture layer is not inserted" in str(exc):
            raise RuntimeError(
                "Metal capture requires launching the process with MTL_CAPTURE_ENABLED=1"
            ) from exc
        raise
    finally:
        if capture_started:
            mx.metal.stop_capture()

    elapsed = time.perf_counter() - started
    peak_memory_bytes = int(mx.metal.get_peak_memory())

    return {
        "trace_path": str(trace_path),
        "prompt_count": len(prompts),
        "output_tokens": sum(len(token_ids) for token_ids in response.token_ids),
        "elapsed_seconds": round(elapsed, 4),
        "peak_metal_mb": round(peak_memory_bytes / 1024 / 1024, 1),
        "warmup": warmup,
    }


def benchmark_generate_fn(generate_fn, model, tokenizer, config: Config, fixtures):
    import mlx.core as mx
    from sacrebleu.metrics import CHRF

    prompts: list[list[int]] = []
    chrf = CHRF()

    for fixture in fixtures:
        prompts.append(build_prompt(tokenizer, config, fixture.source_text))

    if prompts:
        generate_fn(
            model,
            tokenizer,
            [prompts[0]],
            max_tokens=config.max_new_tokens,
        )

    mx.metal.reset_peak_memory()
    mx.synchronize()

    started = time.perf_counter()
    total_output_tokens = 0
    hypotheses: list[str] = []
    references: list[str] = []

    batch_payload = generate_fn(
        model,
        tokenizer,
        prompts,
        max_tokens=config.max_new_tokens,
    )
    batch_output_tokens: int | None = None
    if isinstance(batch_payload, dict):
        batch_results = batch_payload["results"]
        batch_output_tokens = int(batch_payload.get("output_tokens", 0))
    else:
        batch_results = batch_payload
    if len(batch_results) != len(prompts):
        raise RuntimeError(
            "Candidate returned the wrong number of outputs for the prompt batch"
        )
    for fixture, result in zip(fixtures, batch_results):
        hypotheses.append(str(result["text"]).strip())
        references.append(fixture.reference_text)
    if batch_output_tokens is not None:
        total_output_tokens += batch_output_tokens
    else:
        for result in batch_results:
            total_output_tokens += len(result["token_ids"])

    mx.metal.synchronize()

    elapsed = time.perf_counter() - started
    peak_memory_bytes = int(mx.metal.get_peak_memory())
    peak_metal_mb = round(peak_memory_bytes / 1024 / 1024, 1)
    output_tokens_per_sec = 0.0 if elapsed <= 0 else total_output_tokens / elapsed
    within_memory_limit = peak_metal_mb <= float(config.max_peak_metal_mb)
    chrf_score = (
        0.0
        if not references
        else float(chrf.corpus_score(hypotheses, [references]).score)
    )

    return {
        "ok": within_memory_limit,
        "mode": "full",
        "fixture_count": len(prompts),
        "elapsed_seconds": round(elapsed, 4),
        "output_tokens": total_output_tokens,
        "output_tokens_per_sec": round(output_tokens_per_sec, 4),
        "quality_metric": "chrf",
        "quality_fixture_count": len(references),
        "chrf_score": round(chrf_score, 4),
        "peak_metal_mb": peak_metal_mb,
        "max_peak_metal_mb": float(config.max_peak_metal_mb),
        "failure_reason": None if within_memory_limit else "memory_limit_exceeded",
    }


def mlx_lm_generate_text(model, tokenizer, prompt_tokens_batch, *, max_tokens: int):
    response = mlx_lm_batch_generate(
        model,
        tokenizer,
        prompt_tokens_batch,
        max_tokens=max_tokens,
    )
    return {
        "results": [{"text": text, "token_ids": []} for text in response.texts],
        "output_tokens": response.stats.generation_tokens,
    }


def load_module_from_path(path: Path, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to import module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def candidate_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:12]


def append_results_row(row: list[str]):
    ensure_results_header()
    with RESULTS_PATH.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t")
        writer.writerow(row)


def compare_candidate(config: Config, fixtures, description: str, generate_fn):
    if not INCUMBENT_PATH.exists():
        raise ValueError("Incumbent snapshot missing. Run `uv run prepare.py` first.")

    candidate_file_hash = candidate_hash(GENERATE_PATH)
    incumbent_file_hash = candidate_hash(INCUMBENT_PATH)
    model, tokenizer = load_model_and_tokenizer(config)
    mlx_lm_metrics = benchmark_generate_fn(
        mlx_lm_generate_text, model, tokenizer, config, fixtures
    )
    candidate_metrics = benchmark_generate_fn(generate_fn, model, tokenizer, config, fixtures)

    if candidate_file_hash == incumbent_file_hash:
        incumbent_metrics = dict(candidate_metrics)
    else:
        incumbent_module = load_module_from_path(
            INCUMBENT_PATH, f"incumbent_{time.time_ns()}"
        )
        incumbent_metrics = benchmark_generate_fn(
            incumbent_module.generate_text, model, tokenizer, config, fixtures
        )

    if not candidate_metrics["ok"]:
        status = "discard"
        decision_reason = candidate_metrics["failure_reason"]
    elif not incumbent_metrics["ok"]:
        raise RuntimeError("Incumbent benchmark failed; rerun `uv run prepare.py`.")
    elif candidate_file_hash == incumbent_file_hash:
        status = "incumbent"
        decision_reason = "same_as_incumbent"
    elif float(candidate_metrics["chrf_score"]) < float(incumbent_metrics["chrf_score"]):
        status = "discard"
        decision_reason = "quality_regression"
    elif float(candidate_metrics["output_tokens_per_sec"]) > float(
        incumbent_metrics["output_tokens_per_sec"]
    ):
        promote_candidate()
        status = "promoted"
        decision_reason = "throughput_win"
    else:
        status = "discard"
        decision_reason = "no_throughput_win"

    run_identifier = time.strftime("%Y%m%d-%H%M%S")
    append_results_row(
        [
            run_identifier,
            "full",
            candidate_file_hash,
            incumbent_file_hash,
            (
                f"{float(mlx_lm_metrics.get('output_tokens_per_sec', 0.0)):.4f}"
                if mlx_lm_metrics.get("ok")
                else ""
            ),
            f"{float(candidate_metrics.get('output_tokens_per_sec', 0.0)):.4f}",
            f"{float(incumbent_metrics.get('output_tokens_per_sec', 0.0)):.4f}",
            f"{float(candidate_metrics.get('peak_metal_mb', 0.0)):.1f}",
            status,
            description,
        ]
    )

    return {
        "run_id": run_identifier,
        "mode": "full",
        "description": description,
        "mlx_lm": mlx_lm_metrics,
        "candidate": candidate_metrics,
        "incumbent": incumbent_metrics,
        "status": status,
        "decision_reason": decision_reason,
    }
