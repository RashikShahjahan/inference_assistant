import { tool } from "@opencode-ai/plugin"

import { runPythonTool } from "./_shared"

export default tool({
  description: "Open a gputrace bundle and summarize structure",
  args: {
    trace_path: tool.schema
      .string()
      .describe("Path to a .gputrace bundle, relative to repo root or absolute"),
  },
  async execute(args, context) {
    return runPythonTool("trace_open.py", ["--trace-path", args.trace_path], {}, context.worktree)
  },
})
