import { tool } from "@opencode-ai/plugin"

import { runPythonTool } from "./_shared"

export default tool({
  description: "Run a read-only query on trace SQLite data",
  args: {
    database_path: tool.schema
      .string()
      .describe("Path to a .sqlite or .db file, relative to repo root or absolute"),
    sql: tool.schema
      .string()
      .describe("Read-only SELECT statement to execute"),
    limit: tool.schema
      .number()
      .int()
      .positive()
      .default(100)
      .describe("Maximum number of rows to return"),
  },
  async execute(args, context) {
    return runPythonTool(
      "trace_sqlite_query.py",
      ["--database-path", args.database_path, "--sql", args.sql, "--limit", String(args.limit)],
      {},
      context.worktree,
    )
  },
})
