from __future__ import annotations

import argparse
import json

from trace_tooling import buffer_stderr_on_success, resolve_repo_path, search_bundle, tool_result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Search inside a .gputrace bundle for strings or labels")
    parser.add_argument("--trace-path", required=True, help="Path to a .gputrace bundle")
    parser.add_argument("--needle", required=True, help="Substring to search for")
    parser.add_argument(
        "--limit",
        type=int,
        default=50,
        help="Maximum number of matches to return",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()

    with buffer_stderr_on_success():
        trace_path = resolve_repo_path(args.trace_path)
        if not trace_path.exists():
            raise FileNotFoundError(f"Trace path does not exist: {trace_path}")
        if trace_path.suffix != ".gputrace":
            raise ValueError("trace_search only supports .gputrace inputs in this repository")
        if not trace_path.is_dir():
            raise ValueError("trace_search expects a trace bundle directory")

        payload = search_bundle(trace_path, args.needle, limit=max(1, args.limit))
        print(json.dumps(tool_result(payload), indent=2))
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
