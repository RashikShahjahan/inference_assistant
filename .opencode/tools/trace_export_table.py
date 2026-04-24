from __future__ import annotations

import argparse
import json

from trace_query_xpath import _tool_result, export_trace_xpath, resolve_repo_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Export xctrace XML for a trace table schema"
    )
    parser.add_argument(
        "--trace-path",
        default="state/batch_generate_profile.trace",
        help="Path to a .trace document, relative to repo root or absolute",
    )
    parser.add_argument(
        "--schema",
        required=True,
        help="Table schema name from the trace TOC, for example metal-gpu-intervals",
    )
    parser.add_argument(
        "--run-number",
        type=int,
        default=1,
        help="Trace run number to export from",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.run_number <= 0:
        raise ValueError("run_number must be positive")

    trace_path = resolve_repo_path(args.trace_path)
    xpath = f'/trace-toc/run[@number="{args.run_number}"]/data/table[@schema="{args.schema}"]'
    payload = export_trace_xpath(trace_path, xpath)
    payload["schema"] = args.schema
    payload["run_number"] = args.run_number
    print(json.dumps(_tool_result(payload), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
