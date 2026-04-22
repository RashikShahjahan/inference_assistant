import { tool } from "@opencode-ai/plugin"

import { runPythonTool } from "./_shared"

export default tool({
  description: "Search a gputrace bundle for strings",
  args: {
    trace_path: tool.schema
      .string()
      .describe("Path to a .gputrace bundle, relative to repo root or absolute"),
    needle: tool.schema
      .string()
      .describe("Substring to search for in text, sqlite, or extracted binary strings"),
    limit: tool.schema
      .number()
      .int()
      .positive()
      .default(50)
      .describe("Maximum number of matches to return"),
  },
  async execute(args, context) {
    return runPythonTool(
      "trace_search.py",
      ["--trace-path", args.trace_path, "--needle", args.needle, "--limit", String(args.limit)],
      {},
      context.worktree,
    )
  },
})
