from __future__ import annotations

import argparse
import json

from trace_tooling import buffer_stderr_on_success, query_sqlite, resolve_repo_path, tool_result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a read-only SQLite query on a trace-bundle database")
    parser.add_argument("--database-path", required=True, help="Path to a .sqlite or .db file")
    parser.add_argument("--sql", required=True, help="Read-only SELECT query to execute")
    parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help="Maximum number of rows to return",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()

    with buffer_stderr_on_success():
        database_path = resolve_repo_path(args.database_path)
        sql = args.sql.strip()
        if not database_path.exists():
            raise FileNotFoundError(f"Database path does not exist: {database_path}")
        if not sql.lower().startswith("select"):
            raise ValueError("Only SELECT queries are allowed")

        payload = query_sqlite(database_path, sql, limit=max(1, args.limit))
        print(json.dumps(tool_result(payload), indent=2))
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
