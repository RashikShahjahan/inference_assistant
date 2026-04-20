from __future__ import annotations

import argparse
import json

from generate import generate_text
from inference_workflow import compare_candidate
from prepare import load_config, load_fixtures, require_memory_limit


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Benchmark the current generate.py")
    parser.add_argument(
        "--description",
        default="manual run",
        help="Short description of the current experiment",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    config = load_config()
    fixtures = load_fixtures()
    require_memory_limit(config)

    result = compare_candidate(config, fixtures, args.description, generate_text)
    print(json.dumps(result, indent=2))
    return 0 if result["status"] in {"promoted", "incumbent"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
