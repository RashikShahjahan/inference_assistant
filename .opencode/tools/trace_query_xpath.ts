import { tool } from "@opencode-ai/plugin"

import { runPythonTool } from "./_shared"

export default tool({
  description: "Export xctrace XML for a specific XPath",
  args: {
    trace_path: tool.schema
      .string()
      .default("state/batch_generate_profile.trace")
      .describe("Path to a .trace document, relative to repo root or absolute"),
    xpath: tool.schema
      .string()
      .describe("XPath passed through to xctrace export for targeted table export"),
  },
  async execute(args, context) {
    return runPythonTool(
      "trace_query_xpath.py",
      ["--trace-path", args.trace_path, "--xpath", args.xpath],
      {},
      context.worktree,
    )
  },
})
