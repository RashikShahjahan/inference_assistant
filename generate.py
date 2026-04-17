from __future__ import annotations

import argparse
import json

from prepare import (
    compare_candidate,
    load_config,
    load_fixtures,
    require_memory_limit,
    split_fixtures,
)


def generate_text(model, tokenizer, prompt_tokens_batch, *, max_tokens: int):
    import mlx.core as mx

    eos_token_ids = set(tokenizer.eos_token_ids)
    results: list[dict[str, object]] = []

    for prompt_tokens in prompt_tokens_batch:
        prompt = mx.array(prompt_tokens)
        if prompt.size == 0:
            raise ValueError("Prompt must contain at least one token")

        prompt_cache = model.make_cache() if hasattr(model, "make_cache") else None
        if prompt.size > 1:
            prefill_logits = model(prompt[:-1][None], cache=prompt_cache)
            mx.eval(prefill_logits)

        current = prompt[-1:][None]
        generated_token_ids: list[int] = []

        for _ in range(max_tokens):
            logits = model(current, cache=prompt_cache)
            next_token = mx.argmax(logits[:, -1, :], axis=-1)
            mx.eval(next_token)

            token = int(next_token.item())
            if token in eos_token_ids:
                break

            generated_token_ids.append(token)
            current = next_token[:, None]

        results.append(
            {
                "token_ids": generated_token_ids,
                "text": "",
            }
        )

    return results


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Benchmark the current generate.py candidate"
    )
    parser.add_argument("--full", action="store_true", help="Use the full fixture set")
    parser.add_argument(
        "--description",
        default="manual run",
        help="Short description of the candidate change",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    config = load_config()
    fixtures = load_fixtures()
    quick_fixtures, full_fixtures = split_fixtures(config, fixtures)
    require_memory_limit(config)

    mode = "full" if args.full else "quick"
    selected_fixtures = full_fixtures if args.full else quick_fixtures
    result = compare_candidate(config, mode, selected_fixtures, args.description)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
