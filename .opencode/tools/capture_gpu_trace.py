from __future__ import annotations

import argparse
import json

from generate import batch_generate
from inference_workflow import profile_batch_generate_metal
from prepare import (
    build_prompt,
    load_config,
    load_fixtures,
    load_model_and_tokenizer,
    max_tokens_for_fixture,
    require_memory_limit,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Capture a representative Metal trace for generate.py"
    )
    parser.add_argument(
        "--metal-profile-path",
        default="state/batch_generate_profile.gputrace",
        help="Write a Metal GPU trace for one representative batch_generate call",
    )
    parser.add_argument(
        "--metal-profile-fixture-index",
        type=int,
        default=0,
        help="Fixture index to use for representative Metal profiling",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    config = load_config()
    fixtures = load_fixtures()
    require_memory_limit(config)

    fixture_index = args.metal_profile_fixture_index
    if fixture_index < 0 or fixture_index >= len(fixtures):
        raise ValueError(
            f"metal profile fixture index {fixture_index} is out of range for {len(fixtures)} fixtures"
        )

    model, tokenizer = load_model_and_tokenizer(config)
    fixture = fixtures[fixture_index]
    prompt = build_prompt(tokenizer, config, fixture.source_text)
    result = profile_batch_generate_metal(
        batch_generate,
        model,
        tokenizer,
        [prompt],
        max_tokens=max_tokens_for_fixture(config, fixture),
        trace_path=args.metal_profile_path,
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
