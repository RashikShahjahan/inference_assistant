import { tool } from "@opencode-ai/plugin"

import { runPythonTool } from "./_shared"

export default tool({
  description: "Run the generate.py benchmark workflow",
  args: {
    description: tool.schema
      .string()
      .default("manual run")
      .describe("Short description for the benchmark run"),
  },
  async execute(args, context) {
    return runPythonTool(
      "benchmark_generate.py",
      ["--description", args.description],
      {},
      context.worktree,
    )
  },
})
