from __future__ import annotations

import argparse
import json

from trace_tooling import (
    buffer_stderr_on_success,
    path_kind,
    resolve_repo_path,
    scan_bundle,
    tool_result,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Open a .gputrace bundle and summarize its structure")
    parser.add_argument("--trace-path", required=True, help="Path to a .gputrace bundle")
    return parser


def main() -> int:
    args = build_parser().parse_args()

    with buffer_stderr_on_success():
        trace_path = resolve_repo_path(args.trace_path)
        if not trace_path.exists():
            raise FileNotFoundError(f"Trace path does not exist: {trace_path}")
        if trace_path.suffix != ".gputrace":
            raise ValueError("trace_open only supports .gputrace inputs in this repository")

        payload = {
            "trace_path": str(trace_path),
            "kind": path_kind(trace_path),
            "bundle": scan_bundle(trace_path),
        }

        print(json.dumps(tool_result(payload), indent=2))
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
