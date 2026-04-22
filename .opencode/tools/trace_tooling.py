from __future__ import annotations

import contextlib
import io
import json
import plistlib
import sqlite3
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]


@contextlib.contextmanager
def buffer_stderr_on_success():
    buffer = io.StringIO()
    with contextlib.redirect_stderr(buffer):
        try:
            yield
        except Exception:
            sys.stderr.write(buffer.getvalue())
            raise


def tool_result(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "output": json.dumps(payload, indent=2, sort_keys=True),
        "metadata": payload,
    }


def resolve_repo_path(path_str: str) -> Path:
    path = Path(path_str).expanduser()
    if not path.is_absolute():
        path = WORKSPACE_ROOT / path
    return path.resolve()


def path_kind(path: Path) -> str:
    if path.suffix == ".gputrace":
        return "gputrace"
    if path.is_dir():
        return "directory"
    return "file"


def scan_bundle(path: Path, *, max_files: int = 400) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    extension_counts: Counter[str] = Counter()
    sqlite_files: list[dict[str, Any]] = []
    parsed_metadata: list[dict[str, Any]] = []
    file_count = 0

    for file_path in sorted(path.rglob("*")):
        if file_count >= max_files:
            break
        if not file_path.is_file():
            continue
        file_count += 1
        rel_path = file_path.relative_to(path).as_posix()
        suffix = file_path.suffix.lower() or "<none>"
        extension_counts[suffix] += 1
        stat = file_path.stat()
        entry = {
            "path": rel_path,
            "size_bytes": stat.st_size,
            "suffix": suffix,
        }
        entries.append(entry)

        if suffix in {".sqlite", ".db"}:
            sqlite_files.append(
                {
                    **entry,
                    "tables": list_sqlite_tables(file_path),
                }
            )

        if suffix in {".plist", ".json"} and len(parsed_metadata) < 12:
            parsed = parse_metadata_file(file_path)
            if parsed is not None:
                parsed_metadata.append({"path": rel_path, "summary": parsed})

    return {
        "root": str(path),
        "scanned_file_count": file_count,
        "extension_counts": dict(extension_counts.most_common()),
        "files": entries,
        "sqlite_files": sqlite_files,
        "metadata_files": parsed_metadata,
        "truncated": file_count >= max_files,
    }


def parse_metadata_file(path: Path) -> dict[str, Any] | None:
    try:
        if path.suffix.lower() == ".plist":
            with path.open("rb") as handle:
                data = plistlib.load(handle)
        else:
            data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None

    if isinstance(data, dict):
        keys = list(data.keys())[:20]
        preview = {key: summarize_value(data[key]) for key in keys[:8]}
        return {"type": "dict", "keys": keys, "preview": preview}
    if isinstance(data, list):
        return {
            "type": "list",
            "length": len(data),
            "preview": [summarize_value(item) for item in data[:5]],
        }
    return {"type": type(data).__name__, "preview": summarize_value(data)}


def summarize_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {"type": "dict", "keys": list(value.keys())[:8]}
    if isinstance(value, list):
        return {"type": "list", "length": len(value)}
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return repr(value)


def list_sqlite_tables(database_path: Path) -> list[str]:
    try:
        with sqlite3.connect(database_path) as connection:
            rows = connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            ).fetchall()
    except sqlite3.Error:
        return []
    return [str(row[0]) for row in rows]


def search_bundle(path: Path, needle: str, *, limit: int = 50) -> dict[str, Any]:
    needle_lower = needle.lower()
    matches: list[dict[str, Any]] = []
    scanned_files = 0

    for file_path in sorted(path.rglob("*")):
        if len(matches) >= limit:
            break
        if not file_path.is_file():
            continue
        scanned_files += 1
        rel_path = file_path.relative_to(path).as_posix()
        suffix = file_path.suffix.lower()

        if suffix in {".plist", ".json", ".txt", ".xml", ".log", ".metal"}:
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            index = content.lower().find(needle_lower)
            if index >= 0:
                start = max(0, index - 120)
                end = min(len(content), index + 120)
                matches.append(
                    {
                        "path": rel_path,
                        "kind": "text",
                        "snippet": content[start:end].replace("\n", " "),
                    }
                )
            continue

        if suffix in {".sqlite", ".db"}:
            table_matches = search_sqlite(file_path, needle, limit=max(1, limit - len(matches)))
            for table_match in table_matches:
                matches.append({"path": rel_path, "kind": "sqlite", **table_match})
                if len(matches) >= limit:
                    break
            continue

        strings_match = search_binary_strings(file_path, needle)
        if strings_match is not None:
            matches.append({"path": rel_path, "kind": "binary-strings", "snippet": strings_match})

    return {
        "root": str(path),
        "needle": needle,
        "scanned_files": scanned_files,
        "match_count": len(matches),
        "matches": matches,
        "truncated": len(matches) >= limit,
    }


def search_sqlite(database_path: Path, needle: str, *, limit: int) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    try:
        with sqlite3.connect(database_path) as connection:
            tables = list_sqlite_tables(database_path)
            for table in tables:
                if len(results) >= limit:
                    break
                if needle.lower() in table.lower():
                    results.append({"table": table, "column": None, "value": f"table name matches '{needle}'"})
                    continue
                pragma_rows = connection.execute(f'PRAGMA table_info("{table}")').fetchall()
                text_columns = [row[1] for row in pragma_rows if str(row[2]).upper() in {"TEXT", "VARCHAR", "CHAR", ""}]
                for column in text_columns[:8]:
                    if len(results) >= limit:
                        break
                    query = (
                        f'SELECT "{column}" FROM "{table}" '
                        f'WHERE CAST("{column}" AS TEXT) LIKE ? LIMIT 3'
                    )
                    rows = connection.execute(query, (f"%{needle}%",)).fetchall()
                    for row in rows:
                        value = str(row[0])
                        results.append(
                            {
                                "table": table,
                                "column": column,
                                "value": value[:240],
                            }
                        )
                        if len(results) >= limit:
                            break
    except sqlite3.Error:
        return results
    return results


def search_binary_strings(path: Path, needle: str) -> str | None:
    try:
        completed = subprocess.run(
            ["strings", "-a", "-n", "4", str(path)],
            check=True,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None

    needle_lower = needle.lower()
    for line in completed.stdout.splitlines():
        if needle_lower in line.lower():
            return line[:240]
    return None


def query_sqlite(database_path: Path, sql: str, *, limit: int) -> dict[str, Any]:
    with sqlite3.connect(database_path) as connection:
        cursor = connection.execute(sql)
        column_names = [description[0] for description in (cursor.description or [])]
        rows = cursor.fetchmany(limit)
    return {
        "database": str(database_path),
        "sql": sql,
        "columns": column_names,
        "row_count": len(rows),
        "rows": [list(row) for row in rows],
        "truncated": len(rows) >= limit,
    }
